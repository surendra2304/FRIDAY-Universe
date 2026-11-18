"""strategy_vol_regime_trend_ema12_48_gate_lo — TASK-STR-FWD-019
FORWARD-TEST lane entrant (thin variant of strategy_vol_regime_trend).

Judged configuration (TASK-STR-RD-004, vol_regime_trend family):
ema12_48_gate_lo @ CRYPTO30 2h — 3,471 pooled OOS trades,
+0.107%/trade, PF 1.0550, win rate 0.3598, 2/5 positive folds
(results_rd4/synthesis.json ``configs``). It meets the owner's
second tier but did NOT pass the full frozen bar — not a promotion,
not VALIDATED.

Signal: EMA(12)/EMA(48) cross gated by the RD-004 low-volatility
regime gate (R(d) < 0.50), bracket SL 2.0 x ATR(14) / TP 4.0 x
ATR(14), warmup 260 bars — all machinery lives in the core module
strategy_vol_regime_trend.py (line-faithful port of
rigorous_backtest/rd4/families_rd4.py); this module only binds the
ema12_48_gate_lo CFG. Governance: FORWARD_TEST, demo venues only,
fills tagged FORWARD_TEST, never blended with VALIDATED scorecards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_vol_regime_trend as _core

try:
    from config_strategy import (
        VOL_REGIME_TREND_EMA12_48_GATE_LO_STRATEGY as _CFG,
    )
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "2h"))
BAR_SECONDS = _core.BAR_SECONDS
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3598))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR

atr14 = _core.atr14
regime_rank_by_bar = _core.regime_rank_by_bar
base_signal_masks = _core.base_signal_masks
_closed_frame = _core._closed_frame


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return _core.signal_masks_cfg(df, _CFG)


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    return _core.entries_for_frame_cfg(df, _CFG, warmup)


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 2h bar; return the daemon signal dict."""
    return _core.get_signal_cfg(df, _CFG)
