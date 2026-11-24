"""TASK-OBS-002 — rollback_deploy.sh safety-guard drill (git fixture based).

The rollback script's safety property is single-dimensional: it may only move
the deployment BACKWARD. These tests reproduce the critical guards against a
throwaway git repository:

  1. refuses a target that is not a commit
  2. refuses a target that equals the deployed HEAD
  3. refuses a target that is NOT an ancestor (would roll "forward"/sideways)
  4. accepts a genuine ancestor and performs the reset (with --yes)
  5. --dry-run changes nothing
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rollback_deploy.sh"


def run_rollback(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ROLLBACK_REPO_DIR"] = str(repo)
    # No systemctl in the fixture environment: the affected-service loop must
    # degrade to "no services to restart" rather than fail.
    env["PATH"] = "/usr/bin:/bin"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "friday_universe"
    r.mkdir()
    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(r), *a],
                              capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.email", "test@friday.local")
    git("config", "user.name", "Rollback Drill")
    for i, name in enumerate(["A", "B", "C"]):
        (r / name).write_text(f"state {name}\n")
        git("add", "-A")
        git("commit", "-m", f"commit {name}")
    return r


def head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def rev(repo: Path, ref: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", ref],
                          capture_output=True, text=True, check=True).stdout.strip()


def deploy(repo: Path, ref: str) -> None:
    subprocess.run(["git", "-C", str(repo), "reset", "--hard", ref],
                   capture_output=True, check=True)


class TestRollbackGuards:
    def test_rejects_non_commit_target(self, repo):
        res = run_rollback(repo, "0" * 40, "--yes")
        assert res.returncode != 0
        assert "not a commit object" in res.stderr

    def test_rejects_target_equal_to_current_head(self, repo):
        res = run_rollback(repo, head(repo), "--yes")
        assert res.returncode != 0
        assert "already the deployed HEAD" in res.stderr

    def test_rejects_forward_rollback(self, repo):
        # Deployed at B (detached, like a server mid-deploy), main still at C:
        # "rolling back" to C would move FORWARD: must refuse.
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--detach", "HEAD~1"],
                       capture_output=True, check=True)  # B
        res = run_rollback(repo, "main", "--yes")  # C
        assert res.returncode != 0
        assert "NOT an ancestor" in res.stderr
        assert head(repo) == rev(repo, "main~1")

    def test_rejects_sideways_rollback(self, repo):
        # A branch off B is not an ancestor of C: must refuse.
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "side", "HEAD~1"],
                       capture_output=True, check=True)
        (repo / "side").write_text("side\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "sideways"],
                       capture_output=True, check=True)
        side_sha = rev(repo, "side")
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"],
                       capture_output=True, check=True)
        res = run_rollback(repo, side_sha, "--yes")
        assert res.returncode != 0
        assert "NOT an ancestor" in res.stderr

    def test_accepts_true_ancestor_and_resets(self, repo):
        bad = head(repo)  # C
        res = run_rollback(repo, "HEAD~2", "--yes")  # A
        assert res.returncode == 0
        assert head(repo) == rev(repo, "HEAD~0") != bad
        assert "ROLLBACK DONE" in res.stdout

    def test_dry_run_changes_nothing(self, repo):
        before = head(repo)
        res = run_rollback(repo, "HEAD~1", "--dry-run")
        assert res.returncode == 0
        assert "DRY-RUN" in res.stdout
        assert head(repo) == before

    def test_unconfirmed_interactive_mode_aborts(self, repo, monkeypatch):
        before = head(repo)
        res = subprocess.run(
            ["bash", str(SCRIPT), "HEAD~1"],
            input="\n", capture_output=True, text=True,
            env={**os.environ, "ROLLBACK_REPO_DIR": str(repo), "PATH": "/usr/bin:/bin"},
            timeout=60,
        )
        assert res.returncode != 0
        assert "confirmation not given" in res.stderr
        assert head(repo) == before

    def test_affected_service_detection_from_changed_folders(self, repo):
        # Deployed at C which touched FRIDAY/**; rolling back to A must identify
        # FRIDAY as affected (print in dry-run) — no systemctl present, so the
        # unit filter yields empty, but the folder diff logic is exercised.
        (repo / "FRIDAY").mkdir()
        (repo / "FRIDAY" / "app.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "FRIDAY change"],
                       capture_output=True, check=True)
        res = run_rollback(repo, "HEAD~1", "--dry-run")
        assert res.returncode == 0
        # dry-run prints the would-restart list and a diffstat
        assert "would restart" in res.stdout


# --- TASK-OBS-013 (G3) — deterministic, LoadState-gated affected set ---
#
# A fake `systemctl` driven by a LoadState table stands in for the fleet's
# systemd. It implements only what rollback_deploy.sh calls: `show <unit>
# --property=LoadState --value` (with an optional fail-first counter to
# simulate transient D-Bus errors) and `list-unit-files` (kept for the
# old-code A/B harness; the fixed script never calls it).
FAKE_SYSTEMCTL = """#!/usr/bin/env bash
# $FAKE_LOAD_TABLE: lines "UNIT=LoadState"; missing unit -> not-found.
# $FAKE_SHOW_FAIL_FIRST: fail that many initial `show` calls (exit 1).
# $FAKE_COUNTER_FILE: per-invocation counter (created on demand).
table="$FAKE_LOAD_TABLE"
if [ "$1" = "show" ]; then
  unit="${2%.service}"
  n=0
  if [ -n "${FAKE_COUNTER_FILE:-}" ] && [ -f "$FAKE_COUNTER_FILE" ]; then
    n=$(wc -l < "$FAKE_COUNTER_FILE")
  fi
  if [ -n "${FAKE_COUNTER_FILE:-}" ]; then echo x >> "$FAKE_COUNTER_FILE"; fi
  if [ "${FAKE_SHOW_FAIL_FIRST:-0}" -gt "$n" ]; then exit 1; fi
  state=$(grep -E "^${unit}=" "$table" 2>/dev/null | cut -d= -f2)
  echo "${state:-not-found}"
  exit 0
fi
if [ "$1" = "list-unit-files" ]; then
  while IFS='=' read -r u s; do
    [ -n "$u" ] && echo "$u.service enabled enabled"
  done < "$table"
  exit 0
fi
echo "fake systemctl: unsupported: $*" >&2
exit 1
"""


def run_rollback_fake(repo, table, *args, fail_first=0):
    """Run the script with a fake systemctl backed by {unit: LoadState}."""
    import stat
    import tempfile
    bindir = Path(tempfile.mkdtemp(prefix="fakebin-"))
    fake = bindir / "systemctl"
    fake.write_text(FAKE_SYSTEMCTL)
    fake.chmod(0o755)
    table_file = bindir / "loads.txt"
    table_file.write_text("".join(f"{u}={s}\n" for u, s in table.items()))
    counter = bindir / "counter.txt"
    rundir = bindir / "systemd-run"
    rundir.mkdir()
    env = dict(os.environ)
    env["ROLLBACK_REPO_DIR"] = str(repo)
    env["PATH"] = f"{bindir}:/usr/bin:/bin"
    env["FAKE_LOAD_TABLE"] = str(table_file)
    env["FAKE_COUNTER_FILE"] = str(counter)
    env["FAKE_SHOW_FAIL_FIRST"] = str(fail_first)
    env["ROLLBACK_SYSTEMD_RUN_DIR"] = str(rundir)
    return subprocess.run(["bash", str(SCRIPT), *args],
                          capture_output=True, text=True, env=env, timeout=60)


def commit_folder(repo, folder, name="change"):
    (repo / folder).mkdir(exist_ok=True)
    (repo / folder / "app.py").write_text(f"{name}\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"],
                   capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", name],
                   capture_output=True, check=True)


def would_restart(res):
    for line in res.stdout.splitlines():
        if line.startswith("would restart:"):
            return line.split(":", 1)[1].strip()
    return None


S1_LOADS = {"FRIDAY": "loaded", "FRIDAY-Voice": "loaded",
            "Inference": "loaded", "Memora": "loaded",
            "Stratex": "masked", "Forge": "loaded", "Sentinel": "loaded",
            "Stratex-Daemon": "masked", "Futuris": "masked",
            "IntelX": "masked", "Cortex": "not-found", "VyralX": "not-found",
            "VyralX-Daemon": "not-found"}
S2_LOADS = {"VyralX": "masked", "Cortex": "loaded", "IntelX": "loaded",
            "Futuris": "loaded", "VyralX-Daemon": "masked",
            "Sentinel": "masked", "FRIDAY": "not-found",
            "Inference": "not-found", "Memora": "not-found",
            "Stratex": "not-found", "Forge": "not-found",
            "FRIDAY-Voice": "not-found", "Stratex-Daemon": "not-found"}


class TestObs013DeterministicLoadStateGate:
    def test_s1_masked_units_never_in_restart_set_and_deterministic(self, repo):
        commit_folder(repo, "FRIDAY")
        commit_folder(repo, "scripts")
        sets = set()
        for _ in range(5):
            res = run_rollback_fake(repo, S1_LOADS, "HEAD~1", "--dry-run")
            assert res.returncode == 0, res.stderr
            sets.add(would_restart(res))
        # TASK-REL-098 (2026-11-24 move): FRIDAY / Inference live on
        # FRIDAY-Server now — even though their S1 units are still
        # LoadState=loaded (disabled, not masked), the map excludes them,
        # so a rollback never revives the sleeping S1 backups.
        assert sets == {"Memora Forge Sentinel"}

    def test_s2_masked_units_never_in_restart_set(self, repo):
        commit_folder(repo, "VyralX")
        commit_folder(repo, "scripts")
        sets = set()
        for _ in range(3):
            res = run_rollback_fake(repo, S2_LOADS, "HEAD~1", "--dry-run")
            assert res.returncode == 0, res.stderr
            sets.add(would_restart(res))
        assert sets == {"Cortex IntelX Futuris"}

    def test_daemon_and_voice_follow_parent_agent_folder(self, repo):
        # TASK-REL-098 (2026-11-24 move): Stratex-Daemon moved to
        # Stratex-Server with Stratex, and FRIDAY-Voice moved to
        # FRIDAY-Server with FRIDAY — neither is a Server 1 candidate any
        # more, so a Stratex-only or FRIDAY-only change restarts nothing
        # on Server 1 even though the units are still LoadState=loaded.
        loads = dict(S1_LOADS)
        loads["Stratex-Daemon"] = "loaded"
        commit_folder(repo, "Stratex")
        res = run_rollback_fake(repo, loads, "HEAD~1", "--dry-run")
        assert res.returncode == 0, res.stderr
        assert would_restart(res) == "<none>"
        commit_folder(repo, "FRIDAY")
        res = run_rollback_fake(repo, S1_LOADS, "HEAD~1", "--dry-run")
        assert res.returncode == 0, res.stderr
        assert would_restart(res) == "<none>"
        # Folder-following itself is preserved on Server 2: VyralX-Daemon
        # still restarts with a VyralX change when it is loaded there.
        s2 = dict(S2_LOADS)
        s2["VyralX-Daemon"] = "loaded"
        commit_folder(repo, "VyralX")
        res = run_rollback_fake(repo, s2, "HEAD~1", "--dry-run")
        assert res.returncode == 0, res.stderr
        assert would_restart(res) == "VyralX-Daemon"

    def test_transient_show_failure_is_retried_not_dropped(self, repo):
        commit_folder(repo, "FRIDAY")
        commit_folder(repo, "scripts")
        res = run_rollback_fake(repo, S1_LOADS, "HEAD~1", "--dry-run",
                                fail_first=2)
        assert res.returncode == 0, res.stderr
        assert would_restart(res) == "Memora Forge Sentinel"

    def test_persistent_show_failure_aborts_before_reset(self, repo):
        commit_folder(repo, "FRIDAY")
        before = head(repo)
        res = run_rollback_fake(repo, S1_LOADS, "HEAD~1", "--yes",
                                fail_first=999)
        assert res.returncode != 0
        assert "LoadState" in res.stderr
        assert head(repo) == before
        assert "ROLLBACK DONE" not in res.stdout
