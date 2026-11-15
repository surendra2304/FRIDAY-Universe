"""Synthesis for TASK-STR-RD-016.

Mirrors rd3/synth3.py's judgement construction (same ranked-row shape,
same exact 2x-cost construction from saved trades), with the trial
accounting frozen in results_rd16/declaration.json:

* prior global counter = 1,926 (programme floor through RD-005)
  + RD-015's 8 = 1,934 entering this round;
* RD-016 declares 12 trials (8 fixed-config cells + 4 wf-select
  procedures), so the Bonferroni gate is evaluated at the FINAL
  N_global = 1,946 (alpha = 2.5694e-05) regardless of how many cells
  evaluate — a declared-but-unevaluated cell still counts (the
  conservative direction);
* the GATE is the Bonferroni one-sided p from trade_stats, exactly as
  declared. Deflated Sharpe is disclosed where the cross-trial
  dispersion estimators are computable; RD-016 has only 8 cells, below
  the >= 10 qualifying rows the estimators require, so DSR is reported
  as non-computable in-round rather than estimated from too few rows.

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd16.synth16 \
      --work-dir /home/hatch/workspace/rd-016/results_rd16 \
      --out-dir /home/hatch/workspace/rd-016/results_rd16
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..rd.common import dump_json
from ..rd2.stats2 import FOLD_BOUNDS, deflated_sharpe
from .panels16 import fold_profile16

PRIOR_GLOBAL = 1934          # 1,926 floor + RD-015's 8
DECLARED_RD16_TRIALS = 12    # 8 cells + 4 wf-select procedures (frozen)
N_GLOBAL = PRIOR_GLOBAL + DECLARED_RD16_TRIALS   # 1,946


def _load_rows(d: Path) -> list[dict]:
    rows = []
    if not d.exists():
        return rows
    for p in sorted(d.glob("*.json")):
        rows.append(json.loads(p.read_text()))
    return rows


def _oos_windows(tf: str):
    return [(pd.Timestamp(FOLD_BOUNDS[f][0], tz="UTC"),
             pd.Timestamp(FOLD_BOUNDS[f][1], tz="UTC"))
            for f in fold_profile16(tf)]


def _pf(returns: list[float]):
    gains = sum(r for r in returns if r > 0)
    losses = -sum(r for r in returns if r < 0)
    if losses <= 0:
        return float("inf") if gains > 0 else None
    return gains / losses


def cost2x_pf(row: dict):
    """Exact 2x-cost PF over the row's pooled OOS trades (synth3)."""
    trades = row.get("trades")
    if not trades:
        return None
    wins = _oos_windows(row["timeframe"])
    rets = []
    for t in trades:
        et = pd.Timestamp(t["entry_time"])
        if not any(s <= et <= e for s, e in wins):
            continue
        gross = (t["exit_price"] / t["entry_price"] - 1.0) * \
            (1.0 if t["side"] == "LONG" else -1.0)
        net2x = 2.0 * t["net_return"] - gross
        rets.append(net2x)
    if len(rets) < 30:
        return None
    return _pf(rets)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    work = Path(args.work_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(work / "rows")
    wf: dict[str, dict] = {}
    sel_path = work / "wf_select.json"
    if sel_path.exists():
        wf = json.loads(sel_path.read_text())
    n_procedures = len(wf)
    n_evaluated = len(rows) + n_procedures

    # Dispersion estimators (mirror synth3): non-computable in-round
    # if fewer than 10 rows carry trade_stats with n >= 30.
    srs, inv_n, srs_200 = [], [], []
    for r in rows:
        ts = r.get("trade_stats") or {}
        if ts.get("n", 0) >= 30 and ts.get("sharpe_per_trade") is not None:
            srs.append(ts["sharpe_per_trade"])
            inv_n.append(1.0 / ts["n"])
            if ts["n"] >= 200:
                srs_200.append(ts["sharpe_per_trade"])
    sr_std_naive = float(np.std(srs)) if len(srs) >= 10 else None
    sr_std_naive200 = float(np.std(srs_200)) if len(srs_200) >= 10 else None
    sr_std = float(np.sqrt(np.mean(inv_n))) if len(inv_n) >= 10 else None
    dsr_note = None
    if sr_std is None:
        dsr_note = (f"DSR non-computable in-round: only {len(inv_n)} of "
                    f"the >= 10 qualifying rows (trade_stats n >= 30) "
                    f"the cross-trial dispersion estimator requires are "
                    f"available among RD-016's 8 cells. The declared "
                    f"gate (Bonferroni) does not use DSR.")

    ranked = []
    raw_by_key = {}
    for r in rows:
        po = r["report"]["pooled_oos"]
        ts = r.get("trade_stats") or {}
        sig = None
        if ts.get("n", 0) >= 30 and ts.get("p_one_sided") is not None:
            bonf = ts["p_one_sided"] < 0.05 / N_GLOBAL
            dsr = None
            if sr_std:
                dsr = deflated_sharpe(ts["sharpe_per_trade"], ts["n"],
                                      ts.get("skew") or 0.0,
                                      ts.get("kurtosis") or 3.0,
                                      N_GLOBAL, sr_std)
            sig = {"deflated_sharpe": dsr,
                   "bonferroni_pass": bool(bonf),
                   "passes": bool(bonf),
                   "source": "aggregates",
                   "p_one_sided": ts["p_one_sided"],
                   "dsr_naive_all": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"],
                       ts.get("skew") or 0.0, ts.get("kurtosis") or 3.0,
                       N_GLOBAL, sr_std_naive) if sr_std_naive else None,
                   "dsr_naive_200": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"],
                       ts.get("skew") or 0.0, ts.get("kurtosis") or 3.0,
                       N_GLOBAL, sr_std_naive200) if sr_std_naive200 else None}
        folds_pos = sum(1 for f in r["report"]["per_fold"].values()
                        if (f.get("expectancy_net") or -9) > 0
                        and (f.get("trades") or 0) > 0)
        key = (f"{r['family']}/{r['variant']}@{r['panel']}/{r['timeframe']}")
        raw_by_key[key] = r
        ranked.append({
            "family": r["family"], "variant": r["variant"],
            "panel": r["panel"], "timeframe": r["timeframe"],
            "status": r["status"],
            "oos_trades": po.get("trades"),
            "expectancy_net": po.get("expectancy_net"),
            "profit_factor_net": po.get("profit_factor_net"),
            "compounded_return_net": po.get("compounded_return_net"),
            "max_symbol_profit_share":
                (r.get("holdout") or {}).get("max_symbol_profit_share"),
            "positive_folds": folds_pos,
            "passes_bar": (r.get("bar") or {}).get("passes_bar", False),
            "significance": sig,
            "sig_pass": bool(sig and sig["passes"]),
        })
    ranked.sort(key=lambda x: (x["expectancy_net"] is not None,
                               x["expectancy_net"] or -9), reverse=True)
    for x in ranked:
        x["unit_suspect"] = abs(x["expectancy_net"] or 0) > 0.5

    candidates = [x for x in ranked if x["passes_bar"] and x["sig_pass"]
                  and not x["unit_suspect"]]
    passers = []
    for x in candidates:
        key = f"{x['family']}/{x['variant']}@{x['panel']}/{x['timeframe']}"
        pf2 = cost2x_pf(raw_by_key[key])
        x["cost2x_pf"] = pf2
        if pf2 is not None and pf2 >= 1.2:
            passers.append(x)
    near_bar = [x for x in ranked
                if (x["expectancy_net"] or -9) > 0
                and (x["profit_factor_net"] or 0) >= 1.15
                and (x["oos_trades"] or 0) >= 200]
    for x in near_bar:
        if "cost2x_pf" not in x:
            key = (f"{x['family']}/{x['variant']}@"
                   f"{x['panel']}/{x['timeframe']}")
            x["cost2x_pf"] = cost2x_pf(raw_by_key[key])
    watchlist = [x for x in ranked
                 if (x["expectancy_net"] or -9) > 0
                 and (x["oos_trades"] or 0) >= 100
                 and not x["passes_bar"]][:15]

    declared_cells = {
        ("london_drive", "drive_plain", "1h"),
        ("london_drive", "drive_narrow", "1h"),
        ("monday_gap_fade", "gap_0.5", "1d"),
        ("monday_gap_fade", "gap_1.0", "1d"),
        ("trend_pullback", "pb_ema100", "1d"),
        ("trend_pullback", "pb_ema200", "1d"),
        ("trend_pullback", "pb_ema100", "4h"),
        ("trend_pullback", "pb_ema200", "4h"),
    }
    have_cells = {(r["family"], r["variant"], r["timeframe"]) for r in rows}
    uncovered_cells = sorted(
        f"{f}/{v}@{tf}" for (f, v, tf) in declared_cells - have_cells)

    out = {
        "task": "TASK-STR-RD-016",
        "prior_global_trials": PRIOR_GLOBAL,
        "rd016_rows_evaluated": len(rows),
        "rd016_wf_select_procedures": n_procedures,
        "rd016_trials_evaluated": n_evaluated,
        "rd016_trials_declared_and_counted": DECLARED_RD16_TRIALS,
        "global_trials": N_GLOBAL,
        "uncovered_cells": uncovered_cells,
        "sr_std_across_trials": sr_std,
        "sr_std_naive_all": sr_std_naive,
        "sr_std_naive_200": sr_std_naive200,
        "dsr_note": dsr_note,
        "significance_method": (
            "GATE (as frozen in declaration.json): Bonferroni one-sided "
            "p < 0.05/N_global with N_global = 1,946 (1,926 programme "
            "floor + RD-015's 8 + RD-016's declared 12). Deflated "
            "Sharpe disclosed where computable, never gating; in this "
            "round it is non-computable (see dsr_note). 2x-cost "
            "sensitivity is computed exactly from saved trades (costs "
            "enter this harness only through net returns; exits are "
            "price-level based)."),
        "bonferroni_threshold_at_final_n": 0.05 / N_GLOBAL,
        "ranked_table": ranked,
        "candidates_pre_sensitivity": candidates,
        "passers_final": passers,
        "near_bar_for_2x_cost_sensitivity": near_bar,
        "watchlist": watchlist,
        "wf_select": {k: v["wf_selection"] for k, v in wf.items()},
    }
    dump_json(out_dir / "synthesis.json", out)
    print(f"[synth16] rows={len(rows)} procedures={n_procedures} "
          f"evaluated={n_evaluated} counted={DECLARED_RD16_TRIALS} "
          f"global={N_GLOBAL}")
    print(f"[synth16] candidates={len(candidates)} passers={len(passers)} "
          f"near_bar={len(near_bar)} uncovered={uncovered_cells}")
    for x in ranked:
        print(f"  row: {x['family']}/{x['variant']} @{x['panel']}/"
              f"{x['timeframe']} exp={x['expectancy_net']} "
              f"pf={x['profit_factor_net']} trades={x['oos_trades']} "
              f"bar={x['passes_bar']} sig={x['sig_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
