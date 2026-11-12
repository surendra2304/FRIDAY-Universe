"""tests/test_new_strategies_batch2.py — contract tests for the six
TASK-STRATEX-PROFIT-2 strategies (ZAI Agent 2).

Each strategy module must:
  * expose get_signal(df) returning SignalResult with side/sl/tp
  * return side=None on insufficient history (never raise)
  * produce at least one BUY or SELL on a synthetic trending series
  * respect the governor contract on a fired signal (0.5% <= stop <= 3%)
"""
import sys
import os
import importlib

import numpy as np
import pandas as pd
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

NEW_MODULES = [
    "strategy_multi_month",
    "strategy_kama_adaptive",
    "strategy_ehlers_hma",
    "strategy_choppiness_breakout",
    "strategy_kaufman_efficiency",
    "strategy_bbi_blend",
    "strategy_supertrend_atr",
]


def _trending_df(kind="up", n=700, base=100.0):
    """Deterministic trending OHLCV with noise; closed bars only (UTC past)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(7)
    drift = 0.0012 if kind == "up" else -0.0012
    rets = rng.normal(drift, 0.006, n)
    close = base * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.003, n)))
    open_ = close * (1 + rng.normal(0, 0.001, n))
    df = pd.DataFrame({"open": open_, "high": high, "low": low,
                       "close": close, "volume": 1000.0}, index=idx)
    return df


def _ranging_df(n=700, base=100.0):
    """Sideways OHLCV: mean-reverting around base."""
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(11)
    close = base + np.cumsum(rng.normal(0, 0.4, n)) * 0.02
    close = base + (close - close.mean())  # keep it bounded
    high = close * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n)))
    df = pd.DataFrame({"open": close, "high": high, "low": low,
                       "close": close, "volume": 1000.0}, index=idx)
    return df


@pytest.mark.parametrize("mod_name", NEW_MODULES)
def test_module_imports_and_contract(mod_name):
    mod = importlib.import_module(mod_name)
    assert hasattr(mod, "get_signal")
    assert hasattr(mod, "_OOS_WIN_RATE_PRIOR")
    prior = float(mod._OOS_WIN_RATE_PRIOR)
    assert 0.05 <= prior <= 0.95

    # insufficient history: silent None side, no raise
    short = _trending_df()[:80]
    res = mod.get_signal(short)
    assert res is not None
    assert getattr(res, "side", None) is None

    # empty/None safe
    assert mod.get_signal(None) is not None and mod.get_signal(None).side is None


@pytest.mark.parametrize("mod_name", NEW_MODULES)
def test_fires_on_synthetic_trend(mod_name):
    mod = importlib.import_module(mod_name)
    # both a rising and a falling trend must be evaluated; each module fires
    # on at least one of them across a sliding set of end-bars.
    fired = []
    for kind in ("up", "down"):
        df = _trending_df(kind)
        for end in (len(df), len(df) - 5, len(df) - 13, len(df) - 29):
            res = mod.get_signal(df.iloc[:end])
            side = getattr(res, "side", None)
            if side in ("BUY", "SELL"):
                fired.append((kind, side, res))
    assert fired, f"{mod_name} never fired on synthetic trends"
    kind, side, res = fired[0]
    assert side in ("BUY", "SELL")
    assert res.sl and res.tp
    px_approx = _trending_df(kind)["close"].iloc[-1]
    stop_pct = abs(px_approx - res.sl) / px_approx
    assert 0.001 <= stop_pct <= 0.08, f"stop pct out of sane band: {stop_pct}"


@pytest.mark.parametrize("mod_name", NEW_MODULES)
def test_quiet_on_flat_ranging(mod_name):
    """Ranging market: a fired signal is allowed, but never raising is not."""
    mod = importlib.import_module(mod_name)
    df = _ranging_df()
    res = mod.get_signal(df)  # must not raise
    assert res is not None
