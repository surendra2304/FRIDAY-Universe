"""TASK-REL-011: delegate acceptance must schedule execution, and parked
tasks must expire instead of accumulating as forever-"active" zombies.

Live round-2 evidence (2026-11-14): Forge held 153 tasks of which 141 sat in
READY and only 10 had ever completed. The delegate path returned SUCCESS at
intake and never scheduled anything, so FRIDAY's receipt verification failed
("the peer returned no receipt") and callers were told planned work was done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api import delegate, tasks as tasks_api
from app.api.delegate import TaskEnvelopeModel
from app.memory.models import TaskState


@pytest.mark.asyncio
async def test_delegate_without_execute_now_schedules_and_reports_running(monkeypatch):
    scheduled: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        delegate, "_schedule_execution", lambda task_id, url=None: scheduled.append((task_id, url))
    )
    task = SimpleNamespace(id="task_new_1", goal="Build a palindrome checker", state=TaskState.READY)
    plan = SimpleNamespace(stages=["plan", "build", "test"])
    orchestrator = SimpleNamespace(intake_and_plan=AsyncMock(return_value=(task, plan)))

    envelope = TaskEnvelopeModel(
        task_id="env-010",
        source_agent="friday",
        action="build",
        payload={"goal": "Build a palindrome checker"},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    assert scheduled == [("task_new_1", None)]
    assert result.status == "RUNNING"  # not a fake SUCCESS for planned work
    assert result.result["forge_task_id"] == "task_new_1"
    assert result.result["state"] == "RUNNING"
    assert result.receipt is None  # receipts are issued on completion only


class _FakeStore:
    """Minimal StateStore surface used by TaskStateMachine + the reaper."""

    def __init__(self, tasks: list[SimpleNamespace]):
        self._tasks = {t.id: t for t in tasks}
        self.events: list[tuple[str, str, dict]] = []

    async def list_tasks(self, state=None, limit=50):
        return [t for t in self._tasks.values() if state is None or t.state == state][:limit]

    async def get_task(self, task_id):
        return self._tasks.get(task_id)

    async def update_task_state(self, task_id, state, progress_percentage=None, error_message=None):
        task = self._tasks[task_id]
        task.state = state
        return task

    async def record_event(self, task_id, event_type, payload=None):
        self.events.append((task_id, event_type, payload or {}))
        return SimpleNamespace(task_id=task_id, event_type=event_type)


def _task(task_id: str, state: TaskState, age_hours: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=task_id,
        state=state,
        created_at=datetime.now(UTC) - timedelta(hours=age_hours),
    )


@pytest.mark.asyncio
async def test_reconcile_expires_only_stale_unrunnered_tasks(monkeypatch):
    stale_ready = _task("t_stale_ready", TaskState.READY, 72)
    stale_pending = _task("t_stale_pending", TaskState.PENDING, 49)
    fresh_ready = _task("t_fresh_ready", TaskState.READY, 2)
    runnered = _task("t_runnered", TaskState.READY, 96)
    done = _task("t_done", TaskState.COMPLETED, 200)
    store = _FakeStore([stale_ready, stale_pending, fresh_ready, runnered, done])
    monkeypatch.setattr(tasks_api, "get_state_store", lambda: store)
    monkeypatch.setitem(tasks_api._running_tasks, "t_runnered", object())

    expired = await tasks_api.reconcile_stale_tasks(ttl_hours=24)

    assert expired == 2
    assert stale_ready.state == TaskState.CANCELLED
    assert stale_pending.state == TaskState.CANCELLED
    assert fresh_ready.state == TaskState.READY  # within TTL: untouched
    assert runnered.state == TaskState.READY  # has a live runner: untouched
    assert done.state == TaskState.COMPLETED
    # Lifecycle audit events were written for exactly the expired tasks.
    assert {e[0] for e in store.events} == {"t_stale_ready", "t_stale_pending"}
    assert all(e[1] == "task.state_changed.cancelled" for e in store.events)
    # Nothing was deleted.
    assert len(store._tasks) == 5


@pytest.mark.asyncio
async def test_reconcile_respects_ttl_override(monkeypatch):
    task = _task("t_mid", TaskState.READY, 10)
    store = _FakeStore([task])
    monkeypatch.setattr(tasks_api, "get_state_store", lambda: store)

    assert await tasks_api.reconcile_stale_tasks(ttl_hours=24) == 0
    assert task.state == TaskState.READY
    assert await tasks_api.reconcile_stale_tasks(ttl_hours=1) == 1
    assert task.state == TaskState.CANCELLED
