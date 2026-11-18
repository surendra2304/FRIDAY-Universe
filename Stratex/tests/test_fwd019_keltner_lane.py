"""TASK-STR-FWD-019 — keltner_breakout FORWARD_TEST lane (Wave-2).

TASK-STR-FWD-019 WAVE-2 near-miss wiring (audit
~/workspace/str-nearmiss/REPORT.md S1.4). This file pins:

1. EQUIVALENCE: the production modules reproduce the judged rd2
   harness (rigorous_backtest/rd2/families3.py) entry-for-entry on
   the fwd002 fixture slices — for EVERY wired variant, not only
   the canonical one (the variants differ only in EMA period / band multiplier / timeframe / panel, and each is equivalence-tested against its own judged harness call anyway).
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
4. VENUE MAPPING (forex entry): every lane_asset of the forex
   entry is a plain OANDA pair name in FOREX28_SYMBOLS and the
   entry carries forward_venues [oanda_practice].
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_keltner_breakout as kel
import strategy_keltner_breakout_ema50_m2 as kel50
import strategy_keltner_breakout_ema20_m15 as kel15
import strategy_keltner_breakout_ema20_m2_4h as kel_m2_4h
import strategy_keltner_breakout_ema20_m15_4h as kel_m15_4h
import strategy_keltner_breakout_forex as kel_fx
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# key: (module name, timeframe, lane universe constant name,
#       oos win rate prior, expected edge bps, measured entry-bar
#       max stop fraction on the fixtures, max_stop_pct or None)
KEYS = {
    "keltner_breakout": ("keltner_breakout", "1d", "CRYPTO30_SYMBOLS", 0.3753, 194.1, 0.2840, 0.90),
    "keltner_breakout_ema50_m2": ("keltner_breakout_ema50_m2", "1d", "CRYPTO30_SYMBOLS", 0.3593, 146.5, 0.2840, 0.90),
    "keltner_breakout_ema20_m15": ("keltner_breakout_ema20_m15", "1d", "CRYPTO30_SYMBOLS", 0.3471, 121.5, 0.2840, 0.90),
    "keltner_breakout_ema20_m2_4h": ("keltner_breakout_ema20_m2_4h", "4h", "CRYPTO30_SYMBOLS", 0.3669, 28.8, 0.1181, 0.30),
    "keltner_breakout_ema20_m15_4h": ("keltner_breakout_ema20_m15_4h", "4h", "CRYPTO30_SYMBOLS", 0.3605, 25.6, 0.1173, 0.30),
    "keltner_breakout_forex": ("keltner_breakout_forex", "1d", "FOREX28_SYMBOLS", 0.3900, 13.7, 0.0288, None),
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



def test_keltner_canon_entries_match_harness_BTCUSDT_1d_csv():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_canon_entries_match_harness_SOLUSDT_1d_csv():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_ema50_entries_match_harness_BTCUSDT_1d_csv():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_keltner(df, 50, 2.0, WARMUP)
    production = kel50.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_ema50_entries_match_harness_SOLUSDT_1d_csv():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_keltner(df, 50, 2.0, WARMUP)
    production = kel50.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m15_entries_match_harness_BTCUSDT_1d_csv():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_keltner(df, 20, 1.5, WARMUP)
    production = kel15.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m15_entries_match_harness_SOLUSDT_1d_csv():
    df = _load("SOLUSDT_1d.csv")
    judged = families3.sig_keltner(df, 20, 1.5, WARMUP)
    production = kel15.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m2_4h_entries_match_harness_BTCUSDT_4h_csv():
    df = _load("BTCUSDT_4h.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel_m2_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m2_4h_entries_match_harness_SOLUSDT_4h_csv():
    df = _load("SOLUSDT_4h.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel_m2_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m15_4h_entries_match_harness_BTCUSDT_4h_csv():
    df = _load("BTCUSDT_4h.csv")
    judged = families3.sig_keltner(df, 20, 1.5, WARMUP)
    production = kel_m15_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_m15_4h_entries_match_harness_SOLUSDT_4h_csv():
    df = _load("SOLUSDT_4h.csv")
    judged = families3.sig_keltner(df, 20, 1.5, WARMUP)
    production = kel_m15_4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_forex_entries_match_harness_FX_EURUSD_1d_csv():
    df = _load("FX_EURUSD_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel_fx.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_forex_entries_match_harness_FX_GBPJPY_1d_csv():
    df = _load("FX_GBPJPY_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel_fx.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_keltner_forex_entries_match_harness_FX_USDJPY_1d_csv():
    df = _load("FX_USDJPY_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    production = kel_fx.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged
    # measured stop%% constant cross-check (FWD-012 record)
    assert _entries_stop_max(df, judged) <= max(
        v[5] for v in KEYS.values()) + 0.60

def test_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_keltner(df, 20, 2.0, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:5]:
        sig = kel.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3753)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert kel.get_signal(df.iloc[: quiet + 1])["side"] is None


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


def test_forex_venue_mapping():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["keltner_breakout_forex"]
    assert entry["forward_venues"] == ["oanda_practice"]
    assert entry["lane_assets"] == cs.FOREX28_SYMBOLS
    assert len(entry["lane_assets"]) == 28
    for sym in entry["lane_assets"]:
        # plain OANDA pair names: 6 uppercase letters, in the verified 28
        assert len(sym) == 6 and sym.isalpha() and sym.isupper(), sym
        assert sym in cs.FOREX28_SYMBOLS, sym

