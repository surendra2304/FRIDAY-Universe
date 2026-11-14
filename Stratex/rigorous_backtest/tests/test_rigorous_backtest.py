"""Tests for the rigorous backtest harness (TASK-STR-BT-001).

Unit tests use small deterministic toy frames to verify MECHANICS only
(simulation semantics, fold attribution, guards). They are never used as
performance evidence — all reported results come from real, provenance-
checked exchange data via run_all.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG.parent))

from rigorous_backtest import data_feed, factory_eval, module_eval, simulator, walkforward  # noqa: E402
from rigorous_backtest.simulator import Costs, Trade, simulate_module  # noqa: E402


def toy_df(prices, start="2025-01-01", freq="1h"):
    idx = pd.date_range(start, periods=len(prices), freq=freq, tz="UTC")
    close = np.asarray(prices, dtype=float)
    return pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close, "volume": np.ones(len(close)),
    }, index=idx)


# ---------------- data integrity guards ----------------

def test_gap_audit_reports_missing_bars_without_filling():
    idx = pd.to_datetime(["2025-01-01T00:00Z", "2025-01-01T01:00Z", "2025-01-01T04:00Z"])
    df = pd.DataFrame({"open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1],
                       "close": [1, 1, 1], "volume": [1, 1, 1]}, index=idx)
    audit = data_feed.gap_audit(df, "1h")
    assert audit["missing_bars"] == 2
    assert len(df) == 3  # nothing was fabricated to fill the hole


def test_fetch_failure_is_a_hard_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(data_feed.urllib.request, "urlopen", boom)
    with pytest.raises(data_feed.DataUnavailable):
        data_feed.load_dataset("BTCUSDT", "1h", "2025-01", "2025-01")


def test_no_synthetic_data_machinery_in_package():
    for name in ("data_feed.py", "factory_eval.py", "module_eval.py",
                 "simulator.py", "walkforward.py"):
        src = (PKG / name).read_text(encoding="utf-8")
        assert "np.random" not in src, name
        assert "random." not in src.replace("random walk", ""), name
        assert "synthetic" not in src.lower().replace(
            "never fabricates", "").replace("no synthetic", "").replace(
            "synthetic substitution", "").replace("synthetic data", ""), name


# ---------------- cost model ----------------

def test_costs_reduce_a_winning_trade():
    df = toy_df([100.0] * 5 + [110.0] * 5)
    free = simulate_module(df, [(0, "LONG", 90.0, 105.0)], "T", Costs(0.0, 0.0))
    costed = simulate_module(df, [(0, "LONG", 90.0, 105.0)], "T", Costs())
    assert len(free) == len(costed) == 1
    assert costed[0].net_return < free[0].net_return
    # 16 bps round trip on a ~5% winner costs roughly 0.16% of notional.
    assert free[0].net_return - costed[0].net_return == pytest.approx(0.0016, abs=0.0004)


# ---------------- simulator semantics ----------------

def test_stop_wins_when_both_levels_inside_one_bar():
    df = toy_df([100.0, 100.0, 100.0])
    df.iloc[2, df.columns.get_loc("high")] = 130.0
    df.iloc[2, df.columns.get_loc("low")] = 70.0
    trades = simulate_module(df, [(0, "LONG", 90.0, 120.0)], "T", Costs(0.0, 0.0))
    assert len(trades) == 1 and trades[0].exit_reason == "SL"


def test_entry_is_next_bar_open_not_signal_close():
    df = toy_df([100.0, 100.0, 100.0, 100.0])
    df.iloc[1, df.columns.get_loc("open")] = 102.0
    df.iloc[2, df.columns.get_loc("high")] = 200.0  # TP certain on bar 2
    trades = simulate_module(df, [(0, "LONG", 90.0, 150.0)], "T", Costs(0.0, 0.0))
    assert trades[0].entry_price == 102.0


# ---------------- walk-forward attribution ----------------

def _trade(entry):
    return Trade("T", pd.Timestamp(entry, tz="UTC"), pd.Timestamp(entry, tz="UTC"),
                 "LONG", 100.0, 101.0, 0.01, "TP")


def test_oos_report_excludes_pre_fold_trades():
    trades = [_trade("2024-01-15"), _trade("2024-08-15"), _trade("2025-03-15")]
    rep = walkforward.oos_report(trades)
    assert rep["pooled_oos"]["trades"] == 2  # the 2024-01 trade is warm-up era
    assert rep["per_fold"]["W1"]["trades"] == 1
    assert rep["per_fold"]["W2"]["trades"] == 1


# ---------------- feature causality guard ----------------

def test_causality_checker_accepts_causal_and_rejects_peeking():
    df = toy_df(np.linspace(100, 200, 8000))
    causal = lambda d: d.assign(ema=d["close"].ewm(span=20).mean())  # noqa: E731
    peeking = lambda d: d.assign(future=d["close"].shift(-5))  # noqa: E731
    assert module_eval._features_causal(causal, df) is True
    assert module_eval._features_causal(peeking, df) is False


# ---------------- factory replication ----------------

def test_fast_simulator_matches_literal_legacy_loop():
    """simulate_variant (vectorised exit search) must reproduce the literal
    legacy loop semantics in simulator.simulate_factory_original."""
    rng = np.random.default_rng(7)  # toy fixture only — mechanics, not evidence
    steps = rng.normal(0, 0.004, 3000).cumsum()
    df = toy_df(100 * np.exp(steps), freq="5min")
    ls, ss = factory_eval.variant_signals(df, "macd_bb_confluence",
                                          {"macd_fast": 12, "macd_slow": 26,
                                           "macd_signal": 9, "bb_period": 20, "bb_std": 2.0})
    atr = factory_eval.compute_atr(df, 14).to_numpy()
    fast = factory_eval.simulate_variant(df, ls, ss, atr, 1.5, 3.0, "T", Costs(0.0, 0.0))
    literal = simulator.simulate_factory_original(df, ls, ss, 1.5, 3.0, atr, "T", Costs(0.0, 0.0))
    assert len(fast) == len(literal)
    for a, b in zip(fast, literal):
        assert a.entry_time == b.entry_time and a.exit_time == b.exit_time
        assert a.net_return == pytest.approx(b.net_return, abs=1e-12)
