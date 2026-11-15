"""TASK-FUT-010 regression tests: BacktestEngine must never grade a forecast
against itself.

The pre-fix engine substituted the forecast's own prediction as the actual
whenever no observation existed at the forecast's expiry
(``actual_val = f.prediction``), fabricating a perfect zero-error sample —
and persisted it as a real Outcome. These tests construct exactly that
failure (forecast present, actual missing) and pin the honest behaviour:

* the origin is UNSCORED — excluded from every metric,
* it is counted and reported (report fields + horizon metrics + summary),
* no Outcome is recorded for it,
* with zero scored origins the metrics are NaN, never 0.0.
"""

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import futuris.evaluation.backtest as backtest_module
from futuris.core.enums import ConfidenceLevel, ForecastStatus
from futuris.core.schemas import Forecast
from futuris.evaluation.backtest import BacktestEngine

START = datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC)
TARGET = "service:checkout:capacity_exceedance_24h"
PREDICTION = 100.0


class _StubEngine:
    """Returns one fixed forecast per origin."""

    async def orchestrate(self, *, target, as_of, horizon, **kwargs):
        return [
            Forecast(
                target=target,
                as_of=as_of,
                horizon=horizon,
                expires_at=as_of + horizon,
                review_at=as_of + timedelta(hours=6),
                prediction=PREDICTION,
                range_lower=90.0,
                range_upper=110.0,
                probability=0.5,
                confidence=ConfidenceLevel.HIGH,
                model_version="stub@v1",
                status=ForecastStatus.ACTIVE,
            )
        ]


class _FakeConnector:
    """Stands in for SyntheticTelemetryConnector; serves preset observations."""

    def __init__(self, observations):
        self._observations = observations

    async def fetch(self, start, end):
        return list(self._observations)


class _RecordingForecastRepo:
    def __init__(self):
        self.created = []

    async def create(self, forecast):
        self.created.append(forecast)


class _RecordingOutcomeRepo:
    def __init__(self):
        self.recorded = []

    async def record_outcome(self, outcome):
        self.recorded.append(outcome)


def _obs(at: datetime, value: float):
    return SimpleNamespace(observed_at=at, value=value)


async def _run(monkeypatch, observations):
    monkeypatch.setattr(
        backtest_module,
        "SyntheticTelemetryConnector",
        lambda seed=None: _FakeConnector(observations),
    )
    forecast_repo = _RecordingForecastRepo()
    outcome_repo = _RecordingOutcomeRepo()
    engine = BacktestEngine(
        forecast_repo=forecast_repo,
        outcome_repo=outcome_repo,
        engine=_StubEngine(),
    )
    report = await engine.run_backtest(
        target=TARGET,
        start_date=START,
        end_date=START + timedelta(days=2),
        stride_hours=24,
        horizon=timedelta(hours=24),
    )
    return report, forecast_repo, outcome_repo


@pytest.mark.asyncio
async def test_missing_actuals_are_unscored_never_self_graded(monkeypatch):
    """All expiries unobserved: the old code reported MAE 0.0 (perfect)
    and persisted three outcomes whose observed value equalled the
    prediction. The fixed engine scores nothing and records nothing."""
    report, forecast_repo, outcome_repo = await _run(monkeypatch, [])

    assert report.total_forecasts == 3
    assert report.scored_forecasts == 0
    assert report.unscored_forecasts == 3

    h24 = report.metrics_by_horizon["24h"]
    assert h24.sample_count == 0
    assert h24.unscored_count == 3
    assert math.isnan(h24.mae)
    assert math.isnan(h24.rmse)
    assert math.isnan(h24.interval_coverage)

    # The forecasts were issued (and persisted as forecasts)…
    assert len(forecast_repo.created) == 3
    # …but NO outcome may be fabricated for an unobserved origin.
    assert outcome_repo.recorded == []
    assert "0 scored" in report.summary_text
    assert "Metrics unavailable" in report.summary_text


@pytest.mark.asyncio
async def test_partial_coverage_scores_only_observed_pairs(monkeypatch):
    """Two of three expiries observed: metrics cover exactly those two
    pairs (MAE = (|130-100| + |80-100|) / 2 = 25.0), the third origin is
    reported unscored, and only two outcomes are recorded."""
    observations = [
        _obs(START + timedelta(days=1), 130.0),
        _obs(START + timedelta(days=2), 80.0),
        # START + 3 days (third origin's expiry) deliberately missing.
    ]
    report, forecast_repo, outcome_repo = await _run(monkeypatch, observations)

    assert report.total_forecasts == 3
    assert report.scored_forecasts == 2
    assert report.unscored_forecasts == 1

    h24 = report.metrics_by_horizon["24h"]
    assert h24.sample_count == 2
    assert h24.unscored_count == 1
    assert h24.mae == pytest.approx(25.0)

    recorded_values = sorted(o.observed_value for o in outcome_repo.recorded)
    assert recorded_values == [80.0, 130.0]
    assert "1 unscored" in report.summary_text


@pytest.mark.asyncio
async def test_full_coverage_behaves_as_before(monkeypatch):
    """All expiries observed: every origin scores, nothing is unscored,
    MAE = (10 + 10 + 0) / 3."""
    observations = [
        _obs(START + timedelta(days=1), 110.0),
        _obs(START + timedelta(days=2), 90.0),
        _obs(START + timedelta(days=3), 100.0),
    ]
    report, forecast_repo, outcome_repo = await _run(monkeypatch, observations)

    assert report.total_forecasts == 3
    assert report.scored_forecasts == 3
    assert report.unscored_forecasts == 0

    h24 = report.metrics_by_horizon["24h"]
    assert h24.sample_count == 3
    assert h24.unscored_count == 0
    # The engine rounds reported metrics to 4 decimals.
    assert h24.mae == pytest.approx(20.0 / 3.0, abs=1e-3)
    assert len(outcome_repo.recorded) == 3
