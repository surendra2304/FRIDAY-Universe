"""TASK-STR-EXP-006 — starvation breaker for the self-experiment loop.

Root cause (verified live on Server 1, 2026-11-22 ~16:30 IST): the
whole-box load gate (1-minute load < 0.7 x 2 CPUs = 1.4) has never
opened since the loop was armed on 2026-11-20 — 1-minute load sits
at 3.0-4.0 with 7 agents and a 15-second daemon scan cycle on a
2-CPU box. The counter is still 3,979 and experiments.jsonl does
not exist: zero trials in two days.

The fix (scheduling only): when no trial has run for
STARVATION_BREAKER_AFTER_S, one trial may run niced (lowest OS
priority) while the daemon is idle and the load stays below the
breaker ceiling. The frozen judgement (judge.py) and the frozen
bars (bounds.py) are untouched — this suite pins them — and the
daily cap, time box and declaration discipline still apply.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from self_experiments import bounds, daemon_wiring
from self_experiments.counter import SEED_VALUE
from self_experiments.judge import judge
from self_experiments.ledger import ExperimentLedger
from self_experiments.loop import SelfExperimentLoop
from self_experiments.runner import PooledMetrics
from self_experiments.store import StreamStore

FIXTURE_STORE = (
    Path(__file__).parent / "fixtures" / "selfexp_stream_store"
)

UTC = timezone.utc


class RecordingWriter:
    """A lesson writer that records deliveries instead of sending."""

    def __init__(self, succeed: bool = True):
        self.calls: list[tuple[str, dict, bool]] = []
        self.succeed = succeed

    def deliver(self, content, metadata, *, universal):
        self.calls.append((content, metadata, universal))
        return self.succeed


def make_loop(tmp_path, **kwargs):
    kwargs.setdefault("work_probe", lambda: True)
    return SelfExperimentLoop(
        store=StreamStore(FIXTURE_STORE),
        data_dir=tmp_path / "loop_data",
        lesson_writer=RecordingWriter(),
        **kwargs,
    )


def set_load(monkeypatch, load1, cpus=2, load5=None):
    """Pin the load the loop sees: load1 (and load5, defaulting to
    load1) with a 2-CPU box, matching production Server 1 (gate 1.4,
    breaker ceiling 4.0 on the 5-minute average)."""
    load5 = load1 if load5 is None else load5
    monkeypatch.setattr(
        os, "getloadavg", lambda: (load1, load5, load5)
    )
    monkeypatch.setattr(os, "cpu_count", lambda: cpus)


@pytest.fixture(autouse=True)
def _switch_on(monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")


def _result_rows(loop):
    return [
        r for r in loop.ledger.rows() if r.get("kind") == "result"
    ]


# ---------------------------------------------------------------------------
# The breaker fires under the exact starving conditions
# ---------------------------------------------------------------------------


def test_breaker_fires_when_starved_idle_and_below_ceiling(
    tmp_path, monkeypatch
):
    # Production load: 3.0 on a 2-CPU box — above the 1.4 gate, below
    # the 4.0 breaker ceiling. Fresh data dir: no trial ever ran.
    set_load(monkeypatch, 3.0)
    loop = make_loop(tmp_path)
    assert loop.counter.value == SEED_VALUE == 3979
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.via == "starvation_breaker"
    assert report.load1 == pytest.approx(3.0)
    assert report.load5 == pytest.approx(3.0)
    assert report.n_global == 3980  # first trial lands
    rows = _result_rows(loop)
    assert len(rows) == 1
    assert rows[0]["trial"] == 3980
    assert rows[0]["scheduling"] == "starvation_breaker"
    assert rows[0]["load1"] == pytest.approx(3.0)
    assert rows[0]["load5"] == pytest.approx(3.0)
    assert rows[0]["status"] == "ran"


def test_breaker_trial_is_judged_under_the_frozen_bars(
    tmp_path, monkeypatch
):
    # The trial the breaker runs is judged exactly as a normal one:
    # the verdict is one of the frozen outcomes and the counter is
    # the Bonferroni denominator.
    set_load(monkeypatch, 3.0)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict in ("PROVEN", "FORWARD_TEST", "FAIL")
    assert loop.counter.value == 3980


def test_one_breaker_trial_per_starvation_window(tmp_path, monkeypatch):
    # After a breaker trial lands, the loop is no longer starved:
    # the very next poll under the same load skips instead of
    # running trial after trial.
    set_load(monkeypatch, 3.0)
    loop = make_loop(tmp_path)
    assert loop.run_one_cycle().status == "ran"
    second = loop.run_one_cycle()
    assert second.status == "skipped"
    assert second.reason == "host_load_gate"
    assert loop.counter.value == 3980


# ---------------------------------------------------------------------------
# The breaker refuses when any of its conditions fails
# ---------------------------------------------------------------------------


def test_no_breaker_above_ceiling(tmp_path, monkeypatch):
    # Sustained load 9.0: the box is saturated, not merely busy —
    # no trial, even starved.
    set_load(monkeypatch, 9.0)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"
    assert loop.counter.value == 3979
    assert _result_rows(loop) == []


def test_breaker_ignores_transient_spike(tmp_path, monkeypatch):
    # The 1-minute average spikes to 9.0 (a daemon scan landing on
    # the poll instant) but the 5-minute average is 3.0: the box is
    # not sustained-saturated, so the breaker fires.
    set_load(monkeypatch, 9.0, load5=3.0)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.via == "starvation_breaker"
    assert report.n_global == 3980


def test_no_breaker_when_sustained_load_high(tmp_path, monkeypatch):
    # The 1-minute average dips to 5.0 but the 5-minute average is
    # 9.0: sustained saturation — the breaker refuses.
    set_load(monkeypatch, 5.0, load5=9.0)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"
    assert loop.counter.value == 3979


def test_no_breaker_when_trial_ran_recently(tmp_path, monkeypatch):
    # A normal-path trial just ran (calm load): the loop is not
    # starved, so a loaded poll skips instead of breaking through.
    set_load(monkeypatch, 0.1)
    loop = make_loop(tmp_path)
    assert loop.run_one_cycle().status == "ran"
    assert loop.run_one_cycle().status == "ran"  # second proposal, calm
    set_load(monkeypatch, 3.0)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"


def test_no_breaker_when_daemon_busy(tmp_path, monkeypatch):
    # The daemon-activity probe still rules: a breaker trial never
    # runs while the daemon is mid-scan.
    set_load(monkeypatch, 3.0)
    loop = make_loop(tmp_path, work_probe=lambda: False)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "work_in_progress"
    assert loop.counter.value == 3979


def test_breaker_does_not_bypass_daily_cap(tmp_path, monkeypatch):
    # The daily cap still applies to breaker trials.
    set_load(monkeypatch, 3.0)
    loop = make_loop(tmp_path, daily_cap=0)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "daily_cap_reached"
    assert loop.counter.value == 3979


def test_no_breaker_when_switch_off(tmp_path, monkeypatch):
    set_load(monkeypatch, 3.0)
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "off")
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "kill_switch_off"
    assert loop.counter.value == 3979


def test_unreadable_load_fails_closed(tmp_path, monkeypatch):
    # A load the loop cannot read never opens the breaker.
    def _boom():
        raise OSError("no load average here")

    monkeypatch.setattr(os, "getloadavg", _boom)
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"
    assert report.load1 is None
    assert report.load5 is None
    assert loop.counter.value == 3979


# ---------------------------------------------------------------------------
# The normal path is unchanged
# ---------------------------------------------------------------------------


def test_normal_path_still_uses_load_gate(tmp_path, monkeypatch):
    # Calm load: the trial runs via the normal gate, tagged as such.
    set_load(monkeypatch, 0.1)
    loop = make_loop(tmp_path)
    report = loop.run_one_cycle()
    assert report.status == "ran"
    assert report.via == "load_gate"
    assert report.load1 == pytest.approx(0.1)
    assert _result_rows(loop)[0]["scheduling"] == "load_gate"


def test_starved_tracks_last_result(tmp_path, monkeypatch):
    set_load(monkeypatch, 0.1)
    loop = make_loop(tmp_path)
    assert loop.starved() is True  # no result row ever
    assert loop.ledger.last_result_ts() is None
    assert loop.run_one_cycle().status == "ran"
    assert loop.starved() is False
    assert loop.ledger.last_result_ts() is not None


def test_starved_uses_newest_result_row(tmp_path, monkeypatch):
    # The newest result row decides: a 7h-old last result means
    # starved, a 1h-old one does not.
    loop = make_loop(tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
    loop.ledger._append({"kind": "result", "ts": old, "status": "ran"})
    assert loop.starved() is True
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    loop.ledger._append({"kind": "result", "ts": recent, "status": "ran"})
    assert loop.starved() is False


def test_unreadable_last_result_fails_closed(tmp_path, monkeypatch):
    loop = make_loop(tmp_path)
    loop.ledger._append(
        {"kind": "result", "ts": "not-a-timestamp", "status": "ran"}
    )
    assert loop.starved() is False


# ---------------------------------------------------------------------------
# The frozen judgement is untouched by this scheduling change
# ---------------------------------------------------------------------------


def test_frozen_bars_pinned():
    assert bounds.FULL_BAR_PF == 1.2
    assert bounds.SECOND_TIER_PF == 1.05
    assert bounds.MIN_OOS_TRADES == 200
    assert bounds.FULL_BAR_MIN_POSITIVE_FOLDS == 4
    assert bounds.FOLDS_TOTAL == 5
    assert bounds.BONFERRONI_ALPHA == 0.05
    assert bounds.LOAD_GATE_FRACTION == 0.7  # normal gate unchanged
    assert bounds.DEFAULT_DAILY_CAP == 4
    assert bounds.DEFAULT_TIME_BOX_S == 600.0


def test_judge_still_applies_the_frozen_bars():
    def _metrics(**overrides):
        base = dict(
            members=("a", "b"),
            trades=500,
            wins=220,
            expectancy=0.01,
            pf=1.30,
            gross_profit=130.0,
            gross_loss=100.0,
            per_fold={
                f"W{i}": {"trades": 100, "expectancy": 0.01}
                for i in range(1, 6)
            },
            positive_folds=5,
            folds_with_trades=5,
            holdout_trades=100,
            holdout_expectancy=0.01,
            t_stat=6.0,
            p_one_sided=1e-9,
        )
        base.update(overrides)
        return PooledMetrics(**base)

    # Full bar at N=3980 (Bonferroni 0.05/3980): PROVEN.
    assert judge(_metrics(), 3980).verdict == "PROVEN"
    # PF below the full bar but above the second tier: FORWARD_TEST.
    assert judge(_metrics(pf=1.10), 3980).verdict == "FORWARD_TEST"
    # PF below the second tier: FAIL.
    assert judge(_metrics(pf=1.0), 3980).verdict == "FAIL"


# ---------------------------------------------------------------------------
# The loop thread runs niced (daemon_wiring)
# ---------------------------------------------------------------------------


class _NiceRecordingLoop:
    """A stand-in loop that records the priority of the thread
    driving run_forever, then waits for its stop event."""

    def __init__(self):
        self.started = threading.Event()
        self.nice_seen: int | None = None

    async def run_forever(self, stop_event=None):
        self.nice_seen = os.getpriority(
            os.PRIO_PROCESS, threading.get_native_id()
        )
        self.started.set()
        await stop_event.wait()


def test_loop_thread_runs_at_lowest_priority():
    if not hasattr(os, "setpriority"):
        pytest.skip("os.setpriority unavailable on this platform")
    fake = _NiceRecordingLoop()
    control = daemon_wiring._ThreadControl()
    thread = threading.Thread(
        target=daemon_wiring._thread_main, args=(fake, control)
    )
    thread.start()
    try:
        assert fake.started.wait(timeout=10)
        assert fake.nice_seen == bounds.LOOP_THREAD_NICE == 19
    finally:
        if control.stop_event is not None and control.asyncio_loop is not None:
            control.asyncio_loop.call_soon_threadsafe(control.stop_event.set)
        thread.join(timeout=10)
        assert not thread.is_alive()


def test_nice_current_thread_never_raises(monkeypatch):
    # A platform without setpriority degrades to "not niced", never
    # an exception — the loop must still start.
    monkeypatch.delattr(os, "setpriority", raising=False)
    assert daemon_wiring._nice_current_thread(19) is False
