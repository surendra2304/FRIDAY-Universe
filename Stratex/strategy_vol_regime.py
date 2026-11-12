#!/usr/bin/env python3
"""strategy_vol_regime.py — dual-mode: breakout in high vol, mean-reversion in low vol.

Regime: realized vol percentile (90d lookback) of daily returns.
  high  (>70th pct): trade breakouts of the 10d range WITH the move
  low   (<30th pct): fade 2-sigma Bollinger excursions back to the mean
  mid:              no signal (regime unclear)

This addresses the well-documented failure of running a single style across
both regimes. SL/TP adapt per mode: breakout trades trail wide (2.5 ATR),
reversion trades target the mid-band quickly (1.5 ATR).
"""
from __future__ import annotations
import math
from collections import namedtuple
import pandas as pd


class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio", "sl_dist", "tp_dist"], defaults=(None, None))):
    @property
    def confidence(self):
        return self.win_rate_prior


_STRATEGY_TYPE = "HYBRID"
_OOS_WIN_RATE_PRIOR = 0.50
_RR_RATIO = 2.0


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
    if df is None or len(df) < 120:
        return _none()
    work = _drop_forming_bar(df)
    if len(work) < 110:
        return _none()
    if not {"close", "high", "low"}.issubset(work.columns):
        return _none()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)

    ret = close.pct_change()
    vol = ret.rolling(14).std()
    vol_pct = vol.rolling(90).rank(pct=True)  # percentile of current vol

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    vp = float(vol_pct.iloc[-1])
    if any(math.isnan(v) for v in (a, vp)) or a <= 0 or c <= 0:
        return _none()

    if vp > 0.70:
        # HIGH VOL: breakout mode
        hh = float(high.rolling(10).max().shift(1).iloc[-1])
        ll = float(low.rolling(10).min().shift(1).iloc[-1])
        if c > hh:
            sl = c - 2.5 * a
            tp = c + 2.5 * a
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, 0.42, 1.0, c - sl, tp - c)
        if c < ll:
            sl = c + 2.5 * a
            tp = c - 2.5 * a
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, 0.42, 1.0, sl - c, c - tp)
        return _none()

    if vp < 0.30:
        # LOW VOL: mean-reversion mode
        ma = close.rolling(20).mean()
        sd = close.rolling(20).std()
        m, s = float(ma.iloc[-1]), float(sd.iloc[-1])
        if s <= 0:
            return _none()
        z = (c - m) / s
        if z < -2.0:
            sl = c - 1.5 * a
            tp = m
            if tp <= c:
                return _none()
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, 0.58, 1.2, c - sl, tp - c)
        if z > 2.0:
            sl = c + 1.5 * a
            tp = m
            if tp >= c:
                return _none()
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, 0.58, 1.2, sl - c, c - tp)
    return _none()
