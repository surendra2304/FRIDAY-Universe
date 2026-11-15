"""New pre-declared strategy families for TASK-STR-RD-003, Stage 2.

Declared in full in results_rd3/stage2_declaration.json and in
RESULTS_RD3.md BEFORE any Stage-2 cell was executed (the declaration
ships in its own PR, merged before the first Stage-2 run). Four
families, each grounded in a mechanism that RD-001/RD-002 did NOT
judge; none is a parameter re-skin of the crypto daily-trend cluster
(donchian / vol_adaptive / ts_momentum / macd / ichimoku), which the
programme treats as ONE correlated observation:

1. funding_extremes — perpetual-funding positioning (market
   structure). Funding prints are a positioning/crowding gauge no
   OHLCV family can see. Two claims: (a) FADE: extreme funding +
   price extended in the funding direction = crowded trade, fade it;
   (b) CARRY-SIGNAL: take the side that receives funding when the
   print is large, price-only judgement (funding cashflows are NOT
   added to returns — harness convention, declared; a price-only
   pass is therefore conservative for the carry claim).
2. overnight_drift — session return decomposition outside crypto.
   The 21:00->07:00 UTC window (NY close -> Europe open) is held
   outright (drift) or faded against its own previous window
   (session mean-reversion). Yahoo cash-index 1h has no overnight
   bars (RTH 13-21 UTC only), so indices are UNCOVERED for this
   mechanism and are not run.
3. btc_leadlag — cross-asset information diffusion in the crypto
   complex: BTC's trailing move predicts alt returns over the next
   k bars. BTC itself is never traded (trading it on its own move
   would be ts_momentum, already judged).
4. vol_regime_switch — volatility-regime-conditional strategy-class
   selection: breakout continuation in low ATR%-percentile regimes,
   z-score reversion in high regimes, flat between. The components
   were judged standalone; the claim under test is the SWITCH.

All signals are causal: features at bar i use only data with
timestamps <= bar i's open; the harness fills at bar i+1's open.
Warmup 260 bars (RD-001/RD-002 convention) everywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import atr, ema
from ..rd2.families2 import sig_donchian, sig_zscore

BR24 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}


# ------------------------------------------------------- funding family

def funding_features(prints: pd.DataFrame, bars_index: pd.DatetimeIndex,
                     pct_window: int = 540) -> pd.DataFrame:
    """Per-bar funding state from the print series (causal asof).

    prints: DataFrame indexed by print time (UTC) with column 'rate'.
    Returns a frame on bars_index with: last_rate, mean3 (mean of the
    last 3 prints), pct (trailing-pct_window-print percentile rank of
    the last print, in [0,1]), hist_days (days since the first print),
    print_age_h (hours since the last print at the bar open).
    """
    p = prints.sort_index()
    rate = p["rate"]
    mean3 = rate.rolling(3).mean()

    def _rank(w: pd.Series) -> float:
        return float((w.to_numpy() <= w.iloc[-1]).mean())

    pct = rate.rolling(pct_window, min_periods=60).apply(_rank, raw=False)
    feat = pd.DataFrame({
        "last_rate": rate, "mean3": mean3, "pct": pct,
        "print_time": p.index,
        "hist_days": (p.index - p.index[0]).days
                     + (p.index - p.index[0]).seconds / 86400.0,
    })
    out = pd.merge_asof(
        pd.DataFrame({"bar": bars_index}), feat,
        left_on="bar", right_on="print_time", direction="backward")
    out.index = bars_index
    out["print_age_h"] = (out["bar"] - out["print_time"]).dt.total_seconds() / 3600.0
    return out


def sig_funding(df: pd.DataFrame, feat: pd.DataFrame, kind: str,
                pctl: float, thr: float, warmup: int):
    """Entries for the funding family. kind='fade' uses percentile +
    EMA50 extension filter; kind='carry' uses the raw print level."""
    close = df["close"]
    e50 = ema(close, 50)
    last = feat["last_rate"].to_numpy()
    pct = feat["pct"].to_numpy()
    hist = feat["hist_days"].to_numpy()
    age = feat["print_age_h"].to_numpy()
    cv = close.to_numpy()
    ev = e50.to_numpy()
    out = []
    for i in range(warmup, len(df)):
        if not np.isfinite(last[i]) or not np.isfinite(hist[i]):
            continue
        if hist[i] < 160.0 or age[i] > 24.0:
            continue  # declared gates: enough history, fresh print
        if kind == "fade":
            if not np.isfinite(pct[i]) or not np.isfinite(ev[i]):
                continue
            if pct[i] >= pctl and cv[i] > ev[i]:
                out.append((i, "SHORT"))
            elif pct[i] <= 1.0 - pctl and cv[i] < ev[i]:
                out.append((i, "LONG"))
        else:  # carry
            if last[i] > thr:
                out.append((i, "SHORT"))
            elif last[i] < -thr:
                out.append((i, "LONG"))
    return out


# ----------------------------------------------------- overnight family

def _overnight_returns(df: pd.DataFrame) -> pd.Series:
    """Completed overnight-window returns, indexed by completion time
    (the 07:00 bar). Window: open of the 21:00 bar -> close of the
    07:00 bar the next morning (11 bars later on a full 24h grid)."""
    idx = df.index
    pos = {t: i for i, t in enumerate(idx)}
    rec = {}
    for i, t in enumerate(idx):
        if t.hour == 21:
            end_t = t + pd.Timedelta(hours=10)
            j = pos.get(end_t)
            if j is not None and idx[j].hour == 7:
                rec[idx[j]] = df["close"].iloc[j] / df["open"].iloc[i] - 1.0
    return pd.Series(rec).sort_index()


def sig_overnight(df: pd.DataFrame, kind: str, warmup: int):
    """Signal bars are the 20:00 bars (fill at the 21:00 open)."""
    hours = df.index.hour.to_numpy()
    prev = _overnight_returns(df)
    out = []
    for i in range(warmup, len(df) - 1):
        if hours[i] != 20:
            continue
        if kind == "drift":
            out.append((i, "LONG"))
        else:  # fade: opposite of the previous completed window
            done = prev[prev.index <= df.index[i]]
            if len(done) == 0:
                continue
            r = float(done.iloc[-1])
            if r > 0:
                out.append((i, "SHORT"))
            elif r < 0:
                out.append((i, "LONG"))
    return out


# ------------------------------------------------------- leadlag family

def sig_leadlag(alt: pd.DataFrame, btc: pd.DataFrame, k: int,
                theta: float, warmup: int):
    """Entries for one alt from BTC's trailing k-bar move, scaled by
    BTC's ATR% (14). BTC features are mapped onto the alt's bars by
    asof (tolerance 65 min) — only information available at the alt
    bar's open is used."""
    broc = btc["close"] / btc["close"].shift(k) - 1.0
    batrp = atr(btc, 14) / btc["close"]
    feat = pd.DataFrame({"roc": broc, "atrp": batrp,
                         "t": btc.index}).dropna()
    bars = pd.DataFrame({"t": alt.index})
    m = pd.merge_asof(bars, feat, on="t", direction="backward",
                      tolerance=pd.Timedelta(minutes=65))
    roc = m["roc"].to_numpy()
    atrp = m["atrp"].to_numpy()
    out = []
    for i in range(warmup, len(alt)):
        if not np.isfinite(roc[i]) or not np.isfinite(atrp[i]) or atrp[i] <= 0:
            continue
        if roc[i] > theta * atrp[i]:
            out.append((i, "LONG"))
        elif roc[i] < -theta * atrp[i]:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------- vol-switch family

def sig_volswitch(df: pd.DataFrame, lo: float, hi: float, warmup: int):
    """Returns (breakout_entries, reversion_entries): donchian-20
    breakouts on bars whose ATR%-percentile rank <= lo; z-score(20,
    2.0) reversion crossings on bars with rank >= hi."""
    atrp = atr(df, 14) / df["close"]
    rank = atrp.rolling(200).rank(pct=True).to_numpy()
    brk = [(i, s) for i, s in sig_donchian(df, 20, warmup)
           if np.isfinite(rank[i]) and rank[i] <= lo]
    rev = [(i, s) for i, s in sig_zscore(df, 20, 2.0, False, warmup)
           if np.isfinite(rank[i]) and rank[i] >= hi]
    return brk, rev


# ---------------------------------------------------------------- registry

def build_configs_rd3() -> list[dict]:
    C: list[dict] = []
    # funding_extremes: 4 variants x {crypto30 4h, crypto30 1d}
    for vname, kind, pctl, thr in (("fade_p90", "fade", 0.90, None),
                                   ("fade_p95", "fade", 0.95, None),
                                   ("carry_1bp", "carry", None, 0.0001),
                                   ("carry_3bp", "carry", None, 0.0003)):
        spec = BR24 if kind == "fade" else {
            "type": "bracket_time", "sl_atr": 3.0, "tp_atr": 6.0,
            "max_bars_by_tf": {"4h": 6, "1d": 3}}
        C.append({"family": "funding_extremes", "variant": vname,
                  "kind": "funding", "sig_kind": kind, "pctl": pctl,
                  "thr": thr, "spec": spec,
                  "cells": [("crypto30", "4h"), ("crypto30", "1d")]})
    # overnight_drift: 2 variants x {forex12 1h, comm7 1h}
    for vname, kind in (("drift_long", "drift"), ("drift_fade", "fade")):
        C.append({"family": "overnight_drift", "variant": vname,
                  "kind": "overnight", "sig_kind": kind,
                  "spec": {"type": "bracket_time", "sl_atr": 3.0,
                           "tp_atr": 6.0, "max_bars": 11},
                  "cells": [("forex12", "1h"), ("comm7", "1h")]})
    # btc_leadlag: 2 variants x {crypto12 1h, crypto30 1h}
    for vname, k, theta in (("lag4_t1.0", 4, 1.0), ("lag12_t1.5", 12, 1.5)):
        C.append({"family": "btc_leadlag", "variant": vname,
                  "kind": "leadlag", "k": k, "theta": theta,
                  "spec": {"type": "bracket_time", "sl_atr": 2.0,
                           "tp_atr": 4.0, "max_bars": k},
                  "cells": [("crypto12", "1h"), ("crypto30", "1h")]})
    # vol_regime_switch: 2 variants x 4 cells
    for vname, lo, hi in (("switch_a", 0.35, 0.65), ("switch_b", 0.25, 0.75)):
        C.append({"family": "vol_regime_switch", "variant": vname,
                  "kind": "volswitch", "lo": lo, "hi": hi,
                  "spec": BR24,
                  "spec_rev": {"type": "bracket", "sl_atr": 2.0,
                               "tp_atr": 2.0},
                  "cells": [("crypto30", "4h"), ("crypto30", "1d"),
                            ("comm7", "1d"), ("forex28", "1d")]})
    return C
