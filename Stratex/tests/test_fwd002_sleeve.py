"""TASK-STR-FWD-002 sleeve extension — the RD-002 Stage-C sleeve.

The judged sleeve (best_per_class, equal weight) had four legs; venue
fidelity (verified live 2026-11-15: the OANDA practice account holds
68 instruments, ALL currency pairs) excludes two of them:

  IN : shock_breakout/k1.0 @ crypto30 1wk   -> strategy_sleeve_shock_breakout
  IN : tsmom2_dual/roc90_ema200 @ forex28 1d -> oanda_demo/sleeve_runner
  OUT: vol_adaptive_trend @ comm7 4h (no commodity instruments)
  OUT: keltner_breakout @ idx7 1d    (no index instruments)

This suite pins: (1) EQUIVALENCE of the shock leg against the
judged rd2 implementations on real historical slices, including the
judged weekly-bar construction (7-day buckets anchored at each
symbol's judged series start — NOT native weekly klines); (2) the
sleeve-level kill rule (combined drawdown only); (3) the daemon
sleeve-guard actions (denylist + OANDA runner pause file).

TASK-REL-054 (2026-11-19) removed the OANDA leg's coverage with the
venue itself: the tsmom equivalence tests (oanda_demo/sleeve_signals),
the FX-MR-v4 ownership tests (oanda_demo/trader) and the sleeve-runner
governed-scan tests (oanda_demo/sleeve_runner) were deleted together
with the oanda_demo package. The sleeve registry/guard tests remain:
the sleeve's judged record and the daemon-side guard are venue data,
not OANDA code.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_sleeve_shock_breakout as shock
from measurement import forward_guard
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2, families3

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")

SHOCK_TAG = "strategy_sleeve_shock_breakout"
TSMOM_TAG = "strategy_sleeve_tsmom2_dual"


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _candles(df: pd.DataFrame) -> list:
    return [
        {
            "timestamp": int(ts.timestamp()),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(getattr(r, "volume", 0.0)),
        }
        for ts, r in df.iterrows()
    ]


# ---------------------------------------------------------------------------
# Equivalence: shock leg (weekly bars are the judged construction)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1wk.csv", "SUIUSDT_1wk.csv"])
def test_shock_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_shock(df, 1.0, 104)
    assert shock.entries_for_frame(df) == judged
    assert len(judged) > 0  # the slice actually exercises the signal


@pytest.mark.parametrize(
    "daily_fixture,weekly_fixture,symbol",
    [
        ("BTCUSDT_1d_for_wk.csv", "BTCUSDT_1wk.csv", "BTCUSDT"),
        ("SUIUSDT_1d_for_wk.csv", "SUIUSDT_1wk.csv", "SUIUSDT"),
    ],
)
def test_weekly_aggregation_rebuilds_judged_bars(daily_fixture, weekly_fixture, symbol):
    daily = _load(daily_fixture)
    judged_weekly = _load(weekly_fixture)
    rebuilt = shock.weekly_candles(_candles(daily), symbol)
    got = pd.DataFrame(rebuilt)
    got.index = pd.to_datetime(got.pop("timestamp"), unit="s", utc=True)
    # The rebuilt series must cover the judged frame bar-for-bar
    # (the trailing partial bucket, if any, is beyond the judged frame).
    n = len(judged_weekly)
    got = got.iloc[:n]
    assert len(got) == n
    for col in ("open", "high", "low", "close"):
        np.testing.assert_allclose(
            got[col].to_numpy(), judged_weekly[col].to_numpy(), rtol=0, atol=1e-9
        )
    assert (got.index == judged_weekly.index).all()


def test_shock_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1wk.csv")
    entries = shock.entries_for_frame(df)
    i, side = entries[-1]
    frame = df.iloc[: i + 1]
    sig = shock.get_signal(frame)
    assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
    atr_i = float(harness_atr(frame).iloc[i])
    assert sig["sl_dist"] == pytest.approx(2.0 * atr_i)
    assert sig["tp_dist"] == pytest.approx(4.0 * atr_i)
    assert sig["rr_ratio"] == pytest.approx(2.0)


def test_shock_forming_bucket_is_never_evaluated():
    df = _load("BTCUSDT_1wk.csv")
    entries = shock.entries_for_frame(df)
    i, _side = entries[-1]
    frame = df.iloc[: i + 1].copy()
    # Append a still-forming bucket timestamped at the current week:
    # the signal on the last CLOSED bar must be unaffected... and if
    # the last closed bar had no signal, none may appear.
    now_bucket = (int(time.time()) // 604800) * 604800
    forming = frame.iloc[[-1]].copy()
    forming.index = [pd.Timestamp(now_bucket, unit="s", tz="UTC")]
    joined = pd.concat([frame, forming])
    sig = shock.get_signal(joined)
    assert sig == shock.get_signal(frame)


# ---------------------------------------------------------------------------
# Governance: the reduced sleeve is registered honestly
# ---------------------------------------------------------------------------

def test_sleeve_registry_entries():
    from config_strategy import (
        FOREX28_SYMBOLS,
        PRODUCTION_STRATEGY_REGISTRY,
        SLEEVE_NAME,
    )

    assert len(FOREX28_SYMBOLS) == 28
    shock_e = PRODUCTION_STRATEGY_REGISTRY["sleeve_shock_breakout"]
    assert shock_e["status"] == "VALIDATED"
    assert shock_e["sleeve"] == SLEEVE_NAME == "best_per_class"
    assert shock_e["timeframe"] == "1wk"
    assert len(shock_e["validated_assets"]) == 30
    tsmom_e = PRODUCTION_STRATEGY_REGISTRY["sleeve_tsmom2_dual"]
    assert tsmom_e["status"] == "VALIDATED"
    assert tsmom_e["sleeve"] == "best_per_class"
    assert tsmom_e["validated_assets"] == FOREX28_SYMBOLS
    # The excluded legs are on the record as DISABLED, with reasons.
    for key in ("sleeve_vol_adaptive_trend", "sleeve_keltner_breakout"):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "DISABLED"
        assert "EXCLUDED" in entry["reason"]


def test_sleeve_executability_matrix():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    assert reg.executable(SHOCK_TAG, "1wk", "BTCUSDT")[0]
    assert not reg.executable(SHOCK_TAG, "4h", "BTCUSDT")[0]
    assert not reg.executable(SHOCK_TAG, "1wk", "EURUSD")[0]
    # The tsmom leg has NO daemon module by design (the OANDA sleeve
    # runner executes it); the daemon must never claim it.
    assert TSMOM_TAG not in reg.get_all_strategy_names()


# ---------------------------------------------------------------------------
# Sleeve kill rule: combined drawdown only
# ---------------------------------------------------------------------------

def _fill(strategy, net, exit_time):
    return {"strategy": strategy, "net_pnl": net, "exit_time": exit_time}


def test_sleeve_guard_combines_components():
    rows = [
        _fill(SHOCK_TAG, +400.0, 1.0),
        _fill(TSMOM_TAG, -500.0, 2.0),
        _fill(SHOCK_TAG, -250.0, 3.0),
        _fill("strategy_ichimoku_trend", -9999.0, 4.0),  # not a component
    ]
    sleeves = {"best_per_class": [SHOCK_TAG, TSMOM_TAG]}
    (d,) = forward_guard.evaluate_sleeves(rows, 10_000.0, sleeves)
    assert d["trades"] == 3
    # Curve: +400 (peak) -> -100 -> -350: max DD = 400 - (-350) = 750
    assert d["max_drawdown_usd"] == pytest.approx(750.0)
    assert d["breached"] is True  # 750 > 5% of 10,000


def test_sleeve_guard_holds_within_limit():
    rows = [_fill(SHOCK_TAG, +100.0, 1.0), _fill(TSMOM_TAG, -150.0, 2.0)]
    (d,) = forward_guard.evaluate_sleeves(
        rows, 10_000.0, {"best_per_class": [SHOCK_TAG, TSMOM_TAG]}
    )
    assert d["max_drawdown_usd"] == pytest.approx(150.0)
    assert d["breached"] is False


def test_daemon_sleeve_guard_hook_pauses_everything(monkeypatch, tmp_path):
    import measurement.fill_ledger as ledger
    from autonomy import run_daemon as rd

    rows = [
        _fill(SHOCK_TAG, +400.0, 1.0),
        _fill(TSMOM_TAG, -500.0, 2.0),
        _fill(SHOCK_TAG, -250.0, 3.0),
    ]
    monkeypatch.setattr(ledger, "read_fills", lambda: rows)

    daemon = rd.StratexTradingEngine.__new__(rd.StratexTradingEngine)
    daemon.engine = SimpleNamespace(
        get_risk_summary=lambda: {"total_equity": 10_000.0, "daily_loss_limit_hit": False}
    )
    daemon.strategy_denylist = set()
    persisted = []
    daemon._persist_denylist = lambda: persisted.append(True)

    pause_file = (
        os.path.join(os.path.dirname(os.path.dirname(rd.__file__)),
                     "data", "sleeve_oanda", "sleeve_entries_paused")
    )
    preexisting = os.path.exists(pause_file)
    try:
        daemon._maybe_apply_forward_guard()
        assert SHOCK_TAG in daemon.strategy_denylist
        assert TSMOM_TAG in daemon.strategy_denylist
        assert persisted, "denylist must be persisted on a sleeve kill"
        assert os.path.exists(pause_file), "OANDA runner pause file must be written"
        with open(pause_file) as fh:
            assert "sleeve" in fh.read().lower()
    finally:
        if not preexisting and os.path.exists(pause_file):
            os.remove(pause_file)
