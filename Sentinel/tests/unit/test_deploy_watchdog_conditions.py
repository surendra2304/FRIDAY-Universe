"""TASK-OBS-004 supervisor-condition tests.

Cover the AUDIT-2 implementation conditions the base suite predates:
(1) tree state, not just HEAD — a dirty tracked tree at the current
HEAD diverges (the deploy script refuses dirty trees); (2) fail-closed
reference — a failed origin/main read alerts (deduplicated) and its
recovery resolves; plus the git tree provider against a scratch repo.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta

from sentinel.modules.operations.baseline import ChangeType
from sentinel.modules.operations.deploy_watchdog import (
    DeployStatus,
    DeployWatchdog,
    git_checkout_head,
    git_checkout_tree_clean,
)

MAIN = "a" * 40
T0 = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def _watchdog_with_capture(grace: int = 1800):
    deltas: list = []
    wd = DeployWatchdog(grace_seconds=grace, alert_sink=deltas.append)
    return wd, deltas


def test_dirty_tree_at_current_head_diverges_and_alerts():
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-2", MAIN, MAIN, tree_clean=True, now=T0)
    assert state.status == DeployStatus.IN_SYNC
    state = wd.observe("server-2", MAIN, MAIN, tree_clean=False, now=T0 + timedelta(seconds=60))
    assert state.status == DeployStatus.DIVERGED
    state = wd.observe(
        "server-2", MAIN, MAIN, tree_clean=False, now=T0 + timedelta(seconds=60 + 1800)
    )
    assert state.status == DeployStatus.ALERTED
    findings = [d for d in deltas if d.change_type == ChangeType.NEW_FINDING]
    assert len(findings) == 1
    assert "dirty" in findings[0].description


def test_tree_cleaning_again_recovers():
    wd, deltas = _watchdog_with_capture(grace=10)
    wd.observe("server-1", MAIN, MAIN, tree_clean=False, now=T0)
    wd.observe("server-1", MAIN, MAIN, tree_clean=False, now=T0 + timedelta(seconds=30))
    state = wd.observe("server-1", MAIN, MAIN, tree_clean=True, now=T0 + timedelta(seconds=60))
    assert state.status == DeployStatus.IN_SYNC
    resolved = [d for d in deltas if d.change_type == ChangeType.RESOLVED_FINDING]
    assert len(resolved) == 1


def test_untracked_only_tree_state_is_not_divergence():
    # tree_clean None (unreported) must not diverge on the tree axis.
    wd, _ = _watchdog_with_capture()
    state = wd.observe("server-1", MAIN, MAIN, tree_clean=None, now=T0)
    assert state.status == DeployStatus.IN_SYNC


def test_failed_reference_read_alerts_fail_closed_once():
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-1", MAIN, None, now=T0)
    assert state.status == DeployStatus.UNKNOWN
    wd.observe("server-1", MAIN, None, now=T0 + timedelta(seconds=600))
    ref = [d for d in deltas if d.target_ref == "deploy:reference"]
    assert len(ref) == 1
    assert ref[0].change_type == ChangeType.NEW_FINDING
    # Recovery of the reference read resolves the fail-closed alert.
    wd.observe("server-1", MAIN, MAIN, now=T0 + timedelta(seconds=1200))
    ref = [d for d in deltas if d.target_ref == "deploy:reference"]
    assert len(ref) == 2
    assert ref[1].change_type == ChangeType.RESOLVED_FINDING


def test_both_reads_failed_is_unknown_without_reference_alert():
    # With neither read succeeding, the failure cannot be attributed to
    # the reference specifically — no reference alert, still UNKNOWN.
    wd, deltas = _watchdog_with_capture()
    state = wd.observe("server-1", None, None, now=T0)
    assert state.status == DeployStatus.UNKNOWN
    assert deltas == []


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_git_checkout_tree_clean_against_scratch_repo(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "watchdog@test")
    _git(repo, "config", "user.name", "Watchdog Test")
    (repo / "tracked.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "one")
    assert git_checkout_head(str(repo)) is not None
    assert git_checkout_tree_clean(str(repo)) is True
    # Untracked runtime files are a normal fleet condition: still clean.
    (repo / "runtime.log").write_text("noise\n")
    assert git_checkout_tree_clean(str(repo)) is True
    # A tracked modification is the stranding condition: dirty.
    (repo / "tracked.txt").write_text("two\n")
    assert git_checkout_tree_clean(str(repo)) is False
    assert git_checkout_tree_clean(str(tmp_path / "does-not-exist")) is None
