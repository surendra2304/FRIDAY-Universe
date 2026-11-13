"""
oanda_demo — OANDA demo (practice-account) trading for the Stratex agent.

Owner directive (2026-11-13):
  1. Store the OANDA demo API key in credentials.md.
  2. Implement OANDA demo trading.
  3. Make Stratex take profitable trades (risk-first, trend-following).

Modules:
  credentials.py — credential loader (env first, then credentials.md master copy)
  strategy.py    — SMT-v2 (Stratex Momentum-Trend v2) signal engine
  trader.py      — live trading engine (scan / size / execute / manage)
  backtest.py    — historical validation on real OANDA candles
  selftest.py    — live API verification incl. 1-unit order round-trip

All trading happens on the OANDA *practice* environment (demo funds).
The live environment (api-fxtrade.oanda.com) is NEVER used without
explicit owner approval (Surendra Varma Jalli).
"""

__version__ = "1.0.0"
