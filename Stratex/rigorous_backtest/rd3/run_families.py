"""Stage-2 runner for TASK-STR-RD-003 (new pre-declared families).

Mirrors rd2/grid.py's judgement exactly (same fold profiles, holdout,
bar, costs, trade persistence screen); only the signal sources differ.
One (config, panel, timeframe) cell = one trial in the global counter,
whatever its outcome. Rows checkpoint to <out-dir>/stage2_rows/ and are
skipped on re-run.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd3.run_families \
      --out-dir results_rd3 [--families funding_extremes,...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from ..rd.common import atr, dump_json, trades_to_json, wf_select_judge
from ..rd.fastsim import simulate_entries
from ..rd2.costs2 import costs_for, describe
from ..rd2.families2 import warmup_for
from ..rd2.panels import fold_profile, load_panel
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_rd3 import (build_configs_rd3, funding_features,
                           sig_funding, sig_leadlag, sig_overnight,
                           sig_volswitch)

FUND_CACHE = Path("/home/hatch/workspace/str-rd3/cache_funding")
SAVE_SCREEN = lambda po: (po.get("expectancy_net") or -9) > -0.005 or \
    (po.get("profit_factor_net") or 0) >= 0.98


def load_funding(symbol: str) -> pd.DataFrame:
    """Funding prints with manifest integrity verification."""
    csv = FUND_CACHE / f"FUND_{symbol}.csv"
    man = json.loads((FUND_CACHE / f"FUND_{symbol}.csv.json").read_text())
    digest = hashlib.sha256(csv.read_bytes()).hexdigest()
    if digest != man["csv_sha256"]:
        raise RuntimeError(f"funding cache integrity failure: {symbol}")
    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    df.index = df.index.tz_convert("UTC") if df.index.tz is not None \
        else df.index.tz_localize("UTC")
    return df.rename(columns={"funding_rate": "rate"})


def _spec_for(cfg: dict, tf: str) -> dict:
    spec = dict(cfg["spec"])
    if "max_bars_by_tf" in spec:
        spec["max_bars"] = spec.pop("max_bars_by_tf")[tf]
    return spec


def eval_cell(cfg, panel, tf, datasets):
    warmup = warmup_for(tf)
    spec = _spec_for(cfg, tf)
    trades = []
    traded_symbols = sorted(datasets.keys())
    if cfg["kind"] == "funding":
        for sym, ds in datasets.items():
            prints = load_funding(sym)
            feat = funding_features(prints, ds.df.index)
            entries = sig_funding(ds.df, feat, cfg["sig_kind"],
                                  cfg["pctl"] or 0.0, cfg["thr"] or 0.0,
                                  warmup)
            a = atr(ds.df, 14).to_numpy(dtype=float)
            trades.extend(simulate_entries(
                ds.df, entries, a, spec, sym, costs_for(panel, sym)))
    elif cfg["kind"] == "overnight":
        for sym, ds in datasets.items():
            entries = sig_overnight(ds.df, cfg["sig_kind"], warmup)
            a = atr(ds.df, 14).to_numpy(dtype=float)
            trades.extend(simulate_entries(
                ds.df, entries, a, spec, sym, costs_for(panel, sym)))
    elif cfg["kind"] == "leadlag":
        btc = datasets["BTCUSDT"].df
        traded_symbols = sorted(s for s in datasets if s != "BTCUSDT")
        for sym in traded_symbols:
            ds = datasets[sym]
            entries = sig_leadlag(ds.df, btc, cfg["k"], cfg["theta"],
                                  warmup)
            a = atr(ds.df, 14).to_numpy(dtype=float)
            trades.extend(simulate_entries(
                ds.df, entries, a, spec, sym, costs_for(panel, sym)))
    elif cfg["kind"] == "volswitch":
        for sym, ds in datasets.items():
            brk, rev = sig_volswitch(ds.df, cfg["lo"], cfg["hi"], warmup)
            a = atr(ds.df, 14).to_numpy(dtype=float)
            trades.extend(simulate_entries(
                ds.df, brk, a, spec, sym, costs_for(panel, sym)))
            trades.extend(simulate_entries(
                ds.df, rev, a, cfg["spec_rev"], sym,
                costs_for(panel, sym)))
        trades.sort(key=lambda t: t.entry_time)
    else:
        raise ValueError(cfg["kind"])
    return trades, traded_symbols


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--families", default="")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "stage2_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.families.split(",") if s}
    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel(panel, tf)
        return panel_cache[(panel, tf)]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n = 0
    for cfg in build_configs_rd3():
        if only and cfg["family"] not in only:
            continue
        for panel, tf in cfg["cells"]:
            key = f"{cfg['family']}__{cfg['variant']}__{panel}__{tf}"
            row_path = rows_dir / f"{key}.json"
            if row_path.exists():
                # reload trades for the wf-select control on re-runs
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
                trades, symbols = eval_cell(cfg, panel, tf, datasets)
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
                "panel": panel, "timeframe": tf, "stage": "rd3_stage2",
                "status": status, "error": err,
                "spec": _spec_for(cfg, tf),
                "costs_rt_bps": {s: describe(panel, s)["round_trip_bps"]
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
            fam_cell_trades.setdefault((cfg["family"], panel, tf), {})[
                cfg["variant"]] = trades
            n += 1
            print(f"[rd3] {key}: {status} trades={po['trades']} "
                  f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                  f"({row['seconds']}s)", flush=True)

    sel_path = out_dir / "stage2_wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    for (fam, panel, tf), vt in fam_cell_trades.items():
        if len(vt) < 2:
            continue
        sel = wf_select_judge(vt)
        summary[f"{fam}__{panel}__{tf}"] = {
            "family": fam, "panel": panel, "timeframe": tf,
            "variants_tried": len(vt), "wf_selection": sel}
        po = sel["procedure_pooled_oos"]
        print(f"[rd3] WF-SELECT {fam} {panel} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(sel_path, summary)
    print(f"[rd3] done: {n} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
