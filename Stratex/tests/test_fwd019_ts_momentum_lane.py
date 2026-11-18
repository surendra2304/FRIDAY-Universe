"""TASK-STR-FWD-019 (Wave-2, crew A) — ts_momentum + tsmom2_dual lane.

Six cells join the FORWARD_TEST lane: ts_momentum roc72/roc42/roc168 @
crypto30 1d and roc42 @ crypto30 4h (RD-002, audit §1.4 rows 5, 7, 28,
69), ts_momentum roc168_1h (RD-001, audit §1.1) and tsmom2_dual
roc90_ema200 @ crypto30 4h (RD-002, §1.4 row 70, key tsmom2_dual_crypto
— the plain key is taken by the excluded comm7 documentary entry).

RD-001 ALIAS DECISION (pinned here): RD-001's roc42_4h row is NOT
wired separately. Its judged signal (rd/stage3.py fam_ts_momentum),
bracket (2.0/4.0) and warmup (260) are identical to RD-002's roc42 4h
cell — RD-002's harness reproduced RD-001's published row
BIT-IDENTICALLY (results_rd2/sanity_checks.json) and this suite
re-verifies stage3 == families2 entry-for-entry on the fixtures. The
alias is recorded in the ts_momentum_roc42_4h registry reason.

This file pins: (1) equivalence vs the judged harnesses (families2 for
the RD-002 cells AND the tsmom2 cell; rd/stage3 for the RD-001 cell),
(2) registry/partition shape, (3) FWD-012 stop-cap consistency.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_ts_momentum as core
import strategy_ts_momentum_roc168 as v_roc168
import strategy_ts_momentum_roc168_rd001 as v_roc168_rd001
import strategy_ts_momentum_roc42 as v_roc42
import strategy_ts_momentum_roc42_4h as v_roc42_4h
import strategy_tsmom2_dual_crypto as dual
from rigorous_backtest.rd import stage3
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# ts_momentum cells: key -> (module, lookback, timeframe, fixtures, wr, edge)
TS_CELLS = {
    "ts_momentum": (core, 72, "1d", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"], 0.4251, 437.6),
    "ts_momentum_roc42": (v_roc42, 42, "1d", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"], 0.4283, 321.3),
    "ts_momentum_roc168": (v_roc168, 168, "1d", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"], 0.3925, 157.9),
    "ts_momentum_roc42_4h": (v_roc42_4h, 42, "4h", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"], 0.3672, 33.8),
    # RD-001 1h cell: equivalence is run on the 4h fixtures because the
    # signal function is timeframe-agnostic and no 1h fixture exists;
    # its judged harness is rd/stage3 (see the dedicated test below).
    "ts_momentum_roc168_rd001": (v_roc168_rd001, 168, "1h", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"], 0.3805, 8.2),
}

# FWD-012 stop-cap measurements (2026-11-18, this crew): judged stop /
# close over the fwd002 fixture slices — max over ALL post-warmup bars
# and max at entry bars. Bracket differs per family: ts_momentum 2.0x,
# tsmom2_dual 2.5x.
MEASURED_STOP = {  # (family, timeframe): (max_all_bars, max_at_entries, chosen)
    ("ts", "1d"): (0.7128, 0.1840, 0.90),
    ("ts", "4h"): (0.1300, 0.0852, 0.25),
    ("ts", "1h"): (0.1300, 0.0911, 0.25),   # measured on 4h fixtures (upper bound)
    ("dual", "4h"): (0.1625, 0.1044, 0.25),
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harnesses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(TS_CELLS))
def test_ts_entries_match_judged_harness(key):
    module, lookback, _tf, fixtures, _wr, _edge = TS_CELLS[key]
    total = 0
    for fixture in fixtures:
        df = _load(fixture)
        judged = families2.sig_ts_momentum(df, lookback, WARMUP)
        assert module.entries_for_frame(df, WARMUP) == judged, f"{key} on {fixture}"
        total += len(judged)
    # roc168 @ 1d is sparse on BTC (1 entry) — the pair total is the
    # meaningful floor.
    assert total >= 10, f"{key}: fixture entry set too small ({total})"


def test_rd001_stage3_signal_is_identical_to_rd002():
    """The alias decision's evidence, re-verified: RD-001's judged
    fam_ts_momentum and RD-002's sig_ts_momentum produce identical
    entry lists — so RD-001's roc42_4h row is the same stream as the
    wired ts_momentum_roc42_4h config and must not be admitted twice."""
    for fixture, lookback in (("BTCUSDT_4h.csv", 42), ("SOLUSDT_4h.csv", 42),
                              ("BTCUSDT_4h.csv", 168), ("SOLUSDT_1d.csv", 168)):
        df = _load(fixture)
        assert stage3.fam_ts_momentum(df, lookback) == \
            families2.sig_ts_momentum(df, lookback, WARMUP), fixture


def test_rd001_cell_matches_its_own_judged_harness():
    for fixture in ("BTCUSDT_4h.csv", "SOLUSDT_4h.csv"):
        df = _load(fixture)
        assert v_roc168_rd001.entries_for_frame(df, WARMUP) == \
            stage3.fam_ts_momentum(df, 168), fixture


def test_dual_entries_match_judged_harness():
    total = 0
    for fixture in ("BTCUSDT_4h.csv", "SOLUSDT_4h.csv"):
        df = _load(fixture)
        judged = families2.sig_dual_momentum(df, 90, WARMUP)
        assert dual.entries_for_frame(df, WARMUP) == judged, fixture
        total += len(judged)
    assert total >= 10, f"tsmom2 fixture entry set too small ({total})"


def test_lookback_changes_mask_in_judged_direction():
    # Parameterisation: a longer lookback cannot produce MORE crosses
    # than a shorter one on the same frame in general — the pinned
    # property is that the masks genuinely differ (roc42 != roc168).
    df = _load("SOLUSDT_1d.csv")
    assert v_roc42.entries_for_frame(df, WARMUP) != \
        v_roc168.entries_for_frame(df, WARMUP)


def test_live_signals_reproduce_judged_brackets():
    from rigorous_backtest.rd.common import atr as harness_atr

    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_ts_momentum(df, 72, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    assert judged
    for i, side in judged[:5]:
        sig = core.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.4251)
        assert sig["rr_ratio"] == pytest.approx(2.0)

    df4 = _load("SOLUSDT_4h.csv")
    judged4 = families2.sig_dual_momentum(df4, 90, WARMUP)
    atr4 = harness_atr(df4, 14).to_numpy()
    assert judged4
    for i, side in judged4[:5]:
        sig = dual.get_signal(df4.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.5 * atr4[i])
        assert sig["tp_dist"] == pytest.approx(5.0 * atr4[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3627)


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

ALL_KEYS = set(TS_CELLS) | {"tsmom2_dual_crypto"}


def test_registry_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    for key, (_m, _lb, tf, _f, wr, edge) in TS_CELLS.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["timeframe"] == tf, key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["lane_assets"] == CRYPTO30_SYMBOLS, key
        assert entry["validated_assets"] == [], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["total_friction_bps"] == 16.0, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert entry["runtime_priors_nulled"] is False, key

    dual_entry = PRODUCTION_STRATEGY_REGISTRY["tsmom2_dual_crypto"]
    assert dual_entry["status"] == "FORWARD_TEST"
    assert dual_entry["timeframe"] == "4h"
    assert dual_entry["forward_protocol"] is True
    assert dual_entry["oos_win_rate_prior"] == pytest.approx(0.3627)
    assert dual_entry["expected_net_edge_bps"] == pytest.approx(40.2)
    # The plain key remains the excluded documentary registration.
    plain = PRODUCTION_STRATEGY_REGISTRY["tsmom2_dual"]
    assert plain["forward_protocol"] is False
    assert plain["lane_assets"] == []

    # RD-001 flags and the alias are carried in the reasons.
    assert "SOL = 84%" in PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc168_rd001"]["reason"]
    assert "holdout FAIL" in PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc168_rd001"]["reason"]
    assert "BIT-IDENTICALLY" in PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc42_4h"]["reason"]
    assert "NOT separately wired" in PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc42_4h"]["reason"]

    validated = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert not (validated & ALL_KEYS)
    assert validated == {
        "ichimoku_trend", "dow_effect", "fx_mr_v4",
        "sleeve_shock_breakout", "sleeve_tsmom2_dual",
    }


def test_daemon_lane_partition():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    for key in ALL_KEYS:
        assert f"strategy_{key}" in entries, key
        assert daemon._lane_for_strategy(f"strategy_{key}") == "FORWARD_TEST", key
    # The excluded documentary entry stays out of the protocol.
    assert "strategy_tsmom2_dual" not in entries


def test_registry_demo_venue_execution():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    try:
        reg.set_demo_venues({"binance_futures"})
        for key, (_m, _lb, tf, _f, _w, _e) in TS_CELLS.items():
            assert reg.executable(
                f"strategy_{key}", tf, "BTCUSDT", venue="binance_futures"
            )[0], key
        assert reg.executable(
            "strategy_tsmom2_dual_crypto", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not reg.executable(
            "strategy_tsmom2_dual_crypto", "4h", "BTCUSDT", venue="oanda"
        )[0]
    finally:
        reg.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key, (_m, _lb, tf, _f, _w, _e) in TS_CELLS.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        max_all, _max_ent, chosen = MEASURED_STOP[("ts", tf)]
        assert entry["max_stop_pct"] == pytest.approx(chosen), key
        assert entry["max_stop_pct"] > 0.15, key
        assert entry["max_stop_pct"] >= max_all, key
    dual_entry = PRODUCTION_STRATEGY_REGISTRY["tsmom2_dual_crypto"]
    max_all, _max_ent, chosen = MEASURED_STOP[("dual", "4h")]
    assert dual_entry["max_stop_pct"] == pytest.approx(chosen)
    assert dual_entry["max_stop_pct"] >= max_all
