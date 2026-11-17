"""TASK-OBS-005 — deploy watchdog branch naming tests.

The OBS-004 watchdog (TASK-OBS-004) compared deployed HEAD vs
origin/main but never named the checkout's branch. Fleet CD
fast-forwards the CURRENT checkout and never switches branches, so a
checkout parked on a non-main branch strands merged work even when its
HEAD momentarily equals main's (defect D9, three recurrences) — and a
HEAD-only alert left the human to guess the one fact that explains it.

TASK-OBS-005 threads the branch through the watchdog: it is stored on
the server state, a known non-main branch is itself a divergence
reason, and the divergence + recovery alert payloads name the branch.
All HEAD/branch sources here are fakes or scratch git repos: no test
touches the production fleet.
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
    ServerDeployState,
    git_checkout_branch,
)

MAIN = "a" * 40
OLD = "b" * 40
PARKED = "claude/task-rel-012-verified"
T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _watchdog_with_capture(grace: int = 1800):
    deltas: list = []
    wd = DeployWatchdog(grace_seconds=grace, alert_sink=deltas.append)
    return wd, deltas


def _findings(deltas):
    return [d for d in deltas if d.change_type == ChangeType.NEW_FINDING]


# -- the parked-checkout case: HEAD == main, branch != main ---------------


def test_parked_branch_at_main_head_diverges_and_alert_names_branch():
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-2", MAIN, MAIN, tree_clean=True, branch=PARKED, now=T0)
    assert state.status == DeployStatus.DIVERGED
    assert state.branch == PARKED
    state = wd.observe(
        "server-2",
        MAIN,
        MAIN,
        tree_clean=True,
        branch=PARKED,
        now=T0 + timedelta(seconds=1800),
    )
    assert state.status == DeployStatus.ALERTED
    findings = _findings(deltas)
    assert len(findings) == 1
    assert PARKED in findings[0].description
    assert "branch" in findings[0].description.lower()


def test_parked_branch_recovers_when_returned_to_main():
    wd, deltas = _watchdog_with_capture(grace=60)
    wd.observe("server-2", MAIN, MAIN, branch=PARKED, now=T0)
    wd.observe("server-2", MAIN, MAIN, branch=PARKED, now=T0 + timedelta(seconds=61))
    assert len(_findings(deltas)) == 1
    state = wd.observe("server-2", MAIN, MAIN, branch="main", now=T0 + timedelta(seconds=120))
    assert state.status == DeployStatus.IN_SYNC
    resolved = [d for d in deltas if d.change_type == ChangeType.RESOLVED_FINDING]
    assert len(resolved) == 1
    assert "'main'" in resolved[0].description


# -- branch naming on the classic HEAD-divergence alert ---------------------


def test_head_divergence_alert_names_main_branch():
    wd, deltas = _watchdog_with_capture()
    wd.observe("server-1", OLD, MAIN, branch="main", now=T0)
    wd.observe("server-1", OLD, MAIN, branch="main", now=T0 + timedelta(seconds=1800))
    findings = _findings(deltas)
    assert len(findings) == 1
    assert "Checkout branch: 'main'" in findings[0].description


def test_alert_engine_message_carries_the_branch():
    # End-to-end through the real AlertEngine, as in the OBS-004 suite:
    # the human-facing alert message itself must name the branch.
    class RecordingDispatcher:
        def __init__(self):
            self.sent = []

        def dispatch(self, alert, webhook_urls=None):
            self.sent.append(alert)
            return {"telegram": True}

    dispatcher = RecordingDispatcher()
    engine = AlertEngine(dispatcher=dispatcher)
    wd = DeployWatchdog(
        grace_seconds=60,
        state_store=InMemoryDeployStateStore(),
        alert_sink=engine.process_delta,
    )
    wd.observe("server-2", MAIN, MAIN, branch=PARKED, now=T0)
    wd.observe("server-2", MAIN, MAIN, branch=PARKED, now=T0 + timedelta(seconds=61))
    alerts = engine.list_alerts()
    assert len(alerts) == 1
    assert alerts[0].severity == SeverityLevel.HIGH
    assert PARKED in alerts[0].message
    assert len(dispatcher.sent) == 1


# -- non-regression: unknown branch behaves exactly as OBS-004 did ---------


def test_no_branch_reported_preserves_legacy_behaviour():
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-2", MAIN, MAIN, tree_clean=True, now=T0)
    assert state.status == DeployStatus.IN_SYNC
    assert state.branch is None
    wd.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=1))
    wd.observe("server-2", OLD, MAIN, now=T0 + timedelta(seconds=1801))
    findings = _findings(deltas)
    assert len(findings) == 1
    assert "Checkout branch" not in findings[0].description


def test_main_branch_in_sync_never_alerts():
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-2", MAIN, MAIN, tree_clean=True, branch="main", now=T0)
    assert state.status == DeployStatus.IN_SYNC
    state = wd.observe(
        "server-2", MAIN, MAIN, tree_clean=True, branch="main", now=T0 + timedelta(days=1)
    )
    assert state.status == DeployStatus.IN_SYNC
    assert deltas == []


def test_old_state_payload_without_branch_still_validates():
    # State files written before TASK-OBS-005 carry no branch key.
    state = ServerDeployState.model_validate({"server": "server-2", "deployed_head": MAIN})
    assert state.branch is None


# -- provider threading ------------------------------------------------------


def test_check_server_threads_branch_provider():
    wd, _ = _watchdog_with_capture()
    state = wd.check_server(
        "server-2",
        lambda: MAIN,
        lambda: MAIN,
        deployed_branch_provider=lambda: PARKED,
        now=T0,
    )
    assert state.branch == PARKED
    assert state.status == DeployStatus.DIVERGED


def test_check_server_branch_provider_failure_is_unknown_branch():
    wd, _ = _watchdog_with_capture()

    def boom():
        raise RuntimeError("git exploded")

    state = wd.check_server(
        "server-2",
        lambda: MAIN,
        lambda: MAIN,
        deployed_branch_provider=boom,
        now=T0,
    )
    assert state.branch is None
    assert state.status == DeployStatus.IN_SYNC


# -- the git branch provider against scratch repos ----------------------------


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_git_checkout_branch_against_scratch_repos(tmp_path):
    repo = tmp_path / "clone"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "watchdog@test")
    _git(repo, "config", "user.name", "Watchdog Test")
    (repo / "f.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "one")
    _git(repo, "branch", "-M", "main")
    assert git_checkout_branch(str(repo)) == "main"
    _git(repo, "checkout", "-b", PARKED)
    assert git_checkout_branch(str(repo)) == PARKED
    _git(repo, "checkout", "--detach", "HEAD")
    assert git_checkout_branch(str(repo)) is None  # detached: unknown, not a name
    assert git_checkout_branch(str(tmp_path / "does-not-exist")) is None
