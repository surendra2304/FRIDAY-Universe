"""API tests for the TASK-FUT-009 what-if prototype endpoint.

Mirrors the standalone fan-chart test pattern: the endpoint is mounted on
the already-registered fan-chart router (``/v1/scenarios``), needs no DB,
and must label its own output (assumptions printed, probability not
recomputed, evidence class never upgraded).
"""

import httpx
import pytest
from futuris.api.app import app


@pytest.mark.asyncio
async def test_what_if_endpoint_applies_declared_shocks():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        req = {
            "target": "BTCUSDT",
            "base_path": [
                {"step": 1, "central": 100.0, "lower": 90.0, "upper": 110.0},
                {"step": 2, "central": 102.0, "lower": 91.0, "upper": 113.0},
            ],
            "shocks": [
                {"name": "btc_drop", "driver": "BTC", "kind": "pct_change",
                 "magnitude": -20.0, "elasticity": 0.5},
                {"name": "rate_hike", "driver": "policy_rate", "kind": "pp_change",
                 "magnitude": 1.0, "elasticity": -2.0},
            ],
            "base_evidence_class": "live",
            "base_evidence_source": "telemetry:btc_series",
            "base_probability": 0.62,
        }
        resp = await client.post("/v1/scenarios/what-if", json=req)
        assert resp.status_code == 200
        data = resp.json()

        assert data["result_kind"] == "what_if_prototype"
        assert data["prediction_is_not_authorization"] is True
        # -20% * 0.5 + 1pp * -2.0 = -12% total effect on both steps.
        for point in data["adjusted_path"]:
            assert point["total_effect_pct"] == pytest.approx(-12.0)
            assert point["adjusted_lower"] <= point["adjusted_central"] <= point["adjusted_upper"]
        assert data["adjusted_path"][0]["adjusted_central"] == pytest.approx(88.0)
        # Honest labelling: live base -> derived; probability carried, not recomputed.
        assert data["evidence_class"] == "derived"
        assert data["probability_outcome"] == 0.62
        assert data["probability_status"] == "not_recomputed_by_whatif_engine"
        assert any("btc_drop" in a for a in data["assumptions"])
        assert any("not estimated" in a for a in data["assumptions"])


@pytest.mark.asyncio
async def test_what_if_endpoint_rejects_incoherent_path():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        req = {
            "target": "BTCUSDT",
            "base_path": [{"step": 1, "central": 100.0, "lower": 120.0, "upper": 130.0}],
            "shocks": [{"name": "s", "driver": "BTC", "magnitude": -20.0, "elasticity": 0.5}],
        }
        resp = await client.post("/v1/scenarios/what-if", json=req)
        assert resp.status_code == 422
