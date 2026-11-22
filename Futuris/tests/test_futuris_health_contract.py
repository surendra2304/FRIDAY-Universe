"""TASK-REL-067 §5 — Futuris /health capability-contract tests.

REL-004 §2.2: /health returns the capability report with a derived status
and HTTP 503 whenever a required capability is not ``ok``. Futuris has two
required capabilities: ``storage`` (live ``verify_schema()`` check) and
``forecasting`` (no model probe exists anywhere yet, so ``unknown`` /
``NO_MODEL_PROBE`` — storage readiness is not forecasting ability).
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from futuris.api.app import app

_CAPABILITY_STATES = {"ok", "degraded", "unavailable", "unknown"}


@pytest.mark.asyncio
async def test_health_reports_capability_contract_when_storage_ready(health_storage):
    """Storage ready: storage ok, forecasting unknown — top level degraded/503."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["service"] == "futuris"
    assert data["agent"] == "futuris"
    assert data["evidence_class"] == "capability_report"
    assert "observed_at" in data
    assert "version" in data

    caps = data["capabilities"]
    assert set(caps) == {"storage", "forecasting"}
    assert caps["storage"]["state"] == "ok"
    assert "checked_at" in caps["storage"]
    assert caps["forecasting"]["state"] == "unknown"
    assert caps["forecasting"]["detail"] == "NO_MODEL_PROBE"
    assert "checked_at" in caps["forecasting"]
    assert "storage readiness is not forecasting ability" in caps["forecasting"]["evidence"]

    deps = data["dependencies"]
    assert set(deps) == {"database"}
    assert deps["database"]["state"] == "ok"

    # Closed state vocabulary (§2.2 rule 4) — nothing free-text as a state.
    for cap in caps.values():
        assert cap["state"] in _CAPABILITY_STATES
    for dep in deps.values():
        assert dep["state"] in _CAPABILITY_STATES

    # The legacy storage block stays (additive change) and still says ready.
    assert data["storage"]["ready"] is True


@pytest.mark.asyncio
async def test_health_storage_not_ready_is_unavailable_503(tmp_path, monkeypatch):
    """No schema: storage + database unavailable, SCHEMA_INCOMPLETE, 503."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from futuris.storage import db as storage_db
    from futuris.storage.db import install_sqlite_pragmas

    empty = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'uninitialised.db'}")
    install_sqlite_pragmas(empty)
    monkeypatch.setattr(storage_db, "engine", empty)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["capabilities"]["storage"]["state"] == "unavailable"
        assert data["capabilities"]["storage"]["detail"] == "SCHEMA_INCOMPLETE"
        assert data["capabilities"]["storage"]["evidence"], "evidence must name what is missing"
        assert data["dependencies"]["database"]["state"] == "unavailable"
        assert data["dependencies"]["database"]["detail"] == "SCHEMA_INCOMPLETE"
        # forecasting is still honestly unknown, not silently dropped.
        assert data["capabilities"]["forecasting"]["state"] == "unknown"
        assert data["capabilities"]["forecasting"]["detail"] == "NO_MODEL_PROBE"
    finally:
        await empty.dispose()


@pytest.mark.asyncio
async def test_health_database_unreachable_carries_no_raw_exception_text(monkeypatch):
    """Connect failure: DATABASE_UNREACHABLE, and no raw text (DSN) leaks.

    The payload keeps only the exception type name; the full message stays
    server-side in the log (§2.2 rule 8 / criterion 5).
    """

    async def _unreachable():
        return {
            "ready": False,
            "expected": 12,
            "present": 0,
            "missing": ["forecasts"],
            "error": "OperationalError",
        }

    monkeypatch.setattr("futuris.storage.db.verify_schema", _unreachable)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["capabilities"]["storage"]["detail"] == "DATABASE_UNREACHABLE"
    assert data["dependencies"]["database"]["detail"] == "DATABASE_UNREACHABLE"
    assert data["storage"]["error"] == "OperationalError"
    raw = json.dumps(data)
    assert "://" not in raw, "no DSN or URL may appear in a health payload"
    assert "password" not in raw.lower()
    assert "oracle+oracledb" not in raw


@pytest.mark.asyncio
async def test_ready_codes_unchanged(health_storage, tmp_path, monkeypatch):
    """Criterion 6: /ready behaviour is unchanged — 200 ready / 503 not_ready."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from futuris.storage import db as storage_db
    from futuris.storage.db import install_sqlite_pragmas

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    empty = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'uninitialised.db'}")
    install_sqlite_pragmas(empty)
    monkeypatch.setattr(storage_db, "engine", empty)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            not_ready = await client.get("/ready")
        assert not_ready.status_code == 503
        assert not_ready.json()["status"] == "not_ready"
    finally:
        await empty.dispose()
