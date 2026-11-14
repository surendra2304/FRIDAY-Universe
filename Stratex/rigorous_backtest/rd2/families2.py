"""Strategy configurations for the TASK-STR-RD-002 mega-grid.

Two blocks, both PRE-DECLARED here before any RD-002 run:

(A) RD-001 batch-1 families (rd/stage3.py) generalized across timeframes
    and asset panels. Signal logic is re-implemented with a parameterized
    warmup (stage3 hardcodes 260 bars, which would erase weekly panels);
    the logic itself is line-faithful to stage3 and is validated against
    RD-001's published roc42_4h row before the grid runs (see
    results_rd2/sanity_checks.json).

(B) Batch-2 families, new in RD-002: cross-sectional momentum,
    dual-momentum TS trend, filtered turtle, vol-adaptive bracket trend,
    filtered mean reversion, day-of-week effects, crypto pairs stat-arb.
    The forex carry family is UNTESTABLE (no provenance-honest
    historical swap/rate-differential series is obtainable from the
    programme's sources) and is recorded as such, not approximated.

Judgement unit = (config, panel, timeframe). Every cell the runner
attempts increments the global trial counter, whatever its outcome.

Warmup: 260 bars (RD-001 convention) except 1wk, where 104 bars
(~2 years of weeks) is the declared equivalent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import adx, atr, ema, rsi

WARMUP = 260
WARMUP_1WK = 104


def warmup_for(tf: str) -> int:
    return WARMUP_1WK if tf == "1wk" else WARMUP


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


# ------------------------------------------------------- (A) RD-001 batch 1

def sig_donchian(df, n, warmup):
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    return _entries(df["close"] > hi, df["close"] < lo, warmup)


def sig_zscore(df, w, theta, use_filter, warmup):
    mid = df["close"].rolling(w).mean()
    sd = df["close"].rolling(w).std()
    z = (df["close"] - mid) / sd
    prev = z.shift(1)
    long_sig = (prev >= -theta) & (z < -theta)
    short_sig = (prev <= theta) & (z > theta)
    if use_filter:
        ok = adx(df, 14) < 25
        long_sig &= ok
        short_sig &= ok
    return _entries(long_sig, short_sig, warmup)


def sig_vol_trend(df, fast, slow, gate, warmup):
    f = ema(df["close"], fast)
    s = ema(df["close"], slow)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1))
    short_sig = (f < s) & (f.shift(1) >= s.shift(1))
    if gate:
        atrp = atr(df, 14) / df["close"]
        pct = atrp.rolling(200).rank(pct=True)
        ok = (pct >= 0.2) & (pct <= 0.8)
        long_sig &= ok
        short_sig &= ok
    return _entries(long_sig, short_sig, warmup)


def sig_mtf(df, aux, aux_minutes, warmup):
    f = ema(df["close"], 20)
    s = ema(df["close"], 50)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1))
    short_sig = (f < s) & (f.shift(1) >= s.shift(1))
    if aux is not None:
        e50 = ema(aux["close"], 50)
        trend_up = aux["close"] > e50
        # an aux bar opening at T is fully known at T + aux_minutes
        trend = pd.Series(trend_up.to_numpy(),
                          index=aux.index + pd.Timedelta(minutes=aux_minutes))
        bar_close = df.index + pd.Timedelta(minutes=1)  # aligned below
        # align by each bar's close time: use the df's own step
        step = (df.index[1] - df.index[0]) if len(df) > 1 else pd.Timedelta(hours=1)
        closes = df.index + step
        aligned = trend.reindex(closes, method="ffill")
        aligned.index = df.index
        aligned = aligned.fillna(False)
        long_sig &= aligned
        short_sig &= ~aligned
    return _entries(long_sig, short_sig, warmup)


def sig_mtf_native(df, warmup):
    f = ema(df["close"], 20)
    s = ema(df["close"], 50)
    d = ema(df["close"], 200)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1)) & (df["close"] > d)
    short_sig = (f < s) & (f.shift(1) >= s.shift(1)) & (df["close"] < d)
    return _entries(long_sig, short_sig, warmup)


def sig_volume_breakout(df, confirm, warmup):
    hi = df["high"].rolling(20).max().shift(1)
    lo = df["low"].rolling(20).min().shift(1)
    long_sig = df["close"] > hi
    short_sig = df["close"] < lo
    if confirm is not None:
        vma = df["volume"].rolling(20).mean()
        ok = df["volume"] > confirm * vma
        long_sig &= ok
        short_sig &= ok
    return _entries(long_sig, short_sig, warmup)


def sig_ts_momentum(df, lookback, warmup):
    roc = df["close"] / df["close"].shift(lookback) - 1.0
    long_sig = (roc > 0) & (roc.shift(1) <= 0)
    short_sig = (roc < 0) & (roc.shift(1) >= 0)
    return _entries(long_sig, short_sig, warmup)


def sig_session(df, kind, warmup):
    out = []
    hours = df.index.hour.to_numpy()
    closes = df["close"].to_numpy()
    opens = df["open"].to_numpy()
    a = atr(df, 14).to_numpy()
    n = len(df)
    if kind == "london_momentum":
        for i in range(warmup, n - 1):
            if hours[i] == 8:
                move = closes[i] - opens[i]
                if move > 0:
                    out.append((i, "LONG"))
                elif move < 0:
                    out.append((i, "SHORT"))
    elif kind == "ny_reversal":
        for i in range(warmup, n - 1):
            if hours[i] == 14:
                j = i - 6
                if j < 0 or hours[j] != 8:
                    continue
                move = closes[i] - opens[j]
                if a[i] > 0 and move > 1.0 * a[i]:
                    out.append((i, "SHORT"))
                elif a[i] > 0 and move < -1.0 * a[i]:
                    out.append((i, "LONG"))
    return out


# --------------------------------------------------------- (B) batch 2 (new)

def sig_dual_momentum(df, lookback, warmup):
    roc = df["close"] / df["close"].shift(lookback) - 1.0
    e200 = ema(df["close"], 200)
    long_sig = (roc > 0) & (roc.shift(1) <= 0) & (df["close"] > e200)
    short_sig = (roc < 0) & (roc.shift(1) >= 0) & (df["close"] < e200)
    return _entries(long_sig, short_sig, warmup)


def sig_turtle2(df, n, use_filter, warmup):
    entries = sig_donchian(df, n, warmup)
    if not use_filter:
        return entries
    e200 = ema(df["close"], 200)
    close = df["close"].to_numpy()
    ev = e200.to_numpy()
    return [(i, s) for (i, s) in entries
            if (s == "LONG" and close[i] > ev[i])
            or (s == "SHORT" and close[i] < ev[i])]


def sig_voltrend2(df, fast, slow, warmup):
    f = ema(df["close"], fast)
    s = ema(df["close"], slow)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1))
    short_sig = (f < s) & (f.shift(1) >= s.shift(1))
    return _entries(long_sig, short_sig, warmup)


def atr_vol_scaled(df):
    """ATR series rescaled by the rolling vol regime (voltrend2's
    bracket geometry): quiet regimes get wider ATR-multiples in price
    terms, wild regimes tighter — bracket distance tracks a target
    ATR-percentile, not the spot ATR."""
    a = atr(df, 14)
    atrp = a / df["close"]
    med = atrp.rolling(200).median()
    factor = (med / atrp).clip(0.5, 1.75)
    return (a * factor).to_numpy(dtype=float)


def sig_rsi2_filt(df, warmup):
    r = rsi(df["close"], 2)
    e200 = ema(df["close"], 200)
    long_sig = (r < 10) & (df["close"] > e200)
    short_sig = (r > 90) & (df["close"] < e200)
    return _entries(long_sig, short_sig, warmup)


def sig_bb_revert(df, warmup):
    mid = df["close"].rolling(20).mean()
    sd = df["close"].rolling(20).std()
    upper, lower = mid + 2 * sd, mid - 2 * sd
    ok = adx(df, 14) < 25
    long_sig = (df["close"] < lower) & ok
    short_sig = (df["close"] > upper) & ok
    return _entries(long_sig, short_sig, warmup)


def sig_dow(df, kind, warmup):
    out = []
    wd = df.index.weekday.to_numpy()
    roc5 = (df["close"] / df["close"].shift(5) - 1.0).to_numpy()
    for i in range(warmup, len(df) - 1):
        if wd[i] != 0 or np.isnan(roc5[i]):  # Monday entries only
            continue
        mom = roc5[i] > 0
        if kind == "momentum":
            out.append((i, "LONG" if mom else "SHORT"))
        else:
            out.append((i, "SHORT" if mom else "LONG"))
    return out


def xs_entries(panel_dfs: dict, lookback: int, rebalance: int, k: int,
               warmup: int):
    """Cross-sectional momentum: at each rebalance bar, rank the panel
    by ROC(lookback); long the top-k, short the bottom-k until the next
    rebalance (bracket_time exit caps the hold at `rebalance` bars)."""
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    closes = {}
    for sym, df in panel_dfs.items():
        closes[sym] = df["close"].reindex(idx).ffill()
    roc = {s: (c / c.shift(lookback) - 1.0) for s, c in closes.items()}
    out: dict[str, list] = {s: [] for s in panel_dfs}
    pos_of = {s: {t: i for i, t in enumerate(df.index)}
              for s, df in panel_dfs.items()}
    for j in range(warmup, len(idx) - 1, rebalance):
        ranked = sorted(((roc[s].iloc[j], s) for s in closes
                         if pd.notna(roc[s].iloc[j])), reverse=True)
        if len(ranked) < 2 * k:
            continue
        picks = [(s, "LONG") for _, s in ranked[:k]] + \
                [(s, "SHORT") for _, s in ranked[-k:]]
        t = idx[j]
        for sym, side in picks:
            df = panel_dfs[sym]
            pos = df.index.get_indexer([t], method="pad")[0]
            if pos < 0 or pos >= len(df) - 1:
                continue
            if df.index[pos] < t - 3 * (idx[1] - idx[0]):
                continue  # stale series (long market closure) — skip
            out[sym].append((int(pos), side))
    return out


def pairs_frame(dfA: pd.DataFrame, dfB: pd.DataFrame, beta_window: int = 240):
    """Synthetic spread series for a cointegrated-style pair: S = logA -
    beta*logB with beta from a causal trailing OLS. The tradable series
    is exp(S) so harness return fractions are log-spread returns.
    Costs are doubled at simulation (two legs) — see grid runner."""
    la = np.log(dfA["close"])
    lb = np.log(dfB["close"])
    common = la.index.intersection(lb.index)
    la, lb = la.loc[common], lb.loc[common]
    cov = la.rolling(beta_window).cov(lb)
    var = lb.rolling(beta_window).var()
    beta = (cov / var).shift(1)
    spread = la - beta * lb
    price = np.exp(spread - spread.rolling(beta_window).mean().shift(1) * 0)  # level
    sdf = pd.DataFrame({"open": price, "high": price, "low": price,
                        "close": price, "volume": 0.0}, index=common)
    return sdf, spread, beta


def sig_pairs(sdf: pd.DataFrame, spread: pd.Series, warmup: int,
              z_window: int = 48, z_in: float = 2.0):
    mu = spread.rolling(z_window).mean()
    sd = spread.rolling(z_window).std()
    z = (spread - mu) / sd
    long_sig = (z < -z_in) & (z.shift(1) >= -z_in)
    short_sig = (z > z_in) & (z.shift(1) <= z_in)
    return _entries(long_sig, short_sig, warmup)


# ---------------------------------------------------------------- registry

ALL_CLASSES = ["crypto", "forex", "comm", "idx"]
VOL_CLASSES = ["crypto", "comm", "idx"]

BR24 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}
BR26 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 6.0}
TRAIL = {"type": "trail", "sl_atr": 2.0, "trail_atr": 2.5}


def _single(family, variant, fn, spec, tfs, classes=ALL_CLASSES, atr_fn=None):
    return {"family": family, "variant": variant, "kind": "single",
            "fn": fn, "spec": spec, "tfs": tfs, "classes": classes,
            "atr_fn": atr_fn}


def build_configs() -> list[dict]:
    C: list[dict] = []
    W = warmup_for
    # ---- (A) RD-001 batch-1, generalized ----
    for n in (20, 55):
        for sname, spec in (("b24", BR24), ("b26", BR26), ("trail", TRAIL)):
            C.append(_single("donchian_turtle", f"n{n}_{sname}",
                             (lambda nn: lambda df, aux, am, w: sig_donchian(df, nn, w))(n),
                             spec, ["15m", "1h", "4h", "1d", "1wk"]))
    for w_ in (20, 50):
        for th in (2.0, 2.5):
            C.append(_single("zscore_reversion", f"w{w_}_t{th}_filt",
                             (lambda ww, tt: lambda df, aux, am, w: sig_zscore(df, ww, tt, True, w))(w_, th),
                             {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0},
                             ["15m", "1h", "4h", "1d"]))
    for th in (2.0, 2.5):
        C.append(_single("zscore_reversion", f"w20_t{th}_nofilt",
                         (lambda tt: lambda df, aux, am, w: sig_zscore(df, 20, tt, False, w))(th),
                         {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0},
                         ["15m", "1h", "4h", "1d"]))
    C.append(_single("zscore_reversion", "w20_t2.0_filt_time24",
                     lambda df, aux, am, w: sig_zscore(df, 20, 2.0, True, w),
                     {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 2.0,
                      "max_bars": 24}, ["15m", "1h", "4h", "1d"]))
    for (f_, s_) in ((12, 26), (20, 50)):
        for gname, g in (("nogate", False), ("gate", True)):
            C.append(_single("vol_adaptive_trend", f"ema{f_}_{s_}_{gname}",
                             (lambda ff, ss, gg: lambda df, aux, am, w: sig_vol_trend(df, ff, ss, gg, w))(f_, s_, g),
                             {"type": "bracket", "sl_atr": 2.5, "tp_atr": 5.0},
                             ["15m", "1h", "4h", "1d", "1wk"]))
    C.append(_single("mtf_confluence", "h1_cross_nofilt",
                     lambda df, aux, am, w: sig_mtf(df, None, am, w),
                     BR24, ["1h", "15m"]))
    C.append(_single("mtf_confluence", "h1_cross_htfilter",
                     lambda df, aux, am, w: sig_mtf(df, aux, am, w),
                     BR24, ["1h", "15m"]))
    C.append(_single("mtf_confluence", "h4_native_ema200",
                     lambda df, aux, am, w: sig_mtf_native(df, w),
                     BR24, ["4h", "1d"]))
    for cname, c in (("novol", None), ("vol1.5", 1.5)):
        C.append(_single("volume_breakout", f"donch20_{cname}",
                         (lambda cc: lambda df, aux, am, w: sig_volume_breakout(df, cc, w))(c),
                         BR24, ["15m", "1h", "4h", "1d"], classes=VOL_CLASSES))
    for lb in (24, 72, 168):
        C.append(_single("ts_momentum", f"roc{lb}",
                         (lambda ll: lambda df, aux, am, w: sig_ts_momentum(df, ll, w))(lb),
                         BR24, ["15m", "1h", "4h", "1d"]))
    C.append(_single("ts_momentum", "roc42",
                     lambda df, aux, am, w: sig_ts_momentum(df, 42, w),
                     BR24, ["15m", "1h", "4h", "1d", "1wk"]))
    for kind in ("london_momentum", "ny_reversal"):
        C.append(_single("session_effects", kind,
                         (lambda kk: lambda df, aux, am, w: sig_session(df, kk, w))(kind),
                         {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0,
                          "max_bars": 6}, ["1h"]))
    # ---- (B) batch 2 ----
    for lb in (30, 90):
        C.append(_single("tsmom2_dual", f"roc{lb}_ema200",
                         (lambda ll: lambda df, aux, am, w: sig_dual_momentum(df, ll, w))(lb),
                         {"type": "bracket", "sl_atr": 2.5, "tp_atr": 5.0},
                         ["1h", "4h", "1d", "1wk"]))
    for n in (20, 55):
        for fname_, filt in (("trail", False), ("trail_filt", True)):
            C.append(_single("turtle2", f"n{n}_{fname_}",
                             (lambda nn, ff: lambda df, aux, am, w: sig_turtle2(df, nn, ff, w))(n, filt),
                             TRAIL, ["4h", "1d", "1wk"]))
    for (f_, s_) in ((12, 26), (20, 50)):
        C.append(_single("voltrend2", f"ema{f_}_{s_}_adapt",
                         (lambda ff, ss: lambda df, aux, am, w: sig_voltrend2(df, ff, ss, w))(f_, s_),
                         BR24, ["1h", "4h", "1d"], atr_fn=atr_vol_scaled))
    C.append(_single("fx_meanrev", "rsi2_filt",
                     lambda df, aux, am, w: sig_rsi2_filt(df, w),
                     {"type": "bracket", "sl_atr": 1.5, "tp_atr": 2.0},
                     ["1h", "4h", "1d"]))
    C.append(_single("fx_meanrev", "bb_revert_filt",
                     lambda df, aux, am, w: sig_bb_revert(df, w),
                     {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0},
                     ["1h", "4h", "1d"]))
    for kind in ("momentum", "reversal"):
        C.append(_single("dow_effect", kind,
                         (lambda kk: lambda df, aux, am, w: sig_dow(df, kk, w))(kind),
                         {"type": "bracket_time", "sl_atr": 3.0, "tp_atr": 6.0,
                          "max_bars": 5}, ["1d"]))
    for lb, rb in ((20, 5), (20, 20), (60, 5), (60, 20)):
        C.append({"family": "xs_momentum", "variant": f"roc{lb}_rb{rb}",
                  "kind": "xs", "spec": {"type": "bracket_time",
                                         "sl_atr": 3.0, "tp_atr": 6.0,
                                         "max_bars": rb},
                  "xs": {"lookback": lb, "rebalance": rb, "k": 3},
                  "tfs": ["4h", "1d"], "classes": ALL_CLASSES,
                  "atr_fn": None})
    for pair in (("BTCUSDT", "ETHUSDT"), ("BTCUSDT", "SOLUSDT"),
                 ("ETHUSDT", "SOLUSDT")):
        C.append({"family": "pairs_statarb",
                  "variant": f"{pair[0][:3]}_{pair[1][:3]}",
                  "kind": "pairs", "pair": pair,
                  "spec": {"type": "bracket_time", "sl_atr": 3.0,
                           "tp_atr": 3.0, "max_bars": 96},
                  "tfs": ["1h", "4h"], "classes": ["crypto"],
                  "atr_fn": None})
    return C
