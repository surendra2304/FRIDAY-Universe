"""TASK-FUT-005: risk payloads must label the provenance of their returns.

The tail-risk surfaces fall back to a calibrated synthetic return generator
(hardcoded per-asset volatility, Student-t draws) when neither stored
observations nor Stratex telemetry yield >=10 prices. Before this task the
fallback payload was indistinguishable from a measured one, and the pairs
endpoint labelled the built-in watchlist as ``source: stratex`` even when
Stratex never answered (production-verified 2026-11-15). These tests pin
the labels: synthetic stays synthetic, measured stays live.
"""

from datetime import UTC, datetime

import httpx
import pytest

from futuris.api.app import app
from futuris.connectors.base import Observation
from futuris.core.enums import SignalClass


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_risk_audit_labels_synthetic_fallback():
    """No stored observations + no Stratex key -> synthetic labels, not live."""
    async with _client() as client:
        resp = await client.get("/v1/risk/audit/BTCUSDT?window_days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["returns_source"] == "synthetic_calibrated_simulation"
    assert data["evidence_class"] == "synthetic"


@pytest.mark.asyncio
async def test_risk_audit_labels_stored_observations_live():
    """Stored price observations -> measured labels with the real sample size."""
    obs_batch = [
        Observation(
            observed_at=datetime.now(UTC),
            source="test:live",
            series_id="trading:ETHUSDT:price",
            value=2000.0 * (1.0 + 0.01 * (i % 5 - 2)),
            unit="USD",
            tags={"signal_class": SignalClass.TELEMETRY.value},
        )
        for i in range(25)
    ]

    from futuris.api.deps import get_observation_repo

    class FakeObsRepo:
        def __init__(self, *args, **kwargs):
            pass

        async def list_by_series(self, series_id, limit=500, since=None, until=None):
            if "ETHUSDT" in series_id:
                return obs_batch
            return []

    app.dependency_overrides[get_observation_repo] = lambda: FakeObsRepo()
    try:
        async with _client() as client:
            resp = await client.get("/v1/risk/audit/ETHUSDT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["returns_source"] == "stored_observations"
        assert data["evidence_class"] == "live"
        assert data["sample_size"] == 24
    finally:
        app.dependency_overrides.pop(get_observation_repo, None)


@pytest.mark.asyncio
async def test_stream_update_labels_generated_and_caller_returns():
    async with _client() as client:
        generated = await client.post(
            "/v1/risk/stream-update", json={"target": "SOLUSDT", "sample_size": 120}
        )
        supplied = await client.post(
            "/v1/risk/stream-update",
            json={"target": "SOLUSDT", "returns": [0.01, -0.02, 0.005] * 10},
        )
    gen_report = generated.json()["risk_report"]
    assert gen_report["returns_source"] == "synthetic_calibrated_simulation"
    assert gen_report["evidence_class"] == "synthetic"
    sup_report = supplied.json()["risk_report"]
    assert sup_report["returns_source"] == "caller_supplied"
    assert sup_report["evidence_class"] == "derived"


@pytest.mark.asyncio
async def test_portfolio_payload_labels_synthetic_assets():
    """With no observation repo, every asset's returns are the generator's."""
    from futuris.api.routers.risk import calculate_portfolio_risk_payload

    payload = await calculate_portfolio_risk_payload(obs_repo=None, window_days=30)
    assert payload["assets"], "watchlist pairs are always evaluated"
    for asset in payload["assets"]:
        assert asset["returns_source"] == "synthetic_calibrated_simulation"
    assert payload["synthetic_return_assets"] == [a["symbol"] for a in payload["assets"]]
    assert payload["measured_return_assets"] == []


@pytest.mark.asyncio
async def test_risk_pulse_fan_chart_labels_hardcoded_price(monkeypatch):
    """No verified position price -> fan chart must not call 67000 'live'."""
    import futuris.api.routers.risk as risk_module
    import futuris.api.routers.streaming as streaming_module
    from futuris.infra.scheduler import ForecastScheduler

    async def fake_payload(obs_repo=None, window_days=30, confidence_level=0.95):
        return {
            "portfolio_summary": {"highest_risk_asset": "BTCUSDT"},
            "positions": [],
            "assets": [{"symbol": "BTCUSDT", "var_95": 0.04}],
        }

    broadcasts: list[dict] = []

    async def fake_broadcast(event_type, payload, target=None):
        broadcasts.append({"type": event_type, "data": payload})
        return 0

    monkeypatch.setattr(risk_module, "calculate_portfolio_risk_payload", fake_payload)
    monkeypatch.setattr(streaming_module.stream_hub, "broadcast", fake_broadcast)

    scheduler = ForecastScheduler()
    await scheduler.stream_risk_pulse_job()

    fan = next(b for b in broadcasts if b["type"] == "fan_chart_simulation")
    assert fan["data"]["current_price"] == 67000.0
    assert fan["data"]["price_source"] == "hardcoded_fallback_estimate"
    assert fan["data"]["evidence_class"] == "synthetic"


@pytest.mark.asyncio
async def test_pairs_endpoint_does_not_label_watchlist_as_stratex():
    """Unconfigured Stratex -> the watchlist must name itself, not Stratex."""
    async with _client() as client:
        resp = await client.get("/v1/risk/stratex/pairs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "core_watchlist"
    assert data["pair_discovery_status"] == "not_configured"
    assert data["active_pairs"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
