"""Stage the declared order-flow panel (TASK-STR-RD-021 run-prep tool).

Downloads the Binance Vision futures/um monthly aggTrades archives
for the frozen 10-symbol universe (2023-10..2026-10), aggregates the
prints STREAMING into bars on the kline grid at 15m and 1h (prints
are never held in memory wholesale — a measured in-memory attempt
on one BTC month was OOM-killed), joins the flow onto klines loaded
through the programme's verified loader (data_feed.load_dataset),
and writes canonical per-symbol bar CSVs plus panel_provenance.json.

Declaration rules enforced here:
- per-zip SHA-256 recorded for every archive;
- a symbol-month whose prints do not cover a traded kline bar
  (kline volume > 0 but no aggTrades bucket) marks the WHOLE symbol
  EXCLUDED (all-or-nothing), with the reason in the provenance;
- excluded symbols get no CSVs in the panel dir;
- gaps are reported, never filled.
The panel dir must NOT be inside a git tree (panel data never
enters the repo) — enforced by a .git walk + rev-parse check.

This script performs NO signal computation and NO simulation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orderflow import aggregate_aggtrades  # the pinned harness aggregator

UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "TRXUSDT", "LTCUSDT", "LINKUSDT"]
MONTHS_START, MONTHS_END = "2023-10", "2026-10"
ARCHIVE_BASE = "https://data.binance.vision/data/futures/um/monthly/aggTrades"
SOURCE_NAME = "binance_vision_futures_um_monthly_aggTrades"
TIMEFRAMES = ("15m", "1h")


def month_range(start: str, end: str):
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out, y, m = [], sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def refuse_inside_git(path: Path) -> None:
    p = path.resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            raise SystemExit(f"REFUSING: {p} is inside a git tree ({parent})")
    try:
        r = subprocess.run(["git", "-C", str(p), "rev-parse", "--git-dir"],
                           capture_output=True, timeout=10)
        if r.returncode == 0:
            raise SystemExit(f"REFUSING: {p} is inside a git working tree")
    except FileNotFoundError:
        pass


def fetch_zip(symbol: str, ym: str, scratch: Path) -> tuple[Path, str, int]:
    dest = scratch / f"{symbol}-aggTrades-{ym}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        h = hashlib.sha256()
        with open(dest, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return dest, h.hexdigest(), dest.stat().st_size
    url = f"{ARCHIVE_BASE}/{symbol}/{symbol}-aggTrades-{ym}.zip"
    h = hashlib.sha256()
    size = 0
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            f.write(chunk)
            size += len(chunk)
    return dest, h.hexdigest(), size


def rows_from_zip(zip_path: Path):
    """Yield (transact_time_ms, quantity, is_buyer_maker) per print,
    streaming. Raises ValueError on a malformed row."""
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8")
            header = text.readline()
            if not header.startswith("agg_trade_id"):
                raise ValueError(f"unexpected header: {header!r}")
            for line in text:
                line = line.strip()
                if not line:
                    continue
                p = line.split(",")
                yield int(p[5]), float(p[2]), p[6].strip().lower() == "true"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="checkout of origin/main (data_feed loader)")
    ap.add_argument("--out", required=True, help="panel output dir")
    ap.add_argument("--scratch", required=True,
                    help="zip scratch dir (may hold ~40 GB at peak)")
    ap.add_argument("--kline-cache", default=None,
                    help="data_feed cache dir for klines")
    ap.add_argument("--keep-zips", action="store_true",
                    help="keep monthly zips after aggregation "
                         "(default: delete each after both passes)")
    args = ap.parse_args()

    out = Path(args.out)
    refuse_inside_git(out)
    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(Path(args.repo) / "Stratex"))
    from rigorous_backtest.data_feed import load_dataset

    months = month_range(MONTHS_START, MONTHS_END)
    provenance = {
        "panel": "orderflow_top10",
        "source": SOURCE_NAME,
        "span": f"{MONTHS_START}..{MONTHS_END}",
        "staging_script": Path(__file__).name,
        "symbols": {},
    }

    for sym in UNIVERSE:
        print(f"=== {sym} ===", flush=True)
        flow = {tf: {} for tf in TIMEFRAMES}
        month_recs = []
        excluded_reason = None
        for ym in months:
            try:
                zp, zhash, zsize = fetch_zip(sym, ym, scratch)
            except Exception as exc:  # noqa: BLE001 - recorded, symbol excluded
                excluded_reason = f"fetch failed {ym}: {exc}"
                print(f"  {ym}: FETCH FAILED {exc}", flush=True)
                break
            n_rows = 0
            for tf in TIMEFRAMES:
                agg = aggregate_aggtrades(rows_from_zip(zp), tf)
                if tf == "15m":
                    n_rows = sum(c["nprints"] for c in agg.values())
                dest = flow[tf]
                for b, cell in agg.items():
                    cur = dest.get(b)
                    if cur is None:
                        dest[b] = dict(cell)
                    else:
                        cur["delta"] += cell["delta"]
                        cur["qty"] += cell["qty"]
                        cur["nprints"] += cell["nprints"]
            month_recs.append({"month": ym, "zip_sha256": zhash,
                               "zip_bytes": zsize, "rows": n_rows})
            print(f"  {ym}: {n_rows} prints, zip {zsize} bytes", flush=True)
            if not args.keep_zips:
                zp.unlink()
        sym_rec = {"status": "OK", "months": month_recs, "timeframes": {}}
        if excluded_reason is not None:
            sym_rec["status"] = "EXCLUDED"
            sym_rec["reason"] = excluded_reason
            provenance["symbols"][sym] = sym_rec
            continue

        for tf in TIMEFRAMES:
            ds = load_dataset(sym, tf, MONTHS_START, MONTHS_END,
                              cache_dir=Path(args.kline_cache) if args.kline_cache else None)
            m = ds.manifest
            ga = m["gap_audit"]
            mismatches = 0
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["t", "o", "h", "l", "c", "delta", "qty", "nprints"])
            idx = ds.df.index
            vols = ds.df["volume"]
            for i, (o, h, l, c) in enumerate(zip(
                    ds.df["open"], ds.df["high"], ds.df["low"], ds.df["close"])):
                t_ms = int(idx[i].timestamp() * 1000)
                cell = flow[tf].get(t_ms)
                if cell is None:
                    if float(vols.iloc[i]) > 0:
                        mismatches += 1
                    delta, qty, npr = 0.0, 0.0, 0
                else:
                    delta, qty, npr = cell["delta"], cell["qty"], cell["nprints"]
                w.writerow([t_ms, repr(float(o)), repr(float(h)),
                            repr(float(l)), repr(float(c)),
                            repr(float(delta)), repr(float(qty)), npr])
            if mismatches:
                sym_rec["status"] = "EXCLUDED"
                sym_rec["reason"] = (f"{tf}: {mismatches} traded kline bars "
                                     f"with no aggTrades bucket")
                print(f"  {sym} {tf}: EXCLUDED — {sym_rec['reason']}",
                      flush=True)
                break
            payload = buf.getvalue().encode("utf-8")
            csv_name = f"{sym}_{tf}.csv"
            (out / csv_name).write_bytes(payload)
            sym_rec["timeframes"][tf] = {
                "csv_sha256": hashlib.sha256(payload).hexdigest(),
                "rows": int(m["rows"]),
                "kline_csv_sha256": m["csv_sha256"],
                "gap_missing_bars": ga["missing_bars"],
                "first_bar_utc": m["first_bar_utc"],
                "last_bar_utc": m["last_bar_utc"],
            }
            print(f"  {sym} {tf}: staged {m['rows']} bars "
                  f"(kline missing {ga['missing_bars']})", flush=True)
        provenance["symbols"][sym] = sym_rec

    (out / "panel_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")
    ok = [s for s, r in provenance["symbols"].items() if r["status"] == "OK"]
    print(f"STAGED: {len(ok)}/10 symbols OK -> {out}/panel_provenance.json",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
