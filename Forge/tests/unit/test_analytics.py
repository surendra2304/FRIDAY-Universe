"""
Unit and API integration tests for Analytics Subsystem.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.analytics.task_analytics import TaskAnalyticsService
from app.main import app
from app.memory.db import DatabaseManager
from app.memory.models import TaskEntity, TaskState
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_task_analytics_service(temp_dir: Path):
    db_path = temp_dir / "analytics_test.db"
    db_mgr = DatabaseManager(db_path=db_path)
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    t1 = TaskEntity(
        id="task_cli_01",
        goal="Build CLI tool",
        workspace_path=str(temp_dir / "t1"),
        state=TaskState.COMPLETED,
        budget_consumed=0.05,
    )
    t2 = TaskEntity(
        id="task_web_01",
        goal="Build website portfolio",
        workspace_path=str(temp_dir / "t2"),
        state=TaskState.FAILED,
        error_message="Fallback stub generation",
        budget_consumed=0.02,
    )
    await store.save_task(t1)
    await store.save_task(t2)

    svc = TaskAnalyticsService(db=db_mgr)
    summary = await svc.get_summary()
    assert summary.total_tasks == 2
    assert summary.completed_tasks == 1
    assert summary.failed_tasks == 1
    assert summary.success_rate_percentage == 50.0

    types = await svc.get_type_performance()
    assert len(types) >= 2

    failures = await svc.get_failure_analysis()
    assert failures.total_failures == 1
    assert failures.failure_types.get("fallback_stub", 0) == 1


@pytest.mark.asyncio
async def test_analytics_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_summary = await client.get("/api/analytics/summary")
        assert res_summary.status_code == 200
        assert "total_tasks" in res_summary.json()

        res_types = await client.get("/api/analytics/types")
        assert res_types.status_code == 200
        assert isinstance(res_types.json(), list)

        res_failures = await client.get("/api/analytics/failures")
        assert res_failures.status_code == 200
        assert "failure_types" in res_failures.json()
