"""
cortex_api/predictive_analytics.py — Cortex Predictive Analytics Engine.

Extends Cortex's capabilities with:
1. Time Series Forecasting: predict future metrics
2. Trend Analysis: detect and extrapolate trends
3. Seasonality Detection: identify seasonal patterns
4. Anomaly Prediction: predict when anomalies will occur
5. Demand Forecasting: predict product/service demand
6. Customer Behavior Prediction: predict future customer actions
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_api.config import get_db_session
from cortex_api.auth import Role, require_role
from cortex_api.provenance import (
    CALLER_SUPPLIED,
    DERIVED,
    ROUTE_DEFAULT,
    build_provenance,
    input_record,
)

router = APIRouter()


def _history_input(name: str, history: list[float]) -> dict[str, Any]:
    """Provenance record for a caller-supplied series (capped at 50 points)."""
    value: Any = list(history) if len(history) <= 50 else f"{len(history)} points (truncated in provenance)"
    return input_record(name, value, CALLER_SUPPLIED)


@dataclass
class TimeSeriesData:
    """Time series data point."""
    timestamp: float
    value: float
    category: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ForecastResult:
    """Forecast result."""
    metric_name: str
    forecast: list[float]
    confidence_lower: list[float]
    confidence_upper: list[float]
    accuracy: float
    trend: str  # upward, downward, stable
    seasonality: bool
    # TASK-COR-002: provenance block — see cortex_api/provenance.py.
    provenance: dict = field(default_factory=dict)


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric_name: str
    trend_direction: str
    trend_strength: float
    momentum: float
    projected_value: float
    projected_time: float
    confidence: float
    provenance: dict = field(default_factory=dict)


@dataclass
class DemandForecast:
    """Demand forecast."""
    product_id: str
    current_demand: float
    forecasted_demand: float
    growth_rate: float
    confidence: float
    seasonal_factor: float
    recommendation: str
    provenance: dict = field(default_factory=dict)


class PredictiveAnalytics:
    """Predictive analytics engine."""

    def __init__(self):
        self._forecasts: dict[str, ForecastResult] = {}
        self._trends: dict[str, TrendAnalysis] = {}
        self._demand_forecasts: dict[str, DemandForecast] = {}

    # ── Time Series Forecasting ──────────────────────────────────────────────

    def forecast(
        self,
        metric_name: str,
        history: list[float],
        steps: int = 7,
    ) -> ForecastResult:
        """Forecast future values using simple moving average + trend."""
        if len(history) < 3:
            return ForecastResult(
                metric_name=metric_name,
                forecast=[history[-1]] * steps if history else [],
                confidence_lower=[0.0] * steps,
                confidence_upper=[0.0] * steps,
                accuracy=0.0,
                trend="stable",
                seasonality=False,
                provenance=build_provenance(
                    inputs=[_history_input("history", history)],
                    confidence=None,
                    confidence_basis=(
                        "Fewer than 3 history points: no fit is attempted, "
                        "accuracy is 0.0 and the forecast repeats the last "
                        "observed value (or is empty)."
                    ),
                    data_status="no_data" if not history else "estimated_from_inputs",
                ),
            )

        # Calculate trend
        n = len(history)
        x_mean = sum(range(n)) / n
        y_mean = sum(history) / n

        numerator = sum((i - x_mean) * (h - y_mean) for i, h in enumerate(history))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / max(1e-10, denominator)

        intercept = y_mean - slope * x_mean

        # Forecast
        forecast = []
        for i in range(steps):
            idx = n + i
            forecast.append(max(0, intercept + slope * idx))

        # Confidence intervals
        # Calculate residuals
        residuals = [history[i] - (intercept + slope * i) for i in range(n)]
        std = math.sqrt(sum(r ** 2 for r in residuals) / n)

        lower = [f - std * 1.96 for f in forecast]
        upper = [f + std * 1.96 for f in forecast]

        # Accuracy (simplified: 1 - std/mean)
        accuracy = max(0.0, 1.0 - std / max(1.0, y_mean))

        # Trend
        if slope > 0.01:
            trend = "upward"
        elif slope < -0.01:
            trend = "downward"
        else:
            trend = "stable"

        # Seasonality detection
        seasonality = self._detect_seasonality(history)

        result = ForecastResult(
            metric_name=metric_name,
            forecast=forecast,
            confidence_lower=lower,
            confidence_upper=upper,
            accuracy=accuracy,
            trend=trend,
            seasonality=seasonality,
            provenance=build_provenance(
                inputs=[
                    _history_input("history", history),
                    input_record("steps", steps, CALLER_SUPPLIED),
                    input_record("ols_slope", slope, DERIVED),
                    input_record("residual_std", std, DERIVED),
                ],
                confidence=None,
                confidence_basis=(
                    "Model: ordinary least squares linear trend on the point "
                    "index. 'accuracy' = 1 - (in-sample residual std / mean of "
                    "history): it measures FIT to the supplied history, NOT "
                    "out-of-sample forecast accuracy. Intervals are forecast "
                    "+/- 1.96 x residual std. 'seasonality' is a level-shift "
                    "heuristic (first-half vs second-half mean differs by "
                    ">20%), NOT a periodic-pattern test."
                ),
                data_status="estimated_from_inputs",
            ),
        )

        self._forecasts[metric_name] = result
        return result

    def _detect_seasonality(self, history: list[float]) -> bool:
        """Detect if data has seasonality."""
        if len(history) < 7:
            return False

        # Compare first half and second half
        mid = len(history) // 2
        first_half = history[:mid]
        second_half = history[mid:]

        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)

        # If they differ significantly, might have seasonality
        diff = abs(first_mean - second_mean) / max(1.0, first_mean)
        return diff > 0.2

    # ── Trend Analysis ──────────────────────────────────────────────────────

    def analyze_trend(
        self,
        metric_name: str,
        history: list[float],
        project_days: float = 30.0,
    ) -> TrendAnalysis:
        """Analyze trend and project future values."""
        if len(history) < 2:
            return TrendAnalysis(
                metric_name=metric_name,
                trend_direction="stable",
                trend_strength=0.0,
                momentum=0.0,
                projected_value=history[-1] if history else 0.0,
                projected_time=project_days,
                confidence=0.0,
                provenance=build_provenance(
                    inputs=[_history_input("history", history)],
                    confidence=0.0,
                    confidence_basis="Fewer than 2 history points: no trend is computed.",
                    data_status="no_data",
                ),
            )

        # Calculate recent change
        recent_change = history[-1] - history[-2]
        pct_change = recent_change / max(1.0, history[-2])

        # Calculate momentum (average of last 3 changes)
        changes = []
        for i in range(1, min(4, len(history))):
            changes.append(history[-i] - history[-i-1])
        momentum = sum(changes) / len(changes) if changes else 0.0

        # Trend strength
        trend_strength = abs(pct_change)

        # Project
        projected = history[-1] + momentum * (project_days / 1.0)

        # Confidence
        confidence = min(0.9, 0.3 + abs(pct_change) * 5)

        return TrendAnalysis(
            metric_name=metric_name,
            trend_direction="upward" if pct_change > 0.02 else "downward" if pct_change < -0.02 else "stable",
            trend_strength=trend_strength,
            momentum=momentum,
            projected_value=projected,
            projected_time=project_days,
            confidence=confidence,
            provenance=build_provenance(
                inputs=[
                    _history_input("history", history),
                    input_record("last_step_pct_change", pct_change, DERIVED),
                    input_record("project_days", project_days, CALLER_SUPPLIED),
                ],
                confidence=confidence,
                confidence_basis=(
                    "confidence = min(0.9, 0.3 + 5 x |last-step % change|). "
                    "It depends ONLY on the final step of the supplied "
                    "history; it is a heuristic, not a calibrated probability."
                ),
                data_status="estimated_from_inputs",
            ),
        )

    # ── Seasonality Detection ────────────────────────────────────────────────

    def detect_seasonal_pattern(
        self,
        history: list[float],
        period: int = 7,
    ) -> dict[str, Any]:
        """Detect seasonal patterns."""
        # TASK-COR-002: this detector compares WHOLE-period averages, so it
        # can only see level differences between consecutive periods — it
        # structurally cannot detect a pattern that repeats WITHIN a period
        # (production probe 2026-11-15: a perfect [5, 9] x 4 series at
        # period 2 returned has_seasonality=false, CV 0.0). The statistic
        # is unchanged; the provenance states exactly what was computed so
        # the output is no longer read as a general seasonality verdict.
        _basis = (
            "Compares the means of consecutive whole periods: "
            "has_seasonality = (std of period means / overall mean) > 0.15. "
            "Detects level shifts BETWEEN periods only; a pattern repeating "
            "within a period is invisible to this statistic."
        )
        if len(history) < period * 2:
            return {"has_seasonality": False, "period": period,
                    "provenance": build_provenance(
                        inputs=[_history_input("history", history)],
                        confidence=None, confidence_basis=_basis,
                        data_status="no_data")}

        # Split into periods
        periods = []
        for i in range(0, len(history) - period + 1, period):
            periods.append(history[i:i + period])

        if len(periods) < 2:
            return {"has_seasonality": False, "period": period,
                    "provenance": build_provenance(
                        inputs=[_history_input("history", history)],
                        confidence=None, confidence_basis=_basis,
                        data_status="no_data")}

        # Compare period averages
        period_avgs = [sum(p) / len(p) for p in periods]

        # Calculate variance between periods
        overall_avg = sum(period_avgs) / len(period_avgs)
        variance = sum((a - overall_avg) ** 2 for a in period_avgs) / len(period_avgs)
        cv = math.sqrt(variance) / max(1.0, overall_avg)

        has_seasonality = cv > 0.15

        return {
            "has_seasonality": has_seasonality,
            "period": period,
            "period_averages": period_avgs,
            "coefficient_of_variation": cv,
            "peak_period": period_avgs.index(max(period_avgs)),
            "trough_period": period_avgs.index(min(period_avgs)),
            "provenance": build_provenance(
                inputs=[
                    _history_input("history", history),
                    input_record("period", period, CALLER_SUPPLIED),
                    input_record("periods_compared", len(periods), DERIVED),
                ],
                confidence=None,
                confidence_basis=_basis,
                data_status="estimated_from_inputs",
            ),
        }

    # ── Demand Forecasting ──────────────────────────────────────────────────

    def forecast_demand(
        self,
        product_id: str,
        sales_history: list[float],
        seasonal_factor: float = 1.0,
        supplied_fields: set[str] | None = None,
    ) -> DemandForecast:
        """Forecast product demand."""
        if not sales_history:
            return DemandForecast(
                product_id=product_id,
                current_demand=0.0,
                forecasted_demand=0.0,
                growth_rate=0.0,
                confidence=0.0,
                seasonal_factor=seasonal_factor,
                recommendation="No historical data",
                provenance=build_provenance(
                    inputs=[],
                    confidence=0.0,
                    confidence_basis="No sales history supplied: no forecast is computed.",
                    data_status="no_data",
                ),
            )

        current_demand = sales_history[-1]

        # Calculate growth rate
        if len(sales_history) >= 2:
            growth_rate = (sales_history[-1] - sales_history[0]) / max(1.0, sales_history[0])
        else:
            growth_rate = 0.0

        # Forecast next period
        forecasted = current_demand * (1 + growth_rate) * seasonal_factor

        # Confidence
        confidence = min(0.85, 0.4 + abs(growth_rate) * 2)

        # Recommendation
        if growth_rate > 0.1:
            recommendation = "Increase inventory - demand is growing"
        elif growth_rate < -0.1:
            recommendation = "Reduce inventory - demand is declining"
        else:
            recommendation = "Maintain current inventory levels"

        result = DemandForecast(
            product_id=product_id,
            current_demand=current_demand,
            forecasted_demand=forecasted,
            growth_rate=growth_rate,
            confidence=confidence,
            seasonal_factor=seasonal_factor,
            recommendation=recommendation,
            provenance=build_provenance(
                inputs=[
                    _history_input("sales_history", sales_history),
                    input_record(
                        "seasonal_factor", seasonal_factor,
                        CALLER_SUPPLIED
                        if supplied_fields is None or "seasonal_factor" in supplied_fields
                        else ROUTE_DEFAULT,
                    ),
                    input_record("growth_rate_endpoints_only",
                                 [sales_history[0], sales_history[-1]], DERIVED),
                ],
                confidence=confidence,
                confidence_basis=(
                    "confidence = min(0.85, 0.4 + 2 x |growth_rate|), where "
                    "growth_rate = (last - first) / first of the supplied "
                    "sales history — ONLY the first and last points are used; "
                    "intermediate points do not affect the result. The "
                    "inventory recommendation fires at |growth_rate| > 0.1. "
                    "A heuristic, not a calibrated probability."
                ),
                data_status="estimated_from_inputs",
            ),
        )

        self._demand_forecasts[product_id] = result
        return result

    # ── Customer Behavior Prediction ────────────────────────────────────────

    def predict_customer_behavior(
        self,
        customer_id: str,
        behavior_history: list[dict],
    ) -> dict[str, Any]:
        """Predict future customer behavior."""
        if not behavior_history:
            return {
                "prediction": "inactive",
                "confidence": 0.0,
                "provenance": build_provenance(
                    inputs=[],
                    confidence=0.0,
                    confidence_basis="No behavior history supplied: no prediction is computed.",
                    data_status="no_data",
                ),
            }

        # Analyze recent patterns
        recent = behavior_history[-10:]

        # Calculate activity frequency
        days_active = len(set(b.get("date", 0) for b in recent))
        frequency = days_active / max(1, len(recent))

        # Calculate engagement trend
        if len(recent) >= 2:
            engagement_change = recent[-1].get("engagement", 0) - recent[0].get("engagement", 0)
        else:
            engagement_change = 0

        # Predict next action
        if frequency > 0.5 and engagement_change > 0:
            prediction = "highly_active"
            confidence = 0.8
        elif frequency > 0.3:
            prediction = "active"
            confidence = 0.6
        elif frequency > 0.1:
            prediction = "moderately_active"
            confidence = 0.5
        else:
            prediction = "inactive"
            confidence = 0.4

        # Predict next action type
        actions = [b.get("action", "") for b in recent]
        if actions:
            most_common = max(set(actions), key=actions.count)
            predicted_action = most_common
        else:
            predicted_action = "unknown"

        return {
            "prediction": prediction,
            "confidence": confidence,
            "predicted_action": predicted_action,
            "engagement_trend": "rising" if engagement_change > 0 else "falling" if engagement_change < 0 else "stable",
            # TASK-COR-002: the confidence is a bucket constant chosen by a
            # frequency rule — say so, and record the window actually used.
            "provenance": build_provenance(
                inputs=[
                    input_record("behavior_records_supplied", len(behavior_history), CALLER_SUPPLIED),
                    input_record("behavior_records_used", len(recent), DERIVED),
                    input_record("days_active_in_window", days_active, DERIVED),
                    input_record("activity_frequency", frequency, DERIVED),
                    input_record("engagement_change", engagement_change, DERIVED),
                ],
                confidence=confidence,
                confidence_basis=(
                    "Rule buckets over the last 10 supplied records: "
                    "frequency > 0.5 and engagement rising -> 0.8; "
                    "frequency > 0.3 -> 0.6; frequency > 0.1 -> 0.5; "
                    "otherwise 0.4, where frequency = distinct active days / "
                    "records in window. The value is a bucket constant, NOT "
                    "a calibrated probability."
                ),
                data_status="estimated_from_inputs",
            ),
        }

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_analytics_report(self) -> dict[str, Any]:
        """Generate a predictive analytics report."""
        return {
            "total_forecasts": len(self._forecasts),
            "total_trends": len(self._trends),
            "demand_forecasts": len(self._demand_forecasts),
            "avg_forecast_accuracy": sum(
                f.accuracy for f in self._forecasts.values()
            ) / max(1, len(self._forecasts)),
        }


# Module-level singleton
predictive_analytics = PredictiveAnalytics()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/analytics/forecast")
async def forecast_metric(
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Forecast a metric."""
    result = predictive_analytics.forecast(
        metric_name=payload["metric"],
        history=payload["history"],
        steps=payload.get("steps", 7),
    )
    return {
        "metric": result.metric_name,
        "forecast": result.forecast,
        "confidence_lower": result.confidence_lower,
        "confidence_upper": result.confidence_upper,
        "accuracy": result.accuracy,
        "trend": result.trend,
        "seasonality": result.seasonality,
        "provenance": result.provenance,
    }


@router.get("/api/v1/analytics/trend/{metric_name}")
async def analyze_trend(
    metric_name: str,
    history: list[float],
    user: dict = Depends(require_role(Role.CORTEX_VIEWER)),
):
    """Analyze a trend."""
    result = predictive_analytics.analyze_trend(metric_name, history)
    return result.__dict__


@router.post("/api/v1/analytics/seasonality")
async def detect_seasonality(
    payload: dict,
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Detect seasonal patterns."""
    return predictive_analytics.detect_seasonal_pattern(
        payload["history"],
        period=payload.get("period", 7),
    )


@router.post("/api/v1/analytics/demand-forecast")
async def demand_forecast(
    payload: dict,
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Forecast product demand."""
    result = predictive_analytics.forecast_demand(
        product_id=payload["product_id"],
        sales_history=payload["sales_history"],
        seasonal_factor=payload.get("seasonal_factor", 1.0),
        supplied_fields=set(payload.keys()),
    )
    return result.__dict__


@router.get("/api/v1/analytics/predictive/report")
async def predictive_report(
    user: dict = Depends(require_role(Role.CORTEX_VIEWER)),
):
    """Get predictive analytics report."""
    return predictive_analytics.get_analytics_report()
