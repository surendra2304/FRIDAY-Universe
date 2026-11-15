#!/usr/bin/env python3
"""RD-006 data fetcher (crew's own implementation).

Downloads Binance Vision futures/um monthly 1h kline zips for CRYPTO30,
2022-01..2026-10, into ~/workspace/rd-006/data/. Records per-zip SHA-256
in a sidecar per symbol (same contract as the RD-002 cache) and
cross-checks every hash against the RD-002 sidecars where they overlap.
Leading 404 months (pre-listing) are tolerated; a 404 after the first
successful month is a hard failure. Gaps are counted, never filled.
"""
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
OUT = Path("/home/hatch/workspace/rd-006/data")
RD2_CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT",
           "TRXUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "UNIUSDT",
           "ETCUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
           "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT", "HBARUSDT",
           "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT"]
MONTHS = [(y, m) for y in range(2022, 2027) for m in range(1, 13)
          if (y, m) <= (2026, 10)]


def fetch_bytes(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rd006-fetcher"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # proxy flakiness: retry
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


def parse_zip(blob):
    zf = zipfile.ZipFile(io.BytesIO(blob))
    members = [n for n in zf.namelist() if n.endswith(".csv")]
    if len(members) != 1:
        raise RuntimeError(f"unexpected zip contents: {zf.namelist()}")
    raw = zf.read(members[0]).decode()
    rows = []
    for line in raw.splitlines():
        parts = line.split(",")
        try:
            t = int(parts[0])
        except (ValueError, IndexError):
            continue  # header row
        rows.append((t, float(parts[1]), float(parts[2]), float(parts[3]),
                     float(parts[4]), float(parts[5])))
    return rows


def write_with_retry(fn, tries=5):
    last = None
    for i in range(tries):
        try:
            fn()
            return
        except OSError as e:
            last = e
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(f"write failed after retries: {last}")


def fetch_symbol(sym):
    csv_path = OUT / f"{sym}_1h.csv"
    side_path = OUT / f"{sym}_1h.csv.json"
    if csv_path.exists() and side_path.exists():
        print(f"[skip] {sym} cached", flush=True)
        return json.loads(side_path.read_text())
    all_rows, hashes = [], {}
    started = False
    for (y, m) in MONTHS:
        fname = f"{sym}-1h-{y:04d}-{m:02d}.zip"
        url = f"{BASE}/{sym}/1h/{fname}"
        blob = fetch_bytes(url)
        if blob is None:
            if started:
                raise RuntimeError(f"404 after start: {url}")
            continue
        started = True
        hashes[fname] = hashlib.sha256(blob).hexdigest()
        all_rows.extend(parse_zip(blob))
    df = pd.DataFrame(all_rows, columns=["open_time", "open", "high", "low",
                                         "close", "volume"])
    df = df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    expected = int((df["open_time"].iloc[-1] - df["open_time"].iloc[0]) // 3600000) + 1
    sidecar = {
        "source": "binance_vision_futures_um_monthly_klines",
        "archive_base": BASE,
        "symbol": sym, "timeframe": "1h", "months": "2022-01..2026-10",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip_sha256": hashes,
        "rows": int(len(df)),
        "first_bar_utc": datetime.fromtimestamp(df["open_time"].iloc[0] / 1000,
                                                timezone.utc).isoformat(),
        "last_bar_utc": datetime.fromtimestamp(df["open_time"].iloc[-1] / 1000,
                                               timezone.utc).isoformat(),
        "missing_bars_in_span": int(expected - len(df)),
    }
    write_with_retry(lambda: df.to_csv(csv_path, index=False))
    write_with_retry(lambda: side_path.write_text(json.dumps(sidecar, indent=1)))
    print(f"[done] {sym}: {len(df)} rows, missing {sidecar['missing_bars_in_span']}",
          flush=True)
    return sidecar


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:] or SYMBOLS
    sidecars = {}
    for sym in only:
        sidecars[sym] = fetch_symbol(sym)
    # Cross-check zip hashes against RD-002 sidecars.
    report = {}
    for sym, sc in sidecars.items():
        rd2_path = RD2_CACHE / f"{sym}_1h_2022-01_2026-10.csv.json"
        if not rd2_path.exists():
            report[sym] = {"rd2_sidecar": "absent"}
            continue
        rd2 = json.loads(rd2_path.read_text())
        mine, theirs = sc["zip_sha256"], rd2.get("zip_sha256", {})
        common = set(mine) & set(theirs)
        mismatches = [f for f in common if mine[f] != theirs[f]]
        report[sym] = {"common_zips": len(common),
                       "hash_mismatches": mismatches,
                       "rows_mine": sc["rows"], "rows_rd2": rd2.get("rows")}
        print(f"[xcheck] {sym}: {len(common)} common zips, "
              f"{len(mismatches)} mismatches, rows mine={sc['rows']} rd2={rd2.get('rows')}",
              flush=True)
    write_with_retry(lambda: (OUT / "crosscheck_rd2.json").write_text(
        json.dumps(report, indent=1)))
    bad = {s: r for s, r in report.items() if r.get("hash_mismatches")}
    print("CROSSCHECK:", "ALL MATCH" if not bad else f"MISMATCHES: {bad}")


if __name__ == "__main__":
    main()
