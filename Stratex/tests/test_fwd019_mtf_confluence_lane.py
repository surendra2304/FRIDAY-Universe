"""TASK-STR-FWD-019 WAVE-2 — mtf_confluence FORWARD_TEST lane entries.

HARNESS FINDING (pinned here): the judged h4_native_ema200
configuration consumes NO higher-timeframe series.
- families2.build_configs registers it as
  ``lambda df, aux, am, w: sig_mtf_native(df, w)`` (tfs ["4h", "1d"])
  — the aux frame is ignored; sig_mtf (the aux-consuming function)
  is used only by the h1_cross variants.
- rd2/grid.py: AUX_TF = {"15m": "1h", "1h": "4h"} and aux is loaded
  only ``if cfg["family"] == "mtf_confluence" and tf in AUX_TF`` —
  never for 4h or 1d cells.
So the 1d cell was judged by sig_mtf_native on 1d bars natively.
Both cells are wired at their judged constructions (4h core module
+ 1d thin variant); nothing was re-judged.

Also pins: equivalence entry-for-entry vs families2.sig_mtf_native
on the fwd002 4h and 1d fixtures; registry/partition shape;
FWD-012 stop-cap consistency — 1d entry-bar maximum 18.66%
(SOLUSDT), 4h entry maximum 8.13% with an all-bar 4h tail of
56.04% (SOLUSDT), so both entries declare max_stop_pct 0.90
(measured 2026-11-18).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_mtf_confluence as mtf
import strategy_mtf_confluence_1d as mtf1d
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
MEASURED_MAX_STOP = {
    "mtf_confluence": 0.0813,     # SOLUSDT 4h entry bars (BTCUSDT 0.0493)
    "mtf_confluence_1d": 0.1866,  # SOLUSDT 1d entry bars (BTCUSDT 0.1289)
}
MEASURED_ALLBAR_MAX_STOP_4H = 0.5604
GLOBAL_CAP = 0.15


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_mtf_4h_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_mtf_native(df, WARMUP)
    production = mtf.entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_mtf_1d_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_mtf_native(df, WARMUP)
    production = mtf1d.entries_for_frame(df, WARMUP)
    assert len(judged) >= 2, "fixture must contain a meaningful entry set"
    assert production == judged


def test_mtf_live_signal_reproduces_judged_bracket():
    df = _load("SOLUSDT_4h.csv")
    judged = families2.sig_mtf_native(df, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    checked = 0
    for i, side in judged:
        if i >= len(df) - 1:
            continue
        sig = mtf.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3807)
        checked += 1
        if checked >= 4:
            break
    assert checked >= 3
    assert mtf.BAR_SECONDS == 4 * 3600
    assert mtf1d.BAR_SECONDS == 24 * 3600


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0
    opens = [now - 12 * 3600, now - 8 * 3600, now - 4 * 3600 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(mtf._closed_frame(df, now_s=now)) == 3
    opens1 = [now - 3 * 86400, now - 2 * 86400, now - 86400 - 1, now - 3600]
    idx1 = pd.to_datetime(opens1, unit="s", utc=True)
    df1 = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx1,
    )
    assert len(mtf1d._closed_frame(df1, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

NEW_KEYS = {
    "mtf_confluence": ("4h", 0.3807, 49.0),
    "mtf_confluence_1d": ("1d", 0.3779, 147.2),
}


def test_registry_lane_entries():
    import config_strategy as cs

    for key, (tf, wr, edge) in NEW_KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["timeframe"] == tf, key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS, key
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
    reg.set_demo_venues({"binance_futures"})
    try:
        assert reg.executable(
            "strategy_mtf_confluence", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
        assert reg.executable(
            "strategy_mtf_confluence_1d", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not reg.executable(
            "strategy_mtf_confluence", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not reg.executable(
            "strategy_mtf_confluence_1d", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())
    assert not reg.executable(
        "strategy_mtf_confluence", "4h", "BTCUSDT", venue="binance_futures"
    )[0]


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    import config_strategy as cs

    for key, measured in MEASURED_MAX_STOP.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["max_stop_pct"] > GLOBAL_CAP, key
        assert entry["max_stop_pct"] >= measured, key
    df = _load("SOLUSDT_1d.csv")
    atr = harness_atr(df, 14)
    entries = mtf1d.entries_for_frame(df, WARMUP)
    worst = max(2.0 * float(atr.iloc[i]) / float(df["close"].iloc[i])
                for i, _ in entries)
    assert worst == pytest.approx(MEASURED_MAX_STOP["mtf_confluence_1d"], abs=0.005)
    df4 = _load("SOLUSDT_4h.csv")
    atr4 = harness_atr(df4, 14)
    assert float((2.0 * atr4 / df4["close"]).max()) == pytest.approx(
        MEASURED_ALLBAR_MAX_STOP_4H, abs=0.01
    )
