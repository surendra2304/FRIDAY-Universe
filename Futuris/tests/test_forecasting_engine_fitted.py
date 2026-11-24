"""Fitted-model tests for Futuris/predict/forecasting_engine.py (TASK-FUT-026).

The engine's ensemble members must be real data-fitted methods computed from
the input series — not the hash-derived curves the old code produced (labels
arima/prophet/lstm/elastic_net on md5-derived exponentials, plus hash jitter
on every forecast step and a fake rmse = |trend| * 10). These tests pin the
fitted behaviour on the real IARI Delhi minimum-temperature series used by
TASK-FUT-026, and pin the scoring hook (absolute error + interval hit).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

try:
    from predict.forecasting_engine import ForecastingEngine
except ImportError:  # pragma: no cover - fallback when the package path is absent
    _here = Path(__file__).resolve().parent
    _path = _here.parent / "predict" / "forecasting_engine.py"  # repo layout
    if not _path.exists():
        _path = _here / "forecasting_engine.py"  # same-dir draft layout
    _spec = importlib.util.spec_from_file_location("forecasting_engine", _path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["forecasting_engine"] = _mod
    _spec.loader.exec_module(_mod)
    ForecastingEngine = _mod.ForecastingEngine

# IARI Agromet Observatory, Delhi daily MINIMUM temperature, 14-23 Nov 2026.
MIN_TEMPS = [15.8, 13.5, 13.0, 10.5, 9.4, 9.0, 9.8, 9.5, 10.8, 9.4]


def _engine_with_series():
    engine = ForecastingEngine()
    series = engine.add_series("delhi_min_temp", "weather", MIN_TEMPS)
    return engine, series


def test_members_are_data_fitted():
    engine, series = _engine_with_series()
    ens = engine.ensemble_forecast(series.series_id, 1)
    # Hand-computed from MIN_TEMPS: persistence = last value; means are trailing
    # means; OLS is the least-squares fit of values vs index, extrapolated to
    # index 10. No hash can produce these numbers.
    assert ens.predictions["persistence"][0] == pytest.approx(9.4)
    assert ens.predictions["mean_3d"][0] == pytest.approx(9.9)
    assert ens.predictions["mean_7d"][0] == pytest.approx(9.771428571428571)
    assert ens.predictions["ols_trend"][0] == pytest.approx(7.8533, abs=1e-3)
    assert ens.consensus[0] == pytest.approx(9.2312, abs=1e-3)


def test_model_names_are_honest():
    engine, series = _engine_with_series()
    ens = engine.ensemble_forecast(series.series_id, 1)
    assert ens.models == ["persistence", "mean_3d", "mean_7d", "ols_trend"]
    assert not set(ens.models) & {"arima", "prophet", "lstm", "elastic_net"}


def test_forecast_is_deterministic():
    engine, series = _engine_with_series()
    first = engine.forecast(series.series_id, "short_term", 1)
    second = engine.forecast(series.series_id, "short_term", 1)
    # The old code added hash jitter to every step, so two runs differed.
    assert first.predictions == second.predictions
    assert first.confidence_lower == second.confidence_lower
    assert first.confidence_upper == second.confidence_upper


def test_rmse_is_measured_backtest():
    engine, series = _engine_with_series()
    result = engine.forecast(series.series_id, "short_term", 1)
    # One-step-ahead backtest of the fitted ensemble, t = 3..9 (n = 7).
    assert result.rmse == pytest.approx(1.4409, abs=1e-3)
    assert result.rmse > 0
    assert result.model == "fitted_ensemble"


def test_interval_comes_from_rmse():
    engine, series = _engine_with_series()
    result = engine.forecast(series.series_id, "short_term", 1)
    point = result.predictions[0]
    assert result.confidence_lower[0] == pytest.approx(point - 1.96 * result.rmse)
    assert result.confidence_upper[0] == pytest.approx(point + 1.96 * result.rmse)


def test_score_forecast_hit_and_miss():
    engine, series = _engine_with_series()
    result = engine.forecast(series.series_id, "short_term", 1)
    hit = engine.score_forecast(result.forecast_id, 10.0)
    assert hit.absolute_error == pytest.approx(abs(result.predictions[0] - 10.0))
    assert hit.interval_hit is True
    assert engine.get_score(result.forecast_id).forecast_id == result.forecast_id
    miss = engine.score_forecast(result.forecast_id, 20.0)
    assert miss.absolute_error == pytest.approx(abs(result.predictions[0] - 20.0))
    assert miss.interval_hit is False


def test_score_unknown_forecast_raises():
    engine, _ = _engine_with_series()
    with pytest.raises(Exception):
        engine.score_forecast("no-such-forecast", 10.0)
