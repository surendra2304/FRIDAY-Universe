"""Tests for TASK-FRD-024 — the daemon's self-generated task source.

TASK-FRD-023 armed the autonomous daemon at boot, but its only task
source remained manual submission: an armed daemon with an empty queue
idles forever (the state it sat in, unnoticed, from 2026-11-10 to the
2026-11-17 diagnosis). ``friday/autonomous/task_source.py`` closes
that: a closed catalogue of triggers over state FRIDAY can verify
herself (fleet probe anomalies, a stale Stratex heartbeat, repeated
daemon goal failures) seeds READ-ONLY verification goals through the
existing ``submit_goal`` path.

These tests pin the contract:

* each catalogue trigger fires on its evidence and only on it;
* the owner's flag gates seeding on every evaluation, and the
  dedicated kill switch stops it even with the flag on;
* seeding happens only into a fully idle daemon;
* cooldowns, the reported-failure dedupe, the per-evaluation cap and
  the global daily cap all hold, and survive a source restart
  (persisted state);
* the daemon's loop actually evaluates the source, and a failing
  source never breaks the loop.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from friday.autonomous import task_source
from friday.autonomous.task_source import DaemonTaskSource


class _FakeGoal:
    def __init__(self, text, priority=0, metadata=None):
        self.id = f"goal_{abs(hash(text)) % 10_000_000}"
        self.goal = text
        self.priority = priority
        self.metadata = metadata or {}
        self.status = "QUEUED"
        self.completed_at = 0.0


class _FakeDaemon:
    """The slice of AutonomousDaemon the source touches."""

    def __init__(self):
        self._goal_queue: list = []
        self._running_goals: dict = {}
        self._completed_goals: list = []
        self.submitted: list[_FakeGoal] = []

    def submit_goal(self, goal_text, priority=0, metadata=None):
        goal = _FakeGoal(goal_text, priority, metadata)
        self.submitted.append(goal)
        return goal


def _status(agent_id="stratex", status="UNREACHABLE", name="Stratex"):
    return SimpleNamespace(
        id=agent_id,
        name=name,
        status=status,
        details="probe failed",
        last_checked="2026-11-18T00:00:00+00:00",
    )


def _failed_goal(goal_id, *, age_s=60.0, source=None):
    return SimpleNamespace(
        id=goal_id,
        goal=f"goal {goal_id}",
        status="FAILED",
        completed_at=time.time() - age_s,
        metadata={"source": source} if source else {},
    )


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(
        task_source,
        "get_settings",
        lambda: SimpleNamespace(autonomous_mode=True),
    )
    monkeypatch.delenv("FRIDAY_AUTONOMOUS_TASK_SOURCE", raising=False)
    monkeypatch.delenv("FRIDAY_AUTONOMOUS_TASK_SOURCE_DAILY_CAP", raising=False)


def _fleet_of(statuses):
    async def _fleet():
        return statuses

    return _fleet


def _source(tmp_path, *, fleet=None, stratex_age=None):
    if fleet is None:
        fleet_fn = _fleet_of([])
    elif callable(fleet):
        fleet_fn = fleet
    else:
        fleet_fn = _fleet_of(fleet)
    return DaemonTaskSource(
        state_path=tmp_path / "task_source_state.json",
        fleet_statuses=fleet_fn,
        stratex_heartbeat_age_s=stratex_age or (lambda: None),
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# -- gates -------------------------------------------------------------------


def test_flag_off_means_no_seeding_even_with_anomalies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        task_source,
        "get_settings",
        lambda: SimpleNamespace(autonomous_mode=False),
    )
    src = _source(tmp_path, fleet=[_status()])
    daemon = _FakeDaemon()
    assert _run(src.maybe_seed(daemon)) == []
    assert daemon.submitted == []


def test_kill_switch_stops_seeding_with_flag_on(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_AUTONOMOUS_TASK_SOURCE", "off")
    src = _source(tmp_path, fleet=[_status()])
    daemon = _FakeDaemon()
    assert _run(src.maybe_seed(daemon)) == []
    assert daemon.submitted == []


def test_no_seeding_while_owner_work_is_queued_or_running(tmp_path):
    src = _source(tmp_path, fleet=[_status()])
    daemon = _FakeDaemon()
    daemon._goal_queue.append(_FakeGoal("owner goal"))
    assert _run(src.maybe_seed(daemon)) == []
    daemon._goal_queue.clear()
    daemon._running_goals["g"] = _FakeGoal("running")
    assert _run(src.maybe_seed(daemon)) == []
    assert daemon.submitted == []


# -- fleet triggers ------------------------------------------------------------


def test_unhealthy_agent_seeds_one_readonly_goal_with_evidence(tmp_path):
    src = _source(tmp_path, fleet=[_status(), _status("memora", "ONLINE", "Memora")])
    daemon = _FakeDaemon()
    seeded = _run(src.maybe_seed(daemon))
    assert len(seeded) == 1
    goal = daemon.submitted[0]
    assert goal.metadata["source"] == "autonomous_task_source"
    assert goal.metadata["trigger"] == "fleet_agent_unhealthy"
    assert goal.metadata["evidence"]["agent"] == "stratex"
    assert goal.metadata["evidence"]["status"] == "UNREACHABLE"
    assert "Read-only" in goal.goal
    assert goal.priority == -1


def test_healthy_statuses_seed_nothing(tmp_path):
    fleet = [_status("memora", "ONLINE", "Memora"), _status("forge", "REACHABLE", "Forge")]
    src = _source(tmp_path, fleet=fleet)
    assert _run(src.maybe_seed(_FakeDaemon())) == []


def test_fleet_cooldown_blocks_immediate_reseed(tmp_path):
    src = _source(tmp_path, fleet=[_status()])
    daemon = _FakeDaemon()
    assert len(_run(src.maybe_seed(daemon))) == 1
    daemon._goal_queue.clear()  # the seeded goal "ran"
    assert _run(src.maybe_seed(daemon)) == []


def test_fleet_poll_failure_seeds_its_own_trigger(tmp_path):
    async def _boom():
        raise RuntimeError("connect failed")

    src = _source(tmp_path, fleet=_boom)
    daemon = _FakeDaemon()
    assert len(_run(src.maybe_seed(daemon))) == 1
    assert daemon.submitted[0].metadata["trigger"] == "fleet_poll_failing"
    assert "RuntimeError" in daemon.submitted[0].metadata["evidence"]["error"]


def test_per_evaluation_cap_is_two(tmp_path):
    fleet = [
        _status("stratex", "UNREACHABLE", "Stratex"),
        _status("memora", "OFFLINE", "Memora"),
        _status("forge", "DEGRADED", "Forge"),
    ]
    src = _source(tmp_path, fleet=fleet)
    daemon = _FakeDaemon()
    assert len(_run(src.maybe_seed(daemon))) == 2


# -- Stratex trigger -----------------------------------------------------------


def test_stratex_stale_heartbeat_seeds_readonly_status_goal(tmp_path):
    src = _source(tmp_path, stratex_age=lambda: 900.0)
    daemon = _FakeDaemon()
    assert len(_run(src.maybe_seed(daemon))) == 1
    goal = daemon.submitted[0]
    assert goal.metadata["trigger"] == "stratex_heartbeat_stale"
    assert goal.metadata["evidence"]["heartbeat_age_s"] == 900
    assert "do not place, close, pause or modify any" in goal.goal


def test_stratex_fresh_or_unresolvable_heartbeat_seeds_nothing(tmp_path):
    fresh = _source(tmp_path / "a", stratex_age=lambda: 30.0)
    assert _run(fresh.maybe_seed(_FakeDaemon())) == []
    unresolvable = _source(tmp_path / "b", stratex_age=lambda: None)
    assert _run(unresolvable.maybe_seed(_FakeDaemon())) == []


# -- goal-failure trigger --------------------------------------------------------


def test_two_fresh_failures_seed_a_review_goal_once(tmp_path):
    src = _source(tmp_path)
    daemon = _FakeDaemon()
    daemon._completed_goals = [_failed_goal("g1")]
    assert _run(src.maybe_seed(daemon)) == []  # below threshold
    daemon._completed_goals.append(_failed_goal("g2"))
    assert len(_run(src.maybe_seed(daemon))) == 1
    assert daemon.submitted[0].metadata["trigger"] == "daemon_goals_failing"
    # The same failures are deduped: no second review for the same ids.
    daemon._goal_queue.clear()
    assert _run(src.maybe_seed(daemon)) == []


def test_source_seeded_failures_never_trigger_a_review(tmp_path):
    src = _source(tmp_path)
    daemon = _FakeDaemon()
    daemon._completed_goals = [
        _failed_goal("s1", source="autonomous_task_source"),
        _failed_goal("s2", source="autonomous_task_source"),
    ]
    assert _run(src.maybe_seed(daemon)) == []


def test_old_failures_are_outside_the_lookback(tmp_path):
    src = _source(tmp_path)
    daemon = _FakeDaemon()
    daemon._completed_goals = [
        _failed_goal("g1", age_s=7 * 3600.0),
        _failed_goal("g2", age_s=7 * 3600.0),
    ]
    assert _run(src.maybe_seed(daemon)) == []


# -- daily cap + persistence -----------------------------------------------------


def test_daily_cap_bounds_total_seeds(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_AUTONOMOUS_TASK_SOURCE_DAILY_CAP", "1")
    fleet = [_status("stratex", "UNREACHABLE", "Stratex")]
    src = _source(tmp_path, fleet=fleet, stratex_age=lambda: 900.0)
    daemon = _FakeDaemon()
    assert len(_run(src.maybe_seed(daemon))) == 1  # two triggers ready, cap 1


def test_cooldowns_survive_a_source_restart(tmp_path):
    state = tmp_path / "task_source_state.json"
    fleet = [_status()]
    first = DaemonTaskSource(
        state_path=state,
        fleet_statuses=_fleet_of(fleet),
        stratex_heartbeat_age_s=lambda: None,
    )
    daemon = _FakeDaemon()
    assert len(_run(first.maybe_seed(daemon))) == 1
    second = DaemonTaskSource(
        state_path=state,
        fleet_statuses=_fleet_of(fleet),
        stratex_heartbeat_age_s=lambda: None,
    )
    assert _run(second.maybe_seed(_FakeDaemon())) == []


# -- daemon wiring ---------------------------------------------------------------


def test_daemon_loop_evaluates_the_source_and_survives_its_failure():
    from friday.autonomous.daemon import AutonomousDaemon

    daemon = AutonomousDaemon()
    daemon._task_source_interval_s = 0.0
    daemon._heartbeat_interval_s = 3600.0

    calls: list = []

    class _RecordingSource:
        async def maybe_seed(self, d):
            calls.append(d)
            return []

    daemon._task_source = _RecordingSource()

    class _ExplodingSource:
        async def maybe_seed(self, d):
            raise RuntimeError("source broke")

    async def _both_spins() -> None:
        # One event loop for both spins: the daemon's wake Event binds
        # to the first loop that waits on it.
        await _spin(daemon)
        assert calls, "the loop never evaluated the task source"
        daemon._task_source = _ExplodingSource()
        await _spin(daemon)  # must return normally: the loop survived

    _run(_both_spins())
    assert daemon.is_running is False  # _spin stopped it cleanly


async def _spin(daemon, seconds: float = 0.35) -> None:
    await daemon.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await daemon.stop()
