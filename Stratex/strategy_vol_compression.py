"""strategy_vol_compression — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (canonical core module for the vol_compression family).

Judged configuration (TASK-STR-RD-002 near-miss audit,
~/workspace/str-nearmiss/REPORT.md §1.4 row 56): vol_compression /
squeeze_ema200 @ CRYPTO30 1h — 1,104 pooled OOS trades,
+0.182%/trade, PF 1.1310, win rate 0.3732, 3/5 positive folds. It
meets the owner's second tier (expectancy > 0, PF >= 1.05, >= 200
OOS trades, pre-Bonferroni) but did NOT pass the full frozen bar
(Bonferroni at programme N=3,899) — not a promotion, not VALIDATED.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (0.1% per-trade risk on venue equity, 2% aggregate heat
cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50
closed trades or mark-to-market drawdown >5% of venue equity),
fills tagged FORWARD_TEST. Scorecards must never blend this lane
with the VALIDATED entrants.

The signal core is a line-faithful port of the judged implementation
(rigorous_backtest/rd2/families3.py ``sig_vol_compression(df,
filtered=True, warmup)``: ATR(7) at its trailing 50-bar minimum (the
squeeze) AND close breaking the prior 10-bar high/low, gated by
close vs EMA(200)) and the judged exit bracket (families3 BR24:
SL 2.0 x ATR(14), TP 4.0 x ATR(14)). The judged timeframe is 1h
(BAR_SECONDS 3600); the signal logic is a bar-series function and is
timeframe-agnostic, so equivalence is pinned on the 4h fixture frame
(the fwd002 fixtures exist only at 1d/4h) in
tests/test_fwd019_vol_compression_lane.py, at the judged warmup and
at a reduced warmup where the sparse squeeze entries are denser.
The squeeze_raw variant is a thin module binding its own CFG dict
to the parameterised helpers here.

Live-evaluation contract: ``get_signal(df)`` evaluates ONLY the
last CLOSED bar (the feed's final, still-forming row is dropped by
timestamp). A signal on bar i means "enter at the open of bar i+1"
in the judged simulator; live, the order is placed during bar i+1
and the returned sl_dist/tp_dist (multiples of ATR at bar i) are
re-anchored to the fill price. Warmup is the judged 260 bars.
DEPLOY NOTE: the daemon's default timeframe set is 1d,4h and its
generic fetch returns 100 bars for other timeframes — this 1h lane
needs STRATEX_TIMEFRAMES to include 1h AND a >=262-bar 1h fetch at
deploy time, or it will register but never signal (recorded in the
PR body, not silently assumed).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import VOL_COMPRESSION_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1h"))
BAR_SECONDS = 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
ATR_FAST_PERIOD = int(_CFG.get("ATR_FAST_PERIOD", 7))
SQUEEZE_WINDOW = int(_CFG.get("SQUEEZE_WINDOW", 50))
BREAKOUT_BARS = int(_CFG.get("BREAKOUT_BARS", 10))
FILTERED = bool(_CFG.get("FILTERED", True))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3732))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (rigorous_backtest/rd2/families3.py + rd/common.py)
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA exactly as rigorous_backtest/rd/common.py ``ema``."""
    return series.ewm(span=span, adjust=False).mean()


def atr_series(df: pd.DataFrame, period: int) -> pd.Series:
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


def atr14(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    return atr_series(df, period)


def signal_masks_cfg(df: pd.DataFrame, cfg: Dict[str, Any]) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) for an explicit judged configuration —
    families3.sig_vol_compression's masks: ATR(7) <= its trailing
    50-bar rolling minimum (squeeze) AND close above the prior
    10-bar high (long) / below the prior 10-bar low (short); the
    filtered variant additionally requires close on the EMA(200)
    side of the trade."""
    a7 = atr_series(df, int(cfg.get("ATR_FAST_PERIOD", ATR_FAST_PERIOD)))
    squeeze = a7 <= a7.rolling(int(cfg.get("SQUEEZE_WINDOW", SQUEEZE_WINDOW))).min()
    n = int(cfg.get("BREAKOUT_BARS", BREAKOUT_BARS))
    hh10 = df["high"].rolling(n).max().shift(1)
    ll10 = df["low"].rolling(n).min().shift(1)
    up = squeeze & (df["close"] > hh10)
    dn = squeeze & (df["close"] < ll10)
    if bool(cfg.get("FILTERED", FILTERED)):
        e200 = _ema(df["close"], 200)
        up = up & (df["close"] > e200)
        dn = dn & (df["close"] < e200)
    return up, dn


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    return signal_masks_cfg(df, _CFG)


def entries_for_frame_cfg(
    df: pd.DataFrame, cfg: Dict[str, Any], warmup: Optional[int] = None
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_vol_compression's masks: bars [max(warmup, 1), len-2], long
    before short."""
    w = int(cfg.get("WARMUP_BARS", WARMUP_BARS)) if warmup is None else warmup
    long_mask, short_mask = signal_masks_cfg(df, cfg)
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    out: List[Tuple[int, str]] = []
    for i in range(max(w, 1), len(df) - 1):
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
    """Evaluate the last closed 1h bar; return the daemon signal dict."""
    return get_signal_cfg(df, _CFG, BAR_SECONDS)
