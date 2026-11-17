"""Stage / verify the TASK-STR-RD-023 declared panel (grid / passive MM).

Uses ONLY the programme's verified loader (rigorous_backtest.data_feed
.load_dataset) for the declaration's universe — BTCUSDT, ETHUSDT,
SOLUSDT (the rd/common.py SYMBOLS triple) — exactly as the
declaration's data plan specifies: 15m, months 2023-10..2026-10,
108,192 bars/symbol, zero missing bars.

The importable Stratex tree is taken from --repo (default: the
repository this script ships in, resolved from the script's own
path — Stratex/rigorous_backtest/disc/ sits three levels below
the repo root; a git-archive extract of origin/main can be passed
explicitly instead). The Box Theory provenance record is read
from that same tree
(Stratex/rigorous_backtest/ig/box_theory_provenance.json).
Outputs go to --out (default ~/workspace/str-grid, outside the
repo tree): the cache lives at <out>/panel/ and the provenance
record is written to <out>/panel_provenance.json.

Verification (hard stops, nothing patched):
- per symbol: rows == 108,192; gap_audit.missing_bars == 0;
  first bar 2023-10-01T00:00Z; last bar 2026-10-31T23:45Z.
- per symbol: csv_sha256 must equal the Box Theory run's provenance
  (ig/box_theory_provenance.json on main) — the identical panel.

Modes:
  (default)      load with cache_dir=<out>/panel/ (write-capable
                 hosts); afterwards the cache CSV + sidecar are
                 checked to exist with nonzero size — a cache that
                 did not persist is reported as CACHE_NOT_PERSISTED
                 failure.
  --verify-only  load with cache_dir=None (pure fetch + verify in
                 memory) and print the provenance JSON to stdout.
                 This is the mode used in the Muse sandbox, whose
                 child processes cannot reliably write file content;
                 the printed provenance is then saved by the
                 coordinator's file tool.

Exit code 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Stratex/rigorous_backtest/disc/ sits three levels below the repo
# root, so the repository this script ships in is HERE.parents[2].
DEFAULT_REPO = HERE.parents[2]
# Panel outputs live outside the repo tree (see ../RUNBOOK.md).
DEFAULT_OUT = Path.home() / "workspace" / "str-grid"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
EXPECTED_ROWS = 108192
EXPECTED_FIRST = "2023-10-01T00:00:00+00:00"
EXPECTED_LAST = "2026-10-31T23:45:00+00:00"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=DEFAULT_REPO,
                    help="repository tree containing Stratex/ "
                         "(default: the repository this script "
                         "ships in, resolved from its own path)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output directory outside the repo tree; "
                         "the cache goes to <out>/panel/ and the "
                         "provenance record to "
                         "<out>/panel_provenance.json "
                         "(default: ~/workspace/str-grid)")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    repo = args.repo.expanduser()
    out = args.out.expanduser()
    if not (repo / "Stratex/rigorous_backtest/data_feed.py").is_file():
        print(f"ERROR: --repo {repo} does not contain "
              "Stratex/rigorous_backtest/data_feed.py", file=sys.stderr)
        return 2
    sys.path.insert(0, str(repo / "Stratex"))
    from rigorous_backtest.data_feed import load_dataset  # noqa: E402

    cache_dir = None if args.verify_only else out / "panel"

    box_prov = json.loads(
        (repo / "Stratex/rigorous_backtest/ig/box_theory_provenance.json")
        .read_text(encoding="utf-8"))
    box_syms = box_prov["symbols"]
    provenance = {"panel": "BTC/ETH/SOL (rd.common SYMBOLS)",
                  "timeframe": "15m",
                  "months": "2023-10..2026-10",
                  "source": "binance_vision_futures_um_monthly_klines via "
                            "rigorous_backtest.data_feed.load_dataset",
                  "symbols": {}}
    failures = []
    for sym in SYMBOLS:
        try:
            ds = load_dataset(sym, "15m", "2023-10", "2026-10",
                              cache_dir=cache_dir)
        except Exception as exc:  # loader hard-fails by design
            failures.append(f"{sym}: LOAD FAILED: {exc!r}")
            provenance["symbols"][sym] = {"status": "LOAD_FAILED",
                                          "error": repr(exc)}
            print(f"[FAIL] {sym}: load failed: {exc!r}", flush=True)
            continue
        m = ds.manifest
        ga = m["gap_audit"]
        entry = {"status": "OK", "rows": m["rows"],
                 "first_bar_utc": m["first_bar_utc"],
                 "last_bar_utc": m["last_bar_utc"],
                 "csv_sha256": m["csv_sha256"],
                 "missing_bars": ga["missing_bars"],
                 "expected_bars": ga["expected_bars"],
                 "n_gap_spans": len(ga["gap_spans"])}
        provenance["symbols"][sym] = entry
        problems = []
        if m["rows"] != EXPECTED_ROWS:
            problems.append(f"rows {m['rows']} != {EXPECTED_ROWS}")
        if ga["missing_bars"] != 0:
            problems.append(f"missing_bars {ga['missing_bars']} != 0")
        if m["first_bar_utc"] != EXPECTED_FIRST:
            problems.append(f"first {m['first_bar_utc']} != {EXPECTED_FIRST}")
        if m["last_bar_utc"] != EXPECTED_LAST:
            problems.append(f"last {m['last_bar_utc']} != {EXPECTED_LAST}")
        box_hash = box_syms.get(sym, {}).get("csv_sha256")
        if box_hash != m["csv_sha256"]:
            problems.append(
                f"csv_sha256 {m['csv_sha256']} != box provenance {box_hash}")
        if cache_dir is not None:
            csv_f = cache_dir / f"{sym}_15m_2023-10_2026-10.csv"
            side_f = csv_f.with_suffix(".csv.json")
            if not (csv_f.exists() and csv_f.stat().st_size > 0
                    and side_f.exists() and side_f.stat().st_size > 0):
                problems.append("CACHE_NOT_PERSISTED "
                                "(sandbox child-process write denial?)")
        if problems:
            failures.append(f"{sym}: " + "; ".join(problems))
            print(f"[FAIL] {sym}: " + "; ".join(problems), flush=True)
        else:
            print(f"[OK] {sym}: {m['rows']} rows, 0 missing, "
                  f"hash matches Box provenance", flush=True)
    if args.verify_only:
        print("PROVENANCE_JSON_BEGIN")
        print(json.dumps(provenance, indent=1))
        print("PROVENANCE_JSON_END")
    else:
        out.mkdir(parents=True, exist_ok=True)
        (out / "panel_provenance.json").write_text(
            json.dumps(provenance, indent=1), encoding="utf-8")
    if failures:
        print(f"\nPANEL VERIFICATION FAILED ({len(failures)}):", flush=True)
        for f in failures:
            print(" -", f, flush=True)
        return 1
    print(f"\nPANEL OK: {len(SYMBOLS)}/3 symbols, 108192 bars each, "
          "zero missing, all hashes match Box provenance.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
