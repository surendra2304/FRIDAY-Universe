"""
Fine-Grained Task Progress Tracker & ETA Estimator for Project FORGE.
Tracks stage timings across the 8-stage pipeline, computes dynamic ETA based on historical averages,
and publishes structured progress telemetry to event buses and WebSockets.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.events import EventEmitter
from app.core.logging import get_logger
from app.planning.tree import PipelineStage

logger = get_logger("core.progress_tracker")

# Default historical duration benchmarks in seconds per project type
DEFAULT_TYPE_DURATIONS: dict[str, float] = {
    "website": 25.0,
    "cli": 15.0,
    "api": 30.0,
    "script": 10.0,
    "fullstack": 45.0,
    "default": 20.0,
}

STAGE_WEIGHTS: dict[PipelineStage, int] = {
    PipelineStage.PROJECT: 5,
    PipelineStage.REQUIREMENTS: 10,
    PipelineStage.ARCHITECTURE: 15,
    PipelineStage.IMPLEMENTATION: 35,
    PipelineStage.INTEGRATION: 10,
    PipelineStage.VERIFICATION: 15,
    PipelineStage.SECURITY: 5,
    PipelineStage.RELEASE: 5,
}


class StageProgress(BaseModel):
    """Progress record for a single stage in the 8-stage pipeline."""

    stage: PipelineStage
    status: str = "pending"  # pending, running, completed, failed, skipped
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TaskProgressSnapshot(BaseModel):
    """Aggregated progress and ETA snapshot for a task."""

    task_id: str
    project_type: str = "default"
    current_stage: PipelineStage = PipelineStage.PROJECT
    progress_percentage: int = 0
    stages: dict[str, StageProgress] = Field(default_factory=dict)
    started_at: datetime
    elapsed_seconds: float = 0.0
    estimated_total_seconds: float = 20.0
    estimated_remaining_seconds: float = 20.0
    estimated_completion_at: datetime
    is_completed: bool = False
    is_failed: bool = False


class ProgressTracker:
    """Manages active task progress state and dynamic ETA estimation."""

    _instances: dict[str, "ProgressTracker"] = {}

    def __init__(
        self, task_id: str, project_type: str = "default", emitter: EventEmitter | None = None
    ):
        self.task_id = task_id
        self.project_type = project_type.lower()
        self.emitter = emitter
        self.started_at = datetime.now(UTC)
        self.current_stage = PipelineStage.PROJECT
        self.is_completed = False
        self.is_failed = False

        # Initialize all 8 canonical stages
        self.stages: dict[PipelineStage, StageProgress] = {
            stage: StageProgress(stage=stage) for stage in PipelineStage
        }

        base_duration = DEFAULT_TYPE_DURATIONS.get(
            self.project_type, DEFAULT_TYPE_DURATIONS["default"]
        )
        self.estimated_total_seconds = base_duration

        # Store in global registry
        ProgressTracker._instances[task_id] = self

    @classmethod
    def get_tracker(cls, task_id: str) -> Optional["ProgressTracker"]:
        """Retrieve progress tracker for task_id if active."""
        return cls._instances.get(task_id)

    @classmethod
    def get_or_create(
        cls, task_id: str, project_type: str = "default", emitter: EventEmitter | None = None
    ) -> "ProgressTracker":
        """Get existing or create new progress tracker."""
        if task_id in cls._instances:
            return cls._instances[task_id]
        return cls(task_id=task_id, project_type=project_type, emitter=emitter)

    async def start_stage(self, stage: PipelineStage, details: dict[str, Any] | None = None):
        """Mark stage as running and record start timestamp."""
        self.current_stage = stage
        sp = self.stages[stage]
        sp.status = "running"
        sp.started_at = datetime.now(UTC)
        if details:
            sp.details.update(details)

        logger.info(f"Task '{self.task_id}' started stage: {stage.value}")

        if self.emitter:
            await self.emitter.emit(
                task_id=self.task_id,
                event_type="stage.started",
                payload={"stage": stage.value, "progress": self.get_progress_percentage()},
            )

    async def complete_stage(self, stage: PipelineStage, details: dict[str, Any] | None = None):
        """Mark stage as completed, compute elapsed stage duration, and advance progress."""
        sp = self.stages[stage]
        sp.status = "completed"
        sp.completed_at = datetime.now(UTC)
        if sp.started_at:
            sp.duration_seconds = round((sp.completed_at - sp.started_at).total_seconds(), 2)
        if details:
            sp.details.update(details)

        logger.info(
            f"Task '{self.task_id}' completed stage: {stage.value} in {sp.duration_seconds or 0}s"
        )

        if self.emitter:
            await self.emitter.emit(
                task_id=self.task_id,
                event_type="stage.completed",
                payload={
                    "stage": stage.value,
                    "duration_seconds": sp.duration_seconds,
                    "progress": self.get_progress_percentage(),
                },
            )

    def get_progress_percentage(self) -> int:
        """Calculate weighted completion percentage across all completed stages."""
        if self.is_completed:
            return 100
        completed_weight = sum(
            STAGE_WEIGHTS[stage] for stage, sp in self.stages.items() if sp.status == "completed"
        )
        running_weight = sum(
            int(STAGE_WEIGHTS[stage] * 0.5)
            for stage, sp in self.stages.items()
            if sp.status == "running"
        )
        return min(95, completed_weight + running_weight)

    def get_snapshot(self) -> TaskProgressSnapshot:
        """Generate current progress snapshot with dynamic ETA estimation."""
        now = datetime.now(UTC)
        elapsed = (now - self.started_at).total_seconds()
        pct = self.get_progress_percentage()

        if pct >= 100 or self.is_completed:
            remaining = 0.0
            est_total = elapsed
        elif pct > 0:
            est_total = max(self.estimated_total_seconds, (elapsed / (pct / 100.0)))
            remaining = max(0.0, est_total - elapsed)
        else:
            remaining = self.estimated_total_seconds
            est_total = self.estimated_total_seconds

        est_completion = now + timedelta(seconds=remaining)

        return TaskProgressSnapshot(
            task_id=self.task_id,
            project_type=self.project_type,
            current_stage=self.current_stage,
            progress_percentage=pct,
            stages={k.value: v for k, v in self.stages.items()},
            started_at=self.started_at,
            elapsed_seconds=round(elapsed, 1),
            estimated_total_seconds=round(est_total, 1),
            estimated_remaining_seconds=round(remaining, 1),
            estimated_completion_at=est_completion,
            is_completed=self.is_completed,
            is_failed=self.is_failed,
        )

    async def complete_task(self, success: bool = True, error: str | None = None):
        """Finalize task tracking."""
        self.is_completed = success
        self.is_failed = not success
        if success:
            for sp in self.stages.values():
                if sp.status == "pending" or sp.status == "running":
                    sp.status = "completed"
                    if not sp.completed_at:
                        sp.completed_at = datetime.now(UTC)

        if self.emitter:
            event_name = "task.completed" if success else "task.failed"
            await self.emitter.emit(
                task_id=self.task_id,
                event_type=event_name,
                payload={
                    "progress": 100 if success else self.get_progress_percentage(),
                    "error": error,
                },
            )
