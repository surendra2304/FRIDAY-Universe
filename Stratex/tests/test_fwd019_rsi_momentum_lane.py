"""TASK-STR-FWD-019 WAVE-2 — rsi_momentum FORWARD_TEST lane entries.

Pins, in the test_fwd003 pattern:
1. EQUIVALENCE: the production modules (strategy_rsi_momentum core +
   the rsi7_60_40 and forex thin variants) reproduce the judged rd2
   harness (families3.sig_rsi_momentum) entry-for-entry on the fwd002
   fixture slices.
2. REGISTRY/PARTITION: the new keys are FORWARD_TEST with the judged
   universes and FWD-006 risk fields, are in the daemon's
   forward-protocol partition, and are NOT in the VALIDATED partition.
3. VENUE MAPPING (forex entry): every lane_asset is a plain OANDA pair
   name in FOREX28_SYMBOLS and the entry carries forward_venues
   ["oanda_practice"].
4. STOP-CAP CONSISTENCY (FWD-012): crypto entries declare
   max_stop_pct 0.90 >= the measured entry-bar stop maxima (SOLUSDT
   1d: rsi14 20.21%, rsi7 32.94%; BTCUSDT 1d: 9.87% / 10.82% — the
   2.0 x ATR(14)/close distribution over judged entry bars on the
   fwd002 fixtures, measured 2026-11-18); the forex entry declares no
   override and its measured maximum (2.64%, GBPJPY fixture) is
   <= 0.15.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_rsi_momentum as rsi
import strategy_rsi_momentum_forex as rsi_fx
import strategy_rsi_momentum_rsi7_60_40 as rsi7
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# FWD-012 measurements (2026-11-18, fwd002 fixtures, judged entry bars,
# stop% = 2.0 * ATR(14) / close at the entry bar):
MEASURED_MAX_STOP = {
    "rsi_momentum": 0.2021,          # SOLUSDT 1d entries (BTCUSDT: 0.0987)
    "rsi_momentum_rsi7_60_40": 0.3294,  # SOLUSDT 1d entries (BTCUSDT: 0.1082)
    "rsi_momentum_forex": 0.0264,    # GBPJPY 1d entries (EURUSD 0.0158, USDJPY 0.0165)
}
GLOBAL_CAP = 0.15


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_rsi14_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_rsi_momentum(df, 14, 55.0, 45.0, WARMUP)
    production = rsi.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_rsi7_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_rsi_momentum(df, 7, 60.0, 40.0, WARMUP)
    production = rsi7.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize(
    "fixture", ["FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"]
)
def test_rsi_forex_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_rsi_momentum(df, 14, 55.0, 45.0, WARMUP)
    production = rsi_fx.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


def test_rsi_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = families3.sig_rsi_momentum(df, 14, 55.0, 45.0, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:5]:
        sig = rsi.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3642)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert rsi.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0
    opens = [now - 3 * 86400, now - 2 * 86400, now - 86400 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(rsi._closed_frame(df, now_s=now)) == 3
    assert len(rsi7._closed_frame(df, now_s=now)) == 3
    assert len(rsi_fx._closed_frame(df, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

NEW_KEYS = {
    "rsi_momentum": ("CRYPTO30", 0.3642, 91.3),
    "rsi_momentum_rsi7_60_40": ("CRYPTO30", 0.3470, 85.6),
    "rsi_momentum_forex": ("FOREX28", 0.3721, 8.9),
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
            "strategy_rsi_momentum", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert reg.executable(
            "strategy_rsi_momentum_rsi7_60_40", "1d", "SOLUSDT",
            venue="binance_futures",
        )[0]
        assert reg.executable(
            "strategy_rsi_momentum_forex", "1d", "EURUSD", venue="oanda_practice"
        )[0]
        # Off-universe / wrong-venue calls stay blocked.
        assert not reg.executable(
            "strategy_rsi_momentum", "1d", "EURUSD", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())
    # Without demo attestation the lane is blocked fail-closed.
    assert not reg.executable(
        "strategy_rsi_momentum", "1d", "BTCUSDT", venue="binance_futures"
    )[0]


# ---------------------------------------------------------------------------
# 3. Venue mapping (forex)
# ---------------------------------------------------------------------------

def test_forex_venue_mapping():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["rsi_momentum_forex"]
    assert entry["forward_venues"] == ["oanda_practice"]
    for sym in entry["lane_assets"]:
        # Plain OANDA pair names (no separator / suffix), all in the
        # verified FOREX28 set recorded in config_strategy.
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
    # The measured maxima themselves, recomputed from the fixtures:
    df = _load("SOLUSDT_1d.csv")
    atr = harness_atr(df, 14)
    for mod_entries, key in (
        (rsi.entries_for_frame(df, WARMUP), "rsi_momentum"),
        (rsi7.entries_for_frame(df, WARMUP), "rsi_momentum_rsi7_60_40"),
    ):
        worst = max(2.0 * float(atr.iloc[i]) / float(df["close"].iloc[i])
                    for i, _ in mod_entries)
        assert worst == pytest.approx(MEASURED_MAX_STOP[key], abs=0.005), key
