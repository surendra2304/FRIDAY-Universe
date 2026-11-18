"""strategy_rsi_momentum_forex — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (thin variant of strategy_rsi_momentum, OANDA panel).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 78): rsi_momentum /
rsi14_55_45 @ FOREX28 1d — 344 pooled OOS trades, +0.089%/trade,
PF 1.0761, win rate 0.3721, 2/5 positive folds. Second tier met
(expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni);
the full frozen bar was NOT passed — not a promotion, not VALIDATED.

Governance: FORWARD_TEST with forward_venues ["oanda_practice"] —
the registry entry is discoverable by the governed OANDA runner;
execution rides that runner (a separate PR), NOT the Binance daemon.
Phase-3 forward protocol terms and FORWARD_TEST fill tagging as for
the canonical core module (strategy_rsi_momentum). The signal is the
judged families3.sig_rsi_momentum(df, 14, 55.0, 45.0, warmup) with
the judged BR24 bracket (SL 2.0 x ATR(14), TP 4.0 x ATR(14)),
evaluated through the core module's parameterised helpers bound to
this variant's own CFG dict (RSI_MOMENTUM_FOREX_STRATEGY). Judged
cost basis: RD-002 costs2.py forex — 6 bps round trip majors,
10 bps minors/crosses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_rsi_momentum as _core

try:
    from config_strategy import RSI_MOMENTUM_FOREX_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {"RSI_PERIOD": 14, "RSI_HI": 55.0, "RSI_LO": 45.0, "OOS_WIN_RATE": 0.3721}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3721))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR

atr14 = _core.atr14


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return _core.signal_masks_cfg(df, _CFG)


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    return _core.entries_for_frame_cfg(df, _CFG, warmup)


def _closed_frame(df, now_s=None):
    return _core._closed_frame(df, BAR_SECONDS, now_s)


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    return _core.get_signal_cfg(df, _CFG, BAR_SECONDS)
