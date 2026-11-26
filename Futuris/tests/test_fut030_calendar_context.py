"""Economic-calendar context tests (TASK-FUT-030).

The outlook must consume the IG2-STR-11 feed directly: the feed's own
module, classification and store. No network in this file -- the feed
is driven with a fake transport, exactly like its own unit tests.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from futuris.features import calendar_context as cc

# TASK-REL-101: the calendar fixtures track the real current UTC date —
# no fixed calendar date may remain in the Futuris calendar path. The
# old fixed date was harmless here (refresh and query both took it
# explicitly) but the same pin in the router-facing test rolled over
# once the real UTC date moved past it, and failed contracts on main.
TODAY = datetime.now(timezone.utc).date()
DAY = TODAY.isoformat()

ECON_PAYLOAD = {"data": {"rows": [
    {"eventName": "Consumer Price Index (MoM)", "time": "8:30 AM", "country": "US",
     "previous": "0.3%", "consensus": "0.2%", "actual": ""},
    {"eventName": "FOMC Meeting Minutes", "time": "2:00 PM", "country": "US",
     "previous": "", "consensus": "", "actual": ""},
    {"eventName": "Crude Oil Inventories", "time": "10:30 AM", "country": "US",
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


def _feed(tmp_path, fetch=_fake_fetch, **kwargs):
    return cc.CalendarFeed(
        store_path=str(tmp_path / "cal.jsonl"), fetch_json=fetch, **kwargs
    )


def test_loader_resolves_the_real_feed_module():
    module = cc.load_feed_module()
    assert hasattr(module, "EconomicCalendar")
    assert hasattr(module, "CalendarEvent")
    assert hasattr(module, "parse_economic_events")
    path = cc.resolve_feed_module_path()
    assert path is not None
    assert path.name == "economic_calendar.py"
    assert path.parent.name == "research"
    assert path.parent.parent.name == "Stratex"


def test_loader_missing_module_is_file_not_found():
    with pytest.raises(FileNotFoundError):
        cc.load_feed_module("/nonexistent/economic_calendar.py")


def test_default_store_path_is_next_to_the_feed_module():
    store = cc.default_store_path()
    assert store is not None
    assert store.name == "economic_calendar.jsonl"
    assert store.parent.name == "research"


def test_default_transport_is_httpx_not_requests(tmp_path):
    # The feed's own default transport needs ``requests``, which Futuris
    # does not carry; the consumer defaults to the httpx equivalent.
    feed = cc.CalendarFeed(store_path=str(tmp_path / "cal.jsonl"))
    assert feed.calendar.fetch_json is cc.httpx_fetch_json


def test_refresh_populates_store_and_high_impact_query(tmp_path):
    feed = _feed(tmp_path)
    assert feed.refresh_if_stale(days_ahead=0, today=TODAY) is True
    assert feed.last_refresh_ok is True
    events = feed.upcoming_high_impact(days=0, today=TODAY)
    names = {e.name for e in events}
    assert names >= {"Consumer Price Index (MoM)", "FOMC Meeting Minutes"}
    assert any(e.symbol == "NVDA" for e in events)
    assert all(e.impact == "high" for e in events)


def test_refresh_is_skipped_while_store_is_fresh(tmp_path):
    calls = []

    def counting_fetch(url, params=None, timeout=15.0):
        calls.append(url)
        return _fake_fetch(url, params, timeout)

    feed = _feed(tmp_path, fetch=counting_fetch)
    assert feed.refresh_if_stale(days_ahead=0, today=TODAY) is True
    assert len(calls) == 2  # one macro + one earnings fetch
    # Second call inside the max-age window: no refresh, no fetch.
    assert feed.refresh_if_stale(days_ahead=0, today=TODAY) is False
    assert len(calls) == 2


def test_refresh_failure_keeps_serving_stored_events(tmp_path):
    feed = _feed(tmp_path)
    feed.refresh_if_stale(days_ahead=0, today=TODAY)

    def dead(url, params=None, timeout=15.0):
        raise ConnectionError("nasdaq down")

    feed.calendar.fetch_json = dead
    # Force staleness: a fresh store would skip the refresh.
    feed.refresh_max_age_hours = 0
    assert feed.refresh_if_stale(days_ahead=0, today=TODAY) is True
    assert feed.last_refresh_ok is False
    assert len(feed.upcoming_high_impact(days=0, today=TODAY)) == 3


def test_build_context_available_with_headline(tmp_path):
    feed = _feed(tmp_path)
    feed.refresh_if_stale(days_ahead=0, today=TODAY)
    ctx = cc.build_calendar_context(feed, requested=True, days=0, today=TODAY)
    assert ctx.status == "available"
    assert len(ctx.events) == 3
    assert ctx.headline is not None
    # Soonest first: 08:30 CPI before 14:00 FOMC and 16:30 NVDA.
    assert ctx.headline.name == "Consumer Price Index (MoM)"
    assert ctx.headline.kind == "macro" and ctx.headline.impact == "high"
    assert ctx.store_path == str(tmp_path / "cal.jsonl")
    assert ctx.last_refresh_ok is True


def test_build_context_none_upcoming_when_no_high_impact(tmp_path):
    def low_only(url, params=None, timeout=15.0):
        return LOW_ONLY_PAYLOAD

    feed = _feed(tmp_path, fetch=low_only)
    feed.refresh_if_stale(days_ahead=0, today=TODAY)
    ctx = cc.build_calendar_context(feed, requested=True, days=0, today=TODAY)
    assert ctx.status == "none_upcoming"
    assert ctx.events == [] and ctx.headline is None


def test_build_context_source_unavailable_when_store_missing(tmp_path):
    feed = _feed(tmp_path)  # never refreshed: no store file
    assert not feed.store_exists
    ctx = cc.build_calendar_context(feed, requested=True, days=0, today=TODAY)
    assert ctx.status == "source_unavailable"
    assert ctx.events == [] and ctx.headline is None


def test_build_context_source_unavailable_when_feed_missing():
    ctx = cc.build_calendar_context(None, requested=True)
    assert ctx.status == "source_unavailable"


def test_build_context_not_requested(tmp_path):
    feed = _feed(tmp_path)
    feed.refresh_if_stale(days_ahead=0, today=TODAY)
    ctx = cc.build_calendar_context(feed, requested=False, days=0, today=TODAY)
    assert ctx.status == "not_requested"
    assert ctx.events == []


def test_headline_is_the_soonest_event():
    events = [
        cc.CalendarEventItem(date=DAY, time="14:00", name="Late", kind="macro", impact="high"),
        cc.CalendarEventItem(date=DAY, time="08:30", name="Early", kind="macro", impact="high"),
        cc.CalendarEventItem(date=(TODAY + timedelta(days=1)).isoformat(), time="08:30", name="Tomorrow", kind="macro", impact="high"),
    ]
    assert cc.headline_event(events).name == "Early"
    assert cc.headline_event([]) is None


def test_format_headline_cites_feed_record():
    event = cc.CalendarEventItem(
        date=DAY, time="08:30", name="Consumer Price Index (MoM)",
        kind="macro", impact="high",
    )
    text = cc.format_headline(event)
    assert "Calendar [macro/high]: Consumer Price Index (MoM)" in text
    assert f"{DAY} 08:30" in text
    assert "Nasdaq economic calendar" in text
