"""TASK-STR-RD-020 runner — executes the frozen declaration exactly
once per cell (4 cells), writes synthesis.json. Research only.

Usage (at the future declared run, NOT before the issue #35 claim is
read back and the coordinator orders the run):

    python3 run_rotbrake.py [cache_dir] [n_global]

cache_dir defaults to ~/workspace/str-rd2/cache2 (the hash-verified
RD-013 panel). n_global defaults to the declaration's frozen minimum
(3,897); the run must pass the re-read ledger value if higher:
N_global = max(ledger entering N at run time, 3,893) + 4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rotbrake import (KS, LOOKBACKS, evaluate_bar, load_closes,
                      run_config, summarise)

DECLARED_MIN_N_GLOBAL = 3897


def main() -> None:
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path.home() / "workspace/str-rd2/cache2"
    n_global = int(sys.argv[2]) if len(sys.argv) > 2 else DECLARED_MIN_N_GLOBAL
    if n_global < DECLARED_MIN_N_GLOBAL:
        raise SystemExit(
            f"n_global {n_global} below the declaration's frozen minimum "
            f"{DECLARED_MIN_N_GLOBAL}; refusing to run under-charged")
    closes, provenance = load_closes(cache)
    out_rows = []
    for L in LOOKBACKS:
        for k in KS:
            res = run_config(closes, L, k)
            row = {"lookback_days": L, "top_k": k, "cadence": "weekly",
                   "mode": "long_flat", "brake": "frozen_v1",
                   **summarise(res)}
            bar = evaluate_bar(row, n_global)
            entry = {**row, "bar": bar}
            if bar["verdict"] == "MECHANICAL_PASS_X2_PENDING":
                res2 = run_config(closes, L, k, cost_mult=2.0)
                row2 = summarise(res2)
                entry["x2_cost"] = {"oos_compounded": row2["oos_compounded"],
                                    "oos_period_pf": row2["oos_period_pf"]}
                entry["bar"] = evaluate_bar(row, n_global, x2_row=row2)
            entry["transitions"] = res["transitions"]
            out_rows.append(entry)
    out = {"task": "TASK-STR-RD-020", "family": "cross_asset_rotation_drawdown_brake",
           "n_global": n_global, "provenance": provenance, "rows": out_rows}
    dest = Path(__file__).resolve().parent / "synthesis.json"
    dest.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
