"""TASK-IG-VOI-01 — confirmation safeguard for voice-initiated actions.

Source idea: reel DdEg9_QtHbR (the "Dexter" skit): a wake-word
assistant wired into the owner's apps acts on an ambiguous command at
the wrong moment. These tests pin the three layers that prevent the
FRIDAY version of that moment:

- the pure classifier: questions ABOUT actions are read-only and are
  never gated; reversible writes pass; sensitive families confirm
  when the target is a bare pronoun/missing, and the money-out /
  irreversible / security families confirm even when fully specified;
- the gate: first sight of a CONFIRM request blocks it and records a
  fingerprint; the post-confirmation re-issue passes exactly once;
  grants expire; a different family never consumes a grant;
- the bridge: a gated request causes NO brain submission at all (the
  fake _send records every call), and the owner kill switch
  (FRIDAY_VOICE_CONFIRMATION_GATE=off) restores ungated behaviour.

The worker-instructions test needs the livekit stack and skips where
it is absent (CI installs FRIDAY's requirements and runs it).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import confirmation_policy as policy  # noqa: E402
from friday.voice.brain_bridge import VoiceBrainBridge  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Classifier: read-only questions are never gated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "What is my Stratex balance?",
    "Did Stratex place any trades today?",
    "Did you send the report to Priya?",
    "How much did I pay for Netflix last month?",
    "What is the share price of Reliance?",
    "Check the fleet status",
    "Tell me a joke",
    "Did you restart the server?",
    "Has the video been uploaded?",
])
def test_questions_about_actions_are_read_only(text):
    cls = policy.classify_request(text)
    assert cls.category == policy.READ_ONLY, text
    assert policy.decide(text).verdict == policy.ALLOW, text


@pytest.mark.parametrize("text", [
    "Remember that I like filter coffee",
    "Don't forget the team lunch on Friday",
    "Remind me to call mom at six",
    "Open YouTube on my laptop",
    "Remove the background from this photo",
    "Dictation: type the following text into the active app: hello",
])
def test_reversible_and_structured_requests_pass(text):
    assert policy.decide(text).verdict == policy.ALLOW, text


# ---------------------------------------------------------------------------
# Classifier: the Dexter cases — ambiguous person-directed actions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Message her on Instagram",
    "Send it to him",
    "Call her back",
    "Send a message",
    "Follow her on Instagram",
    "Tell her that I will be late",
])
def test_ambiguous_targets_confirm(text):
    cls = policy.classify_request(text)
    assert cls.category == policy.SENSITIVE, text
    assert cls.ambiguous, text
    decision = policy.decide(text)
    assert decision.verdict == policy.CONFIRM, text
    assert "right target" in decision.question, text


@pytest.mark.parametrize("text", [
    "Send a WhatsApp message to Priya saying I will be late",
    "Call mom",
    "Email the invoice to accounts@client.com",
    "Post the video to YouTube",
])
def test_specific_low_risk_actions_pass(text):
    cls = policy.classify_request(text)
    assert cls.category == policy.SENSITIVE, text
    assert not cls.ambiguous, text
    assert policy.decide(text).verdict == policy.ALLOW, text


# ---------------------------------------------------------------------------
# Classifier: always-confirm families (money out, irreversible, security)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Delete the file report.pdf from my downloads",
    "Buy 100 shares of Reliance",
    "Pay the electricity bill of 2400 rupees",
    "Unlock my laptop",
    "Forget the old office address",
    "Run a command on my laptop to clean the temp files",
    "Cancel my three pm meeting",
])
def test_always_confirm_families(text):
    decision = policy.decide(text)
    assert decision.verdict == policy.CONFIRM, text
    assert "Shall I go ahead?" in decision.question, text


# ---------------------------------------------------------------------------
# Gate: block once, pass once, expire
# ---------------------------------------------------------------------------

class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_gate_blocks_then_allows_exactly_once():
    gate = policy.ConfirmationGate(clock=_Clock())
    text = "Delete the file report.pdf from my downloads"
    assert gate.check(text).verdict == policy.CONFIRM
    assert gate.check(text).verdict == policy.ALLOW
    assert gate.check(text).verdict == policy.CONFIRM


def test_gate_allows_a_tidied_reissue():
    gate = policy.ConfirmationGate(clock=_Clock())
    assert gate.check(
        "Delete the file report.pdf from my downloads"
    ).verdict == policy.CONFIRM
    assert gate.check(
        "Delete report.pdf file from the downloads folder"
    ).verdict == policy.ALLOW


def test_gate_grants_expire():
    clock = _Clock()
    gate = policy.ConfirmationGate(clock=clock)
    text = "Pay the electricity bill"
    assert gate.check(text).verdict == policy.CONFIRM
    clock.now += policy.GRANT_TTL_S + 1
    assert gate.check(text).verdict == policy.CONFIRM


def test_gate_grant_is_family_scoped():
    gate = policy.ConfirmationGate(clock=_Clock())
    assert gate.check("Delete the file report.pdf").verdict == policy.CONFIRM
    # A pending delete grant must not wave a payment through.
    assert gate.check("Pay the electricity bill").verdict == policy.CONFIRM
    # ... and the delete grant is still there to be consumed.
    assert gate.check("Delete the file report.pdf").verdict == policy.ALLOW


def test_gate_never_blocks_questions():
    gate = policy.ConfirmationGate(clock=_Clock())
    for _ in range(3):
        assert gate.check(
            "Did Stratex place any trades today?"
        ).verdict == policy.ALLOW


# ---------------------------------------------------------------------------
# Bridge: a gated request is never submitted
# ---------------------------------------------------------------------------

class _Recorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, client, text):
        self.calls.append(text)
        return {"state": "answered", "spoken_reply": "Done."}


def _bridge_with_fake_send(monkeypatch, **kwargs):
    bridge = VoiceBrainBridge(**kwargs)
    recorder = _Recorder()
    monkeypatch.setattr(bridge, "_send", recorder)
    return bridge, recorder


def test_bridge_blocks_ambiguous_request_before_any_submission(monkeypatch):
    bridge, recorder = _bridge_with_fake_send(monkeypatch)
    result = _run(bridge.execute("Message her on Instagram and tell her the plan"))
    assert result["state"] == "confirmation_required"
    assert result["confirmation_required"] is True
    assert "right target" in result["spoken_reply"]
    assert recorder.calls == []  # nothing reached the brain
    # After the owner confirms, the model re-issues the same request:
    result2 = _run(bridge.execute("Message her on Instagram and tell her the plan"))
    assert result2["state"] == "answered"
    assert recorder.calls == ["Message her on Instagram and tell her the plan"]


def test_bridge_passes_questions_immediately(monkeypatch):
    bridge, recorder = _bridge_with_fake_send(monkeypatch)
    result = _run(bridge.execute("What is my Stratex balance?"))
    assert result["state"] == "answered"
    assert len(recorder.calls) == 1


def test_bridge_kill_switch_disables_gate(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_CONFIRMATION_GATE", "off")
    bridge, recorder = _bridge_with_fake_send(monkeypatch)
    assert bridge._gate is None
    result = _run(bridge.execute("Delete the file report.pdf"))
    assert result["state"] == "answered"
    assert len(recorder.calls) == 1


# ---------------------------------------------------------------------------
# Instructions contract (needs the livekit stack; CI runs it)
# ---------------------------------------------------------------------------

def test_worker_instructions_carry_the_confirmation_contract():
    pytest.importorskip("livekit.agents")
    from friday.voice import livekit_worker as worker

    text = worker._instructions(with_memory=False)
    assert "CONFIRMATION RULES" in text
    assert "confirmation_required" in text
