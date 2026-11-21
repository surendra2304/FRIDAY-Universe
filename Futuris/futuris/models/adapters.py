"""StatsForecast model adapters: Naive, SeasonalNaive, Drift, AutoETS, AutoARIMA, MeanEnsemble."""

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from futuris.features.contextualize import (
    CALENDAR_FEATURE_COLUMNS,
    ContextLayer,
    summarize_known_events,
)
from futuris.models.base import (
    ModelPrediction,
    PredictionIntervals,
    calculate_exceedance_probability,
    compute_config_hash,
)

logger = logging.getLogger(__name__)


class StatsForecastUnavailableError(RuntimeError):
    """The statsforecast model backend is not importable in this deployment.

    Raised instead of ever serving a substitute forecast: a flat line at the
    last observed value is not a forecast, and presenting it as one is how
    Futuris silently served mock numbers while the declared ``statsforecast``
    dependency was missing from the production environment (TASK-REL-018).
    """


try:
    from statsforecast.models import AutoARIMA as _SF_AutoARIMA
    from statsforecast.models import AutoETS as _SF_AutoETS
    from statsforecast.models import Naive as _SF_Naive
    from statsforecast.models import RandomWalkWithDrift as _SF_RandomWalkWithDrift
    from statsforecast.models import SeasonalNaive as _SF_SeasonalNaive

    STATSFORECAST_AVAILABLE = True
    STATSFORECAST_IMPORT_ERROR: str | None = None
except (ImportError, OSError) as exc:
    STATSFORECAST_AVAILABLE = False
    STATSFORECAST_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

    class _SFMockModel:
        """Import placeholder ONLY -- it must never produce a forecast.

        Kept so this module (and everything importing the adapters) still
        imports on machines without statsforecast. ``fit``/``predict`` raise
        :class:`StatsForecastUnavailableError`, which the pipeline/engine let
        propagate and the API layer translates into an explicit degraded /
        BLOCKED status. The previous behaviour -- silently returning the last
        observed value repeated across the horizon -- presented a flat line
        as a model forecast; that is the defect TASK-REL-018 removes.
        """

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def fit(self, y: Any = None, *_args: Any, **_kwargs: Any) -> Any:  # noqa: ARG002 -- signature mirrors the real model; the refusal needs no data
            raise StatsForecastUnavailableError(
                "statsforecast is not importable in this deployment "
                f"({STATSFORECAST_IMPORT_ERROR}); refusing to substitute a mock forecast"
            )

        def predict(self, h: int = 1, *_args: Any, **_kwargs: Any) -> Any:  # noqa: ARG002 -- signature mirrors the real model; the refusal needs no horizon
            raise StatsForecastUnavailableError(
                "statsforecast is not importable in this deployment "
                f"({STATSFORECAST_IMPORT_ERROR}); refusing to substitute a mock forecast"
            )

    _SF_AutoARIMA = _SF_AutoETS = _SF_Naive = _SF_RandomWalkWithDrift = _SF_SeasonalNaive = (
        _SFMockModel
    )

    logger.warning(
        "statsforecast_unavailable: model adapters will refuse to fit "
        "(forecasts must surface as degraded/BLOCKED, never as mock flat-lines): %s",
        STATSFORECAST_IMPORT_ERROR,
    )


class BaseStatsForecastAdapter:
    """Base wrapper for single-series statsforecast model estimators."""

    # TASK-FUT-007: whether the wrapped backend can consume exogenous
    # regressors. Only AutoARIMA in the statsforecast family accepts X;
    # the other adapters keep the univariate contract and say so here
    # instead of silently discarding the feature frame they were handed.
    supports_exogenous: bool = False

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self._name = name
        self._config = config or {}
        self.fitted_model: Any | None = None
        self.y_history: np.ndarray | None = None
        self.residuals: np.ndarray = np.array([])
        self.as_of: datetime | None = None
        # Exogenous-wiring state (TASK-FUT-007): the calendar columns the
        # model was actually fitted with, and the history grid needed to
        # derive the future calendar frame at predict time.
        self.exog_columns: list[str] = []
        self.exog_used: bool = False
        self._last_observed_ts: datetime | None = None
        self._step_minutes: float | None = None

    def _note_history_frame(self, x: pd.DataFrame | None) -> None:
        """Record the history grid (last timestamp + step) from the fit frame.

        Known future events are functions of future timestamps; deriving
        those timestamps at predict time requires knowing where history
        ended and on what grid — information every caller already passes
        in ``x`` and every adapter previously threw away.
        """
        if x is None or not isinstance(x.index, pd.DatetimeIndex) or len(x) == 0:
            return
        self._last_observed_ts = x.index[-1].to_pydatetime()
        if len(x) >= 2:
            step = (x.index[-1] - x.index[-2]).total_seconds() / 60.0
            if step > 0:
                self._step_minutes = step

    def _future_calendar_frame(
        self,
        horizon: int,
        future_x: pd.DataFrame | None,
    ) -> pd.DataFrame:
        """Resolve the future calendar frame for an exogenous predict.

        An explicit ``future_x`` wins (validated for length); otherwise the
        frame is derived deterministically from the recorded history grid.
        Raises ValueError when neither is possible — an exogenous model
        must never be served a silently wrong or silently absent frame.
        """
        if future_x is not None:
            if len(future_x) != horizon:
                msg = (
                    f"future_x has {len(future_x)} rows but horizon is {horizon}; "
                    "refusing to misalign known-event features with forecast steps"
                )
                raise ValueError(msg)
            return future_x
        if self._last_observed_ts is None or self._step_minutes is None:
            msg = (
                "model was fitted with exogenous calendar features but the "
                "history frame carried no DatetimeIndex grid to derive future "
                "timestamps from, and no future_x was supplied"
            )
            raise ValueError(msg)
        start = self._last_observed_ts + timedelta(minutes=self._step_minutes)
        return ContextLayer().build_future_calendar_features(
            start=start,
            steps=horizon,
            step_minutes=int(self._step_minutes),
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def get_config_hash(self) -> str:
        return compute_config_hash(self._config)

    def _extract_residuals(self, y: np.ndarray) -> None:
        if len(y) > 1:
            in_sample_pred = np.roll(y, 1)
            in_sample_pred[0] = y[0]
            self.residuals = y - in_sample_pred
        else:
            self.residuals = np.array([0.0])

    def _interval_floor(self) -> float:
        """Lower bound for intervals: 0 when the series is non-negative.

        Demand, rates and counts cannot go below zero, but a residual-std
        interval around a small mean goes deeply negative (a forecast of 1285
        rpm was served with a lower bound of -5700). A calibrated platform must
        not hand operators impossible intervals.
        """
        if self.y_history is not None and len(self.y_history) > 0:
            return 0.0 if bool(np.all(self.y_history >= 0)) else float("-inf")
        return float("-inf")

    def _build_prediction(
        self,
        point_forecast: np.ndarray,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        extra_metadata: dict[str, Any] | None = None,
    ) -> ModelPrediction:
        std_res = float(np.std(self.residuals)) if len(self.residuals) > 0 else 0.0
        z_90 = 1.645  # 90% prediction interval
        floor = self._interval_floor()

        intervals: list[PredictionIntervals] = []
        for i, val in enumerate(point_forecast):
            step_scale = np.sqrt(i + 1)
            step_lower = max(floor, float(val - (z_90 * std_res * step_scale)))
            step_upper = float(val + (z_90 * std_res * step_scale))
            intervals.append(
                PredictionIntervals(
                    lower=step_lower,
                    central=float(val),
                    upper=step_upper,
                )
            )

        range_lower = (
            min(p.lower for p in intervals) if intervals else float(np.min(point_forecast))
        )
        range_upper = (
            max(p.upper for p in intervals) if intervals else float(np.max(point_forecast))
        )
        central = float(np.mean(point_forecast))

        prob: float | None = None
        if capacity_threshold is not None:
            prob = calculate_exceedance_probability(
                point_forecast=point_forecast,
                residuals=self.residuals,
                capacity_threshold=capacity_threshold,
                method=probability_method,
            )

        metadata: dict[str, Any] = {"model": self.name, "config_hash": self.get_config_hash()}
        if extra_metadata:
            metadata.update(extra_metadata)
        return ModelPrediction(
            point_forecast=[float(v) for v in point_forecast],
            intervals=intervals,
            range_lower=round(range_lower, 2),
            range_upper=round(range_upper, 2),
            central_estimate=round(central, 2),
            exceedance_probability=prob,
            metadata=metadata,
        )


class NaiveAdapter(BaseStatsForecastAdapter):
    """Naive persistence forecaster: predicts last observed value forward."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("naive", config)

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "NaiveAdapter":
        self._note_history_frame(x)
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        self.fitted_model = _SF_Naive().fit(y=self.y_history)
        self._extract_residuals(self.y_history)
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        _ = future_x  # univariate backend: known events cannot move this model
        preds = self.fitted_model.predict(h=horizon)["mean"]
        return self._build_prediction(preds, capacity_threshold, probability_method)


class SeasonalNaiveAdapter(BaseStatsForecastAdapter):
    """Seasonal Naive forecaster: repeats past observed seasonal cycle."""

    def __init__(self, season_length: int = 288, config: dict[str, Any] | None = None) -> None:
        cfg = {"season_length": season_length}
        if config:
            cfg.update(config)
        super().__init__("seasonal_naive", cfg)
        self.season_length = season_length

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "SeasonalNaiveAdapter":
        self._note_history_frame(x)
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        eff_season = self.season_length if len(self.y_history) >= self.season_length else 1
        self.fitted_model = _SF_SeasonalNaive(season_length=eff_season).fit(y=self.y_history)

        if len(self.y_history) > eff_season:
            seasonal_lag = np.roll(self.y_history, eff_season)
            self.residuals = self.y_history[eff_season:] - seasonal_lag[eff_season:]
        else:
            self._extract_residuals(self.y_history)
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        _ = future_x  # univariate backend: known events cannot move this model
        preds = self.fitted_model.predict(h=horizon)["mean"]
        return self._build_prediction(preds, capacity_threshold, probability_method)


class DriftAdapter(BaseStatsForecastAdapter):
    """Random walk with linear drift forecaster."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("drift", config)

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "DriftAdapter":
        self._note_history_frame(x)
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        self.fitted_model = _SF_RandomWalkWithDrift().fit(y=self.y_history)
        self._extract_residuals(self.y_history)
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        _ = future_x  # univariate backend: known events cannot move this model
        preds = self.fitted_model.predict(h=horizon)["mean"]
        return self._build_prediction(preds, capacity_threshold, probability_method)


class AutoETSAdapter(BaseStatsForecastAdapter):
    """Automatic Exponential Smoothing (ETS) adapter with deterministic settings."""

    def __init__(self, season_length: int = 288, config: dict[str, Any] | None = None) -> None:
        cfg = {"season_length": season_length, "model": "ZZZ"}
        if config:
            cfg.update(config)
        super().__init__("auto_ets", cfg)
        self.season_length = season_length

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "AutoETSAdapter":
        self._note_history_frame(x)
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        # Cap eff_season at 24 for ETS numerical stability
        base_season = min(self.season_length, 24)
        eff_season = base_season if len(self.y_history) >= 2 * base_season else 1
        self.fitted_model = _SF_AutoETS(season_length=eff_season).fit(y=self.y_history)
        self._extract_residuals(self.y_history)
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        _ = future_x  # statsforecast ETS accepts no regressors; stated, not hidden
        preds = self.fitted_model.predict(h=horizon)["mean"]
        return self._build_prediction(preds, capacity_threshold, probability_method)


class AutoARIMAAdapter(BaseStatsForecastAdapter):
    """Automatic ARIMA adapter with deterministic search parameters.

    TASK-FUT-007: this is the one statsforecast backend that accepts
    exogenous regressors, so it is where known future events (holidays,
    weekends — the calendar block ContextLayer computes) enter the
    forecast path. Fit passes the historical calendar columns as X;
    predict passes the future calendar frame for the horizon, derived
    from the recorded history grid unless the caller supplies one.
    """

    supports_exogenous = True

    def __init__(self, season_length: int = 1, config: dict[str, Any] | None = None) -> None:
        cfg = {"season_length": season_length, "max_p": 3, "max_q": 3}
        if config:
            cfg.update(config)
        super().__init__("auto_arima", cfg)
        self.season_length = season_length

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "AutoARIMAAdapter":
        self._note_history_frame(x)
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        eff_season = self.season_length if len(self.y_history) >= 2 * self.season_length else 1
        model = _SF_AutoARIMA(
            season_length=eff_season,
            max_p=self.config.get("max_p", 3),
            max_q=self.config.get("max_q", 3),
        )
        self.exog_columns = (
            [c for c in CALENDAR_FEATURE_COLUMNS if c in x.columns] if x is not None else []
        )
        self.exog_used = False
        if self.exog_columns:
            try:
                # TASK-FUT-014: statsforecast 2.1.1's arima/auto_arima_f
                # read ``xreg.dtype`` — an attribute only numpy arrays have.
                # Passing the calendar frame as a DataFrame raised
                # "'DataFrame' object has no attribute 'dtype'" and the
                # candidate never fitted. The backend's documented contract
                # is ``X: numpy array``, so hand it a float array.
                self.fitted_model = model.fit(
                    y=self.y_history, X=x[self.exog_columns].to_numpy(dtype=float)
                )
                self.exog_used = True
            except TypeError:
                # A backend build without regressor support: fall back to
                # the univariate fit and record that events are NOT wired,
                # rather than pretending otherwise.
                logger.warning(
                    "auto_arima_exogenous_unsupported_by_backend: "
                    "fitted univariately; calendar features not consumed"
                )
                self.fitted_model = model.fit(y=self.y_history)
                self.exog_columns = []
        else:
            self.fitted_model = model.fit(y=self.y_history)
        self._extract_residuals(self.y_history)
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        if self.exog_used and self.exog_columns:
            future_frame = self._future_calendar_frame(horizon, future_x)
            missing = [c for c in self.exog_columns if c not in future_frame.columns]
            if missing:
                msg = f"future calendar frame is missing fitted exogenous columns: {missing}"
                raise ValueError(msg)
            preds = self.fitted_model.predict(
                # TASK-FUT-014: same numpy-array contract as at fit time —
                # forecast_arima reads ``xreg.dtype`` and a DataFrame fails
                # the same way (see fit above).
                h=horizon,
                X=future_frame[self.exog_columns].to_numpy(dtype=float),
            )["mean"]
            return self._build_prediction(
                preds,
                capacity_threshold,
                probability_method,
                extra_metadata={
                    "exogenous_features": list(self.exog_columns),
                    "known_event_steps": summarize_known_events(future_frame),
                },
            )
        preds = self.fitted_model.predict(h=horizon)["mean"]
        return self._build_prediction(preds, capacity_threshold, probability_method)


class MeanEnsembleAdapter:
    """Averages predictions from AutoETS and SeasonalNaive and pools their uncertainty intervals."""

    def __init__(self, season_length: int = 288, config: dict[str, Any] | None = None) -> None:
        cfg = {"season_length": season_length, "components": ["auto_ets", "seasonal_naive"]}
        if config:
            cfg.update(config)
        self._name = "mean_ensemble"
        self._config = cfg
        self.ets_adapter = AutoETSAdapter(season_length=season_length)
        self.snaive_adapter = SeasonalNaiveAdapter(season_length=season_length)
        self.residuals: np.ndarray = np.array([])
        self.as_of: datetime | None = None
        self.y_history: np.ndarray | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def get_config_hash(self) -> str:
        return compute_config_hash(self._config)

    def fit(self, x: pd.DataFrame, y: pd.Series, as_of: datetime) -> "MeanEnsembleAdapter":
        self.as_of = as_of
        self.y_history = y.to_numpy(dtype=float)
        self.ets_adapter.fit(x, y, as_of)
        self.snaive_adapter.fit(x, y, as_of)
        r_ets = self.ets_adapter.residuals
        r_snaive = self.snaive_adapter.residuals
        if len(r_ets) > 0 and len(r_snaive) > 0:
            min_len = min(len(r_ets), len(r_snaive))
            self.residuals = 0.5 * (r_ets[-min_len:] + r_snaive[-min_len:])
        elif len(r_ets) > 0:
            self.residuals = r_ets
        elif len(r_snaive) > 0:
            self.residuals = r_snaive
        else:
            self.residuals = np.array([])
        return self

    def predict(
        self,
        horizon: int,
        capacity_threshold: float | None = None,
        probability_method: str = "empirical",
        future_x: pd.DataFrame | None = None,
    ) -> ModelPrediction:
        # Both components are univariate backends; future_x is forwarded so
        # the call contract is uniform, and both document that known events
        # cannot move them.
        p_ets = self.ets_adapter.predict(
            horizon, capacity_threshold, probability_method, future_x=future_x
        )
        p_snaive = self.snaive_adapter.predict(
            horizon, capacity_threshold, probability_method, future_x=future_x
        )

        avg_point = 0.5 * (np.array(p_ets.point_forecast) + np.array(p_snaive.point_forecast))
        # Clamp at zero for non-negative series, same rule as the single-model
        # adapters: pooling two wide intervals must not produce an impossible
        # negative lower bound.
        if self.y_history is not None and len(self.y_history) > 0 and bool(
            np.all(self.y_history >= 0)
        ):
            floor = 0.0
        else:
            floor = float("-inf")
        range_lower = max(floor, min(p_ets.range_lower, p_snaive.range_lower))
        range_upper = max(p_ets.range_upper, p_snaive.range_upper)
        central = float(np.mean(avg_point))

        intervals: list[PredictionIntervals] = []
        for int_e, int_s in zip(p_ets.intervals, p_snaive.intervals, strict=True):
            intervals.append(
                PredictionIntervals(
                    lower=max(floor, min(int_e.lower, int_s.lower)),
                    central=0.5 * (int_e.central + int_s.central),
                    upper=max(int_e.upper, int_s.upper),
                )
            )

        prob: float | None = None
        if capacity_threshold is not None:
            prob = calculate_exceedance_probability(
                point_forecast=avg_point,
                residuals=self.residuals,
                capacity_threshold=capacity_threshold,
                method=probability_method,
            )

        return ModelPrediction(
            point_forecast=[float(v) for v in avg_point],
            intervals=intervals,
            range_lower=round(range_lower, 2),
            range_upper=round(range_upper, 2),
            central_estimate=round(central, 2),
            exceedance_probability=prob,
            metadata={"model": self.name, "config_hash": self.get_config_hash()},
        )
