"""Order-flow PROXY families for TASK-STR-RD-012 — PRE-DECLARED.

No L2 / trade-level data exists in this programme, so every "order
flow" quantity here is a proxy computed from OHLCV bars only. The
formulas below are frozen by results_rd12/declaration.json before the
first cell runs; no variant, threshold, cell or exit spec may change
after the declaration PR.

Feature definitions (bar t, all causal — bars <= t only; O/H/L/C/V are
the bar's open/high/low/close/base-volume):

  CLV(t)  = (2C - H - L) / (H - L) if H > L else 0     (close location)
  SV1(t)  = sign(C - O) * V, sign(0) = 0               (directional vol)
  SV2(t)  = V * CLV(t)                                 (CLV-weighted vol)
  CVD_L(t)= sum of SV over the L bars ending at t (rolling, full window
            required). Windowed by construction: an infinite-history
            CVD is NOT reproducible in the live daemon and is never used.
  zV_m(t) = (V(t) - mean_m(V)) / std_m(V), rolling window m ending at
            t, std with ddof=1, full window required; zV = 0 when the
            window std is 0.
  ROC_n(t)= C(t) / C(t-n) - 1

Families (entries are (signal_bar, side) for rd.fastsim; a signal on
bar t enters at the open of bar t+1 under the harness MODULE
convention; one position at a time, entries inside an open position
are skipped by the simulator):

  cvd_momentum — CVD-slope/price agreement, CROSS form: the joint
    condition turning true at t (false at t-1) fires the entry.
      slope = CVD_L(t) - CVD_L(t-s); LONG iff slope > 0 and ROC_s > 0;
      SHORT iff slope < 0 and ROC_s < 0.
  vol_confirmed_momentum — Donchian breakout gated by volume surge
    (state form, the families2 donchian convention):
      LONG iff C(t) > max(H(t-n..t-1)) and zV_m(t) >= z*;
      SHORT iff C(t) < min(L(t-n..t-1)) and zV_m(t) >= z*.
  cvd_divergence — exhaustion reversal on flow non-confirmation
    (proxy fixed to SV2; state form):
      SHORT iff H(t) > max(H(t-n..t-1)) and CVD_L(t) < max(CVD_L(t-n..t-1));
      LONG  iff L(t) < min(L(t-n..t-1)) and CVD_L(t) > min(CVD_L(t-n..t-1)).
  vol_climax_reversal — volume-climax rejection reversal (state form):
      LONG  iff ROC_s(t) < 0 and zV_m(t) >= z* and CLV(t) >= +0.5;
      SHORT iff ROC_s(t) > 0 and zV_m(t) >= z* and CLV(t) <= -0.5.

Warmup: 260 bars (harness convention) for every cell.

Mappability: every quantity above is a pure function of OHLCV bar
history — the live daemon's kline feed (Stratex/autonomy/
async_pipeline.py get_klines) carries exactly open/high/low/close/
volume, so each config below is computable identically in the daemon
(its lookback need is <= 260 bars; the feed's limit parameter must be
set >= 300 by whoever wires a passer — a wiring note, not a formula
change). Variants needing taker-buy volume, quote volume or true
trade-level delta are UNMAPPABLE on that feed, are excluded from this
grid by construction, and are named in the declaration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WARMUP = 260

BRACKET_2_3 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 3.0}
BRACKET_TIME_DIV = {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 2.0,
                    "max_bars_by_tf": {"15m": 24, "1h": 12}}
BRACKET_TIME_VCL = {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 2.5,
                    "max_bars_by_tf": {"15m": 24, "1h": 12}}

CELLS = [("crypto30", "15m"), ("crypto30", "1h")]


def _entries(long_sig: pd.Series, short_sig: pd.Series, warmup: int):
    out = []
    ls = long_sig.fillna(False).to_numpy(dtype=bool)
    ss = short_sig.fillna(False).to_numpy(dtype=bool)
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


def _clv(df: pd.DataFrame) -> pd.Series:
    rng = df["high"] - df["low"]
    clv = (2.0 * df["close"] - df["high"] - df["low"]) / rng
    return clv.where(rng > 0, 0.0)


def signed_volume(df: pd.DataFrame, kind: str) -> pd.Series:
    if kind == "sv1":
        return np.sign(df["close"] - df["open"]) * df["volume"]
    if kind == "sv2":
        return df["volume"] * _clv(df)
    raise ValueError(kind)


def cvd(sv: pd.Series, window: int) -> pd.Series:
    return sv.rolling(window, min_periods=window).sum()


def vol_zscore(volume: pd.Series, window: int) -> pd.Series:
    mean = volume.rolling(window, min_periods=window).mean()
    std = volume.rolling(window, min_periods=window).std(ddof=1)
    z = (volume - mean) / std
    return z.where(std > 0, 0.0)


def sig_cvd_momentum(df: pd.DataFrame, proxy: str, window: int, slope_bars: int,
                     warmup: int):
    cv = cvd(signed_volume(df, proxy), window)
    slope = cv - cv.shift(slope_bars)
    roc = df["close"] / df["close"].shift(slope_bars) - 1.0
    long_state = (slope > 0) & (roc > 0)
    short_state = (slope < 0) & (roc < 0)
    long_sig = long_state & ~long_state.shift(1, fill_value=False)
    short_sig = short_state & ~short_state.shift(1, fill_value=False)
    return _entries(long_sig, short_sig, warmup)


def sig_vol_confirmed_momentum(df: pd.DataFrame, n: int, m: int, zstar: float,
                               warmup: int):
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    z = vol_zscore(df["volume"], m)
    return _entries((df["close"] > hi) & (z >= zstar),
                    (df["close"] < lo) & (z >= zstar), warmup)


def sig_cvd_divergence(df: pd.DataFrame, n: int, window: int, warmup: int):
    cv = cvd(signed_volume(df, "sv2"), window)
    new_high = df["high"] > df["high"].rolling(n).max().shift(1)
    new_low = df["low"] < df["low"].rolling(n).min().shift(1)
    cv_below_peak = cv < cv.rolling(n).max().shift(1)
    cv_above_trough = cv > cv.rolling(n).min().shift(1)
    return _entries(new_low & cv_above_trough, new_high & cv_below_peak,
                    warmup)


def sig_vol_climax(df: pd.DataFrame, m: int, zstar: float, s: int,
                   warmup: int):
    z = vol_zscore(df["volume"], m)
    roc = df["close"] / df["close"].shift(s) - 1.0
    clv = _clv(df)
    return _entries((roc < 0) & (z >= zstar) & (clv >= 0.5),
                    (roc > 0) & (z >= zstar) & (clv <= -0.5), warmup)


def build_configs_rd12() -> list[dict]:
    """The frozen RD-012 grid: 10 variants x 2 cells = 20 trials, plus
    one wf-select procedure per family x cell (8) = 28 trials total."""
    C: list[dict] = []

    def add(family, variant, kind, params, spec):
        C.append({"family": family, "variant": variant, "kind": kind,
                  "params": params, "spec": spec, "cells": list(CELLS)})

    add("cvd_momentum", "ofm_a", "cvd_momentum",
        {"proxy": "sv2", "window": 48, "slope_bars": 12}, BRACKET_2_3)
    add("cvd_momentum", "ofm_b", "cvd_momentum",
        {"proxy": "sv2", "window": 96, "slope_bars": 24}, BRACKET_2_3)
    add("cvd_momentum", "ofm_c", "cvd_momentum",
        {"proxy": "sv1", "window": 48, "slope_bars": 12}, BRACKET_2_3)
    add("vol_confirmed_momentum", "vcm_a", "vol_confirmed_momentum",
        {"n": 20, "m": 48, "zstar": 1.0}, BRACKET_2_3)
    add("vol_confirmed_momentum", "vcm_b", "vol_confirmed_momentum",
        {"n": 40, "m": 96, "zstar": 1.5}, BRACKET_2_3)
    add("vol_confirmed_momentum", "vcm_c", "vol_confirmed_momentum",
        {"n": 20, "m": 48, "zstar": 0.5}, BRACKET_2_3)
    add("cvd_divergence", "div_a", "cvd_divergence",
        {"n": 20, "window": 48}, BRACKET_TIME_DIV)
    add("cvd_divergence", "div_b", "cvd_divergence",
        {"n": 40, "window": 96}, BRACKET_TIME_DIV)
    add("vol_climax_reversal", "vcl_a", "vol_climax_reversal",
        {"m": 48, "zstar": 2.0, "s": 12}, BRACKET_TIME_VCL)
    add("vol_climax_reversal", "vcl_b", "vol_climax_reversal",
        {"m": 96, "zstar": 2.5, "s": 24}, BRACKET_TIME_VCL)
    return C
