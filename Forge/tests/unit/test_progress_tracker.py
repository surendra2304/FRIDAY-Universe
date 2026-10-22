"""
Unit tests for Progress Tracking and ETA Estimation Subsystem.
"""

import pytest

from app.core.progress_tracker import (
    PipelineStage,
    ProgressTracker,
)


@pytest.mark.asyncio
async def test_progress_tracker_stages_and_snapshot():
    task_id = "test_progress_task_01"
    tracker = ProgressTracker(task_id=task_id, project_type="website")

    snapshot = tracker.get_snapshot()
    assert snapshot.task_id == task_id
    assert snapshot.progress_percentage == 0
    assert snapshot.is_completed is False

    # Start Architecture stage
    await tracker.start_stage(PipelineStage.ARCHITECTURE)
    snapshot = tracker.get_snapshot()
    assert snapshot.current_stage == PipelineStage.ARCHITECTURE
    assert snapshot.stages["Architecture"].status == "running"

    # Complete Architecture stage
    await tracker.complete_stage(PipelineStage.ARCHITECTURE, {"manifest_files": ["index.html"]})
    snapshot = tracker.get_snapshot()
    assert snapshot.stages["Architecture"].status == "completed"
    assert snapshot.progress_percentage > 0
    assert snapshot.estimated_remaining_seconds > 0

    # Complete entire task
    await tracker.complete_task(success=True)
    snapshot = tracker.get_snapshot()
    assert snapshot.is_completed is True
    assert snapshot.progress_percentage == 100
    assert snapshot.estimated_remaining_seconds == 0.0


@pytest.mark.asyncio
async def test_progress_tracker_registry():
    task_id = "test_registry_02"
    t1 = ProgressTracker.get_or_create(task_id, project_type="cli")
    t2 = ProgressTracker.get_tracker(task_id)
    assert t1 is t2
