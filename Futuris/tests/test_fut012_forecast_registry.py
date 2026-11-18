"""Tests for the open forecast registry + measured-series path (TASK-FUT-012).

Futuris forecasts everything: the target registry is open (runtime
registration, a VyralX domain), and a target that names a series provider
is fitted on a daily series read from Futuris's own stored data instead of
refusing. Refusal is preserved end-to-end -- short series, a missing
session, and an unavailable statsforecast backend all land in
insufficient_data with the reason recorded.

The forecast-path tests inject a fake selector and a fake series fetcher,
so they run identically with or without a statsforecast backend; one test
additionally pins the real-selector behaviour in backends where
statsforecast is absent (this sandbox and the pre-py3.12 live venv).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from futuris.core.enums import EvidenceClass, ForecastStatus
from futuris.core.series_providers import (
    SERIES_PROVIDERS,
    bucket_daily_counts,
    forecast_request_series,
    get_series_provider,
    intelx_notice_series,
    notice_domain,
    notice_topics,
)
from futuris.core.universe_domains import (
    UNIVERSE_TARGETS,
    DomainTargetSpec,
    UniverseDomain,
    get_target_spec,
    register_target,
)
from futuris.core.universe_forecasting import generate_universe_forecast
from futuris.models.adapters import STATSFORECAST_AVAILABLE, StatsForecastUnavailableError
from futuris.models.base import ModelPrediction

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


def test_vyralx_domain_and_provider_targets_registered():
    assert UniverseDomain.VYRALX == "vyralx"
    for target, provider in [
        ("vyralx:trends:topic_volume_24h", "intelx_topic_notices"),
        ("intelx:research:finding_volume_24h", "intelx_notices"),
        ("friday:fleet:forecast_demand_24h", "forecast_requests"),
    ]:
        spec = get_target_spec(target, strict=True)
        assert spec.series_provider == provider
        assert provider in SERIES_PROVIDERS
    assert get_target_spec("vyralx:trends:topic_volume_24h", strict=True).domain is (
        UniverseDomain.VYRALX
    )


def test_existing_targets_have_no_provider():
    # The 18 pre-FUT-012 targets keep their exact behaviour: only the
    # pipeline target is fitted, the rest refuse without caller context.
    spec = get_target_spec("intelx:research:topic_velocity_surge_24h", strict=True)
    assert spec.series_provider is None and not spec.pipeline_target


def test_register_target_opens_registry_and_refuses_duplicates():
    spec = DomainTargetSpec(
        target="vyralx:uploads:cadence_24h",
        name="VyralX Upload Cadence",
        domain=UniverseDomain.VYRALX,
        unit="events/day",
        description="Runtime-registered test target.",
        high_risk_threshold=10.0,
        critical_risk_threshold=20.0,
        series_provider="intelx_notices",
    )
    try:
        register_target(spec)
        assert get_target_spec(spec.target, strict=True) is spec
        with pytest.raises(ValueError, match="already registered"):
            register_target(spec)
        register_target(spec, replace=True)  # explicit override is allowed
    finally:
        UNIVERSE_TARGETS.pop(spec.target, None)


def test_get_series_provider_unknown_name():
    with pytest.raises(KeyError):
        get_series_provider("no_such_provider")


# --------------------------------------------------------------------------
# Series providers
# --------------------------------------------------------------------------


def test_bucket_daily_counts_zero_fills_and_ends_yesterday():
    stamps = [
        datetime(2026, 11, 17, 9, 0, tzinfo=UTC),
        datetime(2026, 11, 17, 10, 0, tzinfo=UTC),
        datetime(2026, 11, 15, 9, 0),  # naive == UTC by convention
        datetime(2026, 11, 18, 1, 0, tzinfo=UTC),  # today: excluded (partial day)
        datetime(2026, 10, 1, 1, 0, tzinfo=UTC),  # before the window: excluded
    ]
    series = bucket_daily_counts(stamps, days=3, now=NOW)
    assert series == [
        (date(2026, 11, 15), 1.0),
        (date(2026, 11, 16), 0.0),
        (date(2026, 11, 17), 2.0),
    ]


def test_notice_payload_extractors():
    payload = {"relevance": {"domain": "markets"}, "topics": ["btc", "etf"]}
    assert notice_domain(payload) == "markets"
    assert notice_topics(payload) == ["btc", "etf"]
    assert notice_domain({"domain": "ai_models"}) == "ai_models"
    assert notice_domain({}) is None
    assert notice_topics({}) == []
    assert notice_domain("not-a-dict") is None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Returns canned rows for any select; the providers bucket in Python."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _FakeResult(self._rows)


async def test_intelx_notice_series_filters():
    rows = [
        (datetime(2026, 11, 17, 8, 0, tzinfo=UTC), {"relevance": {"domain": "markets"}, "topics": ["btc"]}),
        (datetime(2026, 11, 17, 9, 0, tzinfo=UTC), {"relevance": {"domain": "markets"}}),
        (datetime(2026, 11, 17, 10, 0, tzinfo=UTC), {"relevance": {"domain": "ai_models"}, "topics": ["gpt"]}),
        (datetime(2026, 11, 16, 10, 0, tzinfo=UTC), {"topics": ["drama"]}),
    ]
    session = _FakeSession(rows)
    all_series = await intelx_notice_series(session, days=2, now=NOW)
    assert all_series == [(date(2026, 11, 16), 1.0), (date(2026, 11, 17), 3.0)]
    markets = await intelx_notice_series(session, days=2, now=NOW, domain="markets")
    assert markets == [(date(2026, 11, 16), 0.0), (date(2026, 11, 17), 2.0)]
    tagged = await intelx_notice_series(session, days=2, now=NOW, require_topics=True)
    assert tagged == [(date(2026, 11, 16), 1.0), (date(2026, 11, 17), 2.0)]


async def test_forecast_request_series_counts_rows():
    rows = [
        (datetime(2026, 11, 17, 8, 0, tzinfo=UTC),),
        (datetime(2026, 11, 17, 9, 0, tzinfo=UTC),),
        (datetime(2026, 11, 15, 9, 0, tzinfo=UTC),),
    ]
    series = await forecast_request_series(_FakeSession(rows), days=3, now=NOW)
    assert series == [
        (date(2026, 11, 15), 1.0),
        (date(2026, 11, 16), 0.0),
        (date(2026, 11, 17), 2.0),
    ]


# --------------------------------------------------------------------------
# Forecast path (injected selector + fetcher)
# --------------------------------------------------------------------------


class _FakeAdapter:
    name = "naive"

    def __init__(self):
        self.fitted_points = 0

    def get_config_hash(self):
        return "testhash"

    def fit(self, x, y, as_of):
        self.fitted_points = len(y)
        return self

    def predict(self, horizon, capacity_threshold=None, probability_method="empirical", future_x=None):
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
        return {
            "best_validation_score": 1.5,
            "candidate_scores": {"naive": 1.5},
            "selection_degraded": False,
            "selection_elapsed_seconds": 0.001,
        }


def _fake_selector(candidates, *, x_train, y_train, y_val, as_of, val_steps, step_minutes, budget_seconds=None, cpu_saturated=False):
    assert candidates == ["naive", "drift"]
    assert step_minutes == 1440
    assert len(y_train) + val_steps >= 10
    return _FakeOutcome(_FakeAdapter())


def _series(points: int, start_value: float = 3.0):
    end = NOW.date() - timedelta(days=1)
    return [
        (end - timedelta(days=points - 1 - i), start_value + i) for i in range(points)
    ]


def _fetcher(points: int):
    async def fetch(_session, *, days, now):
        assert days == 28
        return _series(points)

    return fetch


async def test_provider_path_produces_live_forecast():
    forecast = await generate_universe_forecast(
        "intelx:research:finding_volume_24h",
        session=None,
        skip_intelx=True,
        selector=_fake_selector,
        series_fetcher=_fetcher(14),
    )
    assert forecast.status is ForecastStatus.ACTIVE
    assert forecast.prediction == 42.0
    assert (forecast.range_lower, forecast.range_upper) == (38.0, 46.0)
    assert forecast.evidence_class is EvidenceClass.LIVE
    assert forecast.evidence_source == "stored_series:intelx_notices"
    assert forecast.model_metadata["provider"] == "intelx_notices"
    assert forecast.model_metadata["series_points"] == 14
    assert forecast.model_metadata["best_validation_score"] == 1.5
    assert forecast.model_version.startswith("naive@v1:")


async def test_provider_path_short_series_refuses():
    forecast = await generate_universe_forecast(
        "intelx:research:finding_volume_24h",
        session=None,
        skip_intelx=True,
        selector=_fake_selector,
        series_fetcher=_fetcher(5),
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
    assert "10 required" in forecast.model_metadata["error"]


async def test_provider_path_backend_unavailable_refuses():
    def unavailable_selector(*_args, **_kwargs):
        raise StatsForecastUnavailableError("statsforecast is not importable in this deployment")

    forecast = await generate_universe_forecast(
        "vyralx:trends:topic_volume_24h",
        session=None,
        skip_intelx=True,
        selector=unavailable_selector,
        series_fetcher=_fetcher(14),
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
    assert "statsforecast" in forecast.model_metadata["error"]


async def test_provider_path_without_session_or_fetcher_refuses():
    forecast = await generate_universe_forecast(
        "friday:fleet:forecast_demand_24h", session=None, skip_intelx=True
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
    assert "no database session" in forecast.model_metadata["error"]


@pytest.mark.skipif(
    STATSFORECAST_AVAILABLE, reason="real backend present: the real selector fits instead of refusing"
)
async def test_provider_path_real_selector_refuses_without_backend():
    # The pre-py3.12-flip state: the stored series exists, but no honest fit
    # is possible, so the answer is insufficient_data -- never an invented
    # number.
    forecast = await generate_universe_forecast(
        "intelx:research:finding_volume_24h",
        session=None,
        skip_intelx=True,
        series_fetcher=_fetcher(14),
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
    assert "statsforecast" in forecast.model_metadata["error"]


async def test_runtime_registered_provider_target_forecasts():
    spec = DomainTargetSpec(
        target="vyralx:uploads:cadence_24h",
        name="VyralX Upload Cadence",
        domain=UniverseDomain.VYRALX,
        unit="events/day",
        description="Runtime-registered test target.",
        high_risk_threshold=10.0,
        critical_risk_threshold=20.0,
        series_provider="intelx_notices",
    )
    register_target(spec)
    try:
        forecast = await generate_universe_forecast(
            spec.target,
            session=None,
            skip_intelx=True,
            selector=_fake_selector,
            series_fetcher=_fetcher(12),
        )
        assert forecast.status is ForecastStatus.ACTIVE
        assert forecast.prediction == 42.0
    finally:
        UNIVERSE_TARGETS.pop(spec.target, None)


# --------------------------------------------------------------------------
# Unchanged behaviour pins
# --------------------------------------------------------------------------


async def test_unknown_target_still_refused():
    with pytest.raises(ValueError, match="not a registered universe target"):
        await generate_universe_forecast("nope:not:real", skip_intelx=True)


async def test_plain_target_without_context_still_insufficient():
    forecast = await generate_universe_forecast(
        "intelx:research:topic_velocity_surge_24h", session=None, skip_intelx=True
    )
    assert forecast.status is ForecastStatus.INSUFFICIENT_DATA
