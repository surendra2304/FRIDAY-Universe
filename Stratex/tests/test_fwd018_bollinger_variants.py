"""TASK-STR-FWD-018 wave 1 — bollinger_trend parameter variants.

Two RD-002 near-miss cells admitted to the FORWARD_TEST lane under
the owner's second-tier demo-admission bar (2026-11-18: OOS
expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni):

- bollinger_trend_4h:  p50_sd2.0 @ CRYPTO30 4h — 3,211 pooled OOS
  trades, expectancy +0.4650%, PF 1.1371, win rate 0.3759, 4/5 folds.
- bollinger_trend_p20: p20_sd2.0 @ CRYPTO30 1d — 632 pooled OOS
  trades, expectancy +1.2651%, PF 1.1474, win rate 0.3513, 3/5 folds.

(figures: RD-002 grid_rows pooled_oos; near-miss re-audit
2026-11-18). This file pins, in the FWD-003 pattern:

1. EQUIVALENCE: each variant module reproduces the judged rd2
   harness entry-for-entry on the shared fwd002 fixtures, with the
   judged BR24 bracket distances.
2. GOVERNANCE: each entry is FORWARD_TEST (never VALIDATED /
   executable-lane), keeps its judged priors (null-out does not
   apply: forward_protocol on, lane_assets bound), and the registry
   spec binds timeframe + lane universe exactly.
3. STOP CAP (FWD-012 check): the judged stop is 2.0 x ATR(14); the
   cap decision for each variant is pinned against the daemon's
   _max_stop_pct_for_strategy (see the cap-check record in the PR
   body: signal-day stop distribution measured on the full CRYPTO30
   universe).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_bollinger_trend_4h as bol4h
import strategy_bollinger_trend_p20 as bolp20
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

VARIANTS = {
    "bollinger_trend_4h": {
        "module": bol4h, "timeframe": "4h", "sma": 50,
        "win_rate": 0.3759, "edge_bps": 46.5,
    },
    "bollinger_trend_p20": {
        "module": bolp20, "timeframe": "1d", "sma": 20,
        "win_rate": 0.3513, "edge_bps": 126.5,
    },
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_bollinger_4h_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_bollinger_trend(df, 50, WARMUP)
    production = bol4h.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_bollinger_p20_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_bollinger_trend(df, 20, WARMUP)
    production = bolp20.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize(
    "mod,fixture",
    [(bol4h, "BTCUSDT_4h.csv"), (bolp20, "BTCUSDT_1d.csv")],
)
def test_variant_bracket_is_judged_br24(mod, fixture):
    """ATR identical to the harness; bracket multiples are BR24."""
    df = _load(fixture)
    pd.testing.assert_series_equal(
        mod.atr14(df), harness_atr(df), check_names=False
    )
    assert mod.SL_ATR == 2.0 and mod.TP_ATR == 4.0 and mod.RR_RATIO == 2.0


def test_variant_module_bindings():
    assert bol4h.TIMEFRAME == "4h" and bol4h.BAR_SECONDS == 4 * 3600
    assert bol4h.SMA_PERIOD == 50 and bol4h.WIN_RATE_PRIOR == pytest.approx(0.3759)
    assert bolp20.TIMEFRAME == "1d" and bolp20.BAR_SECONDS == 24 * 3600
    assert bolp20.SMA_PERIOD == 20 and bolp20.WIN_RATE_PRIOR == pytest.approx(0.3513)


# ---------------------------------------------------------------------------
# 2. Governance: config registry + partition + registry spec
# ---------------------------------------------------------------------------

def test_config_dicts_carry_judged_figures():
    import config_strategy as cs

    assert cs.BOLLINGER_TREND_4H_STRATEGY["TIMEFRAME"] == "4h"
    assert cs.BOLLINGER_TREND_4H_STRATEGY["SMA_PERIOD"] == 50
    assert cs.BOLLINGER_TREND_4H_STRATEGY["OOS_WIN_RATE"] == 0.3759
    assert cs.BOLLINGER_TREND_4H_STRATEGY["OOS_PROFIT_FACTOR"] == 1.137
    assert cs.BOLLINGER_TREND_P20_STRATEGY["TIMEFRAME"] == "1d"
    assert cs.BOLLINGER_TREND_P20_STRATEGY["SMA_PERIOD"] == 20
    assert cs.BOLLINGER_TREND_P20_STRATEGY["OOS_WIN_RATE"] == 0.3513
    assert cs.BOLLINGER_TREND_P20_STRATEGY["OOS_PROFIT_FACTOR"] == 1.147


@pytest.mark.parametrize("key", list(VARIANTS))
def test_registry_entries_are_forward_test_lane(key):
    import config_strategy as cs

    v = VARIANTS[key]
    entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["timeframe"] == v["timeframe"]
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["oos_win_rate_prior"] == v["win_rate"]
    assert entry["expected_net_edge_bps"] == v["edge_bps"]
    assert entry["runtime_priors_nulled"] is False
    assert entry["risk_per_trade_pct"] == 0.001
    assert entry["max_heat_pct"] == 0.02
    # Lane universe: the judged CRYPTO30 panel, non-empty, crypto only.
    assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS
    assert len(entry["lane_assets"]) == 30
    assert all(s.endswith("USDT") for s in entry["lane_assets"])
    assert entry["validated_assets"] == []


def test_variants_land_in_forward_test_partition_not_executable():
    import config_strategy as cs

    forward_test = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e.get("status") == "FORWARD_TEST" and e.get("forward_protocol") is True
    }
    validated = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e.get("status") == "VALIDATED"
    }
    for key in VARIANTS:
        assert key in forward_test
        assert key not in validated


@pytest.mark.parametrize("key", list(VARIANTS))
def test_registry_spec_binds_lane_universe_and_timeframe(key):
    from strategies.strategy_registry import UnifiedStrategyRegistry

    v = VARIANTS[key]
    reg = UnifiedStrategyRegistry()
    spec = reg.get(f"strategy_{key}")
    assert spec is not None, f"module strategy_{key} not discovered"
    assert spec.status == "FORWARD_TEST"
    assert spec.timeframes == (v["timeframe"],)
    import config_strategy as cs

    assert set(spec.symbols) == set(cs.CRYPTO30_SYMBOLS)
    assert spec.win_rate_prior == v["win_rate"]
    # Evaluable on its judged timeframe/universe; not on others.
    ok, _ = reg.evaluable(f"strategy_{key}", v["timeframe"], "BTCUSDT")
    assert ok
    other_tf = "1d" if v["timeframe"] == "4h" else "4h"
    ok, why = reg.evaluable(f"strategy_{key}", other_tf, "BTCUSDT")
    assert not ok and why == "TIMEFRAME_NOT_VALIDATED"
    ok, why = reg.evaluable(f"strategy_{key}", v["timeframe"], "EURUSD")
    assert not ok and why == "SYMBOL_NOT_VALIDATED"
    # Execution: blocked without an attested demo venue, allowed with one.
    ok, why = reg.executable(f"strategy_{key}", v["timeframe"], "BTCUSDT")
    assert not ok and why == "FORWARD_TEST_REQUIRES_VENUE"
    reg.set_demo_venues({"binance_futures"})
    ok, _ = reg.executable(
        f"strategy_{key}", v["timeframe"], "BTCUSDT", venue="binance_futures"
    )
    assert ok


# ---------------------------------------------------------------------------
# 3. Stop cap (FWD-012 check, measured 2026-11-18)
#
# Judged stop = 2.0 x ATR(14) at the signal bar. Signal bars were
# generated by the RD-002 harness entry functions over current
# Binance klines for all 30 CRYPTO30 symbols (1d x1000, 4h x1500):
#   bollinger_trend_4h  (p50 @ 4h): 1,470 signals — median stop
#       4.33%, p99 9.88%, max 17.82%, 0.07% of signals above the
#       0.15 global cap -> NO override; the global cap binds as the
#       sanity bound (as for the VALIDATED ichimoku_trend).
#   bollinger_trend_p20 (p20 @ 1d): 1,249 signals — median 13.22%,
#       p99 31.37%, max 36.24%, 37.8% of signals above the cap ->
#       override max_stop_pct=0.50, a sanity bound above the whole
#       measured distribution. Without it the lane would repeat the
#       sleeve_shock failure mode (cap silently rejecting a third
#       of the judged signals). Under FWD-006 the wider stop
#       shrinks position size; it does not add risk.
# ---------------------------------------------------------------------------

def test_stop_cap_decisions():
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    assert d._max_stop_pct_for_strategy("strategy_bollinger_trend_p20") == 0.50
    assert d._max_stop_pct_for_strategy("bollinger_trend_p20") == 0.50
    assert d._max_stop_pct_for_strategy("strategy_bollinger_trend_4h") is None
    import config_strategy as cs

    assert cs.PRODUCTION_STRATEGY_REGISTRY["bollinger_trend_p20"]["max_stop_pct"] == 0.50
    assert "max_stop_pct" not in cs.PRODUCTION_STRATEGY_REGISTRY["bollinger_trend_4h"]
