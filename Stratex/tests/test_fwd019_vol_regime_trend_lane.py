"""TASK-STR-FWD-019 WAVE-2 — RD-004 vol_regime_trend gate_lo lane.

The three RD-004 gate_lo cells (ema24_96 / don20 / ema12_48 @
CRYPTO30 2h) meet the owner's second tier (audit
~/workspace/str-nearmiss/REPORT.md §1.2) but did NOT pass the full
frozen bar. This file pins:

1. EQUIVALENCE: the production modules reproduce the judged rd4
   harness (families_rd4.base_entries + regime_rank_by_bar +
   apply_mode "gate_lo") entry-for-entry on the fwd002 fixture
   slices. The judged timeframe is 2h; only 1d/4h fixture slices
   exist, and the bar-series logic is timeframe-agnostic (the regime
   rank operates on UTC days, the signals on bars), so equivalence
   is asserted on BOTH the 4h and the 1d slices and stated as such.
   The 4h slices span only ~183 days, so the 180-day regime rank is
   finite only on their last ~16 bars and gated counts there are
   small by construction; the 1d slices carry the meaningful counts.
2. GOVERNANCE: the three keys are FORWARD_TEST lane entries with the
   judged priors, CRYPTO30 lane_assets, and none is in the VALIDATED
   partition.
3. STOP-CAP: every entry carries the FWD-012 max_stop_pct override
   (0.60), consistent with the measured fixture stop distribution
   recorded below.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_vol_regime_trend as core
import strategy_vol_regime_trend_don20_gate_lo as don20_mod
import strategy_vol_regime_trend_ema12_48_gate_lo as ema12_mod
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd4 import families_rd4

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260

MODULES = {
    "ema24_96": core,
    "don20": don20_mod,
    "ema12_48": ema12_mod,
}
KEYS = {
    "ema24_96": "vol_regime_trend",
    "don20": "vol_regime_trend_don20_gate_lo",
    "ema12_48": "vol_regime_trend_ema12_48_gate_lo",
}
ALL_FIXTURES = ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv", "BTCUSDT_4h.csv", "SOLUSDT_4h.csv"]

# FWD-012 stop-cap measurements (2.0 x ATR(14) / close), computed on
# the fwd002 4h fixtures per the wave-2 brief (2h configs measured on
# 4h slices — per-bar ATR only shrinks with timeframe, so the 4h
# figure is a conservative upper bound for 2h): max over gated entry
# bars 0.0477 (SOLUSDT don20); max over all bars >= warmup 0.1300
# (SOLUSDT; BTCUSDT 0.0936); max over the full SOLUSDT 4h history
# 0.5604. Chosen override: 0.60.
MEASURED_ENTRY_MAX = 0.0477
MEASURED_WARMUP_MAX = 0.1300
MEASURED_FULL_HISTORY_MAX = 0.5604
CHOSEN_MAX_STOP_PCT = 0.60


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _judged(df: pd.DataFrame, signal: str):
    """The judged harness pipeline, verbatim."""
    gated = families_rd4.apply_mode(
        families_rd4.base_entries(df, signal),
        "gate_lo",
        families_rd4.regime_rank_by_bar(df),
    )
    return [(i, side) for i, side, _f in gated]


# ---------------------------------------------------------------------------
# 1. Equivalence: production modules vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ALL_FIXTURES)
@pytest.mark.parametrize("signal", ["ema24_96", "don20", "ema12_48"])
def test_entries_match_judged_harness(fixture, signal):
    df = _load(fixture)
    judged = _judged(df, signal)
    production = MODULES[signal].entries_for_frame(df, WARMUP)
    assert production == judged


def test_equivalence_entry_counts_are_meaningful():
    # Pooled over the four slices each variant must carry a real
    # entry set (the 1d slices dominate; see module docstring).
    for signal, mod in MODULES.items():
        total = sum(len(mod.entries_for_frame(_load(fx), WARMUP)) for fx in ALL_FIXTURES)
        assert total >= 5, (signal, total)
    # don20 on the 1d slices alone is the family's dense stream.
    for fx in ("BTCUSDT_1d.csv", "SOLUSDT_1d.csv"):
        assert len(don20_mod.entries_for_frame(_load(fx), WARMUP)) >= 10


def test_gate_removes_entries_relative_to_base():
    # The gate_lo machinery must actually gate: on the 1d slices the
    # gated list is a strict subset of the ungated base list.
    df = _load("BTCUSDT_1d.csv")
    base = families_rd4.base_entries(df, "don20")
    gated = don20_mod.entries_for_frame(df, WARMUP)
    assert 0 < len(gated) < len(base)
    assert set(gated) <= set(base)


def test_variant_parameters_change_the_mask():
    # Parameterisation: the three base signals are distinct streams
    # under the one gate (masks differ beyond the gate itself).
    df = _load("BTCUSDT_1d.csv")
    masks = {s: m.signal_masks(df) for s, m in MODULES.items()}
    longs = {s: masks[s][0].fillna(False) for s in MODULES}
    assert not longs["ema24_96"].equals(longs["don20"])
    assert not longs["ema12_48"].equals(longs["don20"])
    assert not longs["ema24_96"].equals(longs["ema12_48"])


@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "BTCUSDT_1d.csv"])
def test_atr_matches_judged_harness(fixture):
    df = _load(fixture)
    expected = harness_atr(df, 14)
    np.testing.assert_allclose(core.atr14(df).to_numpy(), expected.to_numpy())


def test_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = don20_mod.entries_for_frame(df, WARMUP)
    assert judged, "fixture must contain judged entries"
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:4]:
        sig = don20_mod.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3681)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert don20_mod.get_signal(df.iloc[: quiet + 1])["side"] is None


# ---------------------------------------------------------------------------
# 2. Governance: registry / partition
# ---------------------------------------------------------------------------

def test_config_registry_lane_entries():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    for key, wr, edge in (
        ("vol_regime_trend", 0.3675, 20.3),
        ("vol_regime_trend_don20_gate_lo", 0.3681, 14.8),
        ("vol_regime_trend_ema12_48_gate_lo", 0.3598, 10.7),
    ):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["timeframe"] == "2h", key
        assert entry["lane_assets"] == CRYPTO30_SYMBOLS, key
        assert entry["runtime_priors_nulled"] is False, key
        assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert entry["risk_per_trade_pct"] == pytest.approx(0.001), key
        assert entry["max_heat_pct"] == pytest.approx(0.02), key
        assert not entry.get("validated_assets"), key

    validated = {
        k for k, e in PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert validated == {
        "ichimoku_trend",
        "dow_effect",
        "fx_mr_v4",
        "sleeve_shock_breakout",
        "sleeve_tsmom2_dual",
    }
    for key in KEYS.values():
        assert key not in validated


def test_registry_discovers_modules_and_binds_lane():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    for key in KEYS.values():
        assert reg.get(f"strategy_{key}") is not None, key
        assert reg.governance_status(f"strategy_{key}") == "FORWARD_TEST", key
    # Blocked without a demo attestation; executable on one.
    ok, reason = reg.executable(
        "strategy_vol_regime_trend", "2h", "BTCUSDT", venue="binance_futures"
    )
    assert not ok and reason == "FORWARD_TEST_DEMO_VENUE_ONLY"
    reg.set_demo_venues({"binance_futures"})
    try:
        for key in KEYS.values():
            assert reg.executable(
                f"strategy_{key}", "2h", "BTCUSDT", venue="binance_futures"
            )[0], key
        # Wrong timeframe is not executable.
        assert not reg.executable(
            "strategy_vol_regime_trend", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())


def test_daemon_forward_protocol_covers_family():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    for key in KEYS.values():
        assert f"strategy_{key}" in entries, key
        assert daemon._lane_for_strategy(f"strategy_{key}") == "FORWARD_TEST", key


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_override_consistent_with_measurements():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    assert MEASURED_WARMUP_MAX <= 0.15  # warmup-window bars fit the cap…
    assert MEASURED_FULL_HISTORY_MAX > 0.15  # …the fixture tail does not
    for key in KEYS.values():
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        # Override present, above the global cap, and at or above
        # every measured fixture maximum.
        assert entry["max_stop_pct"] == pytest.approx(CHOSEN_MAX_STOP_PCT), key
        assert entry["max_stop_pct"] > 0.15, key
        assert entry["max_stop_pct"] >= MEASURED_FULL_HISTORY_MAX, key
        assert entry["max_stop_pct"] >= MEASURED_ENTRY_MAX, key
