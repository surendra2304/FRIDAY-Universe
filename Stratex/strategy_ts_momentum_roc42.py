"""strategy_ts_momentum_roc42 — TASK-STR-FWD-019 FORWARD-TEST lane entrant (thin variant).

Judged configuration (TASK-STR-RD-002, near-miss re-audit
~/workspace/str-nearmiss/REPORT.md §1.4 row 7): ts_momentum /
roc42 @ CRYPTO30 1d — 460 pooled OOS trades, +3.213%/trade,
PF 1.4354, win rate 0.4283, 4/5 positive folds, PF @2x costs 1.4088.
It meets the owner's second tier (expectancy > 0, PF >= 1.05, >= 200
OOS trades, judged before Bonferroni) but did NOT pass the full frozen
bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED.

Thin variant module: binds its own judged CFG dict
(config_strategy.TS_MOMENTUM_ROC42_STRATEGY) to the family's core helpers in
strategy_ts_momentum.py — a line-faithful port of the judged
implementation (rigorous_backtest/rd2/families2.py ``sig_ts_momentum``,
identical to RD-001's rd/stage3.py ``fam_ts_momentum``) and the judged
exit bracket (SL 2.0 x ATR(14), TP 4.0 x ATR(14), BR24).
Governance: FORWARD_TEST — DEMO venues only, phase-3 forward protocol
protections, fills tagged FORWARD_TEST; never blended with VALIDATED
scorecards. ``get_signal`` evaluates ONLY the last CLOSED bar.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_ts_momentum as _core

try:
    from config_strategy import TS_MOMENTUM_ROC42_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = _core._TF_BAR_SECONDS.get(TIMEFRAME, 24 * 3600)
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4283))


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return _core.signal_masks_cfg(df, _CFG)


def entries_for_frame(df: pd.DataFrame, warmup: int = WARMUP_BARS) -> List[Tuple[int, str]]:
    return _core.entries_for_frame_cfg(df, _CFG, warmup)


def _closed_frame(df: pd.DataFrame, now_s=None) -> pd.DataFrame:
    return _core._closed_frame(df, BAR_SECONDS, now_s)


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    return _core.get_signal_cfg(df, _CFG)
