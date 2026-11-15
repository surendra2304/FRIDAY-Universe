"""TASK-IG-VOI-02 — hands-free dictation mode.

Source ideas: reels DfM_GI2EkTH (Infina) + DfOVzvvBxVs (Wispr Flow),
counted once in the corpus roll-up. The owner talks; FRIDAY types
his words into the active app on his laptop via the already-deployed
LAP-001 path; a spoken "send" sends.

These tests pin the pure planner in friday.voice.dictation:
- mode transitions only on whole-utterance control phrases;
- the core safety asymmetry: a dictated sentence that CONTAINS a
  command ("send the report to Priya tomorrow") is typed as content,
  while the bare control word ("send") is the send control;
- every brain-bound relay carries the "Dictation:" structured
  prefix (the confirmation gate's pass-through contract — the
  cross-check runs when TASK-IG-VOI-01's policy module is present);
- scratch erases exactly the last chunk's character count, and a
  sent message cannot be scratched back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import dictation  # noqa: E402


def _kinds(relays):
    return [r.kind for r in relays]


def test_inactive_session_ignores_everything_but_start():
    s = dictation.DictationSession()
    assert s.handle("What is my Stratex balance?") is None
    assert s.handle("send") is None  # no dictation to send
    assert s.handle("start dictation").kind == "start"
    assert s.active


def test_full_dictation_flow():
    relays = dictation.plan([
        "start dictation",
        "Hello Priya, I will be late today",
        "new line",
        "The meeting moved to six",
        "send",
        "stop dictation",
    ])
    assert _kinds(relays) == ["start", "type", "newline", "type", "send", "stop"]
    assert relays[1].brain_request == (
        "Dictation: type the following text into the active app on "
        "my laptop, exactly as written, with no additions: "
        "Hello Priya, I will be late today"
    )
    assert "NOT a send" in relays[2].brain_request


def test_dictated_sentence_containing_a_command_is_typed_not_executed():
    relays = dictation.plan([
        "start dictation",
        "Send the report to Priya tomorrow",
        "Please delete that email thread after reading",
        "stop dictation",
    ])
    assert _kinds(relays) == ["start", "type", "type", "stop"]
    assert "Send the report to Priya tomorrow" in relays[1].brain_request


@pytest.mark.parametrize("utterance", ["send", "Send!", "send it", "please send"])
def test_bare_send_is_the_send_control(utterance):
    relays = dictation.plan(["start dictation", "some words", utterance])
    assert relays[-1].kind == "send"
    assert relays[-1].brain_request.startswith("Dictation:")


@pytest.mark.parametrize("utterance", ["New line.", "new paragraph", "NEXT PARAGRAPH"])
def test_breaks_are_not_sends(utterance):
    relays = dictation.plan(["start dictation", utterance])
    assert relays[-1].kind in ("newline", "paragraph")
    assert "NOT a send" in relays[-1].brain_request


def test_scratch_erases_exactly_the_last_chunk():
    s = dictation.DictationSession()
    s.handle("start dictation")
    s.handle("first chunk")
    s.handle("second chunk!")
    relay = s.handle("scratch that")
    assert relay.kind == "scratch"
    assert "last 13 characters" in relay.brain_request  # len("second chunk!")
    assert "second chunk!" in relay.brain_request
    # The earlier chunk is still scratchable, then the well is dry.
    relay2 = s.handle("scratch that")
    assert relay2 is not None and "first chunk" in relay2.brain_request
    assert s.handle("scratch that") is None


def test_a_sent_message_cannot_be_scratched_back():
    s = dictation.DictationSession()
    s.handle("start dictation")
    s.handle("hello there")
    s.handle("send")
    assert s.handle("scratch that") is None


def test_every_brain_relay_carries_the_structured_prefix():
    relays = dictation.plan([
        "start dictation", "words here", "new line",
        "more words", "scratch that", "final words", "send",
    ])
    for relay in relays:
        if relay.brain_request:
            assert relay.brain_request.startswith("Dictation:"), relay


def test_relays_pass_the_confirmation_gate_when_policy_present():
    policy = pytest.importorskip("friday.voice.confirmation_policy")
    relays = dictation.plan([
        "start dictation", "words here", "new line",
        "scratch that", "final words", "send",
    ])
    for relay in relays:
        if relay.brain_request:
            assert policy.decide(relay.brain_request).verdict == policy.ALLOW, relay


def test_instruction_section_states_the_contract():
    section = dictation.instruction_section()
    assert "DICTATION MODE" in section
    assert "Dictation:" in section
    assert "stop dictation" in section
