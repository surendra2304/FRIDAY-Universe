"""Live forecast-vs-actual tracker (TASK-FUT-006).

Futuris already *stores* every forecast it issues (the ``forecasts`` table,
written by ``ForecastRepository.create`` on every issuance path) and the
calibration sweep already *resolves* expired forecasts into the ``outcomes``
table. What was missing is the scoring layer in between: nobody compared
the stored prediction with the landed actual, so ``/v1/futuris/accuracy``
could only ever answer ``insufficient_data`` and interval calibration was
never measured on live forecasts at all. This module is that layer -- the
live, ongoing counterpart to TASK-FUT-004's offline walk-forward harness.

What it does:

* :func:`score_forecast` -- pure per-forecast scoring: signed/absolute
  error, interval hit, interval width, and the Winkler interval score,
  against the interval's *nominal level* (see :func:`derive_nominal_level`).
* :class:`ForecastTracker` -- the ongoing store. ``score_resolved`` sweeps
  every resolved forecast that has a numeric actual and no score row yet
  and persists one ``forecast_scores`` row per forecast (issuance snapshot
  + measured error). ``calibration_report`` aggregates the store into the
  rolling calibration picture: MAE/RMSE, empirical coverage vs the nominal
  level, mean width, mean Winkler -- overall, per nominal level, per
  target, and per evidence class.

Shared schema with TASK-FUT-004 (one scoring language, no duplication):
the nominal level is 0.90 (the production adapters emit nominal-90%
intervals, ``z = 1.645`` in ``BaseStatsForecastAdapter._build_prediction``),
metric keys match the harness scorecard (``mae``, ``rmse``,
``coverage_90``, ``coverage_gap_vs_nominal``, ``mean_interval_width``,
``winkler_90``), aggregates are computed with the shared
``futuris.evaluation.metrics`` functions, and the Winkler definition is
identical (``alpha = 1 - level``; overshoot penalised by ``2/alpha``).

Honesty rules (the FUT-002/003/004 standard):

* A forecast whose outcome has no numeric ``observed_value`` (event-only
  resolutions) is *not scorable*: it is counted as skipped, never scored
  as zero error, and never given a substituted actual.
* A forecast with no outcome yet is simply absent from the store -- the
  tracker never invents actuals.
* The calibration report calls itself ``insufficient_data`` with null
  metrics below :data:`MIN_REPORT_SAMPLES` scored forecasts; the count is
  always reported, so a small sample can never masquerade as a verdict.
* Provenance is never blended silently: every score row snapshots the
  forecast's ``evidence_class`` and the report breaks aggregates down by
  it, so synthetic/demo forecasts cannot inflate the live record.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from futuris.core.schemas import Forecast, Outcome
from futuris.evaluation.metrics import interval_coverage, interval_width, mae, rmse
from futuris.storage.models import ForecastScoreModel
from futuris.storage.score_repository import ForecastScoreRepository

#: Nominal level of the prediction intervals the production adapters emit
#: (z = 1.645 in ``BaseStatsForecastAdapter._build_prediction``). Shared
#: with TASK-FUT-004's offline harness (``NOMINAL_COVERAGE`` there).
DEFAULT_NOMINAL_LEVEL = 0.90

#: Minimum scored forecasts before the calibration report will call itself
#: "measured". Below this it reports ``insufficient_data`` and null metrics.
MIN_REPORT_SAMPLES = 30

#: |empirical coverage - nominal level| within this band reads "calibrated".
CALIBRATION_TOLERANCE = 0.05

TRACKER_VERSION = "fut006-forecast-tracker/1.0"

#: Percentile pairs in ``Forecast.predictive_distribution`` that pin the
#: nominal level of the stored range, widest (most standard) first.
_PERCENTILE_PAIRS: tuple[tuple[str, str, float], ...] = (
    ("p5", "p95", 0.90),
    ("p10", "p90", 0.80),
    ("p25", "p75", 0.50),
)


def derive_nominal_level(forecast: Forecast) -> tuple[float, str]:
    """Nominal level of a stored forecast's interval, with its source.

    The stored ``range_lower``/``range_upper`` carry no level column, so the
    level is recovered from the forecast's own predictive distribution when
    it records the percentile pair the range was built from (p5/p95 ->
    0.90, p10/p90 -> 0.80, p25/p75 -> 0.50). Otherwise the production
    adapters' documented nominal level (0.90) applies. The source is
    returned alongside and persisted on every score row, so an assumed
    level is always labelled as assumed -- never silently treated as
    recorded fact.
    """
    dist = forecast.predictive_distribution or {}
    for lower_key, upper_key, level in _PERCENTILE_PAIRS:
        if lower_key in dist and upper_key in dist:
            return level, f"predictive_distribution:{lower_key}/{upper_key}"
    return DEFAULT_NOMINAL_LEVEL, "adapter_default"


def winkler_score(actual: float, lower: float, upper: float, level: float) -> float:
    """Winkler interval score for one observation (lower is better).

    Same definition as TASK-FUT-004's harness: the interval width, plus
    ``2/alpha`` times the overshoot when the actual falls outside the
    interval, with ``alpha = 1 - level``.
    """
    alpha = 1.0 - level
    width = upper - lower
    if actual < lower:
        return width + (2.0 / alpha) * (lower - actual)
    if actual > upper:
        return width + (2.0 / alpha) * (actual - upper)
    return width


@dataclass(frozen=True)
class ForecastScore:
    """One scored forecast: the issuance snapshot plus the measured error."""

    forecast_id: UUID
    target: str
    model_version: str
    evidence_class: str
    confidence: str
    as_of: datetime
    horizon_seconds: float
    expires_at: datetime
    prediction: float
    range_lower: float
    range_upper: float
    nominal_level: float
    nominal_level_source: str
    observed_value: float
    resolved_at: datetime
    signed_error: float
    abs_error: float
    pct_error: float | None
    interval_hit: bool
    interval_width: float
    winkler: float
    scored_at: datetime

    def to_model(self) -> ForecastScoreModel:
        return ForecastScoreModel(
            score_id=uuid4(),
            forecast_id=self.forecast_id,
            target=self.target,
            model_version=self.model_version,
            evidence_class=self.evidence_class,
            confidence=self.confidence,
            as_of=self.as_of,
            horizon_seconds=self.horizon_seconds,
            expires_at=self.expires_at,
            prediction=self.prediction,
            range_lower=self.range_lower,
            range_upper=self.range_upper,
            nominal_level=self.nominal_level,
            nominal_level_source=self.nominal_level_source,
            observed_value=self.observed_value,
            resolved_at=self.resolved_at,
            signed_error=self.signed_error,
            abs_error=self.abs_error,
            pct_error=self.pct_error,
            interval_hit=self.interval_hit,
            interval_width=self.interval_width,
            winkler=self.winkler,
            scored_at=self.scored_at,
        )


def score_forecast(
    forecast: Forecast, outcome: Outcome, *, scored_at: datetime | None = None
) -> ForecastScore | None:
    """Score one resolved forecast against its landed actual.

    Returns ``None`` when the outcome carries no numeric observed value
    (event-only resolution): such a forecast is not scorable as a numeric
    forecast-vs-actual pair, and the caller counts it as skipped rather
    than recording a fabricated zero error.
    """
    if outcome.observed_value is None:
        return None
    level, level_source = derive_nominal_level(forecast)
    observed = float(outcome.observed_value)
    signed = observed - forecast.prediction
    abs_err = abs(signed)
    pct = (abs_err / abs(observed) * 100.0) if observed != 0 else None
    return ForecastScore(
        forecast_id=forecast.forecast_id,
        target=forecast.target,
        model_version=forecast.model_version,
        evidence_class=forecast.evidence_class.value,
        confidence=forecast.confidence.value,
        as_of=forecast.as_of,
        horizon_seconds=forecast.horizon.total_seconds(),
        expires_at=forecast.expires_at,
        prediction=forecast.prediction,
        range_lower=forecast.range_lower,
        range_upper=forecast.range_upper,
        nominal_level=level,
        nominal_level_source=level_source,
        observed_value=observed,
        resolved_at=outcome.resolved_at,
        signed_error=signed,
        abs_error=abs_err,
        pct_error=pct,
        interval_hit=forecast.range_lower <= observed <= forecast.range_upper,
        interval_width=forecast.range_upper - forecast.range_lower,
        winkler=winkler_score(
            observed, forecast.range_lower, forecast.range_upper, level
        ),
        scored_at=scored_at or datetime.now(UTC),
    )


def _coverage_key(level: float) -> str:
    return f"coverage_{int(round(level * 100))}"


def _winkler_key(level: float) -> str:
    return f"winkler_{int(round(level * 100))}"


def _group_metrics(rows: list[ForecastScoreModel]) -> dict[str, Any]:
    """Headline metrics for one homogeneous group of score rows.

    Coverage and Winkler are computed over the group's dominant nominal
    level (mixed levels would make a single coverage number meaningless);
    MAE/RMSE/width span the whole group. Keys match TASK-FUT-004's
    scorecard for the 0.90 level.
    """
    actuals = [r.observed_value for r in rows]
    preds = [r.prediction for r in rows]
    lowers = [r.range_lower for r in rows]
    uppers = [r.range_upper for r in rows]
    level_counts = Counter(r.nominal_level for r in rows)
    dominant_level = max(
        sorted(level_counts), key=lambda lv: (level_counts[lv], lv)
    )
    at_level = [r for r in rows if r.nominal_level == dominant_level]
    coverage = interval_coverage(
        [r.observed_value for r in at_level],
        [r.range_lower for r in at_level],
        [r.range_upper for r in at_level],
    )
    pcts = [r.pct_error for r in rows if r.pct_error is not None]
    return {
        "n": len(rows),
        "mae": round(mae(actuals, preds), 6),
        "rmse": round(rmse(actuals, preds), 6),
        "nominal_level": dominant_level,
        _coverage_key(dominant_level): round(coverage, 6),
        "coverage_gap_vs_nominal": round(coverage - dominant_level, 6),
        "mean_interval_width": round(interval_width(lowers, uppers), 6),
        _winkler_key(dominant_level): round(
            sum(r.winkler for r in at_level) / len(at_level), 6
        ),
        "mean_pct_error": round(sum(pcts) / len(pcts), 6) if pcts else None,
    }


def _verdict(gap: float) -> str:
    if gap < -CALIBRATION_TOLERANCE:
        return "overconfident"  # intervals cover less than promised: too narrow
    if gap > CALIBRATION_TOLERANCE:
        return "underconfident"  # intervals cover more than promised: too wide
    return "calibrated"


def build_calibration_report(
    rows: list[ForecastScoreModel],
    *,
    target: str | None = None,
    evidence_class: str | None = None,
    min_samples: int = MIN_REPORT_SAMPLES,
) -> dict[str, Any]:
    """Assemble the rolling calibration report from score rows (pure).

    Below ``min_samples`` the headline is ``insufficient_data`` with null
    metrics and no verdict -- the count is the only claim. Per-group
    breakdowns always carry their own ``n`` so a thin group is visible as
    thin wherever its numbers appear.
    """
    report: dict[str, Any] = {
        "task": "TASK-FUT-006",
        "tracker_version": TRACKER_VERSION,
        "kind": "live_forecast_vs_actual",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filters": {"target": target, "evidence_class": evidence_class},
        "min_samples": min_samples,
        "n_scored": len(rows),
        "status": "insufficient_data",
        "metrics": None,
        "verdict": None,
        "by_nominal_level": {},
        "by_target": {},
        "by_evidence_class": {},
        "honesty": [
            "scores are computed only from recorded outcomes; a forecast "
            "with no outcome is absent, never assigned a substituted actual",
            "event-only outcomes (no numeric observed value) are excluded "
            "from numeric scoring; the sweep reports their count separately",
            "aggregates below min_samples report insufficient_data with "
            "null metrics; the scored count is always shown",
            "evidence classes are reported separately; synthetic/demo "
            "scores never blend into a live-only report unless requested",
        ],
    }
    if not rows:
        return report

    by_level: dict[str, dict[str, Any]] = {}
    level_groups: dict[float, list[ForecastScoreModel]] = {}
    for r in rows:
        level_groups.setdefault(r.nominal_level, []).append(r)
    for level in sorted(level_groups):
        group = level_groups[level]
        cov = interval_coverage(
            [r.observed_value for r in group],
            [r.range_lower for r in group],
            [r.range_upper for r in group],
        )
        by_level[f"{level:.2f}"] = {
            "n": len(group),
            _coverage_key(level): round(cov, 6),
            "coverage_gap_vs_nominal": round(cov - level, 6),
            f"mean_{_winkler_key(level)}": round(
                sum(r.winkler for r in group) / len(group), 6
            ),
        }
    report["by_nominal_level"] = by_level

    def _breakdown(attr: str) -> dict[str, Any]:
        groups: dict[str, list[ForecastScoreModel]] = {}
        for r in rows:
            groups.setdefault(str(getattr(r, attr)), []).append(r)
        return {name: _group_metrics(groups[name]) for name in sorted(groups)}

    report["by_target"] = _breakdown("target")
    report["by_evidence_class"] = _breakdown("evidence_class")

    if len(rows) >= min_samples:
        metrics = _group_metrics(rows)
        report["status"] = "measured"
        report["metrics"] = metrics
        report["verdict"] = _verdict(metrics["coverage_gap_vs_nominal"])
    return report


class ForecastTracker:
    """The live scoring store: sweeps resolved forecasts, serves reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.score_repo = ForecastScoreRepository(session)

    async def score_resolved(self, *, limit: int = 500) -> dict[str, int]:
        """Score every resolved forecast that has no score row yet.

        Idempotent -- a forecast is scored exactly once (unique
        ``forecast_id``), so the sweep may run on any cadence and overlaps
        are harmless. The first pass also backfills historically resolved
        forecasts, so the store covers the full resolved record, not just
        forecasts resolved after this tracker landed.
        """
        pairs = await self.score_repo.list_unscored_resolved(limit=limit)
        scored = 0
        skipped_no_numeric_actual = 0
        for forecast, outcome in pairs:
            score = score_forecast(forecast, outcome)
            if score is None:
                skipped_no_numeric_actual += 1
                continue
            await self.score_repo.record_score(score.to_model())
            scored += 1
        return {
            "considered": len(pairs),
            "scored": scored,
            "skipped_no_numeric_actual": skipped_no_numeric_actual,
            # State count, not work done: event-only resolutions are never
            # numerically scorable, so they stay out of the work queue and
            # are reported here for visibility instead of being re-skipped
            # on every sweep.
            "event_only_resolved": await self.score_repo.count_event_only_resolved(),
        }

    async def calibration_report(
        self,
        *,
        target: str | None = None,
        evidence_class: str | None = None,
        min_samples: int = MIN_REPORT_SAMPLES,
    ) -> dict[str, Any]:
        """Rolling calibration over everything the tracker has scored."""
        rows = await self.score_repo.list_scores(
            target=target, evidence_class=evidence_class
        )
        return build_calibration_report(
            rows,
            target=target,
            evidence_class=evidence_class,
            min_samples=min_samples,
        )
