"""TASK-STR-FWD-031 — overlay entries are placed and held at the venue bracket.

The FWD-021 overlay manager placed overlay entries with no SL/TP
bracket at all: opens went through engine.place_order with
stop_loss=None / take_profit=None, adjustments went through the raw
adapter place_order, and the tracked position recorded stop 0 / take
0 — on 2026-11-19 the daemon opened 30 unprotected overlay positions.
The venue bracket is the SL/TP protective pair the signal path places
on every other entry (venue adapter place_order with stop_loss /
take_profit -> closePosition conditional algo orders).

Pins (TASK-STR-FWD-031):
1. bracket_levels geometry: long -> stop < price < take, short ->
   take < price < stop; the distance is BRACKET_SIGMA_MULTIPLE
   one-bar sigmas (sigma / sqrt(bars_per_year[tf])) and scales with
   the timeframe; degenerate inputs return (None, None).
2. An open carries the bracket: engine.place_order receives the
   stop/take from bracket_levels and the tracked position records
   them.
3. An open with no computable bracket is refused, never placed
   unprotected (fail-closed).
4. An increase reuses the entry bracket: no new protection is placed
   (the closePosition pair covers the whole position).
5. A held legacy position (opened before brackets existed, tracked
   stop/take zero) gets the bracket attached on the next manage pass,
   and the tracked record is updated.
6. The attach is skipped when a protective algo order is already
   open on the symbol (never stack a second bracket).
7. A reduce keeps the entry bracket; a close cancels the protective
   orders.
"""

from __future__ import annotations

import math
import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import overlay_service as ov


# ---------------------------------------------------------------------------
# Stub engine/adapter (mirrors test_fwd028_overlay_allowlist_gate.py,
# extended to record bracket kwargs and simulate the venue arming the
# bracket: engine.place_order with stop/take arms conditional algo
# orders on the adapter, as the real Binance adapter does).
# ---------------------------------------------------------------------------

class _FakeAdapter:
    def __init__(self):
        self.orders = []
        self.protective_calls = []
        self.algo_orders = []
        self.cancel_calls = []

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self.orders.append({
            "symbol": symbol, "side": side, "type": order_type,
            "qty": quantity, "kw": dict(kw),
        })
        return SimpleNamespace(status="FILLED", order_id="x")

    def place_protective_orders(self, symbol, side, quantity,
                                stop_loss, take_profit):
        self.protective_calls.append({
            "symbol": symbol, "side": side, "qty": quantity,
            "stop_loss": stop_loss, "take_profit": take_profit,
        })
        self.algo_orders.append({"type": "STOP_MARKET", "trigger": stop_loss})
        self.algo_orders.append({"type": "TAKE_PROFIT_MARKET", "trigger": take_profit})
        return None

    def get_open_algo_orders(self, symbol):
        return list(self.algo_orders)

    def cancel_protective_orders(self, symbol):
        self.cancel_calls.append(symbol)
        n = len(self.algo_orders)
        self.algo_orders = []
        return n


class _FakeEngine:
    def __init__(self, closes, price=None):
        self.venues = {"binance_futures": _FakeAdapter()}
        self.positions = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self._closes = closes
        self._price = price if price is not None else closes[-1]
        self.opened = []

    def get_candles(self, venue, symbol, timeframe="15m", limit=100):
        now = time.time()
        step = 86400 if timeframe == "1d" else 14400
        start = now - step * (len(self._closes) + 1)
        return [
            {"timestamp": start + step * i, "open": c, "high": c,
             "low": c, "close": c}
            for i, c in enumerate(self._closes)
        ]

    def get_ticker(self, venue, symbol):
        return SimpleNamespace(last=self._price)

    def get_venue_equity(self, venue):
        return 20000.0

    def can_open_position(self, venue):
        return True, ""

    def place_order(self, venue, symbol, side, order_type, quantity,
                    price=None, stop_loss=None, take_profit=None,
                    strategy_name="", timeframe=""):
        self.opened.append({
            "symbol": symbol, "side": side, "qty": quantity,
            "stop_loss": stop_loss, "take_profit": take_profit,
            "strategy": strategy_name,
        })
        key = f"{venue}:{symbol}"
        self.positions[key] = SimpleNamespace(
            symbol=symbol,
            side="LONG" if side == "BUY" else "SHORT",
            quantity=quantity,
            entry_price=self._price,
            stop_loss=float(stop_loss or 0.0),
            take_profit=float(take_profit or 0.0),
        )
        self.position_strategy[key] = strategy_name
        self.position_timeframe[key] = timeframe
        # The real venue adapter arms the bracket with the entry.
        if stop_loss and take_profit:
            self.venues[venue].place_protective_orders(
                symbol, side, quantity, stop_loss, take_profit)
            # engine.place_order arming is the venue's doing, not the
            # daemon's attach path — drop it from the attach record.
            self.venues[venue].protective_calls.clear()
        return SimpleNamespace(status="FILLED", order_id="y",
                               avg_price=self._price)


def _daemon(engine, allowlist=(), denylist=()):
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    daemon.engine = engine
    daemon.symbols = {"binance_futures": ["BTCUSDT"]}
    daemon.strategy_denylist = set(denylist)
    daemon.strategy_allowlist = set(allowlist)
    daemon._last_overlay_exits = 0.0
    daemon._last_overlay_entries = 0.0
    daemon._overlay_entries_blocked = lambda: False
    return daemon


def _trend_closes(n=400, drift=0.004, seed=3):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.005, n)
    return list(100.0 * np.cumprod(1.0 + rets))


@pytest.fixture(autouse=True)
def _demo_venues(monkeypatch):
    from strategies.strategy_registry import strategy_registry

    monkeypatch.setattr(
        strategy_registry, "demo_venues",
        lambda: frozenset({"binance_futures"}),
    )


def _restrict_configs(monkeypatch, keys):
    import config_strategy

    real = config_strategy.PRODUCTION_STRATEGY_REGISTRY
    monkeypatch.setattr(
        config_strategy, "PRODUCTION_STRATEGY_REGISTRY",
        {k: real[k] for k in keys},
    )


ONE = "overlay_tsmom42_vt60_none_1d"
ONE_NAME = "strategy_overlay_tsmom42_vt60_none_1d"


# ---------------------------------------------------------------------------
# 1. bracket_levels geometry
# ---------------------------------------------------------------------------

def test_bracket_levels_long_geometry():
    stop, take = ov.bracket_levels(0.0955, "1d", 100.0, True)
    assert stop is not None and take is not None
    assert stop < 100.0 < take
    # d = 4 * 0.0955 / sqrt(365) * 100 == ~2.0
    assert stop == pytest.approx(100.0 - 4 * 0.0955 / math.sqrt(365) * 100.0)
    assert take == pytest.approx(100.0 + 4 * 0.0955 / math.sqrt(365) * 100.0)


def test_bracket_levels_short_geometry():
    stop, take = ov.bracket_levels(0.0955, "1d", 100.0, False)
    assert stop is not None and take is not None
    assert take < 100.0 < stop
    assert stop == pytest.approx(100.0 + 4 * 0.0955 / math.sqrt(365) * 100.0)
    assert take == pytest.approx(100.0 - 4 * 0.0955 / math.sqrt(365) * 100.0)


def test_bracket_levels_scales_with_timeframe():
    stop_1d, _ = ov.bracket_levels(0.5, "1d", 100.0, True)
    stop_4h, _ = ov.bracket_levels(0.5, "4h", 100.0, True)
    assert stop_1d is not None and stop_4h is not None
    # d_4h / d_1d == sqrt(365 / 2190)
    assert (100.0 - stop_4h) == pytest.approx(
        (100.0 - stop_1d) * math.sqrt(365.0 / 2190.0))


def test_bracket_levels_degenerate_returns_none():
    assert ov.bracket_levels(0.0, "1d", 100.0, True) == (None, None)
    assert ov.bracket_levels(-0.5, "1d", 100.0, True) == (None, None)
    assert ov.bracket_levels(float("nan"), "1d", 100.0, True) == (None, None)
    assert ov.bracket_levels(float("inf"), "1d", 100.0, True) == (None, None)
    assert ov.bracket_levels(0.5, "3h", 100.0, True) == (None, None)
    assert ov.bracket_levels(0.5, "1d", 0.0, True) == (None, None)
    assert ov.bracket_levels(0.5, "1d", -100.0, True) == (None, None)
    # Sigma so large the take would not be positive.
    assert ov.bracket_levels(10.0, "1d", 100.0, True) == (None, None)


# ---------------------------------------------------------------------------
# 2/3. Opens carry the bracket; no computable bracket -> no open
# ---------------------------------------------------------------------------

def test_open_carries_venue_bracket(monkeypatch):
    _restrict_configs(monkeypatch, [ONE])
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    opened = engine.opened[0]
    assert opened["side"] == "BUY"
    # Expected levels from the same judged sigma the manager used.
    target = ov.target_weight(
        pd.Series(closes), "tsmom42", 0.6, "none", "1d")
    exp_stop, exp_take = ov.bracket_levels(
        target["sigma"], "1d", closes[-1], True)
    assert opened["stop_loss"] == pytest.approx(exp_stop)
    assert opened["take_profit"] == pytest.approx(exp_take)
    assert opened["stop_loss"] < closes[-1] < opened["take_profit"]
    pos = engine.positions["binance_futures:BTCUSDT"]
    assert pos.stop_loss == pytest.approx(exp_stop)
    assert pos.take_profit == pytest.approx(exp_take)
    # The venue armed the bracket with the entry.
    assert engine.venues["binance_futures"].algo_orders


def test_open_refused_without_computable_bracket(monkeypatch):
    _restrict_configs(monkeypatch, [ONE])
    monkeypatch.setattr(
        ov, "bracket_levels", lambda *a, **k: (None, None))
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert engine.opened == []
    assert engine.venues["binance_futures"].orders == []
    assert engine.positions == {}


def _open_bracketed(monkeypatch, closes=None):
    """First pass opens a bracketed long; returns (engine, daemon)."""
    _restrict_configs(monkeypatch, [ONE])
    closes = closes if closes is not None else _trend_closes()
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    return engine, daemon


# ---------------------------------------------------------------------------
# 4. An increase reuses the entry bracket
# ---------------------------------------------------------------------------

def test_increase_reuses_entry_bracket(monkeypatch):
    _restrict_configs(monkeypatch, [ONE])
    rng = np.random.default_rng(4)
    base = list(100.0 * np.cumprod(
        1.0 + np.array([0.07, -0.05] * 200) + rng.normal(0, 0.001, 400)))
    engine, daemon = _open_bracketed(monkeypatch, base)
    adapter = engine.venues["binance_futures"]
    assert adapter.algo_orders  # entry bracket armed
    # Calm bars: sigma falls, the vol-target weight rises — increase.
    calm = list(base[-1] * np.cumprod(1.0 + rng.normal(0.004, 0.001, 120)))
    engine._closes = base + calm
    engine._price = engine._closes[-1]
    daemon._last_overlay_entries = 0.0
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(adapter.orders) == 1
    assert adapter.orders[0]["side"] == "BUY"  # the increase
    assert adapter.orders[0]["kw"] == {}  # no new protection placed
    assert adapter.protective_calls == []  # entry bracket reused
    pos = engine.positions["binance_futures:BTCUSDT"]
    assert pos.stop_loss > 0 and pos.take_profit > 0  # unchanged


# ---------------------------------------------------------------------------
# 5/6. A held legacy position gets the bracket attached (once)
# ---------------------------------------------------------------------------

def _seed_legacy_long(monkeypatch, closes):
    """Seed a position whose target already matches (delta ~ 0) and
    whose tracked record carries no bracket — as if opened before
    brackets existed."""
    _restrict_configs(monkeypatch, [ONE])
    engine = _FakeEngine(closes)
    daemon = _daemon(engine)
    target = ov.target_weight(
        pd.Series(closes), "tsmom42", 0.6, "none", "1d")
    book = 0.005 * 20000.0
    qty = target["weight"] * book / closes[-1]
    key = "binance_futures:BTCUSDT"
    engine.positions[key] = SimpleNamespace(
        symbol="BTCUSDT", side="LONG", quantity=qty,
        entry_price=closes[-1])
    engine.position_strategy[key] = ONE_NAME
    engine.position_timeframe[key] = "1d"
    return engine, daemon, target


def test_legacy_position_gets_bracket_attached(monkeypatch):
    closes = _trend_closes()
    engine, daemon, target = _seed_legacy_long(monkeypatch, closes)
    adapter = engine.venues["binance_futures"]
    daemon._manage_overlay_positions(allow_entries=True)
    assert adapter.orders == []  # held at target: no market order
    assert len(adapter.protective_calls) == 1
    call = adapter.protective_calls[0]
    exp_stop, exp_take = ov.bracket_levels(
        target["sigma"], "1d", closes[-1], True)
    assert call["symbol"] == "BTCUSDT"
    assert call["side"] == "BUY"
    assert call["stop_loss"] == pytest.approx(exp_stop)
    assert call["take_profit"] == pytest.approx(exp_take)
    pos = engine.positions["binance_futures:BTCUSDT"]
    assert pos.stop_loss == pytest.approx(exp_stop)
    assert pos.take_profit == pytest.approx(exp_take)
    # Second pass: already bracketed, no re-attach.
    daemon._last_overlay_entries = 0.0
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(adapter.protective_calls) == 1


def test_attach_skipped_when_bracket_already_armed(monkeypatch):
    closes = _trend_closes()
    engine, daemon, _ = _seed_legacy_long(monkeypatch, closes)
    adapter = engine.venues["binance_futures"]
    adapter.algo_orders.append({"type": "STOP_MARKET", "trigger": 90.0})
    daemon._manage_overlay_positions(allow_entries=True)
    assert adapter.protective_calls == []  # never stack a second bracket
    assert adapter.orders == []


# ---------------------------------------------------------------------------
# 7. A reduce keeps the entry bracket; a close cancels it
# ---------------------------------------------------------------------------

def test_reduce_keeps_entry_bracket(monkeypatch):
    engine, daemon = _open_bracketed(monkeypatch)
    adapter = engine.venues["binance_futures"]
    closes = engine._closes
    spike = list(closes[-1] * np.cumprod(
        1.0 + np.array([0.07, -0.05] * 30)))
    engine._closes = closes + spike
    engine._price = engine._closes[-1]
    daemon._last_overlay_exits = 0.0
    daemon._manage_overlay_positions(allow_entries=False)
    assert len(adapter.orders) == 1
    assert adapter.orders[0]["side"] == "SELL"  # the reduce
    assert adapter.orders[0]["kw"] == {}
    assert adapter.protective_calls == []
    pos = engine.positions["binance_futures:BTCUSDT"]
    assert pos.stop_loss > 0 and pos.take_profit > 0
    assert adapter.algo_orders  # bracket still armed after the reduce


def test_close_cancels_protective_orders(monkeypatch):
    engine, daemon = _open_bracketed(monkeypatch)
    adapter = engine.venues["binance_futures"]
    closes = engine._closes
    crash = list(closes[-1] * np.cumprod(1.0 + np.full(80, -0.01)))
    engine._closes = closes + crash
    engine._price = engine._closes[-1]
    daemon._last_overlay_exits = 0.0
    daemon._manage_overlay_positions(allow_entries=False)
    assert len(adapter.orders) == 1
    assert adapter.orders[0]["side"] == "SELL"  # the close
    assert adapter.cancel_calls == ["BTCUSDT"]
    assert adapter.algo_orders == []
