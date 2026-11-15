"""Forex-native strategy families for TASK-STR-RD-003, Stage 2B
(owner scope extension 2026-11-15 ~12:19 IST: 'Stratex should also
take trades in OANDA and it should create strategies using that
also').

Declared in full in results_rd3/stage2b_declaration.json and in
RESULTS_RD3.md BEFORE any Stage-2B cell was executed (declaration
ships in its own PR, merged before the first Stage-2B run).

Venue design: OANDA practice instruments (FX majors/minors + XAU/USD
inside the comm7 panel), OANDA session structure, and RD-002's
OANDA-modelled costs (majors 6 bps RT, minors 10, GOLD 10). Data:
RD-002's provenanced Yahoo FX/commodity series via rd2.panels — the
OANDA practice price API is not reachable from the research sandbox
(no venue credentials in this environment), stated plainly in the
declaration; the forward lane (TASK-STR-FWD-004) supplies live
OANDA evidence for anything that survives.

Three families, each an FX market-structure mechanism that no judged
family implements (breakout/momentum-cross/reversion-cross entries
were the judged entry types; none of these is a re-skin, and neither
SMT-v2 nor FX-MR-v4 logic is re-tested):

1. london_drive — Asia-range -> London-expansion: the 00:00-07:00
   UTC Asia range is set in thin trade; a 07:00-bar close outside it,
   held into the London session, is the FX day's primary liquidity
   event. FX session structure does not exist in crypto panels.
2. monday_gap_fade — the Friday->Monday gap is an FX-specific
   artefact (weekend closure + Monday repricing); gaps beyond a
   fraction of ATR are faded over the following days. Distinct from
   dow_effect (weekday return patterns on crypto, no gap conditioning).
   DECLARED DEVIATION: entries are decided at Monday's open from the
   gap itself and filled at that open (open-auction semantics) —
   the only family in the programme using open-known information.
3. trend_pullback — FX trend persistence traded on RETRACEMENT
   entries (first EMA20 touch-and-reclaim inside an EMA100/200
   trend), an entry type no judged family uses (all judged trend
   entries are breakouts or crosses).

Causality otherwise follows the programme convention: features at
bar i use data <= close of bar i; fills at bar i+1's open. Warmup
260 bars everywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import atr, ema


def sig_london_drive(df: pd.DataFrame, narrow: bool, warmup: int):
    hours = df.index.hour.to_numpy()
    dates = df.index.date
    asia = df[hours < 7].groupby(dates[hours < 7]).agg(
        asia_high=("high", "max"), asia_low=("low", "min"),
        n=("high", "size"))
    a = atr(df, 14).to_numpy(dtype=float)
    close = df["close"].to_numpy()
    out = []
    for i in range(warmup, len(df)):
        if hours[i] != 7:
            continue
        row = asia.loc[dates[i]] if dates[i] in asia.index else None
        if row is None or int(row["n"]) < 4:
            continue
        if narrow:
            width = float(row["asia_high"] - row["asia_low"])
            if not np.isfinite(a[i]) or width >= 1.0 * a[i]:
                continue
        if close[i] > float(row["asia_high"]):
            out.append((i, "LONG"))
        elif close[i] < float(row["asia_low"]):
            out.append((i, "SHORT"))
    return out


def sig_monday_gap(df: pd.DataFrame, theta: float, warmup: int):
    """Signal bar is the FRIDAY bar; the gap is measured at the next
    bar's (Monday's) open and the fill is that same open (declared
    open-auction semantics)."""
    idx = df.index
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    a = atr(df, 14).to_numpy(dtype=float)
    out = []
    for i in range(warmup, len(df) - 1):
        j = i + 1
        if idx[j].dayofweek != 0 or (idx[j] - idx[i]).days < 2:
            continue
        if not np.isfinite(a[i]) or closes[i] <= 0:
            continue
        gap = opens[j] / closes[i] - 1.0
        atrp = a[i] / closes[i]
        if gap > theta * atrp:
            out.append((i, "SHORT"))
        elif gap < -theta * atrp:
            out.append((i, "LONG"))
    return out


def sig_trend_pullback(df: pd.DataFrame, ema_trend: int, warmup: int):
    close = df["close"]
    et = ema(close, ema_trend)
    e20 = ema(close, 20)
    slope = et - et.shift(10)
    cv = close.to_numpy()
    ov = df["open"].to_numpy()
    lv = df["low"].to_numpy()
    hv = df["high"].to_numpy()
    etv, e20v, slv = et.to_numpy(), e20.to_numpy(), slope.to_numpy()
    out = []
    for i in range(warmup, len(df)):
        if not (np.isfinite(etv[i]) and np.isfinite(e20v[i])
                and np.isfinite(slv[i])):
            continue
        if cv[i] > etv[i] and slv[i] > 0:  # uptrend
            if lv[i] <= e20v[i] * 1.001 and cv[i] > e20v[i] \
                    and cv[i] > ov[i]:
                out.append((i, "LONG"))
        elif cv[i] < etv[i] and slv[i] < 0:  # downtrend
            if hv[i] >= e20v[i] * 0.999 and cv[i] < e20v[i] \
                    and cv[i] < ov[i]:
                out.append((i, "SHORT"))
    return out


def build_configs_fx() -> list[dict]:
    C: list[dict] = []
    for vname, narrow in (("drive_plain", False), ("drive_narrow", True)):
        C.append({"family": "london_drive", "variant": vname,
                  "kind": "london", "narrow": narrow,
                  "spec": {"type": "bracket_time", "sl_atr": 2.0,
                           "tp_atr": 4.0, "max_bars": 9},
                  "cells": [("forex12", "1h"), ("comm7", "1h")]})
    for vname, theta in (("gap_0.5", 0.5), ("gap_1.0", 1.0)):
        C.append({"family": "monday_gap_fade", "variant": vname,
                  "kind": "gap", "theta": theta,
                  "spec": {"type": "bracket_time", "sl_atr": 2.0,
                           "tp_atr": 3.0, "max_bars": 3},
                  "cells": [("forex28", "1d"), ("comm7", "1d")]})
    for vname, et in (("pb_ema100", 100), ("pb_ema200", 200)):
        C.append({"family": "trend_pullback", "variant": vname,
                  "kind": "pullback", "ema_trend": et,
                  "spec": {"type": "trail", "sl_atr": 2.0,
                           "trail_atr": 3.0},
                  "cells": [("forex28", "1d"), ("forex12", "4h"),
                            ("comm7", "1d")]})
    return C
