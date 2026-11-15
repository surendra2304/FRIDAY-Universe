"""TASK-FUT-004: the walk-forward forecast evaluation harness.

Pins the harness's honesty contract:
- origins never leak (fit window strictly precedes the scored window);
- metrics match hand-computed values on known inputs;
- production adapters are scored when statsforecast is genuinely
  importable and recorded NOT SCORABLE — with the refusal counted, never
  substituted — when it is not (the production fleet's state today);
- provenanced series are sha256-verified before scoring;
- failed/invalid origins are counted, never silently scored (the defect
  class of the pre-existing BacktestEngine, which substitutes the forecast
  as the actual when an observation is missing).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("DATABASE_URL", "oracle+oracledb://mock:mock@localhost:1521/FREE")

from futuris.evaluation import walkforward
from futuris.evaluation.reference_models import reference_forecasters
from futuris.evaluation.walkforward import (
    SeriesData,
    build_scorecard,
    generate_origins,
    load_series,
    production_forecasters,
    render_scorecard_markdown,
    run_walk_forward,
    score_origins,
)
from futuris.models.adapters import STATSFORECAST_AVAILABLE

FUTURIS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = FUTURIS_ROOT / "evaluation_data"


def _tiny_series(n: int = 48) -> SeriesData:
    t = np.arange(n, dtype=float)
    values = 100.0 + 8.0 * np.sin(2.0 * np.pi * t / 4.0) + 0.05 * t
    import pandas as pd

    times = [str(ts) for ts in pd.date_range("2026-01-01", periods=n, freq="h")]
    return SeriesData(
        series_id="tiny",
        kind="synthetic",
        values=values,
        times=times,
        season_length=4,
        horizon=4,
        min_train=24,
        step=4,
        frequency="h",
        sha256="test-fixture",
    )


# ---------------------------------------------------------------------------
# Origins / leakage
# ---------------------------------------------------------------------------


def test_generate_origins_never_leaks_and_counts_match_protocol() -> None:
    origins = generate_origins(n=144, min_train=84, horizon=12, step=12)
    assert origins == [84, 96, 108, 120, 132]
    for origin in origins:
        assert origin + 12 <= 144  # scored window fully inside the series
    assert generate_origins(n=10, min_train=9, horizon=4, step=1) == []


# ---------------------------------------------------------------------------
# Metrics against hand-computed values
# ---------------------------------------------------------------------------


def test_score_origins_hand_computed() -> None:
    series = _tiny_series()
    # One origin, horizon 4: errors 1, -2, 0, 3; intervals cover steps 1,2,4.
    actuals = [np.array([10.0, 20.0, 30.0, 40.0])]
    points = [np.array([11.0, 18.0, 30.0, 43.0])]
    lowers = [np.array([9.0, 15.0, 31.0, 38.0])]
    uppers = [np.array([13.0, 21.0, 35.0, 44.0])]
    # Training window with seasonal-naive (m=4) scale exactly 2.0.
    train = np.array([0.0, 0.0, 0.0, 0.0, 2.0, 2.0, 2.0, 2.0])
    scale = walkforward._mase_scale(train, season_length=4)
    assert scale == 2.0

    m = score_origins(series, actuals, points, lowers, uppers, [scale])
    assert m["n_points"] == 4
    assert m["mae"] == pytest.approx(1.5)  # (1+2+0+3)/4
    assert m["rmse"] == pytest.approx(np.sqrt((1 + 4 + 0 + 9) / 4))
    assert m["mase"] == pytest.approx(0.75)  # 1.5 / 2.0
    assert m["coverage_90"] == pytest.approx(0.75)  # step 3 (30 < lower 31) misses
    assert m["coverage_gap_vs_nominal"] == pytest.approx(-0.15)
    assert m["mean_interval_width"] == pytest.approx((4 + 6 + 4 + 6) / 4)
    # Winkler (alpha=0.1): widths 4,6,4,6; step 3 misses below by 1 -> +20*1.
    assert m["winkler_90"] == pytest.approx((4 + 6 + (4 + 20.0) + 6) / 4)


# ---------------------------------------------------------------------------
# Reference baselines prove the machinery end-to-end
# ---------------------------------------------------------------------------


def test_reference_baselines_score_on_tiny_series() -> None:
    series = _tiny_series()
    for forecaster in reference_forecasters(series.season_length):
        result = run_walk_forward(series, forecaster)
        assert result.kind == "reference"
        assert result.status == "scored"
        assert result.origins_attempted == 6
        assert result.origins_scored == 6
        m = result.metrics
        assert m is not None
        assert m["n_points"] == 6 * series.horizon
        assert 0.0 <= m["coverage_90"] <= 1.0
        assert m["mase"] is not None and np.isfinite(m["mase"]) and m["mase"] > 0
        assert len(m["per_step_mae"]) == series.horizon
        assert len(m["per_step_coverage_90"]) == series.horizon


# ---------------------------------------------------------------------------
# Production adapters: scored iff the backend genuinely exists
# ---------------------------------------------------------------------------


def test_production_adapters_follow_backend_availability() -> None:
    series = _tiny_series()
    forecasters = production_forecasters(series.season_length)
    assert [f.name for f in forecasters] == list(walkforward.PRODUCTION_CANDIDATES)
    for forecaster in forecasters:
        result = run_walk_forward(series, forecaster)
        assert result.kind == "production"
        if STATSFORECAST_AVAILABLE:
            assert result.status == "scored", (forecaster.name, result.origins)
            assert result.metrics is not None
            assert 0.0 <= result.metrics["coverage_90"] <= 1.0
        else:
            # The production fleet's state: every fit refuses, the harness
            # records it, and NO number is reported for the model.
            assert result.status == "not_scorable"
            assert result.metrics is None
            assert result.origins_scored == 0
            assert result.origins_attempted == 6
            assert all(o.status == "backend_unavailable" for o in result.origins)
            summary = walkforward.failure_summary(result)
            assert summary is not None and "statsforecast" in summary


# ---------------------------------------------------------------------------
# Failure accounting: nothing failed is ever silently scored
# ---------------------------------------------------------------------------


class _NaNForecaster:
    name = "broken_nan"
    kind = "reference"

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None:
        _ = y_train, train_times

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        bad = np.full(horizon, np.nan)
        return bad, bad, bad


class _ExplodingForecaster:
    name = "broken_raise"
    kind = "reference"

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None:
        raise RuntimeError("boom")

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        raise AssertionError("unreachable")


def test_invalid_and_failed_origins_are_counted_never_scored() -> None:
    series = _tiny_series()
    nan_result = run_walk_forward(series, _NaNForecaster())
    assert nan_result.status == "not_scorable"
    assert nan_result.metrics is None
    assert all(o.status == "invalid_output" for o in nan_result.origins)

    err_result = run_walk_forward(series, _ExplodingForecaster())
    assert err_result.status == "not_scorable"
    assert err_result.metrics is None
    assert all(o.status == "error" for o in err_result.origins)
    assert "boom" in (walkforward.failure_summary(err_result) or "")


# ---------------------------------------------------------------------------
# Provenance: data is verified before it is scored
# ---------------------------------------------------------------------------


def test_vendored_series_load_with_verified_provenance() -> None:
    series = load_series(DATA_DIR)
    by_id = {s.series_id: s for s in series}
    assert set(by_id) == {
        "air_passengers_monthly",
        "fred_dexuseu_daily",
        "synthetic_telemetry_5min",
    }
    assert len(by_id["air_passengers_monthly"].values) == 144
    assert len(by_id["fred_dexuseu_daily"].values) == 1000
    assert len(by_id["synthetic_telemetry_5min"].values) == 4032
    assert by_id["air_passengers_monthly"].kind == "real"
    assert by_id["fred_dexuseu_daily"].kind == "real"
    assert by_id["synthetic_telemetry_5min"].kind == "synthetic"
    assert by_id["synthetic_telemetry_5min"].season_length == 288


def test_tampered_series_is_refused(tmp_path: Path) -> None:
    import shutil

    for name in ("PROVENANCE.json", "air_passengers_monthly.csv"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    manifest = (tmp_path / "PROVENANCE.json").read_text()
    # Keep only the air-passengers entry so the loader reaches its check.
    import json

    doc = json.loads(manifest)
    doc["series"] = [e for e in doc["series"] if e["id"] == "air_passengers_monthly"]
    (tmp_path / "PROVENANCE.json").write_text(json.dumps(doc))
    target = tmp_path / "air_passengers_monthly.csv"
    target.write_text(target.read_text().replace(",112", ",113", 1))
    with pytest.raises(ValueError, match="provenance check failed"):
        load_series(tmp_path)


def test_synthetic_series_regenerates_identically() -> None:
    spec = importlib.util.spec_from_file_location(
        "synthetic_generator", DATA_DIR / "generate_synthetic_telemetry.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, values = module.generate()
    loaded = {s.series_id: s for s in load_series(DATA_DIR)}["synthetic_telemetry_5min"]
    # The CSV stores 4 decimal places; regeneration must agree to that precision.
    assert np.allclose(values, loaded.values, atol=1e-4)


# ---------------------------------------------------------------------------
# Scorecard: the honesty contract in the deliverable itself
# ---------------------------------------------------------------------------


def test_scorecard_reports_production_status_explicitly() -> None:
    series = _tiny_series()
    results = [run_walk_forward(series, f) for f in production_forecasters(series.season_length)]
    results += [run_walk_forward(series, f) for f in reference_forecasters(series.season_length)]
    card = build_scorecard([series], results, walkforward.environment_info())

    prod = [r for r in card["results"] if r["kind"] == "production"]
    assert len(prod) == 5
    for entry in prod:
        if STATSFORECAST_AVAILABLE:
            assert entry["status"] == "scored" and entry["metrics"] is not None
        else:
            assert entry["status"] == "not_scorable"
            assert entry["metrics"] is None
            assert entry["origins_scored"] == 0
            assert entry["failure_summary"]
    md = render_scorecard_markdown(card)
    assert "BASELINE SCORECARD" in md
    if not STATSFORECAST_AVAILABLE:
        assert "cannot be scored" in md
