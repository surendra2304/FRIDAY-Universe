"""
Integration tests for Enhanced Task Management REST API endpoints (Consumer-Agnostic).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.memory.db import DatabaseManager


@pytest.mark.asyncio
async def test_task_lifecycle_api(isolated_db_manager: DatabaseManager):
    # `isolated_db_manager` (tests/conftest.py) redirects every module-level
    # `db_manager` binding -- including app.api.tasks's, which is what the
    # real routes below actually use -- to a temp-file-backed database. This
    # test used to call the *real* global `app.memory.db.db_manager`
    # directly against `data/forge.db`, so running it polluted (and could be
    # polluted by) whatever real tasks existed in a developer's local dev
    # database.
    await isolated_db_manager.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Submit task with optional metadata and tags
        payload = {
            "goal": "Build a responsive landing page",
            "requirements": ["Responsive layout", "Hero banner"],
            "max_budget": 5.0,
            "task_metadata": {
                "source": "client_app",
                "priority": "high",
                "tags": ["frontend", "landing-page"],
            },
        }
        res = await client.post("/api/tasks", json=payload)
        assert res.status_code == 201
        data = res.json()
        task_id = data["id"]
        assert data["goal"] == payload["goal"]
        assert data["metadata"]["source"] == "client_app"
        assert data["metadata"]["priority"] == "high"

        # 2. List tasks
        res_list = await client.get("/api/tasks")
        assert res_list.status_code == 200
        summaries = res_list.json()
        assert len(summaries) >= 1
        assert any(s["id"] == task_id for s in summaries)

        # 3. Get detailed task status and ETA
        res_get = await client.get(f"/api/tasks/{task_id}")
        assert res_get.status_code == 200
        detail = res_get.json()
        assert detail["id"] == task_id
        assert "estimated_remaining_seconds" in detail
        assert "workspace_dirs" in detail

        # 4. Deep Inspection
        res_inspect = await client.get(f"/api/tasks/{task_id}/inspect")
        assert res_inspect.status_code == 200
        inspect_data = res_inspect.json()
        assert inspect_data["task_id"] == task_id
        assert "files_created" in inspect_data
        assert "dependencies" in inspect_data
        assert "verification_summary" in inspect_data

        # 5. Execution logs
        res_logs = await client.get(f"/api/tasks/{task_id}/logs")
        assert res_logs.status_code == 200
        log_data = res_logs.json()
        assert log_data["task_id"] == task_id

        # 6. Artifacts Manifest
        res_arts = await client.get(f"/api/tasks/{task_id}/artifacts")
        assert res_arts.status_code == 200

        # 7. Cancel Task
        res_cancel = await client.post(
            f"/api/tasks/{task_id}/cancel", json={"reason": "Test cancel"}
        )
        assert res_cancel.status_code == 200
        cancel_data = res_cancel.json()
        assert cancel_data["current_state"] == "CANCELLED"

        # 8. Soft Archive (Delete)
        res_del = await client.delete(f"/api/tasks/{task_id}")
        assert res_del.status_code == 200
        del_data = res_del.json()
        assert del_data["archived"] is True
