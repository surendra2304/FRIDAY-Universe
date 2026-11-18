"""strategy_ichimoku_trend — TASK-STR-FWD-002 forward entrant #1.

Judged configuration (TASK-STR-RD-002: full bar + Bonferroni at N=1,557 +
untouched holdout + 2x-cost): ichimoku_trend / tk_cloud @ CRYPTO30 4h —
2,302 OOS trades, +0.894%/trade, PF 1.278, win rate 0.4010, breadth 26/30,
2x-cost PF 1.222.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_ichimoku(df, cloud=True)``) and
the judged exit bracket (families3 BR24: SL 2.0 x ATR(14), TP 4.0 x
ATR(14); ATR exactly as rigorous_backtest/rd/common.py ``atr``). The
equivalence is pinned by tests/test_fwd002_forward_strategies.py, which
runs this module and the rd2 harness side by side on real historical
slices and requires identical entry lists and bracket distances.

Live-evaluation contract (Stratex daemon): ``get_signal(df)`` evaluates
ONLY the last CLOSED bar. The daemon feed's final row is the
still-forming bar; it is dropped by timestamp before evaluation. A
signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i) to
the fill price, exactly as the simulator anchors them to the entry
price. Warmup is the judged 260 bars, counted within the evaluated
frame; the ichimoku windows are finite-memory and the ATR EWM's
initialisation error after 260 bars is ~1e-9 relative, so a live frame
reproduces the judged series.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import ICHIMOKU_TREND_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
TENKAN_PERIOD = int(_CFG.get("TENKAN_PERIOD", 9))
KIJUN_PERIOD = int(_CFG.get("KIJUN_PERIOD", 26))
SENKOU_B_PERIOD = int(_CFG.get("SENKOU_B_PERIOD", 52))
CLOUD_SHIFT = int(_CFG.get("CLOUD_SHIFT", 26))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4010))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def _hh_ll_incl(df: pd.DataFrame, n: int):
    """Trailing window including the current bar (families3._hh_ll_incl)."""
    return df["high"].rolling(n).max(), df["low"].rolling(n).min()


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


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
    """(long_mask, short_mask) — sig_ichimoku(df, cloud=True) masks."""
    hh9, ll9 = _hh_ll_incl(df, TENKAN_PERIOD)
    hh26, ll26 = _hh_ll_incl(df, KIJUN_PERIOD)
    hh52, ll52 = _hh_ll_incl(df, SENKOU_B_PERIOD)
    tenkan = (hh9 + ll9) / 2.0
    kijun = (hh26 + ll26) / 2.0
    up = _cross_up(tenkan, kijun)
    dn = _cross_down(tenkan, kijun)
    span_a = ((tenkan + kijun) / 2.0).shift(CLOUD_SHIFT)
    span_b = ((hh52 + ll52) / 2.0).shift(CLOUD_SHIFT)
    top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    bot = pd.concat([span_a, span_b], axis=1).min(axis=1)
    up = up & (df["close"] > top)
    dn = dn & (df["close"] < bot)
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_ichimoku's masks: bars [max(warmup, 1), len-2], long before short."""
    long_mask, short_mask = signal_masks(df)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(warmup, 1), len(df) - 1):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the index's int64 view returns its native unit
    (microseconds under pandas 3), which silently disables the
    drop when divided by 1e9 (TASK-STR-FWD-025).
    """
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        epoch = pd.Timestamp("1970-01-01", tz=idx.tz)
        opens = (idx - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 4h bar; return the daemon signal dict."""
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
