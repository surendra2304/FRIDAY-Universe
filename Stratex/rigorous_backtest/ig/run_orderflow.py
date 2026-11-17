"""THE DECLARED RUN — TASK-STR-RD-021 (true order flow from aggTrades).

DO NOT EXECUTE THIS SCRIPT until every gate in ../RUNBOOK.md passes.
Executing it IS the backtest: the declaration allows exactly ONE run
of these 4 frozen cells. This file was written and verified on
synthetic panels during run-prep only; it has never been executed
against the real panel.

What it does, in order:
1. Refuses to run if RESULTS.md already exists in --out (one run).
2. Re-verifies the declaration hash in the given main checkout and
   the pinned harness hash (orderflow.py, same directory); aborts
   on any mismatch.
3. Loads the staged flow panel (stage_flow_panel.py output),
   re-verifying every staged CSV's SHA-256 against the panel
   provenance; symbols the staging marked EXCLUDED are skipped;
   fewer than 8 surviving symbols -> UNTESTABLE, no simulation.
4. Runs the 4 frozen cells ({flow_thrust, flow_absorption} x
   {15m, 1h}) at programme costs (16 bps RT) and the 2x shadow
   (32 bps RT) — both cost levels are produced by the harness in
   one pass (ret_net / ret_net_2x per trade).
5. Judges each cell with the programme's own functions
   (walkforward.oos_report + rd.common.check_bar + holdout_check
   over a per-symbol report spanning the surviving universe), plus
   the Bonferroni one-sided t-test against the trial floor stated
   on the command line (read from the programme trial ledger at
   run time — there is deliberately no default).
6. Writes results.json + RESULTS.md to --out.

Verdict rules (per cell, declaration + programme practice):
- pooled OOS trades < 200 at programme costs -> "insufficient OOS trades"
- every bar component (expectancy > 0, PF >= 1.2, >= 200 trades,
  >= 4/5 positive folds, holdout, Bonferroni) at BOTH cost levels
  -> PASS (forward-test CANDIDATE only, Phase-3 protocol)
- anything else -> FAIL (the cell closes, per the declaration;
  strict OOS PF < 1.2 -> deleted under the owner rule)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

DECLARATION_SHA256 = "806db8683cf5f9f56dbae0bbf828e0e9a7cc9d7732479eeaf9c6b2670d74764c"
HARNESS_SHA256 = "6f304a99bab465c294702cac4cc27950dd6edbcd501cb614cd46beb7eb7891ec"
UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "TRXUSDT", "LTCUSDT", "LINKUSDT"]
TIMEFRAMES = ("15m", "1h")
MECHANISMS = ("flow_thrust", "flow_absorption")
MIN_SURVIVORS = 8

_REASON_MAP = {"TARGET": "TP", "TARGET_GAP": "TP", "STOP": "SL",
               "STOP_GAP": "SL", "TIME": "TIME",
               "END_OF_DATA": "END_OF_DATA"}


def load_bars(csv_path: Path) -> list[dict]:
    bars = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bars.append({
                "t": int(row["t"]), "o": float(row["o"]),
                "h": float(row["h"]), "l": float(row["l"]),
                "c": float(row["c"]),
                "delta": float(row["delta"]), "qty": float(row["qty"]),
                "nprints": int(row["nprints"]),
            })
    return bars


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="fresh checkout of origin/main containing the "
                         "MERGED declaration (hash is re-verified)")
    ap.add_argument("--panel-dir", required=True,
                    help="staged flow panel (stage_flow_panel.py output)")
    ap.add_argument("--out", required=True, help="results output dir")
    ap.add_argument("--trial-floor", required=True, type=int,
                    help="programme trial counter at run time, read from "
                         "the trial ledger; stated in the results")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "RESULTS.md").exists():
        print("REFUSING: RESULTS.md already exists in --out. "
              "The declaration allows exactly one run.", file=sys.stderr)
        return 2

    repo = Path(args.repo)
    decl = repo / "Stratex/rigorous_backtest/ig/orderflow_declaration.json"
    digest = hashlib.sha256(decl.read_bytes()).hexdigest()
    if digest != DECLARATION_SHA256:
        print(f"ABORT: declaration hash {digest} != {DECLARATION_SHA256}",
              file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent
    harness_digest = hashlib.sha256((here / "orderflow.py").read_bytes()).hexdigest()
    if harness_digest != HARNESS_SHA256:
        print(f"ABORT: harness hash {harness_digest} != {HARNESS_SHA256}",
              file=sys.stderr)
        return 2

    panel_dir = Path(args.panel_dir)
    prov = json.loads((panel_dir / "panel_provenance.json").read_text(encoding="utf-8"))
    survivors = []
    for sym in UNIVERSE:
        st = prov.get("symbols", {}).get(sym, {}).get("status")
        if st == "OK":
            survivors.append(sym)
        else:
            print(f"[panel] {sym}: {st} (excluded at staging)", flush=True)
    if len(survivors) < MIN_SURVIVORS:
        print(f"UNTESTABLE: only {len(survivors)} of {len(UNIVERSE)} "
              f"symbols survived staging (declaration requires "
              f">= {MIN_SURVIVORS}). No simulation performed.",
              file=sys.stderr)
        return 3

    sys.path.insert(0, str(repo / "Stratex"))
    sys.path.insert(0, str(here))
    import orderflow  # the pinned harness (this directory)
    import numpy as np
    import pandas as pd
    from rigorous_backtest.walkforward import FOLDS, oos_report, trades_in_window
    from rigorous_backtest.rd.common import check_bar, holdout_check
    from rigorous_backtest.simulator import Trade as SimTrade
    from scipy import stats as scipy_stats

    def to_sim(trades, sym, field):
        return [SimTrade(sym,
                         pd.Timestamp(t["entry_time"], unit="ms", tz="UTC"),
                         pd.Timestamp(t["exit_time"], unit="ms", tz="UTC"),
                         "LONG" if t["side"] > 0 else "SHORT",
                         t["entry_price"], t["exit_price"], t[field],
                         _REASON_MAP.get(t["exit_reason"], t["exit_reason"]))
                for t in trades]

    cells = {}
    for tf in TIMEFRAMES:
        # load + verify this timeframe's staged bars once
        bars_by_sym = {}
        for sym in survivors:
            rec = prov["symbols"][sym]["timeframes"][tf]
            csv_path = panel_dir / f"{sym}_{tf}.csv"
            got = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            if got != rec["csv_sha256"]:
                print(f"ABORT: staged csv_sha256 mismatch for {sym} {tf}: "
                      f"{got} != {rec['csv_sha256']}", file=sys.stderr)
                return 2
            bars_by_sym[sym] = load_bars(csv_path)
        for mech in MECHANISMS:
            trades_by_cost = {"costs_16bps": [], "costs_32bps_shadow": []}
            per_symbol_trades = {"costs_16bps": {}, "costs_32bps_shadow": {}}
            for sym in survivors:
                raw = orderflow.simulate(bars_by_sym[sym], tf, mech)
                for label, field in (("costs_16bps", "ret_net"),
                                     ("costs_32bps_shadow", "ret_net_2x")):
                    st = to_sim(raw, sym, field)
                    trades_by_cost[label].extend(st)
                    per_symbol_trades[label][sym] = st
                print(f"[done] {tf} {mech} {sym}: {len(raw)} trades",
                      flush=True)

            def judge(label: str) -> dict:
                trades = trades_by_cost[label]
                rep = oos_report(trades)
                per_symbol = {sym: oos_report(ts)["pooled_oos"]
                              for sym, ts in per_symbol_trades[label].items()}
                full = {**rep, "per_symbol_oos": per_symbol}
                bar = check_bar(full)
                holdout = holdout_check(full)
                oos_trades = []
                for _, s, e in FOLDS:
                    oos_trades.extend(trades_in_window(trades, s, e))
                arr = np.array([t.net_return for t in oos_trades], dtype=float)
                n = len(arr)
                if n >= 2 and arr.std(ddof=1) > 0:
                    t_stat = float(arr.mean() / (arr.std(ddof=1) / np.sqrt(n)))
                    p_val = float(1.0 - scipy_stats.t.cdf(t_stat, n - 1))
                else:
                    t_stat, p_val = None, None
                alpha = 0.05 / args.trial_floor
                bonf = {"n": n, "t_stat": t_stat, "p_value": p_val,
                        "alpha": alpha, "trial_floor": args.trial_floor,
                        "passes": (p_val is not None and p_val < alpha)}
                checks = {**bar["checks"], "holdout": bool(holdout["passes"]),
                          "bonferroni": bool(bonf["passes"])}
                return {"pooled_oos": rep["pooled_oos"],
                        "per_fold": rep["per_fold"],
                        "per_symbol_oos": per_symbol, "bar": bar,
                        "holdout": holdout, "bonferroni": bonf,
                        "checks": checks, "passes_all": all(checks.values())}

            judged = {label: judge(label) for label in trades_by_cost}
            n_oos = judged["costs_16bps"]["pooled_oos"].get("trades") or 0
            if n_oos < 200:
                verdict = "insufficient OOS trades"
            elif all(j["passes_all"] for j in judged.values()):
                verdict = ("PASS — promotion candidate (forward-test "
                           "candidate only, under the Phase-3 forward "
                           "protocol)")
            else:
                verdict = "FAIL — the cell closes, per the declaration"
            cells[f"{mech}@{tf}"] = {"judged": judged, "verdict": verdict}
            print(f"[cell] {mech}@{tf}: {verdict} (OOS trades {n_oos})",
                  flush=True)

    payload = {
        "task": "TASK-STR-RD-021",
        "family": "order_flow_aggtrades",
        "declaration_sha256": digest,
        "harness_sha256": harness_digest,
        "panel": {"source": prov.get("source"),
                  "span": prov.get("span"),
                  "universe_survivors": survivors,
                  "per_symbol": prov.get("symbols")},
        "trial_floor_stated": args.trial_floor,
        "cells": cells,
    }
    (out / "results.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = ["# RESULTS — TASK-STR-RD-021 declared run (order_flow_aggtrades)",
             "",
             f"Declaration SHA-256 re-verified: {digest}",
             f"Harness SHA-256 re-verified: {harness_digest}",
             f"Trial floor stated: N = {args.trial_floor} "
             f"(Bonferroni alpha = 0.05/N)",
             f"Universe survivors: {len(survivors)}/10 "
             f"({', '.join(survivors)})",
             ""]
    for name, cell in cells.items():
        j = cell["judged"]["costs_16bps"]
        po = j["pooled_oos"]
        lines += [f"## {name} — {cell['verdict']}", "",
                  f"OOS trades: {po.get('trades')} · expectancy_net: "
                  f"{po.get('expectancy_net')} · PF: "
                  f"{po.get('profit_factor_net')} · checks: {j['checks']}",
                  ""]
    (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE {out}/results.json + RESULTS.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
