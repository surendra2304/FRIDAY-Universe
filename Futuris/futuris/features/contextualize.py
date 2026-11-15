"""Contextualization layer computing calendar features, rolling statistics, and regime flags."""

from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

import numpy as np
import pandas as pd

from futuris.features.normalize import TrustedSignalSet


class SimpleHolidayCalendar:
    """Built-in deterministic holiday and high-load event calendar (no external APIs)."""

    HOLIDAYS_MMDD = {
        (1, 1),  # New Year's Day
        (7, 4),  # Independence Day
        (11, 27),  # Thanksgiving (approx)
        (11, 28),  # Black Friday (approx)
        (12, 25),  # Christmas
        (12, 31),  # New Year's Eve
    }

    @classmethod
    def is_holiday(cls, dt: datetime) -> bool:
        return (dt.month, dt.day) in cls.HOLIDAYS_MMDD


# The subset of ContextLayer features that are pure functions of the
# timestamp: they are knowable for FUTURE steps without observing any future
# values, so they are the only features a model may legitimately consume as
# exogenous regressors for the forecast horizon. Lag / rolling / regime
# features depend on future *values* and must never be fabricated forward.
CALENDAR_FEATURE_COLUMNS: tuple[str, ...] = (
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
)


def calendar_features_for_index(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Compute the calendar feature block for an arbitrary timestamp index.

    Single source of the calendar formulas: the historical feature table
    (``ContextLayer.build_feature_table``) and the future frame
    (``ContextLayer.build_future_calendar_features``) both come from here,
    so a model can never be trained on one definition and served another.
    """
    hours = index.hour
    dows = index.dayofweek
    out = pd.DataFrame(index=index)
    out["hour_of_day"] = hours
    out["day_of_week"] = dows
    out["is_weekend"] = pd.Series(dows, index=index).isin([5, 6]).astype(int).to_numpy()
    out["is_holiday"] = [int(SimpleHolidayCalendar.is_holiday(ts)) for ts in index]
    out["hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * hours / 24.0)
    out["dow_sin"] = np.sin(2 * np.pi * dows / 7.0)
    out["dow_cos"] = np.cos(2 * np.pi * dows / 7.0)
    return out


def summarize_known_events(future_df: pd.DataFrame) -> dict[str, int]:
    """Count known-event steps inside a future calendar frame.

    Surfaced in prediction metadata so a served forecast states, in numbers,
    which known events its horizon contains (0 when there are none).
    """
    summary: dict[str, int] = {}
    if "is_holiday" in future_df.columns:
        summary["holiday_steps"] = int(future_df["is_holiday"].sum())
    if "is_weekend" in future_df.columns:
        summary["weekend_steps"] = int(future_df["is_weekend"].sum())
    return summary


class ContextLayer:
    """Computes features with a strict point-in-time invariant: at T, compute ONLY using <= T."""

    def __init__(
        self,
        rolling_windows: list[int] | None = None,
        lag_steps: list[int] | None = None,
        regime_quantile_threshold: float = 0.90,
    ) -> None:
        self.rolling_windows = rolling_windows or [6, 12, 24, 72, 288]
        self.lag_steps = lag_steps or [1, 2, 3, 6, 12, 288]
        self.regime_quantile_threshold = regime_quantile_threshold

    def build_feature_table(
        self,
        signal_set: TrustedSignalSet,
        as_of: datetime | None = None,
    ) -> pd.DataFrame:
        """Construct feature table up to s_of without any future-data leakage."""
        df = signal_set.to_dataframe()

        # Enforce point-in-time cutoff: strictly filter timestamps <= as_of
        if as_of is not None:
            as_of = as_of.replace(tzinfo=UTC) if as_of.tzinfo is None else as_of.astimezone(UTC)
            df = df[df.index <= as_of].copy()
        else:
            df = df.copy()

        if df.empty:
            msg = "Signal set contains no observations on or before as_of."
            raise ValueError(msg)

        # 1. Calendar / Temporal Features (strictly deterministic from timestamp)
        calendar = calendar_features_for_index(df.index)
        for column in CALENDAR_FEATURE_COLUMNS:
            df[column] = calendar[column].to_numpy()

        # 2. Lag Features (values strictly from previous timesteps)
        for lag in self.lag_steps:
            df[f"lag_{lag}"] = df["value"].shift(lag)

        # 3. Rolling Statistics (strictly trailing windows closed='left' or closed='both' <= T)
        for window in self.rolling_windows:
            rolling = df["value"].rolling(window=window, min_periods=1)
            df[f"rolling_mean_{window}"] = rolling.mean()
            df[f"rolling_std_{window}"] = rolling.std().fillna(0.0)
            df[f"rolling_max_{window}"] = rolling.max()
            df[f"rolling_min_{window}"] = rolling.min()

        # 4. Regime Tagging (strictly above the trailing quantile threshold)
        trailing_24h_window = min(len(df), 288)
        trailing_quantile = (
            df["value"]
            .rolling(window=trailing_24h_window, min_periods=1)
            .quantile(self.regime_quantile_threshold)
        )
        df["regime_high_load"] = (df["value"] > trailing_quantile).astype(int)

        # Drop initial lag NaNs or fill with backward/forward values
        df.bfill(inplace=True)
        df.fillna(0.0, inplace=True)

        return df

    def build_future_calendar_features(
        self,
        start: datetime,
        steps: int,
        step_minutes: int,
    ) -> pd.DataFrame:
        """Calendar features for FUTURE timestamps in the forecast horizon.

        TASK-FUT-007: until now the feature table covered only history
        (``<= as_of``), so even a model able to consume exogenous regressors
        could never receive the holiday/weekend flags of the steps it was
        forecasting — the known events were computed and then discarded.
        Calendar features are deterministic functions of the timestamp, so
        extending them forward is not leakage: a market holiday next Tuesday
        is known today. Only the CALENDAR_FEATURE_COLUMNS are produced;
        value-dependent features are never fabricated for the future.
        """
        if steps < 1:
            msg = "steps must be >= 1"
            raise ValueError(msg)
        start_utc = start.replace(tzinfo=UTC) if start.tzinfo is None else start.astimezone(UTC)
        index = pd.date_range(
            start=start_utc, periods=steps, freq=pd.Timedelta(minutes=step_minutes)
        )
        return calendar_features_for_index(index)
