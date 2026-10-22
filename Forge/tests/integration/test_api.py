"""
Integration tests for FORGE FastAPI REST endpoints.
Covers Tasks, Lifecycle Transitions, Runs/Audit Events, Artifacts, Agents, Capabilities, and Health.
"""

from datetime import datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_capabilities_endpoints(async_client: AsyncClient):
    # Test GET /health
    health_res = await async_client.get("/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] in ["healthy", "ok", "degraded"]
    assert health_data["database_connected"] is True
    # Evidence contract: a probe must state what it proves and when it observed it.
    assert health_data["evidence_class"] == "process_liveness"
    assert datetime.fromisoformat(health_data["observed_at"]).tzinfo is not None

    # Test GET /capabilities
    caps_res = await async_client.get("/capabilities")
    assert caps_res.status_code == 200
    caps_data = caps_res.json()
    assert "autonomous" in caps_data["supported_modes"]
    assert "PENDING" in caps_data["lifecycle_states"]
    assert caps_data["features"]["checkpointing_recovery"] is True


@pytest.mark.asyncio
async def test_agents_endpoint(async_client: AsyncClient):
    res = await async_client.get("/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 11
    agent_names = [a["name"] for a in agents]
    assert "planner" in agent_names
    assert "codebase_analyzer" in agent_names
    assert "architect" in agent_names
    assert "developer" in agent_names
    assert "tester" in agent_names
    assert "debugger" in agent_names
    assert "security_reviewer" in agent_names
    assert "release_engineer" in agent_names


@pytest.mark.asyncio
async def test_task_creation_and_inspection(async_client: AsyncClient):
    payload = {
        "goal": "Build an async task queue worker in Python",
        "requirements": ["Support Redis backend", "Exponential backoff retry"],
        "mode": "autonomous",
        "max_budget": 12.5,
    }

    # Create task via POST /tasks
    create_res = await async_client.post("/tasks", json=payload)
    assert create_res.status_code == 201
    task = create_res.json()

    task_id = task["id"]
    assert task["goal"] == payload["goal"]
    assert task["state"] in ["PENDING", "READY"]
    assert task["max_budget"] == 12.5
    assert "workspace_path" in task

    # Inspect task via GET /tasks/{id}
    get_res = await async_client.get(f"/tasks/{task_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == task_id
    assert "workspace_dirs" in detail
    assert "project" in detail["workspace_dirs"]
    assert "artifacts" in detail["workspace_dirs"]
    assert "logs" in detail["workspace_dirs"]
    assert "state" in detail["workspace_dirs"]
    assert "cache" in detail["workspace_dirs"]


@pytest.mark.asyncio
async def test_task_lifecycle_pause_resume_cancel(async_client: AsyncClient):
    # Create task
    create_res = await async_client.post(
        "/tasks",
        json={"goal": "Lifecycle Testing Goal", "mode": "autonomous"},
    )
    task_id = create_res.json()["id"]

    # Pause task (creates checkpoint & transitions to BLOCKED)
    pause_res = await async_client.post(
        f"/tasks/{task_id}/pause", json={"reason": "Audit checkpoint needed"}
    )
    assert pause_res.status_code == 200
    pause_data = pause_res.json()
    assert pause_data["current_state"] == "BLOCKED"
    assert pause_data["checkpoint_id"] is not None

    # Resume task (transitions to RUNNING)
    resume_res = await async_client.post(
        f"/tasks/{task_id}/resume", json={"reason": "Audit complete"}
    )
    assert resume_res.status_code == 200
    resume_data = resume_res.json()
    assert resume_data["current_state"] == "RUNNING"

    # Cancel task
    cancel_res = await async_client.post(
        f"/tasks/{task_id}/cancel", json={"reason": "User terminated task"}
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["current_state"] == "CANCELLED"


@pytest.mark.asyncio
async def test_runs_audit_trail(async_client: AsyncClient):
    create_res = await async_client.post(
        "/tasks",
        json={"goal": "Audit Trail Verification Task"},
    )
    task_id = create_res.json()["id"]

    await async_client.post(f"/tasks/{task_id}/pause", json={"reason": "Pause 1"})
    await async_client.post(f"/tasks/{task_id}/resume", json={"reason": "Resume 1"})

    # Check audit trail via GET /runs/{id}
    runs_res = await async_client.get(f"/runs/{task_id}")
    assert runs_res.status_code == 200
    trail = runs_res.json()
    assert trail["task_id"] == task_id
    assert trail["total_events"] >= 3
    event_types = [e["event_type"] for e in trail["events"]]
    assert "task.created" in event_types
    assert "task.paused" in event_types
    assert "task.resumed" in event_types


@pytest.mark.asyncio
async def test_artifact_endpoint(async_client: AsyncClient, test_db_manager):
    from app.memory.models import ArtifactRecord, TaskEntity
    from app.memory.state_store import StateStore

    store = StateStore(test_db_manager)
    task_id = str(uuid4())
    art_id = str(uuid4())

    task = TaskEntity(
        id=task_id,
        goal="Artifact Test Parent Task",
        workspace_path=f"/workspaces/task_{task_id}",
    )
    await store.create_task(task)

    art_record = ArtifactRecord(
        id=art_id,
        task_id=task_id,
        name="coverage_report.xml",
        path=f"/workspaces/task_{task_id}/artifacts/coverage.xml",
        file_type="application/xml",
        size_bytes=4096,
    )
    await store.record_artifact(art_record)

    res = await async_client.get(f"/artifacts/{art_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == art_id
    assert data["name"] == "coverage_report.xml"
    assert data["file_type"] == "application/xml"

    # Nonexistent artifact
    missing_res = await async_client.get(f"/artifacts/missing-{uuid4()}")
    assert missing_res.status_code == 404
