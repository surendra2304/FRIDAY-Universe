"""TASK-INT-012: /healthz is process-only liveness.

/healthz must perform NO database work (no pool checkout, no query):
dependency readiness lives at /readyz, unchanged. These tests pin the
split:

- /healthz and its /health alias never call check_database_health;
- /healthz stays 200 / "ok" even when the database check would fail;
- the response shape consumers read is unchanged (same key set), with
  `database` reporting "not_checked" from a non-query source (FRIDAY's
  fleet client ask_intelx reads the field for display);
- /readyz still exercises the database check exactly once per call.
"""

import pytest
from httpx import AsyncClient

import intelx.api.v1.health as health_module

EXPECTED_HEALTHZ_KEYS = {
    "status",
    "evidence_class",
    "observed_at",
    "service",
    "version",
    "mock_mode",
    "database",
    "timestamp",
}


@pytest.fixture
def db_check_spy(monkeypatch):
    """Replace the health module's database check with a recording spy."""
    calls: list[int] = []

    async def spy():
        calls.append(1)
        return True

    monkeypatch.setattr(health_module, "check_database_health", spy)
    return calls


@pytest.mark.asyncio
async def test_healthz_performs_no_database_work(client: AsyncClient, db_check_spy):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert db_check_spy == []


@pytest.mark.asyncio
async def test_health_alias_performs_no_database_work(client: AsyncClient, db_check_spy):
    response = await client.get("/health")
    assert response.status_code == 200
    assert db_check_spy == []


@pytest.mark.asyncio
async def test_healthz_ok_even_when_database_is_down(client: AsyncClient, monkeypatch):
    """Liveness must not degrade with the database; readiness carries that."""

    async def database_down():
        return False

    monkeypatch.setattr(health_module, "check_database_health", database_down)
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "not_checked"


@pytest.mark.asyncio
async def test_healthz_response_shape_for_consumers(client: AsyncClient):
    """Pin the exact key set consumers read (fleet probe: status;
    ask_intelx: version, mock_mode, database) plus the liveness fields."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == EXPECTED_HEALTHZ_KEYS
    assert data["status"] == "ok"
    assert data["evidence_class"] == "process_liveness"
    assert data["database"] == "not_checked"


@pytest.mark.asyncio
async def test_readyz_still_exercises_database_check(client: AsyncClient, db_check_spy):
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert len(db_check_spy) == 1
    assert response.json()["database"] == "connected"
