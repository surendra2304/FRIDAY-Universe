"""Economic-calendar context for market outlooks (TASK-FUT-030).

Owner push (board TASK-FUT-030, source GAP-LIST.md TASK-FUT-CAL):
*"Futuris outlook generation consumes the economic-calendar feed
directly (the feed TASK-IG2-STR-11 built Stratex-primary), evidenced
in one outlook."*

The feed is ``Stratex/research/economic_calendar.py`` (IG2-STR-11,
MERGED PR #697): a structured calendar of high-impact macro releases
and earnings dates from Nasdaq's free public endpoints, with
deterministic HIGH/MEDIUM/LOW classification and a JSONL store. Until
now nothing consumed it in production.

This module is the Futuris-side consumer, mirroring the discipline of
``event_context.py`` (TASK-IG-FUT-02):

* the feed is consumed **directly** -- its own module is loaded by file
  path and its own ``EconomicCalendar`` class, classification and
  parsers do the work. Nothing about the feed is re-implemented here;
  only the outlook-facing context block is new. (``Stratex/`` has no
  ``__init__.py``, so the module cannot be imported as a package; the
  loader below resolves it by walking up to the repo root, which works
  in the monorepo and in the fleet layout where Futuris and Stratex sit
  as siblings under ``/opt/friday_universe``.)
* classification is explanatory only. It changes no number in the
  forecast, names no event the feed did not publish, and when the feed
  module or its store cannot be read the router reports
  ``source_unavailable`` rather than filling the gap.
* the store is refreshed through the feed's own ``refresh()`` and only
  when stale (missing, or older than ``refresh_max_age_hours``): an
  outlook request never pays for a refresh it does not need, and a
  failed refresh keeps serving the last stored events, flagged via
  ``last_refresh_ok``. The feed's default transport is ``requests``
  (a Stratex dependency Futuris does not carry -- Futuris is httpx
  throughout), so this module supplies an httpx transport through the
  feed's own injectable ``fetch_json`` hook; parsing, classification,
  storage and queries stay the feed's own code.

The store path defaults to next to the feed module
(``Stratex/research/economic_calendar.jsonl``); Stratex owns the feed
definition and classification, this module only reads (and, when stale,
refreshes) its store.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from futuris.infra.logging import get_logger

logger = get_logger("futuris.features.calendar_context")

#: File name of the feed module inside the Stratex checkout.
FEED_MODULE_RELATIVE = Path("Stratex/research/economic_calendar.py")
#: Store file kept next to the feed module by default.
FEED_STORE_NAME = "economic_calendar.jsonl"
#: How stale a store may be before an outlook refreshes it (hours).
DEFAULT_REFRESH_MAX_AGE_HOURS = 24.0
#: How far ahead the outlook looks for high-impact events (days).
DEFAULT_HORIZON_DAYS = 7

# Statuses, mirroring EventContext: stated, never filled in.
STATUS_AVAILABLE = "available"
STATUS_NONE_UPCOMING = "none_upcoming"
STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
STATUS_NOT_REQUESTED = "not_requested"

_FEED_MODULE_CACHE: dict[str, ModuleType] = {}

# The feed's own default transport is ``requests`` (a Stratex
# dependency); Futuris is httpx throughout, so the consumer supplies an
# equivalent httpx transport through the feed's injectable fetch hook.
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FRIDAY-Stratex-Research/1.0)",
    "Accept": "application/json",
}


def httpx_fetch_json(
    url: str, params: Optional[dict[str, Any]] = None, timeout: float = 15.0
) -> Any:
    """Synchronous httpx fetch with the feed's own headers/timeout."""
    import httpx

    with httpx.Client(timeout=timeout, headers=FEED_HEADERS) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def resolve_feed_module_path(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate the IG2-STR-11 feed module on disk.

    With no override, walk up from this file looking for a directory
    that contains ``Stratex/research/economic_calendar.py``. Returns
    ``None`` when the feed module cannot be found (fleet layouts where
    the Stratex checkout is absent).
    """
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate if candidate.is_file() else None
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / FEED_MODULE_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def load_feed_module(module_path: Optional[str] = None) -> ModuleType:
    """Load the feed module by file path (cached per resolved path).

    Raises ``FileNotFoundError`` when the feed module cannot be found.
    The feed module's own ``from logger import get_logger`` import falls
    back to stdlib logging when Stratex's logger is not on ``sys.path``,
    so loading it needs no Stratex package on the path.
    """
    resolved = resolve_feed_module_path(module_path)
    if resolved is None:
        raise FileNotFoundError(
            "economic-calendar feed module not found "
            f"(looked for {FEED_MODULE_RELATIVE}"
            + (f" at {module_path}" if module_path else "")
            + ")"
        )
    key = str(resolved)
    cached = _FEED_MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "futuris_economic_calendar_feed", resolved
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load feed module from {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("futuris_economic_calendar_feed", module)
    spec.loader.exec_module(module)
    _FEED_MODULE_CACHE[key] = module
    return module


def default_store_path(module_path: Optional[str] = None) -> Optional[Path]:
    """Default JSONL store path: next to the feed module."""
    resolved = resolve_feed_module_path(module_path)
    if resolved is None:
        return None
    return resolved.parent / FEED_STORE_NAME


class CalendarFeed:
    """Futuris-side handle on the IG2-STR-11 economic-calendar feed.

    Thin wrapper around the feed's own ``EconomicCalendar``: the feed
    class does the storing, parsing, classification and querying; this
    class only resolves paths, gates refreshes on staleness, and reports
    store freshness honestly.
    """

    def __init__(
        self,
        module_path: Optional[str] = None,
        store_path: Optional[str] = None,
        fetch_json: Optional[Callable[..., Any]] = None,
        refresh_max_age_hours: float = DEFAULT_REFRESH_MAX_AGE_HOURS,
    ):
        self.module = load_feed_module(module_path)
        resolved_store = (
            Path(store_path).expanduser()
            if store_path
            else default_store_path(module_path)
        )
        if resolved_store is None:
            raise FileNotFoundError("cannot resolve economic-calendar store path")
        self.store_path = resolved_store
        # Default transport is the httpx fetch above: the feed's own
        # default needs ``requests``, which Futuris does not carry.
        kwargs: dict[str, Any] = {
            "store_path": str(resolved_store),
            "fetch_json": fetch_json if fetch_json is not None else httpx_fetch_json,
        }
        self.calendar = self.module.EconomicCalendar(**kwargs)
        self.refresh_max_age_hours = refresh_max_age_hours
        # Unknown until a refresh is attempted in this process (the
        # feed class defaults True, which would claim a refresh that
        # never happened). The store mtime is the honest freshness signal.
        self.last_refresh_ok: Optional[bool] = None
        self.last_refresh_attempted: bool = False

    # -- freshness ---------------------------------------------------------
    @property
    def store_exists(self) -> bool:
        return self.store_path.is_file()

    @property
    def store_mtime(self) -> Optional[float]:
        try:
            return self.store_path.stat().st_mtime
        except OSError:
            return None

    def store_age_hours(self, now: Optional[float] = None) -> Optional[float]:
        mtime = self.store_mtime
        if mtime is None:
            return None
        return ((now if now is not None else time.time()) - mtime) / 3600.0

    def refresh_needed(self, now: Optional[float] = None) -> bool:
        """True when there is no store, or it is older than the max age."""
        age = self.store_age_hours(now=now)
        if age is None:
            return True
        return age > self.refresh_max_age_hours

    # -- feed operations -----------------------------------------------------
    def refresh_if_stale(
        self, days_ahead: int = DEFAULT_HORIZON_DAYS, today: Optional[date] = None
    ) -> bool:
        """Refresh via the feed's own ``refresh()`` when the store is stale.

        Returns True when a refresh was attempted. A failed refresh keeps
        serving the last stored events (feed behaviour) and is reported
        via ``last_refresh_ok`` -- never raised here, so an outlook is
        never lost to a Nasdaq outage.
        """
        if not self.refresh_needed():
            return False
        self.last_refresh_attempted = True
        try:
            self.calendar.refresh(days_ahead=days_ahead, today=today)
            self.last_refresh_ok = bool(self.calendar.last_refresh_ok)
        except Exception as exc:  # feed refresh must never break an outlook
            self.last_refresh_ok = False
            logger.warning("econ_calendar_refresh_failed", error=type(exc).__name__)
        return True

    def upcoming_high_impact(
        self, days: int = DEFAULT_HORIZON_DAYS, today: Optional[date] = None
    ) -> list[Any]:
        """High-impact events in the window, soonest first (feed order)."""
        return self.calendar.high_impact_events(days=days, today=today)


class CalendarEventItem(BaseModel):
    """One feed-published event, carried verbatim into the outlook."""

    date: str
    time: str = ""
    name: str
    kind: str  # "macro" | "earnings"
    impact: str  # "high" | "medium" | "low"
    country: str = ""
    symbol: str = ""
    forecast: str = ""
    previous: str = ""
    actual: str = ""


class CalendarContext(BaseModel):
    """Structured calendar context attached to a market outlook.

    ``status`` is one of:

    * ``available`` -- at least one high-impact event in the window;
    * ``none_upcoming`` -- the feed answered, no high-impact event in
      the window (stated, not filled);
    * ``source_unavailable`` -- the feed module or its store could not
      be read, so no calendar context could be derived (never backfilled);
    * ``not_requested`` -- the caller did not include calendar context.
    """

    status: str
    events: list[CalendarEventItem] = Field(default_factory=list)
    headline: Optional[CalendarEventItem] = None
    store_path: Optional[str] = None
    store_mtime: Optional[str] = None
    last_refresh_ok: Optional[bool] = None
    refresh_attempted: bool = False


def headline_event(events: list[CalendarEventItem]) -> Optional[CalendarEventItem]:
    """The event an outlook rationale should name, if any.

    The soonest high-impact event: the one whose release the outlook
    window opens on. Deterministic on (date, time, name).
    """
    if not events:
        return None
    return sorted(events, key=lambda e: (e.date, e.time, e.name))[0]


def format_headline(event: CalendarEventItem) -> str:
    """One-line citation for the rationale: name, kind/impact, when, source."""
    when = event.date + (f" {event.time}" if event.time else "")
    return (
        f"Calendar [{event.kind}/{event.impact}]: {event.name} "
        f"({when}, Nasdaq economic calendar)."
    )


def build_calendar_context(
    feed: Optional[CalendarFeed],
    *,
    requested: bool,
    days: int = DEFAULT_HORIZON_DAYS,
    today: Optional[date] = None,
) -> CalendarContext:
    """Compose the honest calendar-context block for one outlook.

    ``feed`` is ``None`` when the feed module could not be loaded; the
    block then honestly says ``source_unavailable``. Refreshing is the
    caller's job (the router refreshes when stale, off the event loop);
    this function only reads the store as it stands.
    """
    if not requested:
        return CalendarContext(status=STATUS_NOT_REQUESTED)
    if feed is None:
        return CalendarContext(status=STATUS_SOURCE_UNAVAILABLE)
    store_mtime = feed.store_mtime
    base = CalendarContext(
        status=STATUS_SOURCE_UNAVAILABLE,
        store_path=str(feed.store_path),
        store_mtime=(
            datetime.fromtimestamp(store_mtime, tz=timezone.utc).isoformat()
            if store_mtime is not None
            else None
        ),
        last_refresh_ok=feed.last_refresh_ok,
        refresh_attempted=feed.last_refresh_attempted,
    )
    if not feed.store_exists:
        return base
    try:
        raw_events = feed.upcoming_high_impact(days=days, today=today)
    except (OSError, ValueError) as exc:
        logger.warning("econ_calendar_read_failed", error=type(exc).__name__)
        return base
    events = [
        CalendarEventItem(
            date=e.date,
            time=e.time or "",
            name=e.name,
            kind=e.kind,
            impact=e.impact,
            country=e.country or "",
            symbol=e.symbol or "",
            forecast=e.forecast or "",
            previous=e.previous or "",
            actual=e.actual or "",
        )
        for e in raw_events
    ]
    if not events:
        base.status = STATUS_NONE_UPCOMING
        return base
    base.status = STATUS_AVAILABLE
    base.events = events
    base.headline = headline_event(events)
    return base
