"""strategy_mtf_confluence — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (canonical core module for the mtf_confluence family).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 39): mtf_confluence /
h4_native_ema200 @ CRYPTO30 4h — 1,668 pooled OOS trades,
+0.490%/trade, PF 1.1538, win rate 0.3807, 4/5 positive folds,
PF @2x costs 1.1006. It meets the owner's second tier (expectancy
> 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni) but did NOT
pass the full frozen bar (Bonferroni at programme N=3,899) — not a
promotion, not VALIDATED.

HARNESS FINDING (checked first, per the wave-2 slice): despite the
"h4_native" name and the family name, the judged h4_native_ema200
configuration consumes NO higher-timeframe series. In
rigorous_backtest/rd2/families2.py its fn is
``lambda df, aux, am, w: sig_mtf_native(df, w)`` — the aux frame is
ignored — and rd2/grid.py only loads an aux panel for timeframes in
AUX_TF = {"15m": "1h", "1h": "4h"} (neither 4h nor 1d), feeding it
only to the h1_cross variants via sig_mtf. sig_mtf_native computes
EMA(20)/EMA(50) cross + close-vs-EMA(200) on the cell's OWN bar
series. The 1d cell was therefore judged on 1d bars natively, and
both cells are faithfully wireable as per-timeframe modules: this
4h core, and the 1d thin variant (strategy_mtf_confluence_1d).

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% aggregate heat
cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50
closed trades or mark-to-market drawdown >5% of venue equity),
fills tagged FORWARD_TEST. Scorecards must never blend this lane
with the VALIDATED entrants.

The signal core is the line-faithful port above and the judged exit
bracket (families2 BR24: SL 2.0 x ATR(14), TP 4.0 x ATR(14)).
Equivalence is pinned by tests/test_fwd019_mtf_confluence_lane.py.

Live-evaluation contract (Stratex daemon): ``get_signal(df)``
evaluates ONLY the last CLOSED bar. The daemon feed's final row is
the still-forming bar; it is dropped by timestamp before evaluation.
A signal on bar i means "enter at the open of bar i+1" in the judged
simulator; live, the daemon places a market order during bar i+1 and
re-anchors the returned sl_dist/tp_dist (multiples of ATR at bar i)
to the fill price. Warmup is the judged 260 bars.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import MTF_CONFLUENCE_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
EMA_FAST = int(_CFG.get("EMA_FAST", 20))
EMA_SLOW = int(_CFG.get("EMA_SLOW", 50))
EMA_TREND = int(_CFG.get("EMA_TREND", 200))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3807))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families2.py + rd/common.py)
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


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


def signal_masks_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) for an explicit judged configuration —
    families2.sig_mtf_native's masks, computed on the frame's OWN
    series: EMA(20) crosses above EMA(50) AND close > EMA(200) ->
    long; cross down AND close < EMA(200) -> short."""
    f = _ema(df["close"], int(cfg.get("EMA_FAST", EMA_FAST)))
    s = _ema(df["close"], int(cfg.get("EMA_SLOW", EMA_SLOW)))
    d = _ema(df["close"], int(cfg.get("EMA_TREND", EMA_TREND)))
    long_sig = (f > s) & (f.shift(1) <= s.shift(1)) & (df["close"] > d)
    short_sig = (f < s) & (f.shift(1) >= s.shift(1)) & (df["close"] < d)
    return long_sig, short_sig


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to families2._entries over
    sig_mtf_native's masks: bars [warmup, len-1] INCLUSIVE of the
    final bar (families2._entries' range — unlike the families3
    convention, which excludes the last bar), long before short."""
    w = int(cfg.get("WARMUP_BARS", WARMUP_BARS)) if warmup is None else warmup
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy(dtype=bool)
    sm = short_mask.fillna(False).to_numpy(dtype=bool)
    out: List[Tuple[int, str]] = []
    for i in range(w, len(lm)):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    return entries_for_frame_cfg(df, _CFG, warmup)


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(
    df: pd.DataFrame, bar_seconds: int = BAR_SECONDS, now_s: Optional[float] = None
) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the bollinger template's ``idx.view("int64")``
    returns the index's native unit (microseconds under pandas 3),
    which silently disables the drop there."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        epoch = pd.Timestamp("1970-01-01", tz="UTC")
        opens = (idx - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + bar_seconds <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], bar_seconds: int = BAR_SECONDS
) -> Dict[str, Any]:
    """Evaluate the last closed bar under an explicit configuration."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        warmup = int(cfg.get("WARMUP_BARS", WARMUP_BARS))
        if df is None or len(df) < warmup + 1:
            return none_signal
        frame = _closed_frame(df, bar_seconds)
        if len(frame) < warmup + 1:
            return none_signal
        i = len(frame) - 1
        if i < warmup:
            return none_signal
        long_mask, short_mask = signal_masks_cfg(frame, cfg)
        is_long = bool(long_mask.fillna(False).iloc[i])
        is_short = bool(short_mask.fillna(False).iloc[i])
        if not (is_long or is_short):
            return none_signal
        atr = atr14(frame, int(cfg.get("ATR_PERIOD", ATR_PERIOD)))
        atr_i = float(atr.iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        sl_atr = float(cfg.get("SL_ATR", SL_ATR))
        tp_atr = float(cfg.get("TP_ATR", TP_ATR))
        return {
            "side": "BUY" if is_long else "SELL",
            "sl_dist": sl_atr * atr_i,
            "tp_dist": tp_atr * atr_i,
            "win_rate_prior": float(cfg.get("OOS_WIN_RATE", WIN_RATE_PRIOR)),
            "rr_ratio": tp_atr / sl_atr,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 4h bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG, BAR_SECONDS)
