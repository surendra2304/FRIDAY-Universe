"""RD-004 synthesis (checkpointed execution stage 4): judge all 32
cells + 2 wf-select procedures at the running global trial count,
exactly per the issue-#35 pre-declaration.

  python3 -m rigorous_backtest.rd4.synth4 --out-dir results_rd4 \
      --anchor-json /home/hatch/workspace/rd-004/anchor_result.json \
      --coverage /home/hatch/workspace/rd-004/coverage.json

Inputs are the assembled rows (rows/*.json from assemble.py) and the
procedure rows (rows/wf_<tf>.json from wf.py); both carry their
fold report, holdout, bar checks, pooled-OOS trade stats and 2x-cost
metrics, so judgement needs no trade reload.

Verdicts: PASS = mechanical bar (stats2.check_bar2, incl. holdout)
AND significance (Bonferroni p < 0.05/N AND deflated Sharpe >= 0.95,
gate sr_std estimator as in rd2/synth.py) AND 2x-cost PF >= 1.2 with
expectancy > 0. WATCHLIST = mechanical bar passed, significance or
2x-cost failed. FAIL = anything else.
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

import numpy as np

from ..rd2.stats2 import deflated_sharpe

N_RD001_RD002 = 1557
N_RD003_DECLARED = 207          # 152 + 34 + 21, RESULTS_RD3.md on main


def _judge(ts, bar, metrics_2x_pooled, n_global, sr_std, sr_naive,
           sr_naive200):
    sig = None
    if sr_std and ts.get("n", 0) >= 30:
        dsr = deflated_sharpe(ts["sharpe_per_trade"], ts["n"],
                              ts["skew"] or 0.0, ts["kurtosis"] or 3.0,
                              n_global, sr_std)
        bonf = (ts["p_one_sided"] or 1.0) < 0.05 / n_global
        sig = {"deflated_sharpe": dsr, "bonferroni_pass": bool(bonf),
               "bonferroni_alpha": 0.05 / n_global,
               "p_one_sided": ts["p_one_sided"],
               "dsr_naive_all": (deflated_sharpe(
                   ts["sharpe_per_trade"], ts["n"], ts["skew"] or 0.0,
                   ts["kurtosis"] or 3.0, n_global, sr_naive)
                   if sr_naive else None),
               "dsr_naive_200": (deflated_sharpe(
                   ts["sharpe_per_trade"], ts["n"], ts["skew"] or 0.0,
                   ts["kurtosis"] or 3.0, n_global, sr_naive200)
                   if sr_naive200 else None),
               "passes": bool(bonf and dsr >= 0.95)}
    m2 = metrics_2x_pooled or {}
    cost2x_pass = bool((m2.get("expectancy_net") or 0) > 0
                       and (m2.get("profit_factor_net") or 0) >= 1.2)
    bar_pass = bool(bar.get("passes_bar"))
    sig_pass = bool(sig and sig["passes"])
    if bar_pass and sig_pass and cost2x_pass:
        verdict = "PASS"
    elif bar_pass:
        verdict = "WATCHLIST"
    else:
        verdict = "FAIL"
    failed = []
    if not bar_pass:
        failed += [k for k, v in bar["checks"].items() if not v]
    if not sig_pass:
        failed.append("significance")
    if not cost2x_pass:
        failed.append("cost_2x")
    return {"trade_stats": ts, "significance": sig,
            "cost_2x_pass": cost2x_pass, "verdict": verdict,
            "failed_elements": failed}


def _dump_retry(path: Path, payload) -> None:
    tmp = path.with_name(path.name + ".tmp")
    for k in range(40):
        try:
            tmp.write_text(json.dumps(payload, indent=2, default=str),
                           encoding="utf-8")
            tmp.replace(path)
            return
        except PermissionError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(min(20.0, 2.0 * (k + 1)))
    raise PermissionError(f"write to {path} blocked after 40 retries")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--anchor-json", default="")
    ap.add_argument("--coverage", default="")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "rows"
    rows = []
    wf_files = {}
    for p in sorted(rows_dir.glob("*.json")):
        if p.name.startswith("wf_"):
            wf_files[p.stem] = json.loads(p.read_text())
        else:
            rows.append(json.loads(p.read_text()))
    assert len(rows) == 32, f"expected 32 cell rows, found {len(rows)}"
    assert len(wf_files) == 2, f"expected 2 wf rows, found {len(wf_files)}"

    n_trials_rd004 = 32 + 2
    n_global = N_RD001_RD002 + N_RD003_DECLARED + n_trials_rd004

    # sr dispersion estimators (rd2/synth.py gate convention), over the
    # 32 cell rows (procedures are selections over cells, not trials
    # in the dispersion pool — same treatment as rd2's grid_wf_select).
    srs, inv_n, srs_200 = [], [], []
    for r in rows:
        ts = r.get("trade_stats") or {}
        if ts.get("n", 0) >= 30 and ts.get("sharpe_per_trade") is not None:
            srs.append(ts["sharpe_per_trade"])
            inv_n.append(1.0 / ts["n"])
            if ts["n"] >= 200:
                srs_200.append(ts["sharpe_per_trade"])
    sr_std = float(np.sqrt(np.mean(inv_n))) if len(inv_n) >= 10 else None
    sr_naive = float(np.std(srs)) if len(srs) >= 10 else None
    sr_naive200 = float(np.std(srs_200)) if len(srs_200) >= 10 else None

    judged = []
    for r in rows:
        j = _judge(r["trade_stats"], r["bar"],
                   r["metrics_2x"]["pooled_oos"], n_global, sr_std,
                   sr_naive, sr_naive200)
        po = r["report"]["pooled_oos"]
        judged.append({
            "family": r["family"], "signal": r["signal"], "mode": r["mode"],
            "variant": r["variant"], "panel": r["panel"],
            "timeframe": r["timeframe"],
            "oos_trades": po.get("trades"),
            "expectancy_net": po.get("expectancy_net"),
            "profit_factor_net": po.get("profit_factor_net"),
            "total_return_net": po.get("total_return_net"),
            "max_drawdown_net": po.get("max_drawdown_net"),
            "win_rate": po.get("win_rate"),
            "positive_folds": r["bar"]["bar"]["positive_folds"],
            "folds_with_trades": r["bar"]["bar"]["folds_with_trades"],
            "holdout_passes": r["holdout"]["passes"],
            "breadth_positive_share":
                r["holdout"]["breadth_positive_share"],
            "max_symbol_profit_share":
                r["holdout"]["max_symbol_profit_share"],
            "untouched_expectancy": r["holdout"]["untouched_expectancy"],
            "untouched_trades": r["holdout"]["untouched_trades"],
            "passes_bar": r["bar"]["passes_bar"],
            "bar_checks": r["bar"]["checks"],
            "pf_2x": r["metrics_2x"]["pooled_oos"].get("profit_factor_net"),
            "expectancy_2x":
                r["metrics_2x"]["pooled_oos"].get("expectancy_net"),
            "trades_2x": r["metrics_2x"]["pooled_oos"].get("trades"),
            **j})
    judged.sort(key=lambda x: (x["expectancy_net"] is not None,
                               x["expectancy_net"] or -9), reverse=True)

    wf_rows = []
    for tf in ("15m", "2h"):
        r = wf_files[f"wf_{tf}"]
        j = _judge(r["trade_stats"], r["bar"],
                   r["metrics_2x"]["pooled_oos"], n_global, sr_std,
                   sr_naive, sr_naive200)
        rep = r["report"]
        wf_rows.append({
            "procedure": r["procedure"], "timeframe": tf,
            "picks": r["picks"],
            "variants_considered": r["variants_considered"],
            "oos_trades": rep["pooled_oos"].get("trades"),
            "expectancy_net": rep["pooled_oos"].get("expectancy_net"),
            "profit_factor_net":
                rep["pooled_oos"].get("profit_factor_net"),
            "holdout_passes": r["holdout"]["passes"],
            "passes_bar": r["bar"]["passes_bar"],
            "pf_2x": r["metrics_2x"]["pooled_oos"].get("profit_factor_net"),
            "expectancy_2x":
                r["metrics_2x"]["pooled_oos"].get("expectancy_net"),
            **j})

    synthesis = {
        "task": "TASK-STR-RD-004",
        "family": "vol_regime_trend (volatility-regime trend following)",
        "declaration": {
            "claim_comment":
                "https://github.com/surendra2304/FRIDAY-Universe/issues/35"
                "#issuecomment-6890957904",
            "declaration_comment":
                "https://github.com/surendra2304/FRIDAY-Universe/issues/35"
                "#issuecomment-6890972056"},
        "trial_accounting": {
            "rd001_rd002_final": N_RD001_RD002,
            "rd003_declared_on_main": N_RD003_DECLARED,
            "rd004_cells": 32, "rd004_wf_select_procedures": 2,
            "rd004_trials": n_trials_rd004,
            "n_global_judged": n_global,
            "note": "Sibling Wave-4 crews (RD-005..RD-013) add their own "
                    "trials concurrently; the coordinator reconciles the "
                    "final global N. A higher reconciled N only tightens "
                    "the Bonferroni/DSR gate."},
        "sr_std_gate": sr_std, "sr_std_naive": sr_naive,
        "sr_std_naive200": sr_naive200,
        "bonferroni_alpha": 0.05 / n_global,
        "passers": [r["variant"] + "@" + r["timeframe"] for r in judged
                    if r["verdict"] == "PASS"]
                   + [r["procedure"] for r in wf_rows
                      if r["verdict"] == "PASS"],
        "watchlist": [r["variant"] + "@" + r["timeframe"] for r in judged
                      if r["verdict"] == "WATCHLIST"]
                     + [r["procedure"] for r in wf_rows
                        if r["verdict"] == "WATCHLIST"],
        "configs": judged, "wf_select": wf_rows,
    }
    if args.anchor_json and Path(args.anchor_json).exists():
        synthesis["sanity_anchor"] = json.loads(
            Path(args.anchor_json).read_text())
    ec = out_dir / "engine_consistency.json"
    if ec.exists():
        synthesis["engine_consistency"] = json.loads(ec.read_text())
    if args.coverage and Path(args.coverage).exists():
        cov = json.loads(Path(args.coverage).read_text())
        synthesis["coverage"] = {
            s: {k: v.get(k) for k in ("status", "start_month", "rows",
                                      "csv_sha256", "first_bar_utc",
                                      "last_bar_utc")}
            for s, v in cov.items()}
    _dump_retry(out_dir / "synthesis.json", synthesis)
    print(f"N_global judged = {n_global}; sr_std_gate = {sr_std}")
    print(f"PASS: {synthesis['passers']}")
    print(f"WATCHLIST: {synthesis['watchlist']}")
    for r in judged:
        print(f"{r['timeframe']:>3} {r['variant']:<16} trades="
              f"{r['oos_trades']:>6} exp={r['expectancy_net']} "
              f"PF={r['profit_factor_net']} verdict={r['verdict']} "
              f"failed={r['failed_elements']}")
    for r in wf_rows:
        print(f"WF {r['procedure']}: trades={r['oos_trades']} "
              f"exp={r['expectancy_net']} PF={r['profit_factor_net']} "
              f"verdict={r['verdict']} failed={r['failed_elements']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
