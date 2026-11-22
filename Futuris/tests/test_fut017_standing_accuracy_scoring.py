"""TASK-FUT-017 tests: standing per-cycle accuracy scoring + fit-cost cap.

FUT-016 grades the backlog once; this task makes grading permanent and
caps the fit cost that caused the OOM saga (MemoryMax raised 180M to
512M on a 956MB box). Pinned here, on a throwaway SQLite schema built
from the real models:

* fit-cost estimates: ordering, scaling with rows/features/exogenous
  width, and the conservative default for unlisted adapters;
* the shortlist: rank order kept, expensive candidates dropped first,
  at least one (cheapest) candidate always kept, the cap recorded;
* selection: a tiny budget drops the expensive fits before any fit
  starts and says so (``fit_cost_cap``), using fake adapters so the
  test runs where statsforecast is not installed (CI has no
  statsforecast on its test surface);
* the pipeline final refit: a winner whose full-data refit exceeds the
  budget is refit as naive instead, with the cap in the model version
  and the metadata;
* the rolling hit-rate: pure window math plus end-to-end through the
  tracker store, including the thin-window honesty rule;
* the scheduler: the lifecycle sweep scores matured forecasts in the
  same cycle, and the scoring summary is recorded per cycle;
* the status surface: ``check_accuracy`` reports the rolling hit-rate
  as a subsystem, ``unknown`` (never a verdict) while data is thin.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from futuris.core.enums import ConfidenceLevel, EvidenceClass, ResolutionMethod
from futuris.core.lifecycle import LifecycleSweepReport
from futuris.core.pipeline import ModelingInput, ModelingStage
from futuris.core.schemas import Forecast, Outcome
from futuris.features.normalize import DataQualityReport
from futuris.infra.scheduler import ForecastScheduler
from futuris.infra.self_healing import SelfHealingSupervisor
from futuris.models.base import ModelPrediction, PredictionIntervals
from futuris.models.fit_cost import (
    DEFAULT_FIT_MEMORY_BUDGET_MB,
    estimate_fit_memory_mb,
    final_fit_within_budget,
    resolve_fit_memory_budget,
    shortlist_candidates,
)
from futuris.services.forecast_tracker import (
    ForecastTracker,
    build_rolling_hit_rate,
)
from futuris.storage import db as storage_db
from futuris.storage.models import Base, ForecastScoreModel
from futuris.storage.repositories import ForecastRepository, OutcomeRepository
from futuris.storage.score_repository import ForecastScoreRepository

AS_OF = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
TARGET = "trading:BTCUSDT:price_variance_24h"
ROUTER_RANKED = [
    "mean_ensemble",
    "auto_ets",
    "seasonal_naive",
    "drift",
    "auto_arima",
    "naive",
]


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
        predictive_distribution={"p5": 90.0, "p50": 100.0, "p95": 110.0},
        evidence_class=evidence,
        evidence_source="fut017 test fixture",
    )


def _outcome(forecast: Forecast, observed: float | None) -> Outcome:
    return Outcome(
        outcome_id=uuid4(),
        forecast_id=forecast.forecast_id,
        observed_value=observed,
        event_occurred=None,
        resolved_at=AS_OF + timedelta(hours=25),
        resolution_method=ResolutionMethod.AUTOMATIC,
        ambiguity_note=None,
        resolution_rule_version="fut017-test:v1",
    )


async def _issue_and_resolve(
    session: AsyncSession, forecast: Forecast, observed: float
) -> None:
    await ForecastRepository(session).create(forecast)
    await OutcomeRepository(session).record_outcome(_outcome(forecast, observed))
    await session.commit()


def _score_row(*, scored_at: datetime, hit: bool) -> ForecastScoreModel:
    return ForecastScoreModel(
        score_id=uuid4(),
        forecast_id=uuid4(),
        target=TARGET,
        model_version="naive@v1:test",
        evidence_class="live",
        confidence="medium",
        as_of=scored_at - timedelta(hours=25),
        horizon_seconds=24 * 3600.0,
        expires_at=scored_at - timedelta(hours=1),
        prediction=100.0,
        range_lower=90.0,
        range_upper=110.0,
        nominal_level=0.90,
        nominal_level_source="adapter_default",
        observed_value=100.0 if hit else 130.0,
        resolved_at=scored_at - timedelta(hours=1),
        signed_error=0.0 if hit else 30.0,
        abs_error=0.0 if hit else 30.0,
        pct_error=0.0 if hit else 30.0 / 130.0 * 100.0,
        interval_hit=hit,
        interval_width=20.0,
        winkler=20.0,
        scored_at=scored_at,
    )


class _FakeAdapter:
    """Minimal adapter standing in for a statsforecast backend.

    CI has no statsforecast on its test surface, so the selection tests
    run against these: they fit (record the last value) and predict a
    flat line at it. Every fake scores identically, so the winner is
    the first kept candidate -- which is exactly what the shortlist
    tests need to observe.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._last = 100.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> dict:
        return {}

    def get_config_hash(self) -> str:
        return "test"

    def fit(self, x, y, as_of=None) -> "_FakeAdapter":
        values = list(y)
        self._last = float(values[-1]) if values else 100.0
        return self

    def predict(
        self,
        h: int | None = None,
        horizon: int | None = None,
        capacity_threshold=None,
        probability_method: str = "empirical",
        future_x=None,
    ) -> ModelPrediction:
        steps = int(h if h is not None else (horizon if horizon is not None else 1))
        return ModelPrediction(
            point_forecast=[self._last] * steps,
            intervals=[
                PredictionIntervals(lower=90.0, central=100.0, upper=110.0)
                for _ in range(steps)
            ],
            range_lower=90.0,
            range_upper=110.0,
            central_estimate=self._last,
            exceedance_probability=None,
        )


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend statsforecast is installed, with fake adapters."""
    import futuris.models.selection as selection
    from futuris.models import registry as registry_module

    monkeypatch.setattr(selection, "STATSFORECAST_AVAILABLE", True)
    monkeypatch.setattr(
        registry_module.model_registry,
        "get_adapter",
        lambda name, config=None: _FakeAdapter(name),
    )
    monkeypatch.setattr(
        registry_module.model_registry,
        "get_version_string",
        lambda adapter: f"{adapter.name}@v1:test",
    )


def _quality_report() -> DataQualityReport:
    return DataQualityReport(
        total_raw_points=4032,
        cleaned_points=4032,
        duplicates_dropped=0,
        gaps_filled_under_15m=0,
        long_gaps_count=0,
        anomalies_clipped=0,
        coverage_percentage=100.0,
    )


# ---------------------------------------------------------------------------
# Fit-cost estimates
# ---------------------------------------------------------------------------


def test_estimate_ordering_and_scaling() -> None:
    rows, cols = 4032, 10
    naive = estimate_fit_memory_mb("naive", rows, cols)
    ets = estimate_fit_memory_mb("auto_ets", rows, cols)
    ensemble = estimate_fit_memory_mb("mean_ensemble", rows, cols)
    arima = estimate_fit_memory_mb("auto_arima", rows, cols, n_exog=cols)
    assert naive < ets < ensemble < arima
    # Linear in rows: doubling the history doubles the variable part.
    assert estimate_fit_memory_mb("auto_ets", 2 * rows, cols) == pytest.approx(
        0.5 + 2 * (ets - 0.5)
    )
    # AutoARIMA grows with exogenous width; the other families ignore it.
    assert estimate_fit_memory_mb("auto_arima", rows, cols, n_exog=0) < arima
    assert estimate_fit_memory_mb("auto_ets", rows, cols, n_exog=cols) == ets


def test_estimate_unknown_adapter_is_conservative() -> None:
    # An unlisted adapter is assumed expensive until it proves otherwise:
    # the AutoARIMA working-copy bound, without AutoARIMA's extra
    # stepwise-search overhead (which belongs to the search, not the fit).
    frame_mb = 4032 * (1 + 10) * 8.0 / 1_000_000.0
    assert estimate_fit_memory_mb("garch_volatility", 4032, 10) == pytest.approx(
        0.5 + frame_mb * 48.0
    )
    assert estimate_fit_memory_mb(
        "garch_volatility", 4032, 10
    ) == estimate_fit_memory_mb("some_future_adapter", 4032, 10)
    with pytest.raises(ValueError):
        estimate_fit_memory_mb("naive", -1, 10)
    with pytest.raises(ValueError):
        estimate_fit_memory_mb("naive", 100, -2)


def test_resolve_fit_memory_budget_defaults_to_256() -> None:
    assert resolve_fit_memory_budget(128.0) == 128.0
    # No explicit budget: the configured cap (256MB by default).
    assert resolve_fit_memory_budget(None) == DEFAULT_FIT_MEMORY_BUDGET_MB == 256.0


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------


def test_shortlist_keeps_everything_under_default_budget() -> None:
    # The production frame (14d lookback, 5m grid, ~10 features) fits
    # the whole routed set in ~39MB -- the cap does not bite at rest.
    result = shortlist_candidates(
        ROUTER_RANKED, n_rows=4032, n_features=10, budget_mb=256.0, n_exog=10
    )
    assert result.kept == ROUTER_RANKED
    assert result.dropped == []
    assert result.capped is False
    assert result.total_kept_mb == pytest.approx(38.61088)


def test_shortlist_drops_expensive_first_and_keeps_a_baseline() -> None:
    result = shortlist_candidates(
        ROUTER_RANKED, n_rows=4032, n_features=10, budget_mb=2.0, n_exog=10
    )
    assert result.capped is True
    assert result.kept == ["seasonal_naive"]
    assert "auto_arima" in result.dropped
    assert "mean_ensemble" in result.dropped
    assert result.total_kept_mb <= 2.0
    meta = result.as_metadata()
    assert meta["fit_memory_budget_mb"] == 2.0
    assert meta["fit_cost_capped"] is True
    assert "auto_arima" in meta["candidates_dropped_by_fit_cost_cap"]


def test_shortlist_never_keeps_nothing() -> None:
    # A budget smaller than even the cheapest single fit still keeps
    # the cheapest baseline: the frame is already in memory, so a cheap
    # fit cannot be what OOMs the process.
    result = shortlist_candidates(
        ROUTER_RANKED, n_rows=4032, n_features=10, budget_mb=0.5, n_exog=10
    )
    assert len(result.kept) == 1
    assert result.kept[0] in {"naive", "drift", "seasonal_naive"}
    with pytest.raises(ValueError):
        shortlist_candidates([], n_rows=100, n_features=1, budget_mb=256.0)
    with pytest.raises(ValueError):
        shortlist_candidates(["naive"], n_rows=100, n_features=1, budget_mb=0.0)


def test_final_fit_within_budget() -> None:
    within, _ = final_fit_within_budget("auto_arima", 4032, 10, 256.0, n_exog=10)
    assert within is True
    within, estimate = final_fit_within_budget(
        "auto_arima", 500_000, 10, 256.0, n_exog=10
    )
    assert within is False
    assert estimate > 256.0
    # Cheap baselines are never refused: their incremental memory over
    # the already-loaded frame is about one series copy.
    within, _ = final_fit_within_budget("naive", 500_000, 10, 1.0)
    assert within is True


# ---------------------------------------------------------------------------
# Selection under the cap (fake backend: no statsforecast needed)
# ---------------------------------------------------------------------------


def _selection_frames(n_rows: int = 4032, n_features: int = 10):
    index = pd.date_range("2026-10-18", periods=n_rows, freq="5min", tz=UTC)
    x_train = pd.DataFrame(
        {f"f{i}": np.full(n_rows, 1.0) for i in range(n_features)}, index=index
    )
    y_train = pd.Series(np.full(n_rows, 100.0), index=index)
    y_val = np.full(24, 100.0)
    return x_train, y_train, y_val


def test_selection_drops_expensive_candidates_under_tiny_budget(
    fake_backend: None,
) -> None:
    from futuris.models.selection import select_best_adapter

    x_train, y_train, y_val = _selection_frames()
    outcome = select_best_adapter(
        ROUTER_RANKED,
        x_train=x_train,
        y_train=y_train,
        y_val=y_val,
        as_of=AS_OF,
        val_steps=24,
        step_minutes=5,
        memory_budget_mb=2.0,
    )
    assert outcome.adapter.name == "seasonal_naive"
    assert outcome.fit_cost_capped is True
    assert outcome.fit_cost_budget_mb == 2.0
    assert "auto_arima" in outcome.skipped
    assert "mean_ensemble" in outcome.skipped
    assert outcome.degraded_reason == "fit_cost_cap"
    assert outcome.degraded is True
    assert set(outcome.scores) == {"seasonal_naive"}
    meta = outcome.metadata()
    assert meta["fit_memory_budget_mb"] == 2.0
    assert meta["fit_cost_capped"] is True
    assert "auto_arima" in meta["candidates_skipped"]


def test_selection_keeps_everything_under_default_budget(fake_backend: None) -> None:
    from futuris.models.selection import select_best_adapter

    x_train, y_train, y_val = _selection_frames()
    outcome = select_best_adapter(
        ROUTER_RANKED,
        x_train=x_train,
        y_train=y_train,
        y_val=y_val,
        as_of=AS_OF,
        val_steps=24,
        step_minutes=5,
    )
    assert outcome.fit_cost_capped is False
    assert outcome.skipped == []
    assert set(outcome.scores) == set(ROUTER_RANKED)
    assert outcome.metadata()["fit_memory_budget_mb"] == 256.0


# ---------------------------------------------------------------------------
# Pipeline final-refit cap (fake backend)
# ---------------------------------------------------------------------------


def test_pipeline_final_refit_falls_back_to_naive_when_capped(
    fake_backend: None,
) -> None:
    """The winner fits on the train split but not on the full frame.

    With a 24h horizon on a 5-minute grid the validation split is 288
    steps, so the backtest trains on 3744 rows while the refit trains
    on 4032. Budget 5.30MB sits between mean_ensemble's backtest
    estimate (5.11MB, kept) and its full-data refit estimate (5.47MB,
    refused), so the pipeline refits naive and says so in the version
    and the metadata.
    """
    from futuris.models.fit_cost import estimate_fit_memory_mb

    n_rows, n_features = 4032, 10
    train_rows = n_rows - 288
    assert estimate_fit_memory_mb("mean_ensemble", train_rows, n_features) < 5.30
    assert estimate_fit_memory_mb("mean_ensemble", n_rows, n_features) > 5.30

    index = pd.date_range("2026-10-18", periods=n_rows, freq="5min", tz=UTC)
    features_df = pd.DataFrame(
        {"value": np.full(n_rows, 100.0)}
        | {f"f{i}": np.full(n_rows, 1.0) for i in range(n_features)},
        index=index,
    )
    stage = ModelingStage()
    out = stage._fit_and_predict(
        ModelingInput(
            features_df=features_df,
            signal_set=SimpleNamespace(
                grid_step_minutes=5, quality_report=_quality_report()
            ),
            target=TARGET,
            as_of=AS_OF,
            horizon=timedelta(hours=24),
            capacity_threshold=4000.0,
            memory_budget_mb=5.30,
        ),
        evidence_ref=SimpleNamespace(evidence_id=uuid4()),
    )
    assert out.model_version.startswith("naive@v1:test")
    assert out.model_version.endswith(":final_fit_cost_capped")
    assert out.selection_metadata["final_fit_cost_capped"] is True
    assert out.selection_metadata["final_fit_fallback_adapter"] == "naive"
    assert out.selection_metadata["final_fit_estimate_mb"] == pytest.approx(
        estimate_fit_memory_mb("mean_ensemble", n_rows, n_features)
    )
    assert out.prediction.central_estimate == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Rolling hit-rate
# ---------------------------------------------------------------------------


def test_rolling_hit_rate_window_math() -> None:
    newest = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    rows = [
        _score_row(scored_at=newest - timedelta(days=1), hit=True)
        for _ in range(30)
    ]
    rows += [
        _score_row(scored_at=newest - timedelta(days=1), hit=False)
        for _ in range(10)
    ]
    # Outside the 30-day window: must not count, however many there are.
    rows += [
        _score_row(scored_at=newest - timedelta(days=40), hit=False)
        for _ in range(50)
    ]
    result = build_rolling_hit_rate(rows, as_of=newest)
    assert result["status"] == "measured"
    assert result["n_in_window"] == 40
    assert result["n_scored_total"] == 90
    assert result["hit_rate"] == pytest.approx(0.75)


def test_rolling_hit_rate_is_insufficient_below_min_samples() -> None:
    newest = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    rows = [_score_row(scored_at=newest, hit=True) for _ in range(5)]
    result = build_rolling_hit_rate(rows, as_of=newest)
    assert result["status"] == "insufficient_data"
    assert result["hit_rate"] is None
    assert result["n_in_window"] == 5
    assert build_rolling_hit_rate([])["status"] == "insufficient_data"


async def test_tracker_rolling_hit_rate_end_to_end(db_session: AsyncSession) -> None:
    for i in range(40):
        await _issue_and_resolve(db_session, _forecast(), 100.0 if i < 30 else 130.0)
    tracker = ForecastTracker(db_session)
    await tracker.score_resolved()

    hit_rate = await tracker.rolling_hit_rate()
    assert hit_rate["status"] == "measured"
    assert hit_rate["hit_rate"] == pytest.approx(0.75)
    assert hit_rate["n_in_window"] == 40
    assert hit_rate["n_scored_total"] == 40
    assert hit_rate["rows_read"] == 40

    report = await tracker.calibration_report()
    assert report["rolling_hit_rate_30d"]["hit_rate"] == pytest.approx(0.75)
    assert report["rolling_hit_rate_30d"]["status"] == "measured"


async def test_tracker_rolling_hit_rate_thin_window(db_session: AsyncSession) -> None:
    for _ in range(5):
        await _issue_and_resolve(db_session, _forecast(), 100.0)
    tracker = ForecastTracker(db_session)
    await tracker.score_resolved()
    hit_rate = await tracker.rolling_hit_rate()
    assert hit_rate["status"] == "insufficient_data"
    assert hit_rate["hit_rate"] is None


# ---------------------------------------------------------------------------
# Scheduler: scoring in the same cycle that matures forecasts
# ---------------------------------------------------------------------------


async def test_lifecycle_sweep_scores_matured_forecasts_in_cycle(
    db_session: AsyncSession,
) -> None:
    pytest.importorskip("apscheduler")
    await _issue_and_resolve(db_session, _forecast(), 105.0)

    sweep_report = LifecycleSweepReport(
        expired_count=0,
        resolved_count=1,
        invalidated_count=0,
        reassessment_due_count=0,
        outcomes=[],
    )
    lifecycle_manager = AsyncMock()
    lifecycle_manager.run_lifecycle_sweep.return_value = sweep_report
    scheduler = ForecastScheduler(
        outcome_repo=OutcomeRepository(db_session),
        lifecycle_manager=lifecycle_manager,
    )
    # The sweep fetches observations from the scheduler connector; the
    # synthetic default works offline.
    report = await scheduler.lifecycle_sweep_job()
    assert report is sweep_report

    row = await ForecastScoreRepository(db_session).get_for_forecast(
        (await ForecastRepository(db_session).list_by_target(TARGET))[0].forecast_id
    )
    assert row is not None
    assert row.observed_value == pytest.approx(105.0)
    assert scheduler.last_cycle_scoring["source"] == "lifecycle_sweep_job"
    assert scheduler.last_cycle_scoring["scored"] == 1
    assert scheduler.last_scoring_summary["n_scored_total"] == 1
    assert scheduler.last_scoring_summary["rolling_hit_rate_30d"]["status"] in (
        "measured",
        "insufficient_data",
    )


async def test_scoring_job_records_per_cycle_summary(
    db_session: AsyncSession,
) -> None:
    pytest.importorskip("apscheduler")
    await _issue_and_resolve(db_session, _forecast(), 105.0)
    scheduler = ForecastScheduler(outcome_repo=OutcomeRepository(db_session))
    result = await scheduler.forecast_scoring_job()
    assert result["scored"] == 1
    assert scheduler.last_scoring_summary["scored"] == 1
    assert "scored_at" in scheduler.last_scoring_summary
    assert "rolling_hit_rate_30d" in result


async def test_cycle_scoring_never_breaks_the_cycle() -> None:
    pytest.importorskip("apscheduler")
    scheduler = ForecastScheduler(outcome_repo=None)
    summary = await scheduler._score_matured_forecasts(source="lifecycle_sweep_job")
    assert summary["status"] == "no_storage"
    assert summary["source"] == "lifecycle_sweep_job"


async def test_calibration_sweep_without_resolutions_does_not_score(
    db_session: AsyncSession,
) -> None:
    pytest.importorskip("apscheduler")
    scheduler = ForecastScheduler(outcome_repo=OutcomeRepository(db_session))
    metrics = await scheduler.calibration_sweep_job()
    assert metrics["resolved_count"] == 0
    assert scheduler.last_cycle_scoring == {}


# ---------------------------------------------------------------------------
# Status surface: rolling hit-rate as a subsystem
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def status_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncEngine, None]:
    """Point the process-wide storage at a throwaway SQLite database.

    Self-contained (not the ``Futuris/tests/conftest.py`` fixture): the
    CI invocation runs with ``--confcutdir=Futuris/tests/infra``, under
    which that conftest does not load, so a status test that relied on
    it would read the real (dummy Oracle) engine instead of a test
    database. The status check resolves the factory at call time, so
    patching the module attributes here is what it reads.
    """
    from sqlalchemy import create_engine as create_sync_engine

    path = tmp_path / "status_probe.db"
    sync_engine = create_sync_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(storage_db, "engine", engine)
    monkeypatch.setattr(
        storage_db,
        "async_session_factory",
        async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False),
    )
    yield engine
    await engine.dispose()


async def _seed_scores(n: int, hits: int) -> None:
    async with storage_db.async_session_factory() as session:
        for i in range(n):
            forecast = _forecast()
            await ForecastRepository(session).create(forecast)
            await OutcomeRepository(session).record_outcome(
                _outcome(forecast, 100.0 if i < hits else 130.0)
            )
        await session.commit()
        await ForecastTracker(session).score_resolved()
        await session.commit()


async def test_status_accuracy_unknown_while_thin(
    status_storage: AsyncEngine,
) -> None:
    supervisor = SelfHealingSupervisor()
    check = await supervisor.check_accuracy()
    assert check.name == "forecast_accuracy"
    assert check.state == "unknown"
    assert "insufficient_data" in check.detail
    assert check.data["n_scored_total"] == 0


async def test_status_accuracy_measured_once_enough_scored(
    status_storage: AsyncEngine,
) -> None:
    await _seed_scores(40, 30)
    supervisor = SelfHealingSupervisor()
    check = await supervisor.check_accuracy()
    assert check.name == "forecast_accuracy"
    assert check.state == "ok"
    assert check.data["hit_rate"] == pytest.approx(0.75)
    assert check.data["n_in_window"] == 40
    assert "0.750" in check.detail
