"""TASK-STR-FWD-019 WAVE-2 — stoch_reversion FORWARD_TEST lane entries.

Pins, in the test_fwd003 pattern:
1. EQUIVALENCE: the production modules (strategy_stoch_reversion core
   = the forex k14_raw cell + the k14_filt forex and k14_raw crypto
   thin variants) reproduce the judged rd2 harness
   (families3.sig_stoch) entry-for-entry on the fwd002 fixture slices.
2. REGISTRY/PARTITION: the new keys are FORWARD_TEST with the judged
   universes and FWD-006 risk fields, are in the daemon's
   forward-protocol partition, and are NOT in the VALIDATED partition.
3. VENUE MAPPING (forex entries): every lane_asset is a plain OANDA
   pair name in FOREX28_SYMBOLS and the entries carry forward_venues
   ["oanda_practice"].
4. STOP-CAP CONSISTENCY (FWD-012): the crypto entry declares
   max_stop_pct 0.90 >= its measured entry-bar stop maximum (SOLUSDT
   1d 58.74%; BTCUSDT 12.38% — 2.0 x ATR(14)/close over judged entry
   bars on the fwd002 fixtures, measured 2026-11-18); the forex
   entries declare no override and their measured maxima (k14_raw
   2.64%, k14_filt 2.14%, GBPJPY fixture) are <= 0.15.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_stoch_reversion as stoch
import strategy_stoch_reversion_crypto as stoch_c
import strategy_stoch_reversion_k14_filt as stoch_f
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

MEASURED_MAX_STOP = {
    "stoch_reversion": 0.0264,        # GBPJPY 1d entries (EURUSD 0.0206)
    "stoch_reversion_k14_filt": 0.0214,  # GBPJPY 1d entries
    "stoch_reversion_crypto": 0.5874,    # SOLUSDT 1d entries (BTCUSDT 0.1238)
}
GLOBAL_CAP = 0.15
FX_FIXTURES = ["FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"]


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", FX_FIXTURES)
def test_stoch_raw_forex_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_stoch(df, False, WARMUP)
    production = stoch.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", FX_FIXTURES)
def test_stoch_filt_forex_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_stoch(df, True, WARMUP)
    production = stoch_f.entries_for_frame(df, WARMUP)
    assert len(judged) >= 3, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_stoch_raw_crypto_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_stoch(df, False, WARMUP)
    production = stoch_c.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


def test_stoch_live_signal_reproduces_judged_bracket():
    df = _load("FX_EURUSD_1d.csv")
    judged = families3.sig_stoch(df, False, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:5]:
        sig = stoch.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3863)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert stoch.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0
    opens = [now - 3 * 86400, now - 2 * 86400, now - 86400 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(stoch._closed_frame(df, now_s=now)) == 3
    assert len(stoch_f._closed_frame(df, now_s=now)) == 3
    assert len(stoch_c._closed_frame(df, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

NEW_KEYS = {
    "stoch_reversion": ("FOREX28", 0.3863, 28.6),
    "stoch_reversion_k14_filt": ("FOREX28", 0.3519, 7.2),
    "stoch_reversion_crypto": ("CRYPTO30", 0.3706, 51.8),
}


def test_registry_lane_entries():
    import config_strategy as cs

    universes = {
        "CRYPTO30": cs.CRYPTO30_SYMBOLS,
        "FOREX28": cs.FOREX28_SYMBOLS,
    }
    for key, (universe, wr, edge) in NEW_KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["lane_assets"] == universes[universe], key
        assert entry["validated_assets"] == [], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert "TASK-STR-FWD-019 WAVE-2 near-miss admission" in entry["reason"], key

    validated = {
        k
        for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e["status"] == "VALIDATED"
    }
    assert not (set(NEW_KEYS) & validated)
    # The canonical core carries the audit §4 combo note.
    assert "0.083" in cs.PRODUCTION_STRATEGY_REGISTRY["stoch_reversion"]["reason"]


def test_daemon_partition_includes_new_keys():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    for key in NEW_KEYS:
        assert f"strategy_{key}" in entries, key
        assert daemon._lane_for_strategy(f"strategy_{key}") == "FORWARD_TEST", key


def test_registry_discovers_modules_on_demo_venue():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    reg.set_demo_venues({"binance_futures", "oanda_practice"})
    try:
        assert reg.executable(
            "strategy_stoch_reversion", "1d", "EURUSD", venue="oanda_practice"
        )[0]
        assert reg.executable(
            "strategy_stoch_reversion_k14_filt", "1d", "GBPJPY",
            venue="oanda_practice",
        )[0]
        assert reg.executable(
            "strategy_stoch_reversion_crypto", "1d", "BTCUSDT",
            venue="binance_futures",
        )[0]
        assert not reg.executable(
            "strategy_stoch_reversion_crypto", "1d", "EURUSD",
            venue="binance_futures",
        )[0]
    finally:
        reg.set_demo_venues(set())
    assert not reg.executable(
        "strategy_stoch_reversion_crypto", "1d", "BTCUSDT", venue="binance_futures"
    )[0]


# ---------------------------------------------------------------------------
# 3. Venue mapping (forex)
# ---------------------------------------------------------------------------

def test_forex_venue_mapping():
    import config_strategy as cs

    for key in ("stoch_reversion", "stoch_reversion_k14_filt"):
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["forward_venues"] == ["oanda_practice"], key
        for sym in entry["lane_assets"]:
            assert sym.isalpha() and sym.isupper(), sym
            assert sym in cs.FOREX28_SYMBOLS, sym


# ---------------------------------------------------------------------------
# 4. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    import config_strategy as cs

    for key, measured in MEASURED_MAX_STOP.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        if "max_stop_pct" in entry:
            assert entry["max_stop_pct"] > GLOBAL_CAP, key
            assert entry["max_stop_pct"] >= measured, key
        else:
            assert measured <= GLOBAL_CAP, key
    df = _load("SOLUSDT_1d.csv")
    atr = harness_atr(df, 14)
    entries = stoch_c.entries_for_frame(df, WARMUP)
    worst = max(2.0 * float(atr.iloc[i]) / float(df["close"].iloc[i])
                for i, _ in entries)
    assert worst == pytest.approx(MEASURED_MAX_STOP["stoch_reversion_crypto"],
                                  abs=0.005)
