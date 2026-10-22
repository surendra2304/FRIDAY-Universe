"""
Unit tests for Synthesis and Pipeline REST/SSE Endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.bus import get_event_bus
from app.pipeline.events import PipelineEvent, PipelineEventType


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_refactor_analyze(client: TestClient) -> None:
    code = """def calc(val, memo=[]):
    memo.append(val)
    return len(memo)
"""
    resp = client.post(
        "/api/synthesis/refactor/analyze",
        json={"source_code": code, "file_path": "calc.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issues_count"] >= 1
    assert "calc" in data["function_metrics"]


def test_api_refactor_transform(client: TestClient) -> None:
    code = """def calc(val, memo=[]):
    memo.append(val)
    return len(memo)"""
    resp = client.post(
        "/api/synthesis/refactor/transform",
        json={"source_code": code, "file_path": "calc.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["changes_count"] >= 1
    assert "memo=None" in data["refactored_code"]
    assert "diff" in data


def test_api_compiler_task_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/synthesis/compilers/compile",
        json={"task_id": "nonexistent_task_9999"},
    )
    assert resp.status_code == 404


def test_api_self_repair_task_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/synthesis/selfrepair/repair",
        json={"task_id": "nonexistent_task_9999"},
    )
    assert resp.status_code == 404


def test_api_pipeline_events_history(client: TestClient) -> None:
    task_id = "test_event_task_42"
    bus = get_event_bus()

    # Pre-populate event
    import asyncio
    ev = PipelineEvent(
        task_id=task_id,
        event_type=PipelineEventType.TASK_STARTED,
        payload={"goal": "Synthesize microservice"},
    )
    asyncio.run(bus.publish(ev))

    resp = client.get(f"/api/pipeline/history/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["count"] >= 1
    assert data["events"][0]["event_type"] == "task.started"


def test_api_pipeline_events_stream_connect(client: TestClient) -> None:
    # Test initial connection event
    with client.stream("GET", "/api/pipeline/stream/mock_task_123?timeout_seconds=0.1") as response:
        assert response.status_code == 200
        first_chunk = next(response.iter_lines())
        assert "event: ping" in first_chunk or "data:" in first_chunk
