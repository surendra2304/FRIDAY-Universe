"""
oanda_demo — OANDA demo (practice-account) trading for the Stratex agent.

Owner directive (2026-11-13):
  1. Store the OANDA demo API key in credentials.md.
  2. Implement OANDA demo trading.
  3. Make Stratex take profitable trades (risk-first, trend-following).

Modules:
  credentials.py — credential loader (env first, then credentials.md master copy)
  strategy.py    — signal engines: Donchian-v3 (breakout + chandelier
                   trail) and FX-MR-v4 (RSI-2 mean reversion, the
                   deployed default)
  trader.py      — live trading engine (scan / size / execute / manage)
  backtest.py    — historical validation on real OANDA candles
  selftest.py    — live API verification incl. 1-unit order round-trip

SMT-v2 (the original EMA-stack engine) was deleted on 2026-11-15 by
TASK-STR-CLEANUP-002 under the owner's strict removal rule (verified
OOS profit factor < 1.2 -> delete completely): its TASK-STR-RD-002
retest measured PF 0.655 over 627 OOS trades.

All trading happens on the OANDA *practice* environment (demo funds).
The live environment (api-fxtrade.oanda.com) is NEVER used without
explicit owner approval (Surendra Varma Jalli).
"""

__version__ = "1.0.0"
