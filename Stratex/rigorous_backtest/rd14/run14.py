"""Grid runner for TASK-STR-RD-014 (declared 96 cells).

Evaluates every declared configuration on crypto30 @ 4h and 1d with
the RD-002 judgement machinery (rd2.stats2 fold_report / holdout2 /
check_bar2), plus a full 2x-cost re-evaluation of every cell. Emits
JSON lines on stdout: one meta line, one benchmark line per timeframe,
one row per cell. Verdicts (Bonferroni at the declared global counter,
DSR, candidate/watchlist) are assigned in synth14.py.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd14.run14 > rows.jsonl
"""
from __future__ import annotations

import json
import time

import numpy as np

from ..rd2.panels import fold_profile, load_panel
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from ..simulator import trade_metrics
from .family14 import COST_PER_TURNOVER, build_configs, eval_config

OOS_START, OOS_END = "2024-07-01", "2026-11-01"


def _coverage(datasets: dict, tf: str) -> list[dict]:
    rows = []
    for sym in sorted(datasets.keys()):
        ds = datasets[sym]
        man = ds.manifest or {}
        rows.append({
            "symbol": sym, "tf": tf, "rows": int(len(ds.df)),
            "first_bar_utc": ds.df.index[0].isoformat(),
            "last_bar_utc": ds.df.index[-1].isoformat(),
            "csv_sha256_16": (man.get("csv_sha256")
                              or man.get("derived_from_csv_sha256")
                              or "")[:16],
            "source": man.get("source"),
        })
    return rows


def _btc_benchmark(datasets: dict) -> dict:
    df = datasets["BTCUSDT"].df
    win = df.loc[OOS_START:OOS_END]
    r = float(win["close"].iloc[-1] / win["close"].iloc[0] - 1.0)
    return {"symbol": "BTCUSDT", "window": [OOS_START, OOS_END],
            "buy_hold_return": r}


def main() -> int:
    t0 = time.time()
    configs = build_configs()
    print(json.dumps({"type": "meta", "task": "TASK-STR-RD-014",
                      "family": "vol_targeted_trend_dd_brake",
                      "n_configs": len(configs),
                      "cost_per_turnover": COST_PER_TURNOVER,
                      "cost2x_per_turnover": COST_PER_TURNOVER * 2}),
          flush=True)
    for tf in ("4h", "1d"):
        datasets = load_panel("crypto30", tf)
        symbols = sorted(datasets.keys())
        print(json.dumps({"type": "coverage", "tf": tf,
                          "symbols_loaded": symbols,
                          "series": _coverage(datasets, tf)}), flush=True)
        print(json.dumps({"type": "benchmark", "tf": tf,
                          **_btc_benchmark(datasets)}), flush=True)
        cache1: dict = {}
        cache2: dict = {}
        for cfg in [c for c in configs if c["tf"] == tf]:
            trades = eval_config(cfg, datasets, COST_PER_TURNOVER, cache1)
            rep = fold_report(trades, fold_profile("crypto30", tf), symbols)
            ho = holdout2(rep, symbols)
            bar = check_bar2(rep, ho)
            st = trade_stats(trades)
            trades2 = eval_config(cfg, datasets, COST_PER_TURNOVER * 2,
                                  cache2)
            po2 = trade_metrics(trades2)
            row = {"type": "row", **cfg,
                   "status": "EVALUATED",
                   "pooled_oos": rep["pooled_oos"],
                   "per_fold": rep["per_fold"],
                   "per_symbol_oos": rep["per_symbol_oos"],
                   "fold_profile": rep["fold_profile"],
                   "holdout": ho, "bar": bar, "trade_stats": st,
                   "cost2x_pooled_oos": po2}
            print(json.dumps(row), flush=True)
        print(json.dumps({"type": "tf_done", "tf": tf,
                          "elapsed_s": round(time.time() - t0, 1)}),
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
