"""TASK-VOI-008 — the voice worker must keep a warmed job executor.

Owner's question, 2026-11-15: the VOI-007 call's greeting took 25.6 s
and the report called it host-bound. The FRIDAY-Voice journal for that
job (AJ_5zsYdisRNeJ4) shows the avoidable part plainly: at 10:58:34.420
the SDK logged "no warmed process available for job, waiting for one
to be created", and the job runner finished initialising 1.78 s later —
because WorkerOptions carried num_idle_processes=0, the pool was
CONFIGURED to keep zero warmed executors. Every call paid executor
creation on its critical path, by configuration, not by hardware.

These tests pin the fix:

- the worker options keep exactly ONE executor warm
  (num_idle_processes=1) on the THREAD executor — a warmed PROCESS
  executor cannot fit the FRIDAY-Voice memory budget (cgroup peak
  ~242 MB of a 300 MB cap already; see the worker module's note);
- the options carry the VOI-008 prewarm hook;
- the prewarm hook returns immediately and never raises (executor
  initialisation has a 10 s SDK timeout; a slow or failing hook would
  remove executors from the pool);
- the warm thread is throttled, and its steps are defensive (a failed
  recall or synthesis only ever logs).
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from livekit.agents import JobExecutorType  # noqa: E402

from friday.voice import livekit_worker as worker  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_warm_state():
    worker._EXECUTOR_WARM_LAST[0] = 0.0
    yield
    worker._EXECUTOR_WARM_LAST[0] = 0.0


def test_worker_options_keep_one_executor_warm():
    opts = worker._worker_options()
    assert opts.num_idle_processes == 1
    assert opts.job_executor_type == JobExecutorType.THREAD
    assert opts.prewarm_fnc is worker._prewarm_job_executor


def test_prewarm_hook_is_immediate_and_never_raises(monkeypatch):
    ran = []
    monkeypatch.setattr(worker, "_executor_warm_steps", lambda: ran.append(1))
    started = time.time()
    worker._prewarm_job_executor(object())
    assert time.time() - started < 2.0
    # the warm work itself is delegated to the daemon thread; give it a
    # moment, then prove it ran exactly once
    deadline = time.time() + 5.0
    while not ran and time.time() < deadline:
        time.sleep(0.05)
    assert ran == [1]


def test_prewarm_hook_is_throttled(monkeypatch):
    ran = []
    monkeypatch.setattr(worker, "_executor_warm_steps", lambda: ran.append(1))
    worker._prewarm_job_executor(object())
    worker._prewarm_job_executor(object())
    worker._prewarm_job_executor(object())
    deadline = time.time() + 5.0
    while not ran and time.time() < deadline:
        time.sleep(0.05)
    time.sleep(0.3)
    assert ran == [1]


def test_warm_steps_survive_failures(monkeypatch):
    def _boom():
        raise RuntimeError("memora unreachable")

    def _boom_preload():
        raise RuntimeError("fixed-line wav unreadable")

    monkeypatch.setattr(worker, "_owner_memory_lines", _boom)
    # TASK-VOI-009: the warm thread's second step was an EdgeTTS
    # synthesis when VOI-008 landed; the greeting is a shipped WAV
    # since the Groq removal, so the step is now the fixed-line
    # preload. The contract is unchanged: a failed step only logs.
    monkeypatch.setattr(worker, "_preload_fixed_lines", _boom_preload)
    # must not raise even when every warm step fails
    worker._executor_warm_steps()
