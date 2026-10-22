"""
Regression tests for CRITICAL execution/security defects found in the 2026-10 audit.

CRITICAL-1  app/execution/terminal.py
    `TerminalTool.run_command` spawned its subprocess WITHOUT start_new_session,
    so the child inherited the *caller's* process group. The timeout handler then
    called os.killpg(os.getpgid(child_pid), SIGKILL) -- which signals the whole
    group, i.e. the FORGE process that issued the command. Symptom: any command
    that exceeded its timeout SIGKILLed FORGE itself (in production: the uvicorn
    worker; in CI: the pytest runner, which is what the "Linux OOM" comment in
    .github/workflows/ci.yml was actually observing).

CRITICAL-2  app/api/tasks.py::download_task_artifact
    The artifact filename was joined into the artifacts path with no containment
    check, so a traversal filename escaped the task sandbox and streamed an
    arbitrary host file to the caller.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.permissions import PermissionManager
from app.execution.terminal import TerminalTool

# ---------------------------------------------------------------------------
# CRITICAL-1 -- timeout cleanup must never signal the caller's process group
# ---------------------------------------------------------------------------


@pytest.fixture
def sandboxed_terminal(tmp_path: Path) -> TerminalTool:
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    return TerminalTool(wm=WorkspaceManager(settings=settings), pm=PermissionManager())


async def test_timeout_does_not_kill_the_calling_process(sandboxed_terminal: TerminalTool):
    """A command that outlives its timeout must be reaped without signalling FORGE.

    Before the fix this test process was SIGKILLed (exit 137) by its own
    TerminalTool call, because os.getpgid(child) returned the *test runner's*
    process group.
    """
    task_id = "crit_timeout_probe"
    result = await sandboxed_terminal.run_command(
        task_id,
        'python -c "import time; time.sleep(30)"',
        timeout_seconds=1,
        role="developer",
    )

    assert result.timed_out is True, "the command should have been reported as timed out"
    assert result.exit_code == -9
    assert "timed out" in result.stderr.lower()

    # If the caller's process group had been signalled we would never get here.
    assert os.getpid() > 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups not supported on Windows")
async def test_child_is_spawned_in_its_own_process_group(sandboxed_terminal: TerminalTool):
    """The spawned command must lead a process group distinct from the caller's."""
    task_id = "crit_pgid_probe"
    probe = (
        "import os, sys; "
        "sys.stdout.write(str(os.getpgid(0))); "
        "sys.stdout.flush()"
    )
    result = await sandboxed_terminal.run_command(
        task_id, f"python -c {probe!r}", timeout_seconds=30, role="developer"
    )

    assert result.exit_code == 0, result.stderr
    child_pgid = int(result.stdout.strip())
    assert child_pgid != os.getpgid(0), (
        "child shares the caller's process group -- killpg() on timeout would kill FORGE"
    )


async def test_timeout_reaps_the_child_and_leaves_no_zombie(sandboxed_terminal: TerminalTool):
    """After a timeout the child must be dead and reaped, not left running."""
    task_id = "crit_reap_probe"
    marker = Path("/tmp/forge_crit_reap_marker")
    if marker.exists():
        marker.unlink()

    result = await sandboxed_terminal.run_command(
        task_id,
        f'python -c "import time; time.sleep(30); open({str(marker)!r}, \'w\').close()"',
        timeout_seconds=1,
        role="developer",
    )
    assert result.timed_out is True

    # Give any (incorrectly) surviving child a chance to prove it is gone.
    import asyncio

    await asyncio.sleep(1.5)
    assert not marker.exists(), "timed-out child process was not killed"


async def test_successful_command_still_returns_output(sandboxed_terminal: TerminalTool):
    """Guard against over-correction: the session change must not break I/O."""
    result = await sandboxed_terminal.run_command(
        task_id="crit_ok_probe",
        command="python -c \"print('hello-from-sandbox')\"",
        timeout_seconds=30,
        role="developer",
    )
    assert result.exit_code == 0
    assert "hello-from-sandbox" in result.stdout
    assert result.timed_out is False


# ---------------------------------------------------------------------------
# CRITICAL-2 -- artifact download must stay inside the artifacts directory
# ---------------------------------------------------------------------------


def _make_workspace(tmp_path: Path, task_id: str) -> WorkspaceManager:
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    wm = WorkspaceManager(settings=settings)
    paths = wm.create_workspace(task_id)
    (paths.artifacts / "completion_report.json").write_text('{"ok": true}', encoding="utf-8")
    # A real host file outside the sandbox that a traversal would try to reach.
    (tmp_path / "outside_secret.txt").write_text("TOP-SECRET-HOST-FILE", encoding="utf-8")
    return wm


def _patch_workspace_manager(monkeypatch, settings: Settings) -> WorkspaceManager:
    """Point the API module's module-level manager at a tmp settings object."""
    wm = WorkspaceManager(settings=settings)
    monkeypatch.setattr("app.api.tasks.workspace_manager", wm)
    return wm


def test_artifact_traversal_is_blocked_direct_call(tmp_path: Path, monkeypatch):
    """Calling the handler with a traversal filename must 404, not stream a host file."""
    from fastapi import HTTPException

    from app.api.tasks import download_task_artifact

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    _patch_workspace_manager(monkeypatch, settings)

    task_id = "crit_artifact_task"
    paths = WorkspaceManager(settings=settings).create_workspace(task_id)
    (paths.artifacts / "completion_report.json").write_text('{"ok": true}', encoding="utf-8")
    (tmp_path / "outside_secret.txt").write_text("TOP-SECRET-HOST-FILE", encoding="utf-8")

    for payload in ("../outside_secret.txt", "../../outside_secret.txt", "../../../etc/passwd"):
        with pytest.raises(HTTPException) as exc:
            _run(download_task_artifact(task_id, payload))
        assert exc.value.status_code == 404, f"traversal payload {payload!r} was not rejected"


def test_artifact_traversal_is_blocked_over_http(tmp_path: Path, monkeypatch):
    """Same guarantee through the real ASGI stack."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.data_dir = tmp_path / "data"
    settings.database_path = tmp_path / "data" / "forge.db"
    settings.ensure_directories()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    _patch_workspace_manager(monkeypatch, settings)

    task_id = "crit_http_task"
    wm = WorkspaceManager(settings=settings)
    paths = wm.create_workspace(task_id)
    (paths.artifacts / "completion_report.json").write_text('{"ok": true}', encoding="utf-8")
    (tmp_path / "outside_secret.txt").write_text("TOP-SECRET-HOST-FILE", encoding="utf-8")

    app = create_app()
    with TestClient(app) as client:
        ok = client.get(f"/api/tasks/{task_id}/artifacts/completion_report.json")
        assert ok.status_code == 200, ok.text
        assert ok.json() == {"ok": True}

        for payload in (
            "..%2foutside_secret.txt",
            "..%2f..%2foutside_secret.txt",
            "%2e%2e%2foutside_secret.txt",
        ):
            resp = client.get(f"/api/tasks/{task_id}/artifacts/{payload}")
            assert resp.status_code == 404, (
                f"traversal payload {payload!r} leaked: {resp.text[:200]}"
            )
            assert "TOP-SECRET-HOST-FILE" not in resp.text


def test_artifact_download_still_serves_legitimate_files(tmp_path: Path, monkeypatch):
    from app.api.tasks import download_task_artifact

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    _patch_workspace_manager(monkeypatch, settings)

    task_id = "crit_ok_task"
    paths = WorkspaceManager(settings=settings).create_workspace(task_id)
    (paths.artifacts / "completion_report.json").write_text('{"ok": true}', encoding="utf-8")

    response = _run(download_task_artifact(task_id, "completion_report.json"))
    assert Path(response.path).name == "completion_report.json"


def _run(coro):
    # asyncio.run (not get_event_loop().run_until_complete) so each call gets a
    # fresh loop even after pytest-asyncio has closed the previous one.
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Proof the original failure mode is gone end-to-end
# ---------------------------------------------------------------------------


def test_full_prompt4_battery_no_longer_self_kills():
    """The 14-test acceptance battery must run as a single file.

    Before CRITICAL-1 this exact invocation was SIGKILLed (exit 137) at
    test_subprocess_timeout_and_process_cleanup.
    """
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_prompt4_forge.py", "-q",
         "--timeout=120", "--timeout-method=thread", "-p", "no:cacheprovider"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        "tests/test_prompt4_forge.py did not complete cleanly.\n"
        f"returncode={proc.returncode} (negative => killed by signal "
        f"{-proc.returncode if proc.returncode < 0 else 'n/a'})\n"
        f"stdout tail:\n{proc.stdout[-2000:]}\nstderr tail:\n{proc.stderr[-2000:]}"
    )
    # -q prints one dot per passed test; the battery has 14.
    assert proc.stdout.count(".") >= 14, f"unexpected test count:\n{proc.stdout}"
    assert "failed" not in proc.stdout and "error" not in proc.stdout.lower()
