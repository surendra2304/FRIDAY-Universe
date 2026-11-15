"""Stage-3 synthesis for TASK-STR-RD-003.

Mirrors rd2/synth.py's judgement construction exactly (same ranked-row
shape, same significance construction from trade_stats aggregates,
same dispersion estimators — computed over RD-003's own rows, as
RD-002 computed them over its own), with three RD-003 additions:

* trial accounting continues from RD-002's final global 1,557;
* 2x-cost sensitivity is computed EXACTLY from saved trades: in this
  harness costs enter only through net returns (exit decisions are
  price-level based — see rd/fastsim.py), so doubling costs maps
  net -> net - (gross - net) per trade, gross from side and prices;
* RD-002's two passers are re-checked against the new Bonferroni
  threshold (their aggregate significance evidence is on RD-002's
  record; the re-check states what it rests on).

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd3.synth3 \
      --work-dir /home/hatch/workspace/str-rd3/work/results_rd3 \
      --out-dir results_rd3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..rd.common import dump_json, trades_from_json, wf_select_judge
from ..rd2.panels import fold_profile
from ..rd2.stats2 import deflated_sharpe

PRIOR_GLOBAL = 1557  # RD-002 final global trial count


def _load_rows(d: Path, src: str) -> list[dict]:
    rows = []
    if not d.exists():
        return rows
    for p in sorted(d.glob("*.json")):
        r = json.loads(p.read_text())
        r["_src"] = src
        rows.append(r)
    return rows


def _oos_windows(panel: str, tf: str):
    from ..rd2.stats2 import FOLD_BOUNDS
    return [(pd.Timestamp(FOLD_BOUNDS[f][0], tz="UTC"),
             pd.Timestamp(FOLD_BOUNDS[f][1], tz="UTC"))
            for f in fold_profile(panel, tf)]


def _pf(returns: list[float]):
    gains = sum(r for r in returns if r > 0)
    losses = -sum(r for r in returns if r < 0)
    if losses <= 0:
        return float("inf") if gains > 0 else None
    return gains / losses


def cost2x_pf(row: dict):
    """Exact 2x-cost PF over the row's pooled OOS trades."""
    trades = row.get("trades")
    if not trades:
        return None
    wins = _oos_windows(row["panel"], row["timeframe"])
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

    rows = (_load_rows(work / "disc_rows", "stage1_disc_rows")
            + _load_rows(work / "gov_rows", "stage1_gov_rows")
            + _load_rows(work / "stage2_rows", "stage2_rows")
            + _load_rows(work / "stage2b_rows", "stage2b_rows"))

    # wf-select procedures: Stages 2/2B (from the runners) + the
    # governed adx_ema crypto30:1h procedure if both configs' trades
    # persisted.
    wf: dict[str, dict] = {}
    for sel_name in ("stage2_wf_select.json", "stage2b_wf_select.json"):
        s2sel = work / sel_name
        if s2sel.exists():
            for k, v in json.loads(s2sel.read_text()).items():
                wf[k] = v
    gov_1h = {r["variant"]: r for r in rows
              if r["_src"] == "stage1_gov_rows"
              and r["panel"] == "crypto30" and r["timeframe"] == "1h"}
    gov_note = None
    if len(gov_1h) == 2 and all("trades" in r for r in gov_1h.values()):
        vt = {v: trades_from_json(r["trades"])
              for v, r in gov_1h.items()}
        sel = wf_select_judge(vt)
        wf["governed__adx_ema__crypto30__1h"] = {
            "family": "governed", "panel": "crypto30",
            "timeframe": "1h", "variants_tried": 2,
            "wf_selection": sel}
    else:
        gov_note = ("adx_ema crypto30:1h wf-select procedure not "
                    "computable (both configs' trades must persist); "
                    "not counted as a trial")
    n_procedures = len(wf)
    n_trials_rd3 = len(rows) + n_procedures
    n_global = PRIOR_GLOBAL + n_trials_rd3

    # Dispersion estimators over RD-003 rows (mirror of rd2/synth.py).
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

    ranked = []
    raw_by_key = {}
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
            sig = {"deflated_sharpe": dsr,
                   "bonferroni_pass": bool(bonf),
                   "passes": bool(bonf),
                   "source": "aggregates",
                   "dsr_naive_all": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"],
                       ts.get("skew") or 0.0, ts.get("kurtosis") or 3.0,
                       n_global, sr_std_naive) if sr_std_naive else None,
                   "dsr_naive_200": deflated_sharpe(
                       ts["sharpe_per_trade"], ts["n"],
                       ts.get("skew") or 0.0, ts.get("kurtosis") or 3.0,
                       n_global, sr_std_naive200) if sr_std_naive200 else None}
            sig["dsr_contested"] = bool(
                sig["passes"] and ((sig["dsr_naive_all"] or 1) < 0.95
                                   or (sig["dsr_naive_200"] or 1) < 0.95))
        folds_pos = sum(1 for f in r["report"]["per_fold"].values()
                        if (f.get("expectancy_net") or -9) > 0
                        and (f.get("trades") or 0) > 0)
        key = (f"{r['family']}/{r['variant']}@{r['panel']}/{r['timeframe']}")
        raw_by_key[key] = r
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

    out = {
        "prior_global_trials": PRIOR_GLOBAL,
        "rd003_rows": len(rows),
        "rd003_wf_select_procedures": n_procedures,
        "rd003_trials": n_trials_rd3,
        "global_trials": n_global,
        "gov_wf_select_note": gov_note,
        "sr_std_across_trials": sr_std,
        "sr_std_gate_null_dispersion": sr_std,
        "sr_std_naive_all": sr_std_naive,
        "sr_std_naive_200": sr_std_naive200,
        "significance_method": (
            "GATE: Bonferroni one-sided p < 0.05/N_global (family-wise "
            "error control valid under arbitrary dependence between "
            "trials; no estimated inputs). Deflated Sharpe ratios are "
            "REPORTED for every near-bar row under three dispersion "
            "estimators but do not veto — RD-002's stated method, "
            "unchanged. 2x-cost sensitivity is computed exactly from "
            "saved trades (costs enter this harness only through net "
            "returns; exits are price-level based)."),
        "bonferroni_threshold_at_final_n": 0.05 / n_global,
        "ranked_table": ranked,
        "candidates_pre_sensitivity": candidates,
        "passers_final": passers,
        "near_bar_for_2x_cost_sensitivity": near_bar,
        "watchlist": watchlist,
        "wf_select": {k: v["wf_selection"] for k, v in wf.items()},
    }
    dump_json(out_dir / "synthesis.json", out)
    print(f"[synth3] rows={len(rows)} procedures={n_procedures} "
          f"rd3_trials={n_trials_rd3} global={n_global}")
    print(f"[synth3] candidates={len(candidates)} passers={len(passers)} "
          f"near_bar={len(near_bar)}")
    for x in ranked[:10]:
        print(f"  top: {x['family']}/{x['variant']} @{x['panel']}/"
              f"{x['timeframe']} exp={x['expectancy_net']} "
              f"pf={x['profit_factor_net']} trades={x['oos_trades']} "
              f"bar={x['passes_bar']} sig={x['sig_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
