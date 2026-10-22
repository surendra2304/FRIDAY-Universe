from __future__ import annotations

import asyncio
import json
import math
import os
import shlex
import sys
import time
from pathlib import Path

import pytest

from forge_upgrade.exec_runner import SandboxedCommandRunner


def python_command(source: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(source)}"


@pytest.mark.asyncio
async def test_runner_captures_both_streams_and_preserves_nonzero_exit(tmp_path: Path) -> None:
    runner = SandboxedCommandRunner(str(tmp_path))
    result = await runner.run(
        python_command(
            "import sys; print('normal output'); print('diagnostic', file=sys.stderr); sys.exit(7)"
        )
    )

    assert result.exit_code == 7
    assert result.stdout.strip() == "normal output"
    assert result.stderr.strip() == "diagnostic"
    assert not result.timed_out
    assert not result.stdout_truncated
    assert not result.stderr_truncated
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_runner_bounds_each_stream_but_continues_draining(tmp_path: Path) -> None:
    runner = SandboxedCommandRunner(str(tmp_path), max_output_bytes=128)
    result = await runner.run(
        python_command(
            "import sys; "
            "sys.stdout.write('x' * 500000); sys.stdout.flush(); "
            "sys.stderr.write('y' * 500000); sys.stderr.flush()"
        ),
        timeout_seconds=10,
    )

    assert result.exit_code == 0
    assert len(result.stdout.encode("utf-8")) == 128
    assert len(result.stderr.encode("utf-8")) == 128
    assert result.stdout == "x" * 128
    assert result.stderr == "y" * 128
    assert result.stdout_truncated
    assert result.stderr_truncated


@pytest.mark.asyncio
async def test_timeout_kills_process_and_preserves_available_output(tmp_path: Path) -> None:
    runner = SandboxedCommandRunner(str(tmp_path))
    result = await runner.run(
        python_command("import time; print('started', flush=True); time.sleep(30)"),
        timeout_seconds=0.5,
    )

    assert result.timed_out
    assert result.exit_code == -9
    assert "started" in result.stdout
    assert result.duration_ms < 5000


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="PID liveness check uses /proc on POSIX")
async def test_cancellation_terminates_child_process_tree_and_propagates(
    tmp_path: Path,
) -> None:
    pid_file = tmp_path / "child.pid"
    source = (
        "import os, pathlib, time; "
        f"pathlib.Path({json.dumps(str(pid_file))}).write_text(str(os.getpid())); "
        "print('started', flush=True); time.sleep(30)"
    )
    runner = SandboxedCommandRunner(str(tmp_path))
    task = asyncio.create_task(runner.run(python_command(source), timeout_seconds=30))

    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    assert pid_file.exists(), "child process did not start within the test deadline"
    child_pid = int(pid_file.read_text(encoding="utf-8"))

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Reaped processes should disappear; a short-lived zombie also counts as not running.
    deadline = time.monotonic() + 2
    while _process_is_running(child_pid) and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    assert not _process_is_running(child_pid), "cancelled child process was left running"


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    stat_path = Path(f"/proc/{pid}/stat")
    if stat_path.exists():
        try:
            state = stat_path.read_text(encoding="utf-8").split(")", 1)[1].strip().split()[0]
            return state != "Z"
        except (OSError, IndexError):
            return True
    return True


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [0, -1, math.inf, -math.inf, math.nan])
async def test_runner_rejects_non_positive_or_non_finite_timeout(
    tmp_path: Path, timeout: float
) -> None:
    runner = SandboxedCommandRunner(str(tmp_path))
    with pytest.raises(ValueError, match="finite positive"):
        await runner.run(python_command("print('not run')"), timeout_seconds=timeout)


@pytest.mark.asyncio
async def test_runner_rejects_blank_commands(tmp_path: Path) -> None:
    runner = SandboxedCommandRunner(str(tmp_path))
    with pytest.raises(ValueError, match="must not be empty"):
        await runner.run("   ")


def test_runner_rejects_invalid_output_limits(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        SandboxedCommandRunner(str(tmp_path), max_output_bytes=-1)
    with pytest.raises(TypeError, match="integer"):
        SandboxedCommandRunner(str(tmp_path), max_output_bytes=1.5)  # type: ignore[arg-type]
