"""
tests/test_oanda_forward_activation.py — TASK-STR-FWD-004.

OANDA venue activation under the phase-3 measurement protocol:

  * governance — the OANDA engine may open entries ONLY when its
    configured strategy is a VALIDATED forward-protocol entrant in
    config_strategy.PRODUCTION_STRATEGY_REGISTRY for the OANDA practice
    venue; every other configuration fails closed, even with the manual
    entries pause lifted. The manual pause stays authoritative.
  * measurement — opens are position-tagged in the shared Phase-2 store
    and closes are booked into the fill ledger from the broker's
    closed-trade record (realized PL); an unbookable close is queued
    for retry with the measurement alert latched, never dropped.
  * forward guard — measurement/forward_guard.py kill criteria are
    evaluated on the scan cadence; a breach re-creates the persisted
    entries-pause file (auto-pause).

No network: the trader is driven through a fake adapter and the real
adapter through a stubbed _request.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import config_strategy
import oanda_demo.trader as trader_mod
from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.strategy import (
    DonchianTrendStrategy,
    MeanReversionStrategy,
)
from oanda_demo.trader import OandaDemoTrader, governance_status


# ---------------------------------------------------------------------------
# Fixtures / fakes
# ---------------------------------------------------------------------------

def reverting_df(n: int = 482, drop: float = 0.020, rise: float = 0.030,
                 cycle: int = 20, rng: float = 0.0002) -> pd.DataFrame:
    """Same D1 mean-reversion shape as tests/test_oanda_demo.py: at
    n=482 the last bar is the second dip bar, so FX-MR-v4 fires LONG."""
    drop_bars = 2
    closes = []
    level = 1.0
    for i in range(n):
        k = i % cycle
        if k < drop_bars:
            level -= drop / drop_bars
        else:
            level += rise / (cycle - drop_bars)
        closes.append(level)
    arr = np.array(closes)
    return pd.DataFrame({
        "timestamp": np.arange(n),
        "open": np.concatenate([[arr[0]], arr[:-1]]),
        "high": arr + rng, "low": arr - rng, "close": arr,
        "volume": np.full(n, 100),
    })


def flat_df(n: int = 300) -> pd.DataFrame:
    close = np.full(n, 1.1000)
    return pd.DataFrame({
        "timestamp": np.arange(n),
        "open": close, "high": close + 0.0002, "low": close - 0.0002,
        "close": close, "volume": np.full(n, 100),
    })


class FakeOandaAdapter:
    """Stateful adapter double: orders open trades, trades can close."""

    def __init__(self, candles, equity=10000.0):
        self.candles = candles
        self.equity = equity
        self.trades = []
        self.orders = []
        self.closed_records = {}   # trade_id -> dict | None
        self._next_id = 100

    def get_account_summary(self):
        return {"equity": self.equity, "balance": self.equity,
                "margin_available": self.equity, "unrealized_pl": 0.0}

    def open_trades(self):
        return list(self.trades)

    def get_pricing(self, symbols):
        return {s: {"mid": 1.1000, "bid": 1.0999, "ask": 1.1001,
                    "spread": 0.0002} for s in symbols}

    def get_historical_data(self, symbol, timeframe, limit):
        return self.candles.tail(limit).to_dict("records")

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self._next_id += 1
        tid = str(self._next_id)
        self.orders.append((symbol, side, order_type, quantity, kw))
        self.trades.append({
            "id": tid, "instrument": symbol,
            "units": quantity if side == "BUY" else -quantity,
            "price": 1.1000, "unrealized_pl": 0.0, "open_time": "",
            "stop_loss": kw.get("stop_loss") or 0.0, "take_profit": 0.0,
        })
        return SimpleNamespace(order_id=f"ord-{tid}", trade_id=tid,
                               price=1.1000, status="FILLED")

    def close_trade(self, trade_id, units=None):
        self.trades = [t for t in self.trades if t["id"] != trade_id]
        return True

    def get_closed_trade(self, trade_id):
        return self.closed_records.get(trade_id)

    def update_trade_stop_loss(self, symbol, trade_id, price):
        return True


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Hermetic trader environment: all state/ledger files in tmp."""
    monkeypatch.setattr(trader_mod, "KILL_SWITCH", tmp_path / "kill")
    monkeypatch.setattr(trader_mod, "ENTRIES_PAUSED_FILE", tmp_path / "paused")
    monkeypatch.setattr(trader_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(trader_mod, "TRADES_CSV", tmp_path / "trades.csv")
    monkeypatch.delenv("STRATEX_OANDA_ENTRIES_PAUSED", raising=False)
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def _trader(tmp_path, adapter, strategy=None):
    return OandaDemoTrader(
        adapter=adapter,
        strategy=strategy or MeanReversionStrategy(),
        dry_run=False,
        state_file=tmp_path / "oanda_state.json",
    )


def _ledger_rows(tmp_path, name):
    path = tmp_path / "state" / name
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Governance (unit)
# ---------------------------------------------------------------------------

class TestGovernanceStatus:
    def test_mr_is_governed_under_the_real_registry(self):
        gov = governance_status(MeanReversionStrategy())
        assert gov["registry_key"] == "fx_mr_v4"
        assert gov["governed"] is True

    def test_donchian_is_unregistered_and_blocked(self):
        gov = governance_status(DonchianTrendStrategy())
        assert gov["governed"] is False
        assert "UNREGISTERED" in gov["reason"]

    def test_unknown_strategy_object_blocked(self):
        gov = governance_status(SimpleNamespace(name="Whatever-v9"))
        assert gov["governed"] is False

    def test_missing_entry_blocked(self):
        gov = governance_status(MeanReversionStrategy(), registry={})
        assert gov["governed"] is False

    def test_observe_only_blocked(self):
        reg = {"fx_mr_v4": {"status": "OBSERVE_ONLY", "forward_protocol": True}}
        assert governance_status(MeanReversionStrategy(), registry=reg)["governed"] is False

    def test_not_forward_protocol_blocked(self):
        reg = {"fx_mr_v4": {"status": "VALIDATED", "forward_protocol": False}}
        assert governance_status(MeanReversionStrategy(), registry=reg)["governed"] is False

    def test_wrong_venue_blocked(self):
        reg = {"fx_mr_v4": {"status": "VALIDATED", "forward_protocol": True,
                            "venue": "binance_futures"}}
        assert governance_status(MeanReversionStrategy(), registry=reg)["governed"] is False


# ---------------------------------------------------------------------------
# Governance gate (trader integration)
# ---------------------------------------------------------------------------

class TestGovernanceGate:
    def test_ungoverned_strategy_opens_nothing(self, env):
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter, strategy=DonchianTrendStrategy())
        summary = t.run_once()
        assert adapter.orders == []
        assert summary["governance"]["governed"] is False
        assert summary["entries_blocked"].startswith("governance:")

    def test_registry_status_flip_blocks_the_incumbent(self, env, monkeypatch):
        monkeypatch.setitem(
            config_strategy.PRODUCTION_STRATEGY_REGISTRY["fx_mr_v4"],
            "status", "OBSERVE_ONLY",
        )
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert adapter.orders == []
        assert summary["entries_blocked"].startswith("governance:")

    def test_manual_pause_stays_authoritative_for_governed(self, env):
        (env / "paused").touch()
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert adapter.orders == []
        assert summary["entries_paused"] is True

    def test_governed_strategy_may_open(self, env):
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert adapter.orders, "governed FX-MR-v4 must be able to enter"
        assert summary["governance"]["governed"] is True
        assert "entries_blocked" not in summary
        assert "entries_paused" not in summary


# ---------------------------------------------------------------------------
# Ledger lifecycle: open tag -> close fill
# ---------------------------------------------------------------------------

class TestLedgerLifecycle:
    def test_open_tag_then_broker_close_books_fill(self, env):
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        t.run_once()
        assert adapter.orders
        tags = _ledger_rows(env, "position_tags.jsonl")
        assert tags and all(r["strategy"] == "fx_mr_v4" for r in tags)
        assert all(r["engine"] == "oanda_demo" for r in tags)
        assert all(r["venue"] == "oanda_practice" for r in tags)

        # Protect one trade from engine management (far-future open
        # time -> no rule/time exit evaluation), then close it at the
        # broker as an SL/TP-style close.
        trade = adapter.trades[0]
        trade["open_time"] = "2999-01-01T00:00:00.000000Z"
        tid = trade["id"]
        adapter.trades = [x for x in adapter.trades if x["id"] != tid]
        adapter.closed_records[tid] = {
            "id": tid, "instrument": trade["instrument"],
            "units": trade["units"], "entry_price": 1.1000,
            "exit_price": 1.0950, "realized_pl": -10.25,
            "open_time": "", "close_time": "2026-11-15T06:00:00.000000Z",
        }
        summary = t.run_once()
        fills = _ledger_rows(env, "fill_ledger.jsonl")
        mine = [r for r in fills if r["order_id"] == tid]
        assert len(mine) == 1
        row = mine[0]
        assert row["strategy"] == "fx_mr_v4"
        assert row["engine"] == "oanda_demo"
        assert row["venue"] == "oanda_practice"
        assert row["net_pnl"] == -10.25
        assert row["gross_pnl"] == -10.25
        assert row["fees_source"] == "broker"
        assert row["exit_reason"] == "BROKER_CLOSE"
        assert tid in summary.get("ledger_fills", [])

        # A later scan must not double-book the same close.
        t.run_once()
        fills = _ledger_rows(env, "fill_ledger.jsonl")
        assert len([r for r in fills if r["order_id"] == tid]) == 1

    def test_engine_time_exit_reason_reaches_the_fill(self, env):
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        t.run_once()
        trade = adapter.trades[0]
        tid = trade["id"]
        # Scan 2: open_time "" -> held bars >> max_hold -> engine TIME
        # exit closes it and remembers the reason in state.
        summary2 = t.run_once()
        assert tid in summary2.get("rule_exits", [])
        adapter.closed_records[tid] = {
            "id": tid, "instrument": trade["instrument"],
            "units": trade["units"], "entry_price": 1.1000,
            "exit_price": 1.1010, "realized_pl": 2.50,
            "open_time": "", "close_time": "2026-11-15T06:05:00.000000Z",
        }
        # Scan 3: the disappearance is detected and booked.
        t.run_once()
        fills = _ledger_rows(env, "fill_ledger.jsonl")
        mine = [r for r in fills if r["order_id"] == tid]
        assert len(mine) == 1
        assert mine[0]["exit_reason"] == "TIME_EXIT"
        assert mine[0]["net_pnl"] == 2.50

    def test_unbookable_close_is_queued_alerted_then_booked(self, env):
        adapter = FakeOandaAdapter(reverting_df())
        t = _trader(env, adapter)
        t.run_once()
        trade = adapter.trades[0]
        trade["open_time"] = "2999-01-01T00:00:00.000000Z"
        tid = trade["id"]
        adapter.trades = [x for x in adapter.trades if x["id"] != tid]
        # Broker record unavailable on the detecting scan.
        t.run_once()
        state = json.loads((env / "oanda_state.json").read_text())
        assert tid in state.get("unrecorded_closes", [])
        alerts = json.loads((env / "state" / "measurement_alerts.json").read_text())
        assert alerts["alerts"]["unrecorded_close"]["active"] is True
        assert _ledger_rows(env, "fill_ledger.jsonl") == []
        # Record appears -> next scan books it and drains the queue.
        adapter.closed_records[tid] = {
            "id": tid, "instrument": trade["instrument"],
            "units": trade["units"], "entry_price": 1.1000,
            "exit_price": 1.1030, "realized_pl": 6.00,
            "open_time": "", "close_time": "2026-11-15T06:10:00.000000Z",
        }
        t.run_once()
        state = json.loads((env / "oanda_state.json").read_text())
        assert tid not in state.get("unrecorded_closes", [])
        fills = _ledger_rows(env, "fill_ledger.jsonl")
        assert len([r for r in fills if r["order_id"] == tid]) == 1


# ---------------------------------------------------------------------------
# Forward guard (kill criteria -> persisted auto-pause)
# ---------------------------------------------------------------------------

def _seed_fill(tmp_path, net, exit_time):
    from measurement import fill_ledger

    return fill_ledger.append_fill({
        "strategy": "fx_mr_v4", "engine": "oanda_demo",
        "venue": "oanda_practice", "symbol": "EURUSD", "side": "LONG",
        "entry_price": 1.1000, "exit_price": 1.0990, "qty": 1000,
        "gross_pnl": net, "fees": 0.0, "fees_source": "broker",
        "net_pnl": net, "exit_reason": "TEST",
        "entry_time": exit_time - 3600, "exit_time": exit_time,
        "order_id": f"seed-{exit_time}",
    })


class TestForwardGuard:
    def test_fifty_losing_trades_auto_pause(self, env):
        for i in range(50):
            assert _seed_fill(env, -1.0, 1_700_000_000 + i * 60) is not None
        adapter = FakeOandaAdapter(flat_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert summary["forward_guard"][0]["breached"] is True
        assert summary["forward_guard_auto_paused"] is True
        assert (env / "paused").exists()
        assert t.status()["entries_paused"] is True

    def test_drawdown_breach_alone_auto_pauses(self, env):
        # One -600 trade: DD $600 > 5% of the $10,000 account.
        assert _seed_fill(env, -600.0, 1_700_000_000) is not None
        adapter = FakeOandaAdapter(flat_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert summary["forward_guard"][0]["breached"] is True
        assert (env / "paused").exists()

    def test_healthy_ledger_never_pauses(self, env):
        for i in range(10):
            assert _seed_fill(env, 2.0, 1_700_000_000 + i * 60) is not None
        adapter = FakeOandaAdapter(flat_df())
        t = _trader(env, adapter)
        summary = t.run_once()
        assert summary["forward_guard"][0]["breached"] is False
        assert not (env / "paused").exists()


# ---------------------------------------------------------------------------
# Adapter: closed-trade record
# ---------------------------------------------------------------------------

class TestClosedTradeAdapter:
    def _adapter(self, payload):
        adapter = OandaExchangeAdapter(
            api_key="k", account_id="101-001-1-001", practice=True
        )
        adapter._request = lambda method, endpoint, **kw: payload
        return adapter

    def test_closed_trade_parsed(self):
        adapter = self._adapter({"trade": {
            "id": "555", "instrument": "EUR_USD", "initialUnits": "2000",
            "price": "1.10000", "state": "CLOSED",
            "averageClosePrice": "1.10500", "realizedPL": "10.00",
            "openTime": "2026-11-15T00:00:00.000000Z",
            "closeTime": "2026-11-15T06:00:00.000000Z",
        }})
        out = adapter.get_closed_trade("555")
        assert out["instrument"] == "EURUSD"
        assert out["units"] == 2000.0
        assert out["entry_price"] == 1.1000
        assert out["exit_price"] == 1.1050
        assert out["realized_pl"] == 10.00

    def test_open_trade_returns_none(self):
        adapter = self._adapter({"trade": {"id": "556", "state": "OPEN"}})
        assert adapter.get_closed_trade("556") is None

    def test_missing_trade_returns_none(self):
        adapter = self._adapter(None)
        assert adapter.get_closed_trade("557") is None
