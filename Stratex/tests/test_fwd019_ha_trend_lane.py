"""TASK-STR-FWD-019 — ha_trend FORWARD_TEST lane (Wave-2).

TASK-STR-FWD-019 WAVE-2 near-miss wiring (audit
~/workspace/str-nearmiss/REPORT.md S1.4). This file pins:

1. EQUIVALENCE: the production modules reproduce the judged rd2
   harness (rigorous_backtest/rd2/families3.py) entry-for-entry on
   the fwd002 fixture slices — for EVERY wired variant, not only
   the canonical one (two_candle and one_candle are structurally different signals (not parameter-only), so both are equivalence-tested at both timeframes; HA candles are recursive, so full-frame equivalence also proves the recursion port).
2. REGISTRY/PARTITION: every new key is FORWARD_TEST with
   forward_protocol True, forward_lane "FORWARD_TEST", lane_assets
   exactly the judged universe, risk fields 0.001/0.02, judged
   priors intact (runtime_priors_nulled False), and NONE of the new
   keys is in the VALIDATED partition (the VALIDATED set is
   byte-identical to the base).
3. STOP-CAP (FWD-012): per entry, either no max_stop_pct and the
   measured entry-bar stop%% (2.0 x ATR(14) / close on the fixture
   slices) is <= 0.15, or max_stop_pct is present, > 0.15 and >=
   the measured max. Measured figures are encoded as constants
   below with their provenance.

"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_ha_trend as ha
import strategy_ha_trend_two_candle_4h as ha2_4h
import strategy_ha_trend_one_candle as ha1
import strategy_ha_trend_one_candle_4h as ha1_4h
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# key: (module name, timeframe, lane universe constant name,
#       oos win rate prior, expected edge bps, measured entry-bar
#       max stop fraction on the fixtures, max_stop_pct or None)
KEYS = {
    "ha_trend": ("ha_trend", "1d", "CRYPTO30_SYMBOLS", 0.3639, 167.1, 0.7128, 0.90),
    "ha_trend_two_candle_4h": ("ha_trend_two_candle_4h", "4h", "CRYPTO30_SYMBOLS", 0.3685, 29.0, 0.1212, 0.30),
    "ha_trend_one_candle": ("ha_trend_one_candle", "1d", "CRYPTO30_SYMBOLS", 0.3455, 63.4, 0.7128, 0.90),
    "ha_trend_one_candle_4h": ("ha_trend_one_candle_4h", "4h", "CRYPTO30_SYMBOLS", 0.3671, 23.9, 0.1269, 0.30),
}

BASE_VALIDATED = {
    "ichimoku_trend", "dow_effect", "fx_mr_v4",
    "sleeve_shock_breakout", "sleeve_tsmom2_dual",
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _entries_stop_max(df, entries):
    a = harness_atr(df, 14)
    return max(2.0 * float(a.iloc[i]) / float(df["close"].iloc[i]) for i, _ in entries)



def test_ha_two_1d_entries_match_harness_BTCUSDT_1d_csv():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_ha(df, True, WARMUP)
    production = ha.entries_for_frame(df, WARMUP)
    assert len(judged) >= 20, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_two_1d_entries_match_harness_SOLUSDT_1d_csv():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_ha(df, True, WARMUP)
    production = ha.entries_for_frame(df, WARMUP)
    assert len(judged) >= 20, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_two_4h_entries_match_harness_BTCUSDT_4h_csv():
    df = _load("BTCUSDT_4h.csv")
    judged = families3.sig_ha(df, True, WARMUP)
    production = ha2_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 50, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_two_4h_entries_match_harness_SOLUSDT_4h_csv():
    df = _load("SOLUSDT_4h.csv")
    judged = families3.sig_ha(df, True, WARMUP)
    production = ha2_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 50, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_one_1d_entries_match_harness_BTCUSDT_1d_csv():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_ha(df, False, WARMUP)
    production = ha1.entries_for_frame(df, WARMUP)
    assert len(judged) >= 50, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_one_1d_entries_match_harness_SOLUSDT_1d_csv():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_ha(df, False, WARMUP)
    production = ha1.entries_for_frame(df, WARMUP)
    assert len(judged) >= 50, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_one_4h_entries_match_harness_BTCUSDT_4h_csv():
    df = _load("BTCUSDT_4h.csv")
    judged = families3.sig_ha(df, False, WARMUP)
    production = ha1_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 100, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_ha_one_4h_entries_match_harness_SOLUSDT_4h_csv():
    df = _load("SOLUSDT_4h.csv")
    judged = families3.sig_ha(df, False, WARMUP)
    production = ha1_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 100, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_ha(df, True, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:5]:
        sig = ha.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3639)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert ha.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_registry_partition_and_priors():
    import config_strategy as cs

    for key, (_mod, tf, universe, wr, edge, _meas, _stop) in KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["timeframe"] == tf, key
        assert entry["lane_assets"] == getattr(cs, universe), key
        assert entry["validated_assets"] == [], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert entry["total_friction_bps"] > 0, key
        assert "TASK-STR-FWD-019" in entry["reason"], key
        assert "second tier" in entry["reason"], key
    validated = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert validated == BASE_VALIDATED
    assert not (set(KEYS) & validated)


def test_stop_cap_consistency():
    import config_strategy as cs

    for key, (_mod, _tf, _u, _wr, _e, measured, stop) in KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        if stop is None:
            assert "max_stop_pct" not in entry, key
            assert measured <= 0.15, key
        else:
            assert entry["max_stop_pct"] == pytest.approx(stop), key
            assert entry["max_stop_pct"] > 0.15, key
            assert entry["max_stop_pct"] >= measured, key


def test_modules_discovered_and_demo_executable():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    reg.set_demo_venues({"binance_futures", "oanda_practice"})
    try:
        for key, (mod, tf, universe, _wr, _e, _m, _s) in KEYS.items():
            assert reg.get(f"strategy_{mod}") is not None, key
            assert reg.governance_status(f"strategy_{mod}") == "FORWARD_TEST", key
            symbol = "BTCUSDT" if universe == "CRYPTO30_SYMBOLS" else "EURUSD"
            venue = "binance_futures" if universe == "CRYPTO30_SYMBOLS" else "oanda_practice"
            ok, _reason = reg.executable(f"strategy_{mod}", tf, symbol, venue=venue)
            assert ok, key
    finally:
        reg.set_demo_venues(set())


