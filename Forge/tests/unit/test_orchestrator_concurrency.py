"""
Regression test for a severe concurrency bug found via live adversarial load
testing against a real running FORGE server (not just the test suite).

Symptom (live-reproduced, 100% repro rate with 20-30 truly concurrent
`POST /api/tasks` requests): every concurrent submission's HTTP response
reported the *same* task id and the *same* goal back to the caller, even
though each caller submitted a distinct goal.

Root cause (two compounding bugs in `OrchestratorCore.intake_and_plan`):

1. Task-id allocation was a classic check-then-act race: `count_tasks()` was
   read, a candidate id built from the count + current-second timestamp, and
   checked with `get_task()` -- all without any lock. Concurrent callers
   within the same wall-clock second could all compute the identical
   candidate id and all pass the `get_task() is None` check before any of
   them had inserted.

2. When two callers *did* collide on the same id, the retry-on-IntegrityError
   path correctly gave the loser a new, unique `task.id` and a new DB row --
   but every subsequent step in the function (`record_event`, `planner.plan`,
   `lifecycle.transition`, and the object ultimately returned to the HTTP
   layer) kept using the *original*, pre-retry `task_id` local variable. The
   result: the DB had correct, isolated rows, but the orchestration logic and
   the HTTP response were both silently bound to whichever task happened to
   win the original id, orphaning every other real submission in PENDING
   forever.

Fix: a process-wide `asyncio.Lock` (`_TASK_ID_ALLOC_LOCK`) now serializes id
allocation + workspace provisioning + the initial insert, and the local
`task_id` is explicitly resynced to `task.id` after that critical section
(including when a retry occurs), so every downstream step and the final
returned task are always bound to whatever id was *actually* persisted.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.orchestrator import OrchestratorCore
from app.memory.db import DatabaseManager
from app.memory.models import TaskState
from app.memory.state_store import StateStore
from app.memory.task_lifecycle import TaskStateMachine


@pytest.mark.asyncio
async def test_concurrent_intake_never_collapses_to_one_task(tmp_path: Path):
    """N concurrent intake_and_plan() calls must produce N distinct, correctly
    attributed tasks -- never fewer, and never cross-contaminated goals."""
    db = DatabaseManager(db_path=tmp_path / "concurrency_test.db")
    store = StateStore(db)

    n = 25

    async def submit(i: int):
        # A fresh OrchestratorCore per call mirrors how FastAPI's
        # `get_orchestrator` dependency constructs one per request -- any fix
        # relying on an instance-level lock would not actually protect
        # concurrent HTTP requests.
        orch = OrchestratorCore(store=store)
        task, _graph = await orch.intake_and_plan(goal=f"Concurrency probe task number {i}")
        return i, task

    results = await asyncio.gather(*[submit(i) for i in range(1, n + 1)])

    ids = [task.id for _, task in results]
    assert len(set(ids)) == n, f"expected {n} unique task ids, got {len(set(ids))}: {ids}"

    for i, task in results:
        assert f"number {i}" in task.goal, (
            f"task returned for submission {i} has mismatched goal: {task.goal!r}"
        )
        # Every task must have actually been planned (READY), not left behind
        # in PENDING because the lifecycle transition silently operated on a
        # different task's stale id.
        assert task.state == TaskState.READY

    # Re-fetch every id from the store directly to rule out the response
    # object being correct while the persisted row is not.
    for i, task in results:
        persisted = await store.get_task(task.id)
        assert persisted is not None, f"task {task.id} (submission {i}) was never persisted"
        assert f"number {i}" in persisted.goal
        assert persisted.state == TaskState.READY


class _FakeRegistry:
    """A throwaway per-test stand-in for `app.agents.registry.agent_registry`.

    `OrchestratorCore` defaults `self.registry` to that module-level
    *singleton* when no `registry=` is passed in. An earlier version of
    these tests mutated `orch.registry.create_agent` directly, which -- since
    `orch.registry` *is* the shared global singleton, not a per-instance
    copy -- permanently replaced real agent creation for every other test in
    the same process for the rest of the session (confirmed live: it made
    unrelated orchestrator tests elsewhere in the suite fail with "Task ...
    not found", because their nodes were silently handed this test's
    pause/cancel-injecting fake agent instead of a real one). Passing a
    dedicated `registry=` object into each `OrchestratorCore(...)` here
    keeps the fake fully scoped to this test.
    """

    def __init__(self, agent_factory):
        self._agent_factory = agent_factory

    def create_agent(self, role_name: str):
        return self._agent_factory()


async def _make_task_with_multi_wave_dag(
    tmp_path: Path, name: str, agent_factory, shared_store: StateStore | None = None
):
    """Shared setup for the Finding 27 tests below: a real planned task whose
    DAG needs more than one execution wave (so `step_task()` takes the
    "more work remains" branch after the first wave, which is where the
    stale-state clobber lived), with an injected, test-local agent registry
    so the very first node's execution can deterministically trigger a
    concurrent pause/cancel exactly while that node is "mid-flight" --
    without racing real wall-clock concurrency, and without touching the
    shared global agent registry other tests depend on.
    """
    if shared_store is not None:
        store = shared_store
    else:
        db = DatabaseManager(db_path=tmp_path / f"{name}.db")
        store = StateStore(db)
    orch = OrchestratorCore(store=store, registry=_FakeRegistry(agent_factory))
    task, graph = await orch.intake_and_plan(
        goal="Build a small CLI todo app with add and list commands"
    )
    assert len(graph.nodes) > 1, "fixture goal must produce a multi-node, multi-wave DAG"
    return orch, store, task.id


@pytest.mark.asyncio
async def test_pause_mid_wave_is_not_silently_undone_by_step_task(tmp_path: Path):
    """Finding 27 (critical, live-reproduced): `step_task()` dispatches a
    wave of DAG nodes concurrently and, once they all finish, used to
    persist a *stale* `task.state` captured before the wave started (or
    compute a fresh COMPLETED/FAILED of its own) -- unconditionally
    overwriting the task's row. A node's `execute_step()` can take a real
    LLM call or file I/O, which is plenty of time for a user to call
    `POST /tasks/{id}/pause` from another request; that call persists
    BLOCKED immediately, but the instant the in-flight wave finished,
    step_task() silently flipped the task straight back to RUNNING -- the
    user's pause was discarded with no error, and the orchestrator kept
    executing a task they believed was paused.
    """
    db = DatabaseManager(db_path=tmp_path / "pause_race.db")
    store = StateStore(db)
    lifecycle = TaskStateMachine(store)

    class PausingAgent:
        async def execute_step(self, *, task_id, node_title, context, engine):
            # Simulate a concurrent pause() landing while this node's own
            # (real) async work -- an LLM call, a file write -- is in flight.
            await lifecycle.pause(task_id, reason="concurrent user pause mid-step")
            await asyncio.sleep(0)
            return {"stdout": "ok", "exit_code": 0}

    orch, _store, task_id = await _make_task_with_multi_wave_dag(
        tmp_path, "pause_race", lambda: PausingAgent(), shared_store=store
    )

    result_task, _executed = await orch.step_task(task_id)
    assert result_task.state == TaskState.BLOCKED, (
        f"pause() set BLOCKED but step_task()'s return value clobbered it back to "
        f"{result_task.state.value} once the in-flight wave finished"
    )

    persisted = await store.get_task(task_id)
    assert persisted.state == TaskState.BLOCKED, (
        f"pause() set BLOCKED but the persisted row was silently overwritten to "
        f"{persisted.state.value} after the wave completed"
    )


@pytest.mark.asyncio
async def test_cancel_mid_wave_is_not_silently_undone_by_step_task(tmp_path: Path):
    """Finding 27, cancel variant -- the more severe case: a task the user
    explicitly cancelled (e.g. to stop burning budget on a runaway task) was
    being silently resurrected to RUNNING once its in-flight wave finished,
    and `run_task()`'s own loop (which only stops on a terminal/BLOCKED
    state) would then happily keep executing further waves of a task the
    user believed was dead.
    """
    db = DatabaseManager(db_path=tmp_path / "cancel_race.db")
    store = StateStore(db)
    lifecycle = TaskStateMachine(store)

    class CancellingAgent:
        async def execute_step(self, *, task_id, node_title, context, engine):
            await lifecycle.cancel(task_id, reason="concurrent user cancel mid-step")
            await asyncio.sleep(0)
            return {"stdout": "ok", "exit_code": 0}

    orch, _store, task_id = await _make_task_with_multi_wave_dag(
        tmp_path, "cancel_race", lambda: CancellingAgent(), shared_store=store
    )

    result_task, _executed = await orch.step_task(task_id)
    assert result_task.state == TaskState.CANCELLED, (
        f"cancel() set CANCELLED but step_task() resurrected it to {result_task.state.value}"
    )

    persisted = await store.get_task(task_id)
    assert persisted.state == TaskState.CANCELLED, (
        f"cancel() set CANCELLED but the persisted row was resurrected to "
        f"{persisted.state.value} after the wave completed"
    )

    # And the orchestrator's own run loop must not keep driving a cancelled task.
    final_task = await orch.run_task(task_id, max_iterations=3)
    assert final_task.state == TaskState.CANCELLED, (
        "run_task() kept executing a task past a concurrent cancel; final state "
        f"was {final_task.state.value}"
    )


@pytest.mark.asyncio
async def test_cancel_mid_wave_survives_a_subsequent_node_failure(tmp_path: Path):
    """Finding 27, edge case: if the *same* node that triggered a concurrent
    cancel then goes on to raise an exception (a real possibility -- e.g. an
    LLM call that fails after the cancel request was already recorded),
    step_task()'s failure-handling path must not override the CANCELLED
    state with FAILED.
    """
    db = DatabaseManager(db_path=tmp_path / "cancel_then_fail_race.db")
    store = StateStore(db)
    lifecycle = TaskStateMachine(store)

    class CancelThenFailAgent:
        async def execute_step(self, *, task_id, node_title, context, engine):
            await lifecycle.cancel(task_id, reason="concurrent user cancel mid-step")
            await asyncio.sleep(0)
            raise RuntimeError("simulated node failure after the user already cancelled")

    orch, _store, task_id = await _make_task_with_multi_wave_dag(
        tmp_path, "cancel_then_fail_race", lambda: CancelThenFailAgent(), shared_store=store
    )

    result_task, _executed = await orch.step_task(task_id)
    assert result_task.state == TaskState.CANCELLED

    persisted = await store.get_task(task_id)
    assert persisted.state == TaskState.CANCELLED, (
        f"a node failure after a concurrent cancel overrode it with {persisted.state.value}"
    )
