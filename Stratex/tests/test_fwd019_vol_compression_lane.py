"""TASK-STR-FWD-019 WAVE-2 — vol_compression FORWARD_TEST lane entries.

The judged timeframe is 1h; the fwd002 fixtures exist only at 1d/4h.
The signal logic is a bar-series function (families3.sig_vol_compression
consumes whatever bar series it is fed — timeframe-agnostic), so
equivalence is pinned on the 4h fixture frame, as the wave-2 brief
directs:
1. EQUIVALENCE at the judged warmup (260) on both 4h fixtures for both
   variants (the squeeze is sparse there — the SOL raw cell carries
   the only entry — so this pins exact agreement incl. empty lists);
   AND equivalence at warmup 60 on the 4h + 1d fixtures, where the
   squeeze fires more often, with a meaningful pooled entry count.
   Warmup is a harness parameter; the port is warmup-agnostic.
2. REGISTRY/PARTITION: FORWARD_TEST, judged universe, FWD-006 fields,
   daemon forward-protocol partition, not VALIDATED.
3. STOP-CAP CONSISTENCY (FWD-012): both entries declare max_stop_pct
   0.90. Measured on the 4h fixture frame (conservative upper bound
   for 1h — per-bar ATR shrinks with timeframe): entry-bar stop max
   4.97% (SOLUSDT 4h squeeze_raw), all-bar stop max 56.04% (SOLUSDT
   4h) / 9.36% (BTCUSDT 4h) — the tail plausibly exceeds the 0.15
   global cap, hence the override (measured 2026-11-18).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_vol_compression as vc
import strategy_vol_compression_squeeze_raw as vc_raw
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
MEASURED_ENTRY_MAX_STOP_4H = 0.0497   # SOLUSDT 4h, squeeze_raw entry bar
MEASURED_ALLBAR_MAX_STOP_4H = 0.5604  # SOLUSDT 4h, all bars (crash tail)
GLOBAL_CAP = 0.15


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness (4h fixture frame, per brief)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_volcomp_entries_match_judged_harness_at_judged_warmup(fixture):
    df = _load(fixture)
    assert vc.entries_for_frame(df, WARMUP) == families3.sig_vol_compression(
        df, True, WARMUP
    )
    assert vc_raw.entries_for_frame(df, WARMUP) == families3.sig_vol_compression(
        df, False, WARMUP
    )


@pytest.mark.parametrize(
    "fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv", "BTCUSDT_1d.csv", "SOLUSDT_1d.csv"]
)
def test_volcomp_entries_match_judged_harness_reduced_warmup(fixture):
    """Same logic at warmup 60 (a harness parameter): the squeeze
    fires often enough here to pin the masks with real entries."""
    df = _load(fixture)
    assert vc.entries_for_frame(df, 60) == families3.sig_vol_compression(df, True, 60)
    assert vc_raw.entries_for_frame(df, 60) == families3.sig_vol_compression(
        df, False, 60
    )


def test_volcomp_reduced_warmup_entry_count_is_meaningful():
    total = 0
    for fixture in ("BTCUSDT_4h.csv", "SOLUSDT_4h.csv",
                    "BTCUSDT_1d.csv", "SOLUSDT_1d.csv"):
        df = _load(fixture)
        total += len(vc.entries_for_frame(df, 60))
        total += len(vc_raw.entries_for_frame(df, 60))
    assert total >= 5, "pooled reduced-warmup equivalence must carry real entries"


def test_volcomp_live_signal_shape():
    df = _load("SOLUSDT_4h.csv")
    judged = families3.sig_vol_compression(df, False, WARMUP)
    assert judged, "SOL 4h fixture carries a judged raw entry at warmup 260"
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged:
        sig = vc_raw.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3655)
    # Module timeframe geometry: 1h bars.
    assert vc.BAR_SECONDS == 3600
    assert vc_raw.BAR_SECONDS == 3600


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0
    opens = [now - 3 * 3600, now - 2 * 3600, now - 3600 - 1, now - 60]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(vc._closed_frame(df, now_s=now)) == 3
    assert len(vc_raw._closed_frame(df, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

NEW_KEYS = {
    "vol_compression": (0.3732, 18.2),
    "vol_compression_squeeze_raw": (0.3655, 7.6),
}


def test_registry_lane_entries():
    import config_strategy as cs

    for key, (wr, edge) in NEW_KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)", key
        assert entry["timeframe"] == "1h", key
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
            "strategy_vol_compression", "1h", "BTCUSDT", venue="binance_futures"
        )[0]
        assert reg.executable(
            "strategy_vol_compression_squeeze_raw", "1h", "SOLUSDT",
            venue="binance_futures",
        )[0]
        assert not reg.executable(
            "strategy_vol_compression", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())
    assert not reg.executable(
        "strategy_vol_compression", "1h", "BTCUSDT", venue="binance_futures"
    )[0]


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    import config_strategy as cs

    for key in NEW_KEYS:
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["max_stop_pct"] > GLOBAL_CAP, key
        assert entry["max_stop_pct"] >= MEASURED_ALLBAR_MAX_STOP_4H, key
    # Recompute the measured constants from the SOL 4h fixture.
    df = _load("SOLUSDT_4h.csv")
    atr = harness_atr(df, 14)
    allbar = (2.0 * atr / df["close"]).max()
    assert float(allbar) == pytest.approx(MEASURED_ALLBAR_MAX_STOP_4H, abs=0.01)
    entries = vc_raw.entries_for_frame(df, WARMUP)
    assert entries
    worst_entry = max(2.0 * float(atr.iloc[i]) / float(df["close"].iloc[i])
                      for i, _ in entries)
    assert worst_entry == pytest.approx(MEASURED_ENTRY_MAX_STOP_4H, abs=0.005)
