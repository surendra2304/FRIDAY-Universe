"""Runner for TASK-STR-RD-016 (forex_cross41 expansion round).

Same judgement machinery and row shape as rd3/run_families_fx.py
(rd2.stats2 bar/holdout, rd2 costs, rd.common wf-select), run over
RD-003's Stage-2B forex-native families (signal code rd3/families_fx,
byte-identical to main) on the TASK-STR-DATA-001 forex_cross41 panel.
Cells, variants, specs, bar and counting are frozen in
results_rd16/declaration.json (SHA-256 in the claim comment) BEFORE
any cell ran. One cell = one trial; one wf-select procedure per
(family, timeframe) = one trial.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd16.run_families16 \
      --out-dir /home/hatch/workspace/rd-016/results_rd16
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
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from ..rd3.families_fx import build_configs_fx
from ..rd3.run_families_fx import SAVE_SCREEN, entries_for
from .panels16 import PANEL, fold_profile16, load_panel16, uncovered

# Declared cells (declaration.json): family -> timeframes on forex_cross41.
CELLS16 = {"london_drive": ["1h"], "monday_gap_fade": ["1d"],
           "trend_pullback": ["1d", "4h"]}


def configs16() -> list[dict]:
    out = []
    for cfg in build_configs_fx():
        if cfg["family"] not in CELLS16:
            continue
        c = dict(cfg)
        c["cells"] = [(PANEL, tf) for tf in CELLS16[cfg["family"]]]
        out.append(c)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    panel_cache: dict[str, dict] = {}

    def get_panel(tf):
        if tf not in panel_cache:
            panel_cache[tf] = load_panel16(tf)
        return panel_cache[tf]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n = 0
    for cfg in configs16():
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
            datasets = get_panel(tf)
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
            profile = fold_profile16(tf)
            rep = fold_report(trades, profile, symbols)
            hold = holdout2(rep, symbols)
            po = rep["pooled_oos"]
            row = {
                "family": cfg["family"], "variant": cfg["variant"],
                "panel": panel, "timeframe": tf, "stage": "rd16",
                "status": status, "error": err, "spec": cfg["spec"],
                "costs_rt_bps": {s: describe(panel, s)["round_trip_bps"]
                                 for s in symbols},
                "symbols": symbols,
                "uncovered_symbols": uncovered(tf),
                "report": rep, "holdout": hold,
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
            print(f"[rd16] {key}: {status} trades={po['trades']} "
                  f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                  f"({row['seconds']}s)", flush=True)

    sel_path = out_dir / "wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    for (fam, panel, tf), vt in fam_cell_trades.items():
        if len(vt) < 2:
            continue
        sel = wf_select_judge(vt)
        summary[f"{fam}__{panel}__{tf}"] = {
            "family": fam, "panel": panel, "timeframe": tf,
            "variants_tried": len(vt), "wf_selection": sel}
        po = sel["procedure_pooled_oos"]
        print(f"[rd16] WF-SELECT {fam} {panel} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(sel_path, summary)
    print(f"[rd16] done: {n} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
