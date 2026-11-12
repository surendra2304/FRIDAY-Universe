#!/usr/bin/env python3
"""strategy_kaufman_efficiency.py — Kaufman Efficiency Ratio trend entry.

Efficiency Ratio ER = |net move over N| / sum(|bar-to-bar moves|) measures
how "straight" price travel is. High ER = clean trend; low ER = noise.
This strategy buys/sells only when ER confirms directional efficiency,
skipping the noisy regimes where trend systems bleed.

Entry : BUY  ER(20) > 0.30 and 21-bar return > 0 and close > EMA200
        SELL ER(20) > 0.30 and 21-bar return < 0 and close < EMA200
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
_ER_N = 20
_ER_MIN = 0.30
_MOM_N = 21


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
    if c <= 0 or len(close) <= _ER_N:
        return _none()

    # Efficiency ratio
    moves = close.diff().abs()
    denom = float(moves.rolling(_ER_N).sum().iloc[-1])
    net = abs(c - float(close.iloc[-1 - _ER_N]))
    er = net / denom if denom > 0 else 0.0

    mom = c / float(close.iloc[-1 - _MOM_N]) - 1.0

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(20).mean()
    a = float(atr.iloc[-1])
    ema200 = close.ewm(span=200, adjust=False).mean()
    s200 = float(ema200.iloc[-1])
    if any(math.isnan(v) for v in (a, s200)) or a <= 0:
        return _none()

    if er > _ER_MIN:
        if mom > 0 and c > s200:
            sl = c - _ATR_MULT * a
            tp = c + _TP_ATR * a
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, c - sl, tp - c)
        if mom < 0 and c < s200:
            sl = c + _ATR_MULT * a
            tp = c - _TP_ATR * a
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO, sl - c, c - tp)
    return _none()
