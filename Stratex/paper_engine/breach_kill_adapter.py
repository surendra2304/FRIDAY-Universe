"""Breach -> kill-switch adapter — TASK-STR-083, Leg 1.

Wires the RiskGovernor breach callback (TASK-IG2-STR-16) to the
paper-engine kill switch (paper_engine/kill_switch.py), so a
per-engine trade-count breach halts the session instead of only
latching the governor.

PLACEMENT (scope Q1, decided): this module lives in paper_engine,
the kill action's home — NOT in rigorous_backtest/ig. The governor
module must stay research-only (its test forbids production imports
inside risk_governor.py), so the wiring goes in a separate module on
the production side, and the governor only ever sees a plain callable
as its on_breach hook.

The adapter takes no live-daemon dependency: it calls
trigger_kill_switch with the portfolio and observed prices the caller
supplies. The breach drill (ig/tests/test_breach_kill_drill.py) runs
it against a synthetic portfolio in a temp dir — never the live
daemon, never a server.
"""
from __future__ import annotations

from paper_engine.kill_switch import trigger_kill_switch


def breach_reason(event: dict) -> str:
    """Human-readable kill-switch reason for a governor breach event.

    The event dict is the one RiskGovernor passes to on_breach:
    engine, kind, trades_taken, cap, rejected_risk_amount.
    """
    return (
        "RiskGovernor breach: engine={engine} kind={kind} "
        "trades_taken={trades_taken} cap={cap}".format(
            engine=event.get("engine"),
            kind=event.get("kind"),
            trades_taken=event.get("trades_taken"),
            cap=event.get("cap"),
        )
    )


class BreachKillSwitch:
    """on_breach handler that fires the paper-engine kill switch.

    portfolio: PaperPortfolio whose open positions are flattened on
    breach, or None (lock file only, no flattening).
    current_market_prices: {symbol: price} the kill switch exits at —
    observed prices only; a position with no usable price is left
    OPEN and reported, per the kill switch's own contract.
    cost_engine: optional CostEngine; defaults to the Binance taker
    config inside trigger_kill_switch.

    Pass ``handler.on_breach`` as RiskGovernor(on_breach=...). Every
    breach event fires the kill switch once; the governor's latch
    means each engine breaches at most once per session, so repeated
    attempts after a breach never re-fire. Summaries and events are
    kept for drill assertions and run reports.
    """

    def __init__(self, portfolio=None, current_market_prices=None,
                 cost_engine=None):
        self.portfolio = portfolio
        self.current_market_prices = dict(current_market_prices or {})
        self.cost_engine = cost_engine
        self.events = []
        self.summaries = []

    def on_breach(self, event: dict) -> dict:
        """Fire the kill switch for one breach event; return its summary."""
        reason = breach_reason(event)
        summary = trigger_kill_switch(
            reason,
            portfolio=self.portfolio,
            current_market_prices=self.current_market_prices,
            cost_engine=self.cost_engine,
        )
        self.events.append(event)
        self.summaries.append(summary)
        return summary
