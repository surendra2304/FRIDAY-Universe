#!/usr/bin/env python3
"""Declared runner for TASK-STR-RD-019 — cross-sectional short-term
reversal conditioned on a volume climax (family
xs_reversal_volclimax_1d).

DO NOT EXECUTE until BOTH gates pass (see ../RUNBOOK.md):
  Gate A — the frozen declaration is merged on origin/main at
           Stratex/rigorous_backtest/rd19/xsrev_declaration.json and
           hashes to DECLARATION_SHA256 below.
  Gate B — the declared runs ahead of this family in the queue (SRS,
           then S-RD1) have concluded; the programme runs one
           declared run at a time.

This runner: loads the frozen declaration from a FRESH origin/main
checkout (--repo) and verifies its SHA-256 before anything else;
loads the declared Binance Vision 15m crypto30 panel via the
programme's own loader and verifies every file against the S-RD1
run-prep provenance manifest (row counts, missing bars, CSV
SHA-256) — any mismatch ABORTS; aggregates to daily bars with the
harness's declared aggregation and asserts the declared day count;
simulates the declared rules at programme costs AND the 2x shadow;
judges with the programme's own functions imported from the same
checkout (oos_report, check_bar, holdout_check, walkforward folds);
applies the declared verdict rules including the Bonferroni
one-sided t-test at --trial-floor. Refuses to run if RESULTS.md
already exists in --out (a declared run is never silently re-run).

The Bonferroni denominator is NOT defaulted: --trial-floor is the
N_global of the declaration's formula — max(global trial-ledger N
entering this run, 3893) + 1, minimum 3894 — computed from the
ledger at run time and passed explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
import xsrev  # noqa: E402

DECLARATION_SHA256 = ("ffc3c573071ee8014d99d125cbc08551b39f47fb756696e603124b81e86f31f1")
DECLARATION_REL = "Stratex/rigorous_backtest/rd19/xsrev_declaration.json"
EXPECTED_ROWS_15M = 108_192
EXPECTED_DAYS = 1127


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bars_from_df(df) -> list[dict]:
    return [
        {"time": ts, "open": float(o), "high": float(h), "low": float(lo),
         "close": float(c), "volume": float(v)}
        for ts, o, h, lo, c, v in zip(
            df.index, df["open"], df["high"], df["low"], df["close"],
            df["volume"])
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True,
                    help="fresh origin/main checkout of FRIDAY-Universe")
    ap.add_argument("--panel-dir",
                    default=str(Path.home() / "workspace" / "srd1-runprep"
                                / "panel"),
                    help="verified 15m panel (S-RD1 run-prep layout)")
    ap.add_argument("--expected-provenance",
                    default=str(Path.home() / "workspace" / "srd1-runprep"
                                / "panel_provenance.json"),
                    help="S-RD1 run-prep panel provenance manifest (JSON)")
    ap.add_argument("--trial-floor", type=int, required=True,
                    help="Bonferroni denominator N_global per the "
                         "declaration: max(ledger N entering this run, "
                         "3893) + 1 (minimum 3894). No default — the "
                         "runner refuses to guess it.")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "RESULTS.md").exists():
        print("REFUSING TO RUN: RESULTS.md already exists in --out; a "
              "declared run is never silently re-run.")
        return 2

    repo = Path(args.repo)
    decl_path = repo / DECLARATION_REL
    if not decl_path.exists():
        print(f"ABORT: declaration not found at {decl_path} "
              "(Gate A: it must be merged on origin/main first).")
        return 2
    got = sha256_file(decl_path)
    if got != DECLARATION_SHA256:
        print(f"ABORT: declaration SHA-256 mismatch.\n  expected "
              f"{DECLARATION_SHA256}\n  got      {got}")
        return 2
    declaration = json.loads(decl_path.read_text(encoding="utf-8"))
    print(f"declaration verified: {DECLARATION_REL} sha256={got}")

    rb = repo / "Stratex" / "rigorous_backtest"
    sys.path.insert(0, str(rb))
    from load import load_dataset                      # noqa: E402
    from rd.common import check_bar, holdout_check     # noqa: E402
    from rd.walkforward import oos_report              # noqa: E402
    from simulator import Trade as SimTrade            # noqa: E402

    symbols = declaration["data_plan"]["symbols"]
    provenance = json.loads(
        Path(args.expected_provenance).read_text(encoding="utf-8"))
    panel: dict[str, list[dict]] = {}
    for sym in symbols:
        df, man = load_dataset(sym, "15m", "2023-10", "2026-10",
                               cache_dir=args.panel_dir)
        exp = provenance["symbols"][sym]
        problems = []
        if man["rows"] != EXPECTED_ROWS_15M or man["rows"] != exp["rows"]:
            problems.append(f"rows {man['rows']} != {exp['rows']}")
        if man["missing_bars"] != 0 or man["missing_bars"] != exp["missing"]:
            problems.append(f"missing {man['missing_bars']} != {exp['missing']}")
        if man["csv_sha256"] != exp["csv_sha256"]:
            problems.append("csv_sha256 mismatch vs S-RD1 provenance")
        if problems:
            print(f"ABORT: panel mismatch for {sym}: {problems}")
            return 2
        daily = xsrev.aggregate_daily(bars_from_df(df))
        if len(daily) != EXPECTED_DAYS:
            print(f"ABORT: {sym} aggregated to {len(daily)} daily bars, "
                  f"expected {EXPECTED_DAYS}")
            return 2
        panel[sym] = daily
        print(f"{sym}: 15m verified ({man['rows']} rows, csv "
              f"{man['csv_sha256'][:12]}...), {len(daily)} daily bars")

    def judge(trades, all_trades, label):
        oos = [t for t in trades]
        rep = oos_report(oos)
        per_symbol = {}
        for sym in symbols:
            st = [t for t in oos if t.symbol == sym]
            per_symbol[sym] = oos_report(st) if st else None
        return {
            "label": label,
            "pooled": rep,
            "per_symbol": per_symbol,
            "bar": check_bar(rep),
            "holdout": holdout_check(oos, all_trades),
        }

    def bonferroni(rep, n_global):
        rets = rep.get("_rets") or []
        n = len(rets)
        if n < 2:
            return {"n": n, "t_stat": None, "alpha": 0.05 / n_global,
                    "pass": False, "note": "too few OOS trades"}
        mean = statistics.fmean(rets)
        sd = statistics.stdev(rets)
        if sd == 0:
            return {"n": n, "t_stat": None, "alpha": 0.05 / n_global,
                    "pass": False, "note": "zero variance"}
        t = mean / (sd / math.sqrt(n))
        # one-sided normal approx via erf (matches the S-RD1 runner)
        p = 0.5 * (1 - math.erf(t / math.sqrt(2)))
        alpha = 0.05 / n_global
        return {"n": n, "t_stat": t, "p_one_sided": p, "alpha": alpha,
                "pass": p < alpha}

    results: dict = {"declaration_sha256": DECLARATION_SHA256,
                     "trial_floor": args.trial_floor}
    verdict_lines = []
    for costs, tag in ((xsrev.COSTS, "programme_16bps"),
                       (xsrev.COSTS_2X, "shadow_32bps")):
        trades, stats = xsrev.simulate(panel, costs)
        sim_trades = [SimTrade(t.symbol, t.entry_time, t.exit_time, t.side,
                               t.entry_price, t.exit_price, t.net_return,
                               t.exit_reason) for t in trades]
        judged = judge(sim_trades, sim_trades, tag)
        bf = bonferroni(judged["pooled"], args.trial_floor)
        results[tag] = {"costs": costs.describe(), "stats": stats,
                        "pooled": {k: v for k, v in judged["pooled"].items()
                                   if k != "_rets"},
                        "per_symbol": judged["per_symbol"],
                        "bar": judged["bar"], "holdout": judged["holdout"],
                        "bonferroni": bf}
        (out / f"trades_{tag}.json").write_text(json.dumps(
            [{**t.__dict__, "entry_time": str(t.entry_time),
              "exit_time": str(t.exit_time)} for t in trades], indent=1),
            encoding="utf-8")
        verdict_lines.append(
            f"{tag}: trades={len(trades)} OOS n={judged['pooled']['n']} "
            f"expectancy={judged['pooled']['expectancy_pct']}% "
            f"PF={judged['pooled']['profit_factor']} "
            f"bar_pass={judged['bar']['pass']} "
            f"holdout_pass={judged['holdout']['pass']} "
            f"bonferroni_pass={bf['pass']} "
            f"(p={bf.get('p_one_sided')}, alpha={bf['alpha']:.3e}) "
            f"signals: ranked={stats['picks_ranked']} "
            f"climax={stats['picks_climax']} "
            f"gated_out={stats['picks_gated_out']} "
            f"skipped_open={stats['skipped_open']}")

    pooled_n = results["programme_16bps"]["pooled"]["n"]
    if pooled_n < 200:
        verdict = ("VERDICT: insufficient OOS trades "
                   f"({pooled_n} < 200 at programme costs) — the family "
                   "is neither proven nor disproven at the programme bar.")
    else:
        def passes(tag):
            r = results[tag]
            return (r["bar"]["pass"] and r["holdout"]["pass"]
                    and r["bonferroni"]["pass"])
        if passes("programme_16bps") and passes("shadow_32bps"):
            verdict = ("VERDICT: PASS at programme costs AND the 2x "
                       "shadow — forward-test CANDIDATE only (Phase-3 "
                       "bar still applies: >=100 forward trades and "
                       ">=8 weeks on demo, FWD-006 sizing).")
        else:
            verdict = ("VERDICT: FAIL — the family does not clear the "
                       "pre-declared bar at both cost levels; per the "
                       "programme rule it closes (strict OOS PF < 1.2 "
                       "components delete the family).")

    (out / "results.json").write_text(json.dumps(results, indent=1,
                                                 default=str),
                                      encoding="utf-8")
    (out / "RESULTS.md").write_text(
        "# TASK-STR-RD-019 — declared run result\n\n"
        f"Declaration: {DECLARATION_REL} sha256={DECLARATION_SHA256}\n"
        f"Trial floor (N_global): {args.trial_floor}\n\n"
        + "\n".join(verdict_lines) + f"\n\n{verdict}\n",
        encoding="utf-8")
    print("\n".join(verdict_lines))
    print(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
