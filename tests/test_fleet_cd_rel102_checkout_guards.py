"""TASK-REL-102 — Fleet CD checkout-guard tests (staged proof of the CD break).

Fleet CD (`.github/workflows/deploy-monorepo.yml`) has deployed nothing in
its last 30 runs: 25 runs skipped both deploy jobs (board-only merges) and
the 5 runs that actually triggered a deploy all failed in BOTH deploy jobs
at the single SSH step (runs 45728251043, 45728272752, 45737375597,
45737535632, 45740553832 — 2026-11-26 00:22-02:09 UTC). The workflow is
behaving correctly: each server trips a different SAFE CHECKOUT guard, and
the guards refuse to deploy rather than deploy over a bad checkout.

Proven first-hand (bridge, read-only) on 2026-11-26 ~10:30-10:50 IST:

(a) Server 1 trips the DIRTY-TREE guard. Checkout on `main` @ `b51ef05f`
    (origin/main `cc66b42d` at read time), but with tracked modifications:
    `M Futuris/futuris/integrations/memora_cloud_fallback.py`,
    `M Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py`,
    `D VyralX/tests/test_vyr057_pool.py`. The guard exits 1 with
    "Tracked collaborator changes present" on every S1 deploy.

(b) Server 2 trips the MAIN-BRANCH guard (TASK-OBS-005). Checkout parked
    on `muse10/task-voi-044-acceptance-run-27` @ `73b2ec2e` — the pushed tip
    of that branch on origin, so no unpushed work is stranded; clean
    tracked tree; origin/main current. The guard exits 1 naming the
    parked branch on every S2 deploy.

These tests extract the two exact guard blocks from the workflow file and
EXECUTE them under bash in scratch git repos reproducing the observed
server states, so what is tested is what deploys:

(a) the S2 state (parked branch, clean tree) -> branch guard fails naming
    the branch, dirty-tree guard passes (each server trips exactly one);
(b) the S1 state (main, the exact tracked M/M/D set) -> dirty-tree guard
    fails with the collaborator message, branch guard passes;
(c) a clean main checkout -> both guards pass (deploy proceeds).

Plus structural pins: exactly two dirty-tree guard blocks (one per deploy
job), byte-identical, each positioned after its job's branch guard and
before its ff-only merge.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"

BRANCH_BEGIN = "# BEGIN MAIN-BRANCH GUARD (TASK-OBS-005)"
BRANCH_END = "# END MAIN-BRANCH GUARD (TASK-OBS-005)"
DIRTY_BEGIN = "# BEGIN DIRTY-TREE GUARD (TASK-REL-102)"
DIRTY_END = "# END DIRTY-TREE GUARD (TASK-REL-102)"

PARKED = "muse10/task-voi-044-acceptance-run-27"

# The exact tracked paths observed dirty on Oracle Server 1.
S1_MODIFIED = [
    "Futuris/futuris/integrations/memora_cloud_fallback.py",
    "Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py",
]
S1_DELETED = "VyralX/tests/test_vyr057_pool.py"


def _blocks(begin: str, end: str) -> list[str]:
    """Extract the executable bash of each marked guard block."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    current: list[str] | None = None
    indent = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(begin):
            indent = line[: len(line) - len(line.lstrip())]
            current = [line]
            continue
        if current is not None:
            current.append(line)
            if stripped.startswith(end):
                blocks.append(
                    "\n".join(
                        ln[len(indent):] if ln.startswith(indent) else ln
                        for ln in current
                    )
                )
                current = None
    return blocks


def _branch_blocks() -> list[str]:
    return _blocks(BRANCH_BEGIN, BRANCH_END)


def _dirty_blocks() -> list[str]:
    return _blocks(DIRTY_BEGIN, DIRTY_END)


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
    for rel in S1_MODIFIED + [S1_DELETED]:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "one")
    _git(repo, "branch", "-M", "main")
    return repo


def _run(block: str, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", block],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


# -- structural pins -------------------------------------------------------


def test_two_identical_dirty_tree_guard_blocks() -> None:
    blocks = _dirty_blocks()
    assert len(blocks) == 2, "expected one dirty-tree guard block per deploy job"
    assert blocks[0] == blocks[1], "the two jobs' guard blocks must stay identical"


def test_dirty_guard_sits_between_branch_guard_and_ff_merge() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    branch_at = [i for i in range(len(text)) if text.startswith(BRANCH_BEGIN, i)]
    dirty_at = [i for i in range(len(text)) if text.startswith(DIRTY_BEGIN, i)]
    ff_at = [i for i in range(len(text)) if text.startswith("merge --ff-only", i)]
    assert len(branch_at) == 2 and len(dirty_at) == 2 and len(ff_at) == 2
    assert branch_at[0] < dirty_at[0] < ff_at[0] < branch_at[1] < dirty_at[1] < ff_at[1], (
        "each job must run branch guard, then dirty-tree guard, then ff-only merge"
    )


# -- behavioural proof: the observed server states -------------------------


def _s2_state(tmp_path: Path) -> Path:
    """Server 2 as observed: parked on the VOI-044 branch, clean tree."""
    repo = _scratch_repo(tmp_path)
    _git(repo, "checkout", "-b", PARKED)
    return repo


def _s1_state(tmp_path: Path) -> Path:
    """Server 1 as observed: on main with the exact tracked M/M/D set."""
    repo = _scratch_repo(tmp_path)
    for rel in S1_MODIFIED:
        (repo / rel).write_text("one\nlocally modified\n")
    (repo / S1_DELETED).unlink()
    return repo


def test_s2_parked_branch_fails_branch_guard_and_passes_dirty_guard(
    tmp_path: Path,
) -> None:
    repo = _s2_state(tmp_path)
    branch = _run(_branch_blocks()[0], repo)
    output = branch.stdout + branch.stderr
    assert branch.returncode == 1
    assert PARKED in output, "the failure must name the parked branch"
    assert "TASK-OBS-005" in output
    dirty = _run(_dirty_blocks()[0], repo)
    assert dirty.returncode == 0, (
        "S2's tree is clean — the dirty-tree guard is not its trip"
    )


def test_s1_dirty_tree_fails_dirty_guard_and_passes_branch_guard(
    tmp_path: Path,
) -> None:
    repo = _s1_state(tmp_path)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=no"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert " M Futuris/futuris/integrations/memora_cloud_fallback.py" in status
    assert (
        " M Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py"
        in status
    )
    assert " D VyralX/tests/test_vyr057_pool.py" in status
    branch = _run(_branch_blocks()[0], repo)
    assert branch.returncode == 0, (
        "S1 is on main — the branch guard is not its trip"
    )
    dirty = _run(_dirty_blocks()[0], repo)
    output = dirty.stdout + dirty.stderr
    assert dirty.returncode == 1
    assert "Tracked collaborator changes present" in output


def test_clean_main_checkout_passes_both_guards(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    assert _run(_branch_blocks()[0], repo).returncode == 0
    assert _run(_dirty_blocks()[0], repo).returncode == 0


def test_staged_only_change_also_trips_dirty_guard(tmp_path: Path) -> None:
    """The guard checks the index too (`git diff --cached`): a staged-only
    modification must trip it, or a worker could stage a change on the
    server and the deploy would sail through."""
    repo = _scratch_repo(tmp_path)
    (repo / S1_MODIFIED[0]).write_text("one\nlocally modified\n")
    _git(repo, "add", S1_MODIFIED[0])
    dirty = _run(_dirty_blocks()[0], repo)
    assert dirty.returncode == 1
    assert "Tracked collaborator changes present" in dirty.stdout + dirty.stderr
