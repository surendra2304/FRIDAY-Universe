"""TASK-OBS-003 — FRIDAY /health must not fabricate its two headline claims.

Before this task, `health_check` built an honest report (friday_deep.health
computes overall from real import checks) and then overwrote it:

    data["status"] = "healthy"        # regardless of the report's verdict
    data["peers_mesh"] = "connected"   # with no mesh probe at all

Live evidence at audit time (2026-11-15): /api/mesh/status reported
history=36 with state_counts {UNVERIFIED: 12, DEGRADED: 4, REFUSED: 4,
PENDING: 4, COMPLETED: 12} and its own live_verification string said
CONFIGURED-BUT-UNVERIFIED — while /health simultaneously claimed
peers_mesh="connected" as a constant.

These tests pin the honest contract:
- `status` is the report's computed overall verdict, never a constant.
- `peers_mesh` is "connected" only when this process has actually recorded
  a completed mesh outcome; otherwise it says what is true instead.
- TASK-REL-067 (REL-004 §2.2/§3): `status` now uses the contract
  vocabulary ok/degraded (never "healthy"), and HTTP is 200 iff ok else
  503. `overall` keeps the report's own "healthy"/"degraded" values.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from friday.api.server import _peers_mesh_state, app
from friday_deep.health import Check, Health, Report


class _MeshStub:
    def __init__(self, status_payload):
        self._payload = status_payload

    def status(self):
        return self._payload


def _report(overall: Health) -> Report:
    return Report(
        overall=overall,
        checks=[Check("friday", overall, "stubbed for OBS-003")],
    )


def test_health_status_follows_the_report_verdict() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "friday.api.server.build_health_report",
        return_value=_report(Health.DEGRADED),
    ):
        resp = client.get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["overall"] == "degraded"
    assert data["status"] == "degraded", (
        "status must be the report's verdict; a constant 'healthy' here is "
        "the fabrication TASK-OBS-003 removed"
    )
    assert data["capabilities"]["orchestration"]["state"] == "degraded"
    assert data["capabilities"]["orchestration"]["detail"] == "IMPORT_CHECK_FAILED"


def test_health_status_healthy_when_report_healthy() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "friday.api.server.build_health_report",
        return_value=_report(Health.HEALTHY),
    ):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "friday_core"


def test_peers_mesh_connected_only_with_completed_outcome() -> None:
    mesh = _MeshStub(
        {"peers": [{"name": "inference"}], "state_counts": {"COMPLETED": 3}}
    )
    with patch("friday.api.server.get_mesh", return_value=mesh):
        assert _peers_mesh_state() == "connected"


def test_peers_mesh_configured_but_unverified_without_outcomes() -> None:
    mesh = _MeshStub(
        {"peers": [{"name": "inference"}], "state_counts": {"UNVERIFIED": 2}}
    )
    with patch("friday.api.server.get_mesh", return_value=mesh):
        assert _peers_mesh_state() == "configured_unverified"


def test_peers_mesh_unavailable_when_mesh_uninspectable() -> None:
    with patch(
        "friday.api.server.get_mesh", side_effect=RuntimeError("mesh down")
    ):
        assert _peers_mesh_state() == "unavailable"
