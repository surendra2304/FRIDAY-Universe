"""
Terminal Tool for Project FORGE Execution Engine.
Executes sandboxed shell commands with timeout enforcement, output streaming, and exit code capture.
"""

import asyncio
import os
import time
from typing import Any

from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.permissions import (
    PermissionManager,
    SandboxViolationError,
    ToolPermission,
    permission_manager,
)

# Host environment variables a sandboxed build command is allowed to see.
# Everything else is withheld, so a new secret added to the host cannot leak
# into generated code by default.
SAFE_HOST_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "USER",
        "LOGNAME",
        "SHELL",
        "TERM",
        "TZ",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
        "VIRTUAL_ENV",
        "PIP_INDEX_URL",
        "PIP_NO_INPUT",
        "PIP_DISABLE_PIP_VERSION_CHECK",
        "NODE_ENV",
        "NODE_PATH",
        "NPM_CONFIG_REGISTRY",
        "GOPATH",
        "GOROOT",
        "GOFLAGS",
        "CARGO_HOME",
        "RUSTUP_HOME",
        "JAVA_HOME",
        "MAVEN_HOME",
        "GRADLE_HOME",
        "CI",
        "FORGE_TASK_ID",
        "FORGE_ROLE",
        "SYSTEMROOT",
        "SystemRoot",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "COMMONPROGRAMFILES",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "ALLUSERSPROFILE",
    }
)


logger = get_logger("execution.terminal")


def kill_process_tree(pid: int, timeout_sec: float = 3.0) -> bool:
    """
    Recursively terminate a process tree on Windows or POSIX.
    Combines OS process-group signaling with psutil descendant traversal
    to guarantee zero orphaned child processes or dev servers.
    """
    import subprocess

    import psutil

    killed = False
    # 1. Platform-native process group kill
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=timeout_sec,
            )
            killed = True
        else:
            import signal

            killpg_fn = getattr(os, "killpg", None)
            getpgid_fn = getattr(os, "getpgid", None)
            sigkill_val = getattr(signal, "SIGKILL", None)
            if killpg_fn and getpgid_fn and sigkill_val:
                try:
                    killpg_fn(getpgid_fn(pid), sigkill_val)
                    killed = True
                except Exception:
                    pass
    except Exception:
        pass

    # 2. psutil recursive cleanup for all descendant processes
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        gone, alive = psutil.wait_procs(children, timeout=1.0)
        for child in alive:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        killed = True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    except Exception:
        pass

    return killed



class CommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    cwd: str


class TerminalTool:
    """Provides sandboxed command execution in the task's project directory."""

    def __init__(
        self,
        wm: WorkspaceManager | None = None,
        pm: PermissionManager | None = None,
    ):
        self.wm = wm or workspace_manager
        self.pm = pm or permission_manager
        self._active_processes: set[asyncio.subprocess.Process] = set()

    async def run_command(
        self,
        task_id: str,
        command: str,
        timeout_seconds: int = 60,
        env_vars: dict[str, str] | None = None,
        role: str = "developer",
        allow_network: bool = False,
        allow_git_push: bool = False,
    ) -> CommandResult:
        """
        Execute command inside the task's project directory with full sandboxing, command policy evaluation,
        controlled environment, process group termination, bounded output, and secret redaction.
        """
        import subprocess

        from forge_upgrade.command_policy import CommandPolicy, Decision
        from forge_upgrade.secret_redaction import redact

        self.pm.check_permission(role, ToolPermission.TERMINAL_EXEC)

        # 1. Centralized Command Risk Policy Check
        import re

        if "git push" in command.lower() and not allow_git_push:
            logger.warning(
                f"Git push command denied by policy for task {task_id}: Git push requires separate authorization ({command})"
            )
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr="Command denied by security policy: Git push requires separate authorization",
                duration_ms=0.0,
                timed_out=False,
                cwd="",
            )

        policy = CommandPolicy()
        decision = policy.evaluate(
            command, allow_network=allow_network, allow_git_push=allow_git_push
        )
        if decision.decision == Decision.DENY or (
            decision.decision == Decision.APPROVE
            and not (
                ("git push" in command.lower() and allow_git_push)
                or (allow_network and any(n in command.lower() for n in ["curl", "wget", "nc", "ssh", "scp", "ftp"]))
            )
        ):
            logger.warning(
                f"Command denied by policy for task {task_id}: {decision.reason} ({command})"
            )
            return CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=f"Command denied by security policy: {decision.reason}",
                duration_ms=0.0,
                timed_out=False,
                cwd="",
            )

        # Prohibit dangerous OS-level destruction or pipe-to-shell patterns
        dangerous_patterns = (
            r"\b(format|shutdown|reboot|mkfs)\b",
            r"(^|[\s;&|])sudo(\s|$)",
            r"(^|[\s;&|])chmod\s+777(\s|$)",
            r"\|\s*(sh|bash|powershell|cmd)",
        )
        for dp in dangerous_patterns:
            if re.search(dp, command, re.IGNORECASE):
                logger.warning(f"Prohibited dangerous command pattern in task {task_id}: {command}")
                return CommandResult(
                    command=command,
                    exit_code=1,
                    stdout="",
                    stderr="Command denied: prohibited system-altering command or shell pipe injection",
                    duration_ms=0.0,
                    timed_out=False,
                    cwd="",
                )

        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        cwd = paths.project.resolve()

        # Enforce strict working-directory confinement
        try:
            cwd.relative_to(paths.project.resolve())
        except ValueError as exc:
            raise SandboxViolationError(f"Working-directory confinement failure: {cwd}") from exc

        # 2. Controlled Environment.
        # This used to be a denylist: every host variable was inherited except a
        # fixed set of nine names, so any credential not on that list (AWS access
        # key id, AZURE_CLIENT_SECRET, NPM_TOKEN, DATABASE_PASSWORD, a bespoke
        # MY_APP_TOKEN, ...) leaked straight into sandboxed commands. An
        # allowlist inverts the default: only what a build genuinely needs is
        # passed through, and everything else -- including future secrets -- is
        # dropped by default.
        controlled_env = {
            key: os.environ[key]
            for key in SAFE_HOST_ENV_ALLOWLIST
            if key in os.environ
        }
        controlled_env["PYTHONIOENCODING"] = "utf-8"
        controlled_env["PYTHONUTF8"] = "1"
        if env_vars:
            controlled_env.update(env_vars)

        start_time = time.perf_counter()
        timed_out = False
        stdout_text = ""
        stderr_text = ""
        exit_code = -1

        try:
            # Spawn the command in its OWN session/process group.
            #
            # This is the root-cause fix for the self-kill bug: without
            # start_new_session=True the child inherits the *caller's* process
            # group, so the timeout handler below (os.killpg(os.getpgid(child)))
            # signals the caller too -- which SIGKILLed FORGE's own uvicorn
            # worker and its own pytest runner. With the child in a fresh
            # session, killpg() only ever reaches the sandboxed command tree.
            spawn_kwargs: dict[str, Any] = {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "cwd": str(cwd),
                "env": controlled_env,
            }
            if os.name == "nt":
                spawn_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                spawn_kwargs["start_new_session"] = True

            process = await asyncio.create_subprocess_shell(command, **spawn_kwargs)
            self._active_processes.add(process)

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_seconds
                )
                exit_code = process.returncode if process.returncode is not None else 0
                stdout_text = stdout_bytes.decode("utf-8", errors="replace")
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            except (asyncio.TimeoutError, TimeoutError):
                timed_out = True
                # Clean up the *child's* process tree only. The child leads its
                # own group (see spawn_kwargs above), so this can never reach
                # the FORGE process that issued the command.
                killed = kill_process_tree(process.pid, timeout_sec=5.0)
                if not killed:
                    try:
                        process.kill()
                    except Exception:
                        pass

                # Reap the child so it does not linger as a zombie.
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except Exception:
                    pass

                # communicate() was cancelled, so its stdout/stderr pipe
                # transports are still open. Close them explicitly; otherwise
                # they are only released at interpreter shutdown, which surfaces
                # as "RuntimeError: Event loop is closed" from
                # BaseSubprocessTransport.__del__ in the logs.
                transport = getattr(process, "_transport", None)
                if transport is not None:
                    try:
                        transport.close()
                    except Exception:
                        pass

                stdout_bytes = b""
                stderr_bytes = b""
                exit_code = -9
                stderr_text = f"Command timed out after {timeout_seconds} seconds"
            finally:
                self._active_processes.discard(process)

        except Exception as e:
            logger.error(f"Error executing command '{command}' in task {task_id}: {e}")
            stderr_text = str(e)
            exit_code = 1

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 3. Secret Redaction across outputs before storing or returning
        stdout_text = redact(stdout_text)
        stderr_text = redact(stderr_text)

        # 4. Output limits: Truncate output exceeding 200,000 characters.
        # The suffix used to be appended AFTER the slice, so the returned string
        # was 200_000 + len(suffix) characters and the limit was never actually
        # honoured.
        MAX_OUTPUT_CHARS = 200_000
        truncation_notice = "\n... [TRUNCATED - Output exceeded 200KB limit]"
        if len(stdout_text) > MAX_OUTPUT_CHARS:
            stdout_text = stdout_text[: MAX_OUTPUT_CHARS - len(truncation_notice)] + truncation_notice
        if len(stderr_text) > MAX_OUTPUT_CHARS:
            stderr_text = stderr_text[: MAX_OUTPUT_CHARS - len(truncation_notice)] + truncation_notice

        # Append command execution record to workspace logs
        log_entry = (
            f"--- [CMD] {command} (exit={exit_code}, duration={duration_ms:.1f}ms) ---\n"
            f"STDOUT:\n{stdout_text}\n"
            f"STDERR:\n{stderr_text}\n"
        )
        self.wm.append_log(task_id, "terminal.log", log_entry)

        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_ms=round(duration_ms, 2),
            timed_out=timed_out,
            cwd=str(cwd),
        )

    async def install_dependencies(
        self,
        task_id: str,
        timeout_seconds: int = 120,
        role: str = "developer",
    ) -> CommandResult:
        """
        Inspect the project workspace and install project dependencies using the appropriate package manager:
        - Node.js / TypeScript: npm install (or yarn install)
        - Go: go mod tidy
        - Python: pip install -r requirements.txt
        """
        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        project_dir = paths.project

        if (project_dir / "package.json").exists():
            cmd = "yarn install" if (project_dir / "yarn.lock").exists() else "npm install"
            return await self.run_command(task_id, cmd, timeout_seconds=timeout_seconds, role=role)
        elif (project_dir / "go.mod").exists():
            return await self.run_command(
                task_id, "go mod tidy", timeout_seconds=timeout_seconds, role=role
            )
        elif (project_dir / "requirements.txt").exists():
            return await self.run_command(
                task_id,
                "pip install -r requirements.txt",
                timeout_seconds=timeout_seconds,
                role=role,
            )

        return CommandResult(
            command="install_dependencies",
            exit_code=0,
            stdout="No recognized manifest (package.json, go.mod, requirements.txt) found.",
            stderr="",
            duration_ms=0.1,
            timed_out=False,
            cwd=str(project_dir),
        )

    async def terminate_all_processes(self, timeout: float = 4.0) -> int:
        """Halt all active sandboxed terminal processes cleanly within timeout seconds."""
        stopped = 0
        for proc in list(self._active_processes):
            if proc.returncode is None:
                try:
                    kill_process_tree(proc.pid, timeout_sec=2.0)
                    stopped += 1
                except Exception as e:
                    logger.warning(f"Error terminating terminal process {proc.pid}: {e}")
                    try:
                        proc.kill()
                    except Exception:
                        pass
        return stopped

