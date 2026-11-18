"""strategy_mtf_confluence_1d — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (thin variant of strategy_mtf_confluence, 1d cell).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 24): mtf_confluence /
h4_native_ema200 @ CRYPTO30 1d — 217 pooled OOS trades,
+1.472%/trade, PF 1.1902, win rate 0.3779, 2/5 positive folds,
PF @2x costs 1.1679. Second tier met (expectancy > 0, PF >= 1.05,
>= 200 OOS trades, pre-Bonferroni); the full frozen bar was NOT
passed — not a promotion, not VALIDATED.

FAITHFULNESS (checked first, per the wave-2 slice): this 1d cell is
wired at its JUDGED construction, not re-judged on 1d bars. The
judged h4_native_ema200 fn (families2.py) ignores the aux frame and
sig_mtf_native computes EMA(20)/EMA(50)/EMA(200) on the cell's own
series; rd2/grid.py supplies an aux panel only for 15m/1h cells.
The judged 1d cell therefore ran sig_mtf_native on 1d bars — which
is exactly what this module does (TIMEFRAME 1d, BAR_SECONDS 86400,
same helpers as the 4h core). Full evidence in the core module's
docstring and the PR body.

Governance as for the core: FORWARD_TEST, demo venues only,
phase-3 forward protocol, fills tagged FORWARD_TEST. Bracket BR24
(SL 2.0 x ATR(14), TP 4.0 x ATR(14)), warmup 260, via the core's
parameterised helpers bound to MTF_CONFLUENCE_1D_STRATEGY.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_mtf_confluence as _core

try:
    from config_strategy import MTF_CONFLUENCE_1D_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {"TIMEFRAME": "1d", "OOS_WIN_RATE": 0.3779}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3779))
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
