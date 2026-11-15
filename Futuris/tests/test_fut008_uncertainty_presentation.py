"""TASK-FUT-008: Futuris uncertainty communication.

Every forecast presented to FRIDAY or the owner must carry its horizon,
its honestly named method (no statsforecast claim while statsforecast is
not installed), and a calibrated uncertainty range in plain language.

These tests pin that contract:

* ``describe_method`` names a statsforecast model as statsforecast ONLY
  when the backend is installed; otherwise the stored label is reported
  as a recorded label that was not produced by a statsforecast run here.
* ``forecast_presentation`` always states the horizon in words, labels the
  range with its actual 90% level, and distinguishes measured calibration
  from unmeasured calibration.
* The FRIDAY delegation response carries ``horizon`` + ``presentation``
  (it previously dropped the horizon entirely), and the canonical
  ForecastResponse carries ``presentation`` too.
* The market router no longer sends the label ``statsforecast_garch_intelx``
  to Inference for numbers a deterministic telemetry rule produced.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from futuris.presentation.uncertainty import (
    INTERVAL_LEVEL_PCT,
    blocked_presentation,
    describe_method,
    forecast_presentation,
    horizon_text,
    scenario_presentation,
)


def test_horizon_text_plain_language():
    assert horizon_text(timedelta(hours=1)) == "1 hour"
    assert horizon_text(timedelta(hours=24)) == "24 hours"
    assert horizon_text(timedelta(days=7)) == "7 days"
    assert horizon_text(timedelta(days=30)) == "30 days"
    assert horizon_text("24h") == "24 hours"
    assert horizon_text("7d") == "7 days"
    # str(timedelta) — the form the canonical API used to serve raw.
    assert horizon_text("1 day, 0:00:00") == "24 hours"
    assert horizon_text(None) == "an unspecified horizon"


def test_method_names_statsforecast_only_when_installed():
    installed = describe_method("seasonal_naive@v1:c8f93a", statsforecast_available=True)
    assert installed["method"] == "Seasonal naive (statsforecast)"
    assert installed["backend_available"] is True

    absent = describe_method("seasonal_naive@v1:c8f93a", statsforecast_available=False)
    assert "statsforecast)" not in absent["method"]
    assert "not installed" in absent["method_detail"]
    assert "not produced by a statsforecast run" in absent["method_detail"]
    assert absent["backend_available"] is False


def test_method_heuristic_and_unknown_labels_are_not_invented():
    heuristic = describe_method(
        "heuristic:telemetry_vol_rule@v2", statsforecast_available=False
    )
    assert heuristic["method"] == "Deterministic telemetry rule"
    assert "not a statsforecast or GARCH run" in heuristic["method_detail"]

    unknown = describe_method("quantum_foo@v9:abc", statsforecast_available=True)
    assert unknown["method"].startswith("Recorded model label")
    assert "does not invent" in unknown["method_detail"]

    missing = describe_method(None, statsforecast_available=False)
    assert missing["method"] == "Not recorded"


def _presentation(**overrides):
    kwargs = {
        "target": "service:checkout:capacity_exceedance_24h",
        "horizon": timedelta(hours=24),
        "prediction": 128.5,
        "range_lower": 100.2,
        "range_upper": 156.8,
        "probability": 0.42,
        "confidence": "medium",
        "model_version": "seasonal_naive@v1:c8f93a",
        "calibration_metrics": {},
        "evidence_class": "synthetic",
        "statsforecast_available": False,
    }
    kwargs.update(overrides)
    return forecast_presentation(**kwargs)


def test_presentation_carries_horizon_level_and_unmeasured_calibration():
    block = _presentation()
    assert block["horizon_text"] == "24 hours"
    assert block["interval_level_pct"] == INTERVAL_LEVEL_PCT == 90
    assert block["uncertainty_range"] == {
        "lower": 100.2,
        "upper": 156.8,
        "level_pct": 90,
    }
    assert block["calibration_status"] == "unmeasured"
    summary = block["summary"]
    assert "over the next 24 hours" in summary
    assert "90% prediction range is 100.2 to 156.8" in summary
    assert "Calibration for this target is unmeasured" in summary
    assert "synthetic/demo data" in summary
    # The confidence label must be explained, not left to be misread as the
    # probability of the event.
    assert "not the probability of the event" in summary
    assert "Estimated probability of the event in this horizon: 42%" in summary


def test_presentation_measured_calibration_is_stated_with_sample_size():
    block = _presentation(
        calibration_metrics={"n_resolved_outcomes": 37, "ece": 0.04},
        evidence_class="live",
    )
    assert block["calibration_status"] == "measured"
    assert "measured from 37 resolved forecast(s)" in block["summary"]
    assert "live measured data" in block["summary"]


def test_presentation_rule_bound_range_is_not_dressed_as_interval():
    block = _presentation(interval_level_pct=None)
    assert block["interval_level_pct"] is None
    assert "deterministic rule bound, not a statistical prediction interval" in (
        block["summary"]
    )


def test_scenario_presentation_states_probability_not_recomputed():
    block = scenario_presentation(
        horizon=timedelta(hours=24),
        base_prediction=100.0,
        divergent_prediction=140.0,
        delta_pct=40.0,
        risk_assessment="HIGH_RISK",
        monte_carlo=True,
        range_lower=110.0,
        range_upper=170.0,
    )
    assert block["probability_status"] == "not_recomputed_by_scenario_engine"
    assert "not recomputed for the scenario" in block["summary"]
    assert "based only on the size of the change" in block["summary"]

    linear = scenario_presentation(
        horizon="24h",
        base_prediction=100.0,
        divergent_prediction=90.0,
        delta_pct=-10.0,
        monte_carlo=False,
    )
    assert linear["method"] == "Deterministic linear scenario propagation"
    assert "no probability distribution" in linear["method_detail"]


def test_blocked_presentation_says_no_forecast_was_computed():
    block = blocked_presentation(
        target="service:checkout:capacity_exceedance_24h",
        horizon="24h",
        reason="The statsforecast model backend is unavailable in this deployment.",
    )
    assert block["uncertainty_range"] is None
    assert "No forecast was computed" in block["summary"]
    assert "over the next 24 hours" in block["summary"]


def test_friday_delegation_response_carries_horizon_and_presentation():
    from futuris.api.routers.friday import (
        FridayForecastRequest,
        _friday_forecast_response,
    )
    from futuris.core.enums import ConfidenceLevel, EvidenceClass, ForecastStatus

    forecast = SimpleNamespace(
        forecast_id=uuid4(),
        target="service:checkout:capacity_exceedance_24h",
        horizon=timedelta(hours=24),
        prediction=128.5,
        range_lower=100.2,
        range_upper=156.8,
        probability=0.42,
        confidence=ConfidenceLevel.MEDIUM,
        status=ForecastStatus.ACTIVE,
        predictive_distribution={},
        intervals=[],
        model_metadata={},
        model_version="seasonal_naive@v1:c8f93a",
        assumptions=[],
        evidence=[],
        drivers=[],
        calibration_metrics={},
        evidence_class=EvidenceClass.SYNTHETIC,
        evidence_source="telemetry:synthetic",
    )
    req = FridayForecastRequest(
        target="service:checkout:capacity_exceedance_24h", horizon="24h"
    )
    resp = _friday_forecast_response(req, forecast)
    assert resp.horizon == "24 hours"
    assert resp.presentation["horizon_text"] == "24 hours"
    assert resp.presentation["calibration_status"] == "unmeasured"
    assert "90% prediction range" in resp.presentation["summary"]


def test_canonical_forecast_response_carries_presentation():
    from futuris.api.routers.forecasts import ForecastResponse

    assert "presentation" in ForecastResponse.model_fields


def test_market_router_no_longer_claims_statsforecast_garch():
    market_py = (
        Path(__file__).resolve().parents[1]
        / "futuris"
        / "api"
        / "routers"
        / "market.py"
    )
    source = market_py.read_text()
    # The string may appear only inside the TASK-FUT-008 comment explaining
    # its removal — never as a value actually sent anywhere.
    for line in source.splitlines():
        if "statsforecast_garch_intelx" in line:
            assert line.strip().startswith("#"), line
    assert 'model_used="heuristic:telemetry_vol_rule@v2"' in source


def test_no_surface_reintroduces_unlabelled_confidence_language():
    """Guard: presentation summaries never use bare certainty words."""
    block = _presentation()
    assert not re.search(r"\b(will definitely|certainly|guaranteed)\b", block["summary"])
