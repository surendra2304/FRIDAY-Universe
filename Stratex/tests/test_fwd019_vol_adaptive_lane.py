"""TASK-STR-FWD-019 (Wave-2, crew A) — vol_adaptive_trend lane wiring.

Five RD-002 near-miss cells of the vol_adaptive_trend family join the
FORWARD_TEST lane (near-miss audit ~/workspace/str-nearmiss/REPORT.md
§1.4 rows 2, 4, 45, 52, 54). This file pins:

1. EQUIVALENCE: every wired module reproduces the judged rd2 harness
   (rigorous_backtest/rd2/families2.py sig_vol_trend) entry-for-entry
   on the fwd002 fixture slices at its judged timeframe.
2. REGISTRY/PARTITION: every new key is FORWARD_TEST with the judged
   priors, lane_assets == CRYPTO30_SYMBOLS, the FWD-006 risk fields,
   and none of the new keys is in the VALIDATED partition; the daemon
   maps each module to the FORWARD_TEST lane.
3. STOP-CAP (FWD-012): each entry's max_stop_pct against the measured
   judged-stop distribution on the fixture slices (constants below).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_vol_adaptive_trend as core
import strategy_vol_adaptive_trend_ema12_26_nogate_4h as v_1226_4h
import strategy_vol_adaptive_trend_ema20_50_gate_4h as v_2050g_4h
import strategy_vol_adaptive_trend_ema20_50_nogate as v_2050_1d
import strategy_vol_adaptive_trend_ema20_50_nogate_4h as v_2050_4h
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# key: (module, harness args (fast, slow, gate), timeframe, fixtures,
#       win_rate_prior, expected_net_edge_bps)
CELLS = {
    "vol_adaptive_trend": (core, (12, 26, False), "1d",
                           ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"], 0.4482, 623.3),
    "vol_adaptive_trend_ema20_50_nogate": (v_2050_1d, (20, 50, False), "1d",
                                           ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"], 0.4268, 560.8),
    "vol_adaptive_trend_ema20_50_nogate_4h": (v_2050_4h, (20, 50, False), "4h",
                                              ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"], 0.3709, 59.1),
    "vol_adaptive_trend_ema12_26_nogate_4h": (v_1226_4h, (12, 26, False), "4h",
                                              ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"], 0.3763, 58.8),
    "vol_adaptive_trend_ema20_50_gate_4h": (v_2050g_4h, (20, 50, True), "4h",
                                            ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"], 0.3743, 55.0),
}

# FWD-012 stop-cap measurements (2026-11-18, this crew): distribution of
# the judged stop 2.5 x ATR(14) / close over the fwd002 fixture slices —
# max over ALL post-warmup bars and max at entry bars, per timeframe.
MEASURED_STOP = {  # timeframe: (max_all_bars, max_at_entries)
    "1d": (0.8910, 0.3551),   # SOLUSDT_1d binds both maxima
    "4h": (0.1625, 0.1364),   # SOLUSDT_4h binds both maxima
}
CHOSEN_MAX_STOP = {"1d": 0.90, "4h": 0.25}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(CELLS))
def test_entries_match_judged_harness(key):
    module, (fast, slow, gate), _tf, fixtures, _wr, _edge = CELLS[key]
    total = 0
    for fixture in fixtures:
        df = _load(fixture)
        judged = families2.sig_vol_trend(df, fast, slow, gate, WARMUP)
        production = module.entries_for_frame(df, WARMUP)
        assert production == judged, f"{key} on {fixture}"
        total += len(judged)
    assert total >= 8, f"{key}: fixture entry set too small ({total})"


def test_gate_changes_mask_in_judged_direction():
    # The gate variant's entries are a strict subset of the ungated
    # variant's on the same frame (the gate only removes crosses).
    df = _load("SOLUSDT_4h.csv")
    gated = v_2050g_4h.entries_for_frame(df, WARMUP)
    ungated = v_2050_4h.entries_for_frame(df, WARMUP)
    assert set(gated) <= set(ungated)
    assert len(gated) < len(ungated)


def test_live_signal_reproduces_judged_bracket():
    from rigorous_backtest.rd.common import atr as harness_atr

    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_vol_trend(df, 12, 26, False, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    assert judged, "fixture must contain judged entries"
    for i, side in judged[:5]:
        sig = core.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.5 * atr[i])
        assert sig["tp_dist"] == pytest.approx(5.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.4482)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert core.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_atr_matches_judged_harness():
    import numpy as np

    from rigorous_backtest.rd.common import atr as harness_atr

    for fixture in ("BTCUSDT_1d.csv", "SOLUSDT_4h.csv"):
        df = _load(fixture)
        np.testing.assert_allclose(
            core.atr14(df).to_numpy(), harness_atr(df, 14).to_numpy()
        )


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    for key, (_m, _a, tf, _f, wr, edge) in CELLS.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["timeframe"] == tf, key
        assert entry["execution_model"] == "RULE_BASED", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["lane_assets"] == CRYPTO30_SYMBOLS, key
        assert entry["validated_assets"] == [], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["total_friction_bps"] == 16.0, key
        assert entry["minimum_required_edge"] == 0.0005, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        # Lane-executable entries keep their runtime priors.
        assert entry["runtime_priors_nulled"] is False, key
        assert "TASK-STR-FWD-019" in entry["reason"], key

    validated = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert not (validated & set(CELLS)), "new lane keys must not be VALIDATED"
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
    entries = daemon._forward_protocol_entries()
    for key in CELLS:
        assert f"strategy_{key}" in entries, key
        assert daemon._lane_for_strategy(f"strategy_{key}") == "FORWARD_TEST", key


def test_registry_demo_venue_execution():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    try:
        reg.set_demo_venues({"binance_futures"})
        for key, (_m, _a, tf, _f, _w, _e) in CELLS.items():
            assert reg.executable(
                f"strategy_{key}", tf, "BTCUSDT", venue="binance_futures"
            )[0], key
            assert not reg.executable(
                f"strategy_{key}", tf, "BTCUSDT", venue="oanda"
            )[0], key
    finally:
        reg.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key, (_m, _a, tf, _f, _w, _e) in CELLS.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        max_all, _max_ent = MEASURED_STOP[tf]
        # The measured judged stop exceeds the 0.15 engine-global cap on
        # the fixture tail at both timeframes, so every entry must carry
        # an override above the cap and at/above the measured maximum.
        assert entry["max_stop_pct"] == pytest.approx(CHOSEN_MAX_STOP[tf]), key
        assert entry["max_stop_pct"] > 0.15, key
        assert entry["max_stop_pct"] >= max_all, key
