"""Synthesis for TASK-STR-RD-014: verdicts vs the declared bar.

Reads the runner's rows.jsonl, computes cross-trial statistics
(sr_std_xtrial as population stdev of per-row per-episode Sharpe,
following rd8.synth8), DSR per row, Bonferroni at the DECLARED global
counter N = 1,913 (floor 1,817 at declaration + this family's 96
trials), and — disclosed alongside, never silently substituted — at
the latest crew-computed floor reference (1,891 after TASK-STR-RD-007,
+ 96 = 1,987). Break-even N is reported per row.

Verdicts: CANDIDATE = check_bar2 passes AND Bonferroni at the declared
N passes AND the 2x-cost gate (expectancy > 0, PF >= 1.2) passes.
WATCHLIST = check_bar2 passes but significance or 2x-cost fails.
FAIL otherwise.

Usage:
  python3 -m rigorous_backtest.rd14.synth14 rows.jsonl anchor.json
Prints the synthesis JSON on stdout.
"""
from __future__ import annotations

import json
import statistics
import sys

from ..rd2.stats2 import deflated_sharpe

FLOOR_AT_DECLARATION = 1817
RD014_TRIALS = 96
N_DECLARED = FLOOR_AT_DECLARATION + RD014_TRIALS        # 1913 (the gate)
N_CURRENT_REF = 1891 + RD014_TRIALS                     # 1987 (disclosed)


def main() -> int:
    rows_path, anchor_path = sys.argv[1], sys.argv[2]
    meta, coverage, benchmarks, raw_rows = {}, [], {}, []
    for line in open(rows_path):
        rec = json.loads(line)
        if rec["type"] == "meta":
            meta = rec
        elif rec["type"] == "coverage":
            coverage.append(rec)
        elif rec["type"] == "benchmark":
            benchmarks[rec["tf"]] = rec
        elif rec["type"] == "row":
            raw_rows.append(rec)
    anchor = json.load(open(anchor_path))

    srs = [r["trade_stats"]["sharpe_per_trade"] for r in raw_rows
           if r["trade_stats"].get("n")]
    sr_std = statistics.pstdev(srs) if len(srs) > 1 else 0.0
    alpha_decl = 0.05 / N_DECLARED
    alpha_curr = 0.05 / N_CURRENT_REF

    rows, candidates, watchlist = [], [], []
    for r in raw_rows:
        ts = r["trade_stats"]
        p = ts.get("p_one_sided")
        breakeven_n = int(0.05 / p) if p and p > 0 else None
        dsr = (deflated_sharpe(ts.get("sharpe_per_trade") or 0.0,
                               ts.get("n") or 0, ts.get("skew") or 0.0,
                               ts.get("kurtosis") or 3.0, N_DECLARED,
                               sr_std) if ts.get("n") else 0.0)
        bonf_decl = bool(p is not None and p < alpha_decl)
        bonf_curr = bool(p is not None and p < alpha_curr)
        po2 = r["cost2x_pooled_oos"]
        cost2x_pass = bool((po2.get("expectancy_net") or 0) > 0
                           and (po2.get("profit_factor_net") or 0) >= 1.2)
        failed = [k for k, v in r["bar"]["checks"].items() if not v]
        if not bonf_decl:
            failed.append("bonferroni_at_declared_N")
        if not cost2x_pass:
            failed.append("cost2x")
        bar_pass = bool(r["bar"]["passes_bar"])
        if bar_pass and bonf_decl and cost2x_pass:
            verdict = "CANDIDATE"
        elif bar_pass:
            verdict = "WATCHLIST"
        else:
            verdict = "FAIL"
        po = r["pooled_oos"]
        row = {
            "family": r["family"], "variant": r["variant"],
            "signal": r["signal"], "vol_target": r["vol_target"],
            "brake": r["brake"], "panel": r["panel"],
            "timeframe": r["tf"], "status": r["status"],
            "verdict": verdict,
            "trades": po.get("trades"),
            "expectancy_net": po.get("expectancy_net"),
            "profit_factor_net": po.get("profit_factor_net"),
            "win_rate": po.get("win_rate"),
            "max_drawdown_net": po.get("max_drawdown_net"),
            "total_return_net": po.get("total_return_net"),
            "per_fold": r["per_fold"],
            "per_symbol_oos": r["per_symbol_oos"],
            "fold_profile": r["fold_profile"],
            "holdout_passes": r["holdout"].get("passes"),
            "holdout": r["holdout"],
            "bar_checks": r["bar"]["checks"],
            "p_one_sided": p,
            "bonferroni_alpha_at_declared_N": alpha_decl,
            "bonferroni_pass_at_declared_N": bonf_decl,
            "bonferroni_pass_at_current_floor_ref": bonf_curr,
            "breakeven_N": breakeven_n,
            "deflated_sharpe_xtrial": dsr,
            "sensitivity_2x": {
                "trades": po2.get("trades"),
                "expectancy_net": po2.get("expectancy_net"),
                "profit_factor_net": po2.get("profit_factor_net"),
                "pass": cost2x_pass},
            "failed_checks": failed,
        }
        rows.append(row)
        if verdict == "CANDIDATE":
            candidates.append(r["variant"] + "@" + r["tf"])
        elif verdict == "WATCHLIST":
            watchlist.append(r["variant"] + "@" + r["tf"])

    synth = {
        "task": "TASK-STR-RD-014",
        "family": "vol_targeted_trend_dd_brake",
        "panel": "crypto30",
        "n_floor_components": {
            "floor_at_declaration": FLOOR_AT_DECLARATION,
            "rd014_trials": RD014_TRIALS,
            "declared_N": N_DECLARED,
            "current_floor_reference": N_CURRENT_REF,
            "current_floor_note": "1,891 was the crew-computed global "
                                  "floor after TASK-STR-RD-007; the "
                                  "declared gate stays at 1,913 and "
                                  "both verdicts are reported."},
        "bonferroni_alpha_at_declared_N": alpha_decl,
        "bonferroni_alpha_at_current_floor_ref": alpha_curr,
        "sr_std_xtrial_for_dsr": sr_std,
        "candidates": candidates,
        "watchlist": watchlist,
        "benchmarks": benchmarks,
        "coverage": coverage,
        "sanity_anchor": anchor,
        "rows": rows,
    }
    print(json.dumps(synth, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
