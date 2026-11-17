"""THE DECLARED RUN — TASK-STR-RD-023 (grid / passive MM, fill haircut).

DO NOT EXECUTE THIS SCRIPT until every gate in ../RUNBOOK.md passes.
Executing it IS the backtest: the declaration allows exactly ONE run
of this frozen cell. This file was written and compile-checked during
declaration prep only; it has never been executed against the panel.

What it does, in order:
1. Re-verifies the declaration hash in the given main checkout
   (aborts on any mismatch).
2. Loads the panel through the programme's verified loader
   (data_feed.load_dataset, 15m, 2023-10..2026-10; cache reads are
   hash-re-verified by the loader itself) for the declaration's
   three symbols, checking rows == 108,192, zero missing bars, and
   — when --expected-provenance is given — csv_sha256 equality with
   the Box Theory provenance record.
3. Runs the pinned harness (grid_mm.py, same directory) at the
   programme cost stack (13 bps/fill, 26 bps effective round trip)
   and at the 2x shadow (21 bps/fill, 42 bps effective round trip).
   The fills are identical under both stacks; only net returns
   differ.
4. Judges pooled walk-forward OOS round trips with the programme's
   own functions (rd.common.check_bar + holdout_check over the
   report built by rigorous_backtest.walkforward.oos_report), plus
   the Bonferroni one-sided t-test against the trial floor stated
   on the command line (read from the rd-reconcile ledger at run
   time — there is deliberately no default).
5. Writes results.json + RESULTS.md to --out and refuses to run if
   RESULTS.md already exists there (one declared run; no re-runs).

Verdict rules (declaration + programme practice):
- pooled OOS round trips < 200 at programme costs
  -> "insufficient OOS trades"
- every bar component (expectancy > 0, PF >= 1.2, >= 200 trades,
  >= 4/5 positive folds, holdout, Bonferroni) at BOTH cost stacks
  -> PASS (forward-test CANDIDATE only, Phase-3 protocol)
- anything else -> FAIL (the family closes, per the declaration;
  strict OOS PF < 1.2 deletes the family per the owner's rule)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DECLARATION_SHA256 = "2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c"
EXPECTED_ROWS = 108192
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def bars_from_df(df):
    idx = df.index
    return [{"time": idx[i], "open": float(o), "high": float(h),
             "low": float(l), "close": float(c)}
            for i, (o, h, l, c) in enumerate(
                zip(df["open"], df["high"], df["low"], df["close"]))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="fresh checkout of origin/main containing the "
                         "MERGED declaration (hash is re-verified)")
    ap.add_argument("--panel-dir",
                    default=str(Path.home() / "workspace/str-grid/panel"),
                    help="staged panel cache dir (loader re-verifies)")
    ap.add_argument("--out", required=True, help="results output dir")
    ap.add_argument("--trial-floor", required=True, type=int,
                    help="programme trial counter at run time, read from "
                         "the rd-reconcile ledger; stated in the results")
    ap.add_argument("--expected-provenance", default=None,
                    help="Box-format provenance JSON (e.g. the "
                         "declaration-prep panel_provenance.json); when "
                         "given, every symbol's csv_sha256 must match "
                         "it or the run aborts before any simulation")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "RESULTS.md").exists():
        print("REFUSING: RESULTS.md already exists in --out. "
              "The declaration allows exactly one run.", file=sys.stderr)
        return 2

    repo = Path(args.repo)
    decl = (repo / "Stratex/rigorous_backtest/disc"
            / "grid_mm_declaration.json")
    digest = hashlib.sha256(decl.read_bytes()).hexdigest()
    if digest != DECLARATION_SHA256:
        print(f"ABORT: declaration hash {digest} != {DECLARATION_SHA256}",
              file=sys.stderr)
        return 2

    sys.path.insert(0, str(repo / "Stratex"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import grid_mm  # the pinned harness (this directory)
    if grid_mm.DECLARATION_SHA256 != DECLARATION_SHA256:
        print("ABORT: harness DECLARATION_SHA256 != runner's pinned "
              "value", file=sys.stderr)
        return 2
    if list(grid_mm.SYMBOLS) != SYMBOLS:
        print("ABORT: harness SYMBOLS != declaration universe",
              file=sys.stderr)
        return 2
    from rigorous_backtest.data_feed import load_dataset
    from rigorous_backtest.walkforward import oos_report
    from rigorous_backtest.rd.common import check_bar, holdout_check
    from rigorous_backtest.simulator import Trade as SimTrade
    from scipy import stats as scipy_stats

    panel_dir = Path(args.panel_dir)
    expected_prov = None
    if args.expected_provenance:
        expected_prov = json.loads(
            Path(args.expected_provenance).read_text(encoding="utf-8"))
    provenance = {}
    trades_by_cost = {"programme": [], "shadow_2x": []}
    per_symbol_trades = {"programme": {}, "shadow_2x": {}}
    totals = {"programme": {}, "shadow_2x": {}}
    for sym in SYMBOLS:
        ds = load_dataset(sym, "15m", "2023-10", "2026-10",
                          cache_dir=panel_dir)
        m = ds.manifest
        ga = m["gap_audit"]
        if m["rows"] != EXPECTED_ROWS or ga["missing_bars"] != 0:
            print(f"ABORT: panel deviation for {sym}: rows={m['rows']} "
                  f"missing={ga['missing_bars']}", file=sys.stderr)
            return 2
        if expected_prov is not None:
            exp_hash = expected_prov.get("symbols", {}).get(sym, {}) \
                .get("csv_sha256")
            if exp_hash != m["csv_sha256"]:
                print(f"ABORT: csv_sha256 mismatch for {sym}: "
                      f"{m['csv_sha256']} != expected {exp_hash}",
                      file=sys.stderr)
                return 2
        provenance[sym] = {"rows": m["rows"],
                           "csv_sha256": m["csv_sha256"],
                           "missing_bars": ga["missing_bars"],
                           "first_bar_utc": m["first_bar_utc"],
                           "last_bar_utc": m["last_bar_utc"]}
        bars = bars_from_df(ds.df)
        for label, costs in (("programme", grid_mm.GRID_COSTS),
                             ("shadow_2x", grid_mm.GRID_COSTS_2X)):
            trades, st = grid_mm.simulate(bars, sym, costs)
            totals[label][sym] = st
            sim_trades = [SimTrade(t.symbol, t.entry_time, t.exit_time,
                                   t.side, t.entry_price, t.exit_price,
                                   t.net_return, t.exit_reason)
                          for t in trades]
            trades_by_cost[label].extend(sim_trades)
            per_symbol_trades[label][sym] = sim_trades
        print(f"[done] {sym}", flush=True)

    def judge(label: str) -> dict:
        trades = trades_by_cost[label]
        rep = oos_report(trades)
        per_symbol = {sym: oos_report(ts)["pooled_oos"]
                      for sym, ts in per_symbol_trades[label].items()}
        full = {**rep, "per_symbol_oos": per_symbol}
        bar = check_bar(full)
        holdout = holdout_check(full)
        pooled = rep["pooled_oos"]
        import numpy as np
        from rigorous_backtest.walkforward import FOLDS, trades_in_window
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
        return {"pooled_oos": pooled, "per_fold": rep["per_fold"],
                "per_symbol_oos": per_symbol, "bar": bar,
                "holdout": holdout, "bonferroni": bonf,
                "checks": checks, "passes_all": all(checks.values())}

    judged = {label: judge(label) for label in trades_by_cost}
    n_oos = judged["programme"]["pooled_oos"].get("trades") or 0
    if n_oos < 200:
        verdict = "insufficient OOS trades"
    elif all(j["passes_all"] for j in judged.values()):
        verdict = ("PASS — promotion candidate (forward-test candidate "
                   "only, under the Phase-3 forward protocol)")
    else:
        verdict = "FAIL — the family closes, per the declaration"

    fill_stats = {
        sym: totals["programme"][sym] for sym in SYMBOLS}
    payload = {
        "task": "TASK-STR-RD-023",
        "declaration_sha256": digest,
        "panel": {"name": "BTC/ETH/SOL (rd.common SYMBOLS)",
                  "timeframe": "15m", "months": "2023-10..2026-10",
                  "source": "binance_vision_futures_um_monthly_klines via "
                            "rigorous_backtest.data_feed.load_dataset",
                  "per_symbol": provenance},
        "trial_floor_stated": args.trial_floor,
        "fill_model": {
            "trade_through_margin": grid_mm.TRADE_THROUGH_MARGIN,
            "adverse_selection_bps_per_fill":
                grid_mm.ADVERSE_SELECTION_BPS_PER_FILL,
            "programme_costs": grid_mm.GRID_COSTS.describe(),
            "shadow_costs": grid_mm.GRID_COSTS_2X.describe(),
            "per_symbol_stats_programme": fill_stats,
            "touch_no_fill_total": sum(
                fill_stats[s]["touch_no_fill"] for s in SYMBOLS),
        },
        "signal_totals": totals,
        "judged": judged,
        "verdict": verdict,
    }
    (out / "results.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = ["# RESULTS — TASK-STR-RD-023 declared run", "",
             f"**Verdict: {verdict}**", "",
             f"Declaration SHA-256 re-verified: {digest}",
             f"Trial floor stated: N = {args.trial_floor} "
             f"(Bonferroni alpha = 0.05/N)",
             f"Touches rejected by the fill haircut (touch_no_fill): "
             f"{payload['fill_model']['touch_no_fill_total']}", ""]
    for label, j in judged.items():
        po = j["pooled_oos"]
        lines += [f"## {label}", "",
                  f"OOS trades: {po.get('trades')}, expectancy_net: "
                  f"{po.get('expectancy_net')}, PF_net: "
                  f"{po.get('profit_factor_net')}", "",
                  f"Checks: {json.dumps(j['checks'])}", ""]
    (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "oos_trades_programme": n_oos},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
