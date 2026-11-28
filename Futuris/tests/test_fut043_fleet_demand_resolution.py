"""TASK-FUT-043 tests: the fleet forecast-demand target resolves against daily counts.

The live class ``friday:fleet:forecast_demand_24h`` forecasts the DAILY
COUNT of forecasts Futuris produced, but the resolver applied the
capacity-exceedance rule to every target: the "observed" daily demand was
the MAXIMUM synthetic checkout-rpm value in the window (~1700-2500) while
the forecasts predicted ~190-270 counts/day. All 136 live scores missed
(coverage_90 0.0, MAE ~1922) because the two sides measured different
quantities, not because the intervals were narrow.

Pinned here, on a throwaway SQLite schema built from the real models:

* the fleet rule resolves the count for the UTC day of ``expires_at``
  out of the daily-counts frame (never the telemetry max);
* the fleet rule defers (``ResolutionNotReadyError``) while its expiry
  day is still in progress, so a partial count is never recorded;
* the resolver dispatches by target: the capacity target still resolves
  by the window max, an unknown target raises instead of silently
  falling through to another target's rule, and a fleet forecast without
  a daily-counts frame defers instead of resolving against telemetry;
* the lifecycle sweep leaves a not-ready fleet forecast ACTIVE (deferred)
  and resolves a ready one with the right count in the same pass;
* the scheduler's daily-counts frame builder counts forecast rows per
  UTC day out of the store, matching the ``forecast_requests`` series
  the target is fitted on.
"""

import os

os.environ.setdefault("DATABASE_URL", "oracle+oracledb://mock:mock@localhost:1521/FREE")

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from futuris.core.enums import (
    ConfidenceLevel,
    EvidenceClass,
    ForecastStatus,
)
from futuris.core.lifecycle import LifecycleManager
from futuris.core.resolution import (
    FleetForecastDemandResolutionRuleV1,
    OutcomeResolver,
    ResolutionNotReadyError,
    outcome_resolver,
)
from futuris.core.schemas import Forecast
from futuris.storage.models import Base, OutcomeModel
from futuris.storage.repositories import (
    EventRepository,
    ForecastRepository,
    OutcomeRepository,
)

FLEET_TARGET = "friday:fleet:forecast_demand_24h"
CAPACITY_TARGET = "service:checkout:capacity_exceedance_24h"

AS_OF = datetime(2026, 11, 26, 13, 33, tzinfo=UTC)
EXPIRES = AS_OF + timedelta(hours=24)  # 2026-11-27 13:33 UTC


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _forecast(
    *,
    target: str = FLEET_TARGET,
    as_of: datetime = AS_OF,
    expires_at: datetime = EXPIRES,
    prediction: float = 243.70,
    lower: float = 180.42,
    upper: float = 306.99,
) -> Forecast:
    return Forecast(
        target=target,
        as_of=as_of,
        horizon=timedelta(hours=24),
        expires_at=expires_at,
        prediction=prediction,
        range_lower=lower,
        range_upper=upper,
        probability=None,
        confidence=ConfidenceLevel.MEDIUM,
        model_version="drift@v1:44136fa355b3678a",
        review_at=expires_at,
        predictive_distribution={},
        evidence_class=EvidenceClass.LIVE,
        evidence_source="fut043 test fixture",
        status=ForecastStatus.ACTIVE,
    )


def _counts_frame(*, days: dict[str, float]) -> pd.DataFrame:
    """Daily-counts frame: one row per UTC day, timestamp at day start."""
    return pd.DataFrame(
        [
            {
                "timestamp": datetime.fromisoformat(day).replace(tzinfo=UTC),
                "value": value,
            }
            for day, value in sorted(days.items())
        ]
    )


def _telemetry_frame(*, start: datetime, hours: int = 24) -> pd.DataFrame:
    """Synthetic-style telemetry: 5-minute rpm values ~1200-2400."""
    stamps = [start + timedelta(minutes=5 * i) for i in range(hours * 12)]
    values = [1200.0 + (i % 288) * 4.0 for i in range(hours * 12)]
    return pd.DataFrame([{"timestamp": ts, "value": v} for ts, v in zip(stamps, values)])


# ---------------------------------------------------------------------------
# The fleet rule itself
# ---------------------------------------------------------------------------


def test_fleet_rule_resolves_expiry_day_count() -> None:
    rule = FleetForecastDemandResolutionRuleV1()
    counts = _counts_frame(days={"2026-11-26": 259.0, "2026-11-27": 322.0})
    outcome = rule.resolve(_forecast(), counts)
    assert outcome.observed_value == pytest.approx(322.0)
    assert outcome.event_occurred is None
    assert outcome.resolution_method.value == "automatic"
    assert outcome.resolution_rule_version == "rule:fleet_forecast_demand:v1.0"


def test_fleet_rule_defers_when_expiry_day_incomplete() -> None:
    rule = FleetForecastDemandResolutionRuleV1()
    # Frame ends yesterday: the expiry day (2026-11-27) has no row yet.
    counts = _counts_frame(days={"2026-11-26": 259.0})
    with pytest.raises(ResolutionNotReadyError, match="2026-11-27"):
        rule.resolve(_forecast(), counts)


def test_fleet_rule_uses_the_frame_it_is_given() -> None:
    # Same forecast, two different frames: the observed value follows the
    # frame, never a hardcoded quantity.
    rule = FleetForecastDemandResolutionRuleV1()
    first = rule.resolve(
        _forecast(), _counts_frame(days={"2026-11-27": 100.0})
    )
    second = rule.resolve(
        _forecast(), _counts_frame(days={"2026-11-27": 400.0})
    )
    assert first.observed_value == pytest.approx(100.0)
    assert second.observed_value == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# Dispatch: the resolver must not apply one target's rule to another
# ---------------------------------------------------------------------------


def test_resolver_never_resolves_fleet_against_telemetry() -> None:
    telemetry = _telemetry_frame(start=AS_OF)
    counts = _counts_frame(days={"2026-11-26": 259.0, "2026-11-27": 322.0})
    outcome = outcome_resolver.resolve_forecast(
        _forecast(), telemetry, daily_counts=counts
    )
    # The telemetry max is ~2348; the daily count is 322. Before FUT-043
    # the resolver returned the telemetry max for this target.
    assert outcome.observed_value == pytest.approx(322.0)
    assert outcome.resolution_rule_version == "rule:fleet_forecast_demand:v1.0"


def test_resolver_defers_fleet_without_daily_counts() -> None:
    telemetry = _telemetry_frame(start=AS_OF)
    with pytest.raises(ResolutionNotReadyError, match="daily-counts"):
        outcome_resolver.resolve_forecast(_forecast(), telemetry)


def test_capacity_target_still_resolves_by_window_max() -> None:
    telemetry = _telemetry_frame(start=AS_OF)
    forecast = _forecast(
        target=CAPACITY_TARGET,
        prediction=4200.0,
        lower=4100.0,
        upper=4300.0,
    )
    outcome = outcome_resolver.resolve_forecast(forecast, telemetry)
    assert outcome.observed_value == pytest.approx(float(telemetry["value"].max()))
    assert outcome.resolution_rule_version == "rule:capacity_exceedance:v1.0"
    assert outcome.event_occurred is False  # max 2348 < 4000 threshold


def test_unknown_target_raises_instead_of_silent_fallthrough() -> None:
    telemetry = _telemetry_frame(start=AS_OF)
    forecast = _forecast(target="trading:BTCUSDT:price_variance_24h")
    with pytest.raises(ValueError, match="No resolution rule"):
        outcome_resolver.resolve_forecast(forecast, telemetry)


def test_resolver_registry_holds_both_rules() -> None:
    resolver = OutcomeResolver()
    assert "capacity_exceedance" in resolver.rules
    assert "fleet_forecast_demand" in resolver.rules
    assert isinstance(
        resolver.rules["fleet_forecast_demand"],
        FleetForecastDemandResolutionRuleV1,
    )


# ---------------------------------------------------------------------------
# Lifecycle sweep: defer the not-ready, resolve the ready, same pass
# ---------------------------------------------------------------------------


class _StubEmitter:
    """Records emitted events without touching the real event bus."""

    def __init__(self) -> None:
        self.emitted: list = []

    async def emit(self, event) -> None:  # noqa: ANN001, ANN202
        self.emitted.append(event)


async def test_lifecycle_sweep_defers_not_ready_and_resolves_ready(
    db_session: AsyncSession,
) -> None:
    f_repo = ForecastRepository(db_session)
    o_repo = OutcomeRepository(db_session)
    e_repo = EventRepository(db_session)
    emitter = _StubEmitter()
    manager = LifecycleManager(
        forecast_repo=f_repo,
        outcome_repo=o_repo,
        event_repo=e_repo,
        emitter=emitter,
    )

    # Ready: expires 2026-11-27 13:33, its day (322) is in the frame.
    ready = _forecast()
    # Not ready: expires 2026-11-28 13:33, its day is still in progress.
    not_ready = _forecast(
        as_of=datetime(2026, 11, 27, 13, 33, tzinfo=UTC),
        expires_at=datetime(2026, 11, 28, 13, 33, tzinfo=UTC),
    )
    await f_repo.create(ready)
    await f_repo.create(not_ready)
    await db_session.commit()

    counts = _counts_frame(days={"2026-11-26": 259.0, "2026-11-27": 322.0})
    telemetry = _telemetry_frame(start=AS_OF)
    report = await manager.run_lifecycle_sweep(
        telemetry,
        as_of=datetime(2026, 11, 28, 14, 0, tzinfo=UTC),
        daily_counts_df=counts,
    )
    await db_session.commit()

    assert report.resolved_count == 1
    assert report.deferred_count == 1
    assert report.resolution_failures == 0
    assert len(report.outcomes) == 1
    assert report.outcomes[0].observed_value == pytest.approx(322.0)
    assert (
        report.outcomes[0].resolution_rule_version
        == "rule:fleet_forecast_demand:v1.0"
    )

    ready_after = await f_repo.get(ready.forecast_id)
    assert ready_after is not None
    assert ready_after.status == ForecastStatus.RESOLVED
    deferred_after = await f_repo.get(not_ready.forecast_id)
    assert deferred_after is not None
    assert deferred_after.status == ForecastStatus.ACTIVE

    outcomes = (
        await db_session.execute(
            select(OutcomeModel).where(
                OutcomeModel.forecast_id == not_ready.forecast_id
            )
        )
    ).all()
    assert outcomes == []


# ---------------------------------------------------------------------------
# Scheduler helper: the daily-counts frame counts stored forecast rows
# ---------------------------------------------------------------------------


async def test_daily_counts_frame_counts_stored_forecast_rows(
    db_session: AsyncSession,
) -> None:
    from futuris.infra.scheduler import _daily_forecast_counts_frame
    from futuris.storage.models import ForecastModel

    # ForecastModel.created_at is the production timestamp the series
    # provider buckets on, so insert rows with explicit created_at values
    # (ForecastRepository.create stamps "now", which would land every row
    # on the same day).
    for day, count in (("2026-11-26", 3), ("2026-11-27", 2)):
        base = datetime.fromisoformat(day).replace(tzinfo=UTC)
        for i in range(count):
            db_session.add(
                ForecastModel(
                    forecast_id=uuid4(),
                    target=FLEET_TARGET,
                    as_of=base + timedelta(hours=i),
                    horizon=timedelta(hours=24),
                    expires_at=base + timedelta(hours=i + 24),
                    prediction=243.70,
                    range_lower=180.42,
                    range_upper=306.99,
                    confidence="medium",
                    model_version="drift@v1:44136fa355b3678a",
                    review_at=base + timedelta(hours=i + 24),
                    status="active",
                    created_at=base + timedelta(hours=i),
                    updated_at=base + timedelta(hours=i),
                )
            )
    await db_session.commit()

    f_repo = ForecastRepository(db_session)
    scope = SimpleNamespace(session=db_session, forecast_repo=f_repo)
    frame = await _daily_forecast_counts_frame(
        scope, now=datetime(2026, 11, 28, 14, 0, tzinfo=UTC), days=30
    )
    assert frame is not None
    by_day = {
        pd.to_datetime(ts).date().isoformat(): value
        for ts, value in zip(frame["timestamp"], frame["value"])
    }
    assert by_day["2026-11-26"] == pytest.approx(3.0)
    assert by_day["2026-11-27"] == pytest.approx(2.0)
    # Complete days only: today (2026-11-28) is excluded.
    assert "2026-11-28" not in by_day


async def test_daily_counts_frame_none_without_session() -> None:
    from futuris.infra.scheduler import _daily_forecast_counts_frame

    scope = SimpleNamespace(session=None, forecast_repo=None)
    frame = await _daily_forecast_counts_frame(
        scope, now=datetime(2026, 11, 28, 14, 0, tzinfo=UTC)
    )
    assert frame is None
