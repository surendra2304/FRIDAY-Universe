"""TASK-STR-FWD-025 — the forming-bar guard must be resolution-independent.

The lane modules' ``_closed_frame`` drops still-forming trailing bars
before any signal is evaluated. It used to compute bar-open epoch
seconds as ``idx.view("int64") / 1e9`` (or ``idx.asi8 / 1e9``), which
is only correct when the frame's DatetimeIndex has nanosecond
resolution. pandas 3 infers non-nanosecond resolutions (``pd.to_datetime
(..., unit="s")`` yields microseconds), so the opens came out 1000x
too small, every bar passed the closed test, and the still-forming
bar WAS evaluated — a trading-safety defect (trading on incomplete
data), reproduced on main c52933e1 by test_fwd003's and test_fwd020's
forming-bar tests.

The fix computes epoch seconds by timedelta division
(``(idx - epoch).total_seconds()``), the pattern the mtf_confluence
family already used. This file pins the invariant across every index
resolution pandas 3 can produce, for one representative of each
fixed template class plus a delegating wrapper (which inherits its
core's fix) and the weekly sleeve module.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_adx_ema_bare as adx_bare
import strategy_bollinger_trend as bol
import strategy_donchian_turtle as don_core
import strategy_donchian_turtle_n20_b26 as don_wrap
import strategy_dow_effect as dow
import strategy_keltner_breakout as kel
import strategy_shock_breakout as shk
import strategy_sleeve_shock_breakout as sleeve
import strategy_supertrend_bare as stb
import strategy_xs_momentum as xs_mom

NOW = 1_800_000_000.0  # fixed epoch, arbitrary (same as fwd003/fwd020)
RESOLUTIONS = ["ns", "us", "ms", "s"]

OPENS_1D = [NOW - 3 * 86400, NOW - 2 * 86400, NOW - 86400 - 1, NOW - 3600]
OPENS_4H = [NOW - 12 * 3600, NOW - 8 * 3600, NOW - 4 * 3600 - 1, NOW - 3600]
OPENS_1WK = [NOW - 21 * 86400, NOW - 14 * 86400, NOW - 7 * 86400 - 1, NOW - 86400]


def _frame(opens, resolution: str) -> pd.DataFrame:
    idx = pd.to_datetime(opens, unit="s", utc=True).as_unit(resolution)
    return pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )


def _assert_closed_prefix(out: pd.DataFrame, opens) -> None:
    # Exactly the three closed bars survive, as instants, in order;
    # the still-forming fourth bar (opens[-1]) is gone.
    assert len(out) == 3
    expected = pd.to_datetime(opens[:3], unit="s", utc=True)
    assert list(out.index) == list(expected)


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_forming_bar_dropped_at_every_resolution_1d(resolution):
    df = _frame(OPENS_1D, resolution)
    _assert_closed_prefix(bol._closed_frame(df, now_s=NOW), OPENS_1D)
    _assert_closed_prefix(shk._closed_frame(df, now_s=NOW), OPENS_1D)
    _assert_closed_prefix(dow._closed_frame(df, now_s=NOW), OPENS_1D)
    _assert_closed_prefix(xs_mom._closed_frame(df, now_s=NOW), OPENS_1D)
    # Core with an explicit bar_seconds parameter, and a thin wrapper
    # that delegates to it (the wrapper inherits the core's fix).
    _assert_closed_prefix(don_core._closed_frame(df, 86400, NOW), OPENS_1D)
    _assert_closed_prefix(don_wrap._closed_frame(df, now_s=NOW), OPENS_1D)
    # The _closed_frame_s template (keltner/ha/bar_patterns/psar cores).
    _assert_closed_prefix(kel._closed_frame_s(df, 86400, NOW), OPENS_1D)


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_forming_bar_dropped_at_every_resolution_4h(resolution):
    df = _frame(OPENS_4H, resolution)
    _assert_closed_prefix(stb._closed_frame(df, now_s=NOW), OPENS_4H)
    _assert_closed_prefix(adx_bare._closed_frame(df, now_s=NOW), OPENS_4H)


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_forming_bar_dropped_at_every_resolution_1wk(resolution):
    df = _frame(OPENS_1WK, resolution)
    _assert_closed_prefix(sleeve._closed_frame(df, now_s=NOW), OPENS_1WK)


def test_forming_bar_dropped_for_tz_naive_frame():
    # The guard also held for tz-naive frames under pandas 2 (the
    # daemon's contract is UTC); the fix must not regress that.
    idx = pd.to_datetime(OPENS_1D, unit="s").as_unit("us")
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    out = bol._closed_frame(df, now_s=NOW)
    assert len(out) == 3
    assert list(out.index) == list(idx[:3])
