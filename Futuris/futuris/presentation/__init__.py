"""Presentation layer: how Futuris explains its forecasts to consumers."""

from futuris.presentation.uncertainty import (
    INTERVAL_LEVEL_PCT,
    blocked_presentation,
    describe_method,
    forecast_presentation,
    horizon_text,
    scenario_presentation,
)

__all__ = [
    "INTERVAL_LEVEL_PCT",
    "blocked_presentation",
    "describe_method",
    "forecast_presentation",
    "horizon_text",
    "scenario_presentation",
]
