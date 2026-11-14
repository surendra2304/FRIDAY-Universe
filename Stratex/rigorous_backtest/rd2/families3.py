"""Batch-3 strategy families (TASK-STR-RD-002, owner expansion order
2026-11-15 ~02:43 IST).

PRE-DECLARED in results_rd2/batch3_declaration.json (written before
this module was first run): 18 families, 36 configurations. Every
(config x panel x timeframe) cell counts in the global trial counter
and is judged OOS-only under the extended Anti-Overfit Law. Batch-3
runs no 15m/5m cells (declared compute deferral). All signals causal;
entries execute next-bar-open via the harness simulators.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..rd.common import atr as atr_fn
from ..rd.common import ema, rsi


def sma(series: pd.Series, w: int) -> pd.Series:
    return series.rolling(w).mean()


def cross_up(a: pd.Series, b) -> pd.Series:
    return (a > b) & (a.shift(1) <= (b.shift(1) if hasattr(b, "shift") else b))


def cross_down(a: pd.Series, b) -> pd.Series:
    return (a < b) & (a.shift(1) >= (b.shift(1) if hasattr(b, "shift") else b))


def _hh_ll_prior(df: pd.DataFrame, n: int):
    """Prior-window high/low (shifted, causal) for breakout levels."""
    return (df["high"].rolling(n).max().shift(1),
            df["low"].rolling(n).min().shift(1))


def _hh_ll_incl(df: pd.DataFrame, n: int):
    """Trailing window including the current bar (textbook stoch /
    ichimoku form; causal — uses bars <= i only)."""
    return df["high"].rolling(n).max(), df["low"].rolling(n).min()
from .families2 import warmup_for  # noqa: F401

BR24 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}
BR25 = {"type": "bracket", "sl_atr": 2.5, "tp_atr": 5.0}

STD_CELLS = {"crypto30": ["1d", "1wk", "4h", "1h"],
             "forex28": ["1d", "1wk"], "forex12": ["4h", "1h"],
             "comm7": ["1d", "1wk", "4h", "1h"],
             "idx7": ["1d", "1wk"], "idx3": ["4h", "1h"]}
DAILY_CELLS = {"crypto30": ["1d"], "forex28": ["1d"], "comm7": ["1d"],
               "idx7": ["1d"]}
XS_CELLS = {"crypto30": ["1d", "4h"], "forex28": ["1d"],
            "forex12": ["4h"], "comm7": ["1d", "4h"]}


def _entries_from_masks(df, warmup, long_mask, short_mask):
    out = []
    lm = long_mask.fillna(False).to_numpy()
    sm = short_mask.fillna(False).to_numpy()
    for i in range(max(warmup, 1), len(df) - 1):
        if lm[i]:
            out.append((i, "LONG"))
        elif sm[i]:
            out.append((i, "SHORT"))
    return out


# ------------------------------------------------------------------ singles
def sig_keltner(df, period, mult, warmup):
    mid = ema(df["close"], period)
    a = atr_fn(df, 14)
    return _entries_from_masks(df, warmup,
                               cross_up(df["close"], mid + mult * a),
                               cross_down(df["close"], mid - mult * a))


def sig_bollinger_trend(df, period, warmup):
    mid = sma(df["close"], period)
    sd = df["close"].rolling(period).std()
    return _entries_from_masks(df, warmup,
                               cross_up(df["close"], mid + 2.0 * sd),
                               cross_down(df["close"], mid - 2.0 * sd))


def sig_macd(df, filtered, warmup):
    macd = ema(df["close"], 12) - ema(df["close"], 26)
    hist = macd - ema(macd, 9)
    up = (hist > 0) & (hist.shift(1) <= 0)
    dn = (hist < 0) & (hist.shift(1) >= 0)
    if filtered:
        e200 = ema(df["close"], 200)
        up = up & (df["close"] > e200)
        dn = dn & (df["close"] < e200)
    return _entries_from_masks(df, warmup, up, dn)


def _psar_flip_entries(df, step, max_af, warmup):
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)
    trend = np.zeros(n, dtype=int)
    sar = np.full(n, np.nan)
    if n < 3:
        return []
    t = 1 if close[1] >= close[0] else -1
    s = low[0] if t == 1 else high[0]
    ep = high[0] if t == 1 else low[0]
    af = step
    trend[0] = t
    sar[0] = s
    out = []
    for i in range(1, n):
        prev_t = t
        s = s + af * (ep - s)
        if t == 1:
            s = min(s, low[i - 1], low[max(0, i - 2)])
            if low[i] < s:
                t = -1
                s = ep
                ep = low[i]
                af = step
            elif high[i] > ep:
                ep = high[i]
                af = min(af + step, max_af)
        else:
            s = max(s, high[i - 1], high[max(0, i - 2)])
            if high[i] > s:
                t = 1
                s = ep
                ep = high[i]
                af = step
            elif low[i] < ep:
                ep = low[i]
                af = min(af + step, max_af)
        sar[i] = s
        trend[i] = t
        if t != prev_t and i >= warmup and i < n - 1:
            out.append((i, "LONG" if t == 1 else "SHORT"))
    return out


def sig_rsi_momentum(df, period, hi, lo, warmup):
    r = rsi(df["close"], period)
    return _entries_from_masks(df, warmup, cross_up(r, hi), cross_down(r, lo))


def sig_stoch(df, filtered, warmup):
    hh, ll = _hh_ll_incl(df, 14)
    rng = (hh - ll).replace(0, np.nan)
    k = sma(100.0 * (df["close"] - ll) / rng, 3)
    up = cross_up(k, 20.0)
    dn = cross_down(k, 80.0)
    if filtered:
        e200 = ema(df["close"], 200)
        up = up & (df["close"] > e200)
        dn = dn & (df["close"] < e200)
    return _entries_from_masks(df, warmup, up, dn)


def sig_ichimoku(df, cloud, warmup):
    hh9, ll9 = _hh_ll_incl(df, 9)
    hh26, ll26 = _hh_ll_incl(df, 26)
    hh52, ll52 = _hh_ll_incl(df, 52)
    tenkan = (hh9 + ll9) / 2.0
    kijun = (hh26 + ll26) / 2.0
    up = cross_up(tenkan, kijun)
    dn = cross_down(tenkan, kijun)
    if cloud:
        span_a = ((tenkan + kijun) / 2.0).shift(26)
        span_b = ((hh52 + ll52) / 2.0).shift(26)
        top = pd.concat([span_a, span_b], axis=1).max(axis=1)
        bot = pd.concat([span_a, span_b], axis=1).min(axis=1)
        up = up & (df["close"] > top)
        dn = dn & (df["close"] < bot)
    return _entries_from_masks(df, warmup, up, dn)


def sig_ha(df, two, warmup):
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    n = len(df)
    hac = (o + h + low + c) / 4.0
    hao = np.empty(n)
    hao[0] = (o[0] + c[0]) / 2.0
    for i in range(1, n):
        hao[i] = (hao[i - 1] + hac[i - 1]) / 2.0
    hah = np.maximum.reduce([h, hao, hac])
    hal = np.minimum.reduce([low, hao, hac])
    bull = (hac > hao) & (np.abs(hao - hal) < 1e-12)
    bear = (hac < hao) & (np.abs(hao - hah) < 1e-12)
    out = []
    for i in range(max(warmup, 2), n - 1):
        if two:
            if bull[i] and bull[i - 1]:
                out.append((i, "LONG"))
            elif bear[i] and bear[i - 1]:
                out.append((i, "SHORT"))
        else:
            if bull[i]:
                out.append((i, "LONG"))
            elif bear[i]:
                out.append((i, "SHORT"))
    return out


def _rolling_linreg(y: np.ndarray, w: int):
    n = len(y)
    slope = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    if n <= w:
        return slope, r2
    x = np.arange(w, dtype=float)
    sx = x.sum()
    sxx = (x * x).sum()
    denom = w * sxx - sx * sx
    sy = np.convolve(y, np.ones(w), mode="valid")
    syy = np.convolve(y * y, np.ones(w), mode="valid")
    sxy = np.convolve(y, x[::-1], mode="valid")
    sl = (w * sxy - sx * sy) / denom
    cov = sxy - sx * sy / w
    var_y = syy - sy * sy / w
    var_x = sxx - sx * sx / w
    rr = np.where(var_y > 0, cov / np.sqrt(np.maximum(var_x * var_y, 1e-18)),
                  0.0)
    slope[w - 1:] = sl
    r2[w - 1:] = rr * rr
    return slope, r2


def sig_linreg(df, window, warmup):
    y = np.log(df["close"].to_numpy(dtype=float))
    slope, r2 = _rolling_linreg(y, window)
    out = []
    for i in range(max(warmup, window + 1), len(df) - 1):
        if np.isnan(slope[i]) or np.isnan(slope[i - 1]):
            continue
        if r2[i] <= 0.3:
            continue
        if slope[i] > 0 and slope[i - 1] <= 0:
            out.append((i, "LONG"))
        elif slope[i] < 0 and slope[i - 1] >= 0:
            out.append((i, "SHORT"))
    return out


def sig_shock(df, k, warmup):
    a = atr_fn(df, 14)
    up = (df["close"] - df["close"].shift(1)) > k * a
    dn = (df["close"].shift(1) - df["close"]) > k * a
    return _entries_from_masks(df, warmup, up, dn)


def sig_inside_bar(df, warmup):
    h = df["high"]
    low = df["low"]
    c = df["close"]
    inside_prev = (h.shift(1) < h.shift(2)) & (low.shift(1) > low.shift(2))
    up = inside_prev & (c > h.shift(2))
    dn = inside_prev & (c < low.shift(2))
    return _entries_from_masks(df, warmup, up, dn)


def sig_engulfing(df, warmup):
    o = df["open"]
    c = df["close"]
    po, pc = o.shift(1), c.shift(1)
    bull = (c > o) & (pc < po) & (c > po) & (o < pc)
    bear = (c < o) & (pc > po) & (c < po) & (o > pc)
    return _entries_from_masks(df, warmup, bull, bear)


def sig_gap(df, mode, warmup):
    gap = df["open"] / df["close"].shift(1) - 1.0
    if mode == "follow":
        up, dn = gap > 0.004, gap < -0.004
    else:
        up, dn = gap < -0.004, gap > 0.004
    return _entries_from_masks(df, warmup, up, dn)


def sig_turn_of_month(df, warmup):
    idx = df.index
    key = pd.Series(idx.year * 12 + idx.month, index=idx)
    from_start = key.groupby(key).cumcount().to_numpy()
    # Causal window only: the first 3 trading bars of the month
    # (known at bar time) plus calendar month-end approach days
    # (day-of-month >= 28, also known at bar time). The textbook
    # "last 3 trading days" is NOT causal (month length unknown
    # mid-month) — a truncation test caught exactly that; excluded.
    window = (from_start < 3) | (idx.day.to_numpy() >= 28)
    first = window & ~np.concatenate([[False], window[:-1]])
    out = []
    for i in range(max(warmup, 1), len(df) - 1):
        if first[i]:
            out.append((i, "LONG"))
    return out


def sig_session(df, anchor_hour, entry_hours, warmup):
    idx = df.index
    hours = idx.hour.to_numpy()
    days = idx.normalize()
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    range_by_day: dict = {}
    for i in range(len(df)):
        if hours[i] == anchor_hour and days[i] not in range_by_day:
            range_by_day[days[i]] = (highs[i], lows[i])
    out = []
    entered: set = set()
    for i in range(max(warmup, 1), len(df) - 1):
        if hours[i] not in entry_hours or days[i] in entered:
            continue
        rng = range_by_day.get(days[i])
        if rng is None:
            continue
        if closes[i] > rng[0]:
            out.append((i, "LONG"))
            entered.add(days[i])
        elif closes[i] < rng[1]:
            out.append((i, "SHORT"))
            entered.add(days[i])
    return out


def sig_vol_compression(df, filtered, warmup):
    a7 = atr_fn(df, 7)
    squeeze = a7 <= a7.rolling(50).min()
    hh10, ll10 = _hh_ll_prior(df, 10)
    up = squeeze & (df["close"] > hh10)
    dn = squeeze & (df["close"] < ll10)
    if filtered:
        e200 = ema(df["close"], 200)
        up = up & (df["close"] > e200)
        dn = dn & (df["close"] < e200)
    return _entries_from_masks(df, warmup, up, dn)


# ------------------------------------------------------------------ xs
def xs_custom_entries(panel_dfs: dict, score_fn, long_low: bool,
                      rebalance: int, k: int, warmup: int):
    """Generic cross-sectional ranker with the same index-alignment and
    stale-series discipline as families2.xs_entries: scores computed on
    the reference index (ffill), picks mapped back to per-symbol bar
    positions, stale mappings skipped. long_low=True longs the LOWEST
    scores (reversal / low-vol); False longs the highest."""
    ref = next(iter(panel_dfs.values()))
    idx = ref.index
    closes = {s: df["close"].reindex(idx).ffill()
              for s, df in panel_dfs.items()}
    scores = score_fn(closes)
    out: dict[str, list] = {s: [] for s in panel_dfs}
    for j in range(warmup, len(idx) - 1, rebalance):
        ranked = sorted(((scores[s].iloc[j], s) for s in scores
                         if pd.notna(scores[s].iloc[j])))
        if len(ranked) < 2 * k:
            continue
        if long_low:
            picks = [(s, "LONG") for _, s in ranked[:k]] + \
                    [(s, "SHORT") for _, s in ranked[-k:]]
        else:
            picks = [(s, "LONG") for _, s in ranked[-k:]] + \
                    [(s, "SHORT") for _, s in ranked[:k]]
        t = idx[j]
        for sym, side in picks:
            df = panel_dfs[sym]
            pos = df.index.get_indexer([t], method="pad")[0]
            if pos < 0 or pos >= len(df) - 1:
                continue
            if df.index[pos] < t - 3 * (idx[1] - idx[0]):
                continue
            out[sym].append((int(pos), side))
    return out


def xs_reversal_fn(lookback: int):
    def _score(closes):
        return {s: c / c.shift(lookback) - 1.0 for s, c in closes.items()}
    def _fn(panel_dfs, warmup):
        return xs_custom_entries(panel_dfs, _score, long_low=True,
                                 rebalance=5, k=3, warmup=warmup)
    return _fn


def xs_lowvol_fn():
    def _score(closes):
        return {s: c.pct_change().rolling(20).std()
                for s, c in closes.items()}
    def _fn(panel_dfs, warmup):
        return xs_custom_entries(panel_dfs, _score, long_low=True,
                                 rebalance=10, k=3, warmup=warmup)
    return _fn


# ------------------------------------------------------------------ configs
def build_configs3() -> list[dict]:
    """Real grid schema (see rd2/grid.py): singles carry a 4-argument
    fn(df, aux_df, aux_min, warmup); xs configs carry xs_fn; pairs
    configs carry pair + bracket_time spec, exactly as batch-2."""
    C: list[dict] = []
    ALL = ["crypto", "forex", "comm", "idx"]
    STD_TFS = ["1d", "1wk", "4h", "1h"]

    def single(family, variant, fn, spec=None, tfs=None, classes=None):
        C.append({"family": family, "variant": variant, "kind": "single",
                  "fn": (lambda f: lambda df, aux, am, w: f(df, w))(fn),
                  "spec": spec or BR24, "tfs": tfs or STD_TFS,
                  "classes": classes or ALL, "atr_fn": None})

    single("keltner_breakout", "ema20_m1.5",
           lambda df, w: sig_keltner(df, 20, 1.5, w))
    single("keltner_breakout", "ema20_m2.0",
           lambda df, w: sig_keltner(df, 20, 2.0, w))
    single("keltner_breakout", "ema50_m2.0",
           lambda df, w: sig_keltner(df, 50, 2.0, w))
    single("bollinger_trend", "p20_sd2.0",
           lambda df, w: sig_bollinger_trend(df, 20, w))
    single("bollinger_trend", "p50_sd2.0",
           lambda df, w: sig_bollinger_trend(df, 50, w))
    single("macd_trend", "hist_ema200", lambda df, w: sig_macd(df, True, w),
           spec=BR25)
    single("macd_trend", "hist_raw", lambda df, w: sig_macd(df, False, w),
           spec=BR25)
    single("psar_trend", "af0.02_max0.20",
           lambda df, w: _psar_flip_entries(df, 0.02, 0.20, w))
    single("psar_trend", "af0.01_max0.10",
           lambda df, w: _psar_flip_entries(df, 0.01, 0.10, w))
    single("rsi_momentum", "rsi14_55_45",
           lambda df, w: sig_rsi_momentum(df, 14, 55.0, 45.0, w))
    single("rsi_momentum", "rsi7_60_40",
           lambda df, w: sig_rsi_momentum(df, 7, 60.0, 40.0, w))
    single("stoch_reversion", "k14_filt",
           lambda df, w: sig_stoch(df, True, w))
    single("stoch_reversion", "k14_raw",
           lambda df, w: sig_stoch(df, False, w))
    single("ichimoku_trend", "tk_cloud",
           lambda df, w: sig_ichimoku(df, True, w))
    single("ichimoku_trend", "tk_raw",
           lambda df, w: sig_ichimoku(df, False, w))
    single("ha_trend", "two_candle", lambda df, w: sig_ha(df, True, w))
    single("ha_trend", "one_candle", lambda df, w: sig_ha(df, False, w))
    single("linreg_trend", "s50_r0.3",
           lambda df, w: sig_linreg(df, 50, w), spec=BR25)
    single("linreg_trend", "s100_r0.3",
           lambda df, w: sig_linreg(df, 100, w), spec=BR25)
    single("shock_breakout", "k1.0", lambda df, w: sig_shock(df, 1.0, w))
    single("shock_breakout", "k1.5", lambda df, w: sig_shock(df, 1.5, w))
    single("bar_patterns", "inside_bar",
           lambda df, w: sig_inside_bar(df, w))
    single("bar_patterns", "engulfing",
           lambda df, w: sig_engulfing(df, w))
    single("gap_daily", "follow_0.4", lambda df, w: sig_gap(df, "follow", w),
           tfs=["1d"])
    single("gap_daily", "fade_0.4", lambda df, w: sig_gap(df, "fade", w),
           tfs=["1d"])
    single("turn_of_month", "window3",
           lambda df, w: sig_turn_of_month(df, w),
           spec={"type": "bracket_time", "sl_atr": 3.0, "tp_atr": 6.0,
                 "max_bars": 6}, tfs=["1d"])
    single("vol_compression", "squeeze_raw",
           lambda df, w: sig_vol_compression(df, False, w))
    single("vol_compression", "squeeze_ema200",
           lambda df, w: sig_vol_compression(df, True, w))
    single("session_breakout", "london",
           lambda df, w: sig_session(df, 7, (8, 9, 10, 11), w),
           spec={"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0,
                 "max_bars": 6}, tfs=["1h"], classes=["forex"])
    single("session_breakout", "newyork",
           lambda df, w: sig_session(df, 14, (15, 16, 17, 18), w),
           spec={"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0,
                 "max_bars": 6}, tfs=["1h"], classes=["idx"])

    XS_TFS = ["1d", "4h"]
    XS_CLASSES = ["crypto", "forex", "comm"]
    C.append({"family": "xs_reversal", "variant": "rev5_r5", "kind": "xs",
              "xs_fn": xs_reversal_fn(5),
              "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0,
                       "max_bars": 5}, "tfs": XS_TFS, "classes": XS_CLASSES,
              "atr_fn": None})
    C.append({"family": "xs_reversal", "variant": "rev10_r5", "kind": "xs",
              "xs_fn": xs_reversal_fn(10),
              "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0,
                       "max_bars": 5}, "tfs": XS_TFS, "classes": XS_CLASSES,
              "atr_fn": None})
    C.append({"family": "xs_lowvol", "variant": "lv20_r10", "kind": "xs",
              "xs_fn": xs_lowvol_fn(),
              "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0,
                       "max_bars": 10}, "tfs": XS_TFS, "classes": XS_CLASSES,
              "atr_fn": None})

    for variant, pair in [("BTC_LTC", ("BTCUSDT", "LTCUSDT")),
                          ("ETH_BNB", ("ETHUSDT", "BNBUSDT")),
                          ("SOL_AVAX", ("SOLUSDT", "AVAXUSDT"))]:
        C.append({"family": "pairs3", "variant": variant, "kind": "pairs",
                  "pair": pair,
                  "spec": {"type": "bracket_time", "sl_atr": 3.0,
                           "tp_atr": 3.0, "max_bars": 96},
                  "tfs": ["1d", "4h", "1h"], "classes": ["crypto"],
                  "atr_fn": None})
    return C
