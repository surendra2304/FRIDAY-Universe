#!/usr/bin/env python3
"""ONE-RUN driver for TASK-STR-DISC-004 (ORB/VWAP equity intraday).

Executes the declared run exactly once, under the SRS TEMPORAL
HOLDOUT v1 section 2.3 procedure. Hard gates, in order — any failure
aborts BEFORE any trade is computed:

  1. The declaration file's SHA-256 must equal the hash pinned in
     orb_vwap.py (DECLARATION_SHA256). Exit 6 on mismatch.
  2. The results file must not already exist — a second run is a
     second look at the holdout and is refused. Exit 7.
  3. verification_report.json in the panel dir must say overall
     PASS (every symbol, all five checks). Exit 8 otherwise.
  4. Every symbol's panel file must re-hash to the frozen
     data_provenance.json value. Exit 9 on deviation (FAIL, not
     re-pin).

--entering-trials is the programme trial counter read from the
ledger at run time (RUNBOOK step); the judge uses final_N =
entering + 1 for the Bonferroni alpha. This family is ONE cell.

Usage (see RUNBOOK.md for the full gated sequence):
  python3 run_orb_vwap.py --panel-dir /path/panel \
      --entering-trials <N> --out /path/orb_vwap_results.json

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orb_vwap  # noqa: E402

DEFAULT_DECLARATION = Path(__file__).resolve().parent.parent / \
    "orb_vwap_declaration.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel-dir", required=True)
    ap.add_argument("--declaration", default=str(DEFAULT_DECLARATION))
    ap.add_argument("--entering-trials", type=int, required=True,
                    help="programme trial counter from the ledger at run time")
    ap.add_argument("--out", required=True, help="results JSON path")
    args = ap.parse_args()

    panel_dir = Path(args.panel_dir)
    out = Path(args.out)

    # Gate 1 — declaration integrity.
    decl = Path(args.declaration)
    actual = sha256_file(decl)
    if actual != orb_vwap.DECLARATION_SHA256:
        print(f"ABORT: declaration hash {actual} != pinned "
              f"{orb_vwap.DECLARATION_SHA256}. The declaration is "
              "frozen; a changed declaration is a new declaration.",
              file=sys.stderr)
        return 6

    # Gate 2 — one run only (holdout burn clause).
    if out.exists():
        print(f"ABORT: results already exist at {out}. The declared "
              "run executes exactly once; a re-run burns the holdout.",
              file=sys.stderr)
        return 7

    # Gate 3 — panel verified PASS.
    report_path = panel_dir / "verification_report.json"
    if not report_path.exists():
        print(f"ABORT: no verification report at {report_path}. "
              "Run verify_orb_panel.py first.", file=sys.stderr)
        return 8
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("overall") != "PASS":
        print(f"ABORT: panel verification overall = "
              f"{report.get('overall')!r}, not PASS. An unverified "
              "panel is not run.", file=sys.stderr)
        return 8

    # Gate 4 — frozen panel integrity.
    prov_path = panel_dir / "data_provenance.json"
    if not prov_path.exists():
        print(f"ABORT: no frozen provenance at {prov_path}.",
              file=sys.stderr)
        return 9
    frozen = json.loads(prov_path.read_text(encoding="utf-8")) \
        .get("symbols", {})
    bars_by_symbol: dict = {}
    for symbol in orb_vwap.UNIVERSE:
        fpath = panel_dir / f"{symbol}_15min_sip_2023-01-01_2026-10-31.csv"
        if not fpath.exists():
            print(f"ABORT: panel file missing for {symbol}.",
                  file=sys.stderr)
            return 9
        digest = sha256_file(fpath)
        if frozen.get(symbol) != digest:
            print(f"ABORT: {symbol} panel hash {digest} != frozen "
                  f"{frozen.get(symbol)}. FAIL, not re-pin.",
                  file=sys.stderr)
            return 9
        bars_by_symbol[symbol] = orb_vwap.load_panel(fpath, symbol)

    result = orb_vwap.judge(bars_by_symbol, args.entering_trials,
                            label="TASK-STR-DISC-004 declared run")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"verdict: {result['verdict']}")
    print(f"pooled OOS trades (1x): {result['pooled_oos_1x']['trades']}")
    print(f"trade_list_sha256: {result['trade_list_sha256']}")
    print(f"final_N: {result['trial_accounting']['final_N']} "
          f"(alpha {result['trial_accounting']['bonferroni_alpha']:.3e})")
    print(f"results -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
