"""TASK-FRD-019: a dropped STT fragment is recovered, not just journalled.

Evidence (FRD-005 re-run #8, run 20261117-055507, production worker
journal, S1):

- 05:55:31.434 user final 1: "Friday, check Stratex for me."
- 05:55:31.609 bridge send b1-4e3cfa with ONLY fragment 1's request
  ("Check Stratex for me." — the model called on the first final).
- 05:55:37.200 an interim carrying fragment 2's full text; the final
  itself landed 05:55:41.800: "What is the balance? How many open
  positions are there? And how many closed trades are in the ledger?"
- Fragment 2 was NEVER dispatched. It surfaced only via the FRD-015
  tracker's dropped-fragment suspect ERROR. The follow-up question
  that landed during the same flight (interim 05:55:48.604) never
  became a bridge call either — the model absorbed it into the
  pending delivery and its answer arrived merged, ~22 s late.
- b1 settled 05:55:51.8 (brain turn 20.20 s).

Why recovery, not a pre-dispatch settle: the journal shows NO
transcription signal of any kind between +0.2 s and +5.8 s — interims
arrive once per segment, at segment end — so at dispatch time there
is no evidence a continuation exists; a settle long enough to catch
this split (>= 11 s) would tax EVERY command and break the owner's
speed-first bar. The remember leg in the same call "consolidated"
only because the model never called on its fragment A (nothing
actionable); model-side turn assembly is the only consolidation
that exists, and it is discretionary. The fix pinned here makes the
WORKER guarantee the whole turn reaches the brain: once the flight
a suspect landed during has settled, a suspect still carrying
substance no dispatch covered is handed out exactly once
(_fragment_recovery_due) and the delivery-watch pass dispatches its
text as its own bridge call; the result flows through the ordinary
result observer into the FRD-012/018 delivery watch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

from friday.voice.livekit_worker import (  # noqa: E402
    _fragment_flight_settled,
    _fragment_flight_started,
    _fragment_flush,
    _fragment_recovery_due,
    _fragment_user_final,
    _new_fragment_watch,
)

# The run #8 shapes, verbatim from the journal.
FRAG1_REQUEST = "Check Stratex for me."
FRAG2 = (
    "What is the balance? How many open positions are there? "
    "And how many closed trades are in the ledger?"
)
FOLLOWUP = "How many closed trades are in the ledger exactly?"


def _run8_state():
    """The delegation flight with fragment 2 landed mid-flight."""
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, FRAG2, 110.0)
    return state


def test_split_delegation_fragment_becomes_due_after_its_flight_settles():
    state = _run8_state()
    # Still in flight: not due — the model may yet call on it, and
    # the flight's own result has not landed.
    assert _fragment_recovery_due(state, 115.0) == []
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert len(due) == 1
    assert due[0]["text"] == FRAG2
    assert due[0]["during"] == ["b1"]


def test_recovery_is_handed_out_exactly_once():
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    assert len(_fragment_recovery_due(state, 121.0)) == 1
    assert _fragment_recovery_due(state, 122.0) == []
    assert _fragment_recovery_due(state, 130.0) == []


def test_fragment_the_model_picked_up_later_is_not_recovered():
    state = _run8_state()
    # The model composes a follow-up call carrying fragment 2's
    # substance before the first flight settles — nothing was lost.
    _fragment_flight_started(state, "b2", FRAG2, 115.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_fragment_carried_by_its_own_flight_is_not_recovered():
    state = _new_fragment_watch()
    whole = f"{FRAG1_REQUEST} {FRAG2}"
    _fragment_flight_started(state, "b1", whole, 100.0)
    _fragment_user_final(state, FRAG2, 110.0)
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_followup_that_landed_during_the_flight_is_also_due():
    # Re-run #8's starved follow-up: a separate question that landed
    # during the delegation flight and never got a bridge call. It is
    # a suspect like any other and earns its own recovery dispatch.
    state = _run8_state()
    _fragment_user_final(state, FOLLOWUP, 118.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [FRAG2, FOLLOWUP]


def test_stale_fragment_is_not_recovered():
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    # 121 s after the fragment landed the conversation has moved on.
    assert _fragment_recovery_due(state, 231.0) == []


def test_contentless_final_is_not_recovered():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, "Okay.", 110.0)
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_final_with_nothing_in_flight_is_never_a_suspect():
    state = _new_fragment_watch()
    _fragment_user_final(state, FRAG2, 110.0)
    assert state["suspects"] == []
    assert _fragment_recovery_due(state, 121.0) == []


def test_recovered_fragment_leaves_the_session_flush_clean():
    # Once the recovery dispatch itself has run (a new flight whose
    # request IS the fragment), the session-end flush must not report
    # the fragment as dropped — it reached the brain.
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert len(due) == 1
    _fragment_flight_started(state, "b9", due[0]["text"], 125.0)
    _fragment_flight_settled(state, "b9")
    assert _fragment_flush(state) == []


def test_unrelated_second_flight_does_not_block_recovery():
    # A suspect is tied to the flight it landed during; a later,
    # unrelated call still being in flight does not hold it back
    # (the bridge's own send lock serializes the actual sends).
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    _fragment_flight_started(state, "b7", "What time is it?", 119.0)
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [FRAG2]


# ---------------------------------------------------------------------------
# Wiring: _voice_tools hands the worker the bridge it built
# ---------------------------------------------------------------------------

def test_voice_tools_registers_the_bridge_in_the_sink(monkeypatch):
    import friday.voice.brain_bridge as bb
    from friday.voice.livekit_worker import _voice_tools

    built = {}

    class _FakeBridge:
        def __init__(self, **kwargs):
            built["bridge_kwargs"] = kwargs

    def _fake_build(**kwargs):
        built["build_kwargs"] = kwargs
        return ["tool"]

    monkeypatch.setattr(bb, "VoiceBrainBridge", _FakeBridge)
    monkeypatch.setattr(bb, "build_voice_tools", _fake_build)

    sink = {}
    tools = _voice_tools(
        result_observer="ro", dispatch_observer="do",
        turn_transcript_provider="tp", bridge_sink=sink)
    assert tools == ["tool"]
    assert isinstance(sink["bridge"], _FakeBridge)
    # The explicitly built bridge carries the SAME observers the tool
    # path would have used — the recovery call settles into the same
    # delivery watch.
    assert built["bridge_kwargs"] == {
        "result_observer": "ro",
        "dispatch_observer": "do",
        "turn_transcript_provider": "tp",
    }
    assert built["build_kwargs"] == {"bridge": sink["bridge"]}

    # No sink: the historical construction path is untouched.
    built.clear()
    tools = _voice_tools(
        result_observer="ro", dispatch_observer="do",
        turn_transcript_provider="tp")
    assert tools == ["tool"]
    assert built["build_kwargs"] == {
        "result_observer": "ro",
        "turn_transcript_provider": "tp",
        "dispatch_observer": "do",
    }


def test_worker_wiring_source_pins():
    src = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "livekit_worker.py"
    ).read_text()
    # The delivery-watch pass consumes the due list and dispatches
    # through the job-level recovery coroutine; sessions register
    # their bridge in the job-level slot.
    assert src.count("_fragment_recovery_due(") >= 2  # def + watch pass
    assert src.count("_recover_dropped_fragment(") >= 2  # def + watch pass
    assert "bridge_sink=bridge_slot" in src
    assert "_FRAGMENT_RECOVERY_MAX_AGE_S = 120.0" in src


# ---------------------------------------------------------------------------
# TASK-FRD-022 (PR #865 review follow-up): a recovered fragment that
# hits the confirmation gate is NEVER executed. The reviewer verified
# this structurally — the recovery dispatch awaits the same
# VoiceBrainBridge.execute() as the tool path, whose confirmation
# gate runs before the only submission seam (bridge._send) — but the
# case was not pinned by a test. Pin it here so it cannot regress:
# the gated fragment still becomes due (the tracker hands out
# undispatched substance; gating is the bridge's job, not the
# tracker's), and its recovery dispatch settles confirmation_required
# with the submission seam never reached.
# ---------------------------------------------------------------------------

GATED_FRAG2 = "And close all my Stratex positions."


class _SendRecorder:
    """Fake bridge._send (the submission seam): records every call."""

    def __init__(self):
        self.calls = []

    async def __call__(self, client, text):
        self.calls.append(text)
        return {"state": "answered", "spoken_reply": "Done."}


def _run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


def test_recovered_fragment_that_hits_the_confirmation_gate_is_never_executed(
        monkeypatch):
    from friday.voice import confirmation_policy as policy
    from friday.voice.brain_bridge import VoiceBrainBridge

    # The gated fragment lands during the read-only Stratex flight.
    # Against that flight's request it shares only 'stratex' (one
    # content word, no figures), so it is genuinely undispatched
    # substance and becomes due once the flight settles — once.
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, GATED_FRAG2, 110.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [GATED_FRAG2]
    assert _fragment_recovery_due(state, 122.0) == []

    # The recovery dispatch itself — what _recover_dropped_fragment
    # awaits on the session bridge — with the REAL confirmation gate,
    # constructed explicitly so the pin does not depend on env. The
    # fragment's shape (close + positions, same clause) classifies
    # trade/sensitive, so the gate must stop it.
    seen = []
    recorder = _SendRecorder()
    bridge = VoiceBrainBridge(
        confirmation_gate=policy.ConfirmationGate(),
        result_observer=seen.append,
    )
    monkeypatch.setattr(bridge, "_send", recorder)
    result = _run(bridge.execute(due[0]["text"]))

    # The gate settles the recovery call: the owner is asked, the
    # result observer closes the record with the gated state (the
    # delivery watch's ordinary close for a gated call) — and the
    # submission seam was NEVER reached. Nothing was executed.
    assert result["state"] == "confirmation_required"
    assert result["confirmation_required"] is True
    assert recorder.calls == []
    assert len(seen) == 1
    assert seen[0]["state"] == "confirmation_required"
