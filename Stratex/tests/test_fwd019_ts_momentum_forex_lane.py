"""TASK-STR-FWD-019 (Wave-2 gap-fill, crew G) — ts_momentum FOREX lane.

The two ts_momentum FOREX cells missed by the original slice plan
join the FORWARD_TEST lane: ts_momentum/roc72 @ forex28 1d (audit
§1.4 row 30: 226 OOS trades, +0.185%/trade, PF 1.1735, 3/5 folds,
PF @2x costs 1.0944) and ts_momentum/roc24 @ forex12 4h (row 68:
715 OOS trades, +0.039%/trade, PF 1.1001, 2/5 folds). Both were
judged by RD-002's rigorous_backtest/rd2/families2.py
``sig_ts_momentum`` under the BR24 bracket recorded in each cell's
own grid row (spec sl_atr 2.0 / tp_atr 4.0), warmup 260 bars.

The lane modules are SELF-CONTAINED ports of the harness function —
crew A's crypto30 ts_momentum modules (PR #991) are not merged at
this base and are not imported.

This file pins: (1) equivalence vs the judged harness on the fwd002
FX fixture slices (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d — the signal
logic is series-only, so the 1d FX slices judge both cells; the
roc24 cell is additionally cross-checked on the 4h crypto slices),
(2) registry/partition shape, (3) the OANDA runner admission
predicate + venue mapping, (4) FWD-012 stop-cap consistency.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_ts_momentum_roc24_fx12 as roc24_fx
import strategy_ts_momentum_roc72_fx28 as roc72_fx
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
FX_FIXTURES = ["FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"]

# key -> (module, lookback, timeframe, win-rate prior, edge bps)
CELLS = {
    "ts_momentum_roc72_fx28": (roc72_fx, 72, "1d", 0.3673, 18.5),
    "ts_momentum_roc24_fx12": (roc24_fx, 24, "4h", 0.3790, 3.9),
}
NEW_KEYS = tuple(CELLS)

# FWD-012 stop-cap measurements (2026-11-18, this crew): judged stop
# 2.0 x ATR(14)/close on the fwd002 FX fixtures — max ATR(14)/close
# over all bars is 0.014689 (FX_GBPJPY 1d), so the all-bars max stop
# is 0.029379; max at each config's own entry bars on the FX slices:
MEASURED_MAX_STOP_ALL_BARS = 0.0294
MEASURED_MAX_STOP_AT_ENTRIES = {
    "ts_momentum_roc72_fx28": 0.0271,
    "ts_momentum_roc24_fx12": 0.0264,  # on 1d slices — upper bound for 4h
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(CELLS))
def test_entries_match_judged_harness_on_fx_fixtures(key):
    module, lookback, _tf, _wr, _edge = CELLS[key]
    total = 0
    for fixture in FX_FIXTURES:
        df = _load(fixture)
        judged = families2.sig_ts_momentum(df, lookback, WARMUP)
        assert module.entries_for_frame(df, WARMUP) == judged, f"{key} on {fixture}"
        total += len(judged)
    assert total >= 30, f"{key}: fixture entry set too small ({total})"


def test_roc24_entries_match_harness_on_4h_slices():
    # The roc24 cell's judged timeframe is 4h; the signal function is
    # timeframe-agnostic, so the 4h fixture slices are an additional
    # equivalence surface at the judged timeframe.
    total = 0
    for fixture in ("BTCUSDT_4h.csv", "SOLUSDT_4h.csv"):
        df = _load(fixture)
        judged = families2.sig_ts_momentum(df, 24, WARMUP)
        assert roc24_fx.entries_for_frame(df, WARMUP) == judged, fixture
        total += len(judged)
    assert total >= 50, f"roc24 4h entry set too small ({total})"


def test_lookback_changes_entries_in_judged_direction():
    # Parameterisation sanity: the two judged lookbacks produce
    # genuinely different entry streams on the same frame.
    df = _load("FX_EURUSD_1d.csv")
    assert roc72_fx.entries_for_frame(df, WARMUP) != \
        roc24_fx.entries_for_frame(df, WARMUP)


def test_live_signals_reproduce_judged_brackets():
    from rigorous_backtest.rd.common import atr as harness_atr

    for key, fixture in (("ts_momentum_roc72_fx28", "FX_EURUSD_1d.csv"),
                         ("ts_momentum_roc24_fx12", "FX_EURUSD_1d.csv")):
        module, lookback, _tf, wr, _edge = CELLS[key]
        df = _load(fixture)
        judged = families2.sig_ts_momentum(df, lookback, WARMUP)
        atr = harness_atr(df, 14).to_numpy()
        assert judged
        for i, side in judged[:5]:
            sig = module.get_signal(df.iloc[: i + 1])
            assert sig["side"] == ("BUY" if side == "LONG" else "SELL"), key
            assert sig["sl_dist"] == pytest.approx(2.0 * atr[i]), key
            assert sig["tp_dist"] == pytest.approx(4.0 * atr[i]), key
            assert sig["win_rate_prior"] == pytest.approx(wr), key
            assert sig["rr_ratio"] == pytest.approx(2.0), key


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_entries_shape():
    import config_strategy as cs

    for key, (_m, _lb, tf, wr, edge) in CELLS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["timeframe"] == tf, key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["forward_venues"] == ["oanda_practice"], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["total_friction_bps"] == 6.0, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert not entry.get("validated_assets"), key
        # Lane-executable entries keep their judged priors (the
        # null-out stamp says so).
        assert entry["runtime_priors_nulled"] is False, key
        assert "TASK-STR-FWD-019 WAVE-2 near-miss admission" in entry["reason"], key
    assert cs.PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc72_fx28"]["lane_assets"] \
        == cs.FOREX28_SYMBOLS
    assert cs.PRODUCTION_STRATEGY_REGISTRY["ts_momentum_roc24_fx12"]["lane_assets"] \
        == cs.FOREX12_SYMBOLS


def test_new_keys_not_in_validated_partition():
    import config_strategy as cs

    validated = {k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
                 if e["status"] == "VALIDATED"}
    assert not (set(NEW_KEYS) & validated)
    assert validated == {
        "ichimoku_trend", "dow_effect", "fx_mr_v4",
        "sleeve_shock_breakout", "sleeve_tsmom2_dual",
    }


def test_entries_satisfy_the_oanda_runner_admission_predicate():
    # The PR-#980 runner (oanda_demo/forward_test_runner.py, separate
    # branch) admits an entry iff status == FORWARD_TEST AND
    # forward_protocol is True AND "oanda_practice" in forward_venues
    # AND lane_assets non-empty. This PR's entries must satisfy that
    # predicate exactly, and the pre-existing entries must not.
    import config_strategy as cs

    def admitted(key):
        e = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        return (
            e.get("status") == "FORWARD_TEST"
            and e.get("forward_protocol") is True
            and "oanda_practice" in (e.get("forward_venues") or [])
            and bool(e.get("lane_assets"))
        )

    for key in NEW_KEYS:
        assert admitted(key), key
    assert not admitted("fx_mr_v4")
    assert not admitted("bollinger_trend")
    assert not admitted("sleeve_tsmom2_dual")


# ---------------------------------------------------------------------------
# 3. Venue mapping
# ---------------------------------------------------------------------------

def test_forex12_mapping_is_faithful():
    import config_strategy as cs
    from rigorous_backtest.rd2.panels import FOREX12 as PANEL_FOREX12

    # The config constant is exactly the judged panel set (panels.py).
    assert set(cs.FOREX12_SYMBOLS) == set(PANEL_FOREX12)
    assert len(cs.FOREX12_SYMBOLS) == 12
    # Every forex12 symbol is one of the 28 verified OANDA pairs.
    for sym in cs.FOREX12_SYMBOLS:
        assert sym in cs.FOREX28_SYMBOLS


def test_lane_assets_are_plain_oanda_pair_names():
    import config_strategy as cs

    for key in NEW_KEYS:
        for sym in cs.PRODUCTION_STRATEGY_REGISTRY[key]["lane_assets"]:
            assert len(sym) == 6 and sym.isalpha(), (key, sym)
            # Every lane asset of either cell is in the verified 28.
            assert sym in cs.FOREX28_SYMBOLS, (key, sym)


# ---------------------------------------------------------------------------
# 4. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_measurement_on_fx_fixtures():
    # Recompute the measurement the constants above record: max
    # ATR(14)/close over the FX fixtures, times the judged SL_ATR 2.0.
    from rigorous_backtest.rd.common import atr as harness_atr

    worst = 0.0
    for fixture in FX_FIXTURES:
        df = _load(fixture)
        pct = (harness_atr(df, 14) / df["close"]).dropna()
        worst = max(worst, float(pct.max()))
    assert worst == pytest.approx(0.0147, abs=0.001)
    assert 2.0 * worst == pytest.approx(MEASURED_MAX_STOP_ALL_BARS, abs=0.002)
    assert MEASURED_MAX_STOP_ALL_BARS <= 0.15
    for key, measured in MEASURED_MAX_STOP_AT_ENTRIES.items():
        assert measured <= MEASURED_MAX_STOP_ALL_BARS, key
        assert measured <= 0.15, key


def test_stop_cap_registry_consistency():
    import config_strategy as cs

    for key in NEW_KEYS:
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        # No override is set, and the measured max stop is under the
        # 0.15 global cap — the (absent override, measured <= cap)
        # branch of the brief's consistency rule.
        assert "max_stop_pct" not in entry, key
        assert MEASURED_MAX_STOP_AT_ENTRIES[key] <= 0.15, key
