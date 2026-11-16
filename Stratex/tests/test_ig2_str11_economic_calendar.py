"""TASK-IG2-STR-11 — economic/earnings calendar tests (no network)."""

from datetime import date, datetime

import pytest

from research.economic_calendar import (
    EconomicCalendar,
    classify_earnings_impact,
    classify_macro_impact,
    parse_earnings,
    parse_economic_events,
)

DAY = "2026-11-17"
TODAY = date(2026, 11, 17)

ECON_PAYLOAD = {"data": {"rows": [
    {"eventName": "Consumer Price Index (MoM)", "time": "8:30 AM", "country": "US",
     "previous": "0.3%", "consensus": "0.2%", "actual": ""},
    {"eventName": "Nonfarm Payrolls", "time": "8:30 AM", "country": "US",
     "previous": "150K", "consensus": "180K", "actual": ""},
    {"eventName": "Crude Oil Inventories", "time": "10:30 AM", "country": "US",
     "previous": "", "consensus": "", "actual": ""},
    {"eventName": "", "time": "1:00 PM"},  # dropped: no name
]}}

EARN_PAYLOAD = {"data": {"rows": [
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "time": "4:30 PM",
     "epsForecast": "$1.20"},
    {"symbol": "SMOL", "name": "Small Co", "time": "7:00 AM", "epsForecast": "$0.01"},
]}}


def test_classify_macro_impact():
    assert classify_macro_impact("Consumer Price Index (MoM)") == "high"
    assert classify_macro_impact("FOMC Meeting Minutes") == "high"
    assert classify_macro_impact("Housing Starts") == "medium"
    assert classify_macro_impact("Crude Oil Inventories") == "low"


def test_classify_earnings_impact():
    assert classify_earnings_impact("NVDA") == "high"
    assert classify_earnings_impact("SMOL") == "medium"
    assert classify_earnings_impact("SMOL", {"SMOL"}) == "high"


def test_parse_economic_events():
    events = parse_economic_events(ECON_PAYLOAD, DAY)
    assert len(events) == 3
    cpi = events[0]
    assert cpi.impact == "high" and cpi.time == "08:30" and cpi.kind == "macro"
    assert cpi.forecast == "0.2%"
    assert events[2].impact == "low"


def test_parse_earnings():
    events = parse_earnings(EARN_PAYLOAD, DAY)
    assert len(events) == 2
    nvda = events[0]
    assert nvda.symbol == "NVDA" and nvda.impact == "high" and nvda.time == "16:30"
    assert events[1].impact == "medium"


def _fake_fetch(url, params=None, timeout=15.0):
    if "economicevents" in url:
        return ECON_PAYLOAD
    if "earnings" in url:
        return EARN_PAYLOAD
    raise AssertionError(url)


def test_refresh_and_queries(tmp_path):
    cal = EconomicCalendar(store_path=str(tmp_path / "cal.jsonl"),
                           fetch_json=_fake_fetch)
    count = cal.refresh(days_ahead=0, today=TODAY)
    assert count == 5  # 3 macro + 2 earnings, deduped by (date, name, kind)
    assert cal.last_refresh_ok is True
    high = cal.high_impact_events(days=0, today=TODAY)
    assert {e.name for e in high} >= {"Consumer Price Index (MoM)", "Nonfarm Payrolls"}
    assert any(e.symbol == "NVDA" for e in high)
    # Re-refresh is idempotent (dedupe).
    assert cal.refresh(days_ahead=0, today=TODAY) == 5


def test_event_risk_window(tmp_path):
    cal = EconomicCalendar(store_path=str(tmp_path / "cal.jsonl"),
                           fetch_json=_fake_fetch)
    cal.refresh(days_ahead=0, today=TODAY)
    inside = cal.event_risk(datetime(2026, 11, 17, 9, 0), window_hours=2.0)
    assert inside["in_risk_window"] is True
    outside = cal.event_risk(datetime(2026, 11, 17, 20, 0), window_hours=1.0)
    assert outside["in_risk_window"] is False
    assert "pause" in inside["advisory"]


def test_refresh_failure_keeps_serving_stored(tmp_path):
    cal = EconomicCalendar(store_path=str(tmp_path / "cal.jsonl"),
                           fetch_json=_fake_fetch)
    cal.refresh(days_ahead=0, today=TODAY)

    def dead(url, params=None, timeout=15.0):
        raise ConnectionError("nasdaq down")

    cal.fetch_json = dead
    cal.refresh(days_ahead=0, today=TODAY)
    assert cal.last_refresh_ok is False
    assert len(cal.upcoming(days=0, today=TODAY)) == 5  # stored data survives


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
