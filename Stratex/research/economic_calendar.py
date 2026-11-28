"""
research/economic_calendar.py — Economic/earnings calendar feed (TASK-IG2-STR-11).

Pattern adopted from OpenTerminal (ErTasselli, MIT, reference-only): a
structured calendar of high-impact macro releases and earnings dates so
strategy scans can flag — or pause around — major events. IntelX watches
headlines; Stratex previously had no structured "do not trade into
CPI/NFP" calendar. This is that loss-avoidance input.

Sources (FREE, no API keys — the same public endpoints Nasdaq's own site
uses, plus FRED release context is intentionally NOT used because the
FRED API needs a key):
- Macro:    https://api.nasdaq.com/api/calendar/economicevents?date=YYYY-MM-DD
- Earnings: https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD

Design:
- Events stored as JSONL (Stratex ledger pattern; no new DB backend),
  deduped on (date, name, type); a failed refresh keeps serving the
  last stored events (flagged via ``last_refresh_ok``).
- Impact classification is deterministic and documented: a keyword table
  marks known market-moving releases HIGH (CPI, NFP, FOMC, GDP, ...);
  earnings are HIGH only for the configurable mega-cap watchlist,
  MEDIUM otherwise; everything else LOW/MEDIUM by table.
  GDP is HIGH only for US releases (TASK-STR-113 scope decision):
  non-US GDP rows and GDP-shaped non-releases (debt-to-GDP, % of GDP,
  current account) never go HIGH on the GDP keyword alone.
- ``event_risk(now, hours)`` is an ADVISORY for scan code: it reports
  whether a high-impact event is inside the window. It does not import
  or touch the execution engine — Stratex stays DEMO-ONLY and any pause
  decision remains with the engine's own governance.
- Transport injectable (``fetch_json``); parsers/classifier are pure and
  unit-tested without network.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Callable, Optional

try:
    from logger import get_logger
except Exception:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore
        return logging.getLogger(name)


logger = get_logger("economic_calendar")

NASDAQ_ECONOMIC_URL = "https://api.nasdaq.com/api/calendar/economicevents"
NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"

# Deterministic high-impact macro keywords (matched case-insensitively).
HIGH_IMPACT_KEYWORDS = (
    "consumer price index", "cpi", "nonfarm", "non-farm", "employment situation",
    "fomc", "federal open market", "interest rate decision", "fed chair",
    "gross domestic product", "gdp", "retail sales", "producer price index",
    "ppi", "personal consumption expenditures", "pce", "jobless claims",
    "unemployment rate", "ism manufacturing", "ism services",
    "consumer confidence", "durable goods",
)
MEDIUM_IMPACT_KEYWORDS = (
    "housing starts", "building permits", "industrial production",
    "factory orders", "trade balance", "consumer sentiment", "jolts",
    "existing home sales", "new home sales", "capacity utilization",
)

# GDP scope (TASK-STR-113): the scan-pause advisory is US-market scoped,
# so GDP is HIGH only for US releases. The GDP keywords are handled
# separately from HIGH_IMPACT_KEYWORDS in classify_macro_impact.
GDP_KEYWORDS = ("gross domestic product", "gdp")
_HIGH_IMPACT_KEYWORDS_NO_GDP = tuple(
    kw for kw in HIGH_IMPACT_KEYWORDS if kw not in GDP_KEYWORDS)
# Name shapes that are never a GDP release even when they contain "gdp"
# (TASK-STR-113 Class C): debt statistics, %-of-GDP statistics, and the
# current account. A word-boundary "gdp" match does NOT exclude
# "Current Account % of GDP", so these are excluded semantically.
GDP_NON_RELEASE_MARKERS = ("debt-to-gdp", "debt to gdp", "% of gdp",
                           "current account")
# Country values Nasdaq reports for US releases; blank is treated as US
# (the classifier's historical default when no country is supplied).
US_COUNTRY_VALUES = {"", "us", "usa", "united states"}

# Earnings from these names are treated as market-moving by default.
DEFAULT_MEGACAP_WATCHLIST = {
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA",
    "AVGO", "BRK/B", "JPM", "LLY", "WMT", "XOM",
}


@dataclass
class CalendarEvent:
    date: str            # YYYY-MM-DD (exchange-local, US/Eastern for Nasdaq)
    time: str            # HH:MM 24h or "" when the source gives none
    name: str
    kind: str            # "macro" | "earnings"
    impact: str          # "high" | "medium" | "low"
    country: str = ""
    symbol: str = ""     # earnings only
    previous: str = ""
    forecast: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.date, self.name.lower(), self.kind)

    def starts_at(self) -> Optional[datetime]:
        """Best-effort tz-aware start (US/Eastern approximated as UTC-5/-4
        is NOT attempted; callers compare by date + hour window instead)."""
        try:
            d = date.fromisoformat(self.date)
        except ValueError:
            return None
        t = dtime(0, 0)
        if self.time:
            try:
                hh, mm = self.time.split(":")[:2]
                t = dtime(int(hh), int(mm))
            except (ValueError, IndexError):
                pass
        return datetime.combine(d, t, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Pure classification + parsing
# ---------------------------------------------------------------------------

def _is_us_country(country: str) -> bool:
    """True for US releases; blank country is treated as US (the
    classifier's historical default when no country is supplied)."""
    return (country or "").strip().lower() in US_COUNTRY_VALUES


def _is_gdp_non_release(name: str) -> bool:
    """True when the name contains a GDP keyword only as part of a
    statistic that is not a GDP release (TASK-STR-113 Class C)."""
    text = (name or "").lower()
    return any(marker in text for marker in GDP_NON_RELEASE_MARKERS)


def classify_macro_impact(name: str, country: str = "") -> str:
    """Classify a macro release name.

    GDP (TASK-STR-113 scope decision) is HIGH only for a genuine US GDP
    release: country US/blank and not a non-release shape. A non-US GDP
    row, or a debt-to-GDP / %-of-GDP / current-account shape, never goes
    HIGH on the GDP keyword alone — it falls through to the remaining
    keyword table, so it can still be HIGH for another reason (e.g. CPI).
    """
    text = (name or "").lower()
    if any(kw in text for kw in GDP_KEYWORDS):
        if _is_us_country(country) and not _is_gdp_non_release(name):
            return "high"
        if any(kw in text for kw in _HIGH_IMPACT_KEYWORDS_NO_GDP):
            return "high"
        if any(kw in text for kw in MEDIUM_IMPACT_KEYWORDS):
            return "medium"
        return "low"
    if any(kw in text for kw in HIGH_IMPACT_KEYWORDS):
        return "high"
    if any(kw in text for kw in MEDIUM_IMPACT_KEYWORDS):
        return "medium"
    return "low"


def classify_earnings_impact(symbol: str, watchlist: Optional[set[str]] = None) -> str:
    watch = watchlist if watchlist is not None else DEFAULT_MEGACAP_WATCHLIST
    return "high" if (symbol or "").upper() in watch else "medium"


def _hhmm(raw: str) -> str:
    """Nasdaq gives times like '8:30 AM' or '4:30 PM' -> '08:30' / '16:30'."""
    text = (raw or "").strip().upper()
    if not text:
        return ""
    try:
        meridiem = "PM" if text.endswith("PM") else "AM" if text.endswith("AM") else ""
        core = text.replace("AM", "").replace("PM", "").strip()
        hh_str, mm_str = core.split(":")
        hh, mm = int(hh_str), int(mm_str)
        if meridiem == "PM" and hh < 12:
            hh += 12
        if meridiem == "AM" and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm:02d}"
    except (ValueError, IndexError):
        return ""


def parse_economic_events(payload: Any, day: str) -> list[CalendarEvent]:
    rows = ((payload or {}).get("data") or {}).get("rows") or []
    events: list[CalendarEvent] = []
    for row in rows:
        name = str(row.get("eventName") or "").strip()
        if not name:
            continue
        events.append(CalendarEvent(
            date=day, time=_hhmm(str(row.get("time") or "")),
            name=name, kind="macro",
            impact=classify_macro_impact(name, str(row.get("country") or "")),
            country=str(row.get("country") or ""),
            previous=str(row.get("previous") or ""),
            forecast=str(row.get("consensus") or row.get("forecast") or ""),
            actual=str(row.get("actual") or "")))
    return events


def parse_earnings(payload: Any, day: str,
                   watchlist: Optional[set[str]] = None) -> list[CalendarEvent]:
    rows = ((payload or {}).get("data") or {}).get("rows") or []
    events: list[CalendarEvent] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        company = str(row.get("name") or symbol).strip()
        when = str(row.get("time") or "")
        events.append(CalendarEvent(
            date=day, time=_hhmm(when) if ":" in when else "",
            name=f"{symbol} earnings ({company})", kind="earnings",
            impact=classify_earnings_impact(symbol, watchlist), symbol=symbol,
            forecast=str(row.get("epsForecast") or "")))
    return events


def default_fetch_json(url: str, params: Optional[dict[str, Any]] = None,
                       timeout: float = 15.0) -> Any:
    import requests  # already a Stratex dependency

    resp = requests.get(
        url, params=params, timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FRIDAY-Stratex-Research/1.0)",
                 "Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Calendar store + queries
# ---------------------------------------------------------------------------

class EconomicCalendar:
    """Refreshes and serves the structured event calendar (JSONL store)."""

    def __init__(self, store_path: str = "economic_calendar.jsonl",
                 fetch_json: Callable[..., Any] = default_fetch_json,
                 megacap_watchlist: Optional[set[str]] = None):
        self.store_path = store_path
        self.fetch_json = fetch_json
        self.megacap_watchlist = megacap_watchlist or set(DEFAULT_MEGACAP_WATCHLIST)
        self.last_refresh_ok = True

    # -- storage -------------------------------------------------------------
    def _read_events(self) -> list[CalendarEvent]:
        if not os.path.exists(self.store_path):
            return []
        out: list[CalendarEvent] = []
        with open(self.store_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(CalendarEvent(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    def _write_events(self, events: list[CalendarEvent]) -> None:
        with open(self.store_path, "w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event.to_dict()) + "\n")

    # -- refresh ---------------------------------------------------------------
    def refresh(self, days_ahead: int = 7, today: Optional[date] = None) -> int:
        """Fetch macro + earnings for each day; merge with stored events.

        Returns the number of events stored after the refresh. A failed
        day/source is skipped (last stored data keeps being served)."""
        today = today or datetime.now(timezone.utc).date()
        merged: dict[tuple[str, str, str], CalendarEvent] = {
            e.key: e for e in self._read_events()}
        ok = True
        for offset in range(days_ahead + 1):
            day = (today + timedelta(days=offset)).isoformat()
            for url, parser in ((NASDAQ_ECONOMIC_URL, parse_economic_events),
                                (NASDAQ_EARNINGS_URL, parse_earnings)):
                try:
                    payload = self.fetch_json(url, params={"date": day})
                    parsed = (parser(payload, day) if parser is parse_economic_events
                              else parser(payload, day, self.megacap_watchlist))
                    for event in parsed:
                        merged[event.key] = event
                except Exception as exc:
                    ok = False
                    logger.warning(f"[ECON_CAL] refresh failed for {day} "
                                   f"({url.rsplit('/', 1)[-1]}): {exc}")
        # Prune events older than yesterday; keep the store bounded.
        cutoff = (today - timedelta(days=1)).isoformat()
        events = sorted((e for e in merged.values() if e.date >= cutoff),
                        key=lambda e: (e.date, e.time, e.name))
        self._write_events(events)
        self.last_refresh_ok = ok
        logger.info(f"[ECON_CAL] refreshed: {len(events)} events stored "
                    f"(sources ok={ok})")
        return len(events)

    # -- queries ---------------------------------------------------------------
    def upcoming(self, days: int = 7, today: Optional[date] = None,
                 min_impact: Optional[str] = None) -> list[CalendarEvent]:
        today = today or datetime.now(timezone.utc).date()
        horizon = (today + timedelta(days=days)).isoformat()
        rank = {"high": 3, "medium": 2, "low": 1}
        out = [e for e in self._read_events()
               if today.isoformat() <= e.date <= horizon]
        if min_impact:
            out = [e for e in out if rank[e.impact] >= rank[min_impact]]
        return sorted(out, key=lambda e: (e.date, e.time, e.name))

    def high_impact_events(self, days: int = 7,
                           today: Optional[date] = None) -> list[CalendarEvent]:
        return self.upcoming(days=days, today=today, min_impact="high")

    def event_risk(self, when: Optional[datetime] = None,
                   window_hours: float = 2.0) -> dict[str, Any]:
        """ADVISORY: is a high-impact event within +/- window_hours of `when`?

        Dates/times are exchange-local as published by Nasdaq; the window
        comparison is done on the naive date+time grid the source publishes,
        which is the right granularity for a scan-pause advisory."""
        when = when or datetime.now(timezone.utc)
        centre = when.replace(tzinfo=None)
        hits: list[CalendarEvent] = []
        for event in self._read_events():
            if event.impact != "high":
                continue
            start = event.starts_at()
            if start is None:
                continue
            delta_h = abs((start.replace(tzinfo=None) - centre).total_seconds()) / 3600.0
            if delta_h <= window_hours:
                hits.append(event)
        return {
            "in_risk_window": bool(hits),
            "window_hours": window_hours,
            "events": [h.to_dict() for h in hits],
            "advisory": ("High-impact event inside the window — flag or pause "
                         "strategy scans per Stratex governance."
                         if hits else "No high-impact event inside the window."),
            "last_refresh_ok": self.last_refresh_ok,
        }
