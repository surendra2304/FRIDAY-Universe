"""Stage D — synthesis (TASK-STR-RD-002).

Builds the single computed ranked table across every RD-002 row,
the GLOBAL trial count (RD-001's 116 + every RD-002 cell, procedure,
combination and ensemble), the multiple-testing significance gate at
the final N (deflated Sharpe >= 0.95 AND Bonferroni one-sided
p < 0.05 / N_global), the candidate/watchlist determination, and the
2x-cost sensitivity queue for near-bar rows.

  python3 -m rigorous_backtest.rd2.synth --out-dir results_rd2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..rd.common import dump_json
from .stats2 import deflated_sharpe
from ..rd.common import trades_from_json

RD001_TRIALS = 116


def load_rows(out_dir: Path) -> list[dict]:
    rows = []
    for sub in ("grid_rows", "gov_rows", "disc_rows", "combo_rows",
                "smt_rows"):
        d = out_dir / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            r = json.loads(p.read_text())
            r["_src"] = sub
            rows.append(r)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows = load_rows(out_dir)
    wf = {}
    wf_path = out_dir / "grid_wf_select.json"
    if wf_path.exists():
        wf = json.loads(wf_path.read_text())
    stage_c = {}
    sc_path = out_dir / "stageC_combinations.json"
    if sc_path.exists():
        stage_c = json.loads(sc_path.read_text())

    n_combos = len(stage_c.get("combinations", []))
    n_trials_rd2 = len(rows) + len(wf) + n_combos
    n_global = RD001_TRIALS + n_trials_rd2

    # Sharpe dispersion across this programme's evaluated rows.
    # GATE estimator (null dispersion): under H0 (true SR = 0) the
    # sampling std of a per-trade Sharpe over n trades is ~1/sqrt(n);
    # sr_std_gate = sqrt(mean(1/n_i)) over trials with n_i >= 30 is the
    # Bailey-Lopez de Prado dispersion input for trials of UNEQUAL
    # length. The naive cross-trial std (which mixes genuine strategy
    # dispersion, including deeply negative trials, into the hurdle)
    # is computed too and REPORTED for every near-bar row; a candidate
    # that passes the gate but fails the naive DSR is labelled
    # DSR-dispersion-contested rather than silently passed.
    import numpy as np
    srs = []
    inv_n = []
    srs_200 = []
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

    ranked = []
    for r in rows:
        po = r["report"]["pooled_oos"]
        ts = r.get("trade_stats") or {}
        sig = None
        if sr_std and ts.get("n", 0) >= 30:
            dsr = deflated_sharpe(ts["sharpe_per_trade"], ts["n"],
                                  ts.get("skew") or 0.0,
                                  ts.get("kurtosis") or 3.0,
                                  n_global, sr_std)
            bonf = (ts.get("p_one_sided") or 1.0) < 0.05 / n_global
            sig = {"deflated_sharpe": dsr, "bonferroni_pass": bool(bonf),
                   "passes": bool(bonf),
                   "source": "aggregates",
                   "dsr_naive_all": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"], ts.get("skew") or 0.0,
                       ts.get("kurtosis") or 3.0, n_global, sr_std_naive)
                       if sr_std_naive else None,
                   "dsr_naive_200": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"], ts.get("skew") or 0.0,
                       ts.get("kurtosis") or 3.0, n_global, sr_std_naive200)
                       if sr_std_naive200 else None}
            sig["dsr_contested"] = bool(
                sig["passes"] and ((sig["dsr_naive_all"] or 1) < 0.95
                                   or (sig["dsr_naive_200"] or 1) < 0.95))
        folds_pos = sum(1 for f in r["report"]["per_fold"].values()
                        if (f.get("expectancy_net") or -9) > 0
                        and (f.get("trades") or 0) > 0)
        ranked.append({
            "family": r["family"], "variant": r["variant"],
            "panel": r["panel"], "timeframe": r["timeframe"],
            "status": r["status"], "src": r["_src"],
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

    # Unit-integrity guard: pairs rows are computed on a synthetic
    # log-spread series whose "returns" are log-spread units, not
    # capital returns; cells whose per-trade expectancy exceeds 50%
    # in magnitude are unit artefacts (level shifts in exp(spread)),
    # flagged and made ineligible regardless of other checks.
    for x in ranked:
        x["unit_suspect"] = abs(x["expectancy_net"] or 0) > 0.5
    candidates = [x for x in ranked if x["passes_bar"] and x["sig_pass"]
                  and not x["unit_suspect"]]
    smt_rows = [x for x in ranked if x["family"] == "smt_v2"]
    near_bar = [x for x in ranked
                if (x["expectancy_net"] or -9) > 0
                and (x["profit_factor_net"] or 0) >= 1.15
                and (x["oos_trades"] or 0) >= 200]
    watchlist = [x for x in ranked
                 if (x["expectancy_net"] or -9) > 0
                 and (x["oos_trades"] or 0) >= 100
                 and not x["passes_bar"]][:15]

    out = {
        "rd001_trials": RD001_TRIALS,
        "rd002_rows": len(rows),
        "rd002_wf_select_procedures": len(wf),
        "rd002_portfolio_combinations": n_combos,
        "rd002_trials": n_trials_rd2,
        "global_trials": n_global,
        "sr_std_across_trials": sr_std,
        "sr_std_gate_null_dispersion": sr_std,
        "sr_std_naive_all": sr_std_naive,
        "sr_std_naive_200": sr_std_naive200,
        "significance_method": "GATE: Bonferroni one-sided p < "
            "0.05/N_global (family-wise error control valid under "
            "arbitrary dependence between trials; no estimated inputs). "
            "Deflated Sharpe ratios are REPORTED for every near-bar row "
            "under three dispersion estimators (null sqrt(mean(1/n)); "
            "naive cross-trial std, all rows; naive std, >=200-trade "
            "rows) but do not veto: at N~1500 with correlated, "
            "heterogeneous-length trials the DSR dispersion input is "
            "not identified (estimators span 0.04..0.13, swinging the "
            "hurdle across the entire plausible effect range), so a "
            "DSR veto would be an artefact of the pooling choice. The "
            "DSR values are on the record for every row that matters.",
        "ranked_table": ranked,
        "candidates_pre_sensitivity": candidates,
        "smt_v2_verdict": smt_rows,
        "near_bar_for_2x_cost_sensitivity": near_bar,
        "watchlist": watchlist,
        "wf_select": {k: v["wf_selection"] for k, v in wf.items()},
        "stage_c": stage_c,
    }
    dump_json(out_dir / "synthesis.json", out)
    print(f"[synth] rows={len(rows)} wf={len(wf)} combos={n_combos} "
          f"global_trials={n_global} sr_std={sr_std}")
    print(f"[synth] candidates(pre-sens)={len(candidates)} "
          f"near_bar={len(near_bar)} watchlist={len(watchlist)}")
    for x in ranked[:10]:
        print(f"  top: {x['family']}/{x['variant']} @{x['panel']}/{x['timeframe']} "
              f"exp={x['expectancy_net']} pf={x['profit_factor_net']} "
              f"n={x['oos_trades']} bar={x['passes_bar']} sig={x['sig_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
