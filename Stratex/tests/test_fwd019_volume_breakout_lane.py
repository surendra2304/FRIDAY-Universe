"""TASK-STR-FWD-019 WAVE-2 — volume_breakout FORWARD_TEST lane entry.

INVESTIGATION RESULT (pinned here): a module
Stratex/strategy_volume_breakout.py already existed at the base, but
(a) it had NO PRODUCTION_STRATEGY_REGISTRY entry (governance status
UNREGISTERED, so the daemon never executed it), and (b) its signal
logic DIFFERS from the judged harness function in substance:
prior-10-bar (judged: prior-20-bar) breakout, an added EMA50/EMA200
trend filter (judged: none), rolling-mean ATR with a 2.5x/5.0x
bracket (judged: EWM ATR, BR24 2.0x/4.0x), and a namedtuple return
(judged daemon contract: dict). The judged port therefore REPLACES
the dead module's logic; the equivalence test below pins the judged
behaviour (families2.sig_volume_breakout, confirm=1.5).

Also pins: registry/partition shape in the test_fwd003 pattern, and
FWD-012 stop-cap consistency — measured entry-bar stop maximum
71.28% (SOLUSDT 1d, the 2022-11-09 FTX-collapse bar; BTCUSDT 1d
12.89%), so the entry declares max_stop_pct 0.90 (measured
2026-11-18 on the fwd002 fixtures).
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_volume_breakout as vb
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260
MEASURED_MAX_STOP = 0.7128  # SOLUSDT 1d entry bars (BTCUSDT: 0.1289)
GLOBAL_CAP = 0.15


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_volume_breakout_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_volume_breakout(df, 1.5, WARMUP)
    production = vb.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


def test_volume_confirmation_is_the_judged_one():
    """The unconfirmed sibling (donch20_novol) is a DIFFERENT stream
    (it duplicates donchian n20_b24 and is not wired here): the
    production module must NOT reproduce it."""
    df = _load("BTCUSDT_1d.csv")
    novol = families2.sig_volume_breakout(df, None, WARMUP)
    production = vb.entries_for_frame(df, WARMUP)
    assert production != novol
    assert len(production) < len(novol)


def test_volume_breakout_live_signal_reproduces_judged_bracket():
    df = _load("SOLUSDT_1d.csv")
    judged = families2.sig_volume_breakout(df, 1.5, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    checked = 0
    for i, side in judged:
        if i >= len(df) - 1:
            continue  # live evaluation needs the bar closed + dropped-bar logic
        sig = vb.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.3925)
        assert sig["rr_ratio"] == pytest.approx(2.0)
        checked += 1
        if checked >= 5:
            break
    assert checked >= 3


def test_forming_bar_is_never_evaluated():
    now = 1_800_000_000.0
    opens = [now - 3 * 86400, now - 2 * 86400, now - 86400 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    assert len(vb._closed_frame(df, now_s=now)) == 3


# ---------------------------------------------------------------------------
# 2. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_lane_entry():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["volume_breakout"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["version"] == "v1.0.0 (TASK-STR-FWD-019)"
    assert entry["forward_protocol"] is True
    assert entry["forward_lane"] == "FORWARD_TEST"
    assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS
    assert entry["validated_assets"] == []
    assert entry["risk_per_trade_pct"] == 0.001
    assert entry["max_heat_pct"] == 0.02
    assert entry["runtime_priors_nulled"] is False
    assert entry["oos_win_rate_prior"] == pytest.approx(0.3925)
    assert entry["expected_net_edge_bps"] == pytest.approx(241.7)
    assert "TASK-STR-FWD-019 WAVE-2 near-miss admission" in entry["reason"]
    assert "donch20_novol" in entry["reason"]  # duplicate-alias note

    validated = {
        k
        for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items()
        if e["status"] == "VALIDATED"
    }
    assert "volume_breakout" not in validated


def test_daemon_partition_includes_key():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    assert "strategy_volume_breakout" in entries
    assert daemon._lane_for_strategy("strategy_volume_breakout") == "FORWARD_TEST"
    assert daemon._max_stop_pct_for_strategy("strategy_volume_breakout") == 0.90


def test_registry_discovers_module_on_demo_venue():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    reg.set_demo_venues({"binance_futures"})
    try:
        assert reg.executable(
            "strategy_volume_breakout", "1d", "BTCUSDT", venue="binance_futures"
        )[0]
        assert not reg.executable(
            "strategy_volume_breakout", "4h", "BTCUSDT", venue="binance_futures"
        )[0]
    finally:
        reg.set_demo_venues(set())
    assert not reg.executable(
        "strategy_volume_breakout", "1d", "BTCUSDT", venue="binance_futures"
    )[0]


# ---------------------------------------------------------------------------
# 3. Stop-cap consistency (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    import config_strategy as cs

    entry = cs.PRODUCTION_STRATEGY_REGISTRY["volume_breakout"]
    assert entry["max_stop_pct"] > GLOBAL_CAP
    assert entry["max_stop_pct"] >= MEASURED_MAX_STOP
    df = _load("SOLUSDT_1d.csv")
    atr = harness_atr(df, 14)
    entries = vb.entries_for_frame(df, WARMUP)
    worst = max(2.0 * float(atr.iloc[i]) / float(df["close"].iloc[i])
                for i, _ in entries)
    assert worst == pytest.approx(MEASURED_MAX_STOP, abs=0.005)
