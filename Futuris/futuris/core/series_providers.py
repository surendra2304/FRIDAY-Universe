"""Measured daily series for universe targets, from Futuris's own stored data.

TASK-FUT-012: a universe target whose spec names a ``series_provider`` is
forecast from a daily series read out of data Futuris itself persisted --
the IntelX notices it consumed through Memora and the forecasts it has
produced for the fleet. Those are measured numbers (EvidenceClass.LIVE),
not telemetry invented by a generator and not caller-supplied estimates.

Providers return a contiguous, zero-filled daily series over the most
recent *complete* UTC days (today is excluded: a partial day would read as
a demand collapse every morning). A day with no stored rows is a measured
zero, so gaps are filled, never interpolated.

Bucketing is done in Python after a plain ``select`` of the timestamp (and
payload, where a filter needs it). That is portable across Oracle and the
SQLite test engines and the tables are small (advisory notice copies and
forecast rows); if either table grows by orders of magnitude, replace the
fetch with a dialect GROUP BY behind this same interface.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from futuris.storage.models import ForecastModel, IntelXNoticeModel

UTC = timezone.utc

#: A provider reads a stored table and returns (day, value) points.
SeriesProvider = Callable[..., Awaitable[list[tuple[date, float]]]]


def bucket_daily_counts(
    timestamps: list[datetime], *, days: int, now: datetime
) -> list[tuple[date, float]]:
    """Zero-filled daily counts over the ``days`` complete UTC days ending yesterday."""
    end = now.astimezone(UTC).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    counts: dict[date, float] = {start + timedelta(days=i): 0.0 for i in range(days)}
    for ts in timestamps:
        if ts is None:
            continue
        # SQLite test engines hand back naive datetimes; the codebase stores
        # UTC by convention, so a naive value is read as UTC, never local.
        day = ts.astimezone(UTC).date() if ts.tzinfo is not None else ts.date()
        if day in counts:
            counts[day] += 1.0
    return sorted(counts.items())


def notice_domain(payload: Any) -> str | None:
    """Domain of an IntelX notice payload, mirroring the feed consumer's rule.

    TASK-INT-014 envelopes carry the domain at ``relevance.domain``; the
    top-level ``domain`` key is accepted for older stored shapes.
    """
    if not isinstance(payload, dict):
        return None
    relevance = payload.get("relevance")
    if isinstance(relevance, dict) and relevance.get("domain"):
        return str(relevance["domain"])
    if payload.get("domain"):
        return str(payload["domain"])
    return None


def notice_topics(payload: Any) -> list[str]:
    """Topic tags of an IntelX notice payload (empty when untagged)."""
    if not isinstance(payload, dict):
        return []
    topics = payload.get("topics")
    if isinstance(topics, list):
        return [str(t) for t in topics if t]
    return []


async def intelx_notice_series(
    session: AsyncSession,
    *,
    days: int,
    now: datetime,
    domain: str | None = None,
    require_topics: bool = False,
) -> list[tuple[date, float]]:
    """Daily counts of stored IntelX notices, optionally filtered.

    ``require_topics`` counts only topic-tagged notices -- the trend
    feedstock VyralX's loop consumes; an untagged notice is a finding, but
    it is not a trend signal.
    """
    rows = (
        await session.execute(
            select(IntelXNoticeModel.received_at, IntelXNoticeModel.payload)
        )
    ).all()
    stamps: list[datetime] = []
    for received_at, payload in rows:
        if domain is not None and notice_domain(payload) != domain:
            continue
        if require_topics and not notice_topics(payload):
            continue
        stamps.append(received_at)
    return bucket_daily_counts(stamps, days=days, now=now)


async def forecast_request_series(
    session: AsyncSession, *, days: int, now: datetime
) -> list[tuple[date, float]]:
    """Daily counts of forecasts Futuris has produced (fleet demand)."""
    rows = (await session.execute(select(ForecastModel.created_at))).all()
    return bucket_daily_counts([row[0] for row in rows], days=days, now=now)


async def _intelx_notices(
    session: AsyncSession, *, days: int, now: datetime
) -> list[tuple[date, float]]:
    return await intelx_notice_series(session, days=days, now=now)


async def _intelx_topic_notices(
    session: AsyncSession, *, days: int, now: datetime
) -> list[tuple[date, float]]:
    return await intelx_notice_series(session, days=days, now=now, require_topics=True)


#: Provider registry, keyed by the name a DomainTargetSpec carries.
SERIES_PROVIDERS: dict[str, SeriesProvider] = {
    "intelx_notices": _intelx_notices,
    "intelx_topic_notices": _intelx_topic_notices,
    "forecast_requests": forecast_request_series,
}


def get_series_provider(name: str) -> SeriesProvider:
    """Resolve a provider by name; ``KeyError`` names the unknown provider."""
    return SERIES_PROVIDERS[name]
