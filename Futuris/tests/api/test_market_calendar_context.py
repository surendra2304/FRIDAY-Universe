"""Market-forecast calendar-context wiring tests (TASK-FUT-030).

The outlook must consume the economic-calendar feed directly: with a
high-impact release in the window, the response carries a cited
``calendar_context`` block and the rationale names the release; with
the feed down, the block honestly says ``source_unavailable``; with no
high-impact release, ``none_upcoming``. The feed itself is driven with
a fake transport (no network); telemetry uses the same fake connector
as the event-context tests.
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from futuris.api.routers import market as market_module
from futuris.connectors.base import Observation
from futuris.features import calendar_context as cc

UTC = timezone.utc
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
TODAY = date(2026, 11, 25)

ECON_PAYLOAD = {"data": {"rows": [
    {"eventName": "Consumer Price Index (MoM)", "time": "8:30 AM", "country": "US",
     "previous": "0.3%", "consensus": "0.2%", "actual": ""},
    {"eventName": "FOMC Meeting Minutes", "time": "2:00 PM", "country": "US",
     "previous": "", "consensus": "", "actual": ""},
]}}

EARN_PAYLOAD = {"data": {"rows": [
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "time": "4:30 PM",
     "epsForecast": "$1.20"},
]}}

LOW_ONLY_PAYLOAD = {"data": {"rows": [
    {"eventName": "Crude Oil Inventories", "time": "10:30 AM", "country": "US",
     "previous": "", "consensus": "", "actual": ""},
]}}


def _fake_fetch(url, params=None, timeout=15.0):
    if "economicevents" in url:
        return ECON_PAYLOAD
    if "earnings" in url:
        return EARN_PAYLOAD
    raise AssertionError(url)


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


class FakeIntelXInjector:
    reports: list = []

    def __init__(self, **kwargs):
        pass

    async def fetch_recent_research(self, asset_or_sector, lookback_days, as_of):
        return list(type(self).reports)

    async def fetch_durable_notice_context(self, asset_or_sector, lookback_days, as_of):
        return []

    def compute_exogenous_adjustments(self, reports):
        return {
            "sentiment_multiplier": 1.0,
            "volatility_multiplier": 1.0,
            "confidence_penalty": 0.0,
        }


def _feed(tmp_path, fetch=_fake_fetch):
    feed = cc.CalendarFeed(
        store_path=str(tmp_path / "cal.jsonl"), fetch_json=fetch
    )
    feed.refresh_if_stale(days_ahead=0, today=TODAY)
    return feed


@pytest.fixture(autouse=True)
def _patch_connectors(monkeypatch):
    FakeIntelXInjector.reports = []
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
        include_intelx=False,
        include_inference=False,
        forecast_repo=None,
        **kwargs,
    )


async def test_calendar_release_is_cited_in_response_and_named_in_rationale(tmp_path):
    feed = _feed(tmp_path)

    resp = await _forecast(include_calendar=True, calendar_feed=feed)

    assert resp.calendar_context.status == "available"
    assert len(resp.calendar_context.events) == 3
    headline = resp.calendar_context.headline
    assert headline is not None
    assert headline.name == "Consumer Price Index (MoM)"
    assert headline.kind == "macro" and headline.impact == "high"
    rationale = resp.regime_outlook.rationale
    assert "Calendar [macro/high]: Consumer Price Index (MoM)" in rationale
    assert "2026-11-25 08:30" in rationale
    assert "Nasdaq economic calendar" in rationale


async def test_feed_unavailable_is_source_unavailable_never_filled():
    resp = await _forecast(include_calendar=True, calendar_feed=None)

    assert resp.calendar_context.status == "source_unavailable"
    assert resp.calendar_context.events == []
    assert "Calendar [" not in resp.regime_outlook.rationale


async def test_no_high_impact_release_is_stated_plainly(tmp_path):
    def low_only(url, params=None, timeout=15.0):
        return LOW_ONLY_PAYLOAD

    feed = _feed(tmp_path, fetch=low_only)

    resp = await _forecast(include_calendar=True, calendar_feed=feed)

    assert resp.calendar_context.status == "none_upcoming"
    assert resp.calendar_context.events == []
    assert "Calendar [" not in resp.regime_outlook.rationale


async def test_calendar_not_requested_is_not_requested(tmp_path):
    feed = _feed(tmp_path)

    resp = await _forecast(include_calendar=False, calendar_feed=feed)

    assert resp.calendar_context.status == "not_requested"
    assert resp.calendar_context.events == []
    assert "Calendar [" not in resp.regime_outlook.rationale
