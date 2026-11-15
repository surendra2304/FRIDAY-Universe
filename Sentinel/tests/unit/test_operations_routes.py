"""TASK-SEN-008: operations router serves alerts/jobs/dashboard and the drill."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel.api.operations_routes import operations_router
from sentinel.modules.operations.alerting import alert_engine
from sentinel.modules.operations.dispatch import OperationsAlertDispatcher


class _FakeChannel:
    channel_configured = True

    def __init__(self):
        self.calls = 0

    def dispatch_notification(self, html_text, discord_payload=None):
        self.calls += 1
        return {"telegram": True, "discord": False}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(operations_router, prefix="/api/v1")
    return TestClient(app)


def test_drill_alert_flows_through_real_path_and_cleans_up():
    channel = _FakeChannel()
    alert_engine.set_dispatcher(OperationsAlertDispatcher(channel=channel))
    try:
        client = _client()
        resp = client.post("/api/v1/operations/drill", json={"target_ref": "asset-routes"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["dispatched"] is True
        assert body["dispatch_channels"] == ["telegram"]
        assert channel.calls == 1
        alert_id = body["alert"]["alert_id"]

        got = client.get(f"/api/v1/operations/alerts/{alert_id}")
        assert got.status_code == 200
        assert got.json()["alert_id"] == alert_id

        resolved = client.post(f"/api/v1/operations/alerts/{alert_id}/resolve")
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"
    finally:
        alert_engine.set_dispatcher(None)


def test_jobs_and_dashboard_endpoints():
    client = _client()
    jobs = client.get("/api/v1/operations/jobs")
    assert jobs.status_code == 200
    assert "scheduler_running" in jobs.json()

    dash = client.get("/api/v1/operations/dashboard")
    assert dash.status_code == 200
    assert "active_alerts_count" in dash.json()
