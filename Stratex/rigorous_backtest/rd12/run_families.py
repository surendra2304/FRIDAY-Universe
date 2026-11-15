"""Runner for TASK-STR-RD-012 (order-flow proxy families).

Mirrors rd3/run_families.py's judgement exactly (same fold profile,
holdout, bar, costs, trade persistence screen); only the signal
sources and the panel loader differ. One (config, panel, timeframe)
cell = one trial in the global counter, whatever its outcome. Rows
checkpoint to <out-dir>/rows/ and are skipped on re-run.

Panels: crypto30 @ 1h comes from the RD-002 verified cache
(rd2.panels). crypto30 @ 15m: the 13 symbols cached by RD-002 are
loaded from that cache (hash-verified by the data_feed contract);
the remaining 17 are fetched from Binance Vision into the RD-012
crew cache under the identical contract (per-zip SHA-256, canonical
CSV SHA-256, gap audit) — months 2023-10..2026-10, matching the
programme's 15m range. Nothing is interpolated or substituted.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd12.run_families \
      --out-dir results_rd12 [--families cvd_momentum,...] \
      [--double-costs]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from ..data_feed import load_dataset
from ..rd.common import atr, dump_json, trades_to_json, wf_select_judge
from ..rd.fastsim import simulate_entries
from ..rd2.costs2 import costs_for, describe, double
from ..rd2.panels import CACHE as RD2_CACHE
from ..rd2.panels import CRYPTO30, fold_profile, load_panel
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_rd12 import (WARMUP, build_configs_rd12, sig_cvd_divergence,
                            sig_cvd_momentum, sig_vol_climax,
                            sig_vol_confirmed_momentum)

RD12_CACHE = Path("/home/hatch/workspace/rd-012/cache")
SAVE_SCREEN = lambda po: (po.get("expectancy_net") or -9) > -0.005 or \
    (po.get("profit_factor_net") or 0) >= 0.98


def load_panel_rd12(tf: str) -> dict:
    if tf == "1h":
        return load_panel("crypto30", "1h")
    if tf != "15m":
        raise ValueError(tf)
    out = {}
    for sym in CRYPTO30:
        cached = RD2_CACHE / f"{sym}_15m_2023-10_2026-10.csv"
        cache_dir = RD2_CACHE if cached.exists() else RD12_CACHE
        out[sym] = load_dataset(sym, "15m", "2023-10", "2026-10",
                                cache_dir=cache_dir)
    return out


def _spec_for(cfg: dict, tf: str) -> dict:
    spec = dict(cfg["spec"])
    if "max_bars_by_tf" in spec:
        spec["max_bars"] = spec.pop("max_bars_by_tf")[tf]
    return spec


def eval_cell(cfg, panel, tf, datasets, double_costs=False):
    spec = _spec_for(cfg, tf)
    p = cfg["params"]
    trades = []
    for sym, ds in datasets.items():
        if cfg["kind"] == "cvd_momentum":
            entries = sig_cvd_momentum(ds.df, p["proxy"], p["window"],
                                       p["slope_bars"], WARMUP)
        elif cfg["kind"] == "vol_confirmed_momentum":
            entries = sig_vol_confirmed_momentum(ds.df, p["n"], p["m"],
                                                 p["zstar"], WARMUP)
        elif cfg["kind"] == "cvd_divergence":
            entries = sig_cvd_divergence(ds.df, p["n"], p["window"], WARMUP)
        elif cfg["kind"] == "vol_climax_reversal":
            entries = sig_vol_climax(ds.df, p["m"], p["zstar"], p["s"],
                                     WARMUP)
        else:
            raise ValueError(cfg["kind"])
        a = atr(ds.df, 14).to_numpy(dtype=float)
        costs = costs_for(panel, sym)
        if double_costs:
            costs = double(costs)
        trades.extend(simulate_entries(ds.df, entries, a, spec, sym, costs))
    trades.sort(key=lambda t: t.entry_time)
    return trades, sorted(datasets.keys())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--families", default="")
    ap.add_argument("--double-costs", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / ("rows_2x" if args.double_costs else "rows")
    rows_dir.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.families.split(",") if s}
    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel_rd12(tf)
        return panel_cache[(panel, tf)]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n = 0
    for cfg in build_configs_rd12():
        if only and cfg["family"] not in only:
            continue
        for panel, tf in cfg["cells"]:
            key = f"{cfg['family']}__{cfg['variant']}__{panel}__{tf}"
            row_path = rows_dir / f"{key}.json"
            if row_path.exists():
                if not args.double_costs:
                    row = json.loads(row_path.read_text())
                    if "trades" in row:
                        from ..rd.common import trades_from_json
                        fam_cell_trades.setdefault(
                            (cfg["family"], panel, tf), {})[cfg["variant"]] = \
                            trades_from_json(row["trades"])
                continue
            datasets = get_panel(panel, tf)
            if not datasets:
                continue
            t0 = time.time()
            try:
                trades, symbols = eval_cell(cfg, panel, tf, datasets,
                                            args.double_costs)
                status = "EVALUATED" if trades else "NO_TRADES"
                err = None
            except Exception as exc:  # noqa: BLE001 - recorded as verdict
                trades, symbols, status = [], sorted(datasets.keys()), "BROKEN"
                err = f"{type(exc).__name__}: {exc}"
            profile = fold_profile(panel, tf)
            rep = fold_report(trades, profile, symbols)
            hold = holdout2(rep, symbols)
            po = rep["pooled_oos"]
            row = {
                "family": cfg["family"], "variant": cfg["variant"],
                "panel": panel, "timeframe": tf, "stage": "rd12",
                "status": status, "error": err,
                "params": cfg["params"], "spec": _spec_for(cfg, tf),
                "costs_multiplier": 2 if args.double_costs else 1,
                "costs_rt_bps": {s: describe(panel, s)["round_trip_bps"]
                                 * (2 if args.double_costs else 1)
                                 for s in symbols},
                "symbols": symbols, "report": rep, "holdout": hold,
                "bar": check_bar2(rep, hold),
                "trade_stats": trade_stats(
                    [t for t in trades
                     if t.entry_time >= pd.Timestamp(
                         rep["per_fold"][profile[0]]["oos_start"], tz="UTC")]),
                "seconds": round(time.time() - t0, 2),
            }
            if SAVE_SCREEN(po) or row["bar"]["passes_bar"]:
                row["trades"] = trades_to_json(trades)
            dump_json(row_path, row)
            if not args.double_costs:
                fam_cell_trades.setdefault((cfg["family"], panel, tf), {})[
                    cfg["variant"]] = trades
            n += 1
            print(f"[rd12] {key}: {status} trades={po['trades']} "
                  f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                  f"({row['seconds']}s)", flush=True)

    if not args.double_costs:
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
            print(f"[rd12] WF-SELECT {fam} {panel} {tf}: trades={po['trades']} "
                  f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
                  flush=True)
        dump_json(sel_path, summary)
    print(f"[rd12] done: {n} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
