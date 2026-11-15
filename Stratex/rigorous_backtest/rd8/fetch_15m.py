"""Fetch provenanced 15m index series for TASK-STR-RD-008.

Source: Yahoo Finance chart API (the RD-002 Stage-A source for all
non-crypto series). 15m depth is hard-limited by the API to ~60 days;
that limit is disclosed in the declaration and caps 15m verdicts at
screening level.

Cache contract (identical to RD-002's): canonical CSV + sidecar JSON
manifest with csv_sha256, response_sha256, row count, null-OHLC drops
counted (never filled), first/last bar, and a gap audit. The runner
re-verifies the CSV hash at load.

Usage:
  python3 -m rigorous_backtest.rd8.fetch_15m --out-dir /path/to/cache15m
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}" \
        "?interval=15m&range=60d&includePrePost=false"
SERIES = {"SPX": "%5EGSPC", "NDX": "%5ENDX"}


def _fetch(url: str, attempts: int = 3) -> bytes:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - retried, then hard-fail
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed after {attempts} attempts: {last}")


def fetch_one(symbol: str, yahoo: str, out_dir: Path) -> dict:
    raw = _fetch(CHART.format(sym=yahoo))
    payload = json.loads(raw)
    result = payload["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]
    df = pd.DataFrame({"open": q["open"], "high": q["high"],
                       "low": q["low"], "close": q["close"],
                       "volume": q.get("volume")},
                      index=pd.to_datetime(ts, unit="s", utc=True))
    n_raw = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    dropped = n_raw - len(df)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df["volume"] = df["volume"].fillna(0.0)
    csv_path = out_dir / f"YH_{symbol}_15m.csv"
    buf = io.StringIO()
    df.to_csv(buf, index_label="ts")
    csv_bytes = buf.getvalue().encode()
    csv_path.write_bytes(csv_bytes)
    # gap audit: jumps > 45 minutes between consecutive bars
    spans = []
    idx = df.index
    for a, b in zip(idx[:-1], idx[1:]):
        gap_min = (b - a).total_seconds() / 60.0
        if gap_min > 45:
            spans.append({"after": a.isoformat(), "before": b.isoformat(),
                          "missing_bars": int(gap_min // 15) - 1})
    expected = int((idx[-1] - idx[0]).total_seconds() // 900) + 1
    manifest = {
        "source": "yahoo_finance_chart_api",
        "yahoo_symbol": result["meta"].get("symbol"),
        "symbol": symbol,
        "timeframe": "15m",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": int(len(df)),
        "null_ohlc_rows_dropped": int(dropped),
        "first_bar_utc": idx[0].isoformat(),
        "last_bar_utc": idx[-1].isoformat(),
        "gap_audit": {
            "expected_bars": expected,
            "actual_bars": int(len(df)),
            "missing_bars": expected - int(len(df)),
            "gap_spans": spans[:200],
            "grid_note": "gaps = inter-bar jumps > 45m (nights, weekends, "
                         "holidays and outages combined); the cash index "
                         "trades only the US regular session",
        },
    }
    csv_path.with_suffix(".csv.json").write_text(
        json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for symbol, yahoo in SERIES.items():
        m = fetch_one(symbol, yahoo, out_dir)
        print(f"[fetch15m] {symbol}: {m['rows']} bars "
              f"{m['first_bar_utc']} -> {m['last_bar_utc']} "
              f"dropped={m['null_ohlc_rows_dropped']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
