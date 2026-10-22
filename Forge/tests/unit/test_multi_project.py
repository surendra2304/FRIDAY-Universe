"""
Unit tests for Multi-Project Priority Queue and Concurrency Governor.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.multi_project import MultiProjectManager
from app.core.workspace import WorkspaceManager


def test_priority_queue_ordering():
    mgr = MultiProjectManager(max_concurrent_tasks=2)

    mgr.enqueue_task("task_normal_1", priority="normal")
    mgr.enqueue_task("task_urgent_1", priority="urgent")
    mgr.enqueue_task("task_high_1", priority="high")
    mgr.enqueue_task("task_normal_2", priority="normal")

    t1 = mgr.get_next_task()
    assert t1 is not None
    assert t1.task_id == "task_urgent_1"
    assert t1.priority == "urgent"

    t2 = mgr.get_next_task()
    assert t2 is not None
    assert t2.task_id == "task_high_1"
    assert t2.priority == "high"

    # Concurrency limit reached (2/2 active)
    t3 = mgr.get_next_task()
    assert t3 is None

    # Release task
    mgr.release_task("task_urgent_1")
    t4 = mgr.get_next_task()
    assert t4 is not None
    assert t4.task_id == "task_normal_1"


def test_preemption_check():
    mgr = MultiProjectManager()
    assert mgr.check_preemption("urgent") is True
    assert mgr.check_preemption("high") is False
    assert mgr.check_preemption("normal") is False


@pytest.mark.asyncio
async def test_workspace_pruning(tmp_path: Path):
    ws_dir = tmp_path / "workspaces"
    art_dir = tmp_path / "artifacts"
    ws_dir.mkdir(parents=True)
    art_dir.mkdir(parents=True)

    settings = Settings()
    settings.workspaces_dir = ws_dir
    settings.artifacts_dir = art_dir

    wm = WorkspaceManager(settings=settings)
    mgr = MultiProjectManager(
        retention_days_completed=0,  # immediate for testing
        retention_hours_failed=0,
        wm=wm,
    )

    # Create dummy failed workspace
    failed_ws = ws_dir / "task_failed_ws"
    failed_ws.mkdir()
    (failed_ws / "state").mkdir()
    (failed_ws / "state" / "FALLBACK_STUB.json").write_text("{}", encoding="utf-8")

    # Prune
    stats = await mgr.prune_workspaces()
    assert stats["cleaned"] >= 1
    assert not failed_ws.exists()
