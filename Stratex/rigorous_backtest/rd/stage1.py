"""STAGE 1 — finish the discovery map (TASK-STR-RD-001).

Evaluates the 51 modules TASK-STR-BT-001 left UNTESTABLE ("not evaluated —
compute budget ended") with the identical harness discipline: the module's
own get_signal(), the MODULE simulation convention, 16 bps round-trip
costs, walk-forward OOS-only reporting. Each module's row is written to
<out-dir>/rows/<module>.json immediately (checkpointing); re-running skips
rows that already exist unless --force is given.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd.stage1 --modules strategy_breakout_retest \
      --cache-dir <cache> --out-dir <results_rd>
  python3 -m rigorous_backtest.rd.stage1 --combine --out-dir <results_rd>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ..module_eval import evaluate_module
from ..run_all import _infer_primary_timeframe
from .common import COSTS, dump_json, load_timeframe

GOVERNED_NAMES = {"strategy_bb_reversion", "strategy_factory_winner_1",
                  "strategy_factory_winner_2", "strategy_factory_winner_3",
                  "strategy_factory_winner_4", "strategy_factory_winner_5",
                  "strategy_supertrend", "strategy_adx_ema",
                  "strategy_factory_winners"}


def candidate_map(stratex_root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for fp in sorted(stratex_root.glob("strategy_*.py")):
        if fp.stem not in GOVERNED_NAMES:
            out[fp.stem] = fp
    strat_dir = stratex_root / "strategies"
    for fp in sorted(strat_dir.glob("*.py")):
        if fp.stem.startswith("__") or fp.stem == "strategy_registry":
            continue
        out[fp.stem] = fp
    return out


def gov_status(stratex_root: Path, module_name: str) -> str:
    try:
        if str(stratex_root) not in sys.path:
            sys.path.insert(0, str(stratex_root))
        from config_strategy import PRODUCTION_STRATEGY_REGISTRY as reg
    except Exception:
        return "UNREGISTERED"
    key = module_name[len("strategy_"):] if module_name.startswith("strategy_") else module_name
    entry = reg.get(key)
    return str(entry.get("status") or "UNREGISTERED").upper() if entry else "UNREGISTERED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratex-root", default=".")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--modules", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--combine", action="store_true")
    ap.add_argument("--max-seconds-per-symbol", type=float, default=900.0)
    args = ap.parse_args()

    stratex_root = Path(args.stratex_root).resolve()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "stage1_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)

    if args.combine:
        bt = json.loads((stratex_root / "rigorous_backtest" / "results" /
                         "phase_discovery.json").read_text())
        merged = {}
        for r in bt["rows"]:
            if r["status"] == "EVALUATED":
                merged[r["strategy"]] = {**r, "source": "TASK-STR-BT-001"}
        n_new = 0
        for p in sorted(rows_dir.glob("*.json")):
            row = json.loads(p.read_text())
            merged[row["strategy"]] = {**row, "source": "TASK-STR-RD-001 stage 1"}
            n_new += 1
        rows = [merged[k] for k in sorted(merged)]
        payload = {"phase": "rd_discovery_complete", "costs": COSTS.describe(),
                   "candidates": len(rows), "rows": rows,
                   "note": "BT-001 EVALUATED rows carried verbatim; all other "
                           "rows evaluated by TASK-STR-RD-001 stage 1."}
        dump_json(out_dir / "phase_rd_discovery.json", payload)
        from collections import Counter
        print("[combine]", Counter(r["status"] for r in rows), f"({n_new} new rows)")
        return 0

    cmap = candidate_map(stratex_root)
    wanted = [m.strip() for m in args.modules.split(",") if m.strip()]
    search_paths = [str(stratex_root), str(stratex_root / "strategies")]
    datasets_by_tf: dict[str, dict] = {}
    for name in wanted:
        row_path = rows_dir / f"{name}.json"
        if row_path.exists() and not args.force:
            print(f"[stage1] {name}: already done, skipping", flush=True)
            continue
        fp = cmap.get(name)
        if fp is None:
            print(f"[stage1] {name}: NOT FOUND in candidate map", flush=True)
            continue
        tf = _infer_primary_timeframe(fp)
        if tf not in datasets_by_tf:
            print(f"[stage1] loading {tf} datasets ...", flush=True)
            datasets_by_tf[tf] = load_timeframe(tf, Path(args.cache_dir))
        print(f"[stage1] {name} on {tf} ...", flush=True)
        t0 = time.time()
        try:
            row = evaluate_module(name, fp, search_paths, datasets_by_tf[tf],
                                  COSTS,
                                  max_seconds_per_symbol=args.max_seconds_per_symbol)
        except Exception as exc:  # noqa: BLE001 - recorded, never fatal
            row = {"strategy": name, "label": "BACKTEST-OOS", "status": "BROKEN",
                   "reason": f"harness-level failure: {type(exc).__name__}: {exc}"}
        row["scope"] = "discovery"
        row["governance_status"] = gov_status(stratex_root, name)
        row["elapsed_seconds"] = round(time.time() - t0, 1)
        dump_json(row_path, row)
        po = row.get("pooled_oos") or {}
        print(f"[stage1] {name}: status={row['status']} trades={po.get('trades')} "
              f"exp={po.get('expectancy_net')} pf={po.get('profit_factor_net')} "
              f"({row['elapsed_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
