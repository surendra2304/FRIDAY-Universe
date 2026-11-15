"""Sanity anchor for TASK-STR-RD-006 (harness fidelity).

Re-runs RD-001's published ts_momentum roc42_4h cell (BTC/ETH/SOL)
through the untouched RD-002 chain (rd2.panels -> rd2.grid.eval_single
-> rd2.stats2.fold_report) and compares against the archived row:
303 trades, expectancy 0.0024275740638451445, PF 1.0969220482985518.
No RD-006 number is trusted unless this reproduces bit-identically.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd6.anchor_check --out results_rd6/sanity_anchor.json
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..rd.common import dump_json
from ..rd2.families2 import build_configs
from ..rd2.grid import eval_single
from ..rd2.panels import load_panel
from ..rd2.stats2 import fold_report

EXPECTED = {"trades": 303,
            "expectancy_net": 0.0024275740638451445,
            "profit_factor_net": 1.0969220482985518}
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    datasets = {s: ds for s, ds in load_panel("crypto12", "4h").items()
                if s in SYMBOLS}
    cfg = next(c for c in build_configs()
               if c["family"] == "ts_momentum" and c["variant"] == "roc42")
    trades = eval_single(cfg, "crypto12", "4h", datasets, None)
    rep = fold_report(trades, ["W1", "W2", "W3", "W4", "W5"], SYMBOLS)
    po = rep["pooled_oos"]
    got = {"trades": po["trades"], "expectancy_net": po["expectancy_net"],
           "profit_factor_net": po["profit_factor_net"]}
    match = (got["trades"] == EXPECTED["trades"]
             and got["expectancy_net"] == EXPECTED["expectancy_net"]
             and got["profit_factor_net"] == EXPECTED["profit_factor_net"])
    payload = {"anchor": "RD-001 ts_momentum roc42_4h BTC/ETH/SOL via rd2 chain",
               "expected": EXPECTED, "got": got, "bit_identical": match}
    dump_json(Path(args.out), payload)
    print(f"[anchor] got={got} bit_identical={match}", flush=True)
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
