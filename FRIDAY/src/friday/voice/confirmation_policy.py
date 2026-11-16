"""TASK-IG-VOI-01 — confirmation safeguard for voice-initiated actions.

Source idea: Instagram reel DdEg9_QtHbR (the "Dexter" skit) — a
wake-word assistant wired into the owner's apps acts on an ambiguous
voice command at exactly the wrong moment. The lesson taken into
FRIDAY: a voice command that would change the world (message a person,
post, pay, trade, delete, unlock) must not execute on a guess. When the
target is ambiguous — or the action family is high-blast-radius — the
assistant asks ONE short question first and acts only after the owner
confirms.

Design (three layers, one source of truth — this module):

1. ``classify_request`` — a deterministic, pure classifier over the
   request text the voice model wants to hand to the FRIDAY brain.
   Read-only questions and reversible writes are ALLOW. Sensitive
   families split two ways:
     - always-confirm: pay / trade / delete / security (money out,
       irreversible, or protective systems) — confirm even when the
       request is fully specified;
     - confirm-if-ambiguous: messaging / posting / calling / social
       follow — confirm only when the target is a bare pronoun
       ("message her", "send it") or missing entirely.
   The bias is deliberate: a false confirmation costs one short
   question; a false execution is the Dexter moment. But questions
   ABOUT actions ("did Stratex place any trades today?") are
   read-only and are never gated — voice stays fast for the owner's
   most common use.

2. ``ConfirmationGate`` — the stateful bridge guard. The first time a
   CONFIRM-verdict request arrives it is NOT executed; the gate
   records its fingerprint and the bridge returns the confirmation
   question for the model to speak. When the model re-issues the same
   request after the owner confirms (the instructions contract below
   requires exactly that), the gate consumes the pending fingerprint
   once and lets it through. Grants expire after ``GRANT_TTL_S`` and
   are single-use: a third identical request is gated again. A
   watchdog session rebuild creates a fresh bridge, so a confirmation
   earned before a rebuild is asked again — fail-closed, by design.

3. ``instruction_section`` — the prompt contract for the voice model,
   appended to the worker instructions by the optional-sections
   aggregator in livekit_worker. It teaches the model the
   confirmation_required tool state and forbids rephrasing a request
   to dodge the gate.

Nothing here touches the greeting or session-build path: the gate
runs inside the brain bridge's execute(), i.e. only when the model
has already decided to act, so time-to-first-word is unchanged.

Kill switch: FRIDAY_VOICE_CONFIRMATION_GATE=off disables the bridge
gate (the instructions contract still applies). Default: on.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

READ_ONLY = "read_only"
WRITE = "write"
SENSITIVE = "sensitive"

ALLOW = "allow"
CONFIRM = "confirm"

GRANT_TTL_S = 180.0

# Structured request prefixes that are owner-invoked protocols rather
# than free-form commands. Dictation relays (TASK-IG-VOI-02) carry the
# owner's own words into his own apps, and the dictation "send" is
# itself an explicit spoken control word — re-gating every relayed
# sentence would make dictation unusable, so relays pass.
STRUCTURED_PREFIXES = ("dictation:",)

_STOPWORDS = frozenset(
    "the a an to for of on in at me my i you it that this please friday "
    "now just go ahead and or with from into your his her their our".split()
)

# ---------------------------------------------------------------------------
# Verb families. Patterns are matched against the lowered request with
# word boundaries; imperative detection keeps questions about actions
# ("what did he buy?") out of the action families.
# ---------------------------------------------------------------------------

_ALWAYS_CONFIRM_FAMILIES = {
    "pay": re.compile(
        r"\b(pay|purchase|buy|order|book|subscribe|checkout|tip)\b"
    ),
    "trade": re.compile(
        r"\b(buy|sell|trade|invest|short|long|place (an? )?order|square off)\b"
    ),
    "delete": re.compile(
        r"\b(delete|remove|erase|wipe|cancel|unsubscribe|forget)\b"
    ),
    "security": re.compile(
        r"\b(unlock|disable|disarm|shut ?down|restart|reboot|run (a |the )?command|execute)\b"
        r"|\b(turn|switch) off (the )?(alarm|security|sentinel|cctv|cameras?)\b"
    ),
}

# Media-editing "remove" is not a deletion: "remove the background from
# this photo" is a VyralX edit, not data loss. The phrase is stripped
# before the delete family is tested.
_DELETE_EXEMPT = re.compile(
    r"\bremove (the )?(background|watermark|noise|silence|blur)\b"
)

_AMBIGUOUS_CONFIRM_FAMILIES = {
    "message": re.compile(
        r"\b(send|message|text|whatsapp|dm|e-?mail|reply|forward|tell)\b"
    ),
    "post": re.compile(r"\b(post|publish|upload)\b"),
    "call": re.compile(r"\b(call|dial|phone|ring)\b"),
    "follow": re.compile(r"\b(follow|unfollow|block|unblock)\b"),
}

# "share" joins the post family only with a media/demonstrative object —
# "share price" is a Stratex question, not a publishing action.
_SHARE_POST = re.compile(
    r"\bshare\b[^.?!]{0,40}\b(this|that|it|the (video|reel|post|photo|clip|link))\b"
)

# Position-closing verbs join the trade family only with a trading
# object in scope. Bare "close" / "exit" are desktop homonyms —
# "close the tab", "exit the app" are laptop control and must stay
# ungated — so, like _SHARE_POST above, the verb alone is not enough:
# a position / trade / order / holdings noun (or a position direction —
# "exit my TRX short") must follow within the same clause. "liquidate"
# and "flatten" are trading idioms with no desktop sense, so they also
# take the bare quantifiers ("flatten everything", "liquidate all").
_TRADE_CLOSE = re.compile(
    r"\b(close|closes|closing|exit|exits|exiting|liquidate|liquidates|"
    r"liquidating|flatten|flattens|flattening)\b[^.?!]{0,40}"
    r"\b(positions?|trades?|orders?|holdings?|portfolio|exposure|"
    r"shorts?|longs?|short|long)\b"
    r"|\b(liquidate|liquidates|liquidating|flatten|flattens|flattening)\b"
    r"[^.?!]{0,20}\b(everything|all)\b"
)

# Memory writes are reversible and owner-serving: remember/recall are
# never gated. ("don't forget X" is a remember, handled before delete.)
_REMEMBER = re.compile(r"\b(remember|note|save|store|remind me)\b")
_DONT_FORGET = re.compile(r"\b(don'?t|do not) forget\b")

_QUESTION_START = re.compile(
    r"^(what|when|where|who|whom|whose|why|how|is|are|was|were|do|does|did|"
    r"can|could|will|would|should|tell me|show me|list|check|find out|search|"
    r"give me|get me|read me|read out)\b"
)

_PRONOUN_TARGET = re.compile(r"\b(her|him|them|it|that|this|those|these)\b")

# A named target after a person-directed verb: "message Priya", "call
# mom", "email the office" — any non-pronoun, non-object token counts
# as named; contact resolution is the brain's job, not the gate's.
_NAMED_TARGET = re.compile(
    r"\b(?:send|message|text|whatsapp|dm|e-?mail|call|dial|phone|tell|forward)"
    r"\s+(?:a\s+|the\s+|an\s+)?([a-z0-9@][\w@.\-']*)",
    re.IGNORECASE,
)

# Object nouns that sit in the target slot without naming a recipient:
# "send a message", "make a call" (the call family reaches the same
# slot through its own verbs, so "call" is here too).
_OBJECT_NOUNS = frozenset(
    "message text email mail call video photo picture image report "
    "file link reminder note song screenshot".split()
)


@dataclass(frozen=True)
class Classification:
    category: str
    family: str
    ambiguous: bool
    reasons: tuple
    action_summary: str


@dataclass(frozen=True)
class Decision:
    verdict: str
    classification: Classification
    question: str


def _significant_tokens(text: str) -> frozenset:
    tokens = re.findall(r"[a-z0-9@.\-']+", text.lower())
    return frozenset(t for t in tokens if len(t) > 2 and t not in _STOPWORDS)


def fingerprint(text: str, family: str) -> tuple:
    """Stable identity of a request for grant matching: the action
    family plus its significant tokens. A re-issue that keeps the
    family and most tokens (the model may tidy the phrasing) matches."""
    return (family, _significant_tokens(text))


def _looks_like_question(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered.endswith("?"):
        return True
    return bool(_QUESTION_START.match(lowered))


def _has_named_target(text: str) -> bool:
    m = _NAMED_TARGET.search(text)
    if not m:
        return False
    target = m.group(1).lower()
    return target not in (
        "her", "him", "them", "it", "that", "this", "me", "us",
    ) and target not in _OBJECT_NOUNS


def _summarize(family: str, text: str) -> str:
    lowered = " ".join(text.strip().split())
    gist = lowered if len(lowered) <= 90 else lowered[:87] + "..."
    return f"{family}: {gist}"


def classify_request(text: str) -> Classification:
    """Classify one request string. Pure and deterministic."""
    raw = (text or "").strip()
    lowered = raw.lower()

    if lowered.startswith(STRUCTURED_PREFIXES):
        return Classification(WRITE, "structured", False,
                              ("owner-invoked structured protocol",),
                              _summarize("structured", raw))

    if _DONT_FORGET.search(lowered) or (
        _REMEMBER.search(lowered) and not lowered.startswith(("forget",))
    ):
        # remembering is a reversible write — unless an action verb is
        # ALSO present as a separate imperative ("remember X and delete
        # Y", "don't forget to book the cab" are judged by their action
        # clause below, never waved through as memory writes).
        action_present = any(
            pattern.search(lowered)
            for fam, pattern in _ALWAYS_CONFIRM_FAMILIES.items()
            if fam != "delete"
        ) or bool(re.search(r"\b(delete|erase|wipe)\b", lowered)) or bool(
            _TRADE_CLOSE.search(lowered)
        )
        if not action_present:
            return Classification(WRITE, "memory", False,
                                  ("reversible memory write",),
                                  _summarize("memory", raw))

    question = _looks_like_question(raw)

    # Always-confirm families first: money out, trades, deletions and
    # security actions confirm even when fully specified — but a
    # question ABOUT them stays read-only.
    for family, pattern in _ALWAYS_CONFIRM_FAMILIES.items():
        haystack = _DELETE_EXEMPT.sub("", lowered) if family == "delete" else lowered
        hit = pattern.search(haystack)
        if family == "trade" and not hit:
            # Position-closing phrasing ("close the position", "flatten
            # everything") joins the trade family via its scoped pattern.
            hit = _TRADE_CLOSE.search(haystack)
        if hit:
            if question:
                return Classification(READ_ONLY, family, False,
                                      ("question about an action",),
                                      _summarize(family, raw))
            return Classification(SENSITIVE, family, False,
                                  (f"{family} actions always confirm",),
                                  _summarize(family, raw))

    for family, pattern in _AMBIGUOUS_CONFIRM_FAMILIES.items():
        hit = pattern.search(lowered)
        if family == "post" and not hit:
            hit = _SHARE_POST.search(lowered)
        if hit:
            if question:
                return Classification(READ_ONLY, family, False,
                                      ("question about an action",),
                                      _summarize(family, raw))
            ambiguous = (
                bool(_PRONOUN_TARGET.search(lowered))
                and not _has_named_target(raw)
            ) or not _has_named_target(raw) and family in ("message", "call")
            reasons = []
            if ambiguous:
                reasons.append("target is a pronoun or missing")
            return Classification(SENSITIVE, family, ambiguous,
                                  tuple(reasons), _summarize(family, raw))

    if question:
        return Classification(READ_ONLY, "none", False,
                              ("question / recall",), _summarize("ask", raw))
    return Classification(WRITE, "none", False,
                          ("no sensitive action detected",),
                          _summarize("do", raw))


def decide(text: str) -> Decision:
    """Full policy decision for one request, including the exact
    spoken question to ask when the verdict is CONFIRM."""
    cls = classify_request(text)
    if cls.category != SENSITIVE:
        return Decision(ALLOW, cls, "")
    if cls.family in _ALWAYS_CONFIRM_FAMILIES:
        question = (
            "Before I do that — just to confirm: "
            f"you want me to {cls.action_summary.split(': ', 1)[-1]}. "
            "Shall I go ahead?"
        )
        return Decision(CONFIRM, cls, question)
    if cls.ambiguous:
        question = (
            "I want to make sure I act on the right target — "
            f"{cls.action_summary.split(': ', 1)[-1]}. "
            "Who exactly should it go to?"
        )
        return Decision(CONFIRM, cls, question)
    return Decision(ALLOW, cls, "")


class ConfirmationGate:
    """Stateful single-use grant store behind ``decide``.

    check(text) -> Decision. On a CONFIRM verdict with no pending
    grant, the request's fingerprint is recorded (the caller must NOT
    execute; it returns the question). On a later check of the same
    (or near-identical) request within GRANT_TTL_S, the grant is
    consumed and the verdict is ALLOW — exactly once.
    """

    def __init__(self, ttl_s: float = GRANT_TTL_S, clock=time.monotonic):
        self._ttl = ttl_s
        self._clock = clock
        self._pending: dict = {}

    def _prune(self, now: float) -> None:
        stale = [fp for fp, ts in self._pending.items() if now - ts > self._ttl]
        for fp in stale:
            del self._pending[fp]

    def check(self, text: str) -> Decision:
        decision = decide(text)
        if decision.verdict == ALLOW:
            return decision
        now = self._clock()
        self._prune(now)
        fp = fingerprint(text, decision.classification.family)
        if fp in self._pending:
            del self._pending[fp]
            return Decision(ALLOW, decision.classification, "")
        # Fuzzy path: same family, near-identical token set (the model
        # tidied the phrasing when re-issuing after the confirmation).
        tokens = fp[1]
        for pending_fp in list(self._pending):
            if pending_fp[0] != fp[0]:
                continue
            other = pending_fp[1]
            union = tokens | other
            if union and len(tokens & other) / len(union) >= 0.6:
                del self._pending[pending_fp]
                return Decision(ALLOW, decision.classification, "")
        self._pending[fp] = now
        return decision


def gate_from_env() -> "ConfirmationGate | None":
    """The bridge gate, or None when the owner kill switch is off."""
    if (os.getenv("FRIDAY_VOICE_CONFIRMATION_GATE") or "").strip().lower() == "off":
        return None
    return ConfirmationGate()


def instruction_section() -> str:
    """The model-facing contract, appended to the worker instructions
    by the optional-sections aggregator (TASK-IG-VOI-01)."""
    return (
        "CONFIRMATION RULES: if execute_friday_task returns state "
        "'confirmation_required', ask its spoken_reply question exactly "
        "as written, then wait. Re-issue the SAME request only after "
        "the user clearly confirms or supplies the missing detail; if "
        "they change the action or the target, treat it as a brand-new "
        "request. Never confirm on the user's behalf, and never "
        "rephrase a request to get around a confirmation. Before "
        "calling the tool for a message, post, call, payment, trade, "
        "deletion or unlock, make sure the target is named clearly — "
        "if the user said 'message her' or 'send it' and no name is "
        "established in this conversation, ask who they mean first. "
        "Read-only questions never need confirmation; answer them "
        "immediately."
    )
