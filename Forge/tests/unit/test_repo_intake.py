"""
Unit tests for Repository & Local Codebase Intake in WorkspaceManager and OrchestratorCore.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.models import TaskState
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_workspace_manager_local_path_intake(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    # 1. Create a dummy external repo/codebase
    source_repo = temp_dir / "external_repo"
    source_repo.mkdir()
    (source_repo / "main.py").write_text('print("Existing codebase main")', encoding="utf-8")
    (source_repo / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    sub_dir = source_repo / "src"
    sub_dir.mkdir()
    (sub_dir / "utils.py").write_text("def helper(): return 42", encoding="utf-8")

    # 2. Provision workspace with local_path
    task_id = str(uuid4())
    paths = wm.create_workspace(task_id=task_id, local_path=source_repo)

    assert paths.project.exists()
    assert (paths.project / "main.py").exists()
    assert (paths.project / "src" / "utils.py").exists()
    assert (paths.project / "requirements.txt").read_text(encoding="utf-8").strip() == "fastapi"


@pytest.mark.asyncio
async def test_orchestrator_plans_codebase_analyzer_when_existing_codebase(temp_dir: Path):
    db_mgr = DatabaseManager(db_path=temp_dir / "test_intake.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    source_repo = temp_dir / "my_project"
    source_repo.mkdir()
    (source_repo / "app.py").write_text('print("Legacy App")', encoding="utf-8")

    task, graph = await orchestrator.intake_and_plan(
        goal="Add caching layer to existing project",
        requirements=["Integrate Redis cache"],
        local_path=source_repo,
    )

    assert task.state == TaskState.READY
    node_agents = [n.assigned_agent for n in graph.nodes.values()]
    assert "codebase_analyzer" in node_agents
