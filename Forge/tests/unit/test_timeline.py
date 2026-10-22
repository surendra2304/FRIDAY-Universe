"""
Unit tests for SecretRedactor, EventEmitter, and Task Timeline API Endpoint.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.events import EventEmitter, SecretRedactor
from app.memory.db import DatabaseManager
from app.memory.models import TaskEntity
from app.memory.state_store import StateStore


def test_secret_redactor_masks_keys_and_tokens():
    raw_payload = {
        "user_goal": "Deploy app to production",
        "api_key": "secret_live_key_9999",
        "nested": {
            "token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "anthropic_key": "sk-ant-api03-123456789012345678901234567890",
            "safe_field": "public_data",
        },
        "log_line": "Connecting with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token",
    }

    clean = SecretRedactor.redact(raw_payload)

    assert clean["api_key"] == "[REDACTED_SECRET]"
    assert clean["nested"]["token"] == "[REDACTED_SECRET]"
    assert clean["nested"]["anthropic_key"] == "[REDACTED_SECRET]"
    assert clean["nested"]["safe_field"] == "public_data"
    assert "eyJhbGciOi" not in clean["log_line"]
    assert "[REDACTED_TOKEN]" in clean["log_line"]


@pytest.mark.asyncio
async def test_event_emitter_structured_event_generation(temp_dir: Path):
    db_mgr = DatabaseManager(db_path=temp_dir / "test_events.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    task_id = str(uuid4())
    await store.create_task(
        TaskEntity(
            id=task_id,
            goal="Observability test task",
            workspace_path="/workspaces/test",
        )
    )

    emitter = EventEmitter(store=store)

    event = await emitter.emit(
        task_id=task_id,
        action="agent.step_executed",
        stage="Architecture",
        agent_id="architect",
        provider_model="claude-3-7-sonnet",
        inputs={"schema": "users", "api_key": "sensitive_key_val"},
        result={"status": "schema_generated"},
        duration_ms=250.5,
    )

    assert event.task_id == task_id
    assert event.stage == "Architecture"
    assert event.agent_id == "architect"
    assert event.inputs["api_key"] == "[REDACTED_SECRET]"
    assert event.inputs["schema"] == "users"

    # Verify event stored in state store audit trail
    audit_trail = await store.get_audit_trail(task_id)
    assert len(audit_trail) >= 1
    assert audit_trail[0].event_type == "agent.step_executed"


@pytest.mark.asyncio
async def test_task_timeline_api_endpoint(async_client: AsyncClient):
    # 1. Create a task via POST /tasks
    create_res = await async_client.post(
        "/tasks",
        json={"goal": "Timeline API Integration Test", "mode": "autonomous"},
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # 2. Query GET /tasks/{id}/timeline
    timeline_res = await async_client.get(f"/tasks/{task_id}/timeline")
    assert timeline_res.status_code == 200
    data = timeline_res.json()

    assert data["task_id"] == task_id
    assert data["total_events"] >= 2
    assert len(data["timeline"]) >= 2
    assert "Execution" in data["stages_covered"] or len(data["stages_covered"]) >= 1

    first_event = data["timeline"][0]
    assert "id" in first_event
    assert "action" in first_event
    assert "timestamp" in first_event
    assert "stage" in first_event
