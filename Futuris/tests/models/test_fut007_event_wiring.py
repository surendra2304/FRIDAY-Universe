"""TASK-FUT-007: known future events must actually reach the forecast path.

Audit finding (before): ContextLayer computed calendar features including
``is_holiday`` for every history row, but every statsforecast adapter
discarded the feature frame (``_ = x``), no adapter ever passed X to its
backend, no future calendar frame existed, and the one regressor-capable
model (AutoARIMA) was registered but never routed. A known event — a
market holiday inside the horizon — could not change any forecast.

These tests pin the repaired wiring with recording stand-ins for the
statsforecast classes (the library is absent from this environment by
design, exactly as in production until the ARM host lands). The fakes
mimic the real library's contract: univariate models take ``fit(y)`` /
``predict(h)``; AutoARIMA additionally accepts ``X`` at fit and requires
the future ``X`` at predict. What is under test is Futuris's own wiring:
which frames are built, which columns are passed, and whether the served
forecast path moves when a known event is inside the horizon.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from futuris.connectors.base import Observation
from futuris.features.contextualize import (
    CALENDAR_FEATURE_COLUMNS,
    ContextLayer,
    calendar_features_for_index,
    summarize_known_events,
)
from futuris.features.normalize import Normalizer
from futuris.models import adapters
from futuris.models.adapters import (
    AutoARIMAAdapter,
    NaiveAdapter,
    StatsForecastUnavailableError,
)
from futuris.models.routing import ModelRouter, SeriesMetadata

HOLIDAY_EFFECT = 25.0


class _UnivariateFake:
    """statsforecast stand-in for the univariate models: last value forward."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._y: np.ndarray | None = None

    def fit(self, y: Any = None, *_args: Any, **_kwargs: Any) -> "_UnivariateFake":
        self._y = np.asarray(y, dtype=float)
        return self

    def predict(self, h: int = 1, *_args: Any, **_kwargs: Any) -> pd.DataFrame:
        assert self._y is not None
        return pd.DataFrame({"mean": np.repeat(self._y[-1], h)})


class _XAwareARIMAFake:
    """AutoARIMA stand-in honouring the real regressor contract.

    fit(y, X) remembers that it was fitted with regressors; predict(h, X)
    then REQUIRES the future X and applies a fixed holiday effect, so a
    test can see the forecast path move at exactly the holiday steps.

    TASK-FUT-014: the real statsforecast 2.1.1 contract is ``X`` as a
    float numpy array in the order of ``CALENDAR_FEATURE_COLUMNS``
    (the backend reads ``xreg.dtype`` and a DataFrame has none), so
    this fake takes an ndarray and reads the holiday column by index
    (``CALENDAR_FEATURE_COLUMNS.index("is_holiday")``) instead of by
    column name.
    """

    instances: list["_XAwareARIMAFake"] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._y: np.ndarray | None = None
        self.fit_X: np.ndarray | None = None
        self.predict_X: np.ndarray | None = None
        _XAwareARIMAFake.instances.append(self)

    def fit(self, y: Any = None, X: Any = None, *_args: Any, **_kwargs: Any) -> "_XAwareARIMAFake":  # noqa: N803 — X mirrors the statsforecast API
        self._y = np.asarray(y, dtype=float)
        self.fit_X = None if X is None else np.asarray(X, dtype=float)
        return self

    def predict(self, h: int = 1, X: Any = None, *_args: Any, **_kwargs: Any) -> pd.DataFrame:  # noqa: N803 — X mirrors the statsforecast API
        assert self._y is not None
        if self.fit_X is not None and X is None:
            raise ValueError("fitted with X: future X is required at predict")
        self.predict_X = None if X is None else np.asarray(X, dtype=float)
        mean = np.repeat(self._y[-1], h)
        if X is not None:
            holiday_col = CALENDAR_FEATURE_COLUMNS.index("is_holiday")
            mean = mean + HOLIDAY_EFFECT * np.asarray(X, dtype=float)[:, holiday_col]
        return pd.DataFrame({"mean": mean})


class _UnavailableFake:
    """The statsforecast-less deployment state: fit refuses, honestly."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def fit(self, y: Any = None, *_args: Any, **_kwargs: Any) -> Any:
        raise StatsForecastUnavailableError("forced unavailable for test")

    def predict(self, h: int = 1, *_args: Any, **_kwargs: Any) -> Any:
        raise StatsForecastUnavailableError("forced unavailable for test")


@pytest.fixture
def x_aware_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _XAwareARIMAFake.instances.clear()
    for name in ("_SF_Naive", "_SF_SeasonalNaive", "_SF_RandomWalkWithDrift", "_SF_AutoETS"):
        monkeypatch.setattr(adapters, name, _UnivariateFake)
    monkeypatch.setattr(adapters, "_SF_AutoARIMA", _XAwareARIMAFake)


def _history(end: datetime, days: int = 3) -> tuple[pd.DataFrame, pd.Series]:
    """Feature frame on a 5-minute grid ending at ``end`` (inclusive)."""
    n = days * 288
    idx = pd.date_range(end=end, periods=n, freq="5min", tz="UTC")
    y = pd.Series(100.0 + 10.0 * np.sin(np.arange(n) / 24.0), index=idx)
    x = calendar_features_for_index(idx)
    return x, y


# ---------------------------------------------------------------------------
# Future calendar frame: the piece that did not exist before
# ---------------------------------------------------------------------------


def test_future_calendar_features_flag_christmas() -> None:
    layer = ContextLayer()
    frame = layer.build_future_calendar_features(
        start=datetime(2026, 12, 25, 0, 0, tzinfo=UTC), steps=288, step_minutes=5
    )
    assert list(frame.columns) == list(CALENDAR_FEATURE_COLUMNS)
    assert int(frame["is_holiday"].sum()) == 288
    assert summarize_known_events(frame)["holiday_steps"] == 288

    plain = layer.build_future_calendar_features(
        start=datetime(2026, 11, 25, 0, 0, tzinfo=UTC), steps=288, step_minutes=5
    )
    assert int(plain["is_holiday"].sum()) == 0
    assert summarize_known_events(plain)["holiday_steps"] == 0


def test_future_calendar_weekend_flags_match_the_calendar() -> None:
    frame = ContextLayer().build_future_calendar_features(
        start=datetime(2026, 12, 21, 0, 0, tzinfo=UTC), steps=7 * 288, step_minutes=5
    )
    for ts, row in frame.iterrows():
        assert int(row["is_weekend"]) == int(ts.weekday() >= 5)
        assert int(row["day_of_week"]) == ts.weekday()


def test_history_and_future_calendar_definitions_match() -> None:
    """The same timestamps must yield the same calendar features in the
    historical table and in the future frame — one formula source."""
    start = datetime(2026, 12, 23, 0, 0, tzinfo=UTC)
    n = 3 * 288
    observations = [
        Observation(
            observed_at=start + timedelta(minutes=5 * i),
            source="audit:synthetic",
            series_id="audit:events",
            unit="rpm",
            value=100.0 + float(i % 24),
        )
        for i in range(n)
    ]
    signal_set = Normalizer().normalize(observations)
    history = ContextLayer().build_feature_table(signal_set, as_of=start + timedelta(days=3))
    future = ContextLayer().build_future_calendar_features(
        start=history.index[0].to_pydatetime(), steps=len(history), step_minutes=5
    )
    for column in CALENDAR_FEATURE_COLUMNS:
        np.testing.assert_allclose(
            history[column].to_numpy(dtype=float),
            future[column].to_numpy(dtype=float),
            err_msg=f"calendar column {column} diverges between history and future frames",
        )


# ---------------------------------------------------------------------------
# The wiring itself: a known event inside the horizon moves the forecast
# ---------------------------------------------------------------------------


def test_known_event_changes_auto_arima_forecast_path(x_aware_backend: None) -> None:
    end = datetime(2026, 12, 24, 12, 0, tzinfo=UTC)
    x, y = _history(end)
    adapter = AutoARIMAAdapter()
    adapter.fit(x, y, as_of=end)

    fake = _XAwareARIMAFake.instances[-1]
    assert fake.fit_X is not None, "fit never received the calendar features"
    # The backend contract is a float array in CALENDAR_FEATURE_COLUMNS
    # order (TASK-FUT-014); the column names live on the adapter.
    assert adapter.exog_columns == list(CALENDAR_FEATURE_COLUMNS)
    assert fake.fit_X.shape == (len(x), len(CALENDAR_FEATURE_COLUMNS))
    assert fake.fit_X.dtype == float
    assert adapter.exog_used is True

    horizon = 288  # 2026-12-24 12:05 .. 2026-12-25 12:00 — Christmas morning inside
    expected_frame = ContextLayer().build_future_calendar_features(
        start=end + timedelta(minutes=5), steps=horizon, step_minutes=5
    )
    expected_holidays = int(expected_frame["is_holiday"].sum())
    assert 0 < expected_holidays < horizon

    with_events = adapter.predict(horizon=horizon)
    assert fake.predict_X is not None, "predict never received the future calendar frame"
    assert with_events.metadata["exogenous_features"] == list(CALENDAR_FEATURE_COLUMNS)
    assert with_events.metadata["known_event_steps"]["holiday_steps"] == expected_holidays

    no_event_frame = expected_frame.copy()
    no_event_frame["is_holiday"] = 0
    without_events = adapter.predict(horizon=horizon, future_x=no_event_frame)

    diff = np.array(with_events.point_forecast) - np.array(without_events.point_forecast)
    expected_diff = HOLIDAY_EFFECT * expected_frame["is_holiday"].to_numpy(dtype=float)
    np.testing.assert_allclose(diff, expected_diff)
    assert set(np.unique(diff)) == {0.0, HOLIDAY_EFFECT}


def test_no_event_in_horizon_reports_zero_holiday_steps(x_aware_backend: None) -> None:
    end = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    x, y = _history(end)
    adapter = AutoARIMAAdapter()
    adapter.fit(x, y, as_of=end)
    prediction = adapter.predict(horizon=288)
    assert prediction.metadata["known_event_steps"]["holiday_steps"] == 0


def test_univariate_adapters_cannot_be_moved_by_events(x_aware_backend: None) -> None:
    """Honesty boundary: Naive documents supports_exogenous=False and its
    output is identical with or without a future frame."""
    end = datetime(2026, 12, 24, 12, 0, tzinfo=UTC)
    x, y = _history(end)
    adapter = NaiveAdapter()
    assert adapter.supports_exogenous is False
    adapter.fit(x, y, as_of=end)
    frame = ContextLayer().build_future_calendar_features(
        start=end + timedelta(minutes=5), steps=48, step_minutes=5
    )
    plain = adapter.predict(horizon=48)
    with_frame = adapter.predict(horizon=48, future_x=frame)
    assert plain.point_forecast == with_frame.point_forecast
    assert "exogenous_features" not in plain.metadata


def test_fit_without_calendar_columns_stays_univariate(x_aware_backend: None) -> None:
    end = datetime(2026, 12, 24, 12, 0, tzinfo=UTC)
    idx = pd.date_range(end=end, periods=400, freq="5min", tz="UTC")
    y = pd.Series(np.linspace(90.0, 110.0, 400), index=idx)
    x = pd.DataFrame(index=idx)  # grid present, no feature columns at all
    adapter = AutoARIMAAdapter()
    adapter.fit(x, y, as_of=end)
    assert adapter.exog_used is False
    assert adapter.exog_columns == []
    prediction = adapter.predict(horizon=12)
    assert len(prediction.point_forecast) == 12
    assert "exogenous_features" not in prediction.metadata


def test_misaligned_future_frame_is_refused(x_aware_backend: None) -> None:
    end = datetime(2026, 12, 24, 12, 0, tzinfo=UTC)
    x, y = _history(end)
    adapter = AutoARIMAAdapter()
    adapter.fit(x, y, as_of=end)
    short_frame = ContextLayer().build_future_calendar_features(
        start=end + timedelta(minutes=5), steps=10, step_minutes=5
    )
    with pytest.raises(ValueError, match="future_x has 10 rows but horizon is 48"):
        adapter.predict(horizon=48, future_x=short_frame)


def test_unavailable_backend_still_raises_instead_of_substituting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TASK-REL-018 honesty contract survives the wiring: with no
    statsforecast backend, fit refuses — with calendar features present."""
    monkeypatch.setattr(adapters, "_SF_AutoARIMA", _UnavailableFake)
    end = datetime(2026, 12, 24, 12, 0, tzinfo=UTC)
    x, y = _history(end)
    with pytest.raises(StatsForecastUnavailableError):
        AutoARIMAAdapter().fit(x, y, as_of=end)


# ---------------------------------------------------------------------------
# Routing: the event-aware model must be selectable, on validation merit
# ---------------------------------------------------------------------------


def test_router_offers_auto_arima_where_history_supports_it() -> None:
    router = ModelRouter()
    moderate = router.select_candidates(
        SeriesMetadata(history_points=500, frequency_minutes=5), horizon_steps=12
    )
    rich = router.select_candidates(
        SeriesMetadata(history_points=3000, frequency_minutes=5), horizon_steps=12
    )
    short = router.select_candidates(
        SeriesMetadata(history_points=100, frequency_minutes=5), horizon_steps=12
    )
    assert "auto_arima" in moderate
    assert "auto_arima" in rich
    assert "auto_arima" not in short


# ---------------------------------------------------------------------------
# TASK-FUT-014: the real statsforecast 2.1.1 backend needs numpy arrays
# ---------------------------------------------------------------------------


def test_auto_arima_exog_fits_real_statsforecast_backend() -> None:
    """statsforecast 2.1.1's ``arima``/``auto_arima_f`` read
    ``xreg.dtype`` — an attribute only numpy arrays have. The adapter
    used to pass the calendar frame as a pandas DataFrame, so the fit
    raised ``'DataFrame' object has no attribute 'dtype'`` and the
    candidate never fitted (nor could predict, which reads the same
    attribute). Skipped where the library is absent, exactly like the
    other real-backend tests in this repo."""
    pytest.importorskip("statsforecast")
    end = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    # Seven days of grid: the calendar regressors are only full-rank
    # once all seven weekdays appear — with fewer days, day_of_week /
    # is_weekend / dow_sin / dow_cos are linearly dependent and
    # auto_arima refuses the fit as rank-deficient, unrelated to this
    # fix. Production refresh cycles use a 14-day lookback, so this
    # matches the real path.
    x, y = _history(end, days=7)
    adapter = AutoARIMAAdapter()
    adapter.fit(x, y, as_of=end)
    assert adapter.exog_used is True
    prediction = adapter.predict(horizon=12)
    assert len(prediction.point_forecast) == 12
    assert np.all(np.isfinite(prediction.point_forecast))
    assert prediction.metadata["exogenous_features"] == list(CALENDAR_FEATURE_COLUMNS)
