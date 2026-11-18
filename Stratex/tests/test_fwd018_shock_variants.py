"""TASK-STR-FWD-018 wave 1 — shock_breakout parameter variant.

One RD-002 near-miss cell admitted to the FORWARD_TEST lane under
the owner's second-tier demo-admission bar (2026-11-18: OOS
expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni):

- shock_breakout_k15: k1.5 @ CRYPTO30 1d — 486 pooled OOS trades,
  expectancy +2.8113%, PF 1.3325, win rate 0.4033, 3/5 folds.

(figures: RD-002 grid_rows pooled_oos; near-miss re-audit
2026-11-18.) The family's 4h cells are NOT admitted — k1.0@4h
(expectancy -0.0315%, PF 0.9918) and k1.5@4h (expectancy -0.0820%,
PF 0.9786) are below the tier on their own records; a pin below
keeps them out.

Pins, in the FWD-003 pattern: (1) equivalence vs the judged rd2
harness on the shared fwd002 fixtures with the judged BR24
bracket; (2) governance — FORWARD_TEST partition, judged priors
kept, lane universe bound; (3) the FWD-012 stop-cap decision for
this config (see PR body for the measured signal-day stop
distribution).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_shock_breakout_k15 as shk15
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_shock_k15_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_shock(df, 1.5, WARMUP)
    production = shk15.entries_for_frame(df, WARMUP)
    assert len(judged) >= 3, "fixture must contain a meaningful entry set"
    assert production == judged


def test_shock_k15_bracket_is_judged_br24():
    df = _load("BTCUSDT_1d.csv")
    pd.testing.assert_series_equal(
        shk15.atr14(df), harness_atr(df), check_names=False
    )
    assert shk15.SL_ATR == 2.0 and shk15.TP_ATR == 4.0 and shk15.RR_RATIO == 2.0


def test_shock_k15_module_bindings():
    assert shk15.TIMEFRAME == "1d" and shk15.BAR_SECONDS == 24 * 3600
    assert shk15.SHOCK_K == 1.5
    assert shk15.WIN_RATE_PRIOR == pytest.approx(0.4033)


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------

def test_config_dict_carries_judged_figures():
    import config_strategy as cs

    d = cs.SHOCK_BREAKOUT_K15_STRATEGY
    assert d["TIMEFRAME"] == "1d" and d["SHOCK_K"] == 1.5
    assert d["OOS_WIN_RATE"] == 0.4033
    assert d["OOS_PROFIT_FACTOR"] == 1.333
    assert d["OOS_EXPECTANCY_PCT"] == 2.811


def test_registry_entry_is_forward_test_lane():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["shock_breakout_k15"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["timeframe"] == "1d"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["oos_win_rate_prior"] == 0.4033
    assert entry["expected_net_edge_bps"] == 281.1
    assert entry["runtime_priors_nulled"] is False
    assert entry["risk_per_trade_pct"] == 0.001
    assert entry["max_heat_pct"] == 0.02
    assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS
    assert len(entry["lane_assets"]) == 30
    assert entry["validated_assets"] == []


def test_shock_k15_lands_in_forward_test_partition_not_executable():
    import config_strategy as cs

    forward_test = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e.get("status") == "FORWARD_TEST" and e.get("forward_protocol") is True
    }
    validated = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e.get("status") == "VALIDATED"
    }
    assert "shock_breakout_k15" in forward_test
    assert "shock_breakout_k15" not in validated


def test_no_shock_4h_variant_is_registered():
    """The k1.0/k1.5 @ 4h cells are below the admission tier on
    their own RD-002 records (negative expectancy) — no registry
    entry and no module may exist for them."""
    import config_strategy as cs

    for key in cs.PRODUCTION_STRATEGY_REGISTRY:
        assert not key.startswith("shock_breakout_4h"), key
        assert not key.startswith("shock_breakout_k15_4h"), key
    assert not os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "strategy_shock_breakout_k15_4h.py")
    )


def test_registry_spec_binds_lane_universe_and_timeframe():
    import config_strategy as cs
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    spec = reg.get("strategy_shock_breakout_k15")
    assert spec is not None
    assert spec.status == "FORWARD_TEST"
    assert spec.timeframes == ("1d",)
    assert set(spec.symbols) == set(cs.CRYPTO30_SYMBOLS)
    assert spec.win_rate_prior == 0.4033
    ok, _ = reg.evaluable("strategy_shock_breakout_k15", "1d", "BTCUSDT")
    assert ok
    ok, why = reg.evaluable("strategy_shock_breakout_k15", "4h", "BTCUSDT")
    assert not ok and why == "TIMEFRAME_NOT_VALIDATED"
    ok, why = reg.executable("strategy_shock_breakout_k15", "1d", "BTCUSDT")
    assert not ok and why == "FORWARD_TEST_REQUIRES_VENUE"
    reg.set_demo_venues({"binance_futures"})
    ok, _ = reg.executable(
        "strategy_shock_breakout_k15", "1d", "BTCUSDT", venue="binance_futures"
    )
    assert ok


# ---------------------------------------------------------------------------
# 3. Stop cap (FWD-012 check, measured 2026-11-18)
#
# Judged stop = 2.0 x ATR(14) at the signal bar; signal bars from
# the RD-002 harness over current Binance klines for all 30
# CRYPTO30 symbols (1d x1000): 676 signals — median stop 12.81%,
# p99 32.46%, max 36.24%, 33.7% of judged signals above the 0.15
# global cap. Override max_stop_pct=0.50 (sanity bound above the
# measured distribution) so the judged bracket is not silently
# clipped — the sleeve_shock failure mode. Under FWD-006 the
# wider stop shrinks position size; it does not add risk.
# ---------------------------------------------------------------------------

def test_stop_cap_decision():
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    assert d._max_stop_pct_for_strategy("strategy_shock_breakout_k15") == 0.50
    assert d._max_stop_pct_for_strategy("shock_breakout_k15") == 0.50
    import config_strategy as cs

    assert cs.PRODUCTION_STRATEGY_REGISTRY["shock_breakout_k15"]["max_stop_pct"] == 0.50
