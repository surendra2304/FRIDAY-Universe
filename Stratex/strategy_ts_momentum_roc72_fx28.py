"""strategy_ts_momentum_roc72_fx28 — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, near-miss re-audit
~/workspace/str-nearmiss/REPORT.md §1.4 row 30): ts_momentum / roc72
@ FOREX28 1d — 226 pooled OOS trades, +0.185%/trade, PF 1.1735, win
rate 0.3673, 3/5 positive folds, PF @2x costs 1.0944. It meets the
owner's second tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades,
judged before Bonferroni) but did NOT pass the full frozen bar
(Bonferroni at programme N=3,899) — not a promotion, not VALIDATED.

This is a SELF-CONTAINED module for the roc72 configuration on the
OANDA forex28 panel. Crew A's strategy_ts_momentum.py (PR #991,
crypto30 cells of the same family) is NOT merged at this branch's
base and is NOT imported here; the signal core below is an
independent line-faithful port of the same judged implementation
(rigorous_backtest/rd2/families2.py ``sig_ts_momentum(df, 72,
warmup)``) and the judged exit bracket (the cell's own RD-002 grid
row record, results_rd2/grid_rows/ts_momentum__roc72__forex28__1d
.json: spec {sl_atr 2.0, tp_atr 4.0} — bracket BR24: SL 2.0 x
ATR(14), TP 4.0 x ATR(14); ATR exactly as rigorous_backtest/rd/
common.py ``atr``; warmup 260 bars, families2 WARMUP /
warmup_for("1d")).

Governance: registered FORWARD_TEST in config_strategy.py —
executable on the OANDA practice venue only via
oanda_demo/forward_test_runner.py (PR #980; forward_venues
["oanda_practice"], lane_assets FOREX28_SYMBOLS), phase-3 forward
protocol protections, fills tagged FORWARD_TEST in the Phase-2
ledger. It is NOT a VALIDATED entrant; scorecards must never blend
this lane with ichimoku/dow/sleeve, nor with the crypto30 ts_momentum
cells (same signal function, different judged cell and records).

Equivalence is pinned by tests/test_fwd019_ts_momentum_forex_lane.py,
which runs this module and the rd2 harness side by side on the
fwd002 FX fixture slices and requires identical entry lists.

Live-evaluation contract (OANDA forward-test runner): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The runner's frames are complete
candles only, so the frame's final row is the last closed bar; the
_closed_frame guard below additionally drops any still-forming
trailing bar by timestamp. A signal on bar i means "enter at the
open of bar i+1" in the judged simulator; live, the runner places a
market order during bar i+1 and re-anchors the returned
sl_dist/tp_dist (multiples of ATR at bar i) to the fill price,
exactly as the simulator anchors them to the entry price. Warmup
is the judged 260 bars.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import TS_MOMENTUM_ROC72_FX28_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ROC_LOOKBACK = int(_CFG.get("ROC_LOOKBACK", 72))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3673))
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


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — sig_ts_momentum(df, 72, warmup)."""
    roc = df["close"] / df["close"].shift(ROC_LOOKBACK) - 1.0
    long_sig = (roc > 0) & (roc.shift(1) <= 0)
    short_sig = (roc < 0) & (roc.shift(1) >= 0)
    return long_sig, short_sig


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over sig_ts_momentum's
    masks: bars [warmup, len-1], long before short."""
    long_mask, short_mask = signal_masks(df)
    ls = long_mask.fillna(False).to_numpy(dtype=bool)
    ss = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------------------------------
# Runner entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        opens = idx.asi8 / 1e9
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the runner signal dict."""
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
        long_mask, short_mask = signal_masks(frame)
        is_long = bool(long_mask.fillna(False).iloc[i])
        is_short = bool(short_mask.fillna(False).iloc[i])
        if not (is_long or is_short):
            return none_signal
        atr = atr14(frame)
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        side = "BUY" if is_long else "SELL"
        return {
            "side": side,
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
