"""Governed + discovery module-cell runner (TASK-STR-RD-002, Stage B).

  python3 -m rigorous_backtest.rd2.modrun --kind governed \
      --out-dir results_rd2 [--cells crypto30:4h,forex12:1d] \
      [--modules strategy_bb_reversion] [--budget 300]

Rows checkpoint per cell; existing rows are skipped. One cell = one
trial in the global counter.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..rd.common import dump_json, trades_to_json
from ..rd.stage1 import candidate_map
from .gov2 import adx_production_filter, eval_module_cell, make_row
from .panels import fold_profile, load_panel
from .stats2 import trade_stats  # noqa: F401  (re-export convenience)

GOVERNED = {
    "strategy_bb_reversion": ["bare"],
    "strategy_supertrend": ["bare"],
    "strategy_adx_ema": ["bare", "production"],
    "strategy_factory_winner_1": ["bare"],
    "strategy_factory_winner_2": ["bare"],
    "strategy_factory_winner_3": ["bare"],
    "strategy_factory_winner_4": ["bare"],
    "strategy_factory_winner_5": ["bare"],
}
GOV_CELLS = [("crypto30", "1d"), ("crypto30", "4h"), ("crypto30", "1h"),
             ("forex12", "1d"), ("forex12", "4h"),
             ("comm7", "1d"), ("comm7", "4h"), ("idx7", "1d")]
DISC_CELLS = [("crypto30", "1d"), ("forex28", "1d"), ("comm7", "1d"),
              ("idx7", "1d"), ("crypto12", "4h"), ("forex12", "4h")]


def _save_screen(row) -> bool:
    po = row["report"]["pooled_oos"]
    return (po.get("expectancy_net") or -9) > -0.005 or \
        (po.get("profit_factor_net") or 0) >= 0.98 or \
        row["bar"]["passes_bar"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["governed", "discovery"], required=True)
    ap.add_argument("--stratex-root", default=".")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cells", default="")
    ap.add_argument("--modules", default="")
    ap.add_argument("--budget", type=float, default=300.0)
    args = ap.parse_args()
    root = Path(args.stratex_root).resolve()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / ("gov_rows" if args.kind == "governed" else "disc_rows")
    rows_dir.mkdir(parents=True, exist_ok=True)
    cells = [tuple(c.split(":")) for c in args.cells.split(",") if c] or \
        (GOV_CELLS if args.kind == "governed" else DISC_CELLS)
    only_mods = {s for s in args.modules.split(",") if s}

    if args.kind == "governed":
        modmap = {m: root / f"{m}.py" for m in GOVERNED}
        configs = GOVERNED
    else:
        modmap = candidate_map(root)
        configs = {m: ["discovery"] for m in modmap}

    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel(panel, tf)
        return panel_cache[(panel, tf)]

    gate_filter = None
    n = 0
    for module_name, cfgs in configs.items():
        if only_mods and module_name not in only_mods:
            continue
        for cfg in cfgs:
            for panel, tf in cells:
                if cfg == "production" and not panel.startswith("crypto"):
                    continue
                key = f"{module_name}__{cfg}__{panel}__{tf}"
                row_path = rows_dir / f"{key}.json"
                if row_path.exists():
                    continue
                datasets = get_panel(panel, tf)
                if not datasets:
                    continue
                filt = None
                if cfg == "production":
                    if gate_filter is None:
                        from .panels import load_panel as _lp
                        from ..rd.stage2 import btc_gate_series
                        btc4h = _lp("crypto30", "4h")["BTCUSDT"]
                        gate_filter = adx_production_filter(
                            btc_gate_series(btc4h.df))
                    filt = gate_filter
                t0 = time.time()
                status, trades, detail = eval_module_cell(
                    module_name, modmap[module_name], root, datasets, panel,
                    max_seconds_per_symbol=args.budget, signal_filter=filt)
                symbols = sorted(datasets.keys())
                row = make_row(module_name, cfg, panel, tf, status, trades,
                               detail, symbols, fold_profile(panel, tf))
                row["seconds"] = round(time.time() - t0, 2)
                if _save_screen(row):
                    row["trades"] = trades_to_json(trades)
                dump_json(row_path, row)
                n += 1
                po = row["report"]["pooled_oos"]
                print(f"[modrun] {key}: {status} trades={po['trades']} "
                      f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
                      f"({row['seconds']}s)", flush=True)
    print(f"[modrun] done: {n} new cells", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
