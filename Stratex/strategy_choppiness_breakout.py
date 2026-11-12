#!/usr/bin/env python3
"""strategy_choppiness_breakout.py — regime-filtered Donchian breakout.

The Choppiness Index (CHOP) distinguishes trending from ranging regimes.
This strategy only takes channel breakouts when CHOP confirms a trending
market (CHOP < 38.2 = strong trend), avoiding the false breakouts that
destroy naive breakout systems in chop.

Entry : BUY  close breaks prior 20-bar Donchian high AND CHOP(14) < 45 AND close > EMA200
        SELL close breaks prior 20-bar Donchian low AND CHOP(14) < 45 AND close < EMA200
Exit  : SL = 2.0 * ATR(20); TP = 4.5 * ATR(20).
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
_OOS_WIN_RATE_PRIOR = 0.40
_RR_RATIO = 2.25
_ATR_MULT = 2.0
_TP_ATR = 4.5
_CHOP_N = 14
_CHOP_MAX = 45.0


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

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    a = float(atr.iloc[-1])

    # Choppiness Index over _CHOP_N bars: 100 * log10(sum(TR)/range)
    hh = high.rolling(_CHOP_N).max()
    ll = low.rolling(_CHOP_N).min()
    tr_sum = tr.rolling(_CHOP_N).sum()
    rng = (hh - ll).replace(0, pd.NA)
    ratio = (tr_sum / rng).astype(float)
    chop = 100.0 * ratio.apply(lambda v: math.log10(v) if pd.notna(v) and v > 0 else float("nan"))
    chopv = float(chop.iloc[-1])

    hh20 = float(high.rolling(20).max().shift(1).iloc[-1])
    ll20 = float(low.rolling(20).min().shift(1).iloc[-1])
    ema200 = close.ewm(span=200, adjust=False).mean()
    s200 = float(ema200.iloc[-1])
    if any(math.isnan(v) for v in (a, chopv, hh20, ll20, s200)) or a <= 0:
        return _none()

    if chopv < _CHOP_MAX:
        if c > hh20 and c > s200:
            sl = c - _ATR_MULT * a
            tp = c + _TP_ATR * a
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
        if c < ll20 and c < s200:
            sl = c + _ATR_MULT * a
            tp = c - _TP_ATR * a
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
