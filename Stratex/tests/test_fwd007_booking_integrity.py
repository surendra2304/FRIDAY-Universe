"""TASK-STR-FWD-007 — forward-ledger booking integrity fixes.

From the FWD-005 untracked-position verification (live evidence
2026-11-16, OANDA trade 470 — a sleeve-owned USDJPY long the daemon
had adopted): four defects that could lose or double-count a forward
fill, or misreport its protection (items 1 and 4 covered the OANDA
sleeve runner and adapter; their tests were removed in TASK-REL-054
with the venue — the daemon-side items 2 and 3 remain pinned here):

  2. The daemon reconciler booked closes for positions it had ADOPTED
     (never opened) as strategy "unknown" — possibly from a ticker
     estimate — and accrued them into realized_pnl, double-counting
     closes the owning engine books itself. Now: no attribution in
     position_strategy -> no ledger rows, no accrual.
  3. The untracked_position alert latched active forever (nothing
     ever called clear_alert). Now: a complete sweep that finds zero
     untracked positions clears it; an incomplete sweep (a venue read
     failed) must NOT clear it.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from measurement import fill_ledger  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """All fill-ledger / alert writes land in a tmp state dir."""
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path / "mstate"))
    yield


# ---------------------------------------------------------------------------
# 2 + 3. Daemon reconciler: adopted positions are not booked; sweep clearing
# ---------------------------------------------------------------------------

class _StubPos:
    def __init__(self, symbol, side="LONG", quantity=15.0,
                 entry_price=159.691, mark_price=160.0, position_id="470"):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.mark_price = mark_price
        self.position_id = position_id


class _StubAdapter:
    def __init__(self, live=None, pnl=None):
        self._live = live
        self._pnl = pnl
        self.base_url = "https://api-fxpractice.oanda.com"

    def get_positions_or_none(self):
        return self._live

    def get_realized_pnl(self, symbol, since_ms=None):
        return self._pnl


class _StubEngine:
    def __init__(self, adapter):
        self.positions = {}
        self.venues = {"oanda": adapter}
        self.position_opened_at = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self.realized_pnl = 100.0
        self.daily_realized_pnl = 10.0
        self.telegram_bot = None
        self.breaker_checks = 0
        self.exits = []

    def _check_daily_loss_limit(self):
        self.breaker_checks += 1

    def save_state(self):
        pass

    def get_ticker(self, venue, symbol):
        return None

    def equity_snapshot(self, trigger=None):
        return {"trigger": trigger}

    def mark_exit(self, venue, symbol):
        self.exits.append((venue, symbol))


def _make_daemon(engine, tmp_path, monkeypatch, reconcile_pass=0):
    from autonomy import run_daemon

    # Redirect the legacy testnet ledger into tmp (path derives from
    # run_daemon.__file__).
    monkeypatch.setattr(
        run_daemon, "__file__", str(tmp_path / "autonomy" / "run_daemon.py")
    )
    daemon = object.__new__(run_daemon.StratexTradingEngine)
    daemon.engine = engine
    daemon._reconcile_pass = reconcile_pass
    return daemon


_PNL = {"net": 5.0, "gross": 5.5, "fees": 0.5, "trades": 1, "last_price": 160.1}
_KEY = "oanda:USDJPY"


def _engine_with_flat_position(strategy_marker):
    adapter = _StubAdapter(live=[], pnl=dict(_PNL))
    engine = _StubEngine(adapter)
    engine.positions[_KEY] = _StubPos("USDJPY")
    engine.position_opened_at[_KEY] = int(time.time() * 1000) - 60_000
    if strategy_marker is not None:
        engine.position_strategy[_KEY] = strategy_marker
        engine.position_timeframe[_KEY] = "1d"
    return engine


def test_reconciler_does_not_book_adopted_position(tmp_path, monkeypatch):
    engine = _engine_with_flat_position(strategy_marker=None)  # adopted
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert _KEY not in engine.positions  # tracking cleanup still happens
    assert engine.realized_pnl == 100.0, "no realized accrual for foreign closes"
    assert engine.daily_realized_pnl == 10.0
    assert engine.breaker_checks == 0
    assert fill_ledger.read_fills() == [], "no measurement-ledger row"
    assert not (tmp_path / "testnet_trade_ledger.jsonl").exists(), \
        "no legacy-ledger row either"


def test_reconciler_books_daemon_opened_position(tmp_path, monkeypatch):
    engine = _engine_with_flat_position(strategy_marker="strategy_test_alpha")
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert _KEY not in engine.positions
    assert engine.realized_pnl == pytest.approx(105.0)
    assert engine.daily_realized_pnl == pytest.approx(15.0)
    assert engine.breaker_checks == 1
    rows = fill_ledger.read_fills()
    assert len(rows) == 1
    assert rows[0]["strategy"] == "strategy_test_alpha"
    assert rows[0]["engine"] == "daemon"
    legacy = (tmp_path / "testnet_trade_ledger.jsonl").read_text().strip().splitlines()
    assert len(legacy) == 1
    assert json.loads(legacy[0])["strategy"] == "strategy_test_alpha"


def test_clean_sweep_clears_latched_untracked_alert(tmp_path, monkeypatch):
    fill_ledger.raise_alert("untracked_position", "stale latch from an earlier raise")
    assert "untracked_position" in fill_ledger.active_alerts()
    adapter = _StubAdapter(live=[])  # venue read succeeds, nothing open
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch, reconcile_pass=19)

    daemon._reconcile_positions()

    assert "untracked_position" not in fill_ledger.active_alerts()


def test_sweep_with_untracked_position_keeps_alert(tmp_path, monkeypatch):
    adapter = _StubAdapter(live=[_StubPos("USDJPY")])  # open, not tracked
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch, reconcile_pass=19)

    daemon._reconcile_positions()

    assert "untracked_position" in fill_ledger.active_alerts()


def test_incomplete_sweep_does_not_clear_alert(tmp_path, monkeypatch):
    fill_ledger.raise_alert("untracked_position", "stale latch from an earlier raise")
    adapter = _StubAdapter(live=None)  # venue read failed -> state unknown
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch, reconcile_pass=19)

    daemon._reconcile_positions()

    assert "untracked_position" in fill_ledger.active_alerts(), \
        "a sweep that could not read a venue must not clear the alert"
