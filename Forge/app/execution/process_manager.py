"""
Process Manager Tool for Project FORGE Execution Engine.
Manages long-running background processes (dev servers, test monitors) inside task sandboxes.
"""

import asyncio
import os
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.permissions import (
    PermissionManager,
    ToolPermission,
    permission_manager,
)

logger = get_logger("execution.process_manager")


class ProcessInfo(BaseModel):
    process_id: str
    task_id: str
    command: str
    pid: int | None = None
    is_running: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stopped_at: datetime | None = None
    exit_code: int | None = None


class ProcessManagerTool:
    """Manages background development servers and persistent processes."""

    def __init__(
        self,
        wm: WorkspaceManager | None = None,
        pm: PermissionManager | None = None,
    ):
        self.wm = wm or workspace_manager
        self.pm = pm or permission_manager
        # In-memory lookup: (task_id, process_id) -> (asyncio.subprocess.Process, ProcessInfo)
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._info: dict[str, ProcessInfo] = {}

    def _key(self, task_id: str, process_id: str) -> str:
        return f"{task_id}:{process_id}"

    async def start_process(
        self,
        task_id: str,
        process_id: str,
        command: str,
        env_vars: dict[str, str] | None = None,
        role: str = "developer",
    ) -> ProcessInfo:
        """Spawn a background process inside the task workspace."""
        self.pm.check_permission(role, ToolPermission.PROCESS_SPAWN)

        key = self._key(task_id, process_id)
        if key in self._processes and self._processes[key].returncode is None:
            raise ValueError(f"Process '{process_id}' is already running for task '{task_id}'")

        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        cwd = paths.project.resolve()

        custom_env = os.environ.copy()
        if env_vars:
            custom_env.update(env_vars)

        log_file_path = paths.logs / f"process_{process_id}.log"
        log_file = open(log_file_path, "a", encoding="utf-8")

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=log_file,
            stderr=log_file,
            cwd=str(cwd),
            env=custom_env,
        )

        info = ProcessInfo(
            process_id=process_id,
            task_id=task_id,
            command=command,
            pid=proc.pid,
            is_running=True,
        )

        self._processes[key] = proc
        self._info[key] = info
        logger.info(
            f"Started background process '{process_id}' (pid={proc.pid}) in task '{task_id}'"
        )
        return info

    def inspect_process(
        self, task_id: str, process_id: str, role: str = "developer"
    ) -> ProcessInfo | None:
        """Inspect current state and PID of a background process."""
        self.pm.check_permission(role, ToolPermission.FS_READ)
        key = self._key(task_id, process_id)
        if key not in self._info:
            return None

        proc = self._processes.get(key)
        info = self._info[key]

        if proc:
            return_code = proc.returncode
            if return_code is not None:
                info.is_running = False
                info.exit_code = return_code
                if not info.stopped_at:
                    info.stopped_at = datetime.now(UTC)
            else:
                info.is_running = True

        return info

    async def stop_process(self, task_id: str, process_id: str, role: str = "developer") -> bool:
        """Stop a running background process."""
        self.pm.check_permission(role, ToolPermission.PROCESS_KILL)
        key = self._key(task_id, process_id)
        proc = self._processes.get(key)
        info = self._info.get(key)

        if not proc or proc.returncode is not None:
            return False

        try:
            if os.name == "nt":
                import subprocess

                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=5,
                )
            proc.terminate()
            await asyncio.sleep(0.1)
            if proc.returncode is None:
                proc.kill()
        except Exception:
            pass

        if info:
            info.is_running = False
            info.stopped_at = datetime.now(UTC)
            info.exit_code = proc.returncode

        logger.info(f"Stopped background process '{process_id}' in task '{task_id}'")
        return True

    async def restart_process(
        self, task_id: str, process_id: str, role: str = "developer"
    ) -> ProcessInfo:
        """Restart an existing background process."""
        self.pm.check_permission(role, ToolPermission.PROCESS_SPAWN)
        self.pm.check_permission(role, ToolPermission.PROCESS_KILL)

        key = self._key(task_id, process_id)
        info = self._info.get(key)
        if not info:
            raise ValueError(f"Process '{process_id}' not found")

        command = info.command
        await self.stop_process(task_id, process_id, role=role)
        return await self.start_process(task_id, process_id, command, role=role)

    def list_processes(self, task_id: str, role: str = "developer") -> list[ProcessInfo]:
        """List all background processes for a given task."""
        self.pm.check_permission(role, ToolPermission.FS_READ)
        results = []
        prefix = f"{task_id}:"
        for key in list(self._info.keys()):
            if key.startswith(prefix):
                proc_id = key[len(prefix) :]
                inspected = self.inspect_process(task_id, proc_id, role=role)
                if inspected:
                    results.append(inspected)
        return results

    async def stop_all_processes(self, timeout: float = 4.0) -> int:
        """Halt all active background sandbox processes cleanly within timeout seconds."""
        stopped = 0
        for key, proc in list(self._processes.items()):
            if proc.returncode is None:
                parts = key.split(":", 1)
                task_id = parts[0]
                proc_id = parts[1] if len(parts) > 1 else key
                try:
                    await asyncio.wait_for(
                        self.stop_process(task_id, proc_id, role="developer"),
                        timeout=timeout,
                    )
                    stopped += 1
                except Exception as e:
                    logger.warning(f"Error halting process {key}: {e}")
                    try:
                        proc.kill()
                    except Exception:
                        pass
        return stopped


process_manager_tool = ProcessManagerTool()
