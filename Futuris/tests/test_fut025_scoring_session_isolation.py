"""TASK-FUT-025 tests: scoring-session isolation.

Before this task every scheduler job shared the process's single
scheduler session (``app.py`` built one ``async_session_factory()``
session and handed it to every repo). APScheduler runs jobs
concurrently, so a flush in one job collided with a flush or commit in
another (``Session is already flushing``), and a rollback after any
job's failure discarded other jobs' uncommitted writes. Live
consequences (FUT-023 section 6; Muse 9's 18:45 re-check, hub #1483
status 7102277953):

* the 17:45 scoring pass logged scored 8 / n=374 while the store still
  held 366 -- the scores were flushed, never committed, and the
  journal counts came from the same uncommitted session;
* the 17:15 telemetry cycle emitted a forecast_updated event for
  forecast 823e8307..., which was never persisted;
* at 18:15 a second scoring job FAILED "Session is already flushing",
  calibration resolve failed for b5c0a661 + f8921fe7, and the provider
  refresh failed for the vyralx + intelx targets with the same error.

Pinned here, on a throwaway file SQLite schema built from the real
models (a file database, not :memory:, because the point is several
sessions on one store):

* a scoring job's reported counts describe persisted rows -- the count
  a fresh session reads afterwards is the count the job reported;
* two scoring jobs running at once complete without a flushing error
  and persist exactly one score row per resolved forecast;
* the calibration sweep and the scoring job running at once complete
  without a flushing error, and the resolutions + scores persist;
* the provider refresh and the scoring job running at once complete
  without a flushing error, and every provider target's forecast
  persists (vyralx/intelx included);
* the telemetry refresh commits a forecast before emitting its
  forecast_updated event, so the event can never name a forecast the
  store does not hold.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from futuris.core.enums import ConfidenceLevel, EvidenceClass, ResolutionMethod
from futuris.core.schemas import Forecast, ForecastEvent, Outcome
from futuris.infra.scheduler import ForecastScheduler, ForecastSubscription
from futuris.storage.db import install_sqlite_pragmas
from futuris.storage.models import Base
from futuris.storage.repositories import ForecastRepository, OutcomeRepository
from futuris.storage.score_repository import ForecastScoreRepository

AS_OF = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
TARGET = "trading:BTCUSDT:price_variance_24h"
CAPACITY_TARGET = "service:checkout:capacity_exceedance_24h"


def _scheduler_class():
    pytest.importorskip("apscheduler")
    from futuris.infra.scheduler import ForecastScheduler

    return ForecastScheduler


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """One throwaway file database + a session factory bound to it.

    A file database (not :memory:) so several sessions -- the point of
    this task -- share one store. WAL + busy-timeout, installed exactly
    like the shared conftest does, so concurrent writers serialise
    instead of failing on a locked database.
    """
    path = tmp_path / "fut025.db"
    sync_engine = create_sync_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    install_sqlite_pragmas(engine)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    await engine.dispose()


def _forecast(
    *,
    target: str = TARGET,
    prediction: float = 100.0,
    as_of: datetime = AS_OF,
    horizon_hours: float = 24.0,
    probability: float | None = None,
) -> Forecast:
    return Forecast(
        target=target,
        as_of=as_of,
        horizon=timedelta(hours=horizon_hours),
        expires_at=as_of + timedelta(hours=horizon_hours),
        prediction=prediction,
        range_lower=prediction - 10.0,
        range_upper=prediction + 10.0,
        probability=probability,
        confidence=ConfidenceLevel.MEDIUM,
        model_version="statsforecast.Naive:v1.0",
        review_at=as_of + timedelta(hours=24),
        predictive_distribution={"p5": 90.0, "p50": 100.0, "p95": 110.0},
        evidence_class=EvidenceClass.LIVE,
        evidence_source="fut025 test fixture",
    )


def _outcome(forecast: Forecast, observed: float | None) -> Outcome:
    return Outcome(
        outcome_id=uuid4(),
        forecast_id=forecast.forecast_id,
        observed_value=observed,
        event_occurred=None,
        resolved_at=forecast.expires_at + timedelta(hours=1),
        resolution_method=ResolutionMethod.AUTOMATIC,
        ambiguity_note=None,
        resolution_rule_version="fut025-test:v1",
    )


async def _issue_and_resolve(
    session: AsyncSession, forecast: Forecast, observed: float
) -> None:
    await ForecastRepository(session).create(forecast)
    await OutcomeRepository(session).record_outcome(_outcome(forecast, observed))
    await session.commit()


async def _count_scores(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return await ForecastScoreRepository(session).count_scores()


async def _unscored_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return len(await ForecastScoreRepository(session).list_unscored_resolved())


async def test_scoring_job_reports_only_persisted_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The 17:45 drain: scored 8 / n=374 logged, store still 366.

    A scoring job's reported counts must describe persisted rows: the
    count a fresh session reads afterwards is the count the job
    reported, and no resolved forecast is left unscored.
    """
    ForecastScheduler = _scheduler_class()
    async with session_factory() as session:
        for i in range(8):
            await _issue_and_resolve(
                session, _forecast(prediction=100.0 + i), 105.0
            )

    scheduler = ForecastScheduler(session_factory=session_factory)
    result = await scheduler.forecast_scoring_job()

    assert result["scored"] == 8
    assert result.get("status") != "error"
    assert result["n_scored_total"] == 8
    assert await _count_scores(session_factory) == 8
    assert await _unscored_count(session_factory) == 0


async def test_concurrent_scoring_jobs_do_not_collide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The 18:15:42 failure: a second scoring job raised "Session is already flushing".

    The standalone 30-minute scoring job and a sweep's tail-call pass
    are two APScheduler job ids calling the same function at once.
    Both runs must complete without a flushing error, and the store
    must hold exactly one score row per resolved forecast -- never
    zero, never two.
    """
    import asyncio

    ForecastScheduler = _scheduler_class()
    async with session_factory() as session:
        for i in range(8):
            await _issue_and_resolve(
                session, _forecast(prediction=100.0 + i), 105.0
            )

    scheduler = ForecastScheduler(session_factory=session_factory)
    first, second = await asyncio.gather(
        scheduler.forecast_scoring_job(),
        scheduler.forecast_scoring_job(),
    )

    assert first.get("status") != "error"
    assert second.get("status") != "error"
    assert "already flushing" not in str(first.get("error", ""))
    assert "already flushing" not in str(second.get("error", ""))
    assert first["scored"] + second["scored"] == 8
    assert await _count_scores(session_factory) == 8
    assert await _unscored_count(session_factory) == 0


async def test_calibration_and_scoring_run_concurrently(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The 18:15 calibration resolve failures (b5c0a661 + f8921fe7).

    The calibration sweep resolves expired forecasts and the scoring
    job scores resolved ones; at :15/:45 both fire in the same minute.
    They must complete without a flushing error, the resolutions must
    persist, and the scores must persist.
    """
    import asyncio

    ForecastScheduler = _scheduler_class()
    now = datetime.now(UTC)
    async with session_factory() as session:
        # Two already-resolved forecasts for the standalone scoring job.
        for i in range(2):
            await _issue_and_resolve(
                session, _forecast(prediction=100.0 + i), 105.0
            )
        # Two expired ACTIVE forecasts for the calibration sweep to
        # resolve against the synthetic observations (capacity rule:
        # numeric outcome from the observed max in the window).
        for i in range(2):
            expired = _forecast(
                target=CAPACITY_TARGET,
                prediction=200.0 + i,
                as_of=now - timedelta(days=2),
                horizon_hours=24.0,
            )
            await ForecastRepository(session).create(expired)
        await session.commit()

    scheduler = ForecastScheduler(session_factory=session_factory)
    calibration, scoring = await asyncio.gather(
        scheduler.calibration_sweep_job(),
        scheduler.forecast_scoring_job(),
    )

    assert calibration["resolved_count"] == 2
    assert "brier_score" in calibration
    assert scoring.get("status") != "error"
    assert "already flushing" not in str(scoring.get("error", ""))
    # The two pre-resolved forecasts plus the two the sweep resolved.
    assert await _count_scores(session_factory) == 4
    assert await _unscored_count(session_factory) == 0


async def test_provider_refresh_and_scoring_run_concurrently(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The 18:15 provider refresh failures (vyralx + intelx targets).

    The universe provider refresh commits per target while the scoring
    job scores. On the old shared session the refresh's commit collided
    with the scoring flush. Both jobs must complete, and every provider
    target's forecast -- vyralx and intelx included -- must persist.
    """
    import asyncio

    ForecastScheduler = _scheduler_class()
    async with session_factory() as session:
        for i in range(4):
            await _issue_and_resolve(
                session, _forecast(prediction=100.0 + i), 105.0
            )

    scheduler = ForecastScheduler(session_factory=session_factory)
    refreshed, scoring = await asyncio.gather(
        scheduler.universe_provider_refresh_job(),
        scheduler.forecast_scoring_job(),
    )

    assert len(refreshed) == 3
    assert {f.target for f in refreshed} == {
        "vyralx:trends:topic_volume_24h",
        "intelx:research:finding_volume_24h",
        "friday:fleet:forecast_demand_24h",
    }
    assert scoring.get("status") != "error"
    assert await _count_scores(session_factory) == 4
    # Every provider forecast persisted on its own commit.
    async with session_factory() as session:
        repo = ForecastRepository(session)
        for target in (
            "vyralx:trends:topic_volume_24h",
            "intelx:research:finding_volume_24h",
            "friday:fleet:forecast_demand_24h",
        ):
            assert len(await repo.list_by_target(target)) == 1


class _RecordingEmitter:
    """Emitter that asserts the forecast exists in the store at emit time.

    The FUT-023 section 6.1 failure: the 17:15 telemetry cycle emitted
    a forecast_updated event for a forecast that was never persisted.
    An emit must only happen after the commit, so a fresh session must
    already see the row when the event goes out.
    """

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory
        self.events: list[ForecastEvent] = []
        self.seen_in_store_at_emit: list[bool] = []

    async def emit(self, event: ForecastEvent) -> None:
        async with self.factory() as session:
            row = await ForecastRepository(session).get(event.forecast_id)
        self.seen_in_store_at_emit.append(row is not None)
        self.events.append(event)


async def test_telemetry_refresh_commits_before_emitting(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The 17:15 phantom event: forecast_updated for a forecast the store never held."""
    ForecastScheduler = _scheduler_class()
    now = datetime.now(UTC)
    async with session_factory() as session:
        prev = _forecast(prediction=100.0, probability=0.5, as_of=now - timedelta(hours=1))
        await ForecastRepository(session).create(prev)
        await session.commit()

    emitter = _RecordingEmitter(session_factory)
    scheduler = ForecastScheduler(
        session_factory=session_factory, emitter=emitter  # type: ignore[arg-type]
    )
    scheduler.subscriptions = [
        ForecastSubscription(target=TARGET),
    ]
    scheduler.sync_dynamic_trading_subscriptions = AsyncMock(return_value=[])

    new_forecast = _forecast(prediction=1000.0, probability=0.5, as_of=now)
    scheduler.pipeline = AsyncMock()
    scheduler.pipeline.run.return_value = SimpleNamespace(forecast=new_forecast)

    refreshed = await scheduler.forecast_refresh_job()

    assert len(refreshed) == 1
    assert refreshed[0].prediction == 1000.0
    # The change is far above the suppression delta, so the event fired.
    assert len(emitter.events) == 1
    # ... and at emit time the forecast was already in the store.
    assert emitter.seen_in_store_at_emit == [True]
    async with session_factory() as session:
        row = await ForecastRepository(session).get(new_forecast.forecast_id)
    assert row is not None
    assert row.prediction == 1000.0
