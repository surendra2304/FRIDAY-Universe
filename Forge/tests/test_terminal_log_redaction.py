"""Regression test for TASK-SEN-011 (SEN-005 finding F-1).

A command carrying a credential in a URL was written to the workspace
terminal.log verbatim, persisting a live GitHub token in plaintext in five
build workspaces. The command stored in the log (and echoed in the result)
must be masked at write time, while the command itself still executes.
"""
import asyncio
from pathlib import Path

from app.execution.terminal import TerminalTool

FAKE_TOKEN = "ghp_" + "Z9" * 18  # fake credential, classic PAT shape


class _Paths:
    def __init__(self, project):
        self.project = project


class _StubWorkspaceManager:
    def __init__(self, project):
        self._paths = _Paths(Path(project))
        self.logs = {}

    def get_workspace_paths(self, task_id):
        return self._paths

    def create_workspace(self, task_id):
        return self._paths

    def append_log(self, task_id, name, entry):
        self.logs.setdefault(name, []).append(entry)


class _StubPermissionManager:
    def check_permission(self, role, permission):
        return True


def test_terminal_log_masks_credentials_in_command(tmp_path):
    wm = _StubWorkspaceManager(tmp_path)
    tool = TerminalTool(wm=wm, pm=_StubPermissionManager())
    command = (
        "echo https://x-access-token:"
        f"{FAKE_TOKEN}@github.com/surendra2304/Forge.git"
    )
    result = asyncio.run(
        tool.run_command("task-sen011", command, timeout_seconds=30)
    )
    assert result.exit_code == 0
    entries = wm.logs.get("terminal.log", [])
    assert entries, "expected a terminal.log entry to be written"
    joined = "\n".join(entries)
    assert FAKE_TOKEN not in joined
    assert "[REDACTED]" in joined
    assert FAKE_TOKEN not in result.command
