"""Synthesis for TASK-STR-RD-008: verdicts per config vs the standing bar.

Reads results_rd8/rows/*.json + wf_select.json (produced by run_idx),
applies the declared judgement (bar + Bonferroni at the running global
floor N + 2x-cost), and writes results_rd8/synthesis.json. Also prints
the ranked markdown table used in RESULTS_RD8.md.

Global N floor components (all evidenced, none invented):
  1,557  global counter through RD-002 (RESULTS_RD2.md)
  + 152  RD-003 Stage 1 (RESULTS_RD3.md)
  + S2   RD-003 Stage 2, counted here from
         results_rd3/stage2_declaration.json (variants x cells +
         wf-select groups)
  + 21   RD-003 Stage 2B (its trial_accounting: 14 cells + 7 wf)
  + RD-008's own trials (43 cells + wf procedures actually run)
Concurrent Wave-4 crews add further trials; the true final N is higher,
so Bonferroni passes at N_floor are provisional and every near-bar row
carries its break-even N.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..rd.common import dump_json
from ..rd2.stats2 import deflated_sharpe

RD001_RD002_GLOBAL = 1557
RD003_STAGE1 = 152
RD003_STAGE2B = 21


def rd003_stage2_trials(repo_root: Path) -> int:
    decl = json.loads((repo_root / "Stratex" / "rigorous_backtest"
                       / "results_rd3" / "stage2_declaration.json")
                      .read_text())
    cells = 0
    wf_groups = 0
    for fam in decl["families"]:
        cells += len(fam["variants"]) * len(fam["cells"])
        for _cell in fam["cells"]:
            if len(fam["variants"]) >= 2:
                wf_groups += 1
    return cells + wf_groups


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results_rd8")
    ap.add_argument("--repo-root", default="..")
    args = ap.parse_args()
    rdir = Path(args.results_dir)
    rows = []
    for p in sorted((rdir / "rows").glob("*.json")):
        rows.append(json.loads(p.read_text()))
    wf = json.loads((rdir / "wf_select.json").read_text()) \
        if (rdir / "wf_select.json").exists() else {}

    s2 = rd003_stage2_trials(Path(args.repo_root))
    rd008_trials = len(rows) + len(wf)
    n_floor = RD001_RD002_GLOBAL + RD003_STAGE1 + s2 + RD003_STAGE2B \
        + rd008_trials
    alpha = 0.05 / n_floor

    # cross-trial Sharpe dispersion across this track's rows (DSR input,
    # disclosed; DSR does not gate — RD-002 synthesis rule)
    srs = [r["trade_stats"]["sharpe_per_trade"] for r in rows
           if r["trade_stats"].get("sharpe_per_trade") is not None
           and (r["trade_stats"].get("n") or 0) > 0]
    import statistics
    sr_std_xtrial = statistics.pstdev(srs) if len(srs) > 1 else 0.0

    out_rows = []
    for r in rows:
        po = r["report"]["pooled_oos"]
        ts = r["trade_stats"]
        p = ts.get("p_one_sided")
        bonf = bool(p is not None and p < alpha)
        breakeven_n = int(0.05 / p) if p and p > 0 else None
        sens = r.get("sensitivity_2x") or {}
        cost2x = bool((sens.get("expectancy_net") or -1) > 0
                      and (sens.get("profit_factor_net") or 0) >= 1.2)
        bar_pass = bool(r["bar"]["passes_bar"])
        dsr = deflated_sharpe(ts.get("sharpe_per_trade") or 0.0,
                              ts.get("n") or 0, ts.get("skew") or 0.0,
                              ts.get("kurtosis") or 3.0, n_floor,
                              sr_std_xtrial) if ts.get("n") else 0.0
        failed = [k for k, v in r["bar"]["checks"].items() if not v]
        if not bonf:
            failed.append("bonferroni_at_N_floor")
        if not cost2x:
            failed.append("cost_2x")
        if r["timeframe"] == "15m":
            verdict = "WATCHLIST-SCREEN" if bar_pass else "FAIL"
        elif bar_pass and bonf and cost2x:
            verdict = "CANDIDATE (provisional at N_floor)"
        elif bar_pass:
            verdict = "WATCHLIST"
        else:
            verdict = "FAIL"
        out_rows.append({
            "family": r["family"], "variant": r["variant"],
            "panel": r["panel"], "timeframe": r["timeframe"],
            "status": r["status"], "verdict": verdict,
            "trades": po.get("trades"),
            "expectancy_net": po.get("expectancy_net"),
            "profit_factor_net": po.get("profit_factor_net"),
            "win_rate": po.get("win_rate"),
            "max_drawdown_net": po.get("max_drawdown_net"),
            "per_symbol": {s: {"trades": m.get("trades"),
                               "expectancy_net": m.get("expectancy_net"),
                               "profit_factor_net":
                                   m.get("profit_factor_net")}
                           for s, m in
                           r["report"]["per_symbol_oos"].items()},
            "folds_positive": r["bar"]["bar"].get("positive_folds"),
            "folds_in_profile": len(r["report"]["fold_profile"]),
            "holdout_passes": r["holdout"].get("passes"),
            "p_one_sided": p, "bonferroni_pass_at_N_floor": bonf,
            "bonferroni_alpha": alpha, "breakeven_N": breakeven_n,
            "deflated_sharpe_xtrial": dsr,
            "sensitivity_2x": {
                "trades": sens.get("trades"),
                "expectancy_net": sens.get("expectancy_net"),
                "profit_factor_net": sens.get("profit_factor_net")},
            "cost_2x_pass": cost2x,
            "failed_checks": failed,
        })
    out_rows.sort(key=lambda x: (x["expectancy_net"] is not None,
                                 x["expectancy_net"] or -9), reverse=True)

    wf_rows = [{"key": k, "family": v["family"], "timeframe": v["timeframe"],
                "variants_tried": v["variants_tried"],
                "procedure_pooled_oos": v["wf_selection"]
                ["procedure_pooled_oos"]}
               for k, v in sorted(wf.items())]

    synthesis = {
        "task": "TASK-STR-RD-008",
        "panel": "idx2 (NDX = OANDA NAS100, SPX = OANDA US500)",
        "n_floor_components": {
            "through_rd002": RD001_RD002_GLOBAL,
            "rd003_stage1": RD003_STAGE1,
            "rd003_stage2_counted_from_declaration": s2,
            "rd003_stage2b": RD003_STAGE2B,
            "rd008_cells": len(rows),
            "rd008_wf_procedures": len(wf),
            "rd008_trials": rd008_trials},
        "n_floor": n_floor,
        "global_counter_floor_after_rd008": n_floor,
        "bonferroni_alpha_at_N_floor": alpha,
        "sr_std_xtrial_for_dsr": sr_std_xtrial,
        "candidates": [r for r in out_rows
                       if r["verdict"].startswith("CANDIDATE")],
        "watchlist": [r for r in out_rows
                      if r["verdict"].startswith("WATCHLIST")],
        "rows": out_rows,
        "wf_procedures": wf_rows,
    }
    dump_json(rdir / "synthesis.json", synthesis)

    def fmt(x, nd=4):
        return "—" if x is None else f"{x:.{nd}f}"

    print(f"N_floor = {n_floor} (alpha {alpha:.3e}); RD-008 trials = "
          f"{rd008_trials} ({len(rows)} cells + {len(wf)} wf procedures)")
    print("| family | variant | tf | trades | exp% | PF | folds+ | "
          "holdout | p | 2x PF | verdict |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in out_rows:
        print(f"| {r['family']} | {r['variant']} | {r['timeframe']} | "
              f"{r['trades']} | {fmt((r['expectancy_net'] or 0) * 100, 3)} | "
              f"{fmt(r['profit_factor_net'], 3)} | "
              f"{r['folds_positive']}/{r['folds_in_profile']} | "
              f"{r['holdout_passes']} | {fmt(r['p_one_sided'], 2)} | "
              f"{fmt(r['sensitivity_2x']['profit_factor_net'], 3)} | "
              f"{r['verdict']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
