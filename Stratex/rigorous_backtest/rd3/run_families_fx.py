"""Stage-2B runner for TASK-STR-RD-003 (forex-native families).

Same judgement machinery and row shape as rd3/run_families.py
(rd2.stats2 bar/holdout, rd2 costs, rd.common wf-select). Rows
checkpoint to <out-dir>/stage2b_rows/, wf-selects to
<out-dir>/stage2b_wf_select.json. One cell = one trial.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd3.run_families_fx \
      --out-dir /home/hatch/workspace/str-rd3/work/results_rd3
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from ..rd.common import (atr, dump_json, trades_from_json, trades_to_json,
                         wf_select_judge)
from ..rd.fastsim import simulate_entries
from ..rd2.costs2 import costs_for, describe
from ..rd2.families2 import warmup_for
from ..rd2.panels import fold_profile, load_panel
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_fx import (build_configs_fx, sig_london_drive,
                          sig_monday_gap, sig_trend_pullback)

SAVE_SCREEN = lambda po: (po.get("expectancy_net") or -9) > -0.005 or \
    (po.get("profit_factor_net") or 0) >= 0.98


def entries_for(cfg, df, warmup):
    if cfg["kind"] == "london":
        return sig_london_drive(df, cfg["narrow"], warmup)
    if cfg["kind"] == "gap":
        return sig_monday_gap(df, cfg["theta"], warmup)
    if cfg["kind"] == "pullback":
        return sig_trend_pullback(df, cfg["ema_trend"], warmup)
    raise ValueError(cfg["kind"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "stage2b_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel(panel, tf)
        return panel_cache[(panel, tf)]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n = 0
    for cfg in build_configs_fx():
        for panel, tf in cfg["cells"]:
            key = f"{cfg['family']}__{cfg['variant']}__{panel}__{tf}"
            row_path = rows_dir / f"{key}.json"
            if row_path.exists():
                row = json.loads(row_path.read_text())
                if "trades" in row:
                    fam_cell_trades.setdefault(
                        (cfg["family"], panel, tf), {})[cfg["variant"]] = \
                        trades_from_json(row["trades"])
                continue
            datasets = get_panel(panel, tf)
            if not datasets:
                continue
            warmup = warmup_for(tf)
            t0 = time.time()
            try:
                trades = []
                for sym, ds in datasets.items():
                    entries = entries_for(cfg, ds.df, warmup)
                    a = atr(ds.df, 14).to_numpy(dtype=float)
                    trades.extend(simulate_entries(
                        ds.df, entries, a, cfg["spec"], sym,
                        costs_for(panel, sym)))
                status = "EVALUATED" if trades else "NO_TRADES"
                err = None
            except Exception as exc:  # noqa: BLE001 - recorded as verdict
                trades, status = [], "BROKEN"
                err = f"{type(exc).__name__}: {exc}"
            symbols = sorted(datasets.keys())
            profile = fold_profile(panel, tf)
            rep = fold_report(trades, profile, symbols)
            hold = holdout2(rep, symbols)
            po = rep["pooled_oos"]
            row = {
                "family": cfg["family"], "variant": cfg["variant"],
                "panel": panel, "timeframe": tf, "stage": "rd3_stage2b",
                "status": status, "error": err, "spec": cfg["spec"],
                "costs_rt_bps": {s: describe(panel, s)["round_trip_bps"]
                                 for s in symbols},
                "symbols": symbols, "report": rep, "holdout": hold,
                "bar": check_bar2(rep, hold),
                "trade_stats": trade_stats(
                    [t for t in trades
                     if t.entry_time >= pd.Timestamp(
                         rep["per_fold"][profile[0]]["oos_start"],
                         tz="UTC")]),
                "seconds": round(time.time() - t0, 2),
            }
            if SAVE_SCREEN(po) or row["bar"]["passes_bar"]:
                row["trades"] = trades_to_json(trades)
            dump_json(row_path, row)
            fam_cell_trades.setdefault((cfg["family"], panel, tf), {})[
                cfg["variant"]] = trades
            n += 1
            print(f"[rd3fx] {key}: {status} trades={po['trades']} "
                  f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                  f"({row['seconds']}s)", flush=True)

    sel_path = out_dir / "stage2b_wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    for (fam, panel, tf), vt in fam_cell_trades.items():
        if len(vt) < 2:
            continue
        sel = wf_select_judge(vt)
        summary[f"{fam}__{panel}__{tf}"] = {
            "family": fam, "panel": panel, "timeframe": tf,
            "variants_tried": len(vt), "wf_selection": sel}
        po = sel["procedure_pooled_oos"]
        print(f"[rd3fx] WF-SELECT {fam} {panel} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(sel_path, summary)
    print(f"[rd3fx] done: {n} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
