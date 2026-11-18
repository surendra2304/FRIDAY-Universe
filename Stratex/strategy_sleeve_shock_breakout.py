"""strategy_sleeve_shock_breakout — TASK-STR-FWD-002 sleeve leg (crypto).

Crypto leg of the RD-002 Stage-C best-per-class portfolio sleeve
(owner-approved third forward entrant, 2026-11-15): shock_breakout /
k1.0 @ CRYPTO30 1wk. Judged implementation:
rigorous_backtest/rd2/families3.py ``sig_shock(df, 1.0)`` — a weekly
close moving more than 1.0 x ATR(14) versus the prior weekly close
enters in the direction of the shock — with the judged bracket BR24
(SL 2.0 x ATR(14), TP 4.0 x ATR(14)). As a standalone cell it did NOT
pass the promotion bar (109 OOS trades, PF 1.575); it trades ONLY as
a sleeve component and is judged on the sleeve's compounded equity +
max drawdown, under the sleeve-level kill rule in
measurement/forward_guard.py.

WEEKLY BARS — the judged construction is NOT Binance's native weekly
kline. The harness built weekly bars as 7-day buckets anchored at
each symbol's judged 1d series start (rd2/panels.py ``_to_weekly``:
resample "7D", origin=start_day, buckets kept only with all 7 daily
bars). :func:`weekly_candles` rebuilds exactly those buckets from
daily candles using the per-symbol anchors pinned in
config_strategy.WEEKLY_BUCKET_ANCHORS; the daemon fetches daily
candles and aggregates through here whenever the 1wk timeframe is
scanned. Equivalence (aggregation + entries) is pinned by
tests/test_fwd002_sleeve.py against harness-built weekly frames,
including a late-listing symbol (SUIUSDT, anchor 2023-05-04).

Live-evaluation contract: as for the other forward modules — only
the last CLOSED weekly bucket is evaluated (the trailing partial
bucket is dropped by timestamp); a signal means entry during the
next bucket, brackets re-anchored to the fill via sl_dist/tp_dist.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import SLEEVE_SHOCK_BREAKOUT_STRATEGY as _CFG
    from config_strategy import WEEKLY_BUCKET_ANCHORS as _ANCHORS
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}
    _ANCHORS = {}

TIMEFRAME = "1wk"
BAR_SECONDS = 7 * 86400
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 104))
SHOCK_K = float(_CFG.get("SHOCK_K", 1.0))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
SL_ATR = float(_CFG.get("SL_ATR", 2.0))
TP_ATR = float(_CFG.get("TP_ATR", 4.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.4267))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged weekly-bar construction (rd2/panels.py _to_weekly)
# ---------------------------------------------------------------------------

def weekly_candles(
    daily_candles: List[Dict[str, Any]],
    symbol: str,
    anchors: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Aggregate daily candle dicts into judged weekly buckets.

    Buckets are 7-day spans anchored at the symbol's judged series
    start (config_strategy.WEEKLY_BUCKET_ANCHORS). Only buckets with
    all 7 daily bars are emitted as complete bars; the final bucket is
    also emitted when partial (it is the still-forming week, which
    get_signal drops by timestamp — mirroring how native feeds carry
    the forming bar). Earlier partial buckets (data gaps) are dropped,
    exactly as the harness dropped them.
    """
    anchor_map = _ANCHORS if anchors is None else anchors
    anchor = anchor_map.get(symbol)
    if anchor is None or not daily_candles:
        return []
    ordered = sorted(daily_candles, key=lambda c: float(c["timestamp"]))
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    for c in ordered:
        idx = int((float(c["timestamp"]) - anchor) // BAR_SECONDS)
        buckets.setdefault(idx, []).append(c)
    out: List[Dict[str, Any]] = []
    keys = sorted(buckets)
    for pos, idx in enumerate(keys):
        bars = buckets[idx]
        is_last = pos == len(keys) - 1
        if len(bars) != 7 and not is_last:
            continue
        out.append(
            {
                "timestamp": anchor + idx * BAR_SECONDS,
                "open": float(bars[0]["open"]),
                "high": max(float(b["high"]) for b in bars),
                "low": min(float(b["low"]) for b in bars),
                "close": float(bars[-1]["close"]),
                "volume": sum(float(b.get("volume", 0)) for b in bars),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Judged-logic port (families3.sig_shock + rd/common.atr)
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
    """(long_mask, short_mask) — sig_shock(df, k=1.0) masks."""
    a = atr14(df)
    up = (df["close"] - df["close"].shift(1)) > SHOCK_K * a
    dn = (df["close"].shift(1) - df["close"]) > SHOCK_K * a
    return up, dn


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to families3._entries_from_masks over
    sig_shock's masks: bars [max(warmup, 1), len-2], long before short."""
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
    """Drop still-forming trailing buckets (open + 7d > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the index's int64 view returns its native unit
    (microseconds under pandas 3), which silently disables the
    drop when divided by 1e9 (TASK-STR-FWD-025).
    """
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    try:
        epoch = pd.Timestamp("1970-01-01", tz=df.index.tz)
        opens = (df.index - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed weekly bar; return the daemon signal dict."""
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
        atr_i = float(atr14(frame).iloc[i])
        if not np.isfinite(atr_i) or atr_i <= 0:
            return none_signal
        return {
            "side": "BUY" if is_long else "SELL",
            "sl_dist": SL_ATR * atr_i,
            "tp_dist": TP_ATR * atr_i,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
