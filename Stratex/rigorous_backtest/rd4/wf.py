"""RD-004 wf-select procedure row (checkpointed execution stage 3).

  python3 -m rigorous_backtest.rd4.wf --tf 15m --out-dir results_rd4

Runs rd.common.wf_select_judge over the timeframe's 16 assembled
variants (legacy sort: IS net PF, then win rate; expanding pre-fold
in-sample), reconstructs the procedure's pooled OOS trade list from
the per-fold picks, and writes rows/wf_<tf>.json with the same
judgement inputs as a config row (fold report, holdout, bar, trade
stats, 2x metrics from the same picks at 2x costs). One procedure per
timeframe = one counted trial.
"""
from __future__ import annotations

import argparse, gzip, sys
from pathlib import Path

import pandas as pd

from ..rd.common import wf_select_judge
from ..simulator import Trade
from ..walkforward import FOLDS, trades_in_window
from ..rd2.panels import CRYPTO30
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_rd4 import MODES, SIGNALS
from .run_rd4 import STANDARD, _dump_json_retry


def _load_trades(path: Path) -> list[Trade]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        df = pd.read_csv(fh, parse_dates=["entry_time", "exit_time"])
    return [Trade(r.symbol, r.entry_time, r.exit_time, r.side, 0.0, 0.0,
                  float(r.net_return), r.exit_reason)
            for r in df.itertuples()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", required=True, choices=["15m", "2h"])
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    trades_dir = out_dir / "rows" / "trades"
    var1, var2 = {}, {}
    for sig in SIGNALS:
        for mode in MODES:
            name = f"{sig}_{mode}"
            var1[name] = _load_trades(
                trades_dir / f"{args.tf}_{sig}_{mode}_1x.csv.gz")
            var2[name] = _load_trades(
                trades_dir / f"{args.tf}_{sig}_{mode}_2x.csv.gz")
    proc = wf_select_judge(var1)
    picks = {p["fold"]: p["pick"] for p in proc["picks"]}
    proc1: list[Trade] = []
    proc2: list[Trade] = []
    for fid, s, e in FOLDS:
        pick = picks.get(fid)
        if pick:
            proc1.extend(trades_in_window(var1[pick], s, e))
            proc2.extend(trades_in_window(var2[pick], s, e))
    rep = fold_report(proc1, STANDARD, CRYPTO30)
    rep2 = fold_report(proc2, STANDARD, CRYPTO30)
    ho = holdout2(rep, CRYPTO30)
    row = {
        "family": "vol_regime_trend", "procedure": f"wf_select[{args.tf}]",
        "timeframe": args.tf, "panel": "crypto30", "status": "EVALUATED",
        "picks": proc["picks"],
        "variants_considered": proc["variants_considered"],
        "report": rep, "holdout": ho, "bar": check_bar2(rep, ho),
        "trade_stats": trade_stats(proc1),
        "metrics_2x": {"pooled_oos": rep2["pooled_oos"],
                       "per_fold": rep2["per_fold"]},
    }
    _dump_json_retry(out_dir / "rows" / f"wf_{args.tf}.json", row)
    po = rep["pooled_oos"]
    print(f"wf_select[{args.tf}]: OOS trades={po['trades']} "
          f"exp={po['expectancy_net']} PF={po['profit_factor_net']} "
          f"picks={picks}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
