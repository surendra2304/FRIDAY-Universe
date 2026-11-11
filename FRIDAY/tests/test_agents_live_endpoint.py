"""Checklist D12 regression: /api/agents/live — per-agent RIGHT-NOW surface.

The endpoint merges peer reachability (supervision snapshot) with the unified
task ledger (TaskRecordStore). Contract locked here:
- all nine canonical agents are always listed (fleet map is the source);
- in_flight is the newest submitted/assigned/dispatched record with its
  description, status and start time — real ledger data only;
- last_outcome is the newest terminal record;
- an agent with no records shows in_flight/last_outcome null and
  total_records 0 — never dressed up as busy;
- the origin gate applies like the other keyless dashboard surfaces.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
_CORE_SRC = REPO / "FRIDAY" / "apps" / "core" / "src"
for _p in (str(_CORE_SRC), str(REPO), str(REPO / "FRIDAY" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday_core.task_records import get_shared_task_records  # noqa: E402

from friday.api.server import app, CANONICAL_INTERNAL_MESH_URLS  # noqa: E402

ATTACKER_ORIGIN = "https://attacker.example"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("FRIDAY_API_KEY", raising=False)
    monkeypatch.delenv("FRIDAY_UNIVERSE_API_KEY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def _clear_shared_store() -> None:
    """Empty the process-wide shared ledger so tests are deterministic."""
    store = get_shared_task_records()
    with store._lock:  # test-only: reset between tests
        store._records.clear()


@pytest.fixture(autouse=True)
def clean_ledger():
    _clear_shared_store()
    yield
    _clear_shared_store()


class TestAgentsLiveEndpoint:
    def test_lists_all_nine_agents_with_zero_records(self, client: TestClient) -> None:
        response = client.get("/api/agents/live")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["scope"] == "reachability_plus_task_ledger"
        assert len(body["agents"]) == len(CANONICAL_INTERNAL_MESH_URLS)
        ids = {a["id"] for a in body["agents"]}
        assert ids == set(CANONICAL_INTERNAL_MESH_URLS.keys())
        for agent in body["agents"]:
            assert agent["in_flight"] is None
            assert agent["last_outcome"] is None
            assert agent["total_records"] == 0
        assert body["ledger_total"] == 0
        assert body["in_flight_count"] == 0

    def test_dispatched_record_surfaces_as_in_flight(self, client: TestClient) -> None:
        store = get_shared_task_records()
        store.create("task_d12aaa111bbb", "Research market catalysts", "intelx")
        store.record_assignment("task_d12aaa111bbb", "intelx")
        store.record_dispatch("task_d12aaa111bbb")

        body = client.get("/api/agents/live").json()
        by_id = {a["id"]: a for a in body["agents"]}
        intelx = by_id["intelx"]
        assert intelx["in_flight"] is not None
        assert intelx["in_flight"]["task_id"] == "task_d12aaa111bbb"
        assert intelx["in_flight"]["description"] == "Research market catalysts"
        assert intelx["in_flight"]["status"] == "dispatched"
        assert intelx["last_outcome"] is None
        assert intelx["total_records"] == 1
        assert body["in_flight_count"] == 1

    def test_terminal_record_surfaces_as_last_outcome_not_in_flight(self, client: TestClient) -> None:
        store = get_shared_task_records()
        store.create("task_d12ccc222ddd", "Portfolio snapshot", "stratex")
        store.record_assignment("task_d12ccc222ddd", "stratex")
        store.record_dispatch("task_d12ccc222ddd")
        store.record_completion("task_d12ccc222ddd", {"result": "balance 10792.8"})

        body = client.get("/api/agents/live").json()
        stratex = {a["id"]: a for a in body["agents"]}["stratex"]
        assert stratex["in_flight"] is None
        assert stratex["last_outcome"] is not None
        assert stratex["last_outcome"]["status"] == "completed"
        assert stratex["last_outcome"]["task_id"] == "task_d12ccc222ddd"
        assert stratex["last_outcome"]["at"]  # terminal time present

    def test_failure_outcome_keeps_status_failed(self, client: TestClient) -> None:
        store = get_shared_task_records()
        store.create("task_d12eee333fff", "Forecast request", "futuris")
        store.record_assignment("task_d12eee333fff", "futuris")
        store.record_dispatch("task_d12eee333fff")
        store.record_failure("task_d12eee333fff", "HTTP 501: no handler")

        body = client.get("/api/agents/live").json()
        futuris = {a["id"]: a for a in body["agents"]}["futuris"]
        assert futuris["in_flight"] is None
        assert futuris["last_outcome"]["status"] == "failed"

    def test_newest_record_wins_per_agent(self, client: TestClient) -> None:
        store = get_shared_task_records()
        store.create("task_d12old000001", "Older completed job", "forge")
        store.record_assignment("task_d12old000001", "forge")
        store.record_dispatch("task_d12old000001")
        store.record_completion("task_d12old000001", {"result": "done"})
        store.create("task_d12new000002", "Newer live job", "forge")
        store.record_assignment("task_d12new000002", "forge")
        store.record_dispatch("task_d12new000002")

        body = client.get("/api/agents/live").json()
        forge = {a["id"]: a for a in body["agents"]}["forge"]
        assert forge["in_flight"]["task_id"] == "task_d12new000002"
        assert forge["total_records"] == 2

    def test_reachability_fields_pass_through(self, client: TestClient) -> None:
        body = client.get("/api/agents/live").json()
        for agent in body["agents"]:
            assert "reachability" in agent
            assert "latency_ms" in agent
            assert "last_checked" in agent

    def test_note_declares_ledger_scope(self, client: TestClient) -> None:
        body = client.get("/api/agents/live").json()
        assert "unified task ledger" in body["note"]

    def test_forged_origin_refused(self, client: TestClient) -> None:
        response = client.get(
            "/api/agents/live", headers={"Origin": ATTACKER_ORIGIN}
        )
        assert response.status_code == 403

    def test_same_origin_allowed(self, client: TestClient) -> None:
        response = client.get(
            "/api/agents/live",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        )
        assert response.status_code == 200


if __name__ == "__main__":  # manual evidence run
    raise SystemExit(pytest.main([__file__, "-q"]))
