"""Signal generators for TASK-STR-RD-007 (gold & commodities intraday).

Every function implements EXACTLY the rules pre-declared in
``results_rd7/declaration.json`` — no parameter here may change after the
declaration PR. Generators return entries as (signal_bar_index, side);
simulation is the harness's rd.fastsim MODULE convention (signal on the
close of bar i -> entry at the open of bar i+1, entry-anchored ATR
brackets, one position at a time).

All times are UTC (the series index is UTC). Warmup is 260 bars for
every family (the RD-003 declaration convention).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import adx, atr, ema, rsi

WARMUP = 260


def _frame(df: pd.DataFrame) -> dict:
    """Precomputed per-bar arrays shared by the families."""
    idx = df.index
    return {
        "open": df["open"].to_numpy(dtype=float),
        "high": df["high"].to_numpy(dtype=float),
        "low": df["low"].to_numpy(dtype=float),
        "close": df["close"].to_numpy(dtype=float),
        "volume": np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0),
        "hour": np.asarray(idx.hour),
        "day": np.asarray(idx.normalize()),
        "atr": atr(df, 14).to_numpy(dtype=float),
    }


def _day_groups(day: np.ndarray) -> list[tuple[int, int]]:
    """(start, end_exclusive) index spans per distinct UTC date, in order."""
    out = []
    n = len(day)
    start = 0
    for i in range(1, n + 1):
        if i == n or day[i] != day[start]:
            out.append((start, i))
            start = i
    return out


# ---------------------------------------------------------------- F1: ORB
def sig_orb(df: pd.DataFrame, narrow: bool) -> list[tuple[int, str]]:
    """NY opening-range breakout (declaration family orb_breakout)."""
    f = _frame(df)
    entries: list[tuple[int, str]] = []
    for start, end in _day_groups(f["day"]):
        hours = f["hour"][start:end]
        pos13 = np.nonzero(hours == 13)[0]
        pos14 = np.nonzero(hours == 14)[0]
        if len(pos13) == 0 or len(pos14) == 0:
            continue  # both range bars must be present
        ridx = np.concatenate([pos13, pos14]) + start
        orh = float(f["high"][ridx].max())
        orl = float(f["low"][ridx].min())
        width = orh - orl
        for i in range(start, end):
            if i < WARMUP or f["hour"][i] not in (15, 16, 17, 18):
                continue
            a = f["atr"][i]
            if not np.isfinite(a) or a <= 0:
                continue
            if narrow and width > 1.5 * a:
                continue
            if f["close"][i] > orh:
                entries.append((i, "LONG"))
                break
            if f["close"][i] < orl:
                entries.append((i, "SHORT"))
                break
    return entries


# ------------------------------------------------------- F2: prev-day break
def sig_prevday(df: pd.DataFrame, ema_filter: bool) -> list[tuple[int, str]]:
    """Prior-trading-day range breakout, intraday (family prevday_breakout)."""
    f = _frame(df)
    e200 = ema(df["close"], 200).to_numpy(dtype=float)
    groups = _day_groups(f["day"])
    stats = []
    for start, end in groups:
        stats.append((start, end, float(f["high"][start:end].max()),
                      float(f["low"][start:end].min()), end - start))
    entries: list[tuple[int, str]] = []
    for g, (start, end, _h, _l, _n) in enumerate(stats):
        # previous trading date present in the series with >= 12 bars
        pdh = pdl = None
        for k in range(g - 1, -1, -1):
            if stats[k][4] >= 12:
                pdh, pdl = stats[k][2], stats[k][3]
                break
        if pdh is None:
            continue
        for i in range(start, end):
            if i < WARMUP or not (8 <= f["hour"][i] <= 18):
                continue
            c = f["close"][i]
            if c > pdh:
                if ema_filter and not (np.isfinite(e200[i]) and c > e200[i]):
                    continue
                entries.append((i, "LONG"))
                break
            if c < pdl:
                if ema_filter and not (np.isfinite(e200[i]) and c < e200[i]):
                    continue
                entries.append((i, "SHORT"))
                break
    return entries


# --------------------------------------------------------- F3: VWAP fade
def sig_vwap(df: pd.DataFrame, k: float) -> list[tuple[int, str]]:
    """Session-VWAP stretch fade (family vwap_reversion)."""
    f = _frame(df)
    typical = (f["high"] + f["low"] + f["close"]) / 3.0
    vol = np.where(f["volume"] > 0, f["volume"], 0.0)
    vwap = np.full(len(df), np.nan)
    for start, end in _day_groups(f["day"]):
        cv = np.cumsum(vol[start:end])
        ctv = np.cumsum(typical[start:end] * vol[start:end])
        with np.errstate(invalid="ignore", divide="ignore"):
            seg = np.where(cv > 0, ctv / np.where(cv > 0, cv, 1.0), np.nan)
        vwap[start:end] = seg
    entries: list[tuple[int, str]] = []
    for i in range(len(df)):
        if i < WARMUP or not (9 <= f["hour"][i] <= 18):
            continue
        a, v = f["atr"][i], vwap[i]
        if not (np.isfinite(a) and a > 0 and np.isfinite(v)):
            continue
        d = (f["close"][i] - v) / a
        if d >= k:
            entries.append((i, "SHORT"))
        elif d <= -k:
            entries.append((i, "LONG"))
    return entries


# ---------------------------------------------------- F4: Bollinger + RSI
def sig_bb_rsi(df: pd.DataFrame, adx_filter: bool) -> list[tuple[int, str]]:
    """Bollinger(20,2) + RSI(14) extreme fade (family bb_rsi_reversion)."""
    f = _frame(df)
    close = df["close"]
    mid = close.rolling(20).mean().to_numpy(dtype=float)
    sd = close.rolling(20).std(ddof=1).to_numpy(dtype=float)
    r = rsi(close, 14).to_numpy(dtype=float)
    ax = adx(df, 14).to_numpy(dtype=float) if adx_filter else None
    entries: list[tuple[int, str]] = []
    for i in range(len(df)):
        if i < WARMUP or not (8 <= f["hour"][i] <= 18):
            continue
        if not (np.isfinite(mid[i]) and np.isfinite(sd[i])
                and np.isfinite(r[i])):
            continue
        if adx_filter and not (np.isfinite(ax[i]) and ax[i] < 25.0):
            continue
        c = f["close"][i]
        if c > mid[i] + 2.0 * sd[i] and r[i] >= 70.0:
            entries.append((i, "SHORT"))
        elif c < mid[i] - 2.0 * sd[i] and r[i] <= 30.0:
            entries.append((i, "LONG"))
    return entries


# ------------------------------------------------------- F5: Donchian 1h
def sig_donchian(df: pd.DataFrame, ema_filter: bool) -> list[tuple[int, str]]:
    """Intraday Donchian(20) breakout, session-filtered (donchian_intra)."""
    f = _frame(df)
    hh = df["high"].rolling(20).max().shift(1).to_numpy(dtype=float)
    ll = df["low"].rolling(20).min().shift(1).to_numpy(dtype=float)
    e200 = ema(df["close"], 200).to_numpy(dtype=float)
    entries: list[tuple[int, str]] = []
    for i in range(len(df)):
        if i < WARMUP or not (8 <= f["hour"][i] <= 18):
            continue
        if not (np.isfinite(hh[i]) and np.isfinite(ll[i])):
            continue
        c = f["close"][i]
        if c > hh[i]:
            if ema_filter and not (np.isfinite(e200[i]) and c > e200[i]):
                continue
            entries.append((i, "LONG"))
        elif c < ll[i]:
            if ema_filter and not (np.isfinite(e200[i]) and c < e200[i]):
                continue
            entries.append((i, "SHORT"))
    return entries


# ------------------------------------------------------------- registry
# (family, variant, signal_fn, exit_spec) — exit specs exactly as declared.
CONFIGS: list[dict] = [
    {"family": "orb_breakout", "variant": "orb_plain",
     "fn": lambda df: sig_orb(df, narrow=False),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0}},
    {"family": "orb_breakout", "variant": "orb_narrow",
     "fn": lambda df: sig_orb(df, narrow=True),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0}},
    {"family": "prevday_breakout", "variant": "pd_plain",
     "fn": lambda df: sig_prevday(df, ema_filter=False),
     "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 3.0}},
    {"family": "prevday_breakout", "variant": "pd_ema",
     "fn": lambda df: sig_prevday(df, ema_filter=True),
     "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 3.0}},
    {"family": "vwap_reversion", "variant": "vwap_15",
     "fn": lambda df: sig_vwap(df, k=1.5),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 1.5}},
    {"family": "vwap_reversion", "variant": "vwap_20",
     "fn": lambda df: sig_vwap(df, k=2.0),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 1.5}},
    {"family": "bb_rsi_reversion", "variant": "bbr_pure",
     "fn": lambda df: sig_bb_rsi(df, adx_filter=False),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 2.0}},
    {"family": "bb_rsi_reversion", "variant": "bbr_adx",
     "fn": lambda df: sig_bb_rsi(df, adx_filter=True),
     "spec": {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 2.0}},
    {"family": "donchian_intra", "variant": "dc_plain",
     "fn": lambda df: sig_donchian(df, ema_filter=False),
     "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0}},
    {"family": "donchian_intra", "variant": "dc_ema",
     "fn": lambda df: sig_donchian(df, ema_filter=True),
     "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0}},
]
