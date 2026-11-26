"""Breach drill for TASK-STR-083, Leg 1.

Proves the RiskGovernor breach callback fires the paper-engine kill
switch: a per-engine trade-count breach writes the lock file, blocks
new signals, flattens the open positions with realistic costs, and
ledgers the forced exits KILL_SWITCH.

HERMETIC: everything lives under pytest's tmp_path — the synthetic
portfolio file, ledger, equity file, and the kill-switch lock file
(the module-level KILL_SWITCH_LOCK_FILE path is monkeypatched to the
temp dir for the test). No live daemon state, no server, no network.
Synthetic symbols/prices only; no real market data.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # Stratex/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # rigorous_backtest/

from paper_engine import kill_switch  # noqa: E402
from paper_engine.breach_kill_adapter import (  # noqa: E402
    BreachKillSwitch,
    breach_reason,
)
from paper_engine.portfolio import PaperPortfolio  # noqa: E402
from ig.risk_governor import RiskGovernor  # noqa: E402

EQ = 100_000.0


def _drill_setup(tmp_path, monkeypatch, cap=2):
    """Synthetic portfolio (2 open positions) + governor wired to the
    kill switch through the adapter. Returns (portfolio, switch,
    governor, lock_file)."""
    lock_file = tmp_path / "KILL_SWITCH_ACTIVE.lock"
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_LOCK_FILE", str(lock_file))
    portfolio = PaperPortfolio(
        filename=str(tmp_path / "portfolio.json"),
        ledger_file=str(tmp_path / "ledger.jsonl"),
        equity_file=str(tmp_path / "equity.jsonl"),
    )
    portfolio.add_position("pos-long", "BTCUSDT", "LONG", 100.0, 0.1)
    portfolio.add_position("pos-short", "ETHUSDT", "SHORT", 50.0, 0.2)
    prices = {"BTCUSDT": 101.0, "ETHUSDT": 49.0}
    switch = BreachKillSwitch(portfolio, prices)
    governor = RiskGovernor(EQ, max_trades_per_engine=cap,
                            on_breach=switch.on_breach)
    return portfolio, switch, governor, lock_file


def _ledger_rows(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(line) for line in
            ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_breach_reason_carries_engine_kind_and_cap():
    event = {"engine": "engine-a", "kind": "trade_count_cap",
             "trades_taken": 2, "cap": 2, "rejected_risk_amount": 10.0}
    reason = breach_reason(event)
    assert "engine-a" in reason
    assert "trade_count_cap" in reason
    assert "cap=2" in reason
    assert "trades_taken=2" in reason


def test_breach_fires_kill_switch_and_flattens_positions(tmp_path, monkeypatch):
    portfolio, switch, governor, lock_file = _drill_setup(tmp_path, monkeypatch)
    assert governor.approve_trade("engine-a", 10.0) is True
    assert governor.approve_trade("engine-a", 10.0) is True
    assert not lock_file.exists()
    assert len(switch.summaries) == 0

    # The breaching attempt: cap hit, engine latches, kill switch fires.
    assert governor.approve_trade("engine-a", 10.0) is False
    assert governor.is_blocked("engine-a") is True

    # 1. Lock file written — new signals blocked.
    assert lock_file.exists()
    assert kill_switch.is_kill_switch_active() is True
    # 2. Kill summary: both synthetic positions flattened, lock confirmed.
    assert len(switch.summaries) == 1
    summary = switch.summaries[0]
    assert summary["positions_closed"] == 2
    assert summary["positions_skipped"] == 0
    assert summary["lock_written"] is True
    assert summary["errors"] == []
    assert "trade_count_cap" in summary["reason"]
    assert all(p["status"] == "CLOSED"
               for p in portfolio.positions.values())
    # 3. Forced exits ledgered KILL_SWITCH (annotation rows carry the
    # breach reason; closed-trade rows carry the fills).
    rows = _ledger_rows(tmp_path)
    annotations = [r for r in rows
                   if r.get("type") == "KILL_SWITCH_ANNOTATION"]
    assert len(annotations) == 2
    assert {a["trade_id"] for a in annotations} == {"pos-long", "pos-short"}
    assert all("trade_count_cap" in a["reason"] for a in annotations)
    closed = [r for r in rows if r.get("status") == "CLOSED"]
    assert {r["trade_id"] for r in closed} == {"pos-long", "pos-short"}

    # Latched: further attempts are engine_blocked and never re-fire.
    assert governor.approve_trade("engine-a", 10.0) is False
    assert len(switch.summaries) == 1


def test_no_breach_means_no_kill_switch(tmp_path, monkeypatch):
    _portfolio, switch, governor, lock_file = _drill_setup(tmp_path, monkeypatch)
    assert governor.approve_trade("engine-a", 10.0) is True
    assert governor.approve_trade("engine-a", 10.0) is True
    assert not lock_file.exists()
    assert kill_switch.is_kill_switch_active() is False
    assert switch.summaries == []
    assert switch.events == []


def test_breach_without_portfolio_still_writes_lock(tmp_path, monkeypatch):
    lock_file = tmp_path / "KILL_SWITCH_ACTIVE.lock"
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_LOCK_FILE", str(lock_file))
    switch = BreachKillSwitch(portfolio=None, current_market_prices={})
    governor = RiskGovernor(EQ, max_trades_per_engine=1,
                            on_breach=switch.on_breach)
    assert governor.approve_trade("engine-a", 10.0) is True
    assert governor.approve_trade("engine-a", 10.0) is False
    assert lock_file.exists()
    assert len(switch.summaries) == 1
    assert switch.summaries[0]["positions_closed"] == 0
    assert switch.summaries[0]["lock_written"] is True
