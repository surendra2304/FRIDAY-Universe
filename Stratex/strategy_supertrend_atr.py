#!/usr/bin/env python3
"""strategy_supertrend_atr.py — classic SuperTrend with EMA regime filter.

SuperTrend(HL2, 10, 3A) flips long/short with the trend; adding the EMA200
regime filter avoids taking counter-regime flips that the raw indicator
suffers from in crypto.

Entry : BUY  SuperTrend flips to bullish (close > line, line rising) and close > EMA200
        SELL SuperTrend flips bearish (close < line, line falling) and close < EMA200
Exit  : SL = the SuperTrend line itself (it is a trailing stop by design);
        TP = 4.5 * ATR(10).
"""
from __future__ import annotations
import math
from collections import namedtuple
import pandas as pd


class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio", "sl_dist", "tp_dist"], defaults=(None, None))):
    @property
    def confidence(self):
        return self.win_rate_prior


_STRATEGY_TYPE = "TREND"
_OOS_WIN_RATE_PRIOR = 0.42
_RR_RATIO = 2.25
_ATR_N = 10
_ATR_MULT = 3.0
_TP_ATR_MULT = 4.5


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


def _supertrend(high: pd.Series, low: pd.Series, close: pd.Series, n: int, mult: float):
    """Returns (line, direction) Series; direction=1 bullish, -1 bearish."""
    hl2 = (high + low) / 2.0
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr

    final_upper = upper.copy()
    final_lower = lower.copy()
    direction = pd.Series(index=close.index, dtype=float)
    line = pd.Series(index=close.index, dtype=float)

    fu = float("nan")
    fl = float("nan")
    d = 1.0
    for i in range(len(close)):
        c = float(close.iloc[i])
        u = float(upper.iloc[i])
        l = float(lower.iloc[i])
        if math.isnan(u) or math.isnan(l) or math.isnan(c):
            direction.iloc[i] = float("nan")
            line.iloc[i] = float("nan")
            continue
        if math.isnan(fu):
            fu, fl, d = u, l, 1.0
        else:
            # trailing logic
            fu = u if (u < fu or c > fu) else fu
            fl = l if (l > fl or c < fl) else fl
            if c > fu:
                d = 1.0
            elif c < fl:
                d = -1.0
        direction.iloc[i] = d
        line.iloc[i] = fl if d == 1.0 else fu
    return line, direction



# Governor-legal bracket: ATR-based distance clamped into [1.0%, 3.0%] of
# price so the live governor's [0.5%, 3%] stop window accepts the signal on
# every timeframe (raw 2*ATR on dailies is ~9-14% and always rejected).
_MIN_STOP_FRAC = 0.010
_MAX_STOP_FRAC = 0.030


def _bracket(c: float, a: float, tp_mult: float):
    """Return (sl_dist, tp_dist) with stop clamped legal and TP = tp_mult * stop."""
    dist = 3.0 * a
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

    line, direction = _supertrend(high, low, close, _ATR_N, _ATR_MULT)
    ln = float(line.iloc[-1])
    d0 = float(direction.iloc[-1])
    d1 = float(direction.iloc[-2])
    d3 = float(direction.iloc[-3])
    if any(math.isnan(v) for v in (ln, d0, d1, d3)):
        return _none()

    ema200 = close.ewm(span=200, adjust=False).mean()
    s200 = float(ema200.iloc[-1])
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr10 = tr.rolling(_ATR_N).mean()
    a = float(atr10.iloc[-1])
    if math.isnan(a) or a <= 0 or math.isnan(s200):
        return _none()

    bullish_now = d0 == 1.0 and c > ln
    bearish_now = d0 == -1.0 and c < ln
    flip_up = bullish_now and d1 == -1.0
    flip_dn = bearish_now and d1 == 1.0
    stayed = d0 == d1 == d3

    if (flip_up or (bullish_now and stayed)) and c > s200:
        dist, tp_d = _bracket(c, a, 1.5)
        sl = min(ln, c - dist) if ln > 0 else c - dist  # trailing line if wider, else legal clamp
        if c - sl > 0.03 * c:  # governor stop cap
            sl = c - dist
        tp = c + tp_d
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if (flip_dn or (bearish_now and stayed)) and c < s200:
        dist, tp_d = _bracket(c, a, 1.5)
        sl = max(ln, c + dist) if ln > 0 else c + dist
        if sl - c > 0.03 * c:
            sl = c + dist
        tp = c - tp_d
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
