"""Stratex rigorous backtesting harness (TASK-STR-BT-001).

Design rules (non-negotiable):
- Real exchange data only, provenance-recorded and hash-verified. Any fetch
  or integrity failure is a hard error: a strategy/market becomes UNTESTABLE.
  Nothing in this package generates, interpolates or substitutes candle data.
- Reported performance is out-of-sample only (walk-forward). Parameters are
  selected exclusively on in-sample folds.
- All figures are net of a stated cost model (fees + spread + slippage).
- This package is research-only. It imports production strategy modules
  read-only and never writes to production code, config or governance.
"""
