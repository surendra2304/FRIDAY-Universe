"""TASK-OBS-004 — deploy watchdog tests.

All HEAD sources are fakes or scratch git repos: no test touches the
production fleet. The alert sink is the real AlertEngine (with a
recording dispatcher) so the operations alert path itself is exercised.
"""

import subprocess
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.alerting import AlertEngine
from sentinel.modules.operations.baseline import ChangeType
from sentinel.modules.operations.deploy_watchdog import (
    DeployStatus,
    DeployWatchdog,
    InMemoryDeployStateStore,
    JsonDeployStateStore,
    git_checkout_head,
    git_remote_main_head,
)

MAIN = "a" * 40
OLD = "b" * 40
NEWER_MAIN = "c" * 40
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


class RecordingDispatcher:
    def __init__(self):
        self.sent = []

    def dispatch(self, alert, webhook_urls=None):
        self.sent.append(alert)
        return {"telegram": True}


def _watchdog(grace=1800):
    dispatcher = RecordingDispatcher()
    engine = AlertEngine(dispatcher=dispatcher)
    watchdog = DeployWatchdog(
        grace_seconds=grace,
        state_store=InMemoryDeployStateStore(),
        alert_sink=engine.process_delta,
    )
    return watchdog, engine, dispatcher


def test_in_sync_never_alerts():
    watchdog, engine, dispatcher = _watchdog()
    state = watchdog.observe("server-2", MAIN, MAIN, now=T0)
    assert state.status == DeployStatus.IN_SYNC
    assert engine.list_alerts() == []
    assert dispatcher.sent == []


def test_divergence_inside_grace_does_not_alert():
    watchdog, engine, dispatcher = _watchdog(grace=1800)
    state = watchdog.observe("server-2", OLD, MAIN, now=T0)
    assert state.status == DeployStatus.DIVERGED
    state = watchdog.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=1799))
    assert state.status == DeployStatus.DIVERGED
    assert engine.list_alerts() == []
    assert dispatcher.sent == []


def test_divergence_beyond_grace_alerts_once_through_alert_engine():
    watchdog, engine, dispatcher = _watchdog(grace=1800)
    watchdog.observe("server-2", OLD, MAIN, now=T0)
    state = watchdog.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=1800))
    assert state.status == DeployStatus.ALERTED
    alerts = engine.list_alerts()
    assert len(alerts) == 1
    assert alerts[0].target_ref == "deploy:server-2"
    assert alerts[0].severity == SeverityLevel.HIGH
    assert OLD[:8] in alerts[0].message and MAIN[:8] in alerts[0].message
    # Dispatched exactly once through the shared-channel dispatcher.
    assert len(dispatcher.sent) == 1
    assert alerts[0].dispatched is True
    # Still diverged on the next cycle: no second alert, no re-dispatch.
    state = watchdog.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=3600))
    assert state.status == DeployStatus.ALERTED
    assert len(engine.list_alerts()) == 1
    assert len(dispatcher.sent) == 1


def test_recovery_emits_resolved_delta_and_closes_episode():
    watchdog, engine, dispatcher = _watchdog(grace=60)
    watchdog.observe("server-1", OLD, MAIN, now=T0)
    watchdog.observe("server-1", OLD, MAIN, now=T0 + timedelta(seconds=61))
    assert len(engine.list_alerts()) == 1
    state = watchdog.observe("server-1", MAIN, MAIN, now=T0 + timedelta(seconds=120))
    assert state.status == DeployStatus.IN_SYNC
    assert state.diverged_since is None and state.alerted is False
    alerts = engine.list_alerts()
    assert len(alerts) == 2
    recovery = [a for a in alerts if a.change_type == ChangeType.RESOLVED_FINDING]
    assert len(recovery) == 1
    assert "back in sync" in recovery[0].message


def test_failed_read_is_unknown_and_preserves_episode_clock():
    watchdog, engine, _ = _watchdog(grace=1800)
    watchdog.observe("server-2", OLD, MAIN, now=T0)
    state = watchdog.observe("server-2", None, None, now=T0 + timedelta(seconds=600))
    assert state.status == DeployStatus.UNKNOWN
    assert state.diverged_since == T0  # episode clock untouched
    assert state.read_failures == 1
    # The episode still alerts on the original schedule once reads recover.
    state = watchdog.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=1801))
    assert state.status == DeployStatus.ALERTED
    assert len(engine.list_alerts()) == 1


def test_main_advancing_mid_episode_keeps_single_alert():
    watchdog, engine, dispatcher = _watchdog(grace=60)
    watchdog.observe("server-2", OLD, MAIN, now=T0)
    watchdog.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=61))
    state = watchdog.observe("server-2", OLD, NEWER_MAIN, now=T0 + timedelta(seconds=3600))
    assert state.status == DeployStatus.ALERTED
    assert state.main_head == NEWER_MAIN
    assert len(engine.list_alerts()) == 1
    assert len(dispatcher.sent) == 1


def test_servers_are_tracked_independently():
    watchdog, engine, _ = _watchdog(grace=60)
    watchdog.observe("server-1", OLD, MAIN, now=T0)
    state2 = watchdog.observe("server-2", MAIN, MAIN, now=T0)
    assert state2.status == DeployStatus.IN_SYNC
    watchdog.observe("server-1", OLD, MAIN, now=T0 + timedelta(seconds=61))
    targets = {a.target_ref for a in engine.list_alerts()}
    assert targets == {"deploy:server-1"}


def test_json_state_store_survives_restart_without_realerting(tmp_path):
    path = tmp_path / "watchdog-state.json"
    engine = AlertEngine()
    first = DeployWatchdog(
        grace_seconds=60,
        state_store=JsonDeployStateStore(path),
        alert_sink=engine.process_delta,
    )
    first.observe("server-2", OLD, MAIN, now=T0)
    first.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=61))
    assert len(engine.list_alerts()) == 1
    # A "restarted" watchdog over the same state file must not re-alert.
    second = DeployWatchdog(
        grace_seconds=60,
        state_store=JsonDeployStateStore(path),
        alert_sink=engine.process_delta,
    )
    state = second.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=3600))
    assert state.status == DeployStatus.ALERTED
    assert state.alerted is True
    assert len(engine.list_alerts()) == 1


def test_check_server_with_raising_providers_is_unknown():
    watchdog, engine, _ = _watchdog()

    def boom():
        raise RuntimeError("git exploded")

    state = watchdog.check_server("server-2", boom, boom, now=T0)
    assert state.status == DeployStatus.UNKNOWN
    assert engine.list_alerts() == []


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_git_providers_against_scratch_repos(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "watchdog@test")
    _git(clone, "config", "user.name", "Watchdog Test")
    (clone / "f.txt").write_text("one\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "one")
    _git(clone, "branch", "-M", "main")
    _git(clone, "push", "origin", "main")
    first_head = git_checkout_head(str(clone))
    assert first_head is not None and len(first_head) == 40
    assert git_remote_main_head(str(origin)) == first_head
    # Advance main from the clone, then rewind the clone's HEAD to stage
    # a deployed-HEAD divergence against the advanced origin/main.
    (clone / "f.txt").write_text("two\n")
    _git(clone, "commit", "-am", "two")
    _git(clone, "push", "origin", "main")
    _git(clone, "reset", "--hard", first_head)
    assert git_checkout_head(str(clone)) == first_head
    assert git_remote_main_head(str(origin)) != first_head
    assert git_checkout_head(str(tmp_path / "does-not-exist")) is None
