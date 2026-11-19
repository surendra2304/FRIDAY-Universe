"""TASK-STR-FWD-028 — overlay manager allowlist gate.

The FWD-021 overlay manager executed every FORWARD_TEST overlay config
from PRODUCTION_STRATEGY_REGISTRY on every scan cycle without ever
consulting STRATEX_STRATEGY_ALLOWLIST, while the signal path skips any
strategy missing from a non-empty allowlist. On 2026-11-19 the daemon
opened 30 overlay positions (the overlay path places orders with no
venue SL/TP brackets) while the allowlist held only the four
signal-path names.

Pins:
1. Non-empty allowlist WITHOUT the overlay name -> the manager opens
   nothing and manages nothing (an existing position of that config is
   left completely untouched).
2. Non-empty allowlist WITH the overlay name -> that config is managed
   exactly as before, and a second, non-allowlisted config is gated
   out even though it sorts first.
3. Empty allowlist -> every overlay config is managed (back-compat;
   this is the pre-fix behaviour and must not change).
4. The skipped names are named in a WARNING log record, so a daemon
   start journal proves the gate is working.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Stub engine/adapter (mirrors test_fwd021_overlay_service.py section 5)
# ---------------------------------------------------------------------------

class _FakeAdapter:
    def __init__(self):
        self.orders = []

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self.orders.append((symbol, side, order_type, quantity))
        return SimpleNamespace(status="FILLED", order_id="x")


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
        self.opened.append((symbol, side, quantity, strategy_name))
        key = f"{venue}:{symbol}"
        self.positions[key] = SimpleNamespace(
            symbol=symbol,
            side="LONG" if side == "BUY" else "SHORT",
            quantity=quantity,
        )
        self.position_strategy[key] = strategy_name
        self.position_timeframe[key] = timeframe
        return SimpleNamespace(status="FILLED", order_id="y")


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
    """Restrict the manager to the given registry configs."""
    import config_strategy

    real = config_strategy.PRODUCTION_STRATEGY_REGISTRY
    monkeypatch.setattr(
        config_strategy, "PRODUCTION_STRATEGY_REGISTRY",
        {k: real[k] for k in keys},
    )


ONE = "overlay_tsmom42_vt60_none_1d"
ONE_NAME = "strategy_overlay_tsmom42_vt60_none_1d"
FIRST = "overlay_ema10_50_vt60_none_1d"  # sorts before ONE
FIRST_NAME = "strategy_overlay_ema10_50_vt60_none_1d"


# ---------------------------------------------------------------------------
# 1. Non-allowlisted config: no entries, no management
# ---------------------------------------------------------------------------

def test_gate_blocks_entries_for_non_allowlisted_overlay(monkeypatch):
    _restrict_configs(monkeypatch, [ONE])
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine, allowlist={"strategy_dow_effect"})
    daemon._manage_overlay_positions(allow_entries=True)
    assert engine.opened == []
    assert engine.venues["binance_futures"].orders == []


def test_gate_blocks_management_of_existing_position(monkeypatch):
    _restrict_configs(monkeypatch, [ONE])
    closes = _trend_closes()
    engine = _FakeEngine(closes)
    # An existing long owned by the overlay config; the crash series
    # flips its target, so an ungated manager would close it here.
    key = "binance_futures:BTCUSDT"
    engine.positions[key] = SimpleNamespace(
        symbol="BTCUSDT", side="LONG", quantity=0.25)
    engine.position_strategy[key] = ONE_NAME
    crash = list(closes[-1] * np.cumprod(1.0 + np.full(80, -0.01)))
    engine._closes = closes + crash
    engine._price = engine._closes[-1]
    daemon = _daemon(engine, allowlist={"strategy_dow_effect"})
    daemon._manage_overlay_positions(allow_entries=False)
    assert engine.venues["binance_futures"].orders == []
    assert key in engine.positions  # untouched


# ---------------------------------------------------------------------------
# 2. Allowlisted config is managed; a gated config sorting first is not
# ---------------------------------------------------------------------------

def test_allowlisted_overlay_managed_others_gated(monkeypatch):
    _restrict_configs(monkeypatch, [FIRST, ONE])
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine, allowlist={ONE_NAME})
    daemon._manage_overlay_positions(allow_entries=True)
    assert len(engine.opened) == 1
    symbol, side, qty, strat = engine.opened[0]
    assert (symbol, side) == ("BTCUSDT", "BUY")
    assert strat == ONE_NAME


# ---------------------------------------------------------------------------
# 3. Empty allowlist: back-compat — every config managed
# ---------------------------------------------------------------------------

def test_empty_allowlist_manages_all_configs(monkeypatch):
    _restrict_configs(monkeypatch, [FIRST, ONE])
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine, allowlist=set())
    daemon._manage_overlay_positions(allow_entries=True)
    # The first-sorted config takes the symbol exactly as pre-fix.
    assert len(engine.opened) == 1
    assert engine.opened[0][3] == FIRST_NAME


# ---------------------------------------------------------------------------
# 4. Skipped names are logged loudly
# ---------------------------------------------------------------------------

def test_gate_logs_skipped_names_as_warning(monkeypatch, caplog):
    _restrict_configs(monkeypatch, [ONE])
    engine = _FakeEngine(_trend_closes())
    daemon = _daemon(engine, allowlist={"strategy_dow_effect"})
    with caplog.at_level(logging.WARNING, logger="stratex_daemon"):
        daemon._manage_overlay_positions(allow_entries=True)
    hits = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "STRATEX_STRATEGY_ALLOWLIST" in r.getMessage()
        and ONE_NAME in r.getMessage()
    ]
    assert hits, "expected a WARNING naming the gated overlay config"
