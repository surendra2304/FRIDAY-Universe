"""TASK-FRD-011: voice delegation / brain-turn latency fixes (D1 + D2).

Evidence (FRD-005 re-run 20261116-103839, production journals + probes):

- D1: the mesh dispatch budget for Stratex was 10 s while a Stratex
  "status" execute took ~14 s in production (two concurrent executes
  sharing Stratex's process with its own analysis cycle) — below the
  stratex_portfolio tool budget (45 s) and the voice brain budget
  (60 s). Every loaded delegation timed out by construction. The fix
  pins the dispatch budget at 30 s: above the measured worst case,
  inside both budgets above it.
- D2: the realtime model issued TWO execute_friday_task calls
  concurrently (one per queued user utterance); both brain turns
  returned the byte-identical timeout answer and the model spoke it
  twice. The bridge now serializes its sends and reuses a settled
  result for a verbatim re-issue inside a short window; the worker's
  rebuild transcript never carries a byte-identical assistant item
  twice in a row.
"""

from __future__ import annotations

import asyncio
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


class _AllowGate:
    """A gate that never confirms (read-only traffic shape)."""

    def check(self, text):
        return SimpleNamespace(verdict=policy.ALLOW)


class _Recorder:
    """Fake bridge._send: records calls, tracks peak concurrency."""

    def __init__(self, result=None, delay=0.0):
        self.calls = []
        self.in_flight = 0
        self.peak = 0
        self.result = result or {"state": "answered", "spoken_reply": "Done."}
        self.delay = delay

    async def __call__(self, client, text):
        self.calls.append(text)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            return dict(self.result)
        finally:
            self.in_flight -= 1


def _bridge(monkeypatch, recorder, **kwargs):
    kwargs.setdefault("confirmation_gate", _AllowGate())
    bridge = VoiceBrainBridge(**kwargs)
    monkeypatch.setattr(bridge, "_send", recorder)
    return bridge


# ---------------------------------------------------------------------------
# D1: the Stratex dispatch budget covers the measured worst case
# ---------------------------------------------------------------------------

def test_stratex_dispatch_budget_covers_measured_worst_case():
    import re

    from friday.ecosystem.fleet_client import STRATEX_TASK_TIMEOUT_S

    # 14 s = the production-measured Stratex execute latency in the
    # FRD-005 re-run; the old budget was 10 s (guaranteed timeout).
    assert STRATEX_TASK_TIMEOUT_S == 30.0
    assert STRATEX_TASK_TIMEOUT_S > 14.0
    # Still inside the budgets above it: the stratex_portfolio tool's
    # own 45 s (read from its source — importing the tools package
    # pulls the vision stack, which not every test env carries) and
    # the voice brain bridge's 60 s.
    tool_src = (Path(__file__).resolve().parents[1]
                / "src" / "friday" / "tools" / "builtin"
                / "stratex_portfolio.py").read_text()
    tool_timeout = float(re.search(r"^\s+timeout = (\d+\.?\d*)\s*$",
                                   tool_src, re.M).group(1))
    assert STRATEX_TASK_TIMEOUT_S < tool_timeout
    assert STRATEX_TASK_TIMEOUT_S < brain_bridge.BRAIN_TIMEOUT_S


def test_stratex_branch_uses_the_named_budget():
    src = (Path(__file__).resolve().parents[1]
           / "src" / "friday" / "ecosystem" / "fleet_client.py").read_text()
    branch = src.split('target == "stratex"')[1].split('target == "intelx"')[0]
    assert "timeout=STRATEX_TASK_TIMEOUT_S" in branch


# ---------------------------------------------------------------------------
# D2: bridge serialization + verbatim re-issue reuse
# ---------------------------------------------------------------------------

def test_concurrent_identical_calls_send_once(monkeypatch):
    recorder = _Recorder(delay=0.2)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        return await asyncio.gather(
            bridge.execute("Check Stratex for me"),
            bridge.execute("Check Stratex for me"),
        )

    first, second = _run(scenario())
    assert recorder.calls == ["Check Stratex for me"]
    assert first["state"] == second["state"] == "answered"


def test_repeat_within_window_reuses_result(monkeypatch):
    recorder = _Recorder()
    bridge = _bridge(monkeypatch, recorder)
    _run(bridge.execute("Check Stratex for me"))
    again = _run(bridge.execute("  check   stratex for me "))
    assert again["state"] == "answered"
    assert len(recorder.calls) == 1  # normalized: case/whitespace-insensitive


def test_distinct_requests_are_serialized_not_merged(monkeypatch):
    recorder = _Recorder(delay=0.1)
    bridge = _bridge(monkeypatch, recorder)

    async def scenario():
        return await asyncio.gather(
            bridge.execute("Check Stratex for me"),
            bridge.execute("What is my favourite colour?"),
        )

    _run(scenario())
    assert len(recorder.calls) == 2
    assert recorder.peak == 1  # never two brain turns in flight at once


def test_reuse_window_expires(monkeypatch):
    recorder = _Recorder()
    bridge = _bridge(monkeypatch, recorder)
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        brain_bridge, "time",
        SimpleNamespace(monotonic=lambda: clock["now"]),
    )
    _run(bridge.execute("Check Stratex for me"))
    clock["now"] += brain_bridge.DEDUPE_WINDOW_S + 1.0
    _run(bridge.execute("Check Stratex for me"))
    assert len(recorder.calls) == 2


def test_confirmation_required_is_never_reused(monkeypatch):
    # Real gate: first sight confirms, the confirmed re-issue passes
    # exactly once, and a third identical call must reach the gate
    # again — the cached "answered" must never bypass it.
    recorder = _Recorder()
    bridge = VoiceBrainBridge()
    monkeypatch.setattr(bridge, "_send", recorder)
    text = "Message her on Instagram and tell her the plan"
    assert _run(bridge.execute(text))["state"] == "confirmation_required"
    assert recorder.calls == []
    assert _run(bridge.execute(text))["state"] == "answered"
    assert len(recorder.calls) == 1
    assert _run(bridge.execute(text))["state"] == "confirmation_required"
    assert len(recorder.calls) == 1


def test_unconfirmed_transport_failure_is_never_reused(monkeypatch):
    import httpx

    calls = []

    async def flaky(client, text):
        calls.append(text)
        raise httpx.ConnectError("brain unreachable")

    bridge = _bridge(monkeypatch, _Recorder())
    monkeypatch.setattr(bridge, "_send", flaky)
    assert _run(bridge.execute("Check Stratex for me"))["state"] == "unconfirmed"
    assert _run(bridge.execute("Check Stratex for me"))["state"] == "unconfirmed"
    assert len(calls) == 2  # a retry may succeed; never serve a cached failure-to-connect


def test_failed_result_is_reused_within_window(monkeypatch):
    recorder = _Recorder(result={"state": "failed", "spoken_reply": "It failed."})
    bridge = _bridge(monkeypatch, recorder)
    _run(bridge.execute("Check Stratex for me"))
    _run(bridge.execute("Check Stratex for me"))
    assert len(recorder.calls) == 1


# ---------------------------------------------------------------------------
# D2: rebuild-transcript dedupe + the once-per-request instruction
# ---------------------------------------------------------------------------

def test_transcript_never_carries_identical_assistant_item_twice():
    from friday.voice.livekit_worker import _append_transcript

    transcript = []
    assert _append_transcript(transcript, "user", "Check Stratex for me") is True
    assert _append_transcript(transcript, "assistant", "Stratex timed out.") is True
    assert _append_transcript(transcript, "assistant", "Stratex timed out.") is False
    assert transcript == [
        ("user", "Check Stratex for me"),
        ("assistant", "Stratex timed out."),
    ]


def test_transcript_dedupe_is_narrow():
    from friday.voice.livekit_worker import _append_transcript

    transcript = []
    # A user repeating himself is a real turn — never deduped.
    assert _append_transcript(transcript, "user", "Hello?") is True
    assert _append_transcript(transcript, "user", "Hello?") is True
    # Non-consecutive identical assistant lines can be legitimate.
    assert _append_transcript(transcript, "assistant", "Yes.") is True
    assert _append_transcript(transcript, "user", "And again?") is True
    assert _append_transcript(transcript, "assistant", "Yes.") is True
    assert len(transcript) == 5


def test_transcript_cap_still_applies():
    from friday.voice.livekit_worker import _append_transcript

    transcript = []
    for i in range(45):
        _append_transcript(transcript, "user", f"turn {i}")
    assert len(transcript) == 40
    assert transcript[0] == ("user", "turn 5")


def test_instructions_pin_once_per_request():
    from friday.voice.livekit_worker import BASE_INSTRUCTIONS

    assert "Call execute_friday_task ONCE per user request" in BASE_INSTRUCTIONS
