"""TASK-STR-FWD-019 (Wave-2, crew A) — macd_trend lane wiring.

One RD-002 near-miss cell joins the FORWARD_TEST lane: macd_trend /
hist_raw @ crypto30 1d (near-miss audit §1.4 row 6 — 369 OOS trades,
+5.840%/trade, PF 1.5522, 2/5 folds flagged weak, PF @2x costs 1.5330,
the audit's most cost-robust row; also a Stage-C sleeve-book member
stream under its sleeve key — a distinct judged object).

Key-collision check (mandatory): at the base
d79723620a36d9175cef9a22b42aab2dc3fd5914 there is NO macd key in
PRODUCTION_STRATEGY_REGISTRY and no strategy_macd_trend.py module —
verified by grep before wiring; the plain key ``macd_trend`` is used.

This file pins: (1) equivalence vs the judged harness
(rigorous_backtest/rd2/families3.py sig_macd, unfiltered) on the
fwd002 fixture slices, (2) registry/partition shape, (3) FWD-012
stop-cap consistency.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_macd_trend as macd
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# FWD-012 stop-cap measurements (2026-11-18, this crew): judged stop
# 2.5 x ATR(14) / close on the fwd002 1d fixture slices — max over ALL
# post-warmup bars 0.8910 (SOLUSDT_1d), max at entry bars 0.4804
# (SOLUSDT_1d). Both exceed the 0.15 engine-global cap.
MEASURED_MAX_ALL = 0.8910
MEASURED_MAX_ENTRIES = 0.4804
CHOSEN_MAX_STOP = 0.90


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_macd(df, False, WARMUP)
    production = macd.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


def test_live_signal_reproduces_judged_bracket():
    from rigorous_backtest.rd.common import atr as harness_atr

    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_macd(df, False, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    assert judged
    for i, side in judged[:6]:
        sig = macd.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.5 * atr[i])
        assert sig["tp_dist"] == pytest.approx(5.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.4201)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert macd.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_atr_matches_judged_harness():
    import numpy as np

    from rigorous_backtest.rd.common import atr as harness_atr

    df = _load("SOLUSDT_1d.csv")
    np.testing.assert_allclose(
        macd.atr14(df).to_numpy(), harness_atr(df, 14).to_numpy()
    )


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_entry():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    entry = PRODUCTION_STRATEGY_REGISTRY["macd_trend"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)"
    assert entry["timeframe"] == "1d"
    assert entry["execution_model"] == "RULE_BASED"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["lane_assets"] == CRYPTO30_SYMBOLS
    assert entry["validated_assets"] == []
    assert entry["risk_per_trade_pct"] == 0.001
    assert entry["max_heat_pct"] == 0.02
    assert entry["total_friction_bps"] == 16.0
    assert entry["minimum_required_edge"] == 0.0005
    assert entry["oos_win_rate_prior"] == pytest.approx(0.4201)
    assert entry["expected_net_edge_bps"] == pytest.approx(584.0)
    assert entry["runtime_priors_nulled"] is False
    # The weak folds and the sleeve-stream membership are on the record.
    assert "2/5 positive folds" in entry["reason"]
    assert "WEAK" in entry["reason"]
    assert "sleeve" in entry["reason"]

    validated = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert "macd_trend" not in validated
    assert validated == {
        "ichimoku_trend",
        "dow_effect",
        "fx_mr_v4",
        "sleeve_shock_breakout",
        "sleeve_tsmom2_dual",
    }


def test_daemon_lane_partition():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    assert "strategy_macd_trend" in daemon._forward_protocol_entries()
    assert daemon._lane_for_strategy("strategy_macd_trend") == "FORWARD_TEST"


def test_registry_demo_venue_execution():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    try:
        reg.set_demo_venues({"binance_futures"})
        assert reg.executable(
            "strategy_macd_trend", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not reg.executable(
            "strategy_macd_trend", "1d", "BTCUSDT", venue="oanda"
        )[0]
        assert not reg.executable(
            "strategy_macd_trend", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    entry = PRODUCTION_STRATEGY_REGISTRY["macd_trend"]
    # Measured judged stop exceeds the 0.15 cap (max 0.8910 over all
    # post-warmup bars; 0.4804 at entry bars), so the override must be
    # present, above the cap, and at/above the measured maximum.
    assert entry["max_stop_pct"] == pytest.approx(CHOSEN_MAX_STOP)
    assert entry["max_stop_pct"] > 0.15
    assert entry["max_stop_pct"] >= MEASURED_MAX_ALL
    assert MEASURED_MAX_ENTRIES > 0.15
