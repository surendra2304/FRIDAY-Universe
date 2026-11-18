"""Build a provenance-verified stream store from research records.

Usage (from the Stratex directory):

    python3 -m self_experiments.export_stream_store \
        --rows-dir ~/workspace/str-rd2/results_full_backup \
        --streams streams_spec.json \
        --out <store_dir>

streams_spec.json declares the streams to export:

    [{"row": "bollinger_trend__p50_sd2.0__crypto30__1d.json",
      "admission": "FORWARD_TEST", "round": "TASK-STR-RD-002"}, ...]

For every declared stream the exporter derives the stored form from
the row file's own per-trade list (fold assignment by ENTRY time in
[oos_start, oos_end) — the harness's convention) and ASSERTS the
derivation against the record before writing anything:

- per-fold trades and wins reproduce the recorded per_fold EXACTLY;
- per-fold expectancy and PF reproduce within 1e-6;
- the holdout (OOS-era trades on the recorded untouched-symbol
  subset) reproduces the recorded untouched trades/expectancy;
- the recomputed t-stat / one-sided p reproduce the recorded
  trade_stats within 1e-3 / 1e-5.

A stream that fails any assertion is refused — its stored form could
not be reconciled with its judged record, so it never enters a store
the loop will judge on. The manifest records the sha256 of every
source row file and every written stream file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from .catalogue import FAMILY_CLUSTERS
from .store import ADMISSION_CLASSES

ROW_SUBDIRS = ("grid_rows", "gov_rows", "disc_rows", "combo_rows")


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _find_row(rows_dir: Path, name: str) -> Path:
    for sub in ROW_SUBDIRS:
        candidate = rows_dir / sub / name
        if candidate.exists():
            return candidate
    direct = rows_dir / name
    if direct.exists():
        return direct
    raise FileNotFoundError(f"row file {name} not found under {rows_dir}")


def _fold_metrics(returns: list[float]) -> tuple[int, int, float, float]:
    trades = len(returns)
    wins = sum(1 for r in returns if r > 0)
    expectancy = statistics.fmean(returns) if returns else 0.0
    gp = sum(r for r in returns if r > 0)
    gl = -sum(r for r in returns if r < 0)
    pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return trades, wins, expectancy, pf


def derive_stream(row_path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Derive + verify one stream's stored form from its row file."""
    raw = json.loads(row_path.read_text(encoding="utf-8"))
    family = str(raw.get("family", ""))
    variant = str(raw.get("variant", ""))
    panel = str(raw.get("panel", ""))
    timeframe = str(raw.get("timeframe", ""))
    stream_id = f"{family}/{variant}@{panel}/{timeframe}"
    per_fold = raw["report"]["per_fold"]
    trades = raw["trades"]

    folds: dict[str, list[float]] = {}
    fold_windows: dict[str, list[str]] = {}
    oos_returns: list[float] = []
    for fold, recorded in sorted(per_fold.items()):
        lo, hi = recorded["oos_start"], recorded["oos_end"]
        fold_windows[fold] = [lo, hi]
        selected = [
            float(t["net_return"])
            for t in trades
            if lo <= str(t["entry_time"])[:10] < hi
        ]
        folds[fold] = selected
        oos_returns.extend(selected)
        d_trades, d_wins, d_exp, d_pf = _fold_metrics(selected)
        if d_trades != int(recorded["trades"]) or d_wins != int(recorded["wins"]):
            raise AssertionError(
                f"{stream_id} fold {fold}: derived trades/wins "
                f"{d_trades}/{d_wins} != recorded "
                f"{recorded['trades']}/{recorded['wins']}"
            )
        if abs(d_exp - float(recorded["expectancy_net"])) > 1e-6:
            raise AssertionError(
                f"{stream_id} fold {fold}: derived expectancy {d_exp} "
                f"!= recorded {recorded['expectancy_net']}"
            )
        recorded_pf = float(recorded["profit_factor_net"])
        if math.isfinite(recorded_pf) and abs(d_pf - recorded_pf) > 1e-6:
            raise AssertionError(
                f"{stream_id} fold {fold}: derived PF {d_pf} != "
                f"recorded {recorded_pf}"
            )

    # Holdout: OOS-era trades on the recorded untouched-symbol subset.
    holdout_block: dict[str, Any] | None = None
    holdout = raw.get("holdout") or {}
    untouched = set(holdout.get("untouched_subset") or [])
    if untouched and holdout.get("untouched_trades") is not None:
        lo = min(w[0] for w in fold_windows.values())
        hi = max(w[1] for w in fold_windows.values())
        selected = [
            float(t["net_return"])
            for t in trades
            if lo <= str(t["entry_time"])[:10] < hi
            and t["symbol"] in untouched
        ]
        if len(selected) != int(holdout["untouched_trades"]):
            raise AssertionError(
                f"{stream_id} holdout: derived {len(selected)} trades "
                f"!= recorded {holdout['untouched_trades']}"
            )
        derived_exp = statistics.fmean(selected) if selected else 0.0
        if abs(derived_exp - float(holdout["untouched_expectancy"])) > 1e-6:
            raise AssertionError(
                f"{stream_id} holdout: derived expectancy {derived_exp} "
                f"!= recorded {holdout['untouched_expectancy']}"
            )
        holdout_block = {
            "trades": len(selected),
            "expectancy": derived_exp,
            "passes": bool(holdout.get("passes")),
        }

    # Significance construction check against the recorded trade_stats.
    stats_block = raw.get("trade_stats") or {}
    if stats_block.get("t_stat") is not None and len(oos_returns) >= 2:
        mean = statistics.fmean(oos_returns)
        sd = statistics.stdev(oos_returns)
        t_stat = mean / (sd / math.sqrt(len(oos_returns))) if sd > 0 else 0.0
        p = 0.5 * math.erfc(t_stat / math.sqrt(2.0))
        if abs(t_stat - float(stats_block["t_stat"])) > 1e-3:
            raise AssertionError(
                f"{stream_id}: derived t {t_stat} != recorded "
                f"{stats_block['t_stat']}"
            )
        if abs(p - float(stats_block["p_one_sided"])) > 1e-5:
            raise AssertionError(
                f"{stream_id}: derived p {p} != recorded "
                f"{stats_block['p_one_sided']}"
            )

    total_trades, _, pooled_exp, pooled_pf = _fold_metrics(oos_returns)
    positive_folds = sum(
        1
        for fold in folds
        if folds[fold] and statistics.fmean(folds[fold]) > 0
    )
    admission = str(spec.get("admission", ""))
    if admission not in ADMISSION_CLASSES:
        raise ValueError(
            f"{stream_id}: admission {admission!r} not in {ADMISSION_CLASSES}"
        )
    raw_costs = raw.get("costs_rt_bps", 16.0)
    if isinstance(raw_costs, dict):
        # Per-symbol cost map in the grid rows; the stored form keeps
        # the common value, or the distinct values if they differ.
        distinct = sorted({float(v) for v in raw_costs.values()})
        costs_value: float | list[float] = (
            distinct[0] if len(distinct) == 1 else distinct
        )
    else:
        costs_value = float(raw_costs)
    return {
        "stream_id": stream_id,
        "family": family,
        "variant": variant,
        "panel": panel,
        "timeframe": timeframe,
        "cluster": FAMILY_CLUSTERS.get(family, "other"),
        "admission": admission,
        "costs_rt_bps": costs_value,
        "folds": folds,
        "fold_windows": fold_windows,
        "holdout": holdout_block,
        "recorded_trades": total_trades,
        "recorded_expectancy": pooled_exp,
        "recorded_pf": pooled_pf,
        "recorded_positive_folds": positive_folds,
    }


def build_store(rows_dir: Path, spec_path: Path, out_dir: Path) -> dict[str, Any]:
    specs = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "streams").mkdir(exist_ok=True)
    manifest: dict[str, Any] = {
        "owner": "stratex_self_experiments",
        "streams": {},
    }
    for spec in specs:
        row_path = _find_row(rows_dir, str(spec["row"]))
        stream = derive_stream(row_path, spec)
        source_sha = _sha256_bytes(row_path.read_bytes())
        stream["source_record"] = {
            "file": str(spec["row"]),
            "sha256": source_sha,
            "round": str(spec.get("round", "TASK-STR-RD-002")),
        }
        slug = (
            stream["stream_id"]
            .replace("/", "__")
            .replace("@", "__at__")
        )
        rel = f"streams/{slug}.json"
        blob = json.dumps(stream, indent=1).encode("utf-8")
        (out_dir / rel).write_bytes(blob)
        manifest["streams"][stream["stream_id"]] = {
            "file": rel,
            "sha256": _sha256_bytes(blob),
            "source_record": stream["source_record"],
        }
        print(
            f"exported {stream['stream_id']}: {stream['recorded_trades']} "
            f"OOS trades, PF {stream['recorded_pf']:.4f}, "
            f"admission {stream['admission']}"
        )
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-dir", required=True, type=Path)
    parser.add_argument("--streams", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    build_store(args.rows_dir, args.streams, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
