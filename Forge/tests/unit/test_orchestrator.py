"""
Unit tests for TaskAnalyzer and OrchestratorCore.
"""

from pathlib import Path

import pytest

from app.core.analyzer import TaskAnalyzer
from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_task_analyzer_heuristics():
    analyzer = TaskAnalyzer()
    res = await analyzer.analyze(
        goal="Create a high-performance REST API with FastAPI and PostgreSQL",
        requirements=["Include JWT auth", "Async DB sessions"],
    )

    assert res.primary_language == "Python"
    assert res.detected_domain == "Software Engineering"
    assert len(res.key_constraints) == 2


@pytest.mark.asyncio
async def test_orchestrator_intake_and_execution_loop(temp_dir: Path):
    db_mgr = DatabaseManager(db_path=temp_dir / "test_orch.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    orchestrator = OrchestratorCore(
        store=store,
        wm=wm,
        engine=engine,
    )

    # 1. Intake and Plan
    task, graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction", "Include unit tests"],
        mode=TaskMode.AUTONOMOUS,
    )

    assert task.state == TaskState.READY
    assert len(graph.nodes) >= 6
    from unittest.mock import AsyncMock, patch

    from app.integrations.ai_universe_client import AIUniverseResponse

    # 2. Run full autonomous loop
    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = AIUniverseResponse(
            answer="def add(a, b): return a + b\n",
            confidence=0.95,
            run_id="run_test_orch",
        )
        completed_task = await orchestrator.run_task(task.id, max_iterations=10)
        assert completed_task.state == TaskState.COMPLETED
        assert completed_task.progress_percentage == 100

    # Verify audit events recorded
    audit_trail = await store.get_audit_trail(task.id)
    event_types = [e.event_type for e in audit_trail]
    assert "task.created" in event_types
    assert "task.analyzed" in event_types
    assert "plan.created" in event_types
    assert "task.completed" in event_types
