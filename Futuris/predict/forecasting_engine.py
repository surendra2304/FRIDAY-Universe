"""
Futuris/predict/forecasting_engine.py — Futuris Multi-Horizon Forecasting Engine.

Predicts future values across financial, weather, demand, energy, traffic, and
sentiment horizons. Supports confidence intervals, ensemble forecasting,
scenario analysis, and anomaly detection.

Fitted models (2026-11-24, TASK-FUT-026): the ensemble members are real
data-fitted methods computed from the input series only — persistence,
trailing means, and an OLS trend. No hash-derived values feed any prediction:
an earlier version generated each "model" curve from an md5 hash of the series
id (labels arima/prophet/lstm/elastic_net on hash-derived exponentials) and
added hash jitter to every forecast step. Those paths are removed. The
reported rmse is a measured one-step-ahead backtest RMSE of the fitted
ensemble, and intervals come from it. A scoring hook (score_forecast) records
an outcome against a filed forecast: absolute error + interval hit.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class TimeSeries:
    """A time series data point."""
    series_id: str
    name: str
    category: str  # financial, weather, demand, energy, traffic, sentiment
    values: list[float] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)
    frequency: str = "daily"  # hourly, daily, weekly, monthly, yearly


@dataclass
class ForecastResult:
    """Result of a forecast."""
    series_id: str
    forecast_id: str
    horizon: str  # short_term, medium_term, long_term
    horizon_periods: int
    predictions: list[float] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)
    confidence_lower: list[float] = field(default_factory=list)
    confidence_upper: list[float] = field(default_factory=list)
    confidence_level: float = 0.95
    rmse: float = 0.0
    model: str = "fitted_ensemble"
    created_at: float = 0.0


@dataclass
class ForecastScore:
    """Score of a filed forecast against its observed outcome."""
    forecast_id: str
    actual: float
    predicted: float
    absolute_error: float
    interval_hit: bool
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    scored_at: float = 0.0


@dataclass
class ScenarioResult:
    """Result of a scenario analysis."""
    scenario_id: str
    name: str
    description: str
    assumptions: list[str] = field(default_factory=list)
    predictions: list[float] = field(default_factory=list)
    impact: str = "neutral"  # positive, negative, neutral
    probability: float = 0.5


@dataclass
class AnomalyDetection:
    """A detected anomaly."""
    series_id: str
    value: float
    expected: float
    deviation: float
    severity: str  # low, medium, high
    detected_at: float = 0.0
    description: str = ""


@dataclass
class EnsembleForecast:
    """Ensemble forecast from multiple models."""
    series_id: str
    models: list[str] = field(default_factory=list)
    predictions: dict = field(default_factory=dict)  # model → predictions
    consensus: list[float] = field(default_factory=list)
    agreement: float = 0.0


class ForecastingEngine:
    """Multi-horizon forecasting engine."""

    def __init__(self):
        self._series: dict[str, TimeSeries] = {}
        self._forecasts: dict[str, ForecastResult] = {}
        self._scores: dict[str, ForecastScore] = {}
        self._scenarios: dict[str, ScenarioResult] = {}
        self._anomalies: list[AnomalyDetection] = []

    def add_series(
        self,
        name: str,
        category: str,
        values: list[float],
        frequency: str = "daily",
    ) -> TimeSeries:
        """Add a time series."""
        series = TimeSeries(
            series_id=hashlib.md5(
                f"series:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            category=category,
            values=values,
            timestamps=[time.time() + i * 86400 for i in range(len(values))],
            frequency=frequency,
        )
        self._series[series.series_id] = series
        return series

    def _fitted_members(
        self, values: list[float], horizon_periods: int
    ) -> dict[str, list[float]]:
        """Real data-fitted ensemble members, computed from the input series only.

        No hash-derived values: every member is a deterministic function of
        `values`, so the same series always yields the same members.
        """
        n = len(values)
        last = values[-1] if values else 100.0
        # Persistence: flat at the last observed value.
        persistence = [last] * horizon_periods
        # Trailing means: flat at the mean of the last 3 / 7 values.
        mean_3 = sum(values[-3:]) / len(values[-3:]) if values else last
        mean_7 = sum(values[-7:]) / len(values[-7:]) if values else last
        mean_3d = [mean_3] * horizon_periods
        mean_7d = [mean_7] * horizon_periods
        # OLS trend: least-squares fit of values vs index, extrapolated.
        if n >= 2:
            xs = list(range(n))
            mx = sum(xs) / n
            my = sum(values) / n
            denom = sum((x - mx) ** 2 for x in xs)
            slope = (
                sum((x - mx) * (v - my) for x, v in zip(xs, values)) / denom
                if denom
                else 0.0
            )
            intercept = my - slope * mx
            ols = [intercept + slope * (n + i) for i in range(horizon_periods)]
        else:
            ols = [last] * horizon_periods
        return {
            "persistence": persistence,
            "mean_3d": mean_3d,
            "mean_7d": mean_7d,
            "ols_trend": ols,
        }

    def _backtest_rmse(self, values: list[float]) -> float:
        """One-step-ahead backtest RMSE of the fitted ensemble.

        For each t >= 3, fit the members on values[:t] and predict values[t].
        Falls back to the std of first differences if too few points exist.
        This is a measured error, not a formula of the trend.
        """
        errors = []
        for t in range(3, len(values)):
            members = self._fitted_members(values[:t], 1)
            pred = sum(m[0] for m in members.values()) / len(members)
            errors.append(pred - values[t])
        if errors:
            return (sum(e * e for e in errors) / len(errors)) ** 0.5
        diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
        if diffs:
            mean_d = sum(diffs) / len(diffs)
            return (sum((d - mean_d) ** 2 for d in diffs) / len(diffs)) ** 0.5
        return 0.0

    def forecast(
        self,
        series_id: str,
        horizon: str,
        horizon_periods: int,
        confidence_level: float = 0.95,
    ) -> ForecastResult:
        """Generate a forecast from the fitted ensemble.

        Point forecast is the equal-weight consensus of the fitted members.
        Intervals come from the measured backtest RMSE, widening with horizon.
        """
        series = self._series.get(series_id)
        if not series:
            raise HTTPException(404, f"Series {series_id} not found")

        values = series.values
        members = self._fitted_members(values, horizon_periods)
        predictions = [
            sum(m[i] for m in members.values()) / len(members)
            for i in range(horizon_periods)
        ]
        rmse = self._backtest_rmse(values)

        z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence_level, 1.96)
        confidence_lower = [
            p - z * rmse * (i + 1) ** 0.5 for i, p in enumerate(predictions)
        ]
        confidence_upper = [
            p + z * rmse * (i + 1) ** 0.5 for i, p in enumerate(predictions)
        ]

        forecast = ForecastResult(
            series_id=series_id,
            forecast_id=hashlib.md5(
                f"forecast:{series_id}:{horizon}:{time.time()}".encode()
            ).hexdigest()[:12],
            horizon=horizon,
            horizon_periods=horizon_periods,
            predictions=predictions,
            timestamps=[time.time() + (i + 1) * 86400 for i in range(horizon_periods)],
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            confidence_level=confidence_level,
            rmse=rmse,
            model="fitted_ensemble",
            created_at=time.time(),
        )

        self._forecasts[forecast.forecast_id] = forecast
        return forecast

    def score_forecast(self, forecast_id: str, actual: float) -> ForecastScore:
        """Score a filed forecast against its observed outcome.

        Scores the first horizon step: absolute error and whether the actual
        fell inside the filed confidence interval. The score is stored so the
        outcome is scored exactly once per forecast id (re-scoring overwrites
        with the latest actual).
        """
        forecast = self._forecasts.get(forecast_id)
        if not forecast:
            raise HTTPException(404, f"Forecast {forecast_id} not found")
        if not forecast.predictions:
            raise HTTPException(400, "Forecast has no predictions to score")

        score = ForecastScore(
            forecast_id=forecast_id,
            actual=actual,
            predicted=forecast.predictions[0],
            absolute_error=abs(forecast.predictions[0] - actual),
            interval_hit=(
                forecast.confidence_lower[0] <= actual <= forecast.confidence_upper[0]
            ),
            confidence_lower=forecast.confidence_lower[0],
            confidence_upper=forecast.confidence_upper[0],
            scored_at=time.time(),
        )
        self._scores[forecast_id] = score
        return score

    def get_score(self, forecast_id: str) -> ForecastScore:
        """Read back a filed forecast's score."""
        score = self._scores.get(forecast_id)
        if not score:
            raise HTTPException(404, f"No score filed for forecast {forecast_id}")
        return score

    def ensemble_forecast(self, series_id: str, horizon_periods: int = 30) -> EnsembleForecast:
        """Run ensemble forecast from the fitted members."""
        series = self._series.get(series_id)
        if not series:
            raise HTTPException(404, f"Series {series_id} not found")

        members = self._fitted_members(series.values, horizon_periods)
        all_predictions = list(members.values())

        # Consensus (average)
        consensus = [
            sum(p[i] for p in all_predictions) / len(all_predictions)
            for i in range(horizon_periods)
        ]

        # Agreement (1 - normalized variance)
        base = series.values[-1] if series.values else 100.0
        variances = [
            sum((p[i] - consensus[i]) ** 2 for p in all_predictions) / len(all_predictions)
            for i in range(horizon_periods)
        ]
        avg_var = sum(variances) / max(1, len(variances))
        agreement = max(0, 1 - avg_var / (base ** 2))

        return EnsembleForecast(
            series_id=series_id,
            models=list(members.keys()),
            predictions=members,
            consensus=consensus,
            agreement=agreement,
        )

    def analyze_scenario(
        self,
        series_id: str,
        name: str,
        description: str,
        assumptions: list[str],
        horizon_periods: int = 30,
    ) -> ScenarioResult:
        """Analyze a scenario."""
        series = self._series.get(series_id)
        if not series:
            raise HTTPException(404, f"Series {series_id} not found")

        base = series.values[-1] if series.values else 100.0

        # Adjust predictions based on assumptions
        adjustment = 0.0
        for a in assumptions:
            a_lower = a.lower()
            if any(w in a_lower for w in ["growth", "increase", "positive", "boom"]):
                adjustment += 0.05
            elif any(w in a_lower for w in ["decline", "decrease", "negative", "recession"]):
                adjustment -= 0.05

        predictions = [base * (1 + adjustment) ** (i + 1) for i in range(horizon_periods)]

        impact = "positive" if adjustment > 0.01 else "negative" if adjustment < -0.01 else "neutral"
        probability = 0.5 + adjustment  # Higher adjustment → higher probability

        scenario = ScenarioResult(
            scenario_id=hashlib.md5(
                f"scenario:{series_id}:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            description=description,
            assumptions=assumptions,
            predictions=predictions,
            impact=impact,
            probability=min(0.99, max(0.01, probability)),
        )

        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def detect_anomalies(self, series_id: str) -> list[AnomalyDetection]:
        """Detect anomalies in a time series."""
        series = self._series.get(series_id)
        if not series:
            raise HTTPException(404, f"Series {series_id} not found")

        anomalies = []
        values = series.values

        if len(values) < 3:
            return anomalies

        # Simple anomaly detection: z-score
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5

        for i, value in enumerate(values):
            z_score = abs(value - mean) / max(1, std)
            if z_score > 2.5:
                anomalies.append(AnomalyDetection(
                    series_id=series_id,
                    value=value,
                    expected=mean,
                    deviation=z_score,
                    severity="high" if z_score > 3 else "medium",
                    detected_at=series.timestamps[i],
                    description=f"Value {value:.2f} deviates {z_score:.1f}σ from mean",
                ))

        self._anomalies.extend(anomalies)
        return anomalies

    def get_report(self) -> dict:
        """Get forecasting report."""
        return {
            "total_series": len(self._series),
            "total_forecasts": len(self._forecasts),
            "total_scores": len(self._scores),
            "total_scenarios": len(self._scenarios),
            "total_anomalies": len(self._anomalies),
            "categories": {
                cat: sum(1 for s in self._series.values() if s.category == cat)
                for cat in set(s.category for s in self._series.values())
            },
            "recent_forecasts": [
                {
                    "series": s.name,
                    "category": s.category,
                    "horizon": f.horizon,
                    "rmse": f.rmse,
                }
                for f in list(self._forecasts.values())[-5:]
                if (s := self._series.get(f.series_id)) is not None
            ],
        }


# Module-level singleton
forecasting_engine = ForecastingEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/futuris/forecast/series")
async def add_series(payload: dict):
    """Add a time series."""
    series = forecasting_engine.add_series(
        name=payload["name"],
        category=payload["category"],
        values=payload["values"],
        frequency=payload.get("frequency", "daily"),
    )
    return {"series_id": series.series_id, "name": series.name, "points": len(series.values)}


@router.post("/api/v1/futuris/forecast/{series_id}/predict")
async def forecast(series_id: str, payload: dict):
    """Generate a forecast."""
    result = forecasting_engine.forecast(
        series_id=series_id,
        horizon=payload.get("horizon", "medium_term"),
        horizon_periods=payload.get("horizon_periods", 30),
        confidence_level=payload.get("confidence_level", 0.95),
    )
    return {
        "forecast_id": result.forecast_id,
        "horizon": result.horizon,
        "predictions": result.predictions,
        "confidence_lower": result.confidence_lower,
        "confidence_upper": result.confidence_upper,
        "rmse": result.rmse,
    }


@router.post("/api/v1/futuris/forecast/{series_id}/score")
async def score_forecast(forecast_id: str, payload: dict):
    """Score a filed forecast against its observed outcome."""
    score = forecasting_engine.score_forecast(forecast_id, float(payload["actual"]))
    return score.__dict__


@router.get("/api/v1/futuris/forecast/{forecast_id}/score")
async def get_score(forecast_id: str):
    """Read back a filed forecast's score."""
    return forecasting_engine.get_score(forecast_id).__dict__


@router.post("/api/v1/futuris/forecast/{series_id}/ensemble")
async def ensemble_forecast(series_id: str, horizon_periods: int = 30):
    """Run ensemble forecast."""
    result = forecasting_engine.ensemble_forecast(series_id, horizon_periods)
    return {
        "models": result.models,
        "predictions": result.predictions,
        "consensus": result.consensus,
        "agreement": result.agreement,
    }


@router.post("/api/v1/futuris/forecast/{series_id}/scenarios")
async def analyze_scenario(series_id: str, payload: dict):
    """Analyze a scenario."""
    result = forecasting_engine.analyze_scenario(
        series_id=series_id,
        name=payload["name"],
        description=payload["description"],
        assumptions=payload["assumptions"],
        horizon_periods=payload.get("horizon_periods", 30),
    )
    return {
        "scenario_id": result.scenario_id,
        "impact": result.impact,
        "probability": result.probability,
        "predictions": result.predictions,
    }


@router.get("/api/v1/futuris/forecast/{series_id}/anomalies")
async def detect_anomalies(series_id: str):
    """Detect anomalies in a time series."""
    anomalies = forecasting_engine.detect_anomalies(series_id)
    return [a.__dict__ for a in anomalies]


@router.get("/api/v1/futuris/forecast/report")
async def get_report():
    """Get forecasting report."""
    return forecasting_engine.get_report()
