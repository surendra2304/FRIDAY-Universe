"""
Unit tests for Task State Lifecycle State Machine & Checkpointing.
"""

from uuid import uuid4

import pytest

from app.memory.models import TaskEntity, TaskMode, TaskState
from app.memory.state_store import StateStore
from app.memory.task_lifecycle import InvalidStateTransitionError, TaskStateMachine


@pytest.mark.asyncio
async def test_lifecycle_valid_transitions(state_store: StateStore):
    lifecycle = TaskStateMachine(state_store)
    task_id = str(uuid4())

    task = TaskEntity(
        id=task_id,
        goal="Build JWT Authentication module",
        mode=TaskMode.AUTONOMOUS,
        workspace_path=f"/workspaces/task_{task_id}",
        state=TaskState.PENDING,
    )
    await state_store.create_task(task)

    # PENDING -> READY
    t1 = await lifecycle.transition(task_id, TaskState.READY)
    assert t1.state == TaskState.READY

    # READY -> RUNNING
    t2 = await lifecycle.transition(task_id, TaskState.RUNNING)
    assert t2.state == TaskState.RUNNING

    # RUNNING -> VERIFYING
    t3 = await lifecycle.transition(task_id, TaskState.VERIFYING)
    assert t3.state == TaskState.VERIFYING

    # VERIFYING -> COMPLETED
    t4 = await lifecycle.transition(task_id, TaskState.COMPLETED)
    assert t4.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_lifecycle_invalid_transitions(state_store: StateStore):
    lifecycle = TaskStateMachine(state_store)
    task_id = str(uuid4())

    task = TaskEntity(
        id=task_id,
        goal="Invalid Transition Check",
        mode=TaskMode.AUTONOMOUS,
        workspace_path=f"/workspaces/task_{task_id}",
        state=TaskState.PENDING,
    )
    await state_store.create_task(task)

    # PENDING -> COMPLETED directly should fail
    with pytest.raises(InvalidStateTransitionError, match="Cannot transition task"):
        await lifecycle.transition(task_id, TaskState.COMPLETED)

    # Move to COMPLETED properly
    await lifecycle.transition(task_id, TaskState.READY)
    await lifecycle.transition(task_id, TaskState.RUNNING)
    await lifecycle.transition(task_id, TaskState.VERIFYING)
    await lifecycle.transition(task_id, TaskState.COMPLETED)

    # Terminal state transition should fail
    with pytest.raises(InvalidStateTransitionError):
        await lifecycle.transition(task_id, TaskState.RUNNING)


@pytest.mark.asyncio
async def test_lifecycle_pause_resume_checkpoint(state_store: StateStore):
    lifecycle = TaskStateMachine(state_store)
    task_id = str(uuid4())

    task = TaskEntity(
        id=task_id,
        goal="Long Running Computation Task",
        workspace_path=f"/workspaces/task_{task_id}",
        state=TaskState.PENDING,
    )
    await state_store.create_task(task)
    await lifecycle.transition(task_id, TaskState.READY)
    await lifecycle.transition(task_id, TaskState.RUNNING)

    # Pause task
    paused_task, cp = await lifecycle.pause(
        task_id=task_id,
        reason="Budget threshold reached",
        snapshot_state={"completed_iterations": 42},
    )
    assert paused_task.state == TaskState.BLOCKED
    assert cp.step_number == 1
    assert cp.state_data["completed_iterations"] == 42

    # Resume task
    resumed_task, restored_cp = await lifecycle.resume(
        task_id=task_id, reason="User allocated budget"
    )
    assert resumed_task.state == TaskState.RUNNING
    assert restored_cp is not None
    assert restored_cp.id == cp.id

    # Cancel task
    cancelled_task = await lifecycle.cancel(task_id=task_id, reason="Goal obsolete")
    assert cancelled_task.state == TaskState.CANCELLED
