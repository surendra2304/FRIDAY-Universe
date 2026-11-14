"""STAGE 2 — adx_ema deep-dive (TASK-STR-RD-001).

Questions:
A. What does the one BT-001 lead look like under PRODUCTION conditions?
   Production applies two downstream filters the bare module does not have
   (config_strategy.ADX_EMA_STRATEGY_V2 + config.LONG_ONLY + the service's
   BTC-regime gate):
     - LONG_ONLY: SELL signals are rejected (spot constraint; also enforced
       in testnet_engine/service.py);
     - BTC regime gate: a BUY executes only when BTCUSDT 4h close > its
       EMA(200) at the signal bar (BTC_REGIME_FILTER: True).
   Filters are applied at SIGNAL level (as production does), then the
   filtered signals are simulated with the harness MODULE convention.
   Ablations: bare / long_only / gate_only / production (both).
B. Timeframe sensitivity under production filters: 2h / 4h / 6h / 1d.
C. ADX-threshold sensitivity at 4h under production filters: 15/20/25/30
   (20 is production). Implemented by setting the module's threshold
   global before extraction — the module reads it at signal time.
D. Exit engineering on the production-filtered 4h entries (fastsim):
   bracket variants, ATR trailing, time exits. Entry-anchored brackets
   (fastsim convention) — the module's own close-anchored 3/3 bracket from
   part A is the reference row.

Sanity gate: part A's bare row must reproduce BT-001's governed adx_ema
row (77 trades, expectancy +1.190%, PF 1.57). If it does not, the runner
raises — the deep-dive does not proceed on a broken replica.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ..module_eval import WARMUP_BARS, WINDOW, _extract, _load_module
from ..simulator import simulate_module
from ..walkforward import oos_report
from .common import (COSTS, SYMBOLS, check_bar, dump_json, full_report,
                     holdout_check, load_timeframe, trades_to_json)
from .fastsim import simulate_entries

MODULE = "strategy_adx_ema"


def extract_signals(mod, df: pd.DataFrame):
    """(signals, atr_at_bar) using the module's own add_features pipeline,
    mirroring module_eval's extraction loop exactly."""
    work = mod.add_features(df.copy())
    n = len(work)
    signals = []
    for i in range(WARMUP_BARS, n - 1):
        res = mod.get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
        ex = _extract(res)
        if ex is not None:
            signals.append((i, ex[0], ex[1], ex[2]))
    atr = work["atr_adx_ema"].to_numpy(dtype=float)
    return signals, atr, work


def btc_gate_series(btc_df: pd.DataFrame) -> pd.Series:
    ema200 = btc_df["close"].ewm(span=200, adjust=False).mean()
    return (btc_df["close"] > ema200)


def apply_filters(signals, symbol: str, gate_ok: pd.Series | None,
                  index: pd.DatetimeIndex, long_only: bool, gate: bool):
    out = []
    for (i, side, sl, tp) in signals:
        if long_only and side == "SHORT":
            continue
        if gate and side == "LONG":
            ts = index[i]
            ok = bool(gate_ok.loc[ts]) if gate_ok is not None and ts in gate_ok.index else False
            if not ok:
                continue
        out.append((i, side, sl, tp))
    return out


def eval_config(mod, datasets, long_only: bool, gate: bool, label: str):
    btc_ds = datasets["BTCUSDT"]
    gate_ok = btc_gate_series(btc_ds.df) if gate else None
    all_trades = []
    raw_counts, kept_counts = {}, {}
    for sym in SYMBOLS:
        ds = datasets[sym]
        signals, _atr, _work = extract_signals(mod, ds.df)
        raw_counts[sym] = len(signals)
        kept = apply_filters(signals, sym, gate_ok, ds.df.index, long_only, gate)
        kept_counts[sym] = len(kept)
        all_trades.extend(simulate_module(ds.df, kept, sym, COSTS))
    rep = full_report(all_trades)
    return {"config": label, "long_only": long_only, "btc_regime_gate": gate,
            "signals_raw": raw_counts, "signals_kept": kept_counts,
            "report": rep, "bar": check_bar(rep), "holdout": holdout_check(rep),
            "trades": trades_to_json(all_trades)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratex-root", default=".")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--parts", default="A,B,C,D")
    args = ap.parse_args()
    stratex_root = Path(args.stratex_root).resolve()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache_dir)
    parts = set(p.strip() for p in args.parts.split(","))

    file_path = stratex_root / f"{MODULE}.py"
    search_paths = [str(stratex_root), str(stratex_root / "strategies")]
    mod = _load_module(MODULE, file_path, search_paths)

    results: dict = {"stage": 2, "module": MODULE,
                     "costs": COSTS.describe()}

    if "A" in parts:
        ds4 = load_timeframe("4h", cache)
        cfgs = []
        for label, lo, gt in [("bare", False, False),
                              ("long_only", True, False),
                              ("gate_only", False, True),
                              ("production", True, True)]:
            row = eval_config(mod, ds4, lo, gt, label)
            cfgs.append(row)
            po = row["report"]["pooled_oos"]
            print(f"[stage2A] {label}: trades={po['trades']} exp={po['expectancy_net']} "
                  f"pf={po['profit_factor_net']}", flush=True)
        bare = cfgs[0]["report"]["pooled_oos"]
        ref = json.loads((stratex_root / "rigorous_backtest" / "results" /
                          "phase_governed.json").read_text())
        ref_row = next(r for r in ref["rows"] if r["strategy"] == MODULE)
        ref_po = ref_row["pooled_oos"]
        match = (bare["trades"] == ref_po["trades"] and
                 abs(bare["expectancy_net"] - ref_po["expectancy_net"]) < 1e-9 and
                 abs(bare["profit_factor_net"] - ref_po["profit_factor_net"]) < 1e-9)
        print(f"[stage2A] bare-vs-BT001 match: {match} "
              f"(mine {bare['trades']}/{bare['expectancy_net']}/{bare['profit_factor_net']} "
              f"vs ref {ref_po['trades']}/{ref_po['expectancy_net']}/{ref_po['profit_factor_net']})",
              flush=True)
        if not match:
            raise SystemExit("SANITY GATE FAILED: bare replica does not match BT-001")
        results["partA_production_faithful"] = {
            "bt001_replica_match": True, "configs": cfgs}
        dump_json(out_dir / "stage2_partA.json", results["partA_production_faithful"])

    if "B" in parts:
        rows = []
        for tf in ("2h", "4h", "6h", "1d"):
            ds = load_timeframe(tf, cache)
            row = eval_config(mod, ds, True, True, f"production@{tf}")
            row["timeframe"] = tf
            rows.append(row)
            po = row["report"]["pooled_oos"]
            print(f"[stage2B] {tf}: trades={po['trades']} exp={po['expectancy_net']} "
                  f"pf={po['profit_factor_net']}", flush=True)
        results["partB_timeframes"] = rows
        dump_json(out_dir / "stage2_partB.json", {"rows": rows})

    if "C" in parts:
        ds4 = load_timeframe("4h", cache)
        rows = []
        orig = mod._ADX_THRESHOLD
        try:
            for thr in (15, 20, 25, 30):
                mod._ADX_THRESHOLD = thr
                row = eval_config(mod, ds4, True, True, f"production@adx{thr}")
                row["adx_threshold"] = thr
                rows.append(row)
                po = row["report"]["pooled_oos"]
                print(f"[stage2C] adx>{thr}: trades={po['trades']} exp={po['expectancy_net']} "
                      f"pf={po['profit_factor_net']}", flush=True)
        finally:
            mod._ADX_THRESHOLD = orig
        results["partC_adx_thresholds"] = rows
        dump_json(out_dir / "stage2_partC.json", {"rows": rows})

    if "D" in parts:
        ds4 = load_timeframe("4h", cache)
        btc_gate = btc_gate_series(ds4["BTCUSDT"].df)
        entries_by_symbol: dict[str, list[tuple[int, str]]] = {}
        atr_by_symbol: dict[str, np.ndarray] = {}
        for sym in SYMBOLS:
            ds = ds4[sym]
            signals, atr, _w = extract_signals(mod, ds.df)
            kept = apply_filters(signals, sym, btc_gate, ds.df.index, True, True)
            entries_by_symbol[sym] = [(i, side) for (i, side, _sl, _tp) in kept]
            atr_by_symbol[sym] = atr
        specs = [
            ("bracket_2_2", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0}),
            ("bracket_2_4", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}),
            ("bracket_3_3_entryanchor", {"type": "bracket", "sl_atr": 3.0, "tp_atr": 3.0}),
            ("bracket_3_6", {"type": "bracket", "sl_atr": 3.0, "tp_atr": 6.0}),
            ("bracket_4_8", {"type": "bracket", "sl_atr": 4.0, "tp_atr": 8.0}),
            ("trail_3_3", {"type": "trail", "sl_atr": 3.0, "trail_atr": 3.0}),
            ("bracket_trail_3_6_t2_arm1", {"type": "bracket_trail", "sl_atr": 3.0,
                                           "tp_atr": 6.0, "trail_atr": 2.0,
                                           "trail_arm_atr": 1.0}),
            ("bracket_time_3_3_30bars", {"type": "bracket_time", "sl_atr": 3.0,
                                         "tp_atr": 3.0, "max_bars": 30}),
            ("bracket_time_3_3_60bars", {"type": "bracket_time", "sl_atr": 3.0,
                                         "tp_atr": 3.0, "max_bars": 60}),
        ]
        rows = []
        for label, spec in specs:
            all_trades = []
            for sym in SYMBOLS:
                all_trades.extend(simulate_entries(ds4[sym].df,
                                                   entries_by_symbol[sym],
                                                   atr_by_symbol[sym], spec,
                                                   sym, COSTS))
            rep = full_report(all_trades)
            rows.append({"config": label, "spec": spec, "report": rep,
                         "bar": check_bar(rep), "holdout": holdout_check(rep),
                         "trades": trades_to_json(all_trades)})
            po = rep["pooled_oos"]
            print(f"[stage2D] {label}: trades={po['trades']} exp={po['expectancy_net']} "
                  f"pf={po['profit_factor_net']}", flush=True)
        results["partD_exit_variants"] = rows
        dump_json(out_dir / "stage2_partD.json", {"rows": rows})

    dump_json(out_dir / "stage2_all.json", results)
    print("[stage2] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
