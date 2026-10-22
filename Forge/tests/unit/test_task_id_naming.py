"""
Unit tests for human-readable Task ID and workspace directory naming format.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.memory.db import DatabaseManager
from app.memory.models import generate_task_id
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_generate_task_id_format():
    """Validates generate_task_id generates task<num><DDMMYYYY><HHMMSS>."""
    fixed_time = datetime(2026, 8, 26, 11, 35, 42, tzinfo=UTC)
    with patch("app.memory.models.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_time
        task_id = generate_task_id(1)
        assert task_id == "task0126082026113542"

        task_id_2 = generate_task_id(12)
        assert task_id_2 == "task1226082026113542"


@pytest.mark.asyncio
async def test_workspace_manager_named_directory(tmp_path: Path):
    """Validates WorkspaceManager maps task0126082026113542 to workspaces/task0126082026113542."""
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "task0126082026113542"
    ws_dir = wm.get_task_workspace_dir(task_id)
    assert ws_dir.name == "task0126082026113542"
    assert "task_task" not in str(ws_dir)

    paths = wm.create_workspace(task_id)
    assert paths.root.name == "task0126082026113542"
    assert paths.project.exists()


@pytest.mark.asyncio
async def test_orchestrator_intake_creates_formatted_task_id(tmp_path: Path):
    """Validates OrchestratorCore.intake_and_plan uses sequential formatted task ID."""
    db_file = tmp_path / "test_store.db"
    db_manager = DatabaseManager(db_path=db_file)
    await db_manager.init_db()

    store = StateStore(db_manager)
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)

    orchestrator = OrchestratorCore(store=store, wm=wm)

    task, _ = await orchestrator.intake_and_plan(
        goal="Build static portfolio site",
    )

    assert task.id.startswith("task01")
    assert len(task.id) >= 18
    assert "task01" in task.workspace_path
    assert not any(c in task.id for c in ["-", "_"])

    # Next task should increment to task02
    task2, _ = await orchestrator.intake_and_plan(
        goal="Build another tool",
    )
    assert task2.id.startswith("task02")
