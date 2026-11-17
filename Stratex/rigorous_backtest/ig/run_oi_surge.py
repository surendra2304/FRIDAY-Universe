"""THE DECLARED RUN — TASK-STR-RD-022 (OI-surge follow-through).

DO NOT EXECUTE THIS SCRIPT until every gate in ../RUNBOOK.md passes.
Executing it IS the backtest: the declaration covers exactly ONE run
of these two frozen cells. This file was written and compile-checked
during prep only; it has never been executed against the real panel.

What it does, in order:
1. Re-verifies the declaration hash in the given main checkout
   (aborts on any mismatch).
2. For each of the 25 declared universe symbols: loads the 1h kline
   panel through the programme's verified loader (aborts on any
   gap-audit deviation), and loads the Binance Vision daily metrics
   archives with per-file SHA-256 checksum verification. A symbol
   with > 1% of its daily metrics files missing is excluded BY THE
   DECLARED RULE and the exclusion is recorded — never patched over.
3. Runs the pinned harness (oi_surge.py, same directory) for both
   cells (4h, 1d) at programme costs (16 bps RT) and at the 2x
   shadow (32 bps RT).
4. Judges each cell separately with the programme's own functions
   (rd.common.check_bar + holdout_check), plus the Bonferroni
   one-sided t-test against the trial floor stated on the command
   line (the FINAL programme counter, entering counter + 2 for
   this declaration's two cells — there is deliberately no default).
5. Writes results.json + RESULTS.md to --out and refuses to run if
   RESULTS.md already exists there (one declared run; no re-runs).

Verdict rules (declaration + programme practice), per cell:
- pooled OOS trades < 200 at programme costs -> "insufficient OOS trades"
- every bar component (expectancy > 0, PF >= 1.2, >= 200 trades,
  >= 4/5 positive folds, holdout, Bonferroni) at BOTH cost levels
  -> PASS (forward-test CANDIDATE only, Phase-3 protocol)
- anything else -> FAIL for that cell; both cells failing closes
  the family.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

DECLARATION_SHA256 = "6368711d5fcef1541b6af49a1d2f48f5b0caafe9b8f6f9109bdd9e7ca3aaecf8"

UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "TRXUSDT", "AVAXUSDT",
    "NEARUSDT", "ATOMUSDT", "UNIUSDT", "ETCUSDT", "BCHUSDT", "FILUSDT",
    "XLMUSDT", "HBARUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT",
    "AAVEUSDT",
]
PANEL_START = date(2022, 1, 1)
PANEL_END = date(2026, 10, 31)
KLINE_MONTHS = ("2022-01", "2026-10")
CELLS = ("4h", "1d")
TF_DELTA = {"4h": timedelta(hours=4), "1d": timedelta(days=1)}
MAX_MISSING_FRACTION = 0.01   # declared panel gate


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
    ap.add_argument("--panel-dir", required=True,
                    help="kline cache dir for the programme loader "
                         "(hash-verified cache; downloads on miss)")
    ap.add_argument("--metrics-dir", required=True,
                    help="cache dir for the daily metrics zips "
                         "(every parsed file is checksum-verified)")
    ap.add_argument("--out", required=True, help="results output dir")
    ap.add_argument("--trial-floor", required=True, type=int,
                    help="FINAL programme trial counter at run time "
                         "(entering counter + 2 for this declaration's "
                         "two cells), read from the rd-reconcile ledger; "
                         "stated in the results")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "RESULTS.md").exists():
        print("REFUSING: RESULTS.md already exists in --out. "
              "The declaration allows exactly one run.", file=sys.stderr)
        return 2

    repo = Path(args.repo)
    decl = repo / "Stratex/rigorous_backtest/ig/oi_declaration.json"
    digest = hashlib.sha256(decl.read_bytes()).hexdigest()
    if digest != DECLARATION_SHA256:
        print(f"ABORT: declaration hash {digest} != {DECLARATION_SHA256}",
              file=sys.stderr)
        return 2

    sys.path.insert(0, str(repo / "Stratex"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import metrics_feed
    import oi_surge  # the pinned harness (this directory)
    from rigorous_backtest.data_feed import load_dataset, resample_dataset
    from rigorous_backtest.walkforward import FOLDS, oos_report, trades_in_window
    from rigorous_backtest.rd.common import check_bar, holdout_check
    from rigorous_backtest.simulator import Trade as SimTrade
    from scipy import stats as scipy_stats
    import numpy as np

    panel_dir = Path(args.panel_dir)
    metrics_dir = Path(args.metrics_dir)
    provenance = {}
    excluded = {}
    # cell -> cost label -> [SimTrade]; cell -> cost label -> {sym: [SimTrade]}
    trades_by_cell = {tf: {"costs_16bps": [], "costs_32bps_shadow": []}
                      for tf in CELLS}
    per_symbol = {tf: {"costs_16bps": {}, "costs_32bps_shadow": {}}
                  for tf in CELLS}
    totals = {tf: {"costs_16bps": {}, "costs_32bps_shadow": {}}
              for tf in CELLS}

    for sym in UNIVERSE:
        ds = load_dataset(sym, "1h", KLINE_MONTHS[0], KLINE_MONTHS[1],
                          cache_dir=panel_dir)
        m = ds.manifest
        ga = m["gap_audit"]
        if ga["missing_bars"] != 0:
            print(f"ABORT: kline panel deviation for {sym}: "
                  f"missing={ga['missing_bars']}", file=sys.stderr)
            return 2
        snapshots, mman = metrics_feed.load_metrics_series(
            sym, PANEL_START, PANEL_END, cache_dir=metrics_dir / sym)
        provenance[sym] = {
            "kline_rows_1h": m["rows"], "kline_csv_sha256": m["csv_sha256"],
            "kline_missing_bars": ga["missing_bars"],
            "metrics_files": len(mman["files"]),
            "metrics_missing_days": len(mman["missing_days"]),
            "metrics_missing_fraction": mman["missing_fraction"],
        }
        if mman["missing_fraction"] > MAX_MISSING_FRACTION:
            excluded[sym] = (f"metrics missing fraction "
                             f"{mman['missing_fraction']:.4f} > 0.01 "
                             f"(declared rule)")
            for tf in CELLS:
                for label in trades_by_cell[tf]:
                    per_symbol[tf][label][sym] = []
            print(f"[excluded] {sym}: {excluded[sym]}", flush=True)
            continue
        for tf in CELLS:
            rs = resample_dataset(ds, tf)
            bars = bars_from_df(rs.df)
            close_times = [b["time"].to_pydatetime() + TF_DELTA[tf]
                           for b in bars]
            oi = metrics_feed.oi_at_bar_close(snapshots, close_times)
            for label, costs in (("costs_16bps", oi_surge.COSTS),
                                 ("costs_32bps_shadow", oi_surge.COSTS_2X)):
                trades, st = oi_surge.simulate(bars, oi, sym, tf, costs)
                totals[tf][label][sym] = st
                sim_trades = [SimTrade(t.symbol, t.entry_time, t.exit_time,
                                       t.side, t.entry_price, t.exit_price,
                                       t.net_return, t.exit_reason)
                              for t in trades]
                trades_by_cell[tf][label].extend(sim_trades)
                per_symbol[tf][label][sym] = sim_trades
        print(f"[done] {sym}", flush=True)

    def judge(tf: str, label: str) -> dict:
        trades = trades_by_cell[tf][label]
        rep = oos_report(trades)
        per_sym = {sym: oos_report(ts)["pooled_oos"]
                   for sym, ts in per_symbol[tf][label].items()}
        full = {**rep, "per_symbol_oos": per_sym}
        bar = check_bar(full)
        holdout = holdout_check(full)
        pooled = rep["pooled_oos"]
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
                "per_symbol_oos": per_sym, "bar": bar,
                "holdout": holdout, "bonferroni": bonf,
                "checks": checks, "passes_all": all(checks.values())}

    judged = {}
    verdicts = {}
    for tf in CELLS:
        judged[tf] = {label: judge(tf, label)
                      for label in ("costs_16bps", "costs_32bps_shadow")}
        n_oos = judged[tf]["costs_16bps"]["pooled_oos"].get("trades") or 0
        if n_oos < 200:
            verdicts[tf] = "insufficient OOS trades"
        elif all(j["passes_all"] for j in judged[tf].values()):
            verdicts[tf] = ("PASS — promotion candidate (forward-test "
                            "candidate only, under the Phase-3 forward "
                            "protocol)")
        else:
            verdicts[tf] = "FAIL — the cell fails the declared bar"
    if all(v.startswith("FAIL") for v in verdicts.values()):
        family_verdict = "FAIL — both cells failed; the family closes"
    else:
        family_verdict = "see per-cell verdicts"

    payload = {
        "task": "TASK-STR-RD-022",
        "declaration_sha256": digest,
        "panel": {"name": "crypto30-metrics-25", "timeframes": list(CELLS),
                  "months": "2022-01..2026-10",
                  "klines_source": "binance_vision_futures_um_monthly_klines "
                                   "via rigorous_backtest.data_feed.load_dataset "
                                   "(1h base, resample_dataset to 4h/1d)",
                  "metrics_source": "binance_vision_futures_um_daily_metrics, "
                                    "per-file .CHECKSUM (SHA-256) verified",
                  "per_symbol": provenance,
                  "excluded_by_declared_rule": excluded},
        "trial_floor_stated": args.trial_floor,
        "signal_totals": totals,
        "judged": judged,
        "verdicts": verdicts,
        "family_verdict": family_verdict,
    }
    (out / "results.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = ["# RESULTS — TASK-STR-RD-022 declared run", "",
             f"**Family verdict: {family_verdict}**", "",
             f"Declaration SHA-256 re-verified: {digest}",
             f"Trial floor stated: N = {args.trial_floor} "
             f"(Bonferroni alpha = 0.05/N)", ""]
    if excluded:
        lines += ["Excluded by the declared >1% metrics-missing rule: "
                  + ", ".join(sorted(excluded)), ""]
    for tf in CELLS:
        lines += [f"## Cell {tf} — verdict: {verdicts[tf]}", ""]
        for label, j in judged[tf].items():
            po = j["pooled_oos"]
            lines += [f"### {label}", "",
                      f"OOS trades: {po.get('trades')}, expectancy_net: "
                      f"{po.get('expectancy_net')}, PF_net: "
                      f"{po.get('profit_factor_net')}", "",
                      f"Checks: {json.dumps(j['checks'])}", ""]
    (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"verdicts": verdicts,
                      "family_verdict": family_verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
