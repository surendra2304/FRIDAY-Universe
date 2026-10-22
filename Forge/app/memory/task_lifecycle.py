"""
Task State Lifecycle & State Machine for Project FORGE.
Implements transition validation, checkpointing, pause, resume, cancel, and recovery.
"""

from typing import Any

from app.core.logging import get_logger
from app.memory.models import Checkpoint, TaskEntity, TaskState
from app.memory.state_store import StateStore

logger = get_logger("memory.lifecycle")


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle transition is attempted."""


class TaskStateMachine:
    """
    Validates and executes task state transitions with automated checkpointing and audit logging.
    """

    # Allowed state transition map
    TRANSITION_MATRIX: dict[TaskState, set[TaskState]] = {
        TaskState.PENDING: {
            TaskState.READY,
            TaskState.RUNNING,
            TaskState.BLOCKED,
            TaskState.CANCELLED,
        },
        TaskState.READY: {
            TaskState.RUNNING,
            TaskState.BLOCKED,
            TaskState.CANCELLED,
        },
        TaskState.RUNNING: {
            TaskState.VERIFYING,
            TaskState.COMPLETED,
            TaskState.BLOCKED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.READY,
        },
        TaskState.VERIFYING: {
            TaskState.COMPLETED,
            TaskState.RUNNING,
            TaskState.FAILED,
            TaskState.BLOCKED,
            TaskState.CANCELLED,
        },
        TaskState.BLOCKED: {
            TaskState.READY,
            TaskState.RUNNING,
            TaskState.CANCELLED,
        },
        TaskState.FAILED: {
            TaskState.READY,  # Retry mechanism
            TaskState.RUNNING,
            TaskState.CANCELLED,
        },
        TaskState.COMPLETED: set(),  # Terminal state
        TaskState.CANCELLED: set(),  # Terminal state
    }

    def __init__(self, store: StateStore):
        self.store = store

    @classmethod
    def can_transition(cls, current_state: TaskState, next_state: TaskState) -> bool:
        """Check if transition from current_state to next_state is valid."""
        if current_state == next_state:
            return True
        allowed = cls.TRANSITION_MATRIX.get(current_state, set())
        return next_state in allowed

    async def transition(
        self,
        task_id: str,
        to_state: TaskState,
        reason: str | None = None,
        progress_percentage: int | None = None,
        error_message: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> TaskEntity:
        """
        Validate and execute state transition, emitting an audit event.
        """
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        if not self.can_transition(task.state, to_state):
            msg = f"Cannot transition task '{task_id}' from {task.state.value} to {to_state.value}"
            logger.error(msg)
            raise InvalidStateTransitionError(msg)

        updated_task = await self.store.update_task_state(
            task_id=task_id,
            state=to_state,
            progress_percentage=progress_percentage,
            error_message=error_message
            or (reason if to_state in [TaskState.FAILED, TaskState.BLOCKED] else None),
        )

        # Record audit event
        payload = event_payload or {}
        payload.update(
            {
                "from_state": task.state.value,
                "to_state": to_state.value,
                "reason": reason,
            }
        )
        await self.store.record_event(
            task_id=task_id,
            event_type=f"task.state_changed.{to_state.value.lower()}",
            payload=payload,
        )

        logger.info(
            f"Task {task_id} transitioned: {task.state.value} -> {to_state.value} ({reason or 'no reason provided'})"
        )
        if not updated_task:
            raise RuntimeError(f"Failed to persist state transition for task '{task_id}'")
        return updated_task

    async def pause(
        self,
        task_id: str,
        reason: str = "User requested pause",
        snapshot_state: dict[str, Any] | None = None,
    ) -> tuple[TaskEntity, Checkpoint]:
        """
        Pause a task, create a checkpoint, and transition to BLOCKED state.
        """
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        if task.state in [TaskState.COMPLETED, TaskState.CANCELLED]:
            raise InvalidStateTransitionError(
                f"Cannot pause task in terminal state {task.state.value}"
            )

        # Save checkpoint before pausing
        checkpoints = await self.store.list_checkpoints(task_id)
        next_step = len(checkpoints) + 1

        checkpoint = Checkpoint(
            project_id=task_id,
            step_number=next_step,
            state_data=snapshot_state
            or {"state": task.state.value, "progress": task.progress_percentage},
            description=f"Checkpoint on pause: {reason}",
        )
        await self.store.save_checkpoint(checkpoint)

        # Transition task to BLOCKED
        updated_task = await self.transition(
            task_id=task_id,
            to_state=TaskState.BLOCKED,
            reason=reason,
            event_payload={"checkpoint_id": checkpoint.id, "step_number": next_step},
        )

        await self.store.record_event(
            task_id=task_id,
            event_type="task.paused",
            payload={"checkpoint_id": checkpoint.id, "reason": reason},
        )
        return updated_task, checkpoint

    async def resume(
        self,
        task_id: str,
        reason: str = "User requested resume",
    ) -> tuple[TaskEntity, Checkpoint | None]:
        """
        Resume a paused / blocked / failed task from its latest checkpoint.
        """
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        if task.state not in [
            TaskState.BLOCKED,
            TaskState.READY,
            TaskState.PENDING,
            TaskState.FAILED,
        ]:
            raise InvalidStateTransitionError(f"Cannot resume task in state {task.state.value}")

        latest_cp = await self.store.get_latest_checkpoint(task_id)

        # Transition back to RUNNING
        updated_task = await self.transition(
            task_id=task_id,
            to_state=TaskState.RUNNING,
            reason=reason,
            event_payload={"restored_checkpoint_id": latest_cp.id if latest_cp else None},
        )

        await self.store.record_event(
            task_id=task_id,
            event_type="task.resumed",
            payload={"checkpoint_id": latest_cp.id if latest_cp else None, "reason": reason},
        )
        return updated_task, latest_cp

    async def cancel(
        self,
        task_id: str,
        reason: str = "User requested cancellation",
    ) -> TaskEntity:
        """
        Cancel a task from any non-terminal state.
        """
        updated_task = await self.transition(
            task_id=task_id,
            to_state=TaskState.CANCELLED,
            reason=reason,
        )
        await self.store.record_event(
            task_id=task_id,
            event_type="task.cancelled",
            payload={"reason": reason},
        )
        return updated_task

    async def checkpoint(
        self,
        task_id: str,
        state_data: dict[str, Any],
        description: str | None = None,
    ) -> Checkpoint:
        """
        Create a checkpoint during task execution for recovery without pausing.
        """
        history = await self.store.list_checkpoints(task_id)
        next_step = len(history) + 1
        cp = Checkpoint(
            project_id=task_id,
            step_number=next_step,
            state_data=state_data,
            description=description or f"Checkpoint step {next_step}",
        )
        saved = await self.store.save_checkpoint(cp)
        await self.store.record_event(
            task_id=task_id,
            event_type="task.checkpointed",
            payload={"checkpoint_id": saved.id, "step_number": next_step},
        )
        return saved
