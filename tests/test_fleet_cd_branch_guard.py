"""TASK-OBS-005 — Fleet CD main-branch guard tests.

Fleet CD (`.github/workflows/deploy-monorepo.yml`) fast-forwards each
server's checkout into the pushed revision WITHOUT switching branches.
A checkout parked on a non-main branch can pass every other SAFE
CHECKOUT check (its HEAD can be an ancestor of the deploy revision)
while the fast-forward advances the WRONG branch and main stays
stranded — defect D9, three recurrences on 2026-11-16/17.

The fix is a marked guard block inside both deploy jobs' SAFE CHECKOUT
sections, asserting `git branch --show-current` == "main" BEFORE the
ff-only merge and failing loudly (naming the branch) otherwise. These
tests extract that exact block from the workflow file and EXECUTE it
under bash in scratch git repos, so what is tested is what deploys:

(a) a checkout parked on a non-main branch -> the guard exits 1 and
    its output names the parked branch;
(b) a checkout on main -> the guard exits 0 (deploy proceeds exactly
    as before);
(c) a detached HEAD -> the guard exits 1 (no branch to fast-forward).

Plus structural pins: exactly two guard blocks (one per deploy job),
byte-identical, and each positioned before its job's ff-only merge.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"

BEGIN = "# BEGIN MAIN-BRANCH GUARD (TASK-OBS-005)"
END = "# END MAIN-BRANCH GUARD (TASK-OBS-005)"
PARKED = "claude/parked-task-branch"


def _guard_blocks() -> list[str]:
    """Extract the executable bash of each marked guard block."""
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
    _git(repo, "config", "user.email", "guard@test")
    _git(repo, "config", "user.name", "Guard Test")
    (repo / "f.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "one")
    return repo


def _run_guard(block: str, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", block],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


# -- structural pins -------------------------------------------------------


def test_two_identical_guard_blocks() -> None:
    blocks = _guard_blocks()
    assert len(blocks) == 2, "expected one guard block per deploy job"
    assert blocks[0] == blocks[1], "the two jobs' guard blocks must stay identical"


def test_guard_precedes_each_ff_only_merge() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    guard_at = [i for i in range(len(text)) if text.startswith(BEGIN, i)]
    ff_at = [i for i in range(len(text)) if text.startswith("merge --ff-only", i)]
    assert len(guard_at) == 2 and len(ff_at) == 2
    assert guard_at[0] < ff_at[0] < guard_at[1] < ff_at[1], (
        "each job's branch guard must run before its ff-only merge"
    )


# -- health-gate second-chance sweep (the PR #868 false-FAILURE) ------------


def _job_scripts() -> list[str]:
    """Extract each deploy job's inline `script: |` block, dedented."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    scripts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip().endswith("script: |"):
            indent = len(line) - len(line.lstrip())
            body: list[str] = []
            i += 1
            while i < len(lines):
                body_line = lines[i]
                if body_line.strip():
                    if len(body_line) - len(body_line.lstrip()) <= indent:
                        break
                    body.append(body_line)
                else:
                    body.append("")
                i += 1
            nonblank = [b for b in body if b.strip()]
            dedent = min(len(b) - len(b.lstrip()) for b in nonblank)
            scripts.append(
                "\n".join(b[dedent:] if b.strip() else "" for b in body)
            )
            continue
        i += 1
    return scripts


def test_second_chance_sweep_in_both_jobs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("second-chance sweep after 60s settle (TASK-OBS-005)") == 2
    assert text.count("STILL_FAILED") >= 2


def test_both_job_scripts_are_valid_bash() -> None:
    import re

    scripts = _job_scripts()
    assert len(scripts) == 2, f"expected 2 deploy scripts, found {len(scripts)}"
    for script in scripts:
        assert BEGIN in script
        neutralised = re.sub(r"\$\{\{[^}]*\}\}", "0" * 40, script)
        result = subprocess.run(
            ["bash", "-n"],
            input=neutralised,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr


# -- behavioural proof -------------------------------------------------------


def test_parked_branch_fails_loudly_naming_the_branch(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    _git(repo, "checkout", "-b", PARKED)
    result = _run_guard(_guard_blocks()[0], repo)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert PARKED in output, "the failure must name the parked branch"
    assert "TASK-OBS-005" in output


def test_main_branch_proceeds(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    _git(repo, "branch", "-M", "main")
    result = _run_guard(_guard_blocks()[0], repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_detached_head_fails_loudly(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    _git(repo, "branch", "-M", "main")
    _git(repo, "checkout", "--detach", "HEAD")
    result = _run_guard(_guard_blocks()[0], repo)
    output = (result.stdout + result.stderr).lower()
    assert result.returncode == 1
    assert "detached" in output
