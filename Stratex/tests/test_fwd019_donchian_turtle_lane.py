"""TASK-STR-FWD-019 WAVE-2 — donchian_turtle / turtle2 FORWARD-TEST lane.

13 distinct near-miss streams from the 2026-11-18 audit
(~/workspace/str-nearmiss/REPORT.md S1.4 rows 3, 18, 20, 34, 35, 36,
41, 47, 49, 63, 65, 87, 89), wired once each under their canonical
names. Duplicate streams are NOT separately wired: turtle2's
unfiltered trail rows (21/42/50/64) are the identical streams to the
donchian_turtle trail keys, and volume_breakout/donch20_novol
(row 66) is the identical stream to donchian_turtle_n20_b24.

Pins:
1. EQUIVALENCE: every new module's entries_for_frame reproduces the
   judged rd2 harness (families2.sig_donchian / sig_turtle2) entry
   for entry on the fwd002 fixture slices at its judged timeframe.
2. REGISTRY/PARTITION: every new key is FORWARD_TEST with the lane
   terms, none is in the VALIDATED partition.
3. STOP-CAP (FWD-012): measured max judged stop on the fixture
   slices (2.0 x ATR(14) / close at entry bars) is 71.28% at 1d
   (SOLUSDT slice — an extreme early-history bar; BTCUSDT 12.89%)
   and 11.12% at 4h (SOLUSDT; BTCUSDT 9.07%). 1d entries therefore
   carry max_stop_pct 0.90 (sleeve precedent) and 4h entries 0.20 —
   both above the 0.15 engine-global cap and above the measured max.
"""

from __future__ import annotations

import importlib
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

# key: (variant n, harness kind, timeframe, oos win rate, rr or None,
#       max_stop_pct)
STREAMS = {
    "donchian_turtle": (55, "donchian", "1d", 0.3523, 3.0, 0.90),
    "donchian_turtle_n20_trail": (20, "donchian", "1d", 0.3885, None, 0.90),
    "donchian_turtle_n20_b26": (20, "donchian", "1d", 0.2750, 3.0, 0.90),
    "donchian_turtle_n55_trail": (55, "donchian", "1d", 0.3632, None, 0.90),
    "donchian_turtle_n55_trail_4h": (55, "donchian", "4h", 0.3920, None, 0.20),
    "donchian_turtle_n20_trail_4h": (20, "donchian", "4h", 0.3747, None, 0.20),
    "donchian_turtle_n20_b24": (20, "donchian", "1d", 0.3466, 2.0, 0.90),
    "donchian_turtle_n20_b26_4h": (20, "donchian", "4h", 0.2760, 3.0, 0.20),
    "donchian_turtle_n55_b24": (55, "donchian", "1d", 0.3468, 2.0, 0.90),
    "turtle2": (55, "turtle_filt", "1d", 0.3725, None, 0.90),
    "turtle2_n20_trail_filt": (20, "turtle_filt", "1d", 0.3710, None, 0.90),
    "turtle2_n55_trail_filt_4h": (55, "turtle_filt", "4h", 0.3911, None, 0.20),
    "turtle2_n20_trail_filt_4h": (20, "turtle_filt", "4h", 0.3809, None, 0.20),
}

MEASURED_MAX_STOP = {"1d": 0.7128, "4h": 0.1112}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _module(key: str):
    return importlib.import_module(f"strategy_{key}")


def _judged(df, kind, n):
    if kind == "donchian":
        return families2.sig_donchian(df, n, WARMUP)
    return families2.sig_turtle2(df, n, True, WARMUP)


# ---------------------------------------------------------------------------
# 1. Equivalence: production modules vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(STREAMS))
@pytest.mark.parametrize("symbol", ["BTCUSDT", "SOLUSDT"])
def test_entries_match_judged_harness(key, symbol):
    n, kind, tf, _wr, _rr, _ms = STREAMS[key]
    df = _load(f"{symbol}_{tf}.csv")
    judged = _judged(df, kind, n)
    production = _module(key).entries_for_frame(df, WARMUP)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


def test_turtle_filter_is_a_strict_subset_of_unfiltered():
    # Parametrisation: the trail_filt EMA(200) filter must only ever
    # REMOVE donchian entries, never add or move them (families2
    # sig_turtle2 construction).
    df = _load("BTCUSDT_1d.csv")
    unfiltered = families2.sig_turtle2(df, 55, False, WARMUP)
    filtered = _module("turtle2").entries_for_frame(df, WARMUP)
    assert set(filtered) <= set(unfiltered)
    assert len(filtered) < len(unfiltered)


def test_channel_width_changes_entries_in_judged_direction():
    # Parametrisation: the wider n=55 channel fires strictly less
    # often than n=20 on the same slice, and every n=55 entry bar is
    # also judged by the harness (exact lists already pinned above).
    df = _load("SOLUSDT_4h.csv")
    e20 = _module("donchian_turtle_n20_trail_4h").entries_for_frame(df, WARMUP)
    e55 = _module("donchian_turtle_n55_trail_4h").entries_for_frame(df, WARMUP)
    assert len(e55) < len(e20)


def test_canonical_donchian_live_signal_reproduces_judged_bracket():
    import strategy_donchian_turtle as mod

    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_donchian(df, 55, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:6]:
        sig = mod.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(6.0 * atr[i])  # BR26
        assert sig["win_rate_prior"] == pytest.approx(0.3523)
        assert sig["rr_ratio"] == pytest.approx(3.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert mod.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_canonical_turtle2_live_signal_trail_geometry():
    import strategy_turtle2 as mod

    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_turtle2(df, 55, True, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    assert judged
    for i, side in judged[:4]:
        sig = mod.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        # Judged TRAIL spec: no fixed take-profit.
        assert sig["tp_dist"] is None
        assert sig["win_rate_prior"] == pytest.approx(0.3725)


def test_atr_matches_judged_harness():
    import numpy as np

    import strategy_donchian_turtle as dmod
    import strategy_turtle2 as tmod

    for fixture in ("BTCUSDT_1d.csv", "SOLUSDT_4h.csv"):
        df = _load(fixture)
        expected = harness_atr(df, 14)
        np.testing.assert_allclose(dmod.atr14(df).to_numpy(), expected.to_numpy())
        np.testing.assert_allclose(tmod.atr14(df).to_numpy(), expected.to_numpy())


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_lane_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    for key, (_n, _kind, tf, wr, rr, ms) in STREAMS.items():
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
        assert entry["expected_net_edge_bps"] > 0, key
        # Lane-executable entries keep their judged priors.
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        if rr is None:
            assert entry["rr_ratio"] is None, key
            assert "TRAIL" in entry["tp_method"], key
        else:
            assert entry["rr_ratio"] == pytest.approx(rr), key
        assert "TASK-STR-FWD-019" in entry["reason"], key

    validated = {
        k
        for k, e in PRODUCTION_STRATEGY_REGISTRY.items()
        if e["status"] == "VALIDATED"
    }
    assert not (validated & set(STREAMS)), "lane keys must not be VALIDATED"
    # The pre-existing VALIDATED entrants are untouched by this wave.
    assert {
        "ichimoku_trend",
        "dow_effect",
        "fx_mr_v4",
        "sleeve_shock_breakout",
        "sleeve_tsmom2_dual",
    } <= validated


def test_alias_streams_not_separately_wired():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    # turtle2 unfiltered trail keys and the volume_breakout dup key
    # must NOT exist — those streams are wired once, above.
    for absent in (
        "turtle2_n20_trail",
        "turtle2_n55_trail",
        "turtle2_n20_trail_4h",
        "turtle2_n55_trail_4h",
        "volume_breakout_donch20_novol",
    ):
        assert absent not in PRODUCTION_STRATEGY_REGISTRY, absent
    # The observe-only donchian object is a different judged object;
    # none of this wave's keys collide with it.
    assert "donchian_observe_only" not in STREAMS


def test_lane_executable_only_on_attested_demo_venue():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    try:
        assert reg.governance_status("strategy_donchian_turtle") == "FORWARD_TEST"
        assert reg.governance_status("strategy_turtle2") == "FORWARD_TEST"
        ok, reason = reg.executable(
            "strategy_donchian_turtle", "1d", "BTCUSDT", venue="binance_futures"
        )
        assert not ok and reason == "FORWARD_TEST_DEMO_VENUE_ONLY"
        reg.set_demo_venues({"binance_futures"})
        assert reg.executable(
            "strategy_donchian_turtle", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert reg.executable(
            "strategy_donchian_turtle_n20_b26_4h", "4h", "ETHUSDT",
            venue="binance_futures",
        )[0]
        assert reg.executable(
            "strategy_turtle2_n55_trail_filt_4h", "4h", "SOLUSDT",
            venue="binance_futures",
        )[0]
        # Wrong timeframe is not executable.
        assert not reg.executable(
            "strategy_donchian_turtle", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key, (_n, _kind, tf, _wr, _rr, ms) in STREAMS.items():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        # Every entry in this wave carries an override: the measured
        # fixture max at 1d (0.7128) exceeds the 0.15 global cap, and
        # at 4h (0.1112) the CRYPTO30 volatile tail plausibly does.
        assert entry["max_stop_pct"] == pytest.approx(ms), key
        assert entry["max_stop_pct"] > 0.15, key
        assert entry["max_stop_pct"] >= MEASURED_MAX_STOP[tf], key


def test_measured_stop_distribution_matches_record():
    # Recompute the measured maxima the overrides rest on, from the
    # harness's own entry lists, so the record cannot drift silently.
    for tf, expected in MEASURED_MAX_STOP.items():
        worst = 0.0
        for symbol in ("BTCUSDT", "SOLUSDT"):
            df = _load(f"{symbol}_{tf}.csv")
            a = harness_atr(df, 14)
            entries = families2.sig_donchian(df, 20, WARMUP)
            for i, _side in entries:
                worst = max(worst, 2.0 * float(a.iloc[i]) / float(df["close"].iloc[i]))
        assert worst == pytest.approx(expected, abs=0.005), tf
