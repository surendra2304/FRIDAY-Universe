"""TASK-FRD-012: brain→voice result delivery fixes (D6 + D7).

Evidence (FRD-005 re-run 20261116-120503, production journals on one
clock — see ~/workspace/frd-012/STATE.md for the full trace):

- D6: the delegation brain turn ran 12:06:48 → 12:08:04 (76 s) while
  the bridge budget was 60 s. The bridge hung up, the completed
  figures-bearing answer was discarded into a closed stream, and the
  "unconfirmed" function result was absorbed unsaid by the model
  while it answered a newer question. The bridge logged NOTHING, so
  no hop was identifiable.
- D7: the remember turn completed inside its budget (~27 s) and the
  bridge returned "answered", but the model verbalized the
  confirmation only after the goodbye, behind the recall and goodbye
  turns. Nothing worker-side noticed an unverbalized settled result.

Fixes pinned here: turn-id journaling on every bridge hop; the
foreground budget aligned to the brain's measured completion
envelope (105 s > the 77.48 s worst degraded turn) with a 240 s hard
transport cap; a shielded background continuation so a settled answer
is filed as a late result instead of discarded (and back-fills the
FRD-011 reuse cache); a worker delivery watch (late results are
delivered into the session; unverbalized settled results are nudged
once) built on the conservative _result_verbalized check.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import brain_bridge  # noqa: E402
from friday.voice import confirmation_policy as policy  # noqa: E402
from friday.voice.brain_bridge import VoiceBrainBridge  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _drain_late_results():
    brain_bridge.pop_late_results()
    yield
    brain_bridge.pop_late_results()


class _AllowGate:
    """A gate that never confirms (read-only traffic shape)."""

    def check(self, text):
        return SimpleNamespace(verdict=policy.ALLOW)


class _Recorder:
    """Fake bridge._send: records calls, returns after a set delay."""

    def __init__(self, result=None, delay=0.0):
        self.calls = []
        self.result = result or {"state": "answered", "spoken_reply": "Done."}
        self.delay = delay

    async def __call__(self, client, text):
        self.calls.append(text)
        if self.delay:
            await asyncio.sleep(self.delay)
        return dict(self.result)


def _bridge(monkeypatch, recorder, **kwargs):
    kwargs.setdefault("confirmation_gate", _AllowGate())
    bridge = VoiceBrainBridge(**kwargs)
    monkeypatch.setattr(bridge, "_send", recorder)
    return bridge


FIGURES = ("Portfolio snapshot (Stratex, FUTURES mode): Balance: "
           "10,792.80, open positions: none, 9 closed trades, net +195.06")


# ---------------------------------------------------------------------------
# Budget alignment: the foreground budget covers the measured envelope
# ---------------------------------------------------------------------------

def test_brain_budget_covers_the_degraded_envelope():
    # Worst measured degraded brain turn: 77.48 s (FRD-005 re-run #2);
    # re-run #3's delegation took 76 s. The old 60 s budget sat below
    # both — every degraded delegation stranded by construction.
    assert brain_bridge.BRAIN_TIMEOUT_S == 105.0
    assert brain_bridge.BRAIN_TIMEOUT_S > 77.48
    # The hard transport cap leashes the background continuation and
    # must sit above the foreground budget.
    assert brain_bridge.BRAIN_HARD_TIMEOUT_S == 240.0
    assert brain_bridge.BRAIN_HARD_TIMEOUT_S > brain_bridge.BRAIN_TIMEOUT_S


def test_budget_chain_stays_coherent():
    import re

    # Stratex dispatch (30 s, FRD-011) < stratex tool (45 s) < bridge.
    fleet_src = (Path(__file__).resolve().parents[1]
                 / "src" / "friday" / "ecosystem"
                 / "fleet_client.py").read_text()
    dispatch = float(re.search(r"STRATEX_TASK_TIMEOUT_S\s*=\s*(\d+\.?\d*)",
                               fleet_src).group(1))
    tool_src = (Path(__file__).resolve().parents[1]
                / "src" / "friday" / "tools" / "builtin"
                / "stratex_portfolio.py").read_text()
    tool_timeout = float(re.search(r"^\s+timeout = (\d+\.?\d*)\s*$",
                                   tool_src, re.M).group(1))
    assert dispatch < tool_timeout < brain_bridge.BRAIN_TIMEOUT_S


# ---------------------------------------------------------------------------
# D6: a brain turn that outlasts the budget is delivered, not discarded
# ---------------------------------------------------------------------------

def test_timeout_returns_honest_unconfirmed_and_files_late_result(monkeypatch):
    monkeypatch.setattr(brain_bridge, "BRAIN_TIMEOUT_S", 0.3)
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES},
                         delay=0.8)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        result = await bridge.execute("Check Stratex for me")
        assert result["state"] == "unconfirmed"
        assert result["late_pending"] is True
        assert result["turn_id"]
        assert "lost contact" in result["spoken_reply"]
        await asyncio.sleep(1.2)  # the brain turn lands at ~0.8 s
        return result

    _run(scenario())
    late = brain_bridge.pop_late_results()
    assert len(late) == 1
    assert late[0]["state"] == "answered"
    assert late[0]["spoken_reply"] == FIGURES
    assert brain_bridge.pop_late_results() == []  # delivered once


def test_caller_cancellation_arms_the_same_continuation(monkeypatch):
    monkeypatch.setattr(brain_bridge, "BRAIN_TIMEOUT_S", 30.0)
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES},
                         delay=0.6)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        task = asyncio.ensure_future(bridge.execute("Check Stratex for me"))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(1.0)  # the orphaned send lands at ~0.6 s
        # The send lock was released by the cancellation: a fresh call
        # is served normally, not queued behind the orphan.
        recorder.delay = 0.0
        return await bridge.execute("What is my favourite colour?")

    followup = _run(scenario())
    assert followup["state"] == "answered"
    late = brain_bridge.pop_late_results()
    assert len(late) == 1
    assert late[0]["spoken_reply"] == FIGURES


def test_late_result_backfills_the_reuse_cache(monkeypatch):
    monkeypatch.setattr(brain_bridge, "BRAIN_TIMEOUT_S", 0.3)
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES},
                         delay=0.8)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        await bridge.execute("Check Stratex for me")
        await asyncio.sleep(1.2)
        return await bridge.execute("  check   stratex for me ")

    again = _run(scenario())
    assert again["state"] == "answered"
    assert again["spoken_reply"] == FIGURES
    assert len(recorder.calls) == 1  # reused, never re-sent


def test_late_unconfirmed_is_journaled_not_filed(monkeypatch):
    import httpx

    monkeypatch.setattr(brain_bridge, "BRAIN_TIMEOUT_S", 0.3)

    async def slow_failure(client, text):
        await asyncio.sleep(0.8)
        raise httpx.ConnectError("brain unreachable")

    bridge = _bridge(monkeypatch, _Recorder())
    monkeypatch.setattr(bridge, "_send", slow_failure)

    async def scenario():
        result = await bridge.execute("Check Stratex for me")
        assert result["state"] == "unconfirmed"
        assert result["late_pending"] is True
        await asyncio.sleep(1.2)

    _run(scenario())
    # The owner already heard the foreground "unconfirmed"; a second,
    # identical one arriving late would be noise — journal only.
    assert brain_bridge.pop_late_results() == []


def test_fast_path_is_unchanged(monkeypatch):
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES})
    bridge = _bridge(monkeypatch, recorder)
    result = _run(bridge.execute("Check Stratex for me"))
    assert result["state"] == "answered"
    assert not result.get("late_pending")
    assert result["turn_id"]
    assert brain_bridge.pop_late_results() == []


# ---------------------------------------------------------------------------
# Instrumentation: every hop journaled under one turn id
# ---------------------------------------------------------------------------

def test_send_and_result_are_journaled_with_the_turn_id(monkeypatch, caplog):
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES})
    bridge = _bridge(monkeypatch, recorder)
    with caplog.at_level(logging.INFO, logger="friday.voice.brain_bridge"):
        result = _run(bridge.execute("Check Stratex for me"))
    lines = [r.getMessage() for r in caplog.records
             if r.name == "friday.voice.brain_bridge"]
    send_lines = [m for m in lines if "VOICE brain bridge send" in m]
    result_lines = [m for m in lines if "VOICE brain bridge result" in m]
    assert len(send_lines) == 1 and len(result_lines) == 1
    assert f"turn={result['turn_id']}" in send_lines[0]
    assert f"turn={result['turn_id']}" in result_lines[0]
    assert "state=answered" in result_lines[0]


def test_timeout_is_journaled_with_the_turn_id(monkeypatch, caplog):
    monkeypatch.setattr(brain_bridge, "BRAIN_TIMEOUT_S", 0.3)
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES},
                         delay=0.8)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        result = await bridge.execute("Check Stratex for me")
        await asyncio.sleep(1.2)
        return result

    with caplog.at_level(logging.INFO, logger="friday.voice.brain_bridge"):
        result = _run(scenario())
    lines = [r.getMessage() for r in caplog.records
             if r.name == "friday.voice.brain_bridge"]
    timeout_lines = [m for m in lines if "VOICE brain bridge timeout" in m]
    late_lines = [m for m in lines if "VOICE brain bridge late result" in m]
    assert len(timeout_lines) == 1 and len(late_lines) == 1
    assert f"turn={result['turn_id']}" in timeout_lines[0]
    assert f"turn={result['turn_id']}" in late_lines[0]


def test_observer_sees_foreground_results(monkeypatch):
    seen = []
    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES})
    bridge = _bridge(monkeypatch, recorder, result_observer=seen.append)
    result = _run(bridge.execute("Check Stratex for me"))
    assert len(seen) == 1
    assert seen[0]["turn_id"] == result["turn_id"]
    assert seen[0]["state"] == "answered"
    assert seen[0]["late_pending"] is False


def test_observer_failure_never_breaks_a_call(monkeypatch):
    def broken_observer(record):
        raise RuntimeError("watch is down")

    recorder = _Recorder(result={"state": "answered", "spoken_reply": FIGURES})
    bridge = _bridge(monkeypatch, recorder, result_observer=broken_observer)
    assert _run(bridge.execute("Check Stratex for me"))["state"] == "answered"


def test_gate_verdict_is_journaled_and_observed(monkeypatch, caplog):
    seen = []
    recorder = _Recorder()
    bridge = VoiceBrainBridge(result_observer=seen.append)  # real gate
    monkeypatch.setattr(bridge, "_send", recorder)
    text = "Message her on Instagram and tell her the plan"
    with caplog.at_level(logging.INFO, logger="friday.voice.brain_bridge"):
        result = _run(bridge.execute(text))
    assert result["state"] == "confirmation_required"
    assert recorder.calls == []  # nothing submitted
    assert seen and seen[0]["state"] == "confirmation_required"
    lines = [r.getMessage() for r in caplog.records
             if r.name == "friday.voice.brain_bridge"]
    assert any("gate" in m and "confirmation_required" in m for m in lines)


# ---------------------------------------------------------------------------
# D7: the worker's verbalization check (pure helpers)
# ---------------------------------------------------------------------------

def test_verbalized_by_figure():
    from friday.voice.livekit_worker import _result_verbalized

    reply = FIGURES
    assert _result_verbalized(reply, [
        "Your balance is 10792.80, with nine closed trades so far.",
    ]) is True


def test_verbalized_by_content_words():
    from friday.voice.livekit_worker import _result_verbalized

    reply = ("Got it, Boss — locked in: your favourite colour is teal. "
             "That one's pinned — it never fades.")
    assert _result_verbalized(reply, [
        "By the way, about your earlier question, I've locked in that "
        "your favorite color is teal. It's pinned and saved in your "
        "memories.",
    ]) is True


def test_filler_is_not_verbalization():
    from friday.voice.livekit_worker import _result_verbalized

    # The re-run #3 fillers: they acknowledge the request but carry
    # none of the result's substance.
    assert _result_verbalized(FIGURES, [
        "I am currently retrieving the latest Stratex data for you.",
        "I am still retrieving the latest Stratex data for you and "
        "will have those details shortly.",
    ]) is False
    # A newer turn's own answer does not verbalize the pending result.
    assert _result_verbalized(FIGURES, [
        "It is currently 3:37 PM in Tokyo, Japan.",
    ]) is False


def test_the_unconfirmed_sentence_verbalizes_itself():
    from friday.voice.livekit_worker import _result_verbalized

    reply = ("I lost contact with FRIDAY's brain. The outcome is "
             "unconfirmed. Please check the task history before "
             "repeating an action.")
    assert _result_verbalized(reply, [reply]) is True


def test_watchdog_thresholds_clear_the_aligned_budget():
    from friday.voice import livekit_worker as worker

    # The wedge threshold and the rung prove window must both clear
    # the bridge budget, or the ladder strands what it rescues.
    assert worker._TURN_WEDGE_THRESHOLD_S > brain_bridge.BRAIN_TIMEOUT_S
    assert worker._RUNG_PROVE_S > brain_bridge.BRAIN_TIMEOUT_S
    # Two full rungs (60 s start + prove) fit the ladder budget.
    assert worker._RECOVERY_BUDGET_S >= 2 * (60.0 + worker._RUNG_PROVE_S)


def test_instructions_carry_the_late_delivery_rule():
    from friday.voice.livekit_worker import BASE_INSTRUCTIONS

    assert "a completed result must never go unspoken" in BASE_INSTRUCTIONS
