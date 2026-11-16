"""The deployed LiveKit worker's connection to the canonical FRIDAY brain.

No second tool registry or memory store, no automatic POST retries, no owner
credential minted by the microphone. The origin-only chat route must retain
boss_verified=False. Transport uncertainty is never reported as non-execution.
"""
from __future__ import annotations

import asyncio
import hashlib
import itertools
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("friday.voice.brain_bridge")

try:  # TASK-IG-VOI-01: the confirmation gate is pure stdlib; if it
    # ever fails to import, the bridge degrades to ungated (its pre-
    # IG-VOI-01 behaviour) instead of taking voice down with it.
    from friday.voice import confirmation_policy as _confirmation_policy
except Exception:  # pragma: no cover - defensive, mirrors _voice_tools
    _confirmation_policy = None

BRAIN_URL = "http://127.0.0.1:10000/api/chat"
BRAIN_ORIGIN = "http://127.0.0.1:10000"

# TASK-VOI-003: a voice turn cannot wait out the old 230 s budget — while
# the tool call is pending, the caller's turn never completes and every
# later utterance queues behind it (the 2026-11-14 call wedged exactly
# this way). VOI-003 set 60 s from that evening's worst measured brain
# call (~26 s under swap load) with headroom; on timeout the bridge
# returns "unconfirmed" and the model SPEAKS that, completing the turn
# honestly.
#
# TASK-FRD-012: 60 s is empirically BELOW the brain's real completion
# envelope, so it manufactured the stranding it was meant to prevent.
# Measured /api/chat turn times (journal + live probes, 2026-11-16):
# healthy pool — 1.4-9.4 s (delegation 9.38 s, remember 9.19 s, recall
# 2.14 s); degraded pool (Gemini-pool exhaustion → failover cascade,
# FRD-011 journal-proven) — 76 s (FRD-005 re-run #3 delegation) and
# 77.48 s (re-run #2 follow-up). At 60 s the bridge hung up on turns
# the brain went on to COMPLETE, and the finished answer was discarded
# into a closed stream (defect D6). The foreground budget is therefore
# 105 s — the worst measured degraded turn plus ~35% — and a hard
# transport cap of 240 s behind it leashes the TASK-FRD-012 background
# continuation: on a foreground timeout the honest "unconfirmed" still
# returns at the budget (the VOI-003 contract is unchanged), but the
# brain's eventual answer is no longer thrown away — it is filed as a
# late result for in-session delivery (see _dispatch).
def _brain_timeout_s() -> float:
    try:
        return float(os.getenv("FRIDAY_VOICE_BRAIN_TIMEOUT_S", "105") or 105)
    except ValueError:
        return 105.0


BRAIN_TIMEOUT_S = _brain_timeout_s()


def _brain_hard_timeout_s() -> float:
    try:
        return float(os.getenv("FRIDAY_VOICE_BRAIN_HARD_TIMEOUT_S", "240") or 240)
    except ValueError:
        return 240.0


BRAIN_HARD_TIMEOUT_S = _brain_hard_timeout_s()


# TASK-FRD-011: one voice conversation must not race itself. In FRD-005
# re-run 20261116-103839 the realtime model issued TWO execute_friday_task
# calls concurrently (one per queued user utterance); the two brain turns
# contended at the brain AND at Stratex, both returned the byte-identical
# timeout answer, and the model spoke it twice (defect D2). The bridge
# therefore serializes its sends, and a verbatim re-issue of a request
# whose call just completed (the interruption-retry shape: the SDK
# cancelled a speech at 10:43:30 in that run and the model re-asked)
# reuses the completed result inside a short window instead of running
# a second identical brain turn. Only settled outcomes are reused —
# confirmation_required must always reach the gate again (the owner's
# confirmation is what the re-issue carries), and refused/pending are
# never served from the window.
def _dedupe_window_s() -> float:
    try:
        return float(os.getenv("FRIDAY_VOICE_BRIDGE_DEDUPE_S", "15") or 15)
    except ValueError:
        return 15.0


DEDUPE_WINDOW_S = _dedupe_window_s()
_CACHEABLE_STATES = {"answered", "failed"}


# TASK-FRD-012: every bridge call carries a turn id (process-monotonic
# sequence + a short request hash) and every hop — send, gate verdict,
# cache reuse, result, foreground timeout, late landing — is journaled
# under it. In FRD-005 re-run #3 the bridge logged NOTHING, so a
# completed brain answer that never reached the voice session could
# not be attributed to any hop (defect D6's instrumentation gap).
_TURN_COUNTER = itertools.count(1)


def _new_turn_id(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:6]
    return f"b{next(_TURN_COUNTER)}-{digest}"


# TASK-FRD-012: settled results that land AFTER their foreground call
# already returned (foreground timeout or caller cancellation) are
# filed here instead of being discarded. The worker drains the
# registry on its watchdog pass and delivers each entry into the live
# session. Module-level on purpose: a watchdog session rebuild creates
# a fresh bridge, and a result earned by the old bridge must survive it.
_LATE_RESULTS: list[dict[str, Any]] = []
# States worth delivering late: a settled outcome the owner has not
# heard. A late "unconfirmed" adds nothing — the owner already heard
# the foreground one — so it is journaled only, never filed.
_LATE_DELIVERABLE_STATES = {"answered", "failed", "refused"}


def pop_late_results() -> list[dict[str, Any]]:
    """Drain the late-result registry (each entry is delivered once)."""
    drained = list(_LATE_RESULTS)
    _LATE_RESULTS.clear()
    return drained


# TASK-FRD-014 (D10): a recall result's spoken form must carry the
# recalled fact itself. The brain's recall gate normally sets
# spoken_summary to the direct answer; this guard is the bridge-side
# enforcement for any recall result that arrives without one (or with
# a summary that lost the fact): the spoken_reply is replaced with a
# templated direct answer built from metadata.fact, the way the fixed
# greeting line is templated — never left for the voice model to mine
# out of a bullet list (FRD-005 re-run #4: the spoken recall answer
# was "I have your favorite color safely recorded in my memory" and
# never stated 'teal').
_FACT_STOPWORDS = {
    "your", "yours", "that", "this", "with", "from", "have", "what",
    "when", "boss", "mine", "called", "about", "favorite", "favourite",
}


def _fact_value_tokens(fact: str) -> list[str]:
    """The value-bearing tokens of a stored fact: the words after the
    last copula ("my favorite color is teal." -> ["teal"]), falling
    back to all distinctive tokens when there is no copula."""
    import re as _re

    low = fact.lower()
    parts = _re.split(r"\b(?:is|are|was|were)\b", low)
    tail = parts[-1] if len(parts) > 1 else low
    tokens = [
        t for t in _re.findall(r"[a-z0-9]+", tail)
        if len(t) >= 3 and t not in _FACT_STOPWORDS
    ]
    if not tokens:
        tokens = [
            t for t in _re.findall(r"[a-z0-9]+", low)
            if len(t) >= 4 and t not in _FACT_STOPWORDS
        ]
    return tokens


def _spoken_fact_form(fact: str) -> str:
    """The templated spoken form of a stored fact: only the leading
    first-person possessive is rewritten ("my favorite color is
    teal." -> "Your favorite color is teal."); the fact stays
    verbatim. Mirrors the brain-side transform in the recall gate."""
    text = fact.strip()
    low = text.lower()
    if low.startswith("my "):
        return "Your " + text[3:]
    if low.startswith("i'm "):
        return "You're " + text[4:]
    if low.startswith("i "):
        return "You " + text[2:]
    return text


# TASK-FRD-015 (D11): a remember request composed from a PARTIAL turn
# must never reach the brain. FRD-005 re-run #5 (production run
# 20261116-175800): Gemini's activity detection (silence 500 ms, end-of-
# speech HIGH — pinned for speed in TASK-VOI-012) split one utterance
# into two finals 2.6 s apart; the model acted on the first fragment
# alone ("Please remember this for me.") and, lacking the fact, composed
# the payload from the PREVIOUS turn's content ("Please remember that
# the current time in Tokyo is 9:29 PM."). The brain's remember gate
# stores any payload unconditionally, so a junk fact was written and
# the spoken confirmation named the junk. Nothing in the dispatch path
# compared the composed payload with what the user actually said in
# the current turn — the guard below is that comparison, placed here
# for the same reason as the recall fact guard above: the bridge is
# the last deterministic checkpoint before the brain.
#
# Scope, evidence-picked: REMEMBER-class requests only — the one class
# whose gate performs an unconditional state write. Forget is excluded
# (its gate no-ops on a non-matching subject and answers honestly), and
# reads/delegations corrupt nothing: their results are spoken, so the
# owner hears and corrects them. A memory write is silent and durable.
#
# Grounding rule: the fact the brain WOULD store (extracted with a
# mirror of the brain's own classification + payload extraction) must
# be grounded in the current turn's user transcript, supplied by the
# worker (user segments since the last assistant item plus the latest
# STT final): at least one content token present AND at least half of
# the fact's content tokens present. The D11 junk scores 0%; a faithful
# composition scores ~100%; the half threshold leaves room for the
# model's sanctioned normalizations (fleet-name corrections, spelling
# variants, light paraphrase). Grounded requests dispatch immediately
# — the check is a token-set comparison, so the normal remember pays
# ~0 ms. Only an UNGROUNDED remember pays: a settle window (default
# 3.5 s, the D11 split gap was 2.6 s) waits for the continuation
# segment; if it grounds the payload the request dispatches, if it
# arrives without grounding it the call returns "superseded" (nothing
# submitted), and if no continuation arrives the write is refused with
# a spoken request to state the fact. Deliberate cost: a remember
# whose fact was stated in an EARLIER turn ("remember that", pointing
# back) is refused the same way — a memory write must be grounded in
# the turn that requests it.
def _fragment_settle_s() -> float:
    try:
        return float(os.getenv("FRIDAY_VOICE_FRAGMENT_SETTLE_S", "3.5") or 3.5)
    except ValueError:
        return 3.5


FRAGMENT_SETTLE_S = _fragment_settle_s()
_FRAGMENT_POLL_S = 0.15

# Mirrors of the brain's memory-gate patterns (api/server.py
# _dispatch_command): recall is checked first there ("do you remember"
# is a question, not a store command), so it is checked first here —
# a recall-shaped request is never treated as a write.
_RECALL_PATTERNS = (
    "what do you remember", "do you remember", "you remember",
    "what do you know about me", "what do you know about my",
    "do you have memory", "do you have any memory", "your memory",
    "what did i say", "what did i tell you", "what have i told you",
    "my preferences", "recall my", "recall what",
    "what was my", "what is my", "what's my", "what did you store",
    "what did you save", "what have you stored", "what have you saved",
)
_REMEMBER_PATTERNS = (
    "remember this", "remember that", "remember:", "remember ,",
    "note that", "don't forget", "dont forget", "keep in mind",
    "memorize this", "memorise this", "store this", "remember it",
)
_REMEMBER_PREFIXES = (
    "remember this", "remember that", "remember it", "remember",
    "note that", "don't forget that", "dont forget that",
    "don't forget", "dont forget", "keep in mind that", "keep in mind",
    "memorize this", "memorise this", "store this",
)
# FRD-014's spelling canonicalization, mirrored (matching only).
_FRAGMENT_SPELLING = {"favourite": "favorite", "colour": "color"}
_FRAGMENT_STOPWORDS = _FACT_STOPWORDS | {
    "please", "remember", "that", "this", "with", "from", "have",
    "what", "when", "your", "yours", "mine", "about", "called",
    "just", "will", "would", "there", "their", "them", "then",
    "than", "into", "onto", "over", "under", "again", "once",
    "the", "and", "but", "for", "are", "was", "were", "been",
    "has", "had", "not", "all", "any", "can", "could", "should",
}


def _content_tokens(text: str) -> set[str]:
    """Content tokens of a text: punctuation-stripped (the FRD-014
    lesson), spelling-canonicalized, length >= 3, stopwords removed."""
    import re as _re

    tokens = set()
    for raw in _re.findall(r"[a-z0-9]+", (text or "").lower()):
        tok = _FRAGMENT_SPELLING.get(raw, raw)
        if len(tok) >= 3 and tok not in _FRAGMENT_STOPWORDS:
            tokens.add(tok)
    return tokens


def _remember_fact_payload(request: str) -> "str | None":
    """The fact the brain's remember gate WOULD store for this
    request, or None when the request is not remember-class.

    Mirrors api/server.py's classification (recall wins) and payload
    extraction (vocative strip, earliest/longest command-phrase cut,
    "boss / for me" residue, trailing meta-instruction drop). An empty
    string means remember-class with NO fact stated — ungrounded by
    construction."""
    import re as _re

    raw_cmd = (request or "").strip()
    cmd = raw_cmd.lower()
    if any(p in cmd for p in _RECALL_PATTERNS):
        return None
    is_remember = cmd.startswith("remember ") or any(
        cmd.startswith(p) or f" {p} " in f" {cmd} " or f" {p}:" in f" {cmd}"
        for p in _REMEMBER_PATTERNS
    )
    if not is_remember:
        return None
    payload = raw_cmd
    voc = _re.match(r"^\s*(?:hey\s+|ok\s+|okay\s+)?friday[\s,:\-]+",
                    raw_cmd, flags=_re.IGNORECASE)
    if voc:
        payload = raw_cmd[voc.end():]
    low_payload = payload.lower()
    cut, cut_len = -1, 0
    for pfx in _REMEMBER_PREFIXES:
        idx = low_payload.find(pfx)
        if idx >= 0 and (cut < 0 or idx < cut
                         or (idx == cut and len(pfx) > cut_len)):
            cut, cut_len = idx, len(pfx)
    if cut >= 0:
        payload = payload[cut + cut_len:]
    payload = payload.strip().lstrip(":, -–").strip()
    residue = _re.match(r"^(?:boss|for me)(?:[\s,:\-]+|\.\s*)",
                        payload, flags=_re.IGNORECASE)
    if residue:
        payload = payload[residue.end():]
    sentences = _re.split(r"(?<=[.!?])\s+", payload)
    if len(sentences) > 1 and _re.match(
        r"^(?:please\s+)?(?:confirm|acknowledge|let me know|tell me when|verify)\b",
        sentences[-1].strip(), flags=_re.IGNORECASE,
    ):
        payload = " ".join(sentences[:-1]).strip()
    return " ".join(payload.split()).strip()


def _payload_grounded(payload: str, turn_text: str) -> bool:
    """True when the fact payload is grounded in the current turn's
    user transcript: at least one of its content tokens was actually
    said this turn AND at least half of them were."""
    tokens = _content_tokens(payload)
    if not tokens:
        # No checkable content (a bare short value): require the
        # payload itself, normalized, inside the turn text.
        needle = " ".join((payload or "").lower().split()).strip(" .")
        hay = " ".join((turn_text or "").lower().split())
        return bool(needle) and needle in hay
    heard = _content_tokens(turn_text)
    present = tokens & heard
    return bool(present) and len(present) / len(tokens) >= 0.5


def consolidate_turn_text(transcript_items, pending_text: str) -> str:
    """The current turn's user text from the worker's records: user
    items since the last assistant item (the accumulated segments of
    the turn in progress), plus the latest STT final when it is newer
    than the last committed item. Pure helper — the worker's provider
    closure feeds it the shared turn dict's contents."""
    segments: list[str] = []
    for role, text in reversed(list(transcript_items or [])):
        if role == "assistant":
            break
        if role == "user" and text:
            segments.append(text)
    segments.reverse()
    pending = (pending_text or "").strip()
    if pending and (not segments or segments[-1].strip() != pending):
        segments.append(pending)
    return " ".join(segments)


def _recall_fact_guard(meta: dict[str, Any], state: str, spoken: str) -> str:
    """Return the spoken_reply for a brain result, enforcing the
    recall-fact contract: for an answered memory_recall result whose
    metadata carries the recalled fact, the spoken form must contain
    the fact's value tokens; if it does not, it is replaced with the
    templated direct answer built from the fact."""
    if state != "answered" or not meta.get("memory_recall"):
        return spoken
    fact = str(meta.get("fact") or "").strip()
    if not fact:
        return spoken
    tokens = _fact_value_tokens(fact)
    low_spoken = spoken.lower()
    if tokens and all(t in low_spoken for t in tokens):
        return spoken
    guarded = _spoken_fact_form(fact)
    logger.info(
        "VOICE brain bridge recall fact guard: spoken_reply did not "
        "carry the recalled fact; replaced with the templated direct "
        "answer %r", guarded[:120],
    )
    return guarded


class VoiceBrainBridge:
    def __init__(self, client: httpx.AsyncClient | None = None,
                 confirmation_gate: Any = None,
                 result_observer: Any = None,
                 turn_transcript_provider: Any = None) -> None:
        self.client = client
        # TASK-FRD-015: the worker supplies a callable returning
        # (current-turn user text, version) so the fragment guard can
        # ground remember payloads in what the user actually said this
        # turn. Absent (non-voice callers, tests) the guard is inert —
        # the pre-FRD-015 behaviour — mirroring how the confirmation
        # gate degrades instead of taking the path down.
        self._turn_provider = turn_transcript_provider
        # TASK-FRD-012: the worker observes every foreground result so
        # its delivery watch can catch a settled result the model
        # never verbalized (defect D7). Observer failures must never
        # break a call — every notification is guarded.
        self._observer = result_observer
        # TASK-IG-VOI-01: one gate per bridge (i.e. per session build).
        # A watchdog rebuild creates a fresh bridge, so a confirmation
        # earned before a rebuild is asked again — fail-closed.
        if confirmation_gate is not None:
            self._gate = confirmation_gate
        elif _confirmation_policy is not None:
            self._gate = _confirmation_policy.gate_from_env()
        else:
            self._gate = None
        # TASK-FRD-011: send serialization + last-result reuse window.
        self._send_lock = asyncio.Lock()
        self._last_key = ""
        self._last_result: dict[str, Any] | None = None
        self._last_ts = 0.0
        self._last_turn_id = ""

    def _cached_result(self, key: str) -> dict[str, Any] | None:
        if (
            self._last_result is not None
            and key == self._last_key
            and (time.monotonic() - self._last_ts) <= DEDUPE_WINDOW_S
        ):
            return dict(self._last_result)
        return None

    def _notify_observer(self, turn_id: str, text: str,
                         result: dict[str, Any]) -> None:
        if self._observer is None:
            return
        try:
            self._observer({
                "turn_id": turn_id,
                "request": text[:120],
                "state": result.get("state"),
                "spoken_reply": result.get("spoken_reply") or "",
                "late_pending": bool(result.get("late_pending")),
                "ts": time.time(),
            })
        except Exception:  # the watch is advisory; the call is not
            logger.warning("VOICE brain bridge: result observer failed "
                           "for turn %s", turn_id, exc_info=True)

    def _settle(self, turn_id: str, text: str, result: dict[str, Any],
                started: float) -> dict[str, Any]:
        """Journal + observe + return one foreground outcome."""
        result = dict(result)
        result.setdefault("turn_id", turn_id)
        logger.info(
            "VOICE brain bridge result turn=%s state=%s elapsed=%.2fs "
            "reply_chars=%d", turn_id, result.get("state"),
            time.monotonic() - started,
            len(result.get("spoken_reply") or ""),
        )
        self._notify_observer(turn_id, text, result)
        return result

    def _turn_snapshot(self) -> "tuple[str, Any] | None":
        """(current-turn user text, version) from the worker's
        provider, or None when there is no provider or it fails —
        the guard degrades open, never breaks a call."""
        if self._turn_provider is None:
            return None
        try:
            text, version = self._turn_provider()
            return str(text or ""), version
        except Exception:
            logger.warning("VOICE brain bridge fragment guard: turn "
                           "transcript provider failed; guard inert "
                           "for this call", exc_info=True)
            return None

    async def _fragment_guard(self, text: str,
                              turn_id: str) -> "dict[str, Any] | None":
        """TASK-FRD-015 (D11): the split-final guard for remember-class
        requests. Returns None when the request may dispatch (not
        remember-class, no provider, or the payload is grounded in
        the current turn's transcript), else the settled result to
        return WITHOUT dispatching: "superseded" when the turn
        continued under this call, "refused" when the settle window
        expired with the payload still ungrounded."""
        payload = _remember_fact_payload(text)
        if payload is None:
            return None
        snapshot = self._turn_snapshot()
        if snapshot is None:
            return None
        turn_text, version = snapshot
        if _payload_grounded(payload, turn_text):
            return None
        logger.info(
            "VOICE brain bridge fragment guard turn=%s: remember "
            "payload %r is NOT grounded in the current turn %r — "
            "holding for end-of-turn consolidation (settle %.1fs)",
            turn_id, payload[:120], turn_text[:120], FRAGMENT_SETTLE_S,
        )
        deadline = time.monotonic() + FRAGMENT_SETTLE_S
        while time.monotonic() < deadline:
            await asyncio.sleep(_FRAGMENT_POLL_S)
            current = self._turn_snapshot()
            if current is None:
                return None
            new_text, new_version = current
            if new_version == version:
                continue
            # The turn continued. If the consolidated turn grounds
            # THIS payload after all, it may dispatch; otherwise this
            # call was composed from a fragment and is abandoned —
            # the model hears the complete turn and re-issues.
            if _payload_grounded(payload, new_text):
                logger.info(
                    "VOICE brain bridge fragment guard turn=%s: the "
                    "consolidated turn grounds the payload — "
                    "dispatching", turn_id,
                )
                return None
            logger.info(
                "VOICE brain bridge fragment guard turn=%s: turn "
                "continued (now %r) without grounding the payload — "
                "superseded, nothing submitted", turn_id,
                new_text[:120],
            )
            return {
                "state": "superseded",
                "spoken_reply": "",
                "fragment_guard": True,
                "model_note": (
                    "This request was NOT submitted: it was composed "
                    "from an incomplete user turn, and the fact it "
                    "carries was not in what the user said. The user "
                    "has continued speaking. Say nothing about this "
                    "result; listen to the complete request and, if "
                    "it is still a remember request, call again with "
                    "the fact exactly as the user stated it."
                ),
            }
        logger.info(
            "VOICE brain bridge fragment guard turn=%s: settle window "
            "expired, payload still ungrounded — refused, nothing "
            "submitted", turn_id,
        )
        return {
            "state": "refused",
            "spoken_reply": (
                "I haven't stored that, Boss — I didn't hear the fact "
                "itself in what you just said. Tell me the fact and "
                "I'll lock it in."
            ),
            "fragment_guard": True,
        }

    async def execute(self, request: str) -> dict[str, Any]:
        text = (request or "").strip()
        turn_id = _new_turn_id(text)
        started = time.monotonic()
        if not text or len(text) > 4000:
            return self._settle(turn_id, text, {"state": "refused", "spoken_reply": "Please give me a request between 1 and 4000 characters. Nothing was submitted."}, started)
        if self._gate is not None:
            # The gate runs BEFORE anything is submitted: a gated
            # request has caused no side effect anywhere when the
            # owner hears the confirmation question.
            decision = self._gate.check(text)
            if decision.verdict == _confirmation_policy.CONFIRM:
                logger.info(
                    "VOICE brain bridge gate turn=%s "
                    "verdict=confirmation_required (nothing submitted)",
                    turn_id,
                )
                return self._settle(turn_id, text, {
                    "state": "confirmation_required",
                    "spoken_reply": decision.question,
                    "confirmation_required": True,
                    "action_summary": decision.classification.action_summary,
                    "completion_verified": False,
                }, started)
        # TASK-FRD-015: the split-final guard runs after the
        # confirmation gate (gate semantics unchanged) and before the
        # reuse window: a superseded/refused outcome is never cached,
        # and a grounded request still reaches the reuse check below.
        guard_result = await self._fragment_guard(text, turn_id)
        if guard_result is not None:
            return self._settle(turn_id, text, guard_result, started)
        # TASK-FRD-011: the gate above has run for THIS call; only the
        # send is serialized/reused, so a confirmed re-issue still passes
        # the gate on its own merits before it can reuse or send.
        key = " ".join(text.split()).casefold()
        cached = self._cached_result(key)
        if cached is not None:
            logger.info(
                "VOICE brain bridge reuse turn=%s — settled result of "
                "turn=%s served from the reuse window", turn_id,
                self._last_turn_id or "?",
            )
            return self._settle(turn_id, text, cached, started)
        async with self._send_lock:
            # A concurrent identical call may have completed while this
            # one waited for the lock — reuse its result, never re-send.
            cached = self._cached_result(key)
            if cached is not None:
                logger.info(
                    "VOICE brain bridge reuse turn=%s — settled result "
                    "of turn=%s served from the reuse window", turn_id,
                    self._last_turn_id or "?",
                )
                return self._settle(turn_id, text, cached, started)
            result = await self._dispatch(text, turn_id)
            if result.get("state") in _CACHEABLE_STATES:
                self._last_key = key
                self._last_result = result
                self._last_ts = time.monotonic()
                self._last_turn_id = turn_id
            return self._settle(turn_id, text, result, started)

    async def _dispatch(self, text: str, turn_id: str) -> dict[str, Any]:
        """Send one brain request under the foreground budget.

        TASK-FRD-012: the HTTP exchange runs as its own shielded task.
        If the foreground budget expires — or the caller is cancelled
        (the realtime SDK cancels a tool call on interruption) — the
        exchange is NOT torn down: it continues in the background
        under the hard transport cap, and a settled outcome is filed
        as a late result instead of being discarded (defect D6: the
        76 s delegation turn of FRD-005 re-run #3 completed 16 s after
        the old 60 s budget hung up on it, into a closed stream).
        The foreground still returns the honest "unconfirmed" at the
        budget — the continuation adds the follow-through, it does
        not soften the timeout.
        """
        logger.info(
            "VOICE brain bridge send turn=%s chars=%d budget=%.0fs "
            "request=%r", turn_id, len(text), BRAIN_TIMEOUT_S, text[:80],
        )
        started = time.monotonic()
        task = asyncio.ensure_future(self._send_guarded(text))

        def _arm_late_filing() -> None:
            # Registered ONLY at the moment the foreground abandons
            # the wait (below), never before: a callback registered
            # up front races the awaiting coroutine's resumption and
            # files results the foreground is about to return itself.
            def _file(done_task: "asyncio.Task[dict[str, Any]]") -> None:
                try:
                    result = done_task.result()
                except Exception:
                    logger.warning(
                        "VOICE brain bridge late result turn=%s — the "
                        "background send failed outright", turn_id,
                        exc_info=True,
                    )
                    return
                self._file_late_result(turn_id, text, result,
                                       time.monotonic() - started)

            task.add_done_callback(_file)

        try:
            return await asyncio.wait_for(
                asyncio.shield(task), timeout=BRAIN_TIMEOUT_S)
        except asyncio.TimeoutError:
            _arm_late_filing()
            logger.error(
                "VOICE brain bridge timeout turn=%s after %.2fs "
                "(budget %.0fs) — honest unconfirmed returned; "
                "background continuation armed", turn_id,
                time.monotonic() - started, BRAIN_TIMEOUT_S,
            )
            return {"state": "unconfirmed",
                    "spoken_reply": "I lost contact with FRIDAY's brain. The outcome is unconfirmed. Please check the task history before repeating an action.",
                    "late_pending": True}
        except asyncio.CancelledError:
            _arm_late_filing()
            logger.warning(
                "VOICE brain bridge send turn=%s caller cancelled "
                "after %.2fs — background continuation armed", turn_id,
                time.monotonic() - started,
            )
            raise

    def _file_late_result(self, turn_id: str, text: str,
                          result: dict[str, Any], brain_elapsed: float) -> None:
        state = result.get("state")
        if state in _CACHEABLE_STATES:
            # A verbatim re-issue inside the window now reuses the
            # landed answer instead of re-running the brain turn
            # (TASK-FRD-011 semantics, extended to late landings).
            self._last_key = " ".join(text.split()).casefold()
            self._last_result = result
            self._last_ts = time.monotonic()
            self._last_turn_id = turn_id
        if state in _LATE_DELIVERABLE_STATES:
            logger.error(
                "VOICE brain bridge late result turn=%s state=%s "
                "brain_elapsed=%.2fs — filed for in-session delivery",
                turn_id, state, brain_elapsed,
            )
            _LATE_RESULTS.append({
                "turn_id": turn_id,
                "state": state,
                "spoken_reply": result.get("spoken_reply") or "",
                "request": text[:120],
                "landed_ts": time.time(),
            })
        else:
            logger.error(
                "VOICE brain bridge late result turn=%s state=%s "
                "brain_elapsed=%.2fs — nothing new to deliver (the "
                "foreground outcome already said it)", turn_id, state,
                brain_elapsed,
            )

    async def _send_guarded(self, text: str) -> dict[str, Any]:
        try:
            if self.client is None:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                    return await self._send(client, text)
            return await self._send(self.client, text)
        except httpx.HTTPError:
            return {"state": "unconfirmed", "spoken_reply": "I lost contact with FRIDAY's brain. The outcome is unconfirmed. Please check the task history before repeating an action."}

    async def _send(self, client: httpx.AsyncClient, text: str) -> dict[str, Any]:
        # The same endpoint used by chat performs memory retrieval, authorization,
        # task dispatch and conversation persistence. No control token is passed.
        # TASK-FRD-012: the transport timeout is the HARD cap, not the
        # foreground budget — the foreground wait lives in _dispatch,
        # and this exchange may legitimately outlive it as a
        # background continuation.
        async with client.stream("POST", BRAIN_URL, json={"message": text},
                                 headers={"Origin": BRAIN_ORIGIN}, timeout=BRAIN_HARD_TIMEOUT_S) as response:
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 65536:
                    return {"state": "unconfirmed", "spoken_reply": "FRIDAY returned an oversized answer. Please inspect the task history; I cannot confirm the outcome by voice."}
            try:
                import json
                body = json.loads(content)
            except (ValueError, UnicodeError):
                body = None
            code = response.status_code
        if not isinstance(body, dict) or not isinstance(body.get("reply"), str) or not body["reply"].strip():
            return {"state": "unconfirmed", "spoken_reply": "FRIDAY did not return a usable answer. I cannot confirm task completion."}
        meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        task_state = str(meta.get("task_state", "")).upper()
        if code in {401, 403} or meta.get("refused") or meta.get("security_blocked"):
            state = "refused"
        elif code == 202 or meta.get("pending") is True or task_state in {"PENDING", "RUNNING", "WAITING_APPROVAL"}:
            state = "pending"
        elif code >= 400 or meta.get("execution_failed") or meta.get("error") or meta.get("success") is False or meta.get("probe_success") is False or meta.get("memory_store") is False or task_state == "FAILED":
            state = "failed"
        else:
            # An answer is not a claim that an external action completed.
            state = "answered"
        spoken = meta.get("spoken_summary") if state == "answered" else None
        if not isinstance(spoken, str) or not spoken.strip():
            spoken = body["reply"]
        # TASK-FRD-014: a recall's spoken form must carry the fact.
        spoken = _recall_fact_guard(meta, state, spoken)
        return {"state": state, "spoken_reply": spoken[:6000],
                "full_reply": body["reply"], "task_state": task_state,
                "task_id": meta.get("task_id"), "completion_verified": False}


def build_voice_tools(bridge: VoiceBrainBridge | None = None,
                      result_observer: Any = None,
                      turn_transcript_provider: Any = None) -> list:
    """Register against the real LiveKit SDK; defer SDK import for light tests."""
    from livekit.agents import function_tool

    brain = bridge or VoiceBrainBridge(
        result_observer=result_observer,
        turn_transcript_provider=turn_transcript_provider)
    if (bridge is not None and turn_transcript_provider is not None
            and brain._turn_provider is None):
        brain._turn_provider = turn_transcript_provider

    @function_tool(name="execute_friday_task", description=(
        "Send the user's complete request to FRIDAY's canonical brain. REQUIRED for "
        "remembering/recalling preferences, sourced research, code build/test, video "
        "draft/render/status/approval, and fleet status. Read spoken_reply faithfully; "
        "never turn pending/refused/failed/unconfirmed into success. Never upload or "
        "publish automatically; approval remains a separate owner action. "
        "If the result state is confirmation_required, nothing was submitted: ask "
        "its spoken_reply as a question and re-issue the SAME request only after "
        "the user clearly confirms or supplies the missing detail. "
        "If the result state is superseded, nothing was submitted and nothing is "
        "wrong: the request was composed from an incomplete turn. Say nothing, "
        "listen to the user's complete request, and call again with it whole — "
        "for a remember request, the fact must be exactly what the user stated, "
        "never filled in from earlier conversation."))
    async def execute_friday_task(request: str) -> dict[str, Any]:
        return await brain.execute(request)

    return [execute_friday_task]
