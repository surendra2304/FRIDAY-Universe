"""strategy_vol_compression_squeeze_raw — TASK-STR-FWD-019
FORWARD-TEST lane entrant (thin variant of strategy_vol_compression).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 94): vol_compression /
squeeze_raw @ CRYPTO30 1h — 1,926 pooled OOS trades, +0.076%/trade,
PF 1.0502, win rate 0.3655, 3/5 positive folds. Second tier met
(expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni);
the full frozen bar was NOT passed — not a promotion, not VALIDATED.

Governance and live contract as for the canonical core module
(strategy_vol_compression): FORWARD_TEST, demo venues only,
phase-3 forward protocol, fills tagged FORWARD_TEST. The signal is
the judged families3.sig_vol_compression(df, filtered=False,
warmup) — squeeze breakout with NO EMA(200) gate — with the judged
BR24 bracket (SL 2.0 x ATR(14), TP 4.0 x ATR(14)), evaluated
through the core module's parameterised helpers bound to this
variant's own CFG dict (VOL_COMPRESSION_SQUEEZE_RAW_STRATEGY).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_vol_compression as _core

try:
    from config_strategy import VOL_COMPRESSION_SQUEEZE_RAW_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {"FILTERED": False, "OOS_WIN_RATE": 0.3655}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1h"))
BAR_SECONDS = 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3655))
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
