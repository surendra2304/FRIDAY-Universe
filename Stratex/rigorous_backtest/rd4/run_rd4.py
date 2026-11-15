"""RD-004 runner: the 32 pre-declared vol-regime trend cells.

This module is the monolithic reference implementation and the home of
the shared helpers (resample_2h, retry-hardened writers) used by the
staged pipeline. The JUDGED execution ran staged — run_symbol.py
(per-symbol fragments) -> assemble.py (per-config rows) -> wf.py
(procedure rows) -> synth4.py — because this VM intermittently
EPERM-blocks file writes from long-running Python processes (it killed
two monolithic attempts at the write stage and silently ate cache
sidecars during data fetch; all incidents disclosed in
RESULTS_RD4.md). The staged stages call the identical functions in
the identical order, so the numbers are the monolithic numbers.

  python3 -m rigorous_backtest.rd4.run_rd4 \
      --cache-dir /home/hatch/workspace/rd-004/cache15m \
      --coverage /home/hatch/workspace/rd-004/coverage.json \
      --out-dir results_rd4

One cell = one trial. Rows checkpoint per cell (existing rows skipped).
Trades are stored full-period (IS + OOS) as compact CSVs; judgement is
OOS-only via stats2, computed in synth4.py. Every cell is also run at
2x costs (sensitivity). Research only.
"""
from __future__ import annotations

import argparse, gzip, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

from ..data_feed import Dataset, load_dataset
from ..rd.common import atr, dump_json, trades_to_json  # noqa: F401
from ..rd.fastsim import simulate_entries
from ..simulator import Trade, trade_metrics
from ..walkforward import FOLDS, trades_in_window
from ..rd2.costs2 import CRYPTO, double
from ..rd2.families2 import BR24
from ..rd2.panels import CRYPTO30
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_rd4 import MODES, SIGNALS, apply_mode, base_entries, \
    regime_rank_by_bar
from .sim_rd4 import simulate_scaled

STANDARD = [fid for fid, _, _ in FOLDS]


def resample_2h(ds: Dataset) -> Dataset:
    """2h derivation with the harness resample rule (complete buckets
    only, UTC-aligned, parent hash recorded). Local because the harness
    _TF_MINUTES table has no 2h entry; the rule is byte-identical."""
    rule = "120min"
    agg = ds.df.resample(rule, origin="start_day").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"})
    counts = ds.df["close"].resample(rule, origin="start_day").count()
    agg = agg[counts == 8].dropna()
    # gap audit with the 120-minute step (data_feed.gap_audit's table has
    # no 2h entry); same shape and semantics as the harness audit.
    if len(agg):
        step = pd.Timedelta(minutes=120)
        expected = int((agg.index[-1] - agg.index[0]) / step) + 1
        missing = expected - len(agg)
        spans = []
        if missing > 0:
            diffs = agg.index.to_series().diff()
            for ts in diffs[diffs > step].index:
                prev = agg.index[agg.index.get_loc(ts) - 1]
                spans.append({"after": prev.isoformat(),
                              "before": ts.isoformat(),
                              "missing_bars": int((ts - prev) / step) - 1})
        audit = {"expected_bars": expected, "actual_bars": len(agg),
                 "missing_bars": missing, "gap_spans": spans[:50]}
    else:
        audit = {"expected_bars": 0, "actual_bars": 0, "missing_bars": 0,
                 "gap_spans": []}
    manifest = {
        "source": "resampled_from:binance_vision_futures_um_monthly_klines",
        "derived_from_csv_sha256": ds.manifest.get("csv_sha256"),
        "derived_from": ds.key, "symbol": ds.symbol, "timeframe": "2h",
        "resample_rule": "120min origin=start_day, complete buckets only",
        "fetched_at_utc": ds.manifest.get("fetched_at_utc"),
        "rows": int(len(agg)),
        "first_bar_utc": agg.index[0].isoformat() if len(agg) else None,
        "last_bar_utc": agg.index[-1].isoformat() if len(agg) else None,
        "gap_audit": audit,
    }
    return Dataset(ds.symbol, "2h", agg, manifest)


def _tuples(trades: list[Trade]) -> list[tuple]:
    return [(t.symbol, t.entry_time.isoformat(), t.exit_time.isoformat(),
             t.side, t.net_return, t.exit_reason) for t in trades]


def _trades(tuples: list[tuple]) -> list[Trade]:
    return [Trade(s, pd.Timestamp(e), pd.Timestamp(x), side, 0.0, 0.0, nr, r)
            for (s, e, x, side, nr, r) in tuples]


def _retry_write(path: Path, write_fn, attempts: int = 40) -> None:
    """Write via tmp file + rename, retrying PermissionError: this VM
    episodically returns EPERM on writes from Python processes for
    minutes at a time (observed killing cache sidecars, two monolithic
    run attempts at the write stage, and fragment writes). Patience
    here rides out an episode; callers are checkpointed per unit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    last: Exception | None = None
    for k in range(attempts):
        try:
            write_fn(tmp)
            tmp.replace(path)
            return
        except PermissionError as exc:  # noqa: PERF203 - deliberate retry
            last = exc
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(min(20.0, 2.0 * (k + 1)))
    raise PermissionError(f"write to {path} blocked after {attempts} "
                          f"retries: {last}")


def _dump_json_retry(path: Path, payload) -> None:
    def _w(tmp: Path) -> None:
        tmp.write_text(json.dumps(payload, indent=2, default=str),
                       encoding="utf-8")
    _retry_write(path, _w)


def _write_trades_csv(path: Path, tuples: list[tuple]) -> None:
    def _w(tmp: Path) -> None:
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            fh.write("symbol,entry_time,exit_time,side,net_return,"
                     "exit_reason\n")
            for s, e, x, side, nr, r in tuples:
                fh.write(f"{s},{e},{x},{side},{nr!r},{r}\n")
    _retry_write(path, _w)


def _oos_trades(trades: list[Trade]) -> list[Trade]:
    pooled: list[Trade] = []
    for _fid, s, e in FOLDS:
        pooled.extend(trades_in_window(trades, s, e))
    return pooled


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tfs", default="15m,2h")
    args = ap.parse_args()
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    coverage = json.loads(Path(args.coverage).read_text())
    symbols = [s for s in CRYPTO30
               if coverage.get(s, {}).get("status") == "OK"]
    print(f"panel: {len(symbols)} symbols covered", flush=True)
    costs2x = double(CRYPTO)
    probe_done = (out_dir / "engine_consistency.json").exists()

    for tf in [t.strip() for t in args.tfs.split(",") if t.strip()]:
        # acc[(signal, mode)] = {"1x": [tuples], "2x": [tuples]}
        acc: dict[tuple[str, str], dict[str, list]] = {
            (sig, mode): {"1x": [], "2x": []}
            for sig in SIGNALS for mode in MODES}
        pending = [(sig, mode) for (sig, mode) in acc
                   if not (rows_dir / f"{tf}_{sig}_{mode}.json").exists()]
        if not pending:
            print(f"{tf}: all rows exist, skipping", flush=True)
            continue
        for sym in symbols:
            start = coverage[sym]["start_month"]
            ds15 = load_dataset(sym, "15m", start, "2026-10", cache_dir)
            ds = ds15 if tf == "15m" else resample_2h(ds15)
            a = atr(ds.df, 14).to_numpy()
            rank = regime_rank_by_bar(ds.df)
            for sig in SIGNALS:
                base = base_entries(ds.df, sig)
                for mode in MODES:
                    if (sig, mode) not in pending:
                        continue
                    entries = apply_mode(base, mode, rank)
                    t1 = simulate_scaled(ds.df, entries, a, sym, CRYPTO)
                    t2 = simulate_scaled(ds.df, entries, a, sym, costs2x)
                    acc[(sig, mode)]["1x"].extend(_tuples(t1))
                    acc[(sig, mode)]["2x"].extend(_tuples(t2))
                    if not probe_done and tf == "15m" and sig == "don20" \
                            and mode == "base":
                        ref = simulate_entries(
                            ds.df, [(i, s) for (i, s, _f) in entries], a,
                            BR24, sym, CRYPTO)
                        mine = [(t.entry_time, t.exit_time, t.net_return)
                                for t in t1]
                        theirs = [(t.entry_time, t.exit_time, t.net_return)
                                  for t in ref]
                        ok = mine == theirs
                        _dump_json_retry(out_dir / "engine_consistency.json", {
                            "probe": f"{sym} 15m don20 base: simulate_scaled"
                                     " (f=1) vs fastsim.simulate_entries"
                                     " BR24",
                            "trades": len(mine), "identical": ok})
                        print(f"engine probe: identical={ok} "
                              f"({len(mine)} trades)", flush=True)
                        if not ok:
                            print("ENGINE MISMATCH — aborting", flush=True)
                            return 1
                        probe_done = True
            print(f"{tf} {sym}: done", flush=True)
        for (sig, mode) in pending:
            t1 = _trades(acc[(sig, mode)]["1x"])
            t2 = _trades(acc[(sig, mode)]["2x"])
            rep = fold_report(t1, STANDARD, symbols)
            rep2 = fold_report(t2, STANDARD, symbols)
            ho = holdout2(rep, symbols)
            row = {
                "family": "vol_regime_trend", "signal": sig, "mode": mode,
                "variant": f"{sig}_{mode}", "panel": "crypto30",
                "timeframe": tf, "status": "EVALUATED",
                "costs": CRYPTO.describe(),
                "report": rep, "holdout": ho, "bar": check_bar2(rep, ho),
                "trade_stats": trade_stats(_oos_trades(t1)),
                "metrics_2x": {"pooled_oos": rep2["pooled_oos"],
                               "per_fold": rep2["per_fold"]},
                "full_period": trade_metrics(t1),
            }
            _dump_json_retry(rows_dir / f"{tf}_{sig}_{mode}.json", row)
            _write_trades_csv(rows_dir / "trades" /
                              f"{tf}_{sig}_{mode}_1x.csv.gz",
                              acc[(sig, mode)]["1x"])
            _write_trades_csv(rows_dir / "trades" /
                              f"{tf}_{sig}_{mode}_2x.csv.gz",
                              acc[(sig, mode)]["2x"])
            po = rep["pooled_oos"]
            print(f"{tf} {sig}_{mode}: OOS trades={po['trades']} "
                  f"exp={po['expectancy_net']} PF={po['profit_factor_net']}",
                  flush=True)
    print("RUN COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
