"""TASK-FRD-015: D11 — the voice model acts on split-STT fragments.

Evidence (FRD-005 re-run #5, production run 20261116-175800, journals):

- The remember utterance was split by Gemini's activity detection
  into two STT finals 2.6 s apart: 'Please remember this for me.'
  (17:59:33.50) and 'My favorite color is teal.' (17:59:36.11).
- The model acted on the FIRST fragment alone and, lacking the fact,
  composed the bridge request from the PREVIOUS turn's content:
  turn b2 'Please remember that the current time in Tokyo is 9:29 PM.'
  The brain's remember gate stores any payload unconditionally, so
  the junk fact was written to Memora (record 9e2bc0fb, hard-deleted
  by the run crew). The correct remember followed as turn b3, and the
  spoken confirmation verbalized the WRONG (junk) store.
- Root cause: nothing in the dispatch path compares the model's
  composed remember payload with what the user actually said in the
  current turn. The worker holds the transcript (STT finals +
  conversation items) but used it only for the dropped-turn watchdog
  and rebuild briefings.

Fix pinned here (bridge-side, mirroring FRD-014's recall fact guard):
for remember-class requests, the fact the brain WOULD store is
extracted with a mirror of the brain's own classification/extraction
and must be grounded in the current turn's user transcript supplied
by the worker. Grounded → dispatch immediately (~0 ms added). Not
grounded → a settle window waits for the turn to consolidate: a
continuation that grounds the payload lets it dispatch; a
continuation that doesn't supersedes the call (nothing submitted);
no continuation refuses the write with a spoken request to state
the fact. The A/B pair below pins the defect itself: the SAME
scenario against a bridge with no transcript provider (the pre-fix
wiring) dispatches the junk remember; with the provider it never
reaches the brain, and exactly one remember — the consolidated one —
is dispatched.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

from friday.voice import brain_bridge  # noqa: E402
from friday.voice import confirmation_policy as policy  # noqa: E402
from friday.voice.brain_bridge import (  # noqa: E402
    VoiceBrainBridge,
    _payload_grounded,
    _remember_fact_payload,
    consolidate_turn_text,
)

FRAGMENT = "Please remember this for me."
CONTINUATION = "My favorite color is teal."
ACCUMULATED = FRAGMENT + " " + CONTINUATION
JUNK_REQUEST = "Please remember that the current time in Tokyo is 9:29 PM."
TEAL_REQUEST = "Remember that my favorite color is teal."


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _AllowGate:
    """A gate that never confirms (read-only traffic shape)."""

    def check(self, text):
        return SimpleNamespace(verdict=policy.ALLOW)


class _Recorder:
    """Fake bridge._send: records every request that WOULD reach the
    brain — the dispatch ledger the assertions are made against."""

    def __init__(self):
        self.calls = []

    async def __call__(self, client, text):
        self.calls.append(text)
        return {"state": "answered", "spoken_reply": "Done."}


class _TurnProvider:
    """The worker's transcript provider, scripted: flip() is the next
    STT segment of the user's turn landing mid-settle-window."""

    def __init__(self, text, version=1):
        self.text = text
        self.version = version

    def __call__(self):
        return self.text, self.version

    def flip(self, text):
        self.text = text
        self.version += 1


def _bridge(monkeypatch, recorder, provider=None):
    bridge = VoiceBrainBridge(
        confirmation_gate=_AllowGate(),
        turn_transcript_provider=provider,
    )
    monkeypatch.setattr(bridge, "_send", recorder)
    return bridge


# ---------------------------------------------------------------------------
# Classification + payload extraction mirror the brain's remember gate
# ---------------------------------------------------------------------------

def test_payload_extraction_mirrors_the_brain():
    assert _remember_fact_payload(JUNK_REQUEST) == \
        "the current time in Tokyo is 9:29 PM."
    assert _remember_fact_payload(TEAL_REQUEST) == \
        "my favorite color is teal."
    assert _remember_fact_payload(
        "remember this for me: my chai is masala chai") == \
        "my chai is masala chai"
    # Remember-class with NO fact stated: empty payload, not None —
    # ungrounded by construction.
    assert _remember_fact_payload("Please remember this for me.") == ""


def test_recall_and_non_remember_requests_are_not_writes():
    # Recall wins over remember, exactly as in the brain.
    assert _remember_fact_payload(
        "what do you remember about my favorite color") is None
    assert _remember_fact_payload("do you remember my chai preference") is None
    assert _remember_fact_payload("What is my Stratex balance?") is None
    assert _remember_fact_payload("research quantum batteries") is None
    assert _remember_fact_payload("Ask Stratex what my balance is") is None


# ---------------------------------------------------------------------------
# Grounding: the payload must come from THIS turn's words
# ---------------------------------------------------------------------------

def test_grounding_rules():
    # The D11 junk: composed from the previous turn — 0% grounded.
    assert not _payload_grounded(
        "the current time in Tokyo is 9:29 PM.", FRAGMENT)
    # The faithful composition, against the accumulated turn and
    # against its own segment alike.
    assert _payload_grounded("my favorite color is teal.", ACCUMULATED)
    assert _payload_grounded("my favorite color is teal.", CONTINUATION)
    # Spelling variants canonicalize on both sides (FRD-014 mirror).
    assert _payload_grounded(
        "my favourite colour is teal", "my favorite color is teal")
    # Light paraphrase survives the half threshold (march carries it).
    assert _payload_grounded("my birthday is march 3", "my bday is on march 3rd")
    # A wholly different fact is not grounded in an unrelated turn.
    assert not _payload_grounded(
        "my favorite color is teal.", "what is the time in tokyo right now")
    # A fact-less payload is never grounded.
    assert not _payload_grounded("", ACCUMULATED)


def test_consolidate_turn_text():
    transcript = [
        ("user", "Ask Stratex for my balance."),
        ("assistant", "Your balance is 10,792.80."),
        ("user", FRAGMENT),
    ]
    # Segments since the last assistant item + the newer pending final.
    assert consolidate_turn_text(transcript, CONTINUATION) == ACCUMULATED
    # A pending final identical to the last item is not doubled.
    assert consolidate_turn_text(transcript, FRAGMENT) == FRAGMENT
    # No items yet: the pending final alone is the turn.
    assert consolidate_turn_text([], CONTINUATION) == CONTINUATION
    assert consolidate_turn_text([], "") == ""


# ---------------------------------------------------------------------------
# The defect, characterized: without the guard the junk IS dispatched
# ---------------------------------------------------------------------------

def test_without_guard_the_junk_remember_is_dispatched(monkeypatch):
    recorder = _Recorder()
    bridge = _bridge(monkeypatch, recorder, provider=None)
    result = _run(bridge.execute(JUNK_REQUEST))
    # Pre-FRD-015 wiring (no transcript provider): the composed junk
    # goes straight to the brain, whose gate stores it. This is the
    # hole D11 proved in production.
    assert recorder.calls == [JUNK_REQUEST]
    assert result["state"] == "answered"


# ---------------------------------------------------------------------------
# THE regression: split finals -> exactly one, consolidated, remember
# ---------------------------------------------------------------------------

def test_split_finals_dispatch_exactly_one_consolidated_remember(monkeypatch):
    monkeypatch.setattr(brain_bridge, "FRAGMENT_SETTLE_S", 1.5)
    recorder = _Recorder()
    provider = _TurnProvider(FRAGMENT, version=1)
    bridge = _bridge(monkeypatch, recorder, provider=provider)

    async def scenario():
        # The model acts on fragment 1 alone, as in production.
        first = asyncio.ensure_future(bridge.execute(JUNK_REQUEST))
        await asyncio.sleep(0.35)
        # 2.6 s later in production; inside the settle window here,
        # the second segment of the SAME utterance lands.
        provider.flip(ACCUMULATED)
        first_result = await first
        # The model now issues the remember from the complete turn.
        second_result = await bridge.execute(TEAL_REQUEST)
        # Even a stubborn verbatim re-issue of the junk afterwards
        # must not get through.
        third_result = await bridge.execute(JUNK_REQUEST)
        return first_result, second_result, third_result

    first, second, third = _run(scenario())
    assert first["state"] == "superseded"
    assert first["spoken_reply"] == ""
    assert second["state"] == "answered"
    assert third["state"] == "refused"
    # Exactly ONE dispatch in the whole sequence, and it is the
    # consolidated, user-stated fact — the junk never reached the brain.
    assert recorder.calls == [TEAL_REQUEST]


def test_continuation_that_grounds_the_payload_dispatches(monkeypatch):
    monkeypatch.setattr(brain_bridge, "FRAGMENT_SETTLE_S", 2.0)
    recorder = _Recorder()
    provider = _TurnProvider(FRAGMENT, version=1)
    bridge = _bridge(monkeypatch, recorder, provider=provider)
    request = "Remember that my new gym is Fitlife Studio."

    async def scenario():
        pending = asyncio.ensure_future(bridge.execute(request))
        await asyncio.sleep(0.35)
        provider.flip(FRAGMENT + " My new gym is Fitlife Studio.")
        started = time.monotonic()
        result = await pending
        return result, time.monotonic() - started

    result, _waited = _run(scenario())
    assert result["state"] == "answered"
    assert recorder.calls == [request]


def test_grounded_remember_pays_no_settle_latency(monkeypatch):
    # A long settle window is configured; a grounded remember must
    # not wait any of it (voice is judged on speed first).
    monkeypatch.setattr(brain_bridge, "FRAGMENT_SETTLE_S", 2.0)
    recorder = _Recorder()
    provider = _TurnProvider(ACCUMULATED, version=7)
    bridge = _bridge(monkeypatch, recorder, provider=provider)

    async def scenario():
        started = time.monotonic()
        result = await bridge.execute(TEAL_REQUEST)
        return result, time.monotonic() - started

    result, elapsed = _run(scenario())
    assert result["state"] == "answered"
    assert recorder.calls == [TEAL_REQUEST]
    # Well under the 2.0 s settle window a guarded path would burn.
    assert elapsed < 1.0


def test_ungrounded_remember_without_continuation_is_refused(monkeypatch):
    monkeypatch.setattr(brain_bridge, "FRAGMENT_SETTLE_S", 0.6)
    recorder = _Recorder()
    provider = _TurnProvider(FRAGMENT, version=1)
    bridge = _bridge(monkeypatch, recorder, provider=provider)
    result = _run(bridge.execute(JUNK_REQUEST))
    assert result["state"] == "refused"
    assert "haven't stored" in result["spoken_reply"]
    assert recorder.calls == []
    # The refusal is not cached as a reusable result: once the user
    # actually states a fact, the remember path works normally.
    provider.flip(ACCUMULATED)
    result2 = _run(bridge.execute(TEAL_REQUEST))
    assert result2["state"] == "answered"
    assert recorder.calls == [TEAL_REQUEST]


# ---------------------------------------------------------------------------
# Guard scope: only remember-class writes are held
# ---------------------------------------------------------------------------

def test_delegation_and_recall_dispatch_unguarded(monkeypatch):
    monkeypatch.setattr(brain_bridge, "FRAGMENT_SETTLE_S", 2.0)
    recorder = _Recorder()
    provider = _TurnProvider(FRAGMENT, version=1)
    bridge = _bridge(monkeypatch, recorder, provider=provider)

    async def scenario():
        started = time.monotonic()
        r1 = await bridge.execute("Ask Stratex what my balance is")
        r2 = await bridge.execute("what do you remember about my chai")
        return r1, r2, time.monotonic() - started

    r1, r2, elapsed = _run(scenario())
    assert r1["state"] == "answered"
    assert r2["state"] == "answered"
    assert len(recorder.calls) == 2
    # The point is "no settle window was waited" (2.0 s configured);
    # the bound leaves room for this host's loaded wall clock.
    assert elapsed < 1.5


def test_provider_failure_degrades_open(monkeypatch):
    recorder = _Recorder()

    def _boom():
        raise RuntimeError("provider unavailable")

    bridge = _bridge(monkeypatch, recorder, provider=_boom)
    result = _run(bridge.execute(JUNK_REQUEST))
    # A broken provider must never take voice down with it: the guard
    # goes inert (pre-FRD-015 behaviour), the call proceeds.
    assert result["state"] == "answered"
    assert recorder.calls == [JUNK_REQUEST]


# ---------------------------------------------------------------------------
# Wiring pins: the worker actually feeds the guard
# ---------------------------------------------------------------------------

def test_worker_wires_the_transcript_provider():
    src = (Path(__file__).resolve().parents[1]
           / "src" / "friday" / "voice" / "livekit_worker.py").read_text()
    assert "turn_transcript_provider=_turn_transcript_snapshot" in src
    assert "consolidate_turn_text(turn[\"transcript\"], turn[\"pending_text\"])" in src
    # Every STT final bumps the version the settle window watches.
    assert 'turn["user_final_seq"] = int(turn.get("user_final_seq") or 0) + 1' in src
    # The delivery watch already exempts unknown states from nudging;
    # "superseded" must stay outside its deliverable set.
    # TASK-FRD-018: the set moved from the watch body into the
    # _delivery_action decision helper; the pin follows it there.
    watch = src.split("def _delivery_action")[1].split("# ---- TASK-VOI-012")[0]
    assert '"superseded"' not in watch.split("state not in")[1].split(")")[0]
