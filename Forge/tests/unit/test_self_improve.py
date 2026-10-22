"""
Unit and API integration tests for Self-Improvement Engine.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.improvement.models import ProposalStatus
from app.improvement.self_improve import SelfImprovementEngine
from app.main import app
from app.memory.db import DatabaseManager
from app.memory.models import TaskEntity, TaskState
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_self_improvement_engine_clustering(temp_dir: Path):
    db_path = temp_dir / "improve_test.db"
    db_mgr = DatabaseManager(db_path=db_path)
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    # Insert failures
    t1 = TaskEntity(
        id="task_fail_dep",
        goal="FastAPI app",
        workspace_path="w1",
        state=TaskState.FAILED,
        error_message="ModuleNotFoundError: No module named 'jwt'",
    )
    t2 = TaskEntity(
        id="task_fail_syntax",
        goal="CLI tool",
        workspace_path="w2",
        state=TaskState.FAILED,
        error_message="SyntaxError: invalid syntax in main.py line 4",
    )
    await store.save_task(t1)
    await store.save_task(t2)

    engine = SelfImprovementEngine(db=db_mgr)
    report = await engine.generate_weekly_report(days=7)

    assert report.total_tasks_analyzed >= 2
    assert report.total_failures_identified >= 2
    assert "missing_dependencies" in report.failure_clusters
    assert "syntax_errors" in report.failure_clusters
    assert len(report.proposals) >= 2

    # Verify safety: proposal is PROPOSED, not yet APPLIED
    first_prop = report.proposals[0]
    assert first_prop.status == ProposalStatus.PROPOSED

    # Apply proposal with explicit approval
    applied = engine.apply_proposal(first_prop.id)
    assert applied is not None
    assert applied.status == ProposalStatus.APPLIED
    assert applied.applied_at is not None


@pytest.mark.asyncio
async def test_improvement_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/improvement/report")
        assert res.status_code == 200
        data = res.json()
        assert "failure_clusters" in data
        assert "proposals" in data
