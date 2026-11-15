"""strategy_dow_effect — TASK-STR-FWD-002 forward entrant #2.

Judged configuration (TASK-STR-RD-002: full bar + Bonferroni at N=1,557 +
untouched holdout + 2x-cost): dow_effect / reversal @ CRYPTO30 1d —
Monday-only reversal of the trailing 5-day move; 3,660 OOS trades,
+0.878%/trade, PF 1.257, win rate 0.5227, breadth 27/30, 2x-cost PF
1.206. Flagged in RD-002 as a calendar effect, the class most prone to
era decay — the phase-3 forward window is the arbiter.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families2.py ``sig_dow(df, kind="reversal")``)
and the judged exit spec (bracket_time: SL 3.0 x ATR(14), TP 6.0 x
ATR(14), time exit at the close of entry_bar + max_bars - 1 with
max_bars=5; ATR exactly as rigorous_backtest/rd/common.py ``atr``).
Equivalence is pinned by tests/test_fwd002_forward_strategies.py
against the harness itself on real historical slices.

The judged TIME exit has no broker-native equivalent: the daemon
carries SL/TP as protective orders and enforces the time exit itself
(autonomy/run_daemon.py ``_manage_forward_time_exits``, using
measurement/forward_guard.time_exit_due) — a position entered in bar E
is closed at market once bar E + max_bars has fully elapsed, which is
the close of bar E + max_bars - 1 the simulator exits at.

Live-evaluation contract: see strategy_ichimoku_trend — only the last
CLOSED bar is evaluated; the forming bar is dropped by timestamp.
Weekday is the UTC weekday of the bar's open (daily bars open 00:00
UTC), exactly the harness's ``df.index.weekday`` on resampled frames.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import DOW_EFFECT_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ROC_LOOKBACK = int(_CFG.get("ROC_LOOKBACK", 5))
ENTRY_WEEKDAY = int(_CFG.get("ENTRY_WEEKDAY", 0))  # Monday (UTC bar open)
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 3.0))
TP_ATR = float(_CFG.get("TP_ATR", 6.0))
MAX_BARS = int(_CFG.get("MAX_BARS", 5))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.5227))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families2.py + rd/common.py)
# ---------------------------------------------------------------------------

def atr14(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """ATR exactly as rigorous_backtest/rd/common.py ``atr``."""
    tr = pd.concat(
        [
            df["high"] - df["low"],
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1)),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bar_sides(df: pd.DataFrame) -> np.ndarray:
    """Per-bar judged side: +1 LONG / -1 SHORT / 0 none (sig_dow core)."""
    wd = df.index.weekday.to_numpy()
    roc = (df["close"] / df["close"].shift(ROC_LOOKBACK) - 1.0).to_numpy()
    sides = np.zeros(len(df), dtype=int)
    monday = (wd == ENTRY_WEEKDAY) & ~np.isnan(roc)
    # reversal: short a positive trailing move, long a negative one
    sides[monday & (roc > 0)] = -1
    sides[monday & (roc <= 0)] = 1
    return sides


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to sig_dow(df, "reversal", warmup)."""
    sides = bar_sides(df)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(df) - 1):
        if sides[i] == 1:
            out.append((i, "LONG"))
        elif sides[i] == -1:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    try:
        opens = df.index.view("int64") / 1e9
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        i = len(frame) - 1
        if i < WARMUP_BARS:
            return none_signal
        side_i = int(bar_sides(frame)[i])
        if side_i == 0:
            return none_signal
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        return {
            "side": "BUY" if side_i == 1 else "SELL",
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
