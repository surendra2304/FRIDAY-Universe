"""strategy_stoch_reversion_k14_filt — TASK-STR-FWD-019 FORWARD-TEST
lane entrant (thin variant of strategy_stoch_reversion, OANDA panel).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 88): stoch_reversion /
k14_filt @ FOREX28 1d — 216 pooled OOS trades, +0.072%/trade,
PF 1.0613, win rate 0.3519, 2/5 positive folds. Second tier met
(expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni);
the full frozen bar was NOT passed — not a promotion, not VALIDATED.

Governance as for the canonical core (strategy_stoch_reversion):
FORWARD_TEST with forward_venues ["oanda_practice"], phase-3
forward protocol, fills tagged FORWARD_TEST; execution rides the
governed OANDA runner (separate PR). The signal is the judged
families3.sig_stoch(df, filtered=True, warmup) — %K(14) SMA(3)
crosses, additionally gated by close vs EMA(200) — with the judged
BR24 bracket (SL 2.0 x ATR(14), TP 4.0 x ATR(14)), evaluated through
the core module's parameterised helpers bound to this variant's own
CFG dict (STOCH_REVERSION_K14_FILT_STRATEGY).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_stoch_reversion as _core

try:
    from config_strategy import STOCH_REVERSION_K14_FILT_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {"FILTERED": True, "OOS_WIN_RATE": 0.3519}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3519))
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
