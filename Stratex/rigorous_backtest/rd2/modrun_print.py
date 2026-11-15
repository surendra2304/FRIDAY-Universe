"""Print-mode module-cell evaluator (workaround driver).

Identical evaluation to modrun.py, but prints each row as a JSON line
to stdout instead of writing files (used when local writes are
unavailable; the caller persists the lines). Checkpointing is the
caller's job: pass only the cells that still need evaluating.

  python3 -m rigorous_backtest.rd2.modrun_print governed \
      strategy_supertrend bare crypto30 1d
  python3 -m rigorous_backtest.rd2.modrun_print discovery \
      <module> discovery <panel> <tf>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ..rd.stage1 import candidate_map
from .gov2 import adx_production_filter, eval_module_cell, make_row
from .modrun import GOVERNED
from .panels import fold_profile, load_panel


def main() -> int:
    kind, module_name, config, panel, tf = sys.argv[1:6]
    root = Path(".").resolve()
    if kind == "governed":
        file_path = root / f"{module_name}.py"
    else:
        file_path = candidate_map(root)[module_name]
    datasets = load_panel(panel, tf)
    filt = None
    if config == "production":
        from ..rd.stage2 import btc_gate_series
        btc4h = load_panel("crypto30", "4h")["BTCUSDT"]
        filt = adx_production_filter(btc_gate_series(btc4h.df))
    t0 = time.time()
    status, trades, detail = eval_module_cell(
        module_name, file_path, root, datasets, panel,
        max_seconds_per_symbol=300.0, signal_filter=filt)
    symbols = sorted(datasets.keys())
    row = make_row(module_name, config, panel, tf, status, trades,
                   detail, symbols, fold_profile(panel, tf))
    row["seconds"] = round(time.time() - t0, 2)
    from .modrun import _save_screen
    if _save_screen(row):
        from ..rd.common import trades_to_json
        tj = trades_to_json(trades)
        for k in range(0, len(tj), 50):
            print("TRADESJSON:" + json.dumps(tj[k:k + 50], default=str),
                  flush=True)
    print("ROWJSON:" + json.dumps(row, default=str), flush=True)
    po = row["report"]["pooled_oos"]
    print(f"[print] {module_name}:{config}@{panel}/{tf}: {status} "
          f"trades={po['trades']} exp={po['expectancy_net']} "
          f"pf={po['profit_factor_net']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
