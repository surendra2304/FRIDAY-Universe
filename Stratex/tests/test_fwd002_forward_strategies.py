"""TASK-STR-FWD-002 — the two RD-002 winners in governed demo trading.

The heart of this file is EQUIVALENCE: the production modules
(strategy_ichimoku_trend / strategy_dow_effect) must reproduce the
judged rigorous_backtest implementations entry-for-entry on real
historical slices (tests/fixtures/fwd002/, Binance data via the RD-002
cache, resampled with the harness's own data_feed). If the traded
configuration ever drifts from the judged configuration, these tests
fail.

Also pinned: the phase-3 kill criteria (measurement/forward_guard), the
dow bracket_time exit arithmetic vs the judged simulator's TIME exits,
the daemon's trend-exit scoping fix (a governed 1d position must NOT be
EMA20-exited), and registry/governance integration.
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_dow_effect as dow
import strategy_ichimoku_trend as ichi
from measurement import forward_guard
from rigorous_backtest.rd import fastsim
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2, families3
from rigorous_backtest.rd2.costs2 import CRYPTO as CRYPTO_COSTS

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
WARMUP = 260


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


# ---------------------------------------------------------------------------
# Equivalence: production modules vs the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "SOLUSDT_4h.csv"])
def test_ichimoku_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_ichimoku(df, True, WARMUP)
    production = ichi.entries_for_frame(df, WARMUP)
    assert len(judged) >= 10, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_dow_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_dow(df, "reversal", WARMUP)
    production = dow.entries_for_frame(df, WARMUP)
    assert len(judged) >= 20, "fixture must contain a meaningful entry set"
    assert production == judged
    # Judged rule sanity: every entry bar is a Monday (UTC bar open).
    for i, _side in production:
        assert df.index[i].weekday() == 0


@pytest.mark.parametrize("fixture", ["BTCUSDT_4h.csv", "BTCUSDT_1d.csv"])
def test_atr_matches_judged_harness(fixture):
    df = _load(fixture)
    expected = harness_atr(df, 14)
    np.testing.assert_allclose(ichi.atr14(df).to_numpy(), expected.to_numpy())
    np.testing.assert_allclose(dow.atr14(df).to_numpy(), expected.to_numpy())


def test_ichimoku_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_4h.csv")
    judged = families3.sig_ichimoku(df, True, WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    checked = 0
    for i, side in judged[:8]:
        sig = ichi.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.4010)
        assert sig["rr_ratio"] == pytest.approx(2.0)
        checked += 1
    assert checked >= 5
    # A bar with no judged entry produces no signal.
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert ichi.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_dow_live_signal_reproduces_judged_bracket():
    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_dow(df, "reversal", WARMUP)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:8]:
        sig = dow.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(3.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(6.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.5227)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    entry_bars = {i for i, _ in judged}
    quiet = next(i for i in range(WARMUP, len(df) - 2) if i not in entry_bars)
    assert dow.get_signal(df.iloc[: quiet + 1])["side"] is None


def test_forming_bar_is_never_evaluated():
    # 4h bars: opens at now-12h (closed), now-8h (closed), now-4h (closed
    # exactly at its end boundary is excluded by +duration<=now only when
    # fully elapsed), now-1h (forming). Keep the three fully-elapsed ones.
    now = 1_800_000_000.0  # fixed epoch, arbitrary
    opens = [now - 12 * 3600, now - 8 * 3600, now - 4 * 3600 - 1, now - 3600]
    idx = pd.to_datetime(opens, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        index=idx,
    )
    kept = ichi._closed_frame(df, now_s=now)
    assert len(kept) == 3
    kept_d = dow._closed_frame(df, now_s=now)
    assert len(kept_d) == 0  # daily bars: none of these spans a full day


def test_dow_time_exit_matches_judged_simulator():
    df = _load("BTCUSDT_1d.csv")
    entries = dow.entries_for_frame(df, WARMUP)
    spec = {"type": "bracket_time", "sl_atr": 3.0, "tp_atr": 6.0, "max_bars": 5}
    trades = fastsim.simulate_entries(
        df, entries, harness_atr(df, 14).to_numpy(), spec, "BTCUSDT", CRYPTO_COSTS
    )
    time_trades = [t for t in trades if t.exit_reason == "TIME"]
    assert time_trades, "fixture must exercise judged TIME exits"
    for t in time_trades:
        entry_open = t.entry_time.timestamp()
        # Judged exit: close of entry_bar + 4 == entry_open + 5 days.
        due = entry_open + 5 * 86400
        assert t.exit_time.timestamp() == entry_open + 4 * 86400
        assert not forward_guard.time_exit_due(entry_open + 3600, due - 1, 5, 86400)
        assert forward_guard.time_exit_due(entry_open + 3600, due, 5, 86400)


# ---------------------------------------------------------------------------
# Phase-3 kill criteria (measurement/forward_guard)
# ---------------------------------------------------------------------------

def _rows(strategy: str, pnls: list[float]) -> list[dict]:
    base = 1_700_000_000.0
    return [
        {
            "strategy": strategy,
            "engine": "daemon",
            "net_pnl": p,
            "exit_time": base + 3600 * k,
        }
        for k, p in enumerate(pnls)
    ]


def test_guard_breaches_on_negative_expectancy_after_50_trades():
    rows = _rows("strategy_dow_effect", [-1.0] * 30 + [0.5] * 25)
    (d,) = forward_guard.evaluate(rows, 10_000.0, ["strategy_dow_effect"])
    assert d["trades"] == 55 and d["breached"]
    assert any("profit factor" in r for r in d["reasons"])


def test_guard_holds_before_50_trades():
    rows = _rows("strategy_dow_effect", [-2.0] * 49)
    (d,) = forward_guard.evaluate(rows, 10_000.0, ["strategy_dow_effect"])
    assert not d["breached"]


def test_guard_passes_a_profitable_strategy():
    rows = _rows("strategy_ichimoku_trend", [3.0] * 40 + [-1.0] * 30)
    (d,) = forward_guard.evaluate(rows, 10_000.0, ["strategy_ichimoku_trend"])
    assert d["profit_factor"] == pytest.approx(4.0)
    assert not d["breached"]


def test_guard_breaches_on_drawdown_over_5pct_equity():
    # Peak +$100 then a slide to -$650: drawdown $750 > 5% of $10,000.
    rows = _rows("strategy_ichimoku_trend", [100.0] + [-75.0] * 10)
    (d,) = forward_guard.evaluate(rows, 10_000.0, ["strategy_ichimoku_trend"])
    assert d["max_drawdown_usd"] == pytest.approx(750.0)
    assert d["breached"]


def test_guard_isolates_strategies():
    rows = _rows("strategy_dow_effect", [-1.0] * 60) + _rows(
        "strategy_ichimoku_trend", [1.0] * 60
    )
    decisions = {
        d["strategy"]: d
        for d in forward_guard.evaluate(
            rows, 10_000.0, ["strategy_dow_effect", "strategy_ichimoku_trend"]
        )
    }
    assert decisions["strategy_dow_effect"]["breached"]
    assert not decisions["strategy_ichimoku_trend"]["breached"]


# ---------------------------------------------------------------------------
# Governance / registry integration
# ---------------------------------------------------------------------------

def test_config_registry_entries_are_the_judged_configs():
    from config_strategy import (
        CRYPTO30_SYMBOLS,
        PRODUCTION_STRATEGY_REGISTRY,
    )

    assert len(CRYPTO30_SYMBOLS) == 30
    for key, wr, pf in (("ichimoku_trend", 0.4010, 1.278), ("dow_effect", 0.5227, 1.257)):
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "VALIDATED"
        assert entry["forward_protocol"] is True
        # VALIDATED entries keep their priors (the registry's nulling loop
        # must not strip them) — the daemon's expectancy gate reads these.
        assert entry["oos_win_rate_prior"] == pytest.approx(wr)
        assert entry["validated_assets"] == CRYPTO30_SYMBOLS
    assert PRODUCTION_STRATEGY_REGISTRY["dow_effect"]["max_bars"] == 5
    assert PRODUCTION_STRATEGY_REGISTRY["adx_ema"]["status"] == "OBSERVE_ONLY"


def test_registry_executability_matrix():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    assert reg.executable("strategy_ichimoku_trend", "4h", "BTCUSDT")[0]
    assert not reg.executable("strategy_ichimoku_trend", "1d", "BTCUSDT")[0]
    assert not reg.executable("strategy_ichimoku_trend", "4h", "EURUSD")[0]
    assert reg.executable("strategy_dow_effect", "1d", "MANAUSDT")[0]
    assert not reg.executable("strategy_dow_effect", "4h", "MANAUSDT")[0]
    assert reg.governance_status("strategy_adx_ema") == "OBSERVE_ONLY"


# ---------------------------------------------------------------------------
# Daemon wiring
# ---------------------------------------------------------------------------

class _FakeAdapter:
    def __init__(self):
        self.orders = []
        self.cancelled = []

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self.orders.append((symbol, side, order_type, quantity))
        return {"orderId": 1}

    def cancel_protective_orders(self, symbol):
        self.cancelled.append(symbol)
        return True


class _FakeEngine:
    def __init__(self, positions):
        self.positions = positions  # {"binance:SYM": SimpleNamespace}
        self.position_strategy = {}
        self.position_timeframe = {}
        self.position_opened_at = {}
        self.venues = {"binance": _FakeAdapter()}

    def get_candles(self, venue, symbol, tf, limit):
        # 60 flat daily candles with the last close below the EMA20 path
        # (declining series) — a trend-exit trigger for a LONG.
        now = time.time()
        day = 86400
        start = now - 60 * day
        return [
            {
                "timestamp": start + k * day,
                "open": 100 - k * 0.1,
                "high": 100 - k * 0.1,
                "low": 100 - k * 0.1,
                "close": 100 - k * 0.1,
                "volume": 1.0,
            }
            for k in range(60)
        ]

    def get_risk_summary(self):
        return {"total_equity": 10_000.0, "daily_loss_limit_hit": False}


def _daemon_with(positions):
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    daemon.engine = _FakeEngine(positions)
    daemon.strategy_denylist = set()
    daemon._last_trend_manage = 0
    daemon._last_forward_manage = 0
    daemon._persist_denylist = lambda: None
    return daemon


def test_trend_exit_manager_never_touches_governed_positions():
    pos = SimpleNamespace(side="LONG", quantity=0.5)
    daemon = _daemon_with({"binance:BTCUSDT": pos})
    daemon.engine.position_strategy["binance:BTCUSDT"] = "strategy_dow_effect"
    daemon.engine.position_timeframe["binance:BTCUSDT"] = "1d"
    daemon._manage_trend_positions()
    assert daemon.engine.venues["binance"].orders == []

    daemon2 = _daemon_with({"binance:BTCUSDT": pos})
    daemon2.engine.position_strategy["binance:BTCUSDT"] = "strategy_trend_daily"
    daemon2.engine.position_timeframe["binance:BTCUSDT"] = "1d"
    daemon2._manage_trend_positions()
    assert len(daemon2.engine.venues["binance"].orders) == 1


def test_forward_time_exit_closes_only_due_positions():
    pos = SimpleNamespace(side="LONG", quantity=0.25)
    daemon = _daemon_with({"binance:ETHUSDT": pos})
    key = "binance:ETHUSDT"
    daemon.engine.position_strategy[key] = "strategy_dow_effect"
    daemon.engine.position_timeframe[key] = "1d"
    # Opened 6 days ago (mid-bar): the 5-bar judged window has elapsed.
    daemon.engine.position_opened_at[key] = (time.time() - 6 * 86400 + 3600) * 1000
    daemon._manage_forward_time_exits()
    adapter = daemon.engine.venues["binance"]
    assert adapter.orders == [("ETHUSDT", "SELL", "MARKET", 0.25)]
    assert adapter.cancelled == ["ETHUSDT"]

    daemon2 = _daemon_with({"binance:ETHUSDT": pos})
    daemon2.engine.position_strategy[key] = "strategy_dow_effect"
    daemon2.engine.position_timeframe[key] = "1d"
    daemon2.engine.position_opened_at[key] = (time.time() - 2 * 86400) * 1000
    daemon2._manage_forward_time_exits()
    assert daemon2.engine.venues["binance"].orders == []


def test_forward_guard_hook_pauses_breached_strategy(monkeypatch):
    from measurement import fill_ledger

    rows = _rows("strategy_dow_effect", [-1.0] * 55)
    monkeypatch.setattr(fill_ledger, "read_fills", lambda: rows)
    daemon = _daemon_with({})
    persisted = []
    daemon._persist_denylist = lambda: persisted.append(True)
    daemon._maybe_apply_forward_guard()
    assert "strategy_dow_effect" in daemon.strategy_denylist
    assert persisted


def test_legacy_pruner_skips_forward_protocol_strategies(monkeypatch):
    import types

    fake = types.ModuleType("trading_report")
    fake.metrics = lambda: {
        "by_strategy": {
            "strategy_dow_effect": {"trades": 20, "net_pnl": -100.0},
            "strategy_legacy": {"trades": 20, "net_pnl": -100.0},
        }
    }
    monkeypatch.setitem(sys.modules, "trading_report", fake)
    daemon = _daemon_with({})
    daemon._maybe_prune_strategies()
    assert "strategy_dow_effect" not in daemon.strategy_denylist
    assert "strategy_legacy" in daemon.strategy_denylist
