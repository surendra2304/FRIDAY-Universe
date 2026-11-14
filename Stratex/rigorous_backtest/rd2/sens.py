"""2x-cost sensitivity for near-bar rows (TASK-STR-RD-002).

Re-evaluates ONE row specification with every cost doubled and prints
the resulting pooled OOS metrics as JSON. Run as a fresh process per
row so the cost patch never leaks into other evaluations.

  python3 -m rigorous_backtest.rd2.sens family <family> <variant> \
      <panel> <tf>
  python3 -m rigorous_backtest.rd2.sens module <module> <config> \
      <panel> <tf>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..simulator import Costs
from . import costs2


def _double_all():
    orig = costs2.costs_for
    def doubled(panel, symbol):
        c = orig(panel, symbol)
        return Costs(c.fee_bps_per_side * 2, c.slip_bps_per_side * 2)
    costs2.costs_for = doubled
    import rigorous_backtest.rd2.grid as grid
    import rigorous_backtest.rd2.gov2 as gov2
    grid.costs_for = doubled
    gov2.costs_for = doubled
    return doubled


def main() -> int:
    kind = sys.argv[1]
    _double_all()
    if kind == "family":
        _k, family, variant, panel, tf = sys.argv[1:6]
        from .families2 import build_configs
        from .grid import eval_single, eval_xs, eval_pairs
        from .panels import load_panel, fold_profile
        from .stats2 import fold_report
        cfg = next(c for c in build_configs()
                   if c["family"] == family and c["variant"] == variant)
        datasets = load_panel(panel, tf)
        aux = None
        if cfg["kind"] == "single":
            from .grid import AUX_TF
            if family == "mtf_confluence" and tf in AUX_TF:
                aux = load_panel(panel, AUX_TF[tf])
            trades = eval_single(cfg, panel, tf, datasets, aux)
        elif cfg["kind"] == "xs":
            trades = eval_xs(cfg, panel, tf, datasets)
        else:
            trades = eval_pairs(cfg, tf, datasets)
        rep = fold_report(trades, fold_profile(panel, tf),
                          sorted(datasets.keys()))
        print(json.dumps({"pooled_oos": rep["pooled_oos"]}))
        return 0
    if kind == "module":
        _k, module_name, config, panel, tf = sys.argv[1:6]
        from .gov2 import eval_module_cell, adx_production_filter
        from .panels import load_panel, fold_profile
        from .stats2 import fold_report
        root = Path(".").resolve()
        datasets = load_panel(panel, tf)
        filt = None
        if config == "production":
            from ..rd.stage2 import btc_gate_series
            btc4h = load_panel("crypto30", "4h")["BTCUSDT"]
            filt = adx_production_filter(btc_gate_series(btc4h.df))
        status, trades, _detail = eval_module_cell(
            module_name, root / f"{module_name}.py", root, datasets,
            panel, signal_filter=filt)
        rep = fold_report(trades, fold_profile(panel, tf),
                          sorted(datasets.keys()))
        print(json.dumps({"status": status, "pooled_oos": rep["pooled_oos"]}))
        return 0
    raise SystemExit(f"unknown kind {kind}")


if __name__ == "__main__":
    raise SystemExit(main())
