"""TASK-FUT-006 tests: the live forecast-vs-actual tracker.

The tracker is the scoring layer between Futuris's two existing stores:
forecasts are issued into ``forecasts`` (``ForecastRepository.create``)
and resolved into ``outcomes`` (``OutcomeRepository.record_outcome``, as
the calibration sweep does). These tests pin, end to end on a throwaway
SQLite schema built from the real models:

* per-forecast scoring math (error, interval hit, Winkler) against
  hand-computed values, using the same definitions as TASK-FUT-004's
  offline harness;
* nominal-level derivation (predictive-distribution percentiles, else the
  adapters' documented 0.90, always with its source recorded);
* the honesty contract: event-only outcomes are skipped (never zero
  error), unscored forecasts are absent (never substituted actuals), and
  the calibration report says ``insufficient_data`` with null metrics
  below the minimum sample;
* calibration measurement: a synthetic population whose nominal-90%
  intervals actually cover 80% of actuals must report coverage 0.80, a
  -0.10 gap, and an ``overconfident`` verdict;
* idempotency (a forecast is scored exactly once) and provenance
  separation (evidence classes aggregate separately).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from futuris.core.enums import ConfidenceLevel, EvidenceClass, ResolutionMethod
from futuris.core.schemas import Forecast, Outcome
from futuris.services.forecast_tracker import (
    ForecastTracker,
    build_calibration_report,
    derive_nominal_level,
    score_forecast,
    winkler_score,
)
from futuris.storage.models import Base, ForecastScoreModel
from futuris.storage.repositories import ForecastRepository, OutcomeRepository
from futuris.storage.score_repository import ForecastScoreRepository

AS_OF = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
TARGET = "trading:BTCUSDT:price_variance_24h"


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
    target: str = TARGET,
    prediction: float = 100.0,
    lower: float = 90.0,
    upper: float = 110.0,
    dist: dict | None = None,
    evidence: EvidenceClass = EvidenceClass.LIVE,
) -> Forecast:
    return Forecast(
        target=target,
        as_of=AS_OF,
        horizon=timedelta(hours=24),
        expires_at=AS_OF + timedelta(hours=24),
        prediction=prediction,
        range_lower=lower,
        range_upper=upper,
        probability=None,
        confidence=ConfidenceLevel.MEDIUM,
        model_version="statsforecast.Naive:v1.0",
        review_at=AS_OF + timedelta(hours=24),
        predictive_distribution=dist or {},
        evidence_class=evidence,
        evidence_source="fut006 test fixture",
    )


def _outcome(
    forecast: Forecast,
    observed: float | None,
    *,
    event: bool | None = None,
) -> Outcome:
    return Outcome(
        outcome_id=uuid4(),
        forecast_id=forecast.forecast_id,
        observed_value=observed,
        event_occurred=event,
        resolved_at=AS_OF + timedelta(hours=25),
        resolution_method=ResolutionMethod.AUTOMATIC,
        ambiguity_note=None,
        resolution_rule_version="fut006-test:v1",
    )


async def _issue_and_resolve(
    session: AsyncSession, forecast: Forecast, observed: float | None, **kw
) -> None:
    await ForecastRepository(session).create(forecast)
    await OutcomeRepository(session).record_outcome(_outcome(forecast, observed, **kw))
    await session.commit()


# ---------------------------------------------------------------------------
# Pure scoring math
# ---------------------------------------------------------------------------


def test_winkler_score_matches_harness_definition() -> None:
    # Inside: score is exactly the width.
    assert winkler_score(100.0, 90.0, 110.0, 0.90) == pytest.approx(20.0)
    # Below by 10 at level 0.90 (alpha 0.10): 20 + (2/0.1)*10 = 220.
    assert winkler_score(80.0, 90.0, 110.0, 0.90) == pytest.approx(220.0)
    # Above by 5 at level 0.80 (alpha 0.20): 20 + (2/0.2)*5 = 70.
    assert winkler_score(115.0, 90.0, 110.0, 0.80) == pytest.approx(70.0)


def test_derive_nominal_level_sources() -> None:
    assert derive_nominal_level(_forecast(dist={"p5": 90.0, "p95": 110.0})) == (
        0.90,
        "predictive_distribution:p5/p95",
    )
    assert derive_nominal_level(_forecast(dist={"p10": 92.0, "p90": 108.0})) == (
        0.80,
        "predictive_distribution:p10/p90",
    )
    # Widest recorded pair wins when several are present.
    level, source = derive_nominal_level(
        _forecast(dist={"p5": 90.0, "p95": 110.0, "p10": 92.0, "p90": 108.0})
    )
    assert (level, source) == (0.90, "predictive_distribution:p5/p95")
    # Nothing recorded: the adapters' documented nominal level, labelled.
    assert derive_nominal_level(_forecast()) == (0.90, "adapter_default")


def test_score_forecast_math_and_event_only_skip() -> None:
    forecast = _forecast(dist={"p5": 90.0, "p95": 110.0})
    score = score_forecast(forecast, _outcome(forecast, 130.0))
    assert score is not None
    assert score.signed_error == pytest.approx(30.0)
    assert score.abs_error == pytest.approx(30.0)
    assert score.pct_error == pytest.approx(30.0 / 130.0 * 100.0)
    assert score.interval_hit is False
    assert score.interval_width == pytest.approx(20.0)
    assert score.winkler == pytest.approx(20.0 + (2.0 / 0.1) * 20.0)
    assert score.nominal_level == 0.90
    assert score.horizon_seconds == 24 * 3600.0

    # Event-only outcome: not scorable, and NOT a zero-error score.
    assert score_forecast(forecast, _outcome(forecast, None, event=True)) is None


# ---------------------------------------------------------------------------
# End-to-end: issue -> resolve -> score -> report
# ---------------------------------------------------------------------------


async def test_scoring_sweep_scores_once_and_skips_event_only(
    db_session: AsyncSession,
) -> None:
    numeric = _forecast()
    event_only = _forecast(target="service:checkout:capacity_exceedance_24h")
    await _issue_and_resolve(db_session, numeric, 95.0)
    await _issue_and_resolve(db_session, event_only, None, event=True)

    tracker = ForecastTracker(db_session)
    first = await tracker.score_resolved()
    # The event-only outcome never enters the work queue (it can never be
    # scored numerically); it is reported as a state count instead.
    assert first == {
        "considered": 1,
        "scored": 1,
        "skipped_no_numeric_actual": 0,
        "event_only_resolved": 1,
    }

    row = await ForecastScoreRepository(db_session).get_for_forecast(
        numeric.forecast_id
    )
    assert row is not None
    assert row.observed_value == pytest.approx(95.0)
    assert row.signed_error == pytest.approx(-5.0)
    assert row.interval_hit is True
    assert row.evidence_class == "live"

    # Idempotent: a second sweep finds nothing left to score.
    second = await tracker.score_resolved()
    assert second == {
        "considered": 0,
        "scored": 0,
        "skipped_no_numeric_actual": 0,
        "event_only_resolved": 1,
    }


async def test_calibration_report_measures_coverage_gap(
    db_session: AsyncSession,
) -> None:
    # 100 forecasts, nominal-90% intervals [90, 110] around 100; exactly 80
    # actuals land inside, 20 land at 130. Hand-computed expectations:
    # coverage_90 = 0.80, gap = -0.10, MAE = 6.0, mean Winkler = 100.0.
    dist = {"p5": 90.0, "p50": 100.0, "p95": 110.0}
    for i in range(100):
        forecast = _forecast(dist=dist)
        await _issue_and_resolve(db_session, forecast, 100.0 if i < 80 else 130.0)

    tracker = ForecastTracker(db_session)
    result = await tracker.score_resolved()
    assert result["scored"] == 100

    report = await tracker.calibration_report()
    assert report["status"] == "measured"
    assert report["n_scored"] == 100
    metrics = report["metrics"]
    assert metrics["mae"] == pytest.approx(6.0)
    assert metrics["rmse"] == pytest.approx((20 * 900.0 / 100) ** 0.5)
    assert metrics["coverage_90"] == pytest.approx(0.80)
    assert metrics["coverage_gap_vs_nominal"] == pytest.approx(-0.10)
    assert metrics["mean_interval_width"] == pytest.approx(20.0)
    assert metrics["winkler_90"] == pytest.approx(100.0)
    assert report["verdict"] == "overconfident"
    assert report["by_nominal_level"]["0.90"]["n"] == 100
    assert report["by_target"][TARGET]["coverage_90"] == pytest.approx(0.80)


async def test_report_is_insufficient_data_below_min_samples(
    db_session: AsyncSession,
) -> None:
    for _ in range(5):
        await _issue_and_resolve(db_session, _forecast(), 100.0)
    tracker = ForecastTracker(db_session)
    await tracker.score_resolved()

    report = await tracker.calibration_report()
    assert report["status"] == "insufficient_data"
    assert report["n_scored"] == 5
    assert report["metrics"] is None
    assert report["verdict"] is None


async def test_report_separates_evidence_classes(db_session: AsyncSession) -> None:
    for _ in range(40):
        await _issue_and_resolve(db_session, _forecast(), 100.0)
    for _ in range(40):
        await _issue_and_resolve(
            db_session, _forecast(evidence=EvidenceClass.SYNTHETIC), 100.0
        )
    tracker = ForecastTracker(db_session)
    await tracker.score_resolved()

    report = await tracker.calibration_report()
    assert report["n_scored"] == 80
    assert set(report["by_evidence_class"]) == {"live", "synthetic"}

    live_only = await tracker.calibration_report(evidence_class="live")
    assert live_only["n_scored"] == 40
    assert live_only["status"] == "measured"


def test_empty_report_is_honest() -> None:
    report = build_calibration_report([])
    assert report["status"] == "insufficient_data"
    assert report["n_scored"] == 0
    assert report["metrics"] is None


# ---------------------------------------------------------------------------
# Scheduler wiring (runs where apscheduler is installed, i.e. CI/production)
# ---------------------------------------------------------------------------


async def test_scoring_job_registered_and_runs(db_session: AsyncSession) -> None:
    pytest.importorskip("apscheduler")
    from futuris.infra.scheduler import ForecastScheduler

    await _issue_and_resolve(db_session, _forecast(), 105.0)
    scheduler = ForecastScheduler(outcome_repo=OutcomeRepository(db_session))

    result = await scheduler.forecast_scoring_job()
    assert result["scored"] == 1
    assert result["n_scored_total"] == 1

    scheduler.start()
    try:
        job_ids = {job.id for job in scheduler.scheduler.get_jobs()}
        assert "forecast_scoring_job" in job_ids
    finally:
        await scheduler.shutdown()
