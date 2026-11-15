"""Walk-forward evaluation harness for Futuris's production forecast path.

TASK-FUT-004. This module is the yardstick Futuris will be judged by when
``statsforecast`` lands (post-ARM, owner decision — it is NOT installed by
this harness and the harness never works around its absence).

What it does:

* Drives the *actual production adapters* — the five active candidates from
  ``futuris.models.registry`` (``mean_ensemble``, ``auto_ets``,
  ``seasonal_naive``, ``drift``, ``naive``) — through expanding-window,
  multi-origin walk-forward evaluation on the provenanced series vendored
  in ``Futuris/evaluation_data/`` (see ``PROVENANCE.json`` there; sha256 is
  verified before any scoring).
* Scores point accuracy (MAE, RMSE, MASE) AND calibration: the adapters
  emit nominal-90% prediction intervals (``z = 1.645`` in
  ``BaseStatsForecastAdapter._build_prediction``), so the headline
  calibration metric is the *empirical coverage* of those intervals,
  reported with mean width and the Winkler interval score.
* Records honesty, not just numbers: a model that cannot produce a
  forecast at an origin is counted and classified (``backend_unavailable``
  / ``error`` / ``invalid_output``). A model with zero scored origins is
  ``not_scorable`` and its metrics are ``None`` — never zeros, never a
  substitute forecast. This is the FUT-002/FUT-003 standard applied to
  evaluation.

Relationship to ``futuris.evaluation.backtest.BacktestEngine``: that engine
evaluates the full pipeline end-to-end against the synthetic telemetry
connector only, scores the single selected model, and — when an actual
observation is missing — substitutes the forecast itself as the actual
(``actual_val = f.prediction``), which manufactures zero error. This
harness exists because that design cannot judge the model layer: it is
per-model, per-origin, on provenanced series, and a missing or refused
forecast is a recorded failure, never a substituted actual.

Harness-internal reference baselines live in
``futuris.evaluation.reference_models``. They are NOT production models
and are labelled ``kind="reference"`` in every output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

from futuris.evaluation.metrics import interval_coverage, interval_width, mae, rmse
from futuris.models import adapters as _adapters_module
from futuris.models.adapters import (
    AutoETSAdapter,
    DriftAdapter,
    MeanEnsembleAdapter,
    NaiveAdapter,
    SeasonalNaiveAdapter,
    StatsForecastUnavailableError,
)

#: The production candidate set, in the registry's prioritized order
#: (``ModelRegistry.current_active()``). ``auto_arima`` is registered but is
#: NOT in the active candidate list, so it is not part of the production
#: forecast path this harness judges.
PRODUCTION_CANDIDATES: tuple[str, ...] = (
    "mean_ensemble",
    "auto_ets",
    "seasonal_naive",
    "drift",
    "naive",
)

#: Nominal level of the prediction intervals the production adapters emit
#: (z = 1.645 in ``BaseStatsForecastAdapter._build_prediction``).
NOMINAL_COVERAGE = 0.90
_INTERVAL_ALPHA = 1.0 - NOMINAL_COVERAGE


# ---------------------------------------------------------------------------
# Series loading with provenance verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeriesData:
    """One provenanced evaluation series plus its evaluation protocol."""

    series_id: str
    kind: str  # "real" | "synthetic"
    values: np.ndarray
    times: list[str]
    season_length: int
    horizon: int
    min_train: int
    step: int
    frequency: str
    sha256: str


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_series(data_dir: str | Path) -> list[SeriesData]:
    """Load every series in ``PROVENANCE.json`` under ``data_dir``.

    Raises ``ValueError`` if a file's sha256 does not match the manifest —
    an unverifiable series is never scored.
    """
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "PROVENANCE.json").read_text())
    out: list[SeriesData] = []
    for entry in manifest["series"]:
        path = data_dir / entry["file"]
        digest = _sha256_file(path)
        if digest != entry["sha256"]:
            raise ValueError(
                f"provenance check failed for {entry['file']}: sha256 {digest} "
                f"!= manifest {entry['sha256']}; refusing to score unverifiable data"
            )
        frame = pd.read_csv(path)
        proto = entry["evaluation_protocol"]
        out.append(
            SeriesData(
                series_id=entry["id"],
                kind=entry["kind"],
                values=frame[entry["value_column"]].to_numpy(dtype=float),
                times=[str(t) for t in frame[entry["time_column"]].tolist()],
                season_length=int(proto["season_length"]),
                horizon=int(proto["horizon"]),
                min_train=int(proto["min_train"]),
                step=int(proto["step"]),
                frequency=str(proto["frequency"]),
                sha256=digest,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Forecaster protocol + production adapter wrapper
# ---------------------------------------------------------------------------


class Forecaster(Protocol):
    """Harness forecaster: fit on a training window, predict ``h`` steps."""

    name: str
    kind: str  # "production" | "reference"

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None: ...

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (point, lower, upper), each of length ``horizon``."""
        ...


class ProductionAdapterForecaster:
    """Wraps one production statsforecast adapter exactly as the pipeline
    invokes it (``fit(x, y, as_of=...)`` then ``predict(horizon)``).

    Adapters are constructed directly rather than through
    ``model_registry.get_adapter`` because the registry passes only a
    config dict, and ``SeasonalNaiveAdapter``/``AutoETSAdapter``/
    ``MeanEnsembleAdapter`` take their effective season length from the
    constructor argument — the registry path cannot set a per-series
    season length. The classes and call sequence are the production ones.
    """

    kind = "production"

    def __init__(self, model_name: str, season_length: int) -> None:
        self.name = model_name
        self.season_length = season_length
        self._adapter: Any = None

    def _new_adapter(self) -> Any:
        m, s = self.name, self.season_length
        if m == "naive":
            return NaiveAdapter()
        if m == "drift":
            return DriftAdapter()
        if m == "seasonal_naive":
            return SeasonalNaiveAdapter(season_length=s)
        if m == "auto_ets":
            return AutoETSAdapter(season_length=s)
        if m == "mean_ensemble":
            return MeanEnsembleAdapter(season_length=s)
        raise ValueError(f"not a production candidate: {m}")

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None:
        index = pd.DatetimeIndex(pd.to_datetime(train_times))
        x = pd.DataFrame(index=index)
        y = pd.Series(y_train, index=index)
        self._adapter = self._new_adapter()
        self._adapter.fit(x, y, as_of=index[-1].to_pydatetime())

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        pred = self._adapter.predict(horizon)
        point = np.asarray(pred.point_forecast, dtype=float)
        lower = np.asarray([iv.lower for iv in pred.intervals], dtype=float)
        upper = np.asarray([iv.upper for iv in pred.intervals], dtype=float)
        return point, lower, upper


def production_forecasters(season_length: int) -> list[ProductionAdapterForecaster]:
    """The five active production candidates, in registry order."""
    return [ProductionAdapterForecaster(name, season_length) for name in PRODUCTION_CANDIDATES]


# ---------------------------------------------------------------------------
# Walk-forward engine
# ---------------------------------------------------------------------------


def generate_origins(n: int, min_train: int, horizon: int, step: int) -> list[int]:
    """Expanding-window origin indices (train_end positions).

    Origin ``t`` fits on ``y[:t]`` and is scored on ``y[t:t+horizon]``;
    every origin satisfies ``t + horizon <= n`` (no leakage by construction).
    """
    if min_train < 1 or horizon < 1 or step < 1:
        raise ValueError("min_train, horizon and step must be positive")
    origins = []
    t = min_train
    while t + horizon <= n:
        origins.append(t)
        t += step
    return origins


@dataclass
class OriginOutcome:
    origin: int  # train_end index
    status: str  # "scored" | "backend_unavailable" | "error" | "invalid_output"
    detail: str = ""


@dataclass
class ModelSeriesResult:
    series_id: str
    model: str
    kind: str
    status: str  # "scored" | "partial" | "not_scorable"
    origins: list[OriginOutcome] = field(default_factory=list)
    metrics: dict[str, Any] | None = None

    @property
    def origins_attempted(self) -> int:
        return len(self.origins)

    @property
    def origins_scored(self) -> int:
        return sum(1 for o in self.origins if o.status == "scored")


def _validate_prediction(
    point: np.ndarray, lower: np.ndarray, upper: np.ndarray, horizon: int
) -> str | None:
    """Return an invalid-output reason, or None if the forecast is usable."""
    if not (len(point) == len(lower) == len(upper) == horizon):
        return (
            f"length mismatch: point={len(point)} lower={len(lower)} "
            f"upper={len(upper)} horizon={horizon}"
        )
    if not (np.all(np.isfinite(point)) and np.all(np.isfinite(lower)) and np.all(np.isfinite(upper))):
        return "non-finite values in forecast or intervals"
    if np.any(lower > upper):
        return "interval lower bound above upper bound"
    return None


def _mase_scale(y_train: np.ndarray, season_length: int) -> float | None:
    """In-sample seasonal-naive MAE of the training window (MASE denominator)."""
    m = season_length if len(y_train) > season_length else 1
    if len(y_train) <= m:
        return None
    scale = float(np.mean(np.abs(y_train[m:] - y_train[:-m])))
    return scale if scale > 0 else None


def _winkler_score(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray, alpha: float) -> float:
    """Mean Winkler interval score at level ``1 - alpha`` (lower is better)."""
    width = upper - lower
    below = actual < lower
    above = actual > upper
    score = width.copy()
    score[below] += (2.0 / alpha) * (lower[below] - actual[below])
    score[above] += (2.0 / alpha) * (actual[above] - upper[above])
    return float(np.mean(score))


def score_origins(
    series: SeriesData,
    actuals: list[np.ndarray],
    points: list[np.ndarray],
    lowers: list[np.ndarray],
    uppers: list[np.ndarray],
    scales: list[float | None],
) -> dict[str, Any]:
    """Pooled + per-step metrics over the scored origins of one model/series."""
    y = np.concatenate(actuals)
    p = np.concatenate(points)
    lo = np.concatenate(lowers)
    hi = np.concatenate(uppers)

    pooled_mae = mae(y, p)
    defined_scales = [s for s in scales if s is not None]
    mase_value = pooled_mae / float(np.mean(defined_scales)) if defined_scales else None

    per_step_mae: list[float] = []
    per_step_cov: list[float] = []
    for j in range(series.horizon):
        step_actual = np.array([a[j] for a in actuals])
        step_point = np.array([a[j] for a in points])
        step_lo = np.array([a[j] for a in lowers])
        step_hi = np.array([a[j] for a in uppers])
        per_step_mae.append(round(mae(step_actual, step_point), 6))
        per_step_cov.append(round(interval_coverage(step_actual, step_lo, step_hi), 6))

    coverage = interval_coverage(y, lo, hi)
    return {
        "n_points": int(len(y)),
        "mae": round(pooled_mae, 6),
        "rmse": round(rmse(y, p), 6),
        "mase": round(mase_value, 6) if mase_value is not None else None,
        "coverage_90": round(coverage, 6),
        "coverage_gap_vs_nominal": round(coverage - NOMINAL_COVERAGE, 6),
        "mean_interval_width": round(interval_width(lo, hi), 6),
        "winkler_90": round(_winkler_score(y, lo, hi, _INTERVAL_ALPHA), 6),
        "per_step_mae": per_step_mae,
        "per_step_coverage_90": per_step_cov,
    }


def run_walk_forward(series: SeriesData, forecaster: Forecaster) -> ModelSeriesResult:
    """Run one forecaster over every origin of one series, honestly."""
    result = ModelSeriesResult(
        series_id=series.series_id, model=forecaster.name, kind=forecaster.kind, status="not_scorable"
    )
    actuals: list[np.ndarray] = []
    points: list[np.ndarray] = []
    lowers: list[np.ndarray] = []
    uppers: list[np.ndarray] = []
    scales: list[float | None] = []

    for origin in generate_origins(len(series.values), series.min_train, series.horizon, series.step):
        y_train = series.values[:origin]
        y_true = series.values[origin : origin + series.horizon]
        try:
            forecaster.fit(y_train, series.times[:origin])
            point, lower, upper = forecaster.predict(series.horizon)
        except StatsForecastUnavailableError as exc:
            result.origins.append(OriginOutcome(origin, "backend_unavailable", str(exc)[:300]))
            continue
        except Exception as exc:  # a failed origin is data, not a crash
            result.origins.append(
                OriginOutcome(origin, "error", f"{type(exc).__name__}: {str(exc)[:300]}")
            )
            continue
        problem = _validate_prediction(point, lower, upper, series.horizon)
        if problem is not None:
            result.origins.append(OriginOutcome(origin, "invalid_output", problem))
            continue
        result.origins.append(OriginOutcome(origin, "scored"))
        actuals.append(y_true)
        points.append(point)
        lowers.append(lower)
        uppers.append(upper)
        scales.append(_mase_scale(y_train, series.season_length))

    if actuals:
        result.metrics = score_origins(series, actuals, points, lowers, uppers, scales)
        result.status = "scored" if len(actuals) == result.origins_attempted else "partial"
    return result


# ---------------------------------------------------------------------------
# Scorecard assembly
# ---------------------------------------------------------------------------


def environment_info() -> dict[str, Any]:
    """The environment this run happened in — part of the evidence."""
    import platform

    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "statsforecast_available": bool(_adapters_module.STATSFORECAST_AVAILABLE),
        "statsforecast_import_error": _adapters_module.STATSFORECAST_IMPORT_ERROR,
    }


def failure_summary(result: ModelSeriesResult) -> str | None:
    """Dominant failure description for a not-fully-scored result."""
    failures = [o for o in result.origins if o.status != "scored"]
    if not failures:
        return None
    kinds: dict[str, int] = {}
    for o in failures:
        kinds[o.status] = kinds.get(o.status, 0) + 1
    dominant = max(kinds, key=lambda k: kinds[k])
    example = next(o.detail for o in failures if o.status == dominant)
    parts = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
    return f"{parts}; dominant: {dominant} — {example}"


def build_scorecard(
    series_list: list[SeriesData],
    results: list[ModelSeriesResult],
    environment: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the machine-readable scorecard (JSON-serializable)."""
    return {
        "task": "TASK-FUT-004",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": environment,
        "protocol": {
            "design": "expanding-window walk-forward; fit on y[:origin], score on the next `horizon` observations; origins step by `step`",
            "interval_nominal_level": NOMINAL_COVERAGE,
            "metrics": [
                "mae",
                "rmse",
                "mase (pooled MAE / mean in-sample seasonal-naive MAE of the training windows)",
                "coverage_90 (empirical coverage of the nominal-90% intervals)",
                "coverage_gap_vs_nominal",
                "mean_interval_width",
                "winkler_90 (mean Winkler interval score, alpha=0.10; lower is better)",
                "per_step_mae",
                "per_step_coverage_90",
            ],
            "honesty_rules": [
                "a refused/failed/invalid origin is counted and classified, never replaced by a substitute forecast",
                "a model with zero scored origins is not_scorable and reports metrics=null",
                "reference baselines are harness-internal and labelled kind=reference; they are not production models",
            ],
        },
        "series": [
            {
                "id": s.series_id,
                "kind": s.kind,
                "rows": int(len(s.values)),
                "season_length": s.season_length,
                "horizon": s.horizon,
                "min_train": s.min_train,
                "step": s.step,
                "origins": len(generate_origins(len(s.values), s.min_train, s.horizon, s.step)),
                "sha256": s.sha256,
            }
            for s in series_list
        ],
        "results": [
            {
                "series_id": r.series_id,
                "model": r.model,
                "kind": r.kind,
                "status": r.status,
                "origins_attempted": r.origins_attempted,
                "origins_scored": r.origins_scored,
                "failure_summary": failure_summary(r),
                "metrics": r.metrics,
            }
            for r in results
        ],
    }


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    """Render the plain-language baseline scorecard."""
    env = scorecard["environment"]
    lines: list[str] = []
    lines.append("# Futuris forecast evaluation — BASELINE SCORECARD")
    lines.append("")
    lines.append("Generated by the TASK-FUT-004 walk-forward evaluation harness")
    lines.append("(`Futuris/futuris/evaluation/walkforward.py`, CLI:")
    lines.append("`Futuris/scripts/run_forecast_evaluation.py`) against the provenanced")
    lines.append("series in `Futuris/evaluation_data/` (see `PROVENANCE.json`).")
    lines.append("")
    lines.append(f"- Generated at (UTC): {scorecard['generated_at_utc']}")
    lines.append(
        f"- Environment: Python {env['python']}, numpy {env['numpy']}, pandas {env['pandas']}"
    )
    if env["statsforecast_available"]:
        lines.append("- statsforecast: AVAILABLE in this environment")
    else:
        lines.append(
            "- statsforecast: **NOT AVAILABLE** in this environment "
            f"({env['statsforecast_import_error']}) — the same state as the "
            "production fleet today (post-ARM install is an owner decision)."
        )
    lines.append("")

    lines.append("## The plain verdict")
    lines.append("")
    prod = [r for r in scorecard["results"] if r["kind"] == "production"]
    scored = [r for r in prod if r["status"] == "scored"]
    not_scorable = [r for r in prod if r["status"] == "not_scorable"]
    if not env["statsforecast_available"]:
        lines.append(
            "**The current production forecast path cannot be scored, because it cannot "
            "forecast at all in this environment.** Every one of the five production "
            "candidate adapters refuses to fit when `statsforecast` is not importable "
            "(the honest post-REL-018 behaviour), so there are no production forecasts "
            "to measure. Any accuracy or calibration number for the production path "
            "today would be fabricated; this scorecard reports none."
        )
    elif not_scorable:
        lines.append(
            f"{len(scored)} of {len(prod)} production model/series combinations scored; "
            f"{len(not_scorable)} could not be scored (reasons in the table)."
        )
    else:
        lines.append("All production model/series combinations scored; see tables below.")
    lines.append("")

    lines.append("## Series (provenance-verified by sha256 before scoring)")
    lines.append("")
    lines.append("| series | kind | rows | season | horizon | origins |")
    lines.append("|---|---|---|---|---|---|")
    for s in scorecard["series"]:
        lines.append(
            f"| {s['id']} | {s['kind']} | {s['rows']} | {s['season_length']} "
            f"| {s['horizon']} | {s['origins']} |"
        )
    lines.append("")

    for kind, title in (
        ("production", "Production candidate adapters (the path being judged)"),
        ("reference", "Harness reference baselines (NOT production — the bar to beat)"),
    ):
        lines.append(f"## {title}")
        lines.append("")
        lines.append(
            "| series | model | status | origins scored | MAE | RMSE | MASE | "
            "coverage@90 | gap vs 0.90 | mean width | Winkler@90 |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in scorecard["results"]:
            if r["kind"] != kind:
                continue
            m = r["metrics"] or {}
            lines.append(
                f"| {r['series_id']} | {r['model']} | {r['status']} "
                f"| {r['origins_scored']}/{r['origins_attempted']} "
                f"| {_fmt(m.get('mae'))} | {_fmt(m.get('rmse'))} | {_fmt(m.get('mase'))} "
                f"| {_fmt(m.get('coverage_90'))} | {_fmt(m.get('coverage_gap_vs_nominal'))} "
                f"| {_fmt(m.get('mean_interval_width'))} | {_fmt(m.get('winkler_90'))} |"
            )
        lines.append("")
        for r in scorecard["results"]:
            if r["kind"] == kind and r["failure_summary"]:
                lines.append(f"- `{r['model']}` on `{r['series_id']}`: {r['failure_summary']}")
        lines.append("")

    lines.append("## How Futuris will be judged when statsforecast lands")
    lines.append("")
    lines.append(
        "Re-run the identical command (`python3 scripts/run_forecast_evaluation.py` "
        "from `Futuris/`) in the environment where statsforecast is installed. Same "
        "series, same origins, same metrics — the production rows above fill in with "
        "real numbers. The bar set by this baseline: a production model earns a "
        "better-than-reference verdict on a series only if it beats the reference "
        "baselines on MASE *and* its empirical coverage@90 is at least as close to "
        "the nominal 0.90. A model whose intervals cover far below 0.90 is "
        "overconfident no matter how good its MAE looks."
    )
    lines.append("")
    lines.append("## Known limits of this harness (stated, not hidden)")
    lines.append("")
    lines.append(
        "- Three series is a floor, not a ceiling: one monthly, one daily, one "
        "synthetic 5-minute telemetry fixture shaped like production targets. "
        "More provenanced series can be added by vendoring the file and extending "
        "PROVENANCE.json."
    )
    lines.append(
        "- The pre-existing `futuris.evaluation.backtest.BacktestEngine` is a "
        "different instrument (pipeline-level, synthetic-connector data) and has "
        "a known honesty defect this harness deliberately does not repeat: when "
        "an actual observation is missing it substitutes the forecast itself as "
        "the actual (`actual_val = f.prediction`), manufacturing zero error. "
        "Fixing or retiring that engine is a follow-up task, not part of FUT-004."
    )
    lines.append(
        "- `auto_arima` is registered in the model registry but is not in the "
        "production active candidate list (`current_active()`), so it is out of "
        "scope for this baseline."
    )
    lines.append("")
    return "\n".join(lines)
