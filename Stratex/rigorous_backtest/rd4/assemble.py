"""RD-004 assembly (checkpointed execution stage 2): one config.

  python3 -m rigorous_backtest.rd4.assemble --tf 15m --signal don20 \
      --mode base --frag-dir results_rd4/frag --out-dir results_rd4

Reads the per-symbol fragments written by run_symbol, rebuilds the
pooled trade lists in CRYPTO30 order (the monolithic accumulation
order), computes the judged row (fold report, holdout, bar, trade
stats, 2x metrics) and writes rows/<tf>_<signal>_<mode>.json plus the
merged full-period trades CSVs under rows/trades/.
"""
from __future__ import annotations

import argparse, csv, sys
from pathlib import Path

import pandas as pd

from ..simulator import Trade, trade_metrics
from ..rd2.costs2 import CRYPTO
from ..rd2.panels import CRYPTO30
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .run_rd4 import STANDARD, _dump_json_retry, _oos_trades, \
    _write_trades_csv


def _load_fragments(frag_dir: Path, stem: str,
                    symbols: list[str]) -> list[Trade]:
    trades: list[Trade] = []
    for sym in symbols:
        p = frag_dir / stem / f"{sym}.csv"
        if not p.exists():
            raise FileNotFoundError(f"missing fragment {p}")
        with open(p, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                trades.append(Trade(
                    row["symbol"], pd.Timestamp(row["entry_time"]),
                    pd.Timestamp(row["exit_time"]), row["side"], 0.0, 0.0,
                    float(row["net_return"]), row["exit_reason"]))
    return trades


def _tuples(trades: list[Trade]) -> list[tuple]:
    return [(t.symbol, t.entry_time.isoformat(), t.exit_time.isoformat(),
             t.side, t.net_return, t.exit_reason) for t in trades]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", required=True, choices=["15m", "2h"])
    ap.add_argument("--signal", required=True)
    ap.add_argument("--mode", required=True)
    ap.add_argument("--frag-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--symbols", default="")  # comma list; default CRYPTO30
    args = ap.parse_args()
    symbols = [s for s in args.symbols.split(",") if s] or CRYPTO30
    frag_dir = Path(args.frag_dir)
    out_dir = Path(args.out_dir)
    stem = f"{args.tf}_{args.signal}_{args.mode}"
    t1 = _load_fragments(frag_dir, f"{stem}_1x", symbols)
    t2 = _load_fragments(frag_dir, f"{stem}_2x", symbols)
    rep = fold_report(t1, STANDARD, symbols)
    rep2 = fold_report(t2, STANDARD, symbols)
    ho = holdout2(rep, symbols)
    row = {
        "family": "vol_regime_trend", "signal": args.signal,
        "mode": args.mode, "variant": f"{args.signal}_{args.mode}",
        "panel": "crypto30", "timeframe": args.tf, "status": "EVALUATED",
        "costs": CRYPTO.describe(),
        "report": rep, "holdout": ho, "bar": check_bar2(rep, ho),
        "trade_stats": trade_stats(_oos_trades(t1)),
        "metrics_2x": {"pooled_oos": rep2["pooled_oos"],
                       "per_fold": rep2["per_fold"]},
        "full_period": trade_metrics(t1),
    }
    rows_dir = out_dir / "rows"
    _dump_json_retry(rows_dir / f"{stem}.json", row)
    _write_trades_csv(rows_dir / "trades" / f"{stem}_1x.csv.gz",
                      _tuples(t1))
    _write_trades_csv(rows_dir / "trades" / f"{stem}_2x.csv.gz",
                      _tuples(t2))
    po = rep["pooled_oos"]
    print(f"{stem}: OOS trades={po['trades']} exp={po['expectancy_net']} "
          f"PF={po['profit_factor_net']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
