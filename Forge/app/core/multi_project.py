"""
Multi-Project Concurrency, Priority Queuing, and Workspace Retention Manager for Project FORGE.
Supports priority task queuing, preemption, concurrency gating, and workspace lifecycle retention.
"""

import heapq
import shutil
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager

logger = get_logger("core.multi_project")

PRIORITY_WEIGHTS = {
    "urgent": 3,
    "high": 2,
    "normal": 1,
    "low": 0,
}


class QueuedTask(BaseModel):
    """Task item inside the priority scheduling queue."""

    task_id: str
    priority: str = "normal"
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    preemptible: bool = True

    @property
    def weight(self) -> int:
        return PRIORITY_WEIGHTS.get(self.priority.lower(), 1)

    def __lt__(self, other: "QueuedTask") -> bool:
        # Higher weight comes first; tie-break by earlier submission time
        if self.weight != other.weight:
            return self.weight > other.weight
        return self.submitted_at < other.submitted_at


class MultiProjectManager:
    """Manages concurrent project queues, priority preemption, and workspace retention policies."""

    def __init__(
        self,
        max_concurrent_tasks: int = 2,
        task_timeout_seconds: float = 1800.0,
        retention_days_completed: int = 7,
        retention_hours_failed: int = 24,
        wm: WorkspaceManager | None = None,
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout_seconds = task_timeout_seconds
        self.retention_days_completed = retention_days_completed
        self.retention_hours_failed = retention_hours_failed
        self.wm = wm or workspace_manager

        self.queue: list[QueuedTask] = []
        self.active_task_ids: set[str] = set()

    def enqueue_task(self, task_id: str, priority: str = "normal") -> QueuedTask:
        """Add task to priority queue."""
        item = QueuedTask(task_id=task_id, priority=priority)
        heapq.heappush(self.queue, item)
        logger.info(
            f"Task '{task_id}' enqueued with priority: {priority} (Queue depth: {len(self.queue)})"
        )
        return item

    def get_next_task(self) -> QueuedTask | None:
        """Pop the highest priority task ready for execution if concurrency limit allows."""
        if len(self.active_task_ids) >= self.max_concurrent_tasks:
            logger.debug(
                f"Concurrency limit reached ({len(self.active_task_ids)}/{self.max_concurrent_tasks}). Waiting for tasks to complete."
            )
            return None

        if not self.queue:
            return None

        next_task = heapq.heappop(self.queue)
        self.active_task_ids.add(next_task.task_id)
        return next_task

    def release_task(self, task_id: str):
        """Mark task as finished running and free up concurrency capacity."""
        if task_id in self.active_task_ids:
            self.active_task_ids.remove(task_id)
            logger.info(f"Task '{task_id}' released from active execution set.")

    def check_preemption(self, incoming_priority: str) -> bool:
        """Check if incoming task priority warrants preemption of running normal tasks."""
        incoming_weight = PRIORITY_WEIGHTS.get(incoming_priority.lower(), 1)
        return incoming_weight >= PRIORITY_WEIGHTS["urgent"]

    async def prune_workspaces(self) -> dict[str, int]:
        """
        Prune and archive old completed/failed workspaces according to retention policies.
        - Completed: Retained for retention_days_completed (default 7 days)
        - Failed: Retained for retention_hours_failed (default 24 hours)
        """
        settings = self.wm.settings
        ws_dir = settings.workspaces_dir
        if not ws_dir.exists():
            return {"archived": 0, "cleaned": 0}

        now = datetime.now(UTC)
        completed_cutoff = now - timedelta(days=self.retention_days_completed)
        failed_cutoff = now - timedelta(hours=self.retention_hours_failed)

        archived_count = 0
        cleaned_count = 0

        for task_folder in ws_dir.iterdir():
            if not task_folder.is_dir() or task_folder.name.startswith("."):
                continue

            try:
                mtime = datetime.fromtimestamp(task_folder.stat().st_mtime, tz=UTC)
                # Check for state markers
                state_dir = task_folder / "state"
                is_failed = (state_dir / "FALLBACK_STUB.json").exists()

                if is_failed and mtime <= failed_cutoff + timedelta(seconds=1):
                    # Clean up old failed workspace
                    shutil.rmtree(task_folder, ignore_errors=True)
                    cleaned_count += 1
                    logger.info(f"Pruned failed workspace sandbox: {task_folder.name}")
                elif mtime <= completed_cutoff + timedelta(seconds=1):
                    # Archive old completed workspace
                    archive_target = settings.artifacts_dir / f"archived_{task_folder.name}"
                    if not archive_target.exists():
                        shutil.move(str(task_folder), str(archive_target))
                        archived_count += 1
                        logger.info(
                            f"Archived workspace {task_folder.name} to {archive_target.name}"
                        )
            except Exception as e:
                logger.debug(f"Error checking workspace {task_folder.name} for pruning: {e}")

        return {"archived": archived_count, "cleaned": cleaned_count}


multi_project_manager = MultiProjectManager()
