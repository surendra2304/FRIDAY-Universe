"""Execute the actual CD checkout block against disposable real Git repositories."""
import os
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/deploy-monorepo.yml"


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def checkout(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init")
    git(origin, "config", "user.email", "fixture@example.org")
    git(origin, "config", "user.name", "Fixture")
    (origin / "app.py").write_text("version=1\n")
    git(origin, "add", ".")
    git(origin, "commit", "-m", "initial")
    local = tmp_path / "local"
    git(tmp_path, "clone", str(origin), str(local))
    git(local, "config", "user.email", "fixture@example.org")
    git(local, "config", "user.name", "Fixture")
    old = git(local, "rev-parse", "HEAD")
    (origin / "app.py").write_text("version=2\n")
    git(origin, "commit", "-am", "update")
    target = git(origin, "rev-parse", "HEAD")
    return origin, local, old, target


def sync(local, target):
    text = WORKFLOW.read_text()
    blocks = text.split("# BEGIN SAFE CHECKOUT")[1:]
    assert len(blocks) == 2
    def block(part):
        lines = part.split("# END SAFE CHECKOUT")[0].splitlines()[1:]
        return "\n".join(line[12:] for line in lines)
    first, second = map(block, blocks)
    assert first == second
    program = first.replace("${{ github.sha }}", target)
    return subprocess.run(["bash", "-c", program], cwd=local, text=True,
                          capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def test_fast_forward_preserves_untracked_collaborator_work(checkout):
    _, local, _, target = checkout
    protected = local / "colleague-test.py"
    protected.write_bytes(b"important collaborator work\n")
    result = sync(local, target)
    assert result.returncode == 0, result.stderr
    assert git(local, "rev-parse", "HEAD") == target
    assert protected.read_bytes() == b"important collaborator work\n"


@pytest.mark.parametrize("staged", [False, True])
def test_dirty_tracked_checkout_is_refused_without_touching_it(checkout, staged):
    _, local, old, target = checkout
    (local / "app.py").write_text("collaborator edit\n")
    if staged:
        git(local, "add", "app.py")
    result = sync(local, target)
    assert result.returncode != 0
    assert git(local, "rev-parse", "HEAD") == old
    assert (local / "app.py").read_text() == "collaborator edit\n"


def test_divergent_branch_is_refused_without_rewriting_history(checkout):
    _, local, _, target = checkout
    (local / "local.py").write_text("local=True\n")
    git(local, "add", ".")
    git(local, "commit", "-m", "collaborator branch")
    previous = git(local, "rev-parse", "HEAD")
    assert sync(local, target).returncode != 0
    assert git(local, "rev-parse", "HEAD") == previous


def test_untracked_collision_aborts_instead_of_overwriting(checkout):
    origin, local, old, _ = checkout
    (origin / "protected.py").write_text("remote code\n")
    git(origin, "add", ".")
    git(origin, "commit", "-m", "new file")
    target = git(origin, "rev-parse", "HEAD")
    (local / "protected.py").write_text("untracked collaborator code\n")
    assert sync(local, target).returncode != 0
    assert git(local, "rev-parse", "HEAD") == old
    assert (local / "protected.py").read_text() == "untracked collaborator code\n"


def test_voice_worker_restart_is_explicit_in_cd():
    text = WORKFLOW.read_text()
    assert "sudo systemctl restart FRIDAY-Voice.service" in text
    assert "git reset --hard" not in text
