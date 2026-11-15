"""POST-HOC portfolio-lens diagnostic for TASK-STR-RD-014 (NOT part of
the declared bar; computed after the verdicts to answer one question:
did the brake cut drawdown the way it was built to?).

For each (signal, vol_target, timeframe) group and each brake: the
equal-weight portfolio of the 30 per-symbol bar-level strategy equity
curves (braked positions, 1x costs), restricted to bars in the OOS
window [2024-07-01, 2026-11-01). Reports compounded return and max
drawdown per group/brake. Positions are computed over full history
(brake state at the window start is the causal one); only the
compounding is windowed.

Usage: python3 -m rigorous_backtest.rd14.portfolio14 > portfolio.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..rd2.panels import load_panel
from .family14 import (BRAKES, COST_PER_TURNOVER, SIGNALS, VOL_TARGETS,
                       positions, raw_weights, shadow_equity)

OOS_START, OOS_END = "2024-07-01", "2026-11-01"


def _portfolio(datasets, signal, vt, brake, tf):
    curves = {}
    for sym, ds in datasets.items():
        df = ds.df
        w = raw_weights(df["close"], signal, vt, tf)
        _ps, dd = shadow_equity(df["close"], w, COST_PER_TURNOVER)
        pos = positions(w, dd, brake)
        ret = df["close"].pct_change().fillna(0.0).to_numpy(dtype=float)
        prev = np.concatenate([[0.0], pos[:-1]])
        r = pos * ret - np.abs(pos - prev) * COST_PER_TURNOVER
        curves[sym] = pd.Series(r, index=df.index)
    mat = pd.DataFrame(curves).loc[OOS_START:OOS_END]
    port = mat.mean(axis=1, skipna=True).fillna(0.0)
    eq = np.cumprod(1.0 + port.to_numpy(dtype=float))
    peak = np.maximum.accumulate(eq)
    return {"compounded": float(eq[-1] - 1.0),
            "max_dd": float((eq / peak - 1.0).min()),
            "bars": int(len(port))}


def main() -> int:
    out = []
    for tf in ("4h", "1d"):
        datasets = load_panel("crypto30", tf)
        for sig in SIGNALS:
            for vt in VOL_TARGETS:
                row = {"tf": tf, "signal": sig, "vol_target": vt}
                for br in BRAKES:
                    row[br] = _portfolio(datasets, sig, vt, br, tf)
                out.append(row)
                print(json.dumps({"type": "group", **row}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
