"""Market-forecast event-context wiring tests (TASK-IG-FUT-02).

The forecast must explain event-driven moves: with a war in the IntelX
reports, the response carries a cited ``event_context`` block and the
rationale names the event; with IntelX down, the block honestly says
``source_unavailable``; with no events reported, ``none_reported``.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from futuris.api.routers import market as market_module
from futuris.connectors.base import Observation
from futuris.connectors.intelx_context import IntelXResearchReport

UTC = timezone.utc
NOW = datetime(2026, 3, 12, tzinfo=UTC)


def _obs(series_id: str, value: float) -> Observation:
    return Observation(
        observed_at=NOW,
        source="stratex",
        series_id=series_id,
        value=value,
        unit="ratio",
    )


class FakeTradingConnector:
    def __init__(self, **kwargs):
        pass

    async def fetch(self, start, end):
        return [
            _obs("trading:volatility:btc", 0.50),
            _obs("trading:drawdown", 3.0),
            _obs("trading:equity", 10000.0),
        ]


def _report(findings, *, summary="Research note."):
    return IntelXResearchReport(
        report_id=uuid4(),
        asset_or_sector="BTCUSDT",
        published_at=NOW,
        summary=summary,
        sentiment_score=0.0,
        volatility_impact_factor=1.0,
        key_findings=findings,
        tags=["intelx"],
    )


class FakeIntelXInjector:
    reports: list = []
    fail: bool = False

    def __init__(self, **kwargs):
        pass

    async def fetch_recent_research(self, asset_or_sector, lookback_days, as_of):
        if type(self).fail:
            raise RuntimeError("intelx down")
        return list(type(self).reports)

    async def fetch_durable_notice_context(self, asset_or_sector, lookback_days, as_of):
        return []

    def compute_exogenous_adjustments(self, reports):
        return {
            "sentiment_multiplier": 1.0,
            "volatility_multiplier": 1.0,
            "confidence_penalty": 0.0,
        }


@pytest.fixture(autouse=True)
def _patch_connectors(monkeypatch):
    FakeIntelXInjector.reports = []
    FakeIntelXInjector.fail = False
    monkeypatch.setattr(market_module, "TradingBotConnector", FakeTradingConnector)
    monkeypatch.setattr(market_module, "IntelXContextInjector", FakeIntelXInjector)
    monkeypatch.setattr(
        market_module.ecosystem_adapter,
        "dispatch_market_forecast_to_stratex",
        AsyncMock(return_value=None),
    )


async def _forecast(**kwargs):
    return await market_module._generate_market_prediction(
        symbol="BTCUSDT",
        include_inference=False,
        forecast_repo=None,
        **kwargs,
    )


async def test_war_context_is_cited_in_response_and_named_in_rationale():
    war = _report(["Missile strikes hit energy infrastructure overnight"])
    FakeIntelXInjector.reports = [war]

    resp = await _forecast(include_intelx=True)

    assert resp.event_context.status == "available"
    assert len(resp.event_context.events) == 1
    event = resp.event_context.events[0]
    assert event.category == "geopolitical_conflict"
    assert event.source_report_id == str(war.report_id)
    assert event.title == "Missile strikes hit energy infrastructure overnight"
    rationale = resp.regime_outlook.rationale
    assert "Event context [geopolitical_conflict]" in rationale
    assert "Missile strikes" in rationale
    assert "(IntelX, 2026-03-12)" in rationale


async def test_intelx_down_is_source_unavailable_never_filled():
    FakeIntelXInjector.fail = True

    resp = await _forecast(include_intelx=True)

    assert resp.event_context.status == "source_unavailable"
    assert resp.event_context.events == []
    assert "Event context" not in resp.regime_outlook.rationale


async def test_no_events_reported_is_stated_plainly():
    FakeIntelXInjector.reports = [_report(["Spot accumulation continues steadily"])]

    resp = await _forecast(include_intelx=True)

    assert resp.event_context.status == "none_reported"
    assert resp.event_context.events == []


async def test_intelx_not_requested_is_not_requested():
    resp = await _forecast(include_intelx=False)

    assert resp.event_context.status == "not_requested"
    assert resp.event_context.events == []
