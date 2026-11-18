"""strategy_donchian_turtle_n20_trail — TASK-STR-FWD-019 FORWARD-TEST lane entrant (thin variant).

Judged configuration (TASK-STR-RD-002, near-miss second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle / n20_trail @ CRYPTO30 1d — 677 pooled OOS trades, +1.087%/trade, PF 1.1968, 3/5 positive folds, PF @2x costs 1.1647 (audit S1.4 row 20). Identical trade stream to turtle2/n20_trail 1d (row 21, dup) — wired ONCE here. Judged exit spec TRAIL (SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed TP): tp_dist=None; daemon trailing-exit limitation in the registry reason.

Governance: registered FORWARD_TEST in config_strategy.py — DEMO
venues only, phase-3 forward protocol, fills tagged FORWARD_TEST.
Not a promotion, not VALIDATED (Bonferroni FAIL at programme
N=3,899). Thin variant module: the signal logic lives in the family
core (strategy_donchian_turtle.py, a line-faithful port of the judged rd2 harness
function); this module binds the variant's own judged CFG dict
(DONCHIAN_TURTLE_N20_TRAIL_STRATEGY) and exposes the daemon contract independently.
Equivalence is pinned by tests/test_fwd019_donchian_turtle_lane.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_donchian_turtle as _core

try:
    from config_strategy import DONCHIAN_TURTLE_N20_TRAIL_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", _core.TIMEFRAME))
BAR_SECONDS = _core._bar_seconds(_CFG)
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.0))
_TP = _CFG.get("TP_ATR")
RR_RATIO = (float(_TP) / float(_CFG.get("SL_ATR", 2.0))) if _TP else None

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


def signal_masks(df: pd.DataFrame):
    return _core.signal_masks_cfg(df, _CFG)


def entries_for_frame(df: pd.DataFrame, warmup: int = WARMUP_BARS) -> List[Tuple[int, str]]:
    return _core.entries_for_frame_cfg(df, _CFG, warmup)


def _closed_frame(df: pd.DataFrame, now_s=None):
    return _core._closed_frame(df, BAR_SECONDS, now_s)


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    return _core.get_signal_cfg(df, _CFG)
