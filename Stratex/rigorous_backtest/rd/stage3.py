"""STAGE 3 — NEW strategy creation, batch 1 (TASK-STR-RD-001).

New parameterized families in areas the existing library lacks or barely
covers. All signal generation is vectorized and strictly causal; entries
use rd.fastsim (validated bit-equivalent to the harness simulator);
brackets are ATR(14)-anchored to the entry price; warmup 260 bars;
judgement is walk-forward OOS only, harness folds and costs.

PRE-DECLARED GRIDS (declared here, before any run; every variant is
evaluated and disclosed — no silent dropping):

  donchian_turtle (1h): N in {20, 55} x exits {bracket 2/4, bracket 2/6,
      trail 2/2.5}                                        -> 6 variants
  zscore_reversion (1h): W in {20, 50} x theta in {2.0, 2.5} with ADX<25
      regime filter (4) + W=20 unfiltered (2) + W=20 theta=2.0 filtered
      with 24-bar time exit (1)                           -> 7 variants
  vol_adaptive_trend (1h): EMA cross {(12,26), (20,50)} x vol-percentile
      gate {off, on} exits bracket 2.5/5                  -> 4 variants
  mtf_confluence: 1h EMA20/50 cross x 4h-trend filter {off, on} (2) +
      4h-native cross with own-EMA200 filter (1)         -> 3 variants
  volume_breakout (1h): Donchian-20 x volume confirm {off, 1.5x} exits
      bracket 2/4                                         -> 2 variants
  ts_momentum (1h): ROC lookback {24, 72, 168} exits bracket 2/4 (3) +
      4h ROC 42 (1)                                       -> 4 variants
  session_effects (1h): London-open momentum (1) + NY-session reversal
      (1)                                                 -> 2 variants
  TOTAL                                                   -> 28 variants

Family headline = wf_select_judge (per fold, the family's variants are
ranked on in-sample trades only; the top-1 is judged on the fold's OOS
trades). The best-pooled-OOS variant per family is also reported with the
promotion bar + holdout checks applied — selection over the family is
disclosed, so the bar (not the ranking) is what protects the verdict.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ..simulator import Trade
from ..walkforward import oos_report
from .common import (COSTS, SYMBOLS, adx, atr, check_bar, dump_json, ema,
                     full_report, holdout_check, load_timeframe, rsi,
                     trades_to_json, wf_select_judge)
from .fastsim import simulate_entries

WARMUP = 260


def _entries_from_bool(long_sig: pd.Series, short_sig: pd.Series):
    out = []
    ls = long_sig.fillna(False).to_numpy(dtype=bool)
    ss = short_sig.fillna(False).to_numpy(dtype=bool)
    for i in range(WARMUP, len(ls)):
        if ls[i]:
            out.append((i, "LONG"))
        elif ss[i]:
            out.append((i, "SHORT"))
    return out


# ---------------------------------------------------------------- families

def fam_donchian(df: pd.DataFrame, n: int):
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    return _entries_from_bool(df["close"] > hi, df["close"] < lo)


def fam_zscore(df: pd.DataFrame, w: int, theta: float, use_filter: bool):
    mid = df["close"].rolling(w).mean()
    sd = df["close"].rolling(w).std()
    z = (df["close"] - mid) / sd
    prev = z.shift(1)
    long_sig = (prev >= -theta) & (z < -theta)
    short_sig = (prev <= theta) & (z > theta)
    if use_filter:
        a = adx(df, 14)
        ok = a < 25
        long_sig &= ok
        short_sig &= ok
    return _entries_from_bool(long_sig, short_sig)


def fam_vol_trend(df: pd.DataFrame, fast: int, slow: int, gate: bool):
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
    return _entries_from_bool(long_sig, short_sig)


def fam_mtf_entries(df1h: pd.DataFrame, df4h: pd.DataFrame | None, mode: str):
    f = ema(df1h["close"], 20)
    s = ema(df1h["close"], 50)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1))
    short_sig = (f < s) & (f.shift(1) >= s.shift(1))
    if mode == "filtered":
        assert df4h is not None
        e50 = ema(df4h["close"], 50)
        trend_up = (df4h["close"] > e50)
        # 4h bar opening at T is fully known at T+4h; align by close time.
        trend = pd.Series(trend_up.to_numpy(),
                          index=df4h.index + pd.Timedelta(hours=4))
        closes_1h = df1h.index + pd.Timedelta(hours=1)
        aligned = trend.reindex(closes_1h, method="ffill")
        aligned.index = df1h.index
        aligned = aligned.fillna(False)
        long_sig &= aligned
        short_sig &= ~aligned
    return _entries_from_bool(long_sig, short_sig)


def fam_mtf_4h_native(df4h: pd.DataFrame):
    f = ema(df4h["close"], 20)
    s = ema(df4h["close"], 50)
    d = ema(df4h["close"], 200)
    long_sig = (f > s) & (f.shift(1) <= s.shift(1)) & (df4h["close"] > d)
    short_sig = (f < s) & (f.shift(1) >= s.shift(1)) & (df4h["close"] < d)
    return _entries_from_bool(long_sig, short_sig)


def fam_volume_breakout(df: pd.DataFrame, confirm: float | None):
    hi = df["high"].rolling(20).max().shift(1)
    lo = df["low"].rolling(20).min().shift(1)
    long_sig = df["close"] > hi
    short_sig = df["close"] < lo
    if confirm is not None:
        vma = df["volume"].rolling(20).mean()
        ok = df["volume"] > confirm * vma
        long_sig &= ok
        short_sig &= ok
    return _entries_from_bool(long_sig, short_sig)


def fam_ts_momentum(df: pd.DataFrame, lookback: int):
    roc = df["close"] / df["close"].shift(lookback) - 1.0
    long_sig = (roc > 0) & (roc.shift(1) <= 0)
    short_sig = (roc < 0) & (roc.shift(1) >= 0)
    return _entries_from_bool(long_sig, short_sig)


def fam_session(df: pd.DataFrame, kind: str):
    out = []
    hours = df.index.hour.to_numpy()
    closes = df["close"].to_numpy()
    opens = df["open"].to_numpy()
    a = atr(df, 14).to_numpy()
    n = len(df)
    if kind == "london_momentum":
        for i in range(WARMUP, n - 1):
            if hours[i] == 8:  # direction of the London-open hour (08:00 UTC
                # bar); fastsim enters at the next bar's open (09:00)
                move = closes[i] - opens[i]
                if move > 0:
                    out.append((i, "LONG"))
                elif move < 0:
                    out.append((i, "SHORT"))
    elif kind == "ny_reversal":
        for i in range(WARMUP, n - 1):
            if hours[i] == 14:  # fade a stretched 08->14 move
                j = i - 6
                if j < 0 or hours[j] != 8:
                    continue
                move = closes[i] - opens[j]
                if a[i] > 0 and move > 1.0 * a[i]:
                    out.append((i, "SHORT"))
                elif a[i] > 0 and move < -1.0 * a[i]:
                    out.append((i, "LONG"))
    return out


# family -> list of (variant_name, timeframe, entries_fn(df, aux4h), spec)
def build_variants():
    V = []
    for n in (20, 55):
        for sname, spec in [("b24", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}),
                            ("b26", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 6.0}),
                            ("trail", {"type": "trail", "sl_atr": 2.0, "trail_atr": 2.5})]:
            V.append(("donchian_turtle", f"n{n}_{sname}", "1h",
                      (lambda nn: lambda df, aux: fam_donchian(df, nn))(n), spec))
    for w in (20, 50):
        for th in (2.0, 2.5):
            V.append(("zscore_reversion", f"w{w}_t{th}_filt", "1h",
                      (lambda ww, tt: lambda df, aux: fam_zscore(df, ww, tt, True))(w, th),
                      {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0}))
    for th in (2.0, 2.5):
        V.append(("zscore_reversion", f"w20_t{th}_nofilt", "1h",
                  (lambda tt: lambda df, aux: fam_zscore(df, 20, tt, False))(th),
                  {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0}))
    V.append(("zscore_reversion", "w20_t2.0_filt_time24", "1h",
              lambda df, aux: fam_zscore(df, 20, 2.0, True),
              {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 2.0, "max_bars": 24}))
    for (f_, s_) in ((12, 26), (20, 50)):
        for gname, g in (("nogate", False), ("gate", True)):
            V.append(("vol_adaptive_trend", f"ema{f_}_{s_}_{gname}", "1h",
                      (lambda ff, ss, gg: lambda df, aux: fam_vol_trend(df, ff, ss, gg))(f_, s_, g),
                      {"type": "bracket", "sl_atr": 2.5, "tp_atr": 5.0}))
    V.append(("mtf_confluence", "h1_cross_nofilt", "1h",
              lambda df, aux: fam_mtf_entries(df, aux, "raw"),
              {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    V.append(("mtf_confluence", "h1_cross_4hfilter", "1h",
              lambda df, aux: fam_mtf_entries(df, aux, "filtered"),
              {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    V.append(("mtf_confluence", "h4_native_ema200", "4h",
              lambda df, aux: fam_mtf_4h_native(df),
              {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    for cname, c in (("novol", None), ("vol1.5", 1.5)):
        V.append(("volume_breakout", f"donch20_{cname}", "1h",
                  (lambda cc: lambda df, aux: fam_volume_breakout(df, cc))(c),
                  {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    for lb in (24, 72, 168):
        V.append(("ts_momentum", f"roc{lb}_1h", "1h",
                  (lambda ll: lambda df, aux: fam_ts_momentum(df, ll))(lb),
                  {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    V.append(("ts_momentum", "roc42_4h", "4h",
              lambda df, aux: fam_ts_momentum(df, 42),
              {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}))
    V.append(("session_effects", "london_momentum", "1h",
              lambda df, aux: fam_session(df, "london_momentum"),
              {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 3.0, "max_bars": 4}))
    V.append(("session_effects", "ny_reversal", "1h",
              lambda df, aux: fam_session(df, "ny_reversal"),
              {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 2.0, "max_bars": 6}))
    return V


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--families", default="")  # comma list; empty = all
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "stage3_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache_dir)
    only = {s.strip() for s in args.families.split(",") if s.strip()}

    variants = build_variants()
    datasets: dict[str, dict] = {}
    aux4h: dict[str, object] = {}
    trades_by_variant: dict[str, list[Trade]] = {}

    for fam, vname, tf, fn, spec in variants:
        if only and fam not in only:
            continue
        key = f"{fam}__{vname}"
        row_path = rows_dir / f"{key}.json"
        if tf not in datasets:
            datasets[tf] = load_timeframe(tf, cache)
        if not aux4h and tf == "1h":
            aux4h = {sym: ds.df for sym, ds in load_timeframe("4h", cache).items()}
        all_trades: list[Trade] = []
        for sym in SYMBOLS:
            ds = datasets[tf][sym]
            entries = fn(ds.df, aux4h.get(sym) if tf == "1h" else None)
            a = atr(ds.df, 14).to_numpy(dtype=float)
            all_trades.extend(simulate_entries(ds.df, entries, a, spec, sym, COSTS))
        trades_by_variant[key] = all_trades
        rep = full_report(all_trades)
        row = {"family": fam, "variant": vname, "timeframe": tf, "spec": spec,
               "report": rep, "bar": check_bar(rep),
               "holdout": holdout_check(rep),
               "trades": trades_to_json(all_trades)}
        dump_json(row_path, row)
        po = rep["pooled_oos"]
        print(f"[stage3] {key}: trades={po['trades']} exp={po['expectancy_net']} "
              f"pf={po['profit_factor_net']} bar={row['bar']['passes_bar']}",
              flush=True)

    # Family-level honest selection (top-1 IS pick per fold).
    fams: dict[str, dict[str, list[Trade]]] = {}
    for (fam, vname, tf, fn, spec) in variants:
        if only and fam not in only:
            continue
        key = f"{fam}__{vname}"
        if key in trades_by_variant:
            fams.setdefault(fam, {})[vname] = trades_by_variant[key]
    summary = {"stage": 3, "variants_tried": sum(len(v) for v in fams.values()),
               "families": {}}
    for fam, vt in fams.items():
        sel = wf_select_judge(vt)
        summary["families"][fam] = {
            "variants_tried": len(vt),
            "wf_selection": sel,
        }
        po = sel["procedure_pooled_oos"]
        print(f"[stage3] FAMILY {fam}: wf-select pooled trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}", flush=True)
    dump_json(out_dir / "stage3_summary.json", summary)
    print("[stage3] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
