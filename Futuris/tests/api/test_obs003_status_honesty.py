"""TASK-OBS-003 — Futuris /status must measure, not assert.

Before this task, GET /status returned a constant ``"status": "healthy"``
and a hardcoded ``"port": 8000``. Live proof at audit time (2026-11-15):
the production process answered on port 8004 while /status reported
``"port": 8000``. The verdict now comes from the same measured storage
check /health uses (verify_schema), and the port from the same PORT env
the server launcher binds (futuris.cli serve).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from futuris.api.app import app


@pytest.mark.asyncio
async def test_status_reports_the_bound_port_from_env(health_storage, monkeypatch):
    """PORT env is the launcher's source of truth; /status must reflect it."""
    _ = health_storage
    monkeypatch.setenv("PORT", "8004")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["port"] == 8004
    assert data["status"] == "healthy"
    assert data["storage"]["ready"] is True


@pytest.mark.asyncio
async def test_status_degrades_when_storage_is_not_ready(health_storage, monkeypatch):
    """A constant 'healthy' cannot survive a failed storage check."""
    _ = health_storage

    async def _not_ready():
        return {"ready": False, "expected": 12, "present": 3, "missing": ["x"], "error": None}

    monkeypatch.setattr("futuris.storage.db.verify_schema", _not_ready)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["storage"]["ready"] is False
