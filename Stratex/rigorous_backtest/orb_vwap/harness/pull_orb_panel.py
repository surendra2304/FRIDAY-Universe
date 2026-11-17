#!/usr/bin/env python3
"""Alpaca SIP panel pull for TASK-STR-DISC-004 (ORB/VWAP equity intraday).

Pulls the declared panel for the frozen 15-symbol universe:
Alpaca Market Data (Basic plan, $0), feed=sip, adjustment=split,
timeframe=15Min, 2023-01-01T00:00:00Z -> 2026-11-01T00:00:00Z (end
exclusive), regular-session bars only (NYSE calendar filter).

Discipline (mirrors the SRS pull tool, alpaca_data_pull.py):
  * Keys come from the ENVIRONMENT ONLY (ALPACA_API_KEY_ID /
    ALPACA_API_SECRET_KEY, APCA_ aliases accepted). Never read from
    files, never printed.
  * Exit 2 = keys not installed (the expected state until the SRS
    execution's install step lands).
  * Exit 3 = output directory inside a git tree (SIP licence: the
    raw panel is NEVER committed; only the provenance record is).
  * Exit 4 = API error.
  * Writes one CSV per symbol plus data_provenance_draft.json
    (per-symbol SHA-256 + counts) beside the panels. The verifier
    (verify_orb_panel.py) turns the draft into the frozen
    data_provenance.json; a panel whose hash later differs from the
    draft is a FAIL, not a re-pin.

Access proof (run time, after keys are installed): pull ONE
symbol-month into a scratch dir, e.g.
  python3 pull_orb_panel.py --out /path/proof --symbols AAPL \
      --start 2026-10-01T00:00:00Z --end 2026-11-01T00:00:00Z
and record the draft provenance in the run record.

Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nyse_calendar  # noqa: E402

ET = ZoneInfo("America/New_York")
API_BASE = "https://data.alpaca.markets/v2/stocks"
UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO",
            "TSLA", "AMD", "NFLX", "XOM", "BAC", "MU", "INTC", "PLTR"]
DEFAULT_START = "2023-01-01T00:00:00Z"
DEFAULT_END = "2026-11-01T00:00:00Z"


def keys_from_env() -> tuple[str, str] | None:
    kid = os.environ.get("ALPACA_API_KEY_ID") or os.environ.get("APCA_API_KEY_ID")
    sec = os.environ.get("ALPACA_API_SECRET_KEY") or \
        os.environ.get("APCA_API_SECRET_KEY")
    if kid and sec:
        return kid, sec
    return None


def inside_git_tree(path: Path) -> bool:
    p = path.resolve()
    while True:
        if (p / ".git").exists():
            return True
        if p.parent == p:
            return False
        p = p.parent


def fetch_bars(symbol: str, start: str, end: str,
               kid: str, sec: str) -> list[dict]:
    bars: list[dict] = []
    token = None
    while True:
        params = {"timeframe": "15Min", "start": start, "end": end,
                  "adjustment": "split", "feed": "sip", "sort": "asc",
                  "limit": 10000}
        if token:
            params["page_token"] = token
        url = f"{API_BASE}/{symbol}/bars?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "APCA-API-KEY-ID": kid, "APCA-API-SECRET-KEY": sec,
            "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — reported, exit 4
            print(f"API ERROR pulling {symbol}: {exc}", file=sys.stderr)
            sys.exit(4)
        bars.extend(payload.get("bars") or [])
        token = payload.get("next_page_token")
        if not token:
            return bars


def regular_session_only(raw_bars: list[dict]) -> list[dict]:
    """Keep exactly the bars whose ET start is an expected session
    bar-start per the NYSE calendar (drops pre/post-market bars)."""
    kept = []
    expected_cache: dict = {}
    for b in raw_bars:
        t_utc = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
        t_et = t_utc.astimezone(ET)
        day = t_et.date()
        if day not in expected_cache:
            expected_cache[day] = set(nyse_calendar.expected_bar_starts(day))
        if t_et.time() in expected_cache[day]:
            kept.append((t_utc, t_et, b))
    kept.sort(key=lambda x: x[0])
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="panel output directory")
    ap.add_argument("--symbols", nargs="*", default=UNIVERSE,
                    help="default: the frozen 15-symbol universe")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    args = ap.parse_args()

    keys = keys_from_env()
    if keys is None:
        print("KEYS NOT INSTALLED: ALPACA_API_KEY_ID / "
              "ALPACA_API_SECRET_KEY are not in the environment. "
              "Installation is step 1 of the SRS execution sequence; "
              "this family's pull waits for it. Not hunting for keys.",
              file=sys.stderr)
        return 2
    kid, sec = keys

    out = Path(args.out)
    if inside_git_tree(out):
        print(f"REFUSED: {out} is inside a git tree. The SIP panel is "
              "never committed (licence); only the provenance record is.",
              file=sys.stderr)
        return 3
    out.mkdir(parents=True, exist_ok=True)

    provenance: dict = {
        "task": "TASK-STR-DISC-004",
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": {"feed": "sip", "adjustment": "split",
                    "timeframe": "15Min", "start": args.start,
                    "end": args.end, "sort": "asc", "limit": 10000},
        "symbols": {},
    }
    for symbol in args.symbols:
        raw = fetch_bars(symbol, args.start, args.end, kid, sec)
        kept = regular_session_only(raw)
        fname = f"{symbol}_15min_sip_2023-01-01_2026-10-31.csv"
        fpath = out / fname
        sessions = set()
        with fpath.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "timestamp_et", "open", "high",
                        "low", "close", "volume", "trade_count", "vwap"])
            for t_utc, t_et, b in kept:
                sessions.add(t_et.date())
                w.writerow([t_utc.isoformat(), t_et.isoformat(),
                            b["o"], b["h"], b["l"], b["c"], b["v"],
                            b.get("n", ""), b.get("vw", "")])
        digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
        provenance["symbols"][symbol] = {
            "file": fname, "sha256": digest,
            "bars_raw": len(raw), "bars_kept": len(kept),
            "sessions": len(sessions)}
        print(f"{symbol}: raw={len(raw)} kept={len(kept)} "
              f"sessions={len(sessions)} sha256={digest[:12]}…")
    draft = out / "data_provenance_draft.json"
    draft.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(f"provenance draft -> {draft}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
