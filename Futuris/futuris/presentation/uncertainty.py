"""Plain-language uncertainty presentation for Futuris forecasts (TASK-FUT-008).

Every forecast Futuris serves — to FRIDAY, to Stratex, or to the owner —
must carry three things a reader can actually use:

1. **Its horizon**, in plain language ("the next 24 hours"), not a raw
   ``timedelta`` repr or a field that silently goes missing.
2. **Its method, honestly named.** The statsforecast adapters are named as
   statsforecast models *only* when the statsforecast backend is installed
   in this deployment. When it is not installed (the production reality
   until the ARM host lands), a stored forecast's model label is reported
   as a recorded label — never as a statsforecast run that happened here.
   Heuristic rules are named as heuristic rules.
3. **A calibrated uncertainty range in plain language**: the numeric range,
   the interval level it actually is (the adapters build 90% prediction
   intervals — ``z = 1.645`` over residual std in
   ``futuris/models/adapters.py``), and whether calibration for the target
   has ever been *measured* from resolved outcomes. An unmeasured range is
   the model's own estimate, and the presentation says so.

This module is deliberately dependency-free (stdlib only) so every surface
— delegation router, owner quick surfaces, canonical forecast API, market
API — can build the same presentation block, and so it can be unit-tested
without the service stack.

The block is additive: consumers that ignore ``presentation`` keep working.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

#: The adapters construct 90% prediction intervals (see
#: ``BaseStatsForecastAdapter._build_prediction``: ``z_90 = 1.645``).
#: Before TASK-FUT-008 no surface stated this level, so a reader could not
#: tell a 90% range from a 50% one.
INTERVAL_LEVEL_PCT = 90

_ADAPTER_METHODS: dict[str, tuple[str, str]] = {
    "naive": (
        "Naive persistence",
        "repeats the last observed value for every future step",
    ),
    "seasonal_naive": (
        "Seasonal naive",
        "repeats the most recent seasonal cycle",
    ),
    "drift": (
        "Drift (random walk with drift)",
        "extends the average historical rate of change",
    ),
    "auto_ets": (
        "AutoETS",
        "an automatic exponential-smoothing (ETS) state-space model",
    ),
    "auto_arima": (
        "AutoARIMA",
        "an automatically selected ARIMA model",
    ),
    "mean_ensemble": (
        "Mean ensemble",
        "the simple average of AutoETS and SeasonalNaive, with pooled intervals",
    ),
}

_HEURISTIC_METHOD = "Deterministic telemetry rule"
_HEURISTIC_DETAIL = (
    "a hand-rolled deterministic formula over live Stratex telemetry — "
    "not a statistical forecasting model, and not a statsforecast or GARCH run"
)


def _fmt(value: float) -> str:
    """Compact number formatting for prose (4 significant figures)."""
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return str(value)


def adapter_key(model_version: Any) -> str | None:
    """Extract the adapter key from a stored ``model_version`` label.

    Labels look like ``seasonal_naive@v1:c8f93a`` (optionally suffixed with
    ``:fallback_after_candidate_failures``) or
    ``heuristic:telemetry_vol_rule@v2``.
    """
    if not model_version:
        return None
    head = str(model_version).split("@", 1)[0]
    if head.startswith("heuristic"):
        return "heuristic"
    key = head.split(":", 1)[0].strip().lower()
    return key or None


def describe_method(
    model_version: Any, *, statsforecast_available: bool
) -> dict[str, Any]:
    """Honestly name the method behind a forecast.

    The word "statsforecast" is used only when the backend is installed in
    this deployment. A stored label recorded while the backend is absent is
    reported as exactly that — a recorded label — because claiming a
    statsforecast run in a deployment where the package is not installed is
    how Futuris previously served mock numbers as model output (TASK-REL-018).
    """
    key = adapter_key(model_version)
    if key == "heuristic":
        return {
            "method": _HEURISTIC_METHOD,
            "method_detail": _HEURISTIC_DETAIL,
            "backend": "none (rule-based)",
            "backend_available": True,
        }
    if key in _ADAPTER_METHODS:
        name, detail = _ADAPTER_METHODS[key]
        if statsforecast_available:
            return {
                "method": f"{name} (statsforecast)",
                "method_detail": f"{detail}, fitted by the statsforecast library",
                "backend": "statsforecast",
                "backend_available": True,
            }
        return {
            "method": f"{name} (recorded model label)",
            "method_detail": (
                f"the stored forecast is labelled {name}, which {detail}. "
                "The statsforecast backend is not installed in this "
                "deployment, so this number was not produced by a "
                "statsforecast run here and cannot be recomputed until the "
                "backend is installed"
            ),
            "backend": "statsforecast",
            "backend_available": False,
        }
    if key:
        return {
            "method": f"Recorded model label '{key}'",
            "method_detail": (
                "no plain-language description exists for this model label; "
                "Futuris reports the label as stored and does not invent one"
            ),
            "backend": "unknown",
            "backend_available": statsforecast_available,
        }
    return {
        "method": "Not recorded",
        "method_detail": (
            "this forecast carries no model label, so no method can be "
            "named for it; treat its numbers as unattributed"
        ),
        "backend": "unknown",
        "backend_available": statsforecast_available,
    }


def horizon_text(horizon: Any) -> str:
    """Render a horizon as plain language: ``24h``/``timedelta`` -> "24 hours"."""
    if horizon is None:
        return "an unspecified horizon"
    if isinstance(horizon, timedelta):
        seconds = horizon.total_seconds()
    elif isinstance(horizon, (int, float)):
        seconds = float(horizon)
    elif isinstance(horizon, str):
        text = horizon.strip().lower()
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|hr|d|day|w|wk)s?", text)
        if match:
            amount = float(match.group(1))
            unit = match.group(2)
            factor = {
                "s": 1,
                "sec": 1,
                "m": 60,
                "min": 60,
                "h": 3600,
                "hr": 3600,
                "d": 86400,
                "day": 86400,
                "w": 604800,
                "wk": 604800,
            }[unit]
            seconds = amount * factor
        elif text.startswith("p") and "t" in text:
            # ISO-8601 duration subset: PnDTnHnM
            days = re.search(r"(\d+(?:\.\d+)?)d", text)
            hours = re.search(r"(\d+(?:\.\d+)?)h", text)
            minutes = re.search(r"(\d+(?:\.\d+)?)m", text)
            seconds = (
                (float(days.group(1)) * 86400 if days else 0)
                + (float(hours.group(1)) * 3600 if hours else 0)
                + (float(minutes.group(1)) * 60 if minutes else 0)
            )
            if seconds == 0:
                return horizon
        else:
            # str(timedelta) forms like "1 day, 0:00:00" or "7 days, 0:00:00"
            day_match = re.match(r"(\d+)\s+days?", text)
            time_match = re.search(r"(\d+):(\d{2}):(\d{2})", text)
            if day_match or time_match:
                seconds = (int(day_match.group(1)) * 86400 if day_match else 0) + (
                    int(time_match.group(1)) * 3600
                    + int(time_match.group(2)) * 60
                    + int(time_match.group(3))
                    if time_match
                    else 0
                )
            else:
                return horizon
    else:
        return str(horizon)

    if seconds <= 0:
        return "an unspecified horizon"
    if seconds % 86400 == 0 and seconds > 86400:
        days = int(seconds // 86400)
        return f"{days} day" + ("s" if days != 1 else "")
    if seconds % 3600 == 0:
        hours = int(seconds // 3600)
        return f"{hours} hour" + ("s" if hours != 1 else "")
    if seconds % 60 == 0:
        minutes = int(seconds // 60)
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    return f"{_fmt(seconds)} seconds"


def calibration_clause(
    calibration_metrics: dict[str, Any] | None,
) -> tuple[str, str]:
    """(status, plain-language clause) from stored calibration metrics.

    Mirrors the honesty rule in ``friday._honest_calibration``: calibration
    counts as measured only when resolved outcomes exist *and* an ECE was
    computed from them. Anything else is "unmeasured", said plainly.
    """
    metrics = dict(calibration_metrics or {})
    raw_count = metrics.get("n_resolved_outcomes", metrics.get("sample_count", 0))
    try:
        resolved = int(raw_count or 0)
    except (TypeError, ValueError):
        resolved = 0
    ece = metrics.get("ece", metrics.get("ece_score"))
    has_ece = isinstance(ece, (int, float)) and not isinstance(ece, bool)
    if resolved > 0 and has_ece:
        return (
            "measured",
            f"Calibration has been measured from {resolved} resolved "
            f"forecast(s) for this target (ECE {_fmt(float(ece))}); past "
            "probabilities for this target have been checked against what "
            "actually happened.",
        )
    return (
        "unmeasured",
        "Calibration for this target is unmeasured — no resolved forecasts "
        "have been checked against outcomes yet — so treat the range as the "
        "model's own estimate, not a proven track record.",
    )


def _evidence_clause(evidence_class: Any) -> str:
    value = getattr(evidence_class, "value", evidence_class)
    text = str(value or "").lower()
    if text == "live":
        return "Its inputs are live measured data."
    if text in ("synthetic", ""):
        return (
            "Its inputs are synthetic/demo data, not live measurements — "
            "do not treat it as a reading of the real system."
        )
    return f"Its inputs are labelled '{text}'."


def forecast_presentation(
    *,
    target: str,
    horizon: Any,
    prediction: float,
    range_lower: float,
    range_upper: float,
    probability: float | None = None,
    confidence: Any = None,
    model_version: Any = None,
    calibration_metrics: dict[str, Any] | None = None,
    evidence_class: Any = None,
    statsforecast_available: bool,
    interval_level_pct: int | None = INTERVAL_LEVEL_PCT,
    calibration_status_override: str | None = None,
    calibration_clause_override: str | None = None,
) -> dict[str, Any]:
    """Build the presentation block for one forecast.

    ``interval_level_pct=None`` is for surfaces whose range is *not* a
    statistical prediction interval (e.g. the market rule bounds); the
    summary then says the range is a deterministic bound instead of
    dressing it up as a calibrated interval.
    """
    method = describe_method(model_version, statsforecast_available=statsforecast_available)
    h_text = horizon_text(horizon)
    if calibration_status_override is not None:
        cal_status = calibration_status_override
        cal_clause = calibration_clause_override or ""
    else:
        cal_status, cal_clause = calibration_clause(calibration_metrics)

    sentences = [
        f"Forecast for {target} over the next {h_text}: "
        f"most likely value {_fmt(prediction)}."
    ]
    if interval_level_pct is not None:
        sentences.append(
            f"The {interval_level_pct}% prediction range is "
            f"{_fmt(range_lower)} to {_fmt(range_upper)} — if the model is "
            f"well calibrated, the actual value should fall inside that "
            f"range about {interval_level_pct} times out of 100."
        )
    else:
        sentences.append(
            f"The stated range is {_fmt(range_lower)} to {_fmt(range_upper)}. "
            "That range is a deterministic rule bound, not a statistical "
            "prediction interval."
        )
    sentences.append(f"Method: {method['method']} — {method['method_detail']}.")
    if probability is not None:
        sentences.append(
            f"Estimated probability of the event in this horizon: "
            f"{float(probability) * 100:.4g}%."
        )
    if cal_clause:
        sentences.append(cal_clause)
    if evidence_class is not None:
        sentences.append(_evidence_clause(evidence_class))
    conf_value = getattr(confidence, "value", confidence)
    if conf_value:
        sentences.append(
            f"The '{str(conf_value).lower()}' confidence label describes "
            "trust in the model's calibration and data quality — it is not "
            "the probability of the event."
        )

    return {
        "horizon_text": h_text,
        "method": method["method"],
        "method_detail": method["method_detail"],
        "backend": method["backend"],
        "backend_available": method["backend_available"],
        "interval_level_pct": interval_level_pct,
        "uncertainty_range": {
            "lower": range_lower,
            "upper": range_upper,
            "level_pct": interval_level_pct,
        },
        "calibration_status": cal_status,
        "summary": " ".join(sentences),
    }


def scenario_presentation(
    *,
    horizon: Any,
    base_prediction: float,
    divergent_prediction: float,
    delta_pct: float,
    risk_assessment: str | None = None,
    monte_carlo: bool,
    range_lower: float | None = None,
    range_upper: float | None = None,
) -> dict[str, Any]:
    """Presentation block for a scenario (what-if) result.

    The scenario engine perturbs values through a dependency graph; it does
    not recompute the event probability. The summary says that, and says
    what the risk label is actually based on (the size of the change), so a
    reader cannot mistake the label for a measured likelihood.
    """
    h_text = horizon_text(horizon)
    if monte_carlo:
        method = "Monte Carlo scenario propagation"
        method_detail = (
            "the what-if changes are propagated through the operations "
            "dependency graph with Monte Carlo sampling; the engine "
            "perturbs values and does not recompute the event probability"
        )
    else:
        method = "Deterministic linear scenario propagation"
        method_detail = (
            "the what-if changes are propagated once through the operations "
            "dependency graph as a single hand-checkable calculation — no "
            "probability distribution, no spread, and no recomputed event "
            "probability"
        )
    sentences = [
        f"What-if scenario over the next {h_text}: the baseline estimate "
        f"{_fmt(base_prediction)} becomes {_fmt(divergent_prediction)} "
        f"({delta_pct:+.4g}%)."
    ]
    if range_lower is not None and range_upper is not None:
        sentences.append(
            f"Across the scenario's sampled outcomes, the middle spread "
            f"(p10–p90) is {_fmt(range_lower)} to {_fmt(range_upper)}."
        )
    sentences.append(f"Method: {method} — {method_detail}.")
    sentences.append(
        "Any probability shown with this scenario is the base forecast's "
        "probability, carried over unchanged — it was not recomputed for "
        "the scenario."
    )
    if risk_assessment:
        sentences.append(
            f"The '{risk_assessment}' label is based only on the size of "
            "the change versus the baseline, not on a recomputed "
            "probability."
        )
    return {
        "horizon_text": h_text,
        "method": method,
        "method_detail": method_detail,
        "backend": "scenario_dependency_graph",
        "backend_available": True,
        "interval_level_pct": None,
        "uncertainty_range": (
            {"lower": range_lower, "upper": range_upper, "level_pct": None}
            if range_lower is not None and range_upper is not None
            else None
        ),
        "calibration_status": "not_applicable",
        "probability_status": "not_recomputed_by_scenario_engine",
        "summary": " ".join(sentences),
    }


def blocked_presentation(*, target: str, horizon: Any, reason: str) -> dict[str, Any]:
    """Presentation block for a refused/blocked forecast: no numbers exist."""
    h_text = horizon_text(horizon)
    return {
        "horizon_text": h_text,
        "method": "None — no forecast was computed",
        "method_detail": reason,
        "backend": "none",
        "backend_available": False,
        "interval_level_pct": None,
        "uncertainty_range": None,
        "calibration_status": "unmeasured",
        "summary": (
            f"No forecast was computed for {target} over the next {h_text}. "
            f"{reason} Any number here would be fabricated, so none is given."
        ),
    }
