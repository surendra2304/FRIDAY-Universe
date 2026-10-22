"""
Unit tests for Execution Engine Tools: FilesystemTool, TerminalTool, ProcessManagerTool, GitTool, and Permissions.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.filesystem import FilesystemTool
from app.execution.git_tool import GitTool
from app.execution.permissions import (
    PermissionManager,
    SandboxViolationError,
)
from app.execution.process_manager import ProcessManagerTool
from app.execution.terminal import TerminalTool


@pytest.fixture
def execution_context(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    pm = PermissionManager()
    return {
        "wm": wm,
        "pm": pm,
        "fs": FilesystemTool(wm=wm, pm=pm),
        "terminal": TerminalTool(wm=wm, pm=pm),
        "process": ProcessManagerTool(wm=wm, pm=pm),
        "git": GitTool(wm=wm, pm=pm),
    }


def test_filesystem_tool_crud(execution_context):
    fs: FilesystemTool = execution_context["fs"]
    task_id = "test_fs_01"

    # Create file
    rel_path = fs.create_file(task_id, "src/main.py", "print('hello')", role="developer")
    assert rel_path == "src/main.py"

    # Read file
    content = fs.read_file(task_id, "src/main.py", role="developer")
    assert content == "print('hello')"

    # Edit file
    fs.edit_file(task_id, "src/main.py", "print('hello')", "print('world')", role="developer")
    updated = fs.read_file(task_id, "src/main.py", role="developer")
    assert updated == "print('world')"

    # Search files
    matches = fs.search_files(task_id, pattern="*.py", role="developer")
    assert "src/main.py" in matches

    # Delete file
    deleted = fs.delete_file(task_id, "src/main.py", role="developer")
    assert deleted is True


def test_filesystem_sandbox_traversal_violation(execution_context):
    fs: FilesystemTool = execution_context["fs"]
    task_id = "test_fs_sec"

    with pytest.raises(SandboxViolationError):
        fs.create_file(task_id, "../../escaped.txt", "payload", role="developer")


@pytest.mark.asyncio
async def test_terminal_tool_execution(execution_context):
    terminal: TerminalTool = execution_context["terminal"]
    task_id = "test_term_01"

    res = await terminal.run_command(task_id, "python -c \"print('FORGE_EXEC')\"", role="developer")
    assert res.exit_code == 0
    assert "FORGE_EXEC" in res.stdout
    assert res.duration_ms >= 0


@pytest.mark.asyncio
async def test_process_manager_tool(execution_context):
    proc_tool: ProcessManagerTool = execution_context["process"]
    task_id = "test_proc_01"

    # Start a quick background process
    info = await proc_tool.start_process(
        task_id=task_id,
        process_id="server_1",
        command='python -c "import time; time.sleep(10)"',
        role="developer",
    )
    assert info.is_running is True
    assert info.pid is not None

    # Inspect
    inspected = proc_tool.inspect_process(task_id, "server_1", role="developer")
    assert inspected.is_running is True

    # Stop
    stopped = await proc_tool.stop_process(task_id, "server_1", role="developer")
    assert stopped is True


@pytest.mark.asyncio
async def test_git_tool_operations(execution_context):
    git: GitTool = execution_context["git"]
    fs: FilesystemTool = execution_context["fs"]
    task_id = "test_git_01"

    # Init
    init_res = await git.init_repo(task_id, role="developer")
    assert init_res is True

    # Add file and commit
    fs.create_file(task_id, "README.md", "# Project", role="developer")
    sha = await git.commit(task_id, "Initial commit", role="developer")
    assert len(sha) >= 7

    # Check status
    status = await git.status(task_id, role="developer")
    assert status.clean is True

    # Checkpoint and tag
    tag = await git.checkpoint(task_id, "v1.0", role="developer")
    assert "checkpoint" in tag
