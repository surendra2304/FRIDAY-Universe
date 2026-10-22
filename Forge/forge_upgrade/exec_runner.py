from __future__ import annotations

import asyncio
import math
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ExecResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class SandboxedCommandRunner:
    """Run a shell command with a deadline, bounded output buffers, and process-tree cleanup.

    The runner is a resource-control boundary, not an authorization boundary: callers must
    apply CommandPolicy before invoking it with untrusted or model-generated commands.
    """

    _READ_CHUNK_BYTES = 64 * 1024
    _TERMINATE_GRACE_SECONDS = 0.2
    _CLEANUP_TIMEOUT_SECONDS = 5.0

    def __init__(self, cwd: str, max_output_bytes: int = 2_000_000):
        if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int):
            raise TypeError("max_output_bytes must be an integer")
        if max_output_bytes < 0:
            raise ValueError("max_output_bytes must be non-negative")
        self.cwd = str(Path(cwd).resolve())
        self.max_output_bytes = max_output_bytes

    async def run(
        self,
        command: str,
        *,
        timeout_seconds: float = 120,
        env: Mapping[str, str] | None = None,
    ) -> ExecResult:
        """Execute a command and retain at most max_output_bytes from each output stream.

        Both pipes are always drained, even after the capture limit is reached, so a noisy
        child cannot deadlock by filling an OS pipe. Cancellation is propagated only after
        the spawned process tree has been terminated and the direct child has been reaped.
        """
        if not isinstance(command, str):
            raise TypeError("command must be a string")
        if not command.strip():
            raise ValueError("command must not be empty")
        try:
            timeout_value = float(timeout_seconds)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("timeout_seconds must be a finite positive number") from exc
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_value)
            or timeout_value <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number")

        start = time.perf_counter()
        process_options: dict[str, int | bool] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **dict(env or {})},
            **process_options,
        )
        # PIPE is explicit above; these checks also keep static type checkers aware that
        # each reader receives a stream rather than None.
        assert proc.stdout is not None
        assert proc.stderr is not None

        stdout_task = asyncio.create_task(self._capture(proc.stdout))
        stderr_task = asyncio.create_task(self._capture(proc.stderr))
        wait_task = asyncio.create_task(proc.wait())
        tasks = (stdout_task, stderr_task, wait_task)
        timed_out = False

        try:
            _, pending = await asyncio.wait(
                tasks,
                timeout=timeout_value,
                return_when=asyncio.ALL_COMPLETED,
            )
            if pending:
                timed_out = True
                await self._terminate_process_tree(proc)
                await self._settle_tasks(tasks)
        except asyncio.CancelledError:
            # Shield cleanup from the cancellation that brought us here. A second
            # cancellation is allowed to interrupt the caller, but cleanup is bounded.
            cleanup_task = asyncio.create_task(self._terminate_process_tree(proc))
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                # Preserve cancellation while still making a best effort to reap the
                # shell process and stop stream readers.
                try:
                    await asyncio.wait_for(cleanup_task, timeout=self._CLEANUP_TIMEOUT_SECONDS)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            finally:
                await self._settle_tasks(tasks)
            raise

        stdout_b, stdout_truncated = self._task_output(stdout_task)
        stderr_b, stderr_truncated = self._task_output(stderr_task)
        exit_code = -9 if timed_out else (proc.returncode if proc.returncode is not None else 127)
        return ExecResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout_b.decode("utf-8", "replace"),
            stderr=stderr_b.decode("utf-8", "replace"),
            timed_out=timed_out,
            duration_ms=(time.perf_counter() - start) * 1000,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )

    async def _capture(self, stream: asyncio.StreamReader) -> tuple[bytes, bool]:
        """Drain a pipe but store no more than the configured number of bytes."""
        captured = bytearray()
        truncated = False
        while True:
            chunk = await stream.read(self._READ_CHUNK_BYTES)
            if not chunk:
                break
            remaining = self.max_output_bytes - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
            if len(chunk) > max(remaining, 0):
                truncated = True
        return bytes(captured), truncated

    @staticmethod
    def _task_output(task: asyncio.Task[tuple[bytes, bool]]) -> tuple[bytes, bool]:
        # A reader is only cancelled if the OS pipe cannot be closed after cleanup.
        # Keep the partial result predictable in that exceptional path.
        if task.cancelled():
            return b"", False
        return task.result()

    async def _settle_tasks(self, tasks: tuple[asyncio.Task, ...]) -> None:
        """Wait briefly for readers and waiters, then cancel any task that cannot settle."""
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self._CLEANUP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _terminate_process_tree(self, proc: asyncio.subprocess.Process) -> None:
        """Terminate descendants as well as the shell, then reap the direct child."""
        if os.name == "nt":
            killer: asyncio.subprocess.Process | None = None
            try:
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/F",
                    "/T",
                    "/PID",
                    str(proc.pid),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), timeout=self._CLEANUP_TIMEOUT_SECONDS)
            except (OSError, asyncio.TimeoutError):
                if killer is not None and killer.returncode is None:
                    killer.kill()
                    await killer.wait()
                if proc.returncode is None:
                    proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                if proc.returncode is None:
                    proc.terminate()

            await asyncio.sleep(self._TERMINATE_GRACE_SECONDS)

            # Send SIGKILL to the group even if the shell has already exited: a child
            # may still hold stdout/stderr open and keep the reader tasks alive.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                if proc.returncode is None:
                    proc.kill()

        if proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=self._CLEANUP_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
