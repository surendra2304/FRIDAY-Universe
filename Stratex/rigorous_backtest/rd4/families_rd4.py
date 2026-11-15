"""Volatility-regime trend family (TASK-STR-RD-004), as pre-declared.

Signals (events only, causal, warmup 260 bars):
  don20 / don55    close crosses the prior-N-bar Donchian channel edge
  ema12_48 / ema24_96   EMA(f) crosses EMA(s)

Regime state (causal, daily): bar ATR%(14) = ATR(14)/close; daily vol
V(d) = mean bar ATR% over UTC day d; regime rank for day d is
R(d) = #{k in [d-180, d-1] : V(k) <= V(d-1)} / 180 — yesterday's vol
level ranked against the prior 180 days. All bars of day d use R(d).
First usable day needs 181 days of history (earlier days -> NaN, and
regime modes take no entries on NaN days).

Modes:
  base     ungated control (f = 1)
  gate_hi  entries only when R(d) >= 0.50
  gate_lo  entries only when R(d) <  0.50
  scale    always enter; bracket multiples scaled by f = 0.75 + 0.5*R(d)

Exits are applied by sim_rd4 / fastsim: bracket SL 2.0 x ATR(14),
TP 4.0 x ATR(14) at the signal bar (x f in scale mode).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import atr, ema

WARMUP = 260
REGIME_DAYS = 180

SIGNALS = ("don20", "don55", "ema12_48", "ema24_96")
MODES = ("base", "gate_hi", "gate_lo", "scale")


def _entries(long_sig: pd.Series, short_sig: pd.Series,
             warmup: int = WARMUP) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    ls = long_sig.fillna(False).to_numpy(dtype=bool)
    ss = short_sig.fillna(False).to_numpy(dtype=bool)
    for i in range(warmup, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


def base_entries(df: pd.DataFrame, signal: str) -> list[tuple[int, str]]:
    """Ungated cross/breakout events for one signal spec."""
    close = df["close"]
    if signal.startswith("don"):
        n = int(signal[3:])
        hi = df["high"].rolling(n).max().shift(1)
        lo = df["low"].rolling(n).min().shift(1)
        long_sig = (close > hi) & (close.shift(1) <= hi.shift(1))
        short_sig = (close < lo) & (close.shift(1) >= lo.shift(1))
        return _entries(long_sig, short_sig)
    f, s = (int(x) for x in signal[3:].split("_"))
    ef, es = ema(close, f), ema(close, s)
    long_sig = (ef > es) & (ef.shift(1) <= es.shift(1))
    short_sig = (ef < es) & (ef.shift(1) >= es.shift(1))
    return _entries(long_sig, short_sig)


def regime_rank_by_bar(df: pd.DataFrame) -> np.ndarray:
    """Per-bar regime rank R(d) (float array, NaN where not yet usable)."""
    atr_pct = (atr(df, 14) / df["close"])
    daily = atr_pct.groupby(df.index.date).mean()
    V = daily.to_numpy(dtype=float)
    R = np.full(len(V), np.nan)
    for j in range(REGIME_DAYS + 1, len(V)):
        window = V[j - REGIME_DAYS:j]          # V[j-180 .. j-1]
        R[j] = float(np.mean(window <= V[j - 1]))
    rank_of_day = dict(zip(daily.index, R))
    return np.array([rank_of_day[d] for d in df.index.date], dtype=float)


def apply_mode(entries: list[tuple[int, str]], mode: str,
               rank_by_bar: np.ndarray) -> list[tuple[int, str, float]]:
    """Apply a regime mode to base entries -> (bar, side, bracket factor)."""
    out: list[tuple[int, str, float]] = []
    for i, side in entries:
        if mode == "base":
            out.append((i, side, 1.0))
            continue
        r = rank_by_bar[i]
        if not np.isfinite(r):
            continue
        if mode == "gate_hi":
            if r >= 0.50:
                out.append((i, side, 1.0))
        elif mode == "gate_lo":
            if r < 0.50:
                out.append((i, side, 1.0))
        elif mode == "scale":
            out.append((i, side, 0.75 + 0.5 * float(r)))
        else:
            raise ValueError(f"unknown mode {mode}")
    return out
