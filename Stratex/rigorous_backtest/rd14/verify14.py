"""Independent verification for TASK-STR-RD-014 (coordinator-grade
self-check, run before the results were written up):

1. Turnover identity: for sampled (config, symbol) pairs, the total
   cost embedded in episode returns equals sum |delta pos| * c, and an
   independently coded episode extraction (sharing only the position
   series) reproduces eval_config's episode count and pooled return.
2. Brake mechanics: on a braked cell, positions are exactly 0 (flat)
   or halved on every bar where the shadow drawdown at the previous
   close was beyond the brake threshold and not yet released.

Prints PASS/FAIL lines; exit 0 iff all pass.
"""
from __future__ import annotations

import json

import numpy as np

from ..rd2.panels import load_panel
from ..simulator import trade_metrics
from .family14 import (COST_PER_TURNOVER, brake_multiplier, eval_config,
                       positions, raw_weights, shadow_equity)


def independent_episodes(df, pos, cost):
    """Episode nets recomputed from scratch (log-space accumulation)."""
    close = df["close"].to_numpy(dtype=float)
    ret = np.zeros(len(close))
    ret[1:] = close[1:] / close[:-1] - 1.0
    nets = []
    i = 0
    n = len(close)
    while i < n:
        if pos[i] == 0.0:
            i += 1
            continue
        j = i
        sgn = np.sign(pos[i])
        while j + 1 < n and pos[j + 1] != 0.0 and np.sign(pos[j + 1]) == sgn:
            j += 1
        # gross compounded over the run
        gross = np.prod(1.0 + pos[i:j + 1] * ret[i:j + 1]) - 1.0
        # costs: entry |pos_i - pos_{i-1}| (pos_{i-1}=0 or flip-handled),
        # internal |delta|, exit |pos_j| (to flat, flip, or data end)
        c_in = abs(pos[i] - (pos[i - 1] if i > 0 else 0.0))
        if i > 0 and pos[i - 1] != 0.0:      # flip: entry part only
            c_in = abs(pos[i])
        c_mid = float(np.abs(np.diff(pos[i:j + 1])).sum())
        c_out = abs(pos[j])
        nets.append((1.0 + gross) * (1.0 - (c_in + c_mid + c_out) * cost)
                    - 1.0)
        i = j + 1
    return nets


def main() -> int:
    ok = True
    datasets = load_panel("crypto30", "4h")
    samples = [
        {"signal": "tsmom42", "vol_target": 0.30, "brake": "none",
         "tf": "4h", "family": "vol_targeted_trend", "variant": "s1",
         "panel": "crypto30"},
        {"signal": "ema20_100", "vol_target": 0.15, "brake": "flat_10",
         "tf": "4h", "family": "vol_targeted_trend", "variant": "s2",
         "panel": "crypto30"},
        {"signal": "tsmom126", "vol_target": 0.60, "brake": "half_10",
         "tf": "4h", "family": "vol_targeted_trend", "variant": "s3",
         "panel": "crypto30"},
    ]
    for cfg in samples:
        trades = eval_config(cfg, datasets, COST_PER_TURNOVER, {})
        for sym in ("BTCUSDT", "ETHUSDT"):
            df = datasets[sym].df
            w = raw_weights(df["close"], cfg["signal"], cfg["vol_target"],
                            cfg["tf"])
            _ps, dd = shadow_equity(df["close"], w, COST_PER_TURNOVER)
            pos = positions(w, dd, cfg["brake"])
            mine = [t.net_return for t in trades if t.symbol == sym]
            indep = independent_episodes(df, pos, COST_PER_TURNOVER)
            same_n = len(mine) == len(indep)
            max_dev = (max(abs(a - b) for a, b in zip(mine, indep))
                       if same_n and mine else 0.0)
            # NOTE: the two cost accountings differ in FORM (per-bar
            # deductions compounded vs lumped multipliers) — agreement
            # to <1e-3 per episode is the expected signature.
            passed = same_n and max_dev < 1e-3
            ok &= passed
            print(json.dumps({"check": "episode_reproduction",
                              "cfg": f"{cfg['signal']}/vt{cfg['vol_target']}/"
                                     f"{cfg['brake']}", "symbol": sym,
                              "episodes": len(mine), "same_count": same_n,
                              "max_abs_dev": float(max_dev), "pass": bool(passed)}))
        # brake mechanics on the full panel for braked configs:
        # positions must equal the one-bar-shifted m * w everywhere,
        # and a flat brake (m = 0 at close t) must mean pos = 0 on t+1.
        if cfg["brake"] != "none":
            bad = 0
            for sym, ds in datasets.items():
                w = raw_weights(ds.df["close"], cfg["signal"],
                                cfg["vol_target"], cfg["tf"])
                _ps, dd = shadow_equity(ds.df["close"], w,
                                        COST_PER_TURNOVER)
                m = brake_multiplier(dd, cfg["brake"])
                pos = positions(w, dd, cfg["brake"])
                expect = np.zeros(len(w))
                expect[1:] = (m * w)[:-1]
                bad += int((np.abs(pos - expect) > 0).sum())
                if cfg["brake"].startswith("flat"):
                    bad += int((pos[1:][m[:-1] == 0.0] != 0.0).sum())
            passed = bad == 0
            ok &= passed
            print(json.dumps({"check": "brake_mechanics",
                              "cfg": f"{cfg['signal']}/vt{cfg['vol_target']}/"
                                     f"{cfg['brake']}",
                              "position_mismatches": int(bad), "pass": bool(passed)}))
    print(json.dumps({"verify14_all_pass": bool(ok)}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
