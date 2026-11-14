"""
tests/test_oanda_entries_pause.py — TASK-STR-PHASE2-001, SMT-v2 pause.

The OANDA demo engine's exchange-verified record is 19 trades, -$167,
negative on every instrument. The phase-2 entries pause must:
  * keep the scan cycle running (account read, trade management, state),
  * open NO new trades while active (env flag OR pause file),
  * be fully reversible (removing both resumes normal scanning),
  * never be confused with the kill switch (which halts the whole scan).
"""

import pytest

import oanda_demo.trader as trader_mod
from oanda_demo.trader import OandaDemoTrader


class _FakeAdapter:
    def __init__(self):
        self.orders = []

    def get_account_summary(self):
        return {"equity": 99833.0, "balance": 99833.0, "margin_available": 90000.0}

    def open_trades(self):
        return []

    def get_pricing(self, symbols):
        return {s: {"mid": 1.1000, "bid": 1.0999, "ask": 1.1001, "spread": 0.0002}
                for s in symbols}

    def get_historical_data(self, symbol, timeframe, limit):
        return []  # no candles -> no signals in the unpaused path either

    def place_order(self, *args, **kwargs):
        self.orders.append((args, kwargs))
        raise AssertionError("place_order must not be called in these tests")


@pytest.fixture()
def trader(tmp_path, monkeypatch):
    monkeypatch.setattr(trader_mod, "KILL_SWITCH", tmp_path / "kill")
    monkeypatch.setattr(trader_mod, "ENTRIES_PAUSED_FILE", tmp_path / "paused")
    monkeypatch.setattr(trader_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(trader_mod, "TRADES_CSV", tmp_path / "trades.csv")
    monkeypatch.delenv("STRATEX_OANDA_ENTRIES_PAUSED", raising=False)
    adapter = _FakeAdapter()
    t = OandaDemoTrader(adapter=adapter, state_file=tmp_path / "state.json")
    return t, adapter, tmp_path


def test_pause_file_blocks_entries_but_scan_runs(trader):
    t, adapter, tmp_path = trader
    (tmp_path / "paused").touch()
    summary = t.run_once()
    assert summary.get("entries_paused") is True
    assert summary.get("equity") == 99833.0  # account was still read
    assert adapter.orders == []
    assert t.status()["entries_paused"] is True


def test_env_flag_blocks_entries(trader, monkeypatch):
    t, adapter, _ = trader
    monkeypatch.setenv("STRATEX_OANDA_ENTRIES_PAUSED", "1")
    summary = t.run_once()
    assert summary.get("entries_paused") is True
    assert adapter.orders == []


def test_unpaused_scan_has_no_pause_flag(trader):
    t, adapter, _ = trader
    summary = t.run_once()
    assert "entries_paused" not in summary
    assert summary.get("equity") == 99833.0
    assert t.status()["entries_paused"] is False


def test_pause_is_reversible(trader):
    t, adapter, tmp_path = trader
    (tmp_path / "paused").touch()
    assert t.run_once().get("entries_paused") is True
    (tmp_path / "paused").unlink()
    assert "entries_paused" not in t.run_once()


def test_kill_switch_still_halts_everything(trader):
    t, adapter, tmp_path = trader
    (tmp_path / "kill").touch()
    summary = t.run_once()
    assert summary.get("halted") == "kill switch present"
    assert "equity" not in summary  # scan never ran — distinct from pause
