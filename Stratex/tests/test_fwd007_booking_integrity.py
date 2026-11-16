"""TASK-STR-FWD-007 — forward-ledger booking integrity fixes.

From the FWD-005 untracked-position verification (live evidence
2026-11-16, OANDA trade 470 — a sleeve-owned USDJPY long the daemon
had adopted): four defects that could lose or double-count a forward
fill, or misreport its protection:

  1. The sleeve runner popped a closed trade from own_trades BEFORE
     booking it, and _book_close swallowed all exceptions — one
     transient broker failure at close time permanently lost the fill.
     Now: book first, pop only on success; failure keeps the trade in
     own_trades (the retry queue) and latches unrecorded_close.
  2. The daemon reconciler booked closes for positions it had ADOPTED
     (never opened) as strategy "unknown" — possibly from a ticker
     estimate — and accrued them into realized_pnl, double-counting
     closes the owning engine books itself. Now: no attribution in
     position_strategy -> no ledger rows, no accrual.
  3. The untracked_position alert latched active forever (nothing
     ever called clear_alert). Now: a complete sweep that finds zero
     untracked positions clears it; an incomplete sweep (a venue read
     failed) must NOT clear it.
  4. The OANDA adapter's open_trades() read the legacy stopLoss /
     takeProfit fields, which are null in the current API, reporting
     SL/TP as 0.0 for protected trades. Now it reads the linked
     stopLossOrder / takeProfitOrder records.
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
# 1. Sleeve runner: book-first-then-pop with retry
# ---------------------------------------------------------------------------

_TRADE_META = {
    "symbol": "USDJPY",
    "side": "LONG",
    "units": 15,
    "entry_price": 159.691,
    "entry_time": 1794780546.0,
    "order_id": "470",
}

_CLOSED_RECORD = {
    "trade": {
        "id": "470",
        "state": "CLOSED",
        "realizedPL": "1.23",
        "averageClosePrice": "160.100",
        "price": "159.691",
        "closeTime": "2026-11-16T01:00:00.000000000Z",
    }
}


class _SleeveFakeAdapter:
    account_id = "acct-1"

    def __init__(self):
        self.fail_fetch = True
        self.record = None

    def get_account_summary(self):
        return {"equity": 10000.0, "margin_available": 10000.0, "margin_rate": 0.02}

    def open_trades(self):
        return []  # trade 470 is gone from the account -> close detected

    def _request(self, method, path, params=None):
        if "/trades/" in path:
            if self.fail_fetch:
                raise RuntimeError("transient broker failure")
            return self.record
        return {}


def _make_sleeve_runner(tmp_path, adapter):
    from oanda_demo.sleeve_runner import SleeveRunner

    state_file = tmp_path / "sleeve_state.json"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state_file.write_text(json.dumps({
        "day": today,
        "day_start_nav": 10000.0,
        "own_trades": {"470": dict(_TRADE_META)},
    }))
    (tmp_path / "sleeve_entries_paused").write_text("test pause")
    return SleeveRunner(
        adapter=adapter, dry_run=False,
        state_file=state_file, data_dir=tmp_path,
    ), state_file


def test_sleeve_booking_failure_keeps_trade_and_latches_alert(tmp_path):
    adapter = _SleeveFakeAdapter()  # fetch raises
    runner, state_file = _make_sleeve_runner(tmp_path, adapter)

    out = runner.run_once()

    assert out.get("closes_unbooked") == ["470"]
    state = json.loads(state_file.read_text())
    assert "470" in state["own_trades"], "failed booking must keep the trade for retry"
    assert fill_ledger.read_fills() == []
    assert "unrecorded_close" in fill_ledger.active_alerts()


def test_sleeve_booking_retry_succeeds_next_scan(tmp_path):
    adapter = _SleeveFakeAdapter()
    runner, state_file = _make_sleeve_runner(tmp_path, adapter)

    runner.run_once()  # fails, trade kept
    assert "470" in json.loads(state_file.read_text())["own_trades"]

    adapter.fail_fetch = False
    adapter.record = _CLOSED_RECORD
    out = runner.run_once()  # retry succeeds

    assert out.get("closes") == ["470"]
    state = json.loads(state_file.read_text())
    assert state["own_trades"] == {}
    rows = fill_ledger.read_fills()
    assert len(rows) == 1
    row = rows[0]
    assert row["strategy"] == "strategy_sleeve_tsmom2_dual"
    assert row["sleeve"] == "best_per_class"
    assert row["engine"] == "oanda_sleeve"
    assert row["order_id"] == "470"
    assert row["net_pnl"] == pytest.approx(1.23)


def test_sleeve_unclosed_broker_record_is_not_booked(tmp_path):
    adapter = _SleeveFakeAdapter()
    adapter.fail_fetch = False
    adapter.record = {"trade": {"id": "470", "state": "OPEN"}}
    runner, state_file = _make_sleeve_runner(tmp_path, adapter)

    runner.run_once()

    assert "470" in json.loads(state_file.read_text())["own_trades"]
    assert fill_ledger.read_fills() == []
    assert "unrecorded_close" in fill_ledger.active_alerts()


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


# ---------------------------------------------------------------------------
# 4. OANDA adapter: SL/TP from the linked order records
# ---------------------------------------------------------------------------

def _adapter_with_payload(payload):
    from exchanges.oanda_adapter import OandaExchangeAdapter

    adapter = OandaExchangeAdapter(api_key="x", account_id="acc", practice=True)
    adapter._request = lambda method, path, params=None, json=None: payload
    return adapter


def _trade(**overrides):
    base = {
        "id": "470",
        "instrument": "USD_JPY",
        "currentUnits": "15",
        "price": "159.691",
        "unrealizedPL": "0.0069",
        "openTime": "2026-11-15T22:09:05.810Z",
        "financing": "0",
        "stopLoss": None,
        "takeProfit": None,
    }
    base.update(overrides)
    return base


def test_open_trades_reads_linked_sl_tp_orders():
    payload = {"trades": [_trade(
        stopLossOrder={"id": "472", "price": "157.543",
                       "state": "PENDING", "timeInForce": "GTC"},
        takeProfitOrder={"id": "471", "price": "163.838",
                         "state": "PENDING", "timeInForce": "GTC"},
    )]}
    trades = _adapter_with_payload(payload).open_trades()
    assert len(trades) == 1
    assert trades[0]["stop_loss"] == pytest.approx(157.543)
    assert trades[0]["take_profit"] == pytest.approx(163.838)


def test_open_trades_cancelled_sl_order_is_not_protection():
    payload = {"trades": [_trade(
        stopLossOrder={"id": "472", "price": "157.543", "state": "CANCELLED"},
    )]}
    trades = _adapter_with_payload(payload).open_trades()
    assert trades[0]["stop_loss"] == 0.0
    assert trades[0]["take_profit"] == 0.0


def test_open_trades_legacy_fields_still_parse():
    payload = {"trades": [_trade(
        stopLoss={"price": "157.543"}, takeProfit={"price": "163.838"},
    )]}
    trades = _adapter_with_payload(payload).open_trades()
    assert trades[0]["stop_loss"] == pytest.approx(157.543)
    assert trades[0]["take_profit"] == pytest.approx(163.838)


def test_open_trades_without_orders_reports_zero():
    trades = _adapter_with_payload({"trades": [_trade()]}).open_trades()
    assert trades[0]["stop_loss"] == 0.0
    assert trades[0]["take_profit"] == 0.0
