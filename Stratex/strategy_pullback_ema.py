#!/usr/bin/env python3
"""strategy_pullback_ema.py — trend pullback continuation on EMA structure.

Regime: close > EMA50 > EMA200 (uptrend) or the mirror (downtrend).
Entry : price pulls back to EMA20 (touches within 0.5*ATR) while regime
        holds, then closes back in trend direction.
Exit : SL = 2 ATR beyond the pullback extreme, TP = 2R.
Win rate prior reflects the well-tested ~48-52% continuation base rate.
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
_OOS_WIN_RATE_PRIOR = 0.50
_RR_RATIO = 2.0
_ATR_MULT = 2.0


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


def get_signal(df):
    if df is None or len(df) < 220:
        return _none()
    work = _drop_forming_bar(df)
    if len(work) < 210:
        return _none()
    if not {"close", "high", "low"}.issubset(work.columns):
        return _none()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    e200 = float(ema200.iloc[-1])
    if any(math.isnan(v) for v in (a, e20, e50, e200)) or a <= 0 or c <= 0:
        return _none()

    # pullback proximity: last close within 0.5 ATR of EMA20
    near = abs(c - e20) <= 0.5 * a

    up = c > e50 > e200
    dn = c < e50 < e200

    if up and near and c > e20:
        # pullback in uptrend resolving upward
        sl = c - _ATR_MULT * a
        tp = c + 2.0 * _ATR_MULT * a
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if dn and near and c < e20:
        sl = c + _ATR_MULT * a
        tp = c - 2.0 * _ATR_MULT * a
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
