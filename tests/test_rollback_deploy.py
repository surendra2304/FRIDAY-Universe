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
