"""Harness-internal reference baselines for the walk-forward harness.

These are NOT production models. They exist for two reasons:

1. They prove the harness machinery end-to-end (origins, scoring, coverage
   math) in environments where the production adapters cannot run — today,
   every environment without ``statsforecast``.
2. They set the bar the production models must beat when ``statsforecast``
   lands: a production model that cannot outperform a naive reference on
   MASE, or whose intervals calibrate worse, has earned nothing.

Their construction deliberately mirrors the production adapters'
uncertainty machinery in ``futuris.models.adapters`` — in-sample residuals
(``_extract_residuals`` / the seasonal-lag variant) and the interval
formula of ``BaseStatsForecastAdapter._build_prediction``
(``point ± 1.645 * std(residuals) * sqrt(step)``, floored at 0 for
non-negative series). When statsforecast is installed, the production
``naive`` / ``seasonal_naive`` adapters should therefore score *close to*
these references on point error and coverage; a large divergence is itself
a finding about the adapter layer, and the harness will show it.
"""

from __future__ import annotations

import numpy as np

_Z_90 = 1.645  # matches BaseStatsForecastAdapter._build_prediction


def _one_step_residuals(y: np.ndarray) -> np.ndarray:
    """Mirror of ``BaseStatsForecastAdapter._extract_residuals``."""
    if len(y) <= 1:
        return np.array([0.0])
    in_sample_pred = np.roll(y, 1)
    in_sample_pred[0] = y[0]
    return y - in_sample_pred


def _intervals(
    point: np.ndarray, residuals: np.ndarray, y_history: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Mirror of the interval construction in ``_build_prediction``."""
    std_res = float(np.std(residuals)) if len(residuals) > 0 else 0.0
    floor = 0.0 if len(y_history) > 0 and bool(np.all(y_history >= 0)) else float("-inf")
    steps = np.sqrt(np.arange(1, len(point) + 1, dtype=float))
    lower = np.maximum(floor, point - _Z_90 * std_res * steps)
    upper = point + _Z_90 * std_res * steps
    return lower, upper


class ReferenceNaiveForecaster:
    """Last-value persistence with production-mirroring intervals."""

    name = "ref_naive"
    kind = "reference"

    def __init__(self) -> None:
        self._y: np.ndarray | None = None
        self._residuals: np.ndarray = np.array([])

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None:
        _ = train_times
        self._y = np.asarray(y_train, dtype=float)
        self._residuals = _one_step_residuals(self._y)

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert self._y is not None and len(self._y) > 0
        point = np.full(horizon, float(self._y[-1]))
        lower, upper = _intervals(point, self._residuals, self._y)
        return point, lower, upper


class ReferenceSeasonalNaiveForecaster:
    """Last-season repetition with production-mirroring intervals."""

    name = "ref_seasonal_naive"
    kind = "reference"

    def __init__(self, season_length: int) -> None:
        self.season_length = season_length
        self._y: np.ndarray | None = None
        self._residuals: np.ndarray = np.array([])

    def fit(self, y_train: np.ndarray, train_times: list[str]) -> None:
        _ = train_times
        self._y = np.asarray(y_train, dtype=float)
        m = self.season_length if len(self._y) >= self.season_length else 1
        self._eff_season = m
        if len(self._y) > m:
            # Mirror of SeasonalNaiveAdapter.fit's residual construction.
            seasonal_lag = np.roll(self._y, m)
            self._residuals = self._y[m:] - seasonal_lag[m:]
        else:
            self._residuals = _one_step_residuals(self._y)

    def predict(self, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert self._y is not None and len(self._y) > 0
        m = self._eff_season
        season = self._y[-m:]
        reps = int(np.ceil(horizon / m))
        point = np.tile(season, reps)[:horizon].astype(float)
        lower, upper = _intervals(point, self._residuals, self._y)
        return point, lower, upper


def reference_forecasters(season_length: int) -> list:
    """All harness reference baselines for one series."""
    return [
        ReferenceNaiveForecaster(),
        ReferenceSeasonalNaiveForecaster(season_length=season_length),
    ]
