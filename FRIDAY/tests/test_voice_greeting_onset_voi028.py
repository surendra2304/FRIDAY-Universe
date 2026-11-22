"""TASK-VOI-028: greeting-onset latency fix — proof-model reuse + build yields.

The greeting misses the 8 s bar even on a calm box (11.3 s / 17.0 s
in the VOI-024 A/B arms) and VOI-026's prime suspect is the session
build starving the greeting task's listening-gate timer: the build is
1.1-5.1 s of purely local, synchronous work (VOI-011) on the job
loop, and the 5 s gate cap is an ``asyncio.wait_for`` timeout that
fires only when the loop iterates — so the cap stretches with the
build and the line fires when the session starts, not at the cap.
Two fixes land in this task, and these tests pin them:

- The first session reuses the proof model (``artifacts={"model":
  _proof_model}``) instead of constructing a second identical
  ``RealtimeModel`` — the model was built twice per job.
- ``_make_session`` yields the loop (``await asyncio.sleep(0)``)
  between its synchronous construction steps, so the greeting task's
  gate timer can fire on wall-clock time during the build instead of
  being starved behind it.

The behavioral test proves the yield mechanism with
``_await_session_listening`` itself: a slow synchronous build with
no yields resolves a 0.5 s gate cap late (the VOI-026 mechanism),
while the same build with yields between its chunks lets the cap
fire on time. The production proof is still owed: the live re-probe
in the next calm window reads the VOI-026 decomposition line.
"""
import asyncio
import inspect
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


# ---------- entrypoint wiring (source shape) ----------


def test_proof_model_reused_for_first_session():
    """The first session is built from the proof model, not a second
    construction: the entrypoint passes ``artifacts={"model":
    _proof_model}`` to ``_make_session`` (the artifacts mechanism
    exists for this), and ``_make_session`` honours a supplied
    model instead of building one."""
    src = inspect.getsource(w.entrypoint)
    assert 'artifacts={"model": _proof_model}' in src
    # The reuse happens at the first-build call site, after the
    # VOI-026 build stamp — not in a rebuild path.
    assert src.index('greet_timing["build_start"]') < src.index(
        'artifacts={"model": _proof_model}'
    )
    # The mechanism: a supplied model short-circuits the build.
    body = src[src.index("async def _make_session"):]
    assert 'model = artifacts.get("model")' in body
    assert 'if model is None:' in body


def test_build_yields_to_loop_between_construction_steps():
    """``_make_session`` yields the job loop between its synchronous
    construction steps: one yield after the ``Agent()`` construction
    and one after the model build, before the ``AgentSession``
    construction — so the greeting task's pending callbacks (its
    participant poll, 0.3 s settle, gate timer) get loop time during
    the build instead of waiting for the whole build to finish."""
    src = inspect.getsource(w.entrypoint)
    start = src.index("async def _make_session")
    end = src.index("return session, agent", start)
    body = src[start:end]
    # Statement-position yields only: the docstring above mentions
    # ``await asyncio.sleep(0)`` in prose, so a bare substring scan
    # would count the docstring as a yield. Anchor to line starts.
    yields = [
        m.start()
        for m in re.finditer(r"(?m)^[ \t]*await asyncio\.sleep\(0\)", body)
    ]
    assert len(yields) >= 2, "expected at least two yields in _make_session"
    agent_i = body.index("agent = Agent(")
    model_i = body.index("_build_realtime_model(")
    session_i = body.index("_build_session(")
    assert agent_i < yields[0] < model_i, "first yield must follow Agent() and precede the model build"
    assert model_i < yields[1] < session_i, "second yield must follow the model build and precede AgentSession()"


# ---------- yield mechanism (behavioral) ----------


def _slow_chunks(n=6, chunk_s=0.3):
    """A slow synchronous build: n chunks of purely local work."""
    for _ in range(n):
        time.sleep(chunk_s)


async def _gate_during_build(build, cap_s=0.5):
    """Run ``build`` (an async callable) while the greeting gate
    waits with a ``cap_s`` cap; return (heard, gate_resolution_s)
    measured by the gate task itself — the build keeps running after
    the gate resolves, so the gate's own clock is what matters."""
    event = asyncio.Event()
    result = {}

    async def gate():
        t0 = time.perf_counter()
        heard = await w._await_session_listening(event, cap_s)
        result["heard"] = heard
        result["elapsed"] = time.perf_counter() - t0

    gate_task = asyncio.create_task(gate())
    await asyncio.sleep(0.05)  # let the gate task start waiting
    await build()
    await gate_task
    return result["heard"], result["elapsed"]


def test_gate_cap_fires_late_when_build_never_yields():
    """Control (the VOI-026 mechanism): a 1.8 s synchronous build
    with no yields resolves a 0.5 s gate cap at ~1.85 s, not 0.5 s —
    the cap cannot fire while the loop is held."""

    async def blocking_build():
        _slow_chunks()

    heard, elapsed = asyncio.run(_gate_during_build(blocking_build))
    assert heard is False  # the event was never set; the cap expired
    assert elapsed > 1.5, f"cap resolved at {elapsed:.2f}s, not late"
    assert elapsed < 3.0, f"cap resolved at {elapsed:.2f}s, implausibly late"


def test_yielded_build_lets_gate_cap_fire_on_time():
    """The fix's mechanism: the same 1.8 s build with a
    ``sleep(0)`` yield between its chunks lets the 0.5 s gate cap
    fire on wall-clock time while the build is still running — the
    greeting task gets loop time during the build. Measured ~1.25 s
    on this host (the timeout->cancel->resume chain takes two extra
    loop turns past the first due chunk), vs ~1.85 s with no yields:
    the bound sits between the yielded resolution and the unyielded
    control, and well inside the 1.8 s build itself."""

    async def yielding_build():
        for _ in range(6):
            time.sleep(0.3)
            await asyncio.sleep(0)

    heard, elapsed = asyncio.run(_gate_during_build(yielding_build))
    assert heard is False  # the event was never set; the cap expired
    assert elapsed < 1.5, f"cap resolved at {elapsed:.2f}s despite yields"
    assert elapsed > 0.3, f"cap resolved at {elapsed:.2f}s, implausibly early"
