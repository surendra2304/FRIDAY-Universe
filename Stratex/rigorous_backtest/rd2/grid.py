"""Mega-grid runner (TASK-STR-RD-002, Stage B).

Evaluates every registered configuration on every (class, timeframe)
cell it declares, pooled over the canonical panel for that cell.
One cell = one trial in the global counter, whatever its outcome.
Rows checkpoint to <out-dir>/grid_rows/<family>__<variant>__<panel>__
<tf>.json and are skipped on re-run (delete a row to redo it).

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd2.grid --out-dir results_rd2 \
      [--classes crypto,forex] [--tfs 4h,1d] [--families ts_momentum,...]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ..rd.common import atr, dump_json, trades_to_json, wf_select_judge
from ..rd.fastsim import simulate_entries
from ..simulator import Costs
from .costs2 import costs_for, describe
from .families2 import (build_configs, pairs_frame, sig_pairs, warmup_for,
                        xs_entries)
from .families3 import build_configs3
from .panels import PANEL_TFS, fold_profile, load_panel
from .stats2 import check_bar2, fold_report, holdout2, trade_stats

CANON = {("crypto", "1d"): "crypto30", ("crypto", "4h"): "crypto30",
         ("crypto", "1h"): "crypto30", ("crypto", "1wk"): "crypto30",
         ("crypto", "15m"): "crypto12", ("crypto", "5m"): "crypto6",
         ("forex", "1d"): "forex28", ("forex", "1wk"): "forex28",
         ("forex", "4h"): "forex12", ("forex", "1h"): "forex12",
         ("comm", "1d"): "comm7", ("comm", "1wk"): "comm7",
         ("comm", "4h"): "comm7", ("comm", "1h"): "comm7",
         ("idx", "1d"): "idx7", ("idx", "1wk"): "idx7",
         ("idx", "4h"): "idx3", ("idx", "1h"): "idx3"}
TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1wk": 10080}
AUX_TF = {"15m": "1h", "1h": "4h"}

# Trades are persisted only for streams that could matter downstream
# (Stage C combinations / audit): near-breakeven or better, or bar-pass.
SAVE_SCREEN = lambda po: (po.get("expectancy_net") or -9) > -0.005 or \
    (po.get("profit_factor_net") or 0) >= 0.98


def eval_single(cfg, panel_name, tf, datasets, aux_datasets):
    warmup = warmup_for(tf)
    aux_min = TF_MIN[AUX_TF[tf]] if tf in AUX_TF else None
    all_trades = []
    for sym, ds in datasets.items():
        aux_df = aux_datasets[sym].df if aux_datasets and sym in aux_datasets else None
        entries = cfg["fn"](ds.df, aux_df, aux_min, warmup)
        if cfg.get("atr_fn"):
            a = cfg["atr_fn"](ds.df)
        else:
            a = atr(ds.df, 14).to_numpy(dtype=float)
        all_trades.extend(simulate_entries(ds.df, entries, a, cfg["spec"],
                                           sym, costs_for(panel_name, sym)))
    return all_trades


def eval_xs(cfg, panel_name, tf, datasets):
    if cfg.get("xs_fn") is not None:
        per_sym = cfg["xs_fn"]({s: ds.df for s, ds in datasets.items()},
                               warmup_for(tf))
        all_trades = []
        for sym, ds in datasets.items():
            a = atr(ds.df, 14).to_numpy(dtype=float)
            all_trades.extend(simulate_entries(
                ds.df, per_sym.get(sym, []), a, cfg["spec"], sym,
                costs_for(panel_name, sym)))
        return all_trades
    p = cfg["xs"]
    per_sym = xs_entries({s: ds.df for s, ds in datasets.items()},
                         p["lookback"], p["rebalance"], p["k"],
                         warmup_for(tf))
    all_trades = []
    for sym, ds in datasets.items():
        a = atr(ds.df, 14).to_numpy(dtype=float)
        all_trades.extend(simulate_entries(ds.df, per_sym.get(sym, []), a,
                                           cfg["spec"], sym,
                                           costs_for(panel_name, sym)))
    return all_trades


def eval_pairs(cfg, tf, datasets):
    A, B = cfg["pair"]
    sdf, spread, _beta = pairs_frame(datasets[A].df, datasets[B].df)
    entries = sig_pairs(sdf, spread, warmup_for(tf))
    a = atr(sdf, 14).to_numpy(dtype=float)
    return simulate_entries(sdf, entries, a, cfg["spec"], f"{A}-{B}",
                            Costs(10.0, 6.0))  # two legs x crypto costs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--classes", default="")
    ap.add_argument("--tfs", default="")
    ap.add_argument("--families", default="")
    ap.add_argument("--batch", default="2",
                    help="config batch: 2 (default), 3, or all")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "grid_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    only_classes = {s for s in args.classes.split(",") if s}
    only_tfs = {s for s in args.tfs.split(",") if s}
    only_fams = {s for s in args.families.split(",") if s}

    configs = []
    if args.batch in ("2", "all"):
        configs += build_configs()
    if args.batch in ("3", "all"):
        configs += build_configs3()
    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel(panel, tf)
        return panel_cache[(panel, tf)]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n_cells = 0
    for cfg in configs:
        if only_fams and cfg["family"] not in only_fams:
            continue
        for cls in cfg["classes"]:
            if only_classes and cls not in only_classes:
                continue
            for tf in cfg["tfs"]:
                if only_tfs and tf not in only_tfs:
                    continue
                panel = CANON.get((cls, tf))
                if panel is None or tf not in PANEL_TFS[panel]:
                    continue
                key = f"{cfg['family']}__{cfg['variant']}__{panel}__{tf}"
                row_path = rows_dir / f"{key}.json"
                if row_path.exists():
                    continue
                datasets = get_panel(panel, tf)
                if not datasets:
                    continue
                t0 = time.time()
                try:
                    if cfg["kind"] == "single":
                        aux = None
                        if cfg["family"] == "mtf_confluence" and tf in AUX_TF:
                            aux = get_panel(panel, AUX_TF[tf])
                        trades = eval_single(cfg, panel, tf, datasets, aux)
                    elif cfg["kind"] == "xs":
                        trades = eval_xs(cfg, panel, tf, datasets)
                    else:
                        trades = eval_pairs(cfg, tf, datasets)
                    status = "EVALUATED" if trades else "NO_TRADES"
                except Exception as exc:  # noqa: BLE001 - recorded as verdict
                    trades, status = [], "BROKEN"
                    err = f"{type(exc).__name__}: {exc}"
                else:
                    err = None
                symbols = sorted(datasets.keys())
                profile = fold_profile(panel, tf)
                rep = fold_report(trades, profile, symbols)
                hold = holdout2(rep, symbols)
                po = rep["pooled_oos"]
                row = {
                    "family": cfg["family"], "variant": cfg["variant"],
                    "panel": panel, "timeframe": tf, "asset_class": cls,
                    "status": status, "error": err,
                    "spec": cfg["spec"],
                    "costs_rt_bps": {s: describe(panel, s)["round_trip_bps"]
                                     for s in symbols},
                    "symbols": symbols, "report": rep, "holdout": hold,
                    "bar": check_bar2(rep, hold),
                    "trade_stats": trade_stats(
                        [t for t in trades
                         if t.entry_time >= __import__("pandas").Timestamp(
                             rep["per_fold"][profile[0]]["oos_start"], tz="UTC")]),
                    "seconds": round(time.time() - t0, 2),
                }
                if SAVE_SCREEN(po) or row["bar"]["passes_bar"]:
                    from ..rd.common import trades_to_json as _t2j
                    row["trades"] = _t2j(trades)
                dump_json(row_path, row)
                fam_cell_trades.setdefault((cfg["family"], panel, tf), {})[
                    cfg["variant"]] = trades
                n_cells += 1
                print(f"[grid] {key}: {status} trades={po['trades']} "
                      f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                      f"({row['seconds']}s)", flush=True)

    # Factory-procedure control: per (family, cell) honest wf-selection.
    sel_path = out_dir / "grid_wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    for (fam, panel, tf), vt in fam_cell_trades.items():
        if len(vt) < 2:
            continue
        sel = wf_select_judge(vt)
        summary[f"{fam}__{panel}__{tf}"] = {
            "family": fam, "panel": panel, "timeframe": tf,
            "variants_tried": len(vt), "wf_selection": sel}
        po = sel["procedure_pooled_oos"]
        print(f"[grid] WF-SELECT {fam} {panel} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(sel_path, summary)
    print(f"[grid] done: {n_cells} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
