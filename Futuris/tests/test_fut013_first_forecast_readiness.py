"""Tests for first-forecast readiness after the py3.12 flip (TASK-FUT-013).

Three post-flip blockers that had nothing to do with the missing
statsforecast backend in the live venv:

1. The series providers zero-fill missing days, so a window with NO
   observed events at all arrived as a full-length all-zero series and
   fitted into an ACTIVE forecast of 0.0 labelled LIVE -- an absent
   intake presented as a measured zero. The provider path now refuses
   that window as ``insufficient_data``.
2. ``refresh_missing_within_budget`` treated a stored
   ``insufficient_data`` refusal as a present forecast forever, so the
   pre-flip refusals of the data-path targets (pipeline + provider)
   could never be retried through the matrix backfill once the backend
   landed; and the paced refresh visited targets in registry order,
   where the provider targets sit last, behind targets that can each
   burn a research-peer timeout against the same 15s budget.
3. No scheduled job ever called ``generate_universe_forecast``: the
   scheduler's only forecast job runs the telemetry pipeline over its
   eight subscriptions, so the provider targets had no unattended path
   to a first real forecast at all. ``ForecastScheduler`` now carries a
   ``universe_provider_refresh_job`` registered in ``start()``.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

# futuris.infra.config validates the database backend at import time and
# the scheduler chain imports it; use the same mock-Oracle DSN pattern as
# test_fut004_walkforward_harness.py. Set before any futuris import.
os.environ.setdefault("DATABASE_URL", "oracle+oracledb://mock:mock@localhost:1521/FREE")

from futuris.core.enums import ForecastStatus  # noqa: E402
from futuris.core.universe_domains import UNIVERSE_TARGETS  # noqa: E402
from futuris.core.universe_forecasting import (  # noqa: E402
    generate_universe_forecast,
    refresh_all_within_budget,
    refresh_missing_within_budget,
)
from futuris.models.base import ModelPrediction  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

PROVIDER_TARGET = "intelx:research:finding_volume_24h"
PLAIN_TARGET = "intelx:research:topic_velocity_surge_24h"


# ---------------------------------------------------------------------------
# 1. All-zero provider window refuses
# ---------------------------------------------------------------------------


class _FakeAdapter:
    name = "naive"

    def get_config_hash(self):
        return "testhash"

    def fit(self, x, y, as_of):
        return self

    def predict(
        self, horizon, capacity_threshold=None, probability_method="empirical", future_x=None
    ):
        return ModelPrediction(
            point_forecast=[42.0] * horizon,
            intervals=[],
            range_lower=38.0,
            range_upper=46.0,
            central_estimate=42.0,
            exceedance_probability=0.1,
        )


class _FakeOutcome:
    is_fallback = False

    def __init__(self, adapter):
        self.adapter = adapter

    def metadata(self):
        return {"best_validation_score": 1.5}


def _fetcher_of(values: list[float]):
    async def fetch(_session, *, days, now):
        end = NOW.date() - timedelta(days=1)
        return [
            (end - timedelta(days=len(values) - 1 - i), float(v))
            for i, v in enumerate(values)
        ]

    return fetch


async def test_all_zero_series_refuses_instead_of_live_zero_forecast():
    calls = []

    def selector(*args, **kwargs):
        calls.append(1)
        return _FakeOutcome(_FakeAdapter())

    forecast = await generate_universe_forecast(
        PROVIDER_TARGET,
        session=None,
        skip_intelx=True,
        selector=selector,
        series_fetcher=_fetcher_of([0.0] * 28),
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
    assert "no observed events" in forecast.model_metadata["error"]
    assert calls == [], "an all-zero window must be refused before any fit is attempted"


async def test_series_with_one_observed_event_still_forecasts():
    def selector(*args, **kwargs):
        return _FakeOutcome(_FakeAdapter())

    values = [0.0] * 27 + [3.0]
    forecast = await generate_universe_forecast(
        PROVIDER_TARGET,
        session=None,
        skip_intelx=True,
        selector=selector,
        series_fetcher=_fetcher_of(values),
    )
    assert forecast.status is ForecastStatus.ACTIVE
    assert forecast.prediction == 42.0


# ---------------------------------------------------------------------------
# 2. Refresh pacing: data-path targets first; stale refusals retried
# ---------------------------------------------------------------------------


def _forecast_stub(target: str, status: ForecastStatus):
    from uuid import uuid4

    from futuris.core.enums import ConfidenceLevel
    from futuris.core.schemas import Forecast

    return Forecast(
        forecast_id=uuid4(),
        target=target,
        as_of=NOW,
        horizon=timedelta(hours=24),
        expires_at=NOW + timedelta(hours=24),
        review_at=NOW + timedelta(hours=6),
        prediction=1.0,
        range_lower=0.0,
        range_upper=2.0,
        probability=None,
        confidence=ConfidenceLevel.LOW,
        drivers=[],
        evidence=[],
        assumptions=[],
        model_version="test",
        status=status,
    )


def _recording_generate(monkeypatch, record: list[str]):
    import futuris.core.universe_forecasting as uf

    async def fake_generate(
        target, context=None, session=None, skip_intelx=False, model_budget_seconds=None, **_kw
    ):
        record.append(target)
        return _forecast_stub(target, ForecastStatus.ACTIVE)

    monkeypatch.setattr(uf, "generate_universe_forecast", fake_generate)


async def test_refresh_all_visits_provider_targets_first(monkeypatch):
    record: list[str] = []
    _recording_generate(monkeypatch, record)

    generated = await refresh_all_within_budget(object(), budget_seconds=60.0)

    assert generated == len(UNIVERSE_TARGETS)
    provider_targets = [t for t, s in UNIVERSE_TARGETS.items() if s.series_provider]
    data_path = [t for t, s in UNIVERSE_TARGETS.items() if s.series_provider or s.pipeline_target]
    # Every data-path target (pipeline + provider) is attempted before any
    # plain target; within the group, registry order is preserved.
    assert record[: len(data_path)] == data_path
    first_plain = min(
        record.index(t)
        for t, s in UNIVERSE_TARGETS.items()
        if not (s.series_provider or s.pipeline_target)
    )
    assert all(record.index(t) < first_plain for t in provider_targets)


async def test_refresh_missing_retries_insufficient_provider_target(monkeypatch):
    record: list[str] = []
    _recording_generate(monkeypatch, record)

    present = {t: _forecast_stub(t, ForecastStatus.ACTIVE) for t in UNIVERSE_TARGETS}
    present[PROVIDER_TARGET] = _forecast_stub(PROVIDER_TARGET, ForecastStatus.INSUFFICIENT_DATA)
    present[PLAIN_TARGET] = _forecast_stub(PLAIN_TARGET, ForecastStatus.INSUFFICIENT_DATA)

    generated = await refresh_missing_within_budget(object(), present, budget_seconds=60.0)

    # Only the provider target is retried: the plain target's refusal is
    # its only possible answer without caller context, so re-refusing it
    # on every read would burn the budget for nothing.
    assert record == [PROVIDER_TARGET]
    assert generated == 1
    assert present[PROVIDER_TARGET].status is ForecastStatus.ACTIVE
    assert present[PLAIN_TARGET].status is ForecastStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# 3. Scheduler: the provider targets have an unattended job
# ---------------------------------------------------------------------------


async def test_universe_provider_refresh_job_forecasts_provider_targets(monkeypatch):
    pytest.importorskip("apscheduler")
    import futuris.core.universe_forecasting as uf
    from futuris.infra.scheduler import ForecastScheduler

    record: list[str] = []

    async def fake_generate(
        target, context=None, session=None, skip_intelx=False, model_budget_seconds=None, **_kw
    ):
        record.append(target)
        assert session == "scheduler-session"
        return _forecast_stub(target, ForecastStatus.ACTIVE)

    monkeypatch.setattr(uf, "generate_universe_forecast", fake_generate)

    class _Repo:
        session = "scheduler-session"

    scheduler = ForecastScheduler(forecast_repo=_Repo())
    refreshed = await scheduler.universe_provider_refresh_job()

    expected = [t for t, s in UNIVERSE_TARGETS.items() if s.series_provider]
    assert record == expected
    assert [f.target for f in refreshed] == expected


async def test_universe_provider_refresh_job_without_session_skips(monkeypatch):
    pytest.importorskip("apscheduler")
    from futuris.infra.scheduler import ForecastScheduler

    scheduler = ForecastScheduler(forecast_repo=None)
    assert await scheduler.universe_provider_refresh_job() == []


async def test_scheduler_registers_universe_provider_job():
    pytest.importorskip("apscheduler")
    from futuris.infra.scheduler import ForecastScheduler

    scheduler = ForecastScheduler()
    scheduler.start()
    try:
        job_ids = {job.id for job in scheduler.scheduler.get_jobs()}
        assert "universe_provider_refresh_job" in job_ids
        assert "forecast_refresh_job" in job_ids
    finally:
        scheduler.scheduler.shutdown(wait=False)
