"""Tests for TASK-IG2-STR-04 walkforward_gate (stdlib-only, offline).

Deterministic hand-built price paths only — mechanics evidence, never
performance evidence (same rule as the harness's own test suite).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.walkforward_gate import (  # noqa: E402
    GateConfig, GateFailed, evaluate_walk_forward, require_gate,
    rolling_windows, simulate_signals,
)

CFG = GateConfig(train_bars=60, test_bars=40, min_windows=3,
                 min_pooled_test_trades=3)


def make_bars(closes):
    bars = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        bars.append({"time": i, "open": o, "high": max(o, c) * 1.001,
                     "low": min(o, c) * 0.999, "close": c})
        prev = c
    return bars


def trend_closes(n, rate=0.005, dip_every=25):
    closes = []
    price = 100.0
    for i in range(n):
        price *= 1.0 + rate
        closes.append(price * (0.96 if (i + 1) % dip_every == 0 else 1.0))
    return closes


def fit_trend(train_bars):
    return "LONG" if train_bars[-1]["close"] >= train_bars[0]["close"] else "SHORT"


def trend_signal_fn(view, params):
    """One bracket signal every 8 bars of the test segment (the view's
    train segment is warm-up only: signals start at the test boundary)."""
    train_len = CFG.train_bars
    out = []
    entry_ref = None
    for i in range(train_len, len(view) - 1, 8):
        entry_ref = view[i]["close"]
        if params == "LONG":
            out.append((i, "LONG", entry_ref * 0.975, entry_ref * 1.03))
        else:
            out.append((i, "SHORT", entry_ref * 1.025, entry_ref * 0.97))
    return out


def always_long_signal_fn(view, params):
    train_len = CFG.train_bars
    out = []
    for i in range(train_len, len(view) - 1, 8):
        ref = view[i]["close"]
        out.append((i, "LONG", ref * 0.975, ref * 1.03))
    return out


# ---------------- window geometry ----------------

def test_rolling_windows_never_overlap_train_and_test():
    ws = rolling_windows(1000, GateConfig(train_bars=200, test_bars=100))
    assert len(ws) == 8
    for w in ws:
        assert w["train"][1] == w["test"][0]          # test starts where train ends
        assert w["train"][0] < w["train"][1] <= w["test"][0] < w["test"][1]


def test_rolling_windows_empty_when_data_too_short():
    assert rolling_windows(250, GateConfig(train_bars=200, test_bars=100)) == []


# ---------------- gate behaviour ----------------

def test_trend_candidate_passes_gate_on_persistent_trend():
    bars = make_bars(trend_closes(60 + 3 * 40))
    report = evaluate_walk_forward(bars, trend_signal_fn, fit_fn=fit_trend, config=CFG)
    assert report.pooled["trades"] >= 3
    assert report.pooled["expectancy_net"] > 0
    assert report.passed, report.to_dict()
    assert require_gate(report) is report


def test_overfit_always_long_fails_when_regime_flips():
    closes = []
    price = 100.0
    for i in range(400):
        price *= 1.005 if i < 100 else 0.995
        closes.append(price)
    bars = make_bars(closes)
    report = evaluate_walk_forward(bars, always_long_signal_fn, config=CFG)
    assert not report.passed
    assert report.checks["positive_window_fraction_gte_min"] is False
    with pytest.raises(GateFailed):
        require_gate(report)


def test_silent_candidate_fails_on_trade_count():
    bars = make_bars(trend_closes(60 + 3 * 40))
    report = evaluate_walk_forward(bars, lambda view, params: [], config=CFG)
    assert not report.passed
    assert report.checks["pooled_test_trades_gte_min"] is False
    assert report.pooled["trades"] == 0


def test_fit_fn_sees_train_segment_only():
    seen = []

    def recording_fit(train_bars):
        seen.append((len(train_bars), train_bars[0]["time"], train_bars[-1]["time"]))
        return fit_trend(train_bars)

    bars = make_bars(trend_closes(60 + 3 * 40))
    evaluate_walk_forward(bars, trend_signal_fn, fit_fn=recording_fit, config=CFG)
    assert len(seen) == 3
    for length, first, last in seen:
        assert length == CFG.train_bars
        assert last - first == CFG.train_bars - 1


def test_trades_counted_only_when_entry_inside_test_segment():
    bars = make_bars(trend_closes(60 + 3 * 40))

    def warmup_only_signals(view, params):
        # signals only in the warm-up (train) part of the view
        return [(5, "LONG", view[5]["close"] * 0.9, view[5]["close"] * 1.5)]

    report = evaluate_walk_forward(bars, warmup_only_signals, config=CFG)
    assert report.pooled["trades"] == 0
    assert not report.passed


# ---------------- simulation / costs ----------------

def test_costs_reduce_a_winning_trade():
    closes = [100.0] * 5 + [110.0] * 10
    bars = make_bars(closes)
    sig = [(0, "LONG", 90.0, 105.0)]
    free = simulate_signals(bars, sig, GateConfig(fee_bps_per_side=0.0, slip_bps_per_side=0.0))
    costed = simulate_signals(bars, sig, CFG)
    assert len(free) == len(costed) == 1
    assert costed[0].net_return < free[0].net_return
    assert free[0].exit_reason == "TP"


def test_stop_wins_when_both_levels_inside_one_bar():
    bars = make_bars([100.0, 100.0, 100.0])
    bars[2]["high"] = 130.0
    bars[2]["low"] = 70.0
    trades = simulate_signals(bars, [(0, "LONG", 90.0, 110.0)], CFG)
    assert len(trades) == 1
    assert trades[0].exit_reason == "SL"
