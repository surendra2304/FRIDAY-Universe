"""fetch_fxsession_panel.py — stage the declared TASK-STR-RD-018
panel from the OANDA practice API (free; the forward venue itself).

Fetches M15 mid candles (price=M) for EUR_USD, GBP_USD, USD_JPY,
AUD_USD over [2023-01-01T00:00Z, 2026-11-01T00:00Z) by 5,000-candle
pagination chained on `from`, writes one CSV per instrument
(<SYMBOL>.csv: time,open,high,low,close,complete) plus
panel_provenance.json (per-file SHA-256, row counts, first/last
times, fetch metadata). No filling, no interpolation: whatever the
venue returns is what is staged; gaps are left for the engine's
tradeable-day rule to void mechanically.

The API key is read from --env-file (a .env containing
OANDA_API_KEY). It is never printed and never written anywhere.

Part of the declared run step — running this script is NOT the
backtest; it only stages data. (At declaration time only the
archive-depth probe was run: M15 reaches 2005-01-02 for all four
instruments.)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

INSTRUMENTS = {"EURUSD": "EUR_USD", "GBPUSD": "GBP_USD",
               "USDJPY": "USD_JPY", "AUDUSD": "AUD_USD"}
HOST = "https://api-fxpractice.oanda.com"
PAGE = 5000


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def read_token(env_file: Path) -> str:
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("OANDA_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OANDA_API_KEY not found in env file")


def fetch_page(token: str, instrument: str, frm: datetime) -> list[dict]:
    q = urllib.parse.urlencode({
        "granularity": "M15", "count": PAGE, "price": "M",
        "from": _rfc3339(frm)})
    url = f"{HOST}/v3/instruments/{instrument}/candles?{q}"
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept-Datetime-Format": "RFC3339"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r).get("candles", [])


def stage_instrument(token: str, instrument: str,
                     start: datetime, end: datetime) -> list[dict]:
    by_time: dict[str, dict] = {}
    frm = start
    while frm < end:
        page = fetch_page(token, instrument, frm)
        if not page:
            break
        for c in page:
            by_time[c["time"]] = c
        last = _parse(page[-1]["time"])
        nxt = last + timedelta(minutes=15)
        if nxt <= frm:
            break
        frm = nxt
    rows = [c for t, c in sorted(by_time.items()) if start <= _parse(t) < end]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start", default="2023-01-01T00:00:00Z")
    ap.add_argument("--end", default="2026-11-01T00:00:00Z")
    args = ap.parse_args()

    token = read_token(Path(args.env_file))
    start, end = _parse(args.start), _parse(args.end)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files_meta = {}
    for sym, inst in INSTRUMENTS.items():
        rows = stage_instrument(token, inst, start, end)
        path = out / f"{sym}.csv"
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "open", "high", "low", "close", "complete"])
            for c in rows:
                mid = c["mid"]
                w.writerow([c["time"], mid["o"], mid["h"], mid["l"],
                            mid["c"], str(bool(c["complete"])).lower()])
        raw = path.read_bytes()
        files_meta[path.name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows),
            "first": rows[0]["time"] if rows else None,
            "last": rows[-1]["time"] if rows else None,
        }
        print(f"{sym}: {len(rows)} bars "
              f"({files_meta[path.name]['first']} .. "
              f"{files_meta[path.name]['last']})")

    prov = {
        "task_id": "TASK-STR-RD-018",
        "source": f"{HOST} v3 candles, granularity M15, price=M",
        "span": [args.start, args.end],
        "fetched_at": _rfc3339(datetime.now(timezone.utc)),
        "files": files_meta,
    }
    (out / "panel_provenance.json").write_text(json.dumps(prov, indent=2))
    print("panel staged:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
