"""TASK-API-001: Forge exposes POST /v1/task/execute and does not 404.

Shipped by TASK-FRG-002: the fleet dispatch bus posts code tasks to this
route, so the adapter in app/api/delegate.py (task_contract_router) must
serve it."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.delegate import get_orchestrator, get_state_store, task_contract_router


class _Store:
    async def list_tasks(self, limit: int = 5):
        return []


class _Orchestrator:
    pass


def test_forge_v1_task_execute_ping_is_not_404():
    app = FastAPI()
    app.include_router(task_contract_router)
    app.dependency_overrides[get_state_store] = lambda: _Store()
    app.dependency_overrides[get_orchestrator] = lambda: _Orchestrator()
    client = TestClient(app)

    response = client.post(
        "/v1/task/execute",
        json={
            "task_id": "task_api_001",
            "source_agent": "friday",
            "target_agent": "forge",
            "action": "ping",
            "payload": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task_api_001"
    assert body["target_agent"] == "forge"
    assert body["status"] == "SUCCESS"
    assert body["result"]["engine_status"] == "ONLINE"


def test_forge_v1_task_execute_accepts_fleet_wire_shape():
    """TASK-FRG-002: the dispatch bus's exact wire shape must validate.

    The bus posts task_id/agent/action/payload/priority (string)/
    timeout_sec/source_agent (universe_dispatch_bus._request_payload).
    The adapter must accept it: extra fields ignored, string priority kept.
    """
    app = FastAPI()
    app.include_router(task_contract_router)
    app.dependency_overrides[get_state_store] = lambda: _Store()
    app.dependency_overrides[get_orchestrator] = lambda: _Orchestrator()
    client = TestClient(app)

    response = client.post(
        "/v1/task/execute",
        json={
            "task_id": "task_frg_002_fleet",
            "agent": "forge",
            "action": "ping",
            "payload": {},
            "priority": "100",
            "timeout_sec": 30.0,
            "source_agent": "FRIDAY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task_frg_002_fleet"
    assert body["target_agent"] == "forge"
    assert body["status"] == "SUCCESS"
    assert body["result"]["engine_status"] == "ONLINE"
