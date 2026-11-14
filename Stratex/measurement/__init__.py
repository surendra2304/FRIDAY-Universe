"""
measurement — Stratex profitability measurement layer (TASK-STR-PHASE2-001).

Phase 1 of the profitability programme proved Stratex could not state its
own demo-trading results honestly: closes went unrecorded, no equity curve
existed, fees were partly fee-blind estimates, and per-strategy attribution
was missing. This package is the measurement infrastructure that fixes
that, shared by both engines (testnet engine + multi-venue daemon):

  * fill_ledger.py — append-only, strategy-tagged record of every closed
    trade, append-only equity snapshots, position ownership tags, and the
    reconciliation alert state.
  * shadow.py      — shadow-trade lifecycle for OBSERVE_ONLY strategies
    (would-be entries/exits, fees ESTIMATED and labelled as such).
  * scorecard.py   — per-strategy scorecard computed ONLY from the fill
    ledger (trades, win rate, expectancy net of fees, profit factor,
    attributed drawdown).

Everything here is bookkeeping: it never places, sizes, or blocks an
order. Demo/testnet only, like the rest of Stratex's governed execution.
"""
