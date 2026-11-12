#!/usr/bin/env python3
"""strategy_momentum_rotation.py — time-series momentum with dual horizon confirmation.

Entry: 30d AND 90d returns both positive (long) / both negative (short) —
       the classic dual-momentum confirmation that filters chop.
Filter: 200d SMA slope must agree for longs (inverted for shorts).
Exit : expressed as SL = 2 ATR(20) against the move, TP = 2R.
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
_OOS_WIN_RATE_PRIOR = 0.45
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
    if df is None or len(df) < 210:
        return _none()
    work = _drop_forming_bar(df)
    if len(work) < 200:
        return _none()
    if not {"close", "high", "low"}.issubset(work.columns):
        return _none()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    sma200 = close.rolling(200).mean()
    slope = sma200.diff(20)

    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    sl200 = float(slope.iloc[-1])
    if any(math.isnan(v) for v in (a, sl200)) or a <= 0 or c <= 0:
        return _none()

    r30 = c / float(close.iloc[-31]) - 1.0
    r90 = c / float(close.iloc[-91]) - 1.0

    if r30 > 0 and r90 > 0 and sl200 > 0:
        sl = c - _ATR_MULT * a
        tp = c + 2.0 * _ATR_MULT * a
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if r30 < 0 and r90 < 0 and sl200 < 0:
        sl = c + _ATR_MULT * a
        tp = c - 2.0 * _ATR_MULT * a
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
