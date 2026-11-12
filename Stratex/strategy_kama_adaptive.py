#!/usr/bin/env python3
"""strategy_kama_adaptive.py — Kaufman Adaptive Moving Average trend riding.

KAMA slows down in choppy markets and speeds up in trends — the classic
"adaptive MA" fix for whipsaw losses.

Entry : BUY  KAMA(10,2,30) crosses above price-anchored regime (close > KAMA
        and KAMA rising for 3 bars) while KAMA slope > 0 and close > EMA200
        SELL mirror-image short
Exit  : SL = 2.0 * ATR(20); TP = 4.0 * ATR(20).
"""
from __future__ import annotations
import math
from collections import namedtuple
import numpy as np
import pandas as pd


class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio", "sl_dist", "tp_dist"], defaults=(None, None))):
    @property
    def confidence(self):
        return self.win_rate_prior


_STRATEGY_TYPE = "TREND"
_OOS_WIN_RATE_PRIOR = 0.42
_RR_RATIO = 2.0
_ATR_MULT = 2.0
_TP_ATR = 4.0


def _none():
    return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, None, None)


def _drop_forming_bar(df):
    try:
        last_ts = df.index[-1]
        now = pd.Timestamp.now(tz="UTC")
        if getattr(last_ts, "tzinfo", None) is None:
            today = now.tz_localize(None).normalize()
        else:
            today = now.tz_convert(last_ts.tzinfo).normalize()
        if last_ts >= today:
            return df.iloc[:-1]
    except Exception:
        return df
    return df


def _kama(close: pd.Series, er: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Vectorized-ish KAMA over the whole series (numba-free)."""
    vals = close.to_numpy(dtype=float)
    n = len(vals)
    out = np.full(n, np.nan)
    if n < er + 2:
        return pd.Series(out, index=close.index)
    # efficiency ratio + smoothing constant per bar
    # direction: |close_t - close_{t-er}|; volatility: sum |close_i - close_{i-1}| over er bars
    direction = np.abs(vals - np.roll(vals, er))
    one = np.abs(np.diff(vals))
    vol_sum = np.convolve(one, np.ones(er, dtype=float), mode="full")[:n]
    vol_sum[:er] = np.nan
    er_ratio = np.where(vol_sum > 0, direction / vol_sum, np.nan)
    sc = (er_ratio * (2.0 / (fast + 1) - 2.0 / (slow + 1)) + 2.0 / (slow + 1)) ** 2
    out[er - 1] = vals[er - 1]
    for i in range(er, n):
        prev = out[i - 1]
        if math.isnan(prev):
            out[i] = vals[i]
            continue
        out[i] = prev + sc[i] * (vals[i] - prev)
    return pd.Series(out, index=close.index)



# Governor-legal bracket: ATR-based distance clamped into [1.0%, 3.0%] of
# price so the live governor's [0.5%, 3%] stop window accepts the signal on
# every timeframe (raw 2*ATR on dailies is ~9-14% and always rejected).
_MIN_STOP_FRAC = 0.010
_MAX_STOP_FRAC = 0.030


def _bracket(c: float, a: float, tp_mult: float):
    """Return (sl_dist, tp_dist) with stop clamped legal and TP = tp_mult * stop."""
    dist = 2.0 * a
    if dist < _MIN_STOP_FRAC * c:
        dist = _MIN_STOP_FRAC * c
    if dist > _MAX_STOP_FRAC * c:
        dist = _MAX_STOP_FRAC * c
    tp = dist * tp_mult
    return dist, tp


def get_signal(df):
    if df is None or len(df) < 260:
        return _none()
    work = _drop_forming_bar(df)
    if len(work) < 250:
        return _none()
    if not {"close", "high", "low"}.issubset(work.columns):
        return _none()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)

    c = float(close.iloc[-1])
    if c <= 0:
        return _none()

    kama = _kama(close)
    k = float(kama.iloc[-1])
    k1 = float(kama.iloc[-2])
    k3 = float(kama.iloc[-4])
    if any(math.isnan(v) for v in (k, k1, k3)):
        return _none()

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    a = float(atr.iloc[-1])
    ema200 = close.ewm(span=200, adjust=False).mean()
    s200 = float(ema200.iloc[-1])
    if math.isnan(a) or a <= 0 or math.isnan(s200):
        return _none()

    rising = k > k1 > k3
    falling = k < k1 < k3
    if c > k and rising and c > s200:
        dist, tp_d = _bracket(c, a, 2.0)
        sl = c - dist
        tp = c + tp_d
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if c < k and falling and c < s200:
        dist, tp_d = _bracket(c, a, 2.0)
        sl = c + dist
        tp = c - tp_d
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
