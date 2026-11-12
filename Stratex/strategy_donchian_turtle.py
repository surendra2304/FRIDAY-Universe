#!/usr/bin/env python3
"""strategy_donchian_turtle.py — classic turtle trend following, live-interface compatible.

Entry : close breaks the prior N-day Donchian channel (20d entry / 10d exit)
        with ATR(20) volatility filter; longs only above 200d SMA, shorts only
        below (regime alignment — the edge turtles relied on).
Exit  : opposite 10-day channel extreme, expressed as SL/TP bracket for the
        live engine (SL = 2*ATR adverse, TP = 10-day channel extreme).
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
_OOS_WIN_RATE_PRIOR = 0.38   # classic turtle: low win rate, big winners
_RR_RATIO = 3.0
_ENTRY_N = 20
_EXIT_N = 10
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

    # ATR(20)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    sma200 = close.rolling(200).mean()

    # completed prior bars (exclude the last close itself from the channel)
    hh = high.rolling(_ENTRY_N).max().shift(1)   # prior 20-day high
    ll = low.rolling(_ENTRY_N).min().shift(1)    # prior 20-day low
    exit_hh = high.rolling(_EXIT_N).max().shift(1)
    exit_ll = low.rolling(_EXIT_N).min().shift(1)

    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    s200 = float(sma200.iloc[-1])
    if any(math.isnan(v) for v in (a, s200)) or a <= 0 or c <= 0:
        return _none()

    long_break = c > float(hh.iloc[-1])
    short_break = c < float(ll.iloc[-1])
    if not (long_break or short_break):
        return _none()

    if long_break and c > s200:
        sl = c - _ATR_MULT * a
        tp = float(exit_hh.iloc[-1]) if exit_hh.iloc[-1] and not math.isnan(exit_hh.iloc[-1]) else c + 3.0 * _ATR_MULT * a
        if tp <= c:  # channel extreme below entry (rare): fall back to 3R
            tp = c + 3.0 * _ATR_MULT * a
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
    if short_break and c < s200:
        sl = c + _ATR_MULT * a
        tp = float(exit_ll.iloc[-1]) if exit_ll.iloc[-1] and not math.isnan(exit_ll.iloc[-1]) else c - 3.0 * _ATR_MULT * a
        if tp >= c:
            tp = c - 3.0 * _ATR_MULT * a
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
