"""TASK-STR-FWD-018 wave 1 — ichimoku_trend variants.

Two RD-002 near-miss cells admitted to the FORWARD_TEST lane under
the owner's second-tier demo-admission bar (2026-11-18: OOS
expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni):

- ichimoku_trend_1d:  tk_cloud @ CRYPTO30 1d — 398 pooled OOS
  trades, expectancy +3.0131%, PF 1.3674, win rate 0.3970, 4/5 folds.
- ichimoku_trend_raw: tk_raw @ CRYPTO30 4h — 3,630 pooled OOS
  trades, expectancy +0.4106%, PF 1.1144, win rate 0.3741, 3/5 folds.

(figures: RD-002 grid_rows pooled_oos; near-miss re-audit
2026-11-18.) The VALIDATED ichimoku_trend entrant (tk_cloud @ 4h)
is a different judged object and is untouched by this wiring; its
registry entry and module are pinned unchanged below.

Pins, in the FWD-003 pattern: (1) equivalence vs the judged rd2
harness (sig_ichimoku cloud=True / cloud=False) on the shared
fwd002 fixtures with the judged BR24 bracket; (2) governance —
FORWARD_TEST partition, judged priors kept, lane universe bound;
(3) the FWD-012 stop-cap decision per config (see PR body for the
measured signal-day stop distributions).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_ichimoku_trend_1d as ichi1d
import strategy_ichimoku_trend_raw as ichiraw
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

VARIANTS = {
    "ichimoku_trend_1d": {
        "module": ichi1d, "timeframe": "1d", "win_rate": 0.3970, "edge_bps": 301.3,
    },
    "ichimoku_trend_raw": {
        "module": ichiraw, "timeframe": "4h", "win_rate": 0.3741, "edge_bps": 41.1,
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

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_ichimoku_1d_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_ichimoku(df, True, WARMUP)
    production = ichi1d.entries_for_frame(df, WARMUP)
    assert len(judged) >= 3, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_ichimoku_raw_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_ichimoku(df, False, WARMUP)
    production = ichiraw.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize(
    "mod,fixture", [(ichi1d, "BTCUSDT_1d.csv"), (ichiraw, "BTCUSDT_4h.csv")]
)
def test_variant_bracket_is_judged_br24(mod, fixture):
    df = _load(fixture)
    pd.testing.assert_series_equal(
        mod.atr14(df), harness_atr(df), check_names=False
    )
    assert mod.SL_ATR == 2.0 and mod.TP_ATR == 4.0 and mod.RR_RATIO == 2.0


def test_variant_module_bindings():
    assert ichi1d.TIMEFRAME == "1d" and ichi1d.BAR_SECONDS == 24 * 3600
    assert ichi1d.WIN_RATE_PRIOR == pytest.approx(0.3970)
    assert ichiraw.TIMEFRAME == "4h" and ichiraw.BAR_SECONDS == 4 * 3600
    assert ichiraw.WIN_RATE_PRIOR == pytest.approx(0.3741)


def test_raw_variant_has_no_cloud_gate():
    """tk_raw must produce a superset of the cloud variant's entries
    on the same frame (the gate only removes crosses)."""
    df = _load("BTCUSDT_4h.csv")
    import strategy_ichimoku_trend as ichi_cloud

    raw = set(ichiraw.entries_for_frame(df, WARMUP))
    cloud = set(ichi_cloud.entries_for_frame(df, WARMUP))
    assert cloud <= raw
    assert len(raw) > len(cloud)


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------

def test_config_dicts_carry_judged_figures():
    import config_strategy as cs

    assert cs.ICHIMOKU_TREND_1D_STRATEGY["TIMEFRAME"] == "1d"
    assert cs.ICHIMOKU_TREND_1D_STRATEGY["OOS_WIN_RATE"] == 0.3970
    assert cs.ICHIMOKU_TREND_1D_STRATEGY["OOS_PROFIT_FACTOR"] == 1.367
    assert cs.ICHIMOKU_TREND_RAW_STRATEGY["TIMEFRAME"] == "4h"
    assert cs.ICHIMOKU_TREND_RAW_STRATEGY["OOS_WIN_RATE"] == 0.3741
    assert cs.ICHIMOKU_TREND_RAW_STRATEGY["OOS_PROFIT_FACTOR"] == 1.114


def test_validated_ichimoku_entry_untouched():
    """The VALIDATED entrant's record must not move under this wiring."""
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["ichimoku_trend"]
    assert entry["status"] == "VALIDATED"
    assert entry["timeframe"] == "4h"
    assert entry["oos_win_rate_prior"] == 0.4010


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
    assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS
    assert len(entry["lane_assets"]) == 30
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
    import config_strategy as cs
    from strategies.strategy_registry import UnifiedStrategyRegistry

    v = VARIANTS[key]
    reg = UnifiedStrategyRegistry()
    spec = reg.get(f"strategy_{key}")
    assert spec is not None, f"module strategy_{key} not discovered"
    assert spec.status == "FORWARD_TEST"
    assert spec.timeframes == (v["timeframe"],)
    assert set(spec.symbols) == set(cs.CRYPTO30_SYMBOLS)
    assert spec.win_rate_prior == v["win_rate"]
    ok, _ = reg.evaluable(f"strategy_{key}", v["timeframe"], "BTCUSDT")
    assert ok
    other_tf = "1d" if v["timeframe"] == "4h" else "4h"
    ok, why = reg.evaluable(f"strategy_{key}", other_tf, "BTCUSDT")
    assert not ok and why == "TIMEFRAME_NOT_VALIDATED"
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
# Judged stop = 2.0 x ATR(14) at the signal bar; signal bars from
# the RD-002 harness over current Binance klines for all 30
# CRYPTO30 symbols:
#   ichimoku_trend_1d  (tk_cloud @ 1d): 462 signals — median stop
#       13.41%, p99 27.46%, max 36.92%, 36.2% of signals above the
#       0.15 global cap -> override max_stop_pct=0.50.
#   ichimoku_trend_raw (tk_raw @ 4h): 1,818 signals — median
#       4.06%, p99 10.41%, max 16.85%, 0.11% above the cap ->
#       NO override; the global cap binds as the sanity bound
#       (as for the VALIDATED ichimoku_trend).
# ---------------------------------------------------------------------------

def test_stop_cap_decisions():
    from autonomy.run_daemon import StratexTradingEngine

    d = StratexTradingEngine.__new__(StratexTradingEngine)
    assert d._max_stop_pct_for_strategy("strategy_ichimoku_trend_1d") == 0.50
    assert d._max_stop_pct_for_strategy("strategy_ichimoku_trend_raw") is None
    import config_strategy as cs

    assert cs.PRODUCTION_STRATEGY_REGISTRY["ichimoku_trend_1d"]["max_stop_pct"] == 0.50
    assert "max_stop_pct" not in cs.PRODUCTION_STRATEGY_REGISTRY["ichimoku_trend_raw"]
