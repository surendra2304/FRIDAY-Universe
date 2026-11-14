"""TASK-FUT-002 regression tests: honest Futuris outputs under the
statsforecast-unavailable constraint (owner decision: statsforecast is not
installed until the ARM server arrives; REL-018's honest-unavailable
behaviour must stay intact).

Every test here pins a place where Futuris invented a number, a driver, or
a provenance-free payload instead of computing from its stated inputs or
saying plainly that the value was not measured:

* pipeline: fabricated fallback driver + hardcoded assumption + a 0.5
  exceedance probability (and a Brier score derived from it) when the model
  produced no probability and the driver analyzer found no drivers;
* model selection: five futile candidate fits (each logging a failure)
  before the unavailable error surfaces -- the journal spam behind every
  scheduler skip;
* FRIDAY delegation: 0.5 probability fabrication, a hardcoded
  "2h (lag-2 peak)" lead time, a scenario probability invented from the
  delta, and a calibration report computed from invented probabilities
  with per-target ECE multipliers and a fixed "improving" trend;
* market router: fixed 0.84-base confidence, a filler IntelX driver when
  no research existed, and a regime transition probability that is an
  arbitrary transform of the volatility probability;
* quick surfaces: /trends dropping provenance, /simulate crashing on
  attributes ScenarioResult does not have (and dropping provenance);
* scenario + fan-chart surfaces carrying no provenance at all.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import numpy as np
import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from futuris.core.enums import (
    ConfidenceLevel,
    EvidenceClass,
    ForecastStatus,
    ResolutionMethod,
    SignalClass,
    SourceTrust,
)
from futuris.core.schemas import Driver, EvidenceRef, Forecast, Outcome
from futuris.storage.models import Base

AS_OF = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


def _forecast(**overrides) -> Forecast:
    evidence_id = uuid4()
    base = {
        "forecast_id": uuid4(),
        "target": "service:checkout:capacity_exceedance_24h",
        "as_of": AS_OF,
        "horizon": timedelta(hours=24),
        "expires_at": AS_OF + timedelta(hours=24),
        "prediction": 100.0,
        "range_lower": 90.0,
        "range_upper": 110.0,
        "probability": None,
        "confidence": ConfidenceLevel.LOW,
        "drivers": [],
        "evidence": [
            EvidenceRef(
                evidence_id=evidence_id,
                source="telemetry:synthetic",
                source_trust=SourceTrust.HIGH,
                signal_class=SignalClass.TELEMETRY,
                as_of=AS_OF,
                snapshot_path="/tmp/snap.parquet",
                content_hash="mockhash",
                evidence_class=EvidenceClass.SYNTHETIC,
            )
        ],
        "model_version": "naive@v1",
        "assumptions": [],
        "review_at": AS_OF + timedelta(hours=6),
        "status": ForecastStatus.ACTIVE,
        "evidence_class": EvidenceClass.SYNTHETIC,
        "evidence_source": "test:synthetic",
    }
    base.update(overrides)
    return Forecast(**base)


@pytest.fixture
async def fut002_db():
    """Isolated in-memory SQLite database (same pattern as the FRIDAY tests)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Pipeline: no fabricated driver, assumption, probability, or Brier score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_invents_nothing_when_no_drivers_and_no_probability():
    from futuris.core.pipeline import (
        CalibrationDecisionStage,
        IngestionInput,
        IngestionStage,
        ModelingOutput,
        NormalizationInput,
        NormalizationStage,
    )
    from futuris.models.base import ModelPrediction, PredictionIntervals

    raw = await IngestionStage().execute(
        IngestionInput(
            target="service:checkout:capacity_exceedance_24h",
            start_time=AS_OF - timedelta(days=2),
            end_time=AS_OF,
        )
    )
    signal_set = await NormalizationStage().execute(NormalizationInput(observations=raw))
    # A feature table with ONLY the target column: the driver analyzer can
    # find no drivers in it, by construction.
    features_df = pd.DataFrame({"value": signal_set.values})
    evidence_ref = _forecast().evidence[0]

    modeling_out = ModelingOutput(
        prediction=ModelPrediction(
            point_forecast=[100.0],
            intervals=[PredictionIntervals(lower=90.0, central=100.0, upper=110.0)],
            range_lower=90.0,
            range_upper=110.0,
            central_estimate=100.0,
            exceedance_probability=None,
        ),
        model_version="naive@v1",
        best_score=1.0,
        features_df=features_df,
        signal_set=signal_set,
        evidence_ref=evidence_ref,
        horizon=timedelta(hours=24),
        as_of=AS_OF,
        target="service:checkout:capacity_exceedance_24h",
    )

    forecast, _, _ = await CalibrationDecisionStage().execute(modeling_out)

    # No driver was measured, so none may be reported.
    assert forecast.drivers == []
    # No assumption was supplied or derived, so none may be asserted.
    assert forecast.assumptions == []
    # The model produced no exceedance probability: the forecast and its
    # distribution must say so instead of substituting 0.5.
    assert forecast.probability is None
    assert "exceedance_probability" not in forecast.predictive_distribution
    # A Brier score computed from the invented 0.5 is an invented number.
    assert "brier_score" not in forecast.calibration_metrics
    assert forecast.calibration_metrics["calibration_status"] == "uncalibrated"


# ---------------------------------------------------------------------------
# 2. Model selection: refuse once, up front, when statsforecast is absent
# ---------------------------------------------------------------------------


def test_model_selection_refuses_fast_when_statsforecast_unavailable(monkeypatch):
    from futuris.models import selection as selection_module
    from futuris.models.adapters import StatsForecastUnavailableError

    monkeypatch.setattr(selection_module, "STATSFORECAST_AVAILABLE", False, raising=False)

    with pytest.raises(StatsForecastUnavailableError):
        selection_module.select_best_adapter(
            ["naive", "drift", "seasonal_naive"],
            x_train=pd.DataFrame(index=range(6)),
            y_train=pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            y_val=np.array([7.0, 8.0]),
            as_of=AS_OF,
            val_steps=2,
            step_minutes=5,
        )


# ---------------------------------------------------------------------------
# 3. Scheduler: repeated unavailable cycles skip cleanly, one warning each
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_repeated_unavailable_cycles_skip_cleanly(monkeypatch):
    from futuris.infra import scheduler as scheduler_module
    from futuris.infra.scheduler import ForecastScheduler, ForecastSubscription
    from futuris.models.adapters import StatsForecastUnavailableError

    class RecordingLogger:
        def __init__(self):
            self.warnings = []

        def info(self, *args, **kwargs):
            pass

        def debug(self, *args, **kwargs):
            pass

        def warning(self, event, **kwargs):
            self.warnings.append(event)

        def error(self, *args, **kwargs):
            pass

    recorder = RecordingLogger()
    monkeypatch.setattr(scheduler_module, "logger", recorder)

    class UnavailablePipeline:
        def __init__(self):
            self.calls = 0

        async def run(self, **kwargs):
            self.calls += 1
            raise StatsForecastUnavailableError("forced unavailable for test")

    pipeline = UnavailablePipeline()
    scheduler = ForecastScheduler(pipeline=pipeline)
    scheduler.subscriptions = [
        ForecastSubscription(target="service:checkout:capacity_exceedance_24h"),
        ForecastSubscription(target="trading:BTCUSDT:price_variance_24h"),
    ]
    scheduler.sync_dynamic_trading_subscriptions = AsyncMock(return_value=[])

    first = await scheduler.forecast_refresh_job()
    second = await scheduler.forecast_refresh_job()

    assert first == []
    assert second == []
    assert pipeline.calls == 4
    assert recorder.warnings == ["forecast_refresh_skipped_statsforecast_unavailable"] * 4


# ---------------------------------------------------------------------------
# 4. FRIDAY forecast response: no 0.5, no fabricated lead time
# ---------------------------------------------------------------------------


def test_friday_response_does_not_fabricate_probability_or_lead_time():
    from futuris.api.routers.friday import FridayForecastRequest, _friday_forecast_response

    base = _forecast()
    forecast = base.model_copy(
        update={
            "drivers": [
                Driver(
                    name="traffic",
                    direction="positive",
                    strength=0.8,
                    leading_or_lagging="leading",
                    evidence_refs=[base.evidence[0].evidence_id],
                )
            ]
        }
    )
    req = FridayForecastRequest(
        friday_request_id="req_fut002",
        target=forecast.target,
        horizon="24h",
    )
    resp = _friday_forecast_response(req, forecast)

    assert "exceedance_probability" not in resp.prediction.probability_distribution
    assert "exceedance_probability" not in resp.predictive_distribution
    # The Driver record carries no measured lag, so the response must not
    # claim a specific "2h (lag-2 peak)".
    assert resp.drivers_identified[0].lead_time != "2h (lag-2 peak)"
    assert resp.evidence_class == EvidenceClass.SYNTHETIC


# ---------------------------------------------------------------------------
# 5. FRIDAY calibration: computed from the real resolved pairs only
# ---------------------------------------------------------------------------


class _FakeOutcomeRepo:
    """Outcome repository stand-in serving a fixed set of resolved pairs."""

    def __init__(self, pairs):
        self._pairs = pairs

    async def list_resolved_with_forecasts(self, limit=5000):
        return self._pairs

    async def list_all(self, limit=1000):
        return [outcome for _, outcome in self._pairs]


def _pair(target: str, probability: float, occurred: bool, observed: float, resolved_at):
    forecast = _forecast(
        target=target,
        probability=probability,
        prediction=100.0,
        range_lower=90.0,
        range_upper=110.0,
    )
    outcome = Outcome(
        outcome_id=uuid4(),
        forecast_id=forecast.forecast_id,
        observed_value=observed,
        event_occurred=occurred,
        resolved_at=resolved_at,
        resolution_method=ResolutionMethod.AUTOMATED_TELEMETRY,
        resolution_rule_version="fut002-test:v1",
    )
    return forecast, outcome


@pytest.mark.asyncio
async def test_friday_calibration_is_computed_from_real_pairs():
    from futuris.api.routers.friday import get_friday_calibration
    from futuris.evaluation.calibration import CalibrationAnalyzer

    pairs = [
        _pair("target:a", 0.9, True, 100.0, AS_OF),
        _pair("target:a", 0.8, True, 100.0, AS_OF + timedelta(hours=1)),
        _pair("target:b", 0.2, False, 50.0, AS_OF + timedelta(hours=2)),
        _pair("target:b", 0.1, False, 95.0, AS_OF + timedelta(hours=3)),
    ]
    report = await get_friday_calibration(outcome_repo=_FakeOutcomeRepo(pairs))

    expected_ece = CalibrationAnalyzer().compute_expected_calibration_error(
        [0.9, 0.8, 0.2, 0.1], [True, True, False, False]
    )
    assert report.overall_ece == pytest.approx(expected_ece)
    # Only targets that actually resolved appear -- no invented breakdown.
    assert set(report.per_target_type_calibration) == {"target:a", "target:b"}
    summary = report.recent_accuracy_summary
    assert summary["resolved_samples"] == 4
    assert summary["calibration_status"] == "measured"
    # Brier from the real pairs: (0.01 + 0.04 + 0.04 + 0.01) / 4.
    assert summary["brier_score"] == pytest.approx(0.025)
    # Coverage from the real ranges: 3 of 4 observed values fell inside.
    assert summary["coverage_90_pct"] == pytest.approx(0.75)
    # Older half ECE 0.10, recent half ECE 0.20 -> calibration is degrading.
    assert report.trend == "degrading"


@pytest.mark.asyncio
async def test_friday_calibration_with_no_pairs_is_unmeasured():
    from futuris.api.routers.friday import get_friday_calibration

    report = await get_friday_calibration(outcome_repo=_FakeOutcomeRepo([]))

    assert report.per_target_type_calibration == {}
    assert report.trend == "unmeasured"
    assert report.recent_accuracy_summary["resolved_samples"] == 0
    assert report.recent_accuracy_summary["calibration_status"] == "unmeasured"


# ---------------------------------------------------------------------------
# 6. FRIDAY scenario: probability and provenance come from the base forecast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friday_scenario_does_not_invent_probability_and_carries_provenance(fut002_db):
    from futuris.api.routers.friday import (
        FridayScenarioRequest,
        FridayScenarioSpec,
        VariableChange,
        evaluate_scenario,
    )
    from futuris.storage.repositories import ForecastRepository

    base = _forecast(probability=None)
    repo = ForecastRepository(fut002_db)
    await repo.create(base)
    await fut002_db.commit()

    resp = await evaluate_scenario(
        FridayScenarioRequest(
            question="What if demand rises 10%?",
            base_forecast_id=base.forecast_id,
            scenario_spec=FridayScenarioSpec(
                name="demand_up",
                variable_changes=[VariableChange(metric="demand", change_pct=10.0)],
                assumptions=[],
            ),
        ),
        session=fut002_db,
    )

    # The scenario engine does not recompute a probability, and the base
    # forecast has none: the answer must carry none, not 0.5.
    assert resp.probability_outcome is None
    assert resp.evidence_class == EvidenceClass.SYNTHETIC
    assert resp.evidence_source == "test:synthetic"


# ---------------------------------------------------------------------------
# 7. Market router: derived-or-absent confidence, no filler drivers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_market_forecast_has_no_filler_driver_or_invented_confidence(monkeypatch):
    from futuris.api.routers import market as market_module
    from futuris.connectors.base import Observation

    def _obs(series_id: str, value: float) -> Observation:
        return Observation(
            observed_at=datetime.now(UTC),
            source="stratex",
            series_id=series_id,
            value=value,
            unit="ratio",
        )

    class FakeTradingConnector:
        def __init__(self, **kwargs):
            pass

        async def fetch(self, start, end):
            return [
                _obs("trading:volatility:btc", 0.50),
                _obs("trading:drawdown", 3.0),
                _obs("trading:equity", 10000.0),
            ]

    monkeypatch.setattr(market_module, "TradingBotConnector", FakeTradingConnector)
    monkeypatch.setattr(
        market_module.ecosystem_adapter,
        "dispatch_market_forecast_to_stratex",
        AsyncMock(return_value=None),
    )

    resp = await market_module._generate_market_prediction(
        symbol="BTCUSDT",
        include_intelx=False,
        include_inference=False,
        forecast_repo=None,
    )

    drivers = resp.volatility_forecast.drivers
    # No IntelX research was included, so no IntelX driver may appear --
    # least of all a "liquidity baseline" filler.
    assert not any("intelx" in d for d in drivers), drivers
    # No resolved market outcomes exist to calibrate against: the
    # confidence must be the declared uncalibrated sentinel, not 0.84.
    assert resp.volatility_forecast.confidence == 0.0
    assert resp.confidence_status == "uncalibrated"
    # No regime history was measured, so no transition probability.
    assert resp.regime_outlook.transition_probability is None
    assert resp.evidence_class == EvidenceClass.LIVE


# ---------------------------------------------------------------------------
# 8. Quick surfaces: /trends and /simulate carry the base provenance
# ---------------------------------------------------------------------------


async def _seed_stored_forecast() -> Forecast:
    from futuris.storage import db as storage_db
    from futuris.storage.repositories import ForecastRepository

    forecast = _forecast(probability=0.4)
    async with storage_db.async_session_factory() as session:
        await ForecastRepository(session).create(forecast)
        await session.commit()
    return forecast


@pytest.mark.asyncio
async def test_quick_trends_carries_provenance():
    from futuris.api.app import app
    from futuris.infra.cache import forecast_cache

    seeded = await _seed_stored_forecast()
    forecast_cache.delete("trends:limit_3")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/trends", params={"limit": 3})
    forecast_cache.delete("trends:limit_3")

    assert resp.status_code == 200, resp.text
    items = {t["forecast_id"]: t for t in resp.json()["trends"]}
    item = items[str(seeded.forecast_id)]
    assert item["evidence_class"] == "synthetic"
    assert item["evidence_source"] == "test:synthetic"
    assert item["input_telemetry_verified"] is False


@pytest.mark.asyncio
async def test_quick_simulate_computes_from_scenario_result_and_carries_provenance():
    from futuris.api.app import app

    seeded = await _seed_stored_forecast()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/simulate",
            json={
                "forecast_id": str(seeded.forecast_id),
                "assumption_overrides": {"demand": 1.5},
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Base prediction 100.0 with demand x1.5 through the ops graph.
    assert body["perturbed_prediction"] == pytest.approx(150.0)
    assert body["evidence_class"] == "synthetic"
    assert body["evidence_source"] == "test:synthetic"
    # The scenario engine does not recompute a probability.
    assert body["perturbed_probability"] is None
    assert body["probability_status"] == "not_recomputed_by_scenario_engine"


# ---------------------------------------------------------------------------
# 9. Scenario results and fan charts carry provenance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_result_inherits_base_provenance():
    from futuris.scenarios.engine import ScenarioEngine
    from futuris.scenarios.spec import ScenarioSpec

    base = _forecast()
    result = await ScenarioEngine().run_scenario(
        base_forecast=base,
        spec=ScenarioSpec.stress(),
        use_monte_carlo=False,
    )
    assert result.evidence_class == EvidenceClass.SYNTHETIC
    assert result.evidence_source == "test:synthetic"


def test_fan_chart_is_labelled_synthetic_simulation():
    from futuris.api.routers.scenarios import FanChartRequest, _execute_fan_chart_simulation

    resp = _execute_fan_chart_simulation(
        FanChartRequest(target="BTCUSDT", base_value=100.0, horizon_steps=3, num_samples=100)
    )
    # A seeded Monte Carlo over caller-supplied parameters is a simulation,
    # not measured market data, and the response must say so.
    assert resp.evidence_class == EvidenceClass.SYNTHETIC
    assert resp.evidence_source is not None and "seed" in resp.evidence_source
