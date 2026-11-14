"""TASK-REL-018: the FRIDAY delegation payload must carry real provenance,
and a dead model backend must answer BLOCKED -- never a mock forecast.

Before the fix, ``FridayForecastResponse.evidence_class`` /
``evidence_source`` were never copied from the forecast, so they sat at
their schema defaults (``synthetic`` / null) regardless of the actual
input; and with statsforecast missing from the deployment, the endpoint
served flat-line mock numbers as forecasts.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from futuris.api.app import app
from futuris.api.deps import get_db_session
from futuris.storage.models import Base

MASTER_KEY = "futuris_master_test_key_0123456789abcdef"


@pytest_asyncio.fixture(scope="function")
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[httpx.AsyncClient, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db_session] = _override_get_db
        from futuris.infra.config import settings

        monkeypatch.setattr(settings, "FUTURIS_API_KEY", MASTER_KEY)
        monkeypatch.setattr(settings, "FUTURIS_FRIDAY_API_KEY", MASTER_KEY)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"X-API-Key": MASTER_KEY},
        ) as ac:
            yield ac
        app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_forecast_blocked_when_statsforecast_unavailable(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forced backend failure (test environment): the delegation answers
    BLOCKED with the reason named and the would-be input's provenance --
    and no invented prediction."""
    monkeypatch.setattr("futuris.api.routers.friday.STATSFORECAST_AVAILABLE", False)
    monkeypatch.setattr(
        "futuris.api.routers.friday.STATSFORECAST_IMPORT_ERROR",
        "ModuleNotFoundError: forced for test",
    )
    resp = await client.post(
        "/v1/friday/forecast",
        json={
            "friday_request_id": "req_rel018_blocked",
            "target": "service:checkout:capacity_exceedance_24h",
            "horizon": "24h",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "BLOCKED"
    assert data["model_used"] == "none"
    assert data["calibration_metrics"]["error"] == "statsforecast_unavailable"
    assert data["model_metadata"]["blocked_reason"] == "statsforecast_unavailable"
    # Provenance of the configured input is still reported, honestly.
    assert data["evidence_class"] == "synthetic"
    assert "SyntheticTelemetryConnector" in data["evidence_source"]
    assert "SYNTHETIC" in data["evidence_source"]


@pytest.mark.asyncio
async def test_forecast_payload_provenance_matches_actual_input(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Happy path with a working backend: the configured telemetry source
    in this deployment is the synthetic generator, and the payload must
    SAY so -- naming the connector -- instead of leaving provenance at a
    default that merely happens to agree."""
    pytest.importorskip("statsforecast")
    pytest.importorskip("pyarrow")
    from futuris.infra.config import settings

    monkeypatch.setattr(settings, "OBJECT_STORE_PATH", str(tmp_path))
    resp = await client.post(
        "/v1/friday/forecast",
        json={
            "friday_request_id": "req_rel018_provenance",
            "target": "service:checkout:capacity_exceedance_24h",
            "horizon": "24h",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] != "BLOCKED"
    assert data["evidence_class"] == "synthetic"
    assert data["evidence_source"] is not None
    assert "SyntheticTelemetryConnector" in data["evidence_source"]
    assert data["model_metadata"]["data_connector"] == "SyntheticTelemetryConnector"
    assert data["model_metadata"]["data_synthetic"] is True
