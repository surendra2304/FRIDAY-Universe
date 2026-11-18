"""strategy_keltner_breakout_forex — TASK-STR-FWD-019 FORWARD-TEST lane entrant
(thin variant of strategy_keltner_breakout).

Judged configuration (TASK-STR-RD-002 near-miss, second tier per the
2026-11-18 audit ~/workspace/str-nearmiss/REPORT.md S1.4: OOS
expectancy > 0, PF >= 1.05, >= 200 OOS trades, judged BEFORE the
Bonferroni correction; it did NOT pass the full frozen bar —
Bonferroni at programme N=3,899 — so it is NOT promoted and NOT
VALIDATED; the owner directed 2026-11-18 that ALL actionable
near-miss candidates be forward-tested on demo):
keltner_breakout / ema20_m2.0 @ FOREX28 1d — 241 pooled OOS trades,
+0.137%/trade, PF 1.1273, win rate 0.3900, 3/5 positive folds.
OANDA entry: lane_assets FOREX28_SYMBOLS with forward_venues
[oanda_practice]; the Binance daemon will not execute it — the
OANDA runner PR is a separate crew's work (dependency stated in
the PR body).

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% heat cap, 3%
daily breaker, kill criteria via measurement/forward_guard.py),
fills tagged FORWARD_TEST in the Phase-2 ledger. It is NOT a
VALIDATED entrant; scorecards must never blend this lane with
ichimoku/dow/sleeve.

Thin variant module: the judged signal core lives in
strategy_keltner_breakout.py (a line-faithful port of the judged harness function);
this module binds it to this variant's own judged CFG dict
(KELTNER_BREAKOUT_FOREX_STRATEGY) and independently exposes get_signal +
entries_for_frame, per the registry's strict 1:1 module/key rule.
Judged exit bracket: families3 BR24 (SL 2.0 x ATR(14), TP 4.0 x
ATR(14)); warmup is the judged 260 bars (families2.warmup_for).

Live-evaluation contract: get_signal(df) evaluates ONLY the last
CLOSED bar (the still-forming trailing bar is dropped by timestamp
in the core's _closed_frame_s with this variant's bar duration).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

import strategy_keltner_breakout as _core

try:
    from config_strategy import KELTNER_BREAKOUT_FOREX_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 86400
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3900))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


def atr14(df: pd.DataFrame, period: int = ATR_PERIOD):
    return _core.atr14(df, period)


def signal_masks(df: pd.DataFrame) -> Tuple[Any, Any]:
    return _core.signal_masks_cfg(df, _CFG)


def entries_for_frame(df: pd.DataFrame, warmup: int = WARMUP_BARS) -> List[Tuple[int, str]]:
    return _core.entries_for_frame_cfg(df, _CFG, warmup)


def _closed_frame(df: pd.DataFrame, now_s=None):
    return _core._closed_frame_s(df, BAR_SECONDS, now_s)


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    return _core.get_signal_cfg(df, _CFG)
