#!/usr/bin/env python3
"""Declared runner for TASK-STR-RD-019 — cross-sectional short-term
reversal conditioned on a volume climax (family
xs_reversal_volclimax_1d).

DO NOT EXECUTE until ALL gates pass (see ../RUNBOOK.md):
  Gate A — the frozen declaration is merged on origin/main at
           Stratex/rigorous_backtest/rd19/xsrev_declaration.json and
           hashes to DECLARATION_SHA256 below.
  Gate B — the declared runs ahead of this family in the queue (SRS,
           then S-RD1, then RD-018) have concluded; the programme
           runs one declared run at a time.
  Gate C — the harness files hash to the RUNBOOK pins and the
           synthetic suites pass.

This runner: loads the frozen declaration from a FRESH origin/main
checkout (--repo) and verifies its SHA-256 before anything else;
loads the declared Binance Vision 15m crypto30 panel via the
programme's own loader (rigorous_backtest.data_feed.load_dataset,
which returns a Dataset whose manifest the provenance checks below
read) and verifies every symbol against the S-RD1 run-prep
provenance manifest (row counts, gap-audit missing bars, CSV
SHA-256) — any mismatch ABORTS; aggregates to daily bars with the
harness's declared aggregation and asserts the declared day count;
simulates the declared rules at programme costs AND the 2x shadow;
judges with the programme's own functions imported from the same
checkout (walkforward.oos_report for per-fold + pooled OOS metrics,
rd.common.check_bar for the promotion bar, rd.common.holdout_check
for the per-symbol breadth holdout — the report dict is built
runner-side over all 30 panel symbols, the S-RD1 adaptation, since
rd.common.full_report covers only the RD-001 symbol triple);
applies the TEMPORAL HOLDOUT v1 overlay (H = trades entered in W5,
D = trades entered in W1..W4) and the Bonferroni one-sided t-test
at --trial-floor. Refuses to run if RESULTS.md already exists in
--out (a declared run is never silently re-run).

Refusals, all enforced BEFORE any data load:
  * --trial-floor below the declared minimum N_global (3894);
  * missing --declared-run attestation (TEMPORAL HOLDOUT v1, H5:
    the operator attests the panel was verified first and the
    holdout's trades/metrics were never computed or inspected
    before this single evaluation);
  * RESULTS.md already present in --out.

The Bonferroni denominator is NOT defaulted: --trial-floor is the
N_global of the declaration's formula — max(global trial-ledger N
entering this run, 3893) + 1, minimum 3894 — computed from the
ledger at run time and passed explicitly.

AMENDMENT RECORD (2026-11-17, PR #897 supervisor review):
  F1 — this runner's programme-API glue was rewritten against the
  real origin/main APIs (the original called modules/signatures
  that do not exist on main and could never execute; the judge path
  is now covered by test_xsrev_judge_smoke.py end-to-end on
  synthetic trades through the real programme code).
  F2 — the declaration gained the TEMPORAL HOLDOUT v1 overlay
  (coordinator ruling); DECLARATION_SHA256 below is the AMENDED
  declaration hash. The signal harness xsrev.py is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
import xsrev  # noqa: E402

DECLARATION_SHA256 = ("a2d5f212308fdd097e968c801c175b9513da3ff24c49456590eec70d324d917b")
DECLARATION_REL = "Stratex/rigorous_backtest/rd19/xsrev_declaration.json"
EXPECTED_ROWS_15M = 108_192
EXPECTED_DAYS = 1127
MIN_TRIAL_FLOOR = 3894
# The frozen universe: the declaration's rules.universe list, identical
# to rd2/panels.py CRYPTO30 on origin/main at declaration time. The
# runner imports CRYPTO30 from the checkout and aborts on any drift.
EXPECTED_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "TRXUSDT", "AVAXUSDT",
    "NEARUSDT", "ATOMUSDT", "UNIUSDT", "ETCUSDT", "BCHUSDT", "FILUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT",
    "HBARUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT",
]
COST_LEVELS = (("programme_16bps", xsrev.COSTS),
               ("shadow_32bps", xsrev.COSTS_2X))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_programme(repo: Path) -> types.SimpleNamespace:
    """Import the programme's own machinery from a fresh origin/main
    checkout (--repo): the verified loader, the walk-forward report,
    the promotion bar, the breadth holdout and the trade metrics.
    All judging in this runner goes through these functions — no
    re-implementation."""
    stratex = str(repo / "Stratex")
    if stratex not in sys.path:
        sys.path.insert(0, stratex)
    from rigorous_backtest.data_feed import load_dataset
    from rigorous_backtest.rd.common import check_bar, holdout_check
    from rigorous_backtest.rd2.panels import CRYPTO30
    from rigorous_backtest.simulator import Trade as SimTrade
    from rigorous_backtest.simulator import trade_metrics
    from rigorous_backtest.walkforward import (FOLDS, oos_report,
                                               trades_in_window)
    return types.SimpleNamespace(
        load_dataset=load_dataset, check_bar=check_bar,
        holdout_check=holdout_check, CRYPTO30=list(CRYPTO30),
        SimTrade=SimTrade, trade_metrics=trade_metrics, FOLDS=FOLDS,
        oos_report=oos_report, trades_in_window=trades_in_window)


def bars_from_df(df) -> list[dict]:
    return [
        {"time": ts, "open": float(o), "high": float(h), "low": float(lo),
         "close": float(c), "volume": float(v)}
        for ts, o, h, lo, c, v in zip(
            df.index, df["open"], df["high"], df["low"], df["close"],
            df["volume"])
    ]


def bonferroni(trades, n_global: int, prog) -> dict:
    """Bonferroni one-sided t-test on the pooled OOS per-trade net
    returns (the S-RD1 runner's construction): OOS = trades entered
    inside the walk-forward folds, entry-time attribution."""
    import numpy as np
    from scipy import stats as scipy_stats
    oos: list = []
    for _, s, e in prog.FOLDS:
        oos.extend(prog.trades_in_window(trades, s, e))
    arr = np.array([t.net_return for t in oos], dtype=float)
    n = int(len(arr))
    if n >= 2 and arr.std(ddof=1) > 0:
        t_stat = float(arr.mean() / (arr.std(ddof=1) / np.sqrt(n)))
        p_val = float(1.0 - scipy_stats.t.cdf(t_stat, n - 1))
    else:
        t_stat, p_val = None, None
    alpha = 0.05 / n_global
    return {"n": n, "t_stat": t_stat, "p_value": p_val, "alpha": alpha,
            "trial_floor": n_global,
            "passes": (p_val is not None and p_val < alpha)}


def temporal_holdout(trades, per_fold: dict, prog) -> dict:
    """TEMPORAL HOLDOUT v1 (declaration evaluation_bar overlay):
    H = trades entered in W5, D = trades entered in W1..W4.
    H1 |H| >= 20; H2 expectancy_net(H) > 0; H3 expectancy_net(D) > 0;
    H4 no single fold contributes more than 80% of total positive
    fold profit (fold profit = expectancy_net x trades, the
    rd.common.holdout_check construction applied to folds);
    H5 is the run-protocol attestation enforced in main()."""
    folds = prog.FOLDS
    holdout_id, h_start, h_end = folds[-1]
    if holdout_id != "W5":
        raise ValueError(f"expected the last fold to be W5, got {holdout_id}")
    h_trades = prog.trades_in_window(trades, h_start, h_end)
    d_trades = prog.trades_in_window(trades, folds[0][1], h_start)
    m_h = prog.trade_metrics(h_trades)
    m_d = prog.trade_metrics(d_trades)
    fold_profits = {}
    for fid, _, _ in folds:
        m = per_fold[fid]
        fold_profits[fid] = (m.get("expectancy_net") or 0.0) * \
            (m.get("trades") or 0)
    total_pos = sum(p for p in fold_profits.values() if p > 0)
    max_share = (max(fold_profits.values()) / total_pos) \
        if total_pos > 0 else 1.0
    checks = {
        "H1_holdout_trades_gte_20": m_h["trades"] >= 20,
        "H2_holdout_expectancy_gt_0": (m_h["expectancy_net"] or 0.0) > 0,
        "H3_dev_oos_expectancy_gt_0": (m_d["expectancy_net"] or 0.0) > 0,
        "H4_fold_concentration_lte_0.80": total_pos > 0 and max_share <= 0.80,
    }
    return {"checks": checks, "passes": all(checks.values()),
            "holdout_fold": holdout_id,
            "holdout_metrics": m_h, "dev_oos_metrics": m_d,
            "fold_profits": fold_profits,
            "max_fold_profit_share": max_share,
            "H5_burn_clause": "ATTESTED_BY_RUN_PROTOCOL (--declared-run)"}


def judge_level(trades, symbols, trial_floor: int, prog) -> dict:
    """Judge one cost level's pooled trade list with the programme's
    own functions: oos_report (per-fold + pooled), check_bar over a
    report whose per_symbol_oos spans ALL panel symbols (the S-RD1
    adaptation), holdout_check (breadth), the TEMPORAL HOLDOUT v1
    overlay, and the Bonferroni t-test."""
    rep = prog.oos_report(trades)
    per_symbol = {}
    for sym in symbols:
        st = [t for t in trades if t.symbol == sym]
        per_symbol[sym] = prog.oos_report(st)["pooled_oos"]
    full = {**rep, "per_symbol_oos": per_symbol}
    bar = prog.check_bar(full)
    holdout = prog.holdout_check(full)
    bonf = bonferroni(trades, trial_floor, prog)
    th = temporal_holdout(trades, rep["per_fold"], prog)
    checks = {**bar["checks"],
              "holdout_breadth": bool(holdout["passes"]),
              "temporal_holdout_v1": bool(th["passes"]),
              "bonferroni": bool(bonf["passes"])}
    return {"pooled_oos": rep["pooled_oos"], "per_fold": rep["per_fold"],
            "per_symbol_oos": per_symbol, "bar": bar, "holdout": holdout,
            "temporal_holdout": th, "bonferroni": bonf,
            "checks": checks, "passes_all": all(checks.values())}


def judge_all(trades_by_tag, symbols, trial_floor: int, prog):
    """Judge every cost level and apply the declaration's verdict
    rules. Returns (judged, verdict, verdict_note). The insufficient
    verdict is exactly the declared phrase, nothing added."""
    judged = {tag: judge_level(ts, symbols, trial_floor, prog)
              for tag, ts in trades_by_tag.items()}
    n_oos = judged["programme_16bps"]["pooled_oos"].get("trades") or 0
    if n_oos < 200:
        return judged, "insufficient OOS trades", (
            f"Pooled OOS trades at programme costs = {n_oos} < 200 — "
            "the family is neither proven nor disproven at the "
            "programme bar (declared up front as a live possibility).")
    if all(j["passes_all"] for j in judged.values()):
        return judged, "PASS", (
            "Every bar component passes at programme costs AND the "
            "2x shadow — forward-test CANDIDATE only (Phase-3 bar "
            "still applies: >= 100 forward trades and >= 8 weeks on "
            "demo, FWD-006 sizing).")
    return judged, "FAIL", (
        "The family does not clear the pre-declared bar at both "
        "cost levels; per the declaration it closes (strict OOS "
        "PF < 1.2 components delete the family).")


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
                         "runner refuses to guess it, and refuses any "
                         "value below the declared minimum.")
    ap.add_argument("--declared-run", action="store_true",
                    help="attest the run protocol (TEMPORAL HOLDOUT "
                         "v1, H5): panel verified first; holdout "
                         "trades/metrics never previously computed or "
                         "inspected. Required — the runner refuses "
                         "to judge without it.")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    # Refusals first — every one fires before any data load.
    if args.trial_floor < MIN_TRIAL_FLOOR:
        print(f"REFUSING TO RUN: --trial-floor {args.trial_floor} is "
              f"below the declared minimum N_global {MIN_TRIAL_FLOOR} "
              "(the declaration's Bonferroni floor: max(ledger N, "
              "3893) + 1).", file=sys.stderr)
        return 2
    if not args.declared_run:
        print("REFUSING TO RUN: --declared-run attestation required "
              "(TEMPORAL HOLDOUT v1, H5 burn clause): the operator "
              "must attest the panel was verified first and the "
              "holdout was never previously computed or inspected.",
              file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "RESULTS.md").exists():
        print("REFUSING TO RUN: RESULTS.md already exists in --out; "
              "a declared run is never silently re-run.",
              file=sys.stderr)
        return 2

    repo = Path(args.repo)
    decl_path = repo / DECLARATION_REL
    if not decl_path.exists():
        print(f"ABORT: declaration not found at {decl_path} "
              "(Gate A: it must be merged on origin/main first).",
              file=sys.stderr)
        return 2
    got = sha256_file(decl_path)
    if got != DECLARATION_SHA256:
        print(f"ABORT: declaration SHA-256 mismatch.\n  expected "
              f"{DECLARATION_SHA256}\n  got      {got}",
              file=sys.stderr)
        return 2
    declaration = json.loads(decl_path.read_text(encoding="utf-8"))
    if "temporal_holdout_v1" not in declaration.get("evaluation_bar", {}):
        print("ABORT: the declaration on main carries no "
              "temporal_holdout_v1 overlay — it is not the amended "
              "declaration this runner was fixed against.",
              file=sys.stderr)
        return 2
    print(f"declaration verified: {DECLARATION_REL} sha256={got}")

    prog = load_programme(repo)
    symbols = list(prog.CRYPTO30)
    if symbols != EXPECTED_SYMBOLS:
        print("ABORT: rd2.panels.CRYPTO30 in the checkout differs "
              "from the declaration's frozen universe — panel "
              "definition drift; escalate, do not run.",
              file=sys.stderr)
        return 2

    import pandas as pd

    provenance = json.loads(
        Path(args.expected_provenance).read_text(encoding="utf-8"))
    panel: dict[str, list[dict]] = {}
    panel_provenance: dict[str, dict] = {}
    for sym in symbols:
        ds = prog.load_dataset(sym, "15m", "2023-10", "2026-10",
                               cache_dir=Path(args.panel_dir))
        m = ds.manifest
        ga = m["gap_audit"]
        exp = provenance["symbols"][sym]
        problems = []
        if m["rows"] != EXPECTED_ROWS_15M or m["rows"] != exp["rows"]:
            problems.append(f"rows {m['rows']} != {exp['rows']}")
        if ga["missing_bars"] != 0 or ga["missing_bars"] != exp["missing"]:
            problems.append(
                f"missing {ga['missing_bars']} != {exp['missing']}")
        if m["csv_sha256"] != exp["csv_sha256"]:
            problems.append("csv_sha256 mismatch vs S-RD1 provenance")
        if problems:
            print(f"ABORT: panel mismatch for {sym}: {problems}",
                  file=sys.stderr)
            return 2
        daily = xsrev.aggregate_daily(bars_from_df(ds.df))
        if len(daily) != EXPECTED_DAYS:
            print(f"ABORT: {sym} aggregated to {len(daily)} daily "
                  f"bars, expected {EXPECTED_DAYS}", file=sys.stderr)
            return 2
        panel[sym] = daily
        panel_provenance[sym] = {
            "rows": m["rows"], "csv_sha256": m["csv_sha256"],
            "missing_bars": ga["missing_bars"],
            "first_bar_utc": m["first_bar_utc"],
            "last_bar_utc": m["last_bar_utc"]}
        print(f"{sym}: 15m verified ({m['rows']} rows, csv "
              f"{m['csv_sha256'][:12]}...), {len(daily)} daily bars")

    trades_by_tag: dict[str, list] = {}
    stats_by_tag: dict[str, dict] = {}
    for tag, costs in COST_LEVELS:
        trades, stats = xsrev.simulate(panel, costs)
        trades_by_tag[tag] = [
            prog.SimTrade(t.symbol, pd.Timestamp(t.entry_time),
                          pd.Timestamp(t.exit_time), t.side,
                          t.entry_price, t.exit_price, t.net_return,
                          t.exit_reason) for t in trades]
        stats_by_tag[tag] = stats
        (out / f"trades_{tag}.json").write_text(json.dumps(
            [{**t.__dict__, "entry_time": str(t.entry_time),
              "exit_time": str(t.exit_time)} for t in trades], indent=1),
            encoding="utf-8")

    judged, verdict, verdict_note = judge_all(
        trades_by_tag, symbols, args.trial_floor, prog)

    results: dict = {
        "task": "TASK-STR-RD-019",
        "declaration_sha256": DECLARATION_SHA256,
        "trial_floor": args.trial_floor,
        "holdout_attestation": (
            "operator attested via --declared-run: panel verified "
            "first; holdout (W5) trades/metrics never computed or "
            "inspected before this evaluation (TEMPORAL HOLDOUT "
            "v1, H5)"),
        "panel_provenance": panel_provenance,
        "costs": {tag: costs.describe() for tag, costs in COST_LEVELS},
        "signal_stats": stats_by_tag,
        "judged": judged,
        "verdict": verdict,
        "verdict_note": verdict_note,
    }
    (out / "results.json").write_text(json.dumps(results, indent=1,
                                                 default=str),
                                      encoding="utf-8")
    lines = ["# TASK-STR-RD-019 — declared run result", "",
             f"**Verdict: {verdict}**", "", verdict_note, "",
             f"Declaration: {DECLARATION_REL} sha256={DECLARATION_SHA256}",
             f"Trial floor (N_global): {args.trial_floor}", ""]
    for tag, _ in COST_LEVELS:
        j = judged[tag]
        po = j["pooled_oos"]
        st = stats_by_tag[tag]
        lines += [f"## {tag}", "",
                  f"OOS trades: {po.get('trades')}, expectancy_net: "
                  f"{po.get('expectancy_net')}, PF_net: "
                  f"{po.get('profit_factor_net')}", "",
                  f"Checks: {json.dumps(j['checks'])}", "",
                  f"Temporal holdout v1: "
                  f"{json.dumps(j['temporal_holdout']['checks'])} "
                  f"(H trades "
                  f"{j['temporal_holdout']['holdout_metrics']['trades']}, "
                  f"H expectancy_net "
                  f"{j['temporal_holdout']['holdout_metrics']['expectancy_net']})",
                  "",
                  f"Signals: ranked={st['picks_ranked']} "
                  f"climax={st['picks_climax']} "
                  f"gated_out={st['picks_gated_out']} "
                  f"skipped_open={st['skipped_open']}", ""]
    (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    for tag, _ in COST_LEVELS:
        j = judged[tag]
        po = j["pooled_oos"]
        print(f"{tag}: OOS trades={po.get('trades')} "
              f"expectancy_net={po.get('expectancy_net')} "
              f"PF_net={po.get('profit_factor_net')} "
              f"passes_all={j['passes_all']}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
