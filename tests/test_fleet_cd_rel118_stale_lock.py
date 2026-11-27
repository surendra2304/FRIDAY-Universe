"""TASK-REL-118 — Fleet CD stale index.lock recovery tests.

Fleet CD (`.github/workflows/deploy-monorepo.yml`) failed BOTH deploy jobs
in the only two runs that actually triggered a deploy after the REL-102
break (runs 45969056089 and 46006566115 — 2026-11-27 14:22 and 18:52 IST):

(a) Server 1 failed the ff-only merge in both runs with
    "Unable to create '/opt/friday_universe/.git/index.lock': File exists"
    — a lock left by a crashed/interrupted git process, stranding the
    checkout at bf3c76c9 across both attempts 4.5h apart. No live git
    process holds it (a concurrent process does not survive 4.5h across
    two deploy attempts); the lock is stale.
(b) Server 2 failed the MAIN-BRANCH guard (TASK-OBS-005) in both runs:
    checkout parked on `musetp13/task-frd-046-storage-repair-sequences`.
    The guard is correct — the checkout must be returned to main on the
    server; no workflow change can or should do that. This test file
    covers only leg (a); leg (b) is operational, not code.

The fix is a marked stale-lock recovery block inside both deploy jobs'
SAFE CHECKOUT sections, between the branch guard and the dirty-tree
guard: when `.git/index.lock` exists, refuse loudly if any git process
is working in this checkout (cwd-scoped pgrep — a live process means a
real concurrent operation, and deleting its lock would corrupt the
index); otherwise remove the stale lock and proceed. pgrep missing is
also a refusal — the lock is never removed blind.

These tests extract that exact block from the workflow file and EXECUTE
it under bash in scratch git repos, so what is tested is what deploys:

(a) a stale lock with no git process running -> block exits 0 and the
    lock is gone (deploy proceeds);
(b) a lock with a live git process in this checkout -> block exits 1,
    names the refusal, and the lock is preserved;
(c) no lock at all -> block exits 0 and changes nothing;
(d) a lock with a git process running in a DIFFERENT directory -> block
    exits 0 and removes the lock (only this checkout's processes count).

Plus structural pins: exactly two recovery blocks (one per deploy job),
byte-identical, each positioned after its job's branch guard and before
its job's dirty-tree guard.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"

BEGIN = "# BEGIN STALE-LOCK RECOVERY (TASK-REL-118)"
END = "# END STALE-LOCK RECOVERY (TASK-REL-118)"
BRANCH_BEGIN = "# BEGIN MAIN-BRANCH GUARD (TASK-OBS-005)"
DIRTY_BEGIN = "# BEGIN DIRTY-TREE GUARD (TASK-REL-102)"


def _blocks() -> list[str]:
    """Extract the executable bash of each marked recovery block."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    current: list[str] | None = None
    indent = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(BEGIN):
            indent = line[: len(line) - len(line.lstrip())]
            current = [line]
            continue
        if current is not None:
            current.append(line)
            if stripped.startswith(END):
                blocks.append(
                    "\n".join(
                        ln[len(indent):] if ln.startswith(indent) else ln
                        for ln in current
                    )
                )
                current = None
    return blocks


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "lock@test")
    _git(repo, "config", "user.name", "Lock Test")
    _git(repo, "branch", "-M", "main")
    (repo / "f.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "one")
    return repo


def _run(block: str, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", block],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _fake_git_process(cwd: Path) -> subprocess.Popen:
    """A live process whose comm is `git`, running in `cwd`.

    Copies /bin/sleep to a file named `git` and executes it: the kernel
    comm follows the executed file's basename, so `pgrep -x git` matches
    it exactly like a real git process, without touching any repo.
    """
    fakebin = cwd.parent / "fakebin"
    fakebin.mkdir(exist_ok=True)
    fake_git = fakebin / "git"
    if not fake_git.exists():
        shutil.copy("/bin/sleep", fake_git)
    proc = subprocess.Popen(
        [str(fake_git), "30"], cwd=cwd, stdout=subprocess.DEVNULL
    )
    for _ in range(50):
        found = subprocess.run(
            ["pgrep", "-x", "git"], capture_output=True, text=True
        ).stdout.split()
        if str(proc.pid) in found:
            return proc
        time.sleep(0.1)
    raise AssertionError("fake git process did not appear under pgrep -x git")


# -- structural pins -------------------------------------------------------


def test_two_identical_stale_lock_recovery_blocks() -> None:
    blocks = _blocks()
    assert len(blocks) == 2, "expected one recovery block per deploy job"
    assert blocks[0] == blocks[1], "the two jobs' blocks must stay identical"


def test_recovery_sits_between_branch_guard_and_dirty_guard() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    branch_at = [i for i in range(len(text)) if text.startswith(BRANCH_BEGIN, i)]
    lock_at = [i for i in range(len(text)) if text.startswith(BEGIN, i)]
    dirty_at = [i for i in range(len(text)) if text.startswith(DIRTY_BEGIN, i)]
    assert len(branch_at) == 2 and len(lock_at) == 2 and len(dirty_at) == 2
    assert branch_at[0] < lock_at[0] < dirty_at[0] < branch_at[1] < lock_at[1] < dirty_at[1], (
        "each job must run branch guard, then stale-lock recovery, then dirty-tree guard"
    )


# -- behavioural proof: the observed Server 1 state ------------------------


def test_stale_lock_removed_when_no_git_process_running(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    lock = repo / ".git" / "index.lock"
    lock.write_text("")  # crashed git left this behind; no process holds it
    result = _run(_blocks()[0], repo)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert not lock.exists(), "the stale lock must be gone so the deploy can proceed"
    assert "Stale .git/index.lock" in output


def test_live_git_process_refuses_and_preserves_lock(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    lock = repo / ".git" / "index.lock"
    lock.write_text("")
    proc = _fake_git_process(repo)
    try:
        result = _run(_blocks()[0], repo)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "TASK-REL-118" in output
    assert str(proc.pid) in output, "the refusal must name the live process"
    assert lock.exists(), "a live process's lock must never be removed"


def test_no_lock_is_a_noop(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    result = _run(_blocks()[0], repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (repo / ".git" / "index.lock").exists()


def test_git_process_elsewhere_does_not_block_recovery(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    lock = repo / ".git" / "index.lock"
    lock.write_text("")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    proc = _fake_git_process(elsewhere)
    try:
        result = _run(_blocks()[0], repo)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not lock.exists(), (
        "only git processes working in THIS checkout count as live"
    )
