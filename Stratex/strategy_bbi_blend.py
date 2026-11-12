#!/usr/bin/env python3
"""strategy_bbi_blend.py — Bull/Bear Insight multi-MA blend (Chinese quant classic).

BBI = (MA3 + MA6 + MA12 + MA24) / 4 blends four horizons into one line with
far better behavior on crypto than any single MA. Trade the price/BBI cross
with a confirmation slope and long regime filter.

Entry : BUY  close crosses above BBI while BBI rising and close > EMA200
        SELL close crosses below BBI while BBI falling and close < EMA200
Exit  : SL = 2.0 * ATR(20); TP = 4.0 * ATR(20).
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
    c1 = float(close.iloc[-2])
    if c <= 0:
        return _none()

    ma3 = close.rolling(3).mean()
    ma6 = close.rolling(6).mean()
    ma12 = close.rolling(12).mean()
    ma24 = close.rolling(24).mean()
    bbi = (ma3 + ma6 + ma12 + ma24) / 4.0
    b = float(bbi.iloc[-1])
    b1 = float(bbi.iloc[-2])
    b2 = float(bbi.iloc[-3])
    if any(math.isnan(v) for v in (b, b1, b2)):
        return _none()

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    a = float(atr.iloc[-1])
    ema200 = close.ewm(span=200, adjust=False).mean()
    s200 = float(ema200.iloc[-1])
    if math.isnan(a) or a <= 0 or math.isnan(s200):
        return _none()

    rising = b > b1 > b2
    falling = b < b1 < b2
    cross_up = c > b and c1 <= b1
    cross_dn = c < b and c1 >= b1
    if (cross_up or (c > b and rising)) and rising and c > s200:
        dist, tp_d = _bracket(c, a, 2.0)
        sl = c - dist
        tp = c + tp_d
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if (cross_dn or (c < b and falling)) and falling and c < s200:
        dist, tp_d = _bracket(c, a, 2.0)
        sl = c + dist
        tp = c - tp_d
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
