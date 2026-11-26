"""TASK-API-001: POST /v1/task/execute is served by the assembled Forge app.

TASK-FRG-002 shipped the route plus router-only contract tests, but those
mount task_contract_router on a bare FastAPI app -- they never proved the
route is reachable in the real app (Forge/app/main.py create_app), where
router registration, the production API-key middleware and the delegate
dependencies all apply. This file boots create_app() and posts the dispatch
bus's exact wire shape (universe_dispatch_bus._request_payload).
"""

from fastapi.testclient import TestClient

from app.api.delegate import get_orchestrator, get_state_store
from app.main import create_app


class _Store:
    async def list_tasks(self, limit: int = 5):
        return []


class _Orchestrator:
    pass


def _bus_payload(**overrides):
    payload = {
        "task_id": "task_api_001_mounted",
        "agent": "forge",
        "action": "ping",
        "payload": {},
        "priority": "100",
        "timeout_sec": 30.0,
        "source_agent": "FRIDAY",
    }
    payload.update(overrides)
    return payload


def test_mounted_app_serves_task_execute_on_bus_wire_shape():
    """The assembled app answers the bus's exact POST, with a receipt."""
    app = create_app()
    app.dependency_overrides[get_state_store] = lambda: _Store()
    app.dependency_overrides[get_orchestrator] = lambda: _Orchestrator()
    client = TestClient(app)

    # The mount itself: the route must be listed in the assembled OpenAPI.
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/v1/task/execute" in openapi.json()["paths"]
    assert "post" in openapi.json()["paths"]["/v1/task/execute"]

    response = client.post("/v1/task/execute", json=_bus_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task_api_001_mounted"
    assert body["target_agent"] == "forge"
    assert body["status"] == "SUCCESS"
    assert body["result"]["engine_status"] == "ONLINE"
    # FRIDAY's mesh certifies completion only from a receipt naming the
    # dispatched action, this agent as target, and non-empty evidence.
    receipt = body["receipt"]
    assert receipt["requested_action"] == "ping"
    assert receipt["target"] == "forge"
    assert receipt["verification_evidence"]["engine_status"] == "ONLINE"


class _PlannedTask:
    def __init__(self):
        self.id = "task_plan_only_1"
        self.goal = "Add a trivial hello function to a fresh Python module"


class _Plan:
    def __init__(self):
        self.nodes = {"analyse": 1, "synthesize": 2}


class _PlanningOrchestrator:
    async def intake_and_plan(self, **kwargs):
        return _PlannedTask(), _Plan()


def test_mounted_app_build_plan_only_through_delegate():
    """A build reaches delegate_task's synthesis branch via the mounted route.

    mode plan_only plans without executing anything, so this proves the
    build path is wired end to end (route -> delegate_task -> intake_and_plan)
    while executing no code. The orchestrator boundary is stubbed at the
    same seam FRG-002 used; the real OrchestratorCore cannot run in this
    environment because the suite's SQLite DatabaseManager(db_path=...)
    fixtures are broken on current main (DatabaseManager is Oracle-only
    now; CI deselects the tests that hit it -- pre-existing, out of scope).
    """
    app = create_app()
    app.dependency_overrides[get_state_store] = lambda: _Store()
    app.dependency_overrides[get_orchestrator] = lambda: _PlanningOrchestrator()
    client = TestClient(app)

    response = client.post(
        "/v1/task/execute",
        json=_bus_payload(
            task_id="task_api_001_plan_only",
            action="build",
            payload={
                "goal": "Add a trivial hello function to a fresh Python module",
                "mode": "plan_only",
            },
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task_api_001_plan_only"
    assert body["target_agent"] == "forge"
    assert body["status"] == "PLANNED"
    assert body["result"]["state"] == "PLANNED"
    assert body["result"]["plan_stages"] == 2
    # plan_only certifies nothing: no completion receipt by design.
    assert body["receipt"] is None
