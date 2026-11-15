"""oanda_demo/sleeve_signals.py — judged signal cores for sleeve legs.

Forex leg of the RD-002 Stage-C best-per-class sleeve:
tsmom2_dual / roc90_ema200 @ FOREX28 1d. Line-faithful port of
rigorous_backtest/rd2/families2.py ``sig_dual_momentum(df, 90)``:

  ROC(90) = close / close[-90] - 1; EMA200 trend filter.
  LONG  when ROC crosses up through zero AND close > EMA(200).
  SHORT when ROC crosses down through zero AND close < EMA(200).

Judged bracket (families2 tsmom2_dual): SL 2.5 x ATR(14), TP 5.0 x
ATR(14), ATR exactly as rigorous_backtest/rd/common.py. Warmup 260
(families2 ``_entries`` convention: bars [warmup, len) — the final
bar of a frame IS an entry bar, unlike families3's masks helper).

Equivalence is pinned by tests/test_fwd002_sleeve.py against the
harness on Yahoo-cache slices (the judged data source).

The frames fed here are COMPLETE daily candles only (the sleeve
runner requests complete candles from OANDA with UTC-midnight
alignment), so the last bar of a frame is the last closed bar and is
evaluated directly — no forming-bar drop is needed or applied.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import SLEEVE_TSMOM2_DUAL_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

ROC_LOOKBACK = int(_CFG.get("ROC_LOOKBACK", 90))
TREND_EMA = int(_CFG.get("TREND_EMA", 200))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 5.0))
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))


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


def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


def bar_sides(df: pd.DataFrame) -> np.ndarray:
    """Per-bar judged side: +1 LONG / -1 SHORT / 0 none."""
    roc = df["close"] / df["close"].shift(ROC_LOOKBACK) - 1.0
    e200 = _ema(df["close"], TREND_EMA)
    long_sig = (roc > 0) & (roc.shift(1) <= 0) & (df["close"] > e200)
    short_sig = (roc < 0) & (roc.shift(1) >= 0) & (df["close"] < e200)
    sides = np.zeros(len(df), dtype=int)
    sides[long_sig.fillna(False).to_numpy()] = 1
    sides[short_sig.fillna(False).to_numpy()] = -1
    return sides


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to sig_dual_momentum(df, 90, warmup)."""
    sides = bar_sides(df)
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(df)):
        if sides[i] == 1:
            out.append((i, "LONG"))
        elif sides[i] == -1:
            out.append((i, "SHORT"))
    return out


def evaluate_last_bar(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Signal on the frame's last (closed) bar, or None.

    Returns side plus the judged bracket DISTANCES (multiples of
    ATR at the signal bar); the runner anchors them to the live
    fill price, as the judged simulator anchors to the entry price.
    """
    if df is None or len(df) < WARMUP_BARS + 1:
        return None
    i = len(df) - 1
    if i < WARMUP_BARS:
        return None
    side_i = int(bar_sides(df)[i])
    if side_i == 0:
        return None
    atr_i = float(atr14(df).iloc[i])
    if not np.isfinite(atr_i) or atr_i <= 0:
        return None
    return {
        "side": "BUY" if side_i == 1 else "SELL",
        "sl_dist": SL_ATR * atr_i,
        "tp_dist": TP_ATR * atr_i,
        "atr": atr_i,
        "signal_close": float(df["close"].iloc[i]),
    }
