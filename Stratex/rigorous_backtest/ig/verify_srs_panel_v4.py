#!/usr/bin/env python3
"""Five-point verification of the SRS TSLA panel (PROVENANCE.md §3.5)
— V4 VERIFIER, frozen under DATA-SPEC ADDENDUM V4.

This file is verify_srs_panel.py (the frozen v3 verifier, SHA-256
6bb5f922db281d56550429677c696536f924ecd6d432749a4ceddf2674048e11)
with EXACTLY ONE change: the CLOSE leg of check 4, re-founded on the
SIP tick tape's official-close print per addendum v4 Rule R1b (see
cross_source_check below). Checks 1, 2, 3 and 5, check 4's sampler,
its open/high/low legs, all tolerances, the >= 10-compared rule and
the NOT_RUN semantics are byte-identical logic to the v3 verifier.
The v3 verifier itself is untouched and remains the verifier of
record for the v3 gate attempt (which stopped at check 4).

Runs BEFORE any backtest. The panel is judged, not trusted:

  1. Gap audit      — every NYSE session in 2023-01-01..2026-10-31 has
                      exactly its expected bars (26 full / 10 early-close),
                      at exactly the expected bar-starts; no bars on
                      non-sessions; no duplicates. Expected total for the
                      declared panel: 961 sessions / 24,842 bars.
  2. Feed check     — median daily volume must be consolidated-scale.
                      TSLA trades tens of millions of shares/day on the
                      SIP tape; an IEX-only feed (~2-3% of volume) would
                      show a median around 1.5-3M. PASS: median >= 10M.
  3. Split check    — no overnight price ratio in the split bands
                      [2.70, 3.30] or [0.303, 0.367] (a missed 3-for-1
                      would appear there). Extreme non-split overnight
                      moves (>50%) are listed as findings to eyeball.
  4. Cross-source   — >= 10 sampled sessions spread across the folds,
                      session OHL compared against an independent
                      source file (--cross-source CSV with columns
                      date,open,high,low,close — under addendum v3,
                      Yahoo Finance daily). Highs/lows must match
                      within $0.05 on every sampled session. The CLOSE
                      leg (addendum v4, Rule R1b) compares the
                      cross-source close against the SIP feed's own
                      official close for the session: the price of the
                      trade carrying condition 'M' (Market Center
                      Official Closing Price) on the listing exchange
                      (Alpaca exchange code 'Q', Nasdaq) with ET
                      timestamp in [scheduled close, +1 minute).
                      Exactly one such trade must exist — zero or
                      more than one is a finding — and its price must
                      match the cross-source close within $0.02.
                      The panel's own last-bar close is a pre-auction
                      trade by construction and is NOT the official
                      close; it is recorded in the sample table
                      (panel_close, auction_minus_panel), never
                      compared. Tick data comes from --ticks-dir
                      (<session>.json files, Alpaca trades format) or
                      --pull-ticks (fresh pull, feed=sip). Without
                      --cross-source, or without a tick source, this
                      check is NOT_RUN and the overall verdict is
                      INCOMPLETE, never PASS — an unrun check is not a
                      passed check.
  5. Freeze         — SHA-256 of the panel file is computed and written,
                      with the full request provenance, into
                      data_provenance.json (the COMMITTABLE record; the
                      panel itself must never be committed). If a
                      download-time provenance draft sits beside the
                      panel, its hash must match — a changed panel is
                      a FAIL, not a re-pin.

Overall verdict is PASS only if all five checks PASS.
Exit codes: 0 = PASS · 5 = FAIL or INCOMPLETE.

Usage:
  python3 verify_srs_panel_v4.py --panel /path/outside/git/TSLA_15min_sip_2023-01-01_2026-10-31.csv \
      --cross-source /path/tsla_yahoo_daily_transformed.csv \
      (--ticks-dir /path/ticks | --pull-ticks) \
      [--provenance-out ~/workspace/.../data_provenance.json]   # committable copy for the run PR

  --pull-ticks reads the Alpaca keys from the environment
  (APCA_API_KEY_ID / APCA_API_SECRET_KEY, or ALPACA_API_KEY_ID /
  ALPACA_API_SECRET_KEY — the installed SRS channel). Like the v3
  verifier, this file expects the pinned nyse_calendar.py
  (SHA-256 e6722180605bebf826b8525489e3e7e3dbaaa50fb48841c2f0119fe0df252db1)
  beside it on sys.path.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from time import sleep as _sleep
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nyse_calendar import (  # noqa: E402
    NYSE_EARLY_CLOSES,
    expected_bar_starts,
    sessions_between,
)

PANEL_START = date(2023, 1, 1)
PANEL_END = date(2026, 10, 31)
EXPECTED_SESSIONS = 961
EXPECTED_BARS = 24_842
VOLUME_MEDIAN_PASS = 10_000_000  # shares/day; see module docstring check 2
SPLIT_BANDS = [(2.70, 3.30), (0.303, 0.367)]
FOLDS = {  # session-date ranges per walkforward.py FOLDS (W5 ends 2026-10-31 in-panel)
    "W1": (date(2024, 7, 1), date(2024, 12, 31)),
    "W2": (date(2025, 1, 1), date(2025, 6, 30)),
    "W3": (date(2025, 7, 1), date(2025, 12, 31)),
    "W4": (date(2026, 1, 1), date(2026, 6, 30)),
    "W5": (date(2026, 7, 1), date(2026, 10, 31)),
}


# ------------------------------------------------------------------- load
def load_panel(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            et = datetime.fromisoformat(r["timestamp_et"])
            rows.append({
                "timestamp_utc": r["timestamp_utc"],
                "timestamp_et": et,
                "date_et": et.date(),
                "bar_start": et.time(),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
    rows.sort(key=lambda r: r["timestamp_utc"])
    return rows


def daily_aggregates(rows: list[dict]) -> dict[date, dict]:
    by_day: dict[date, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r["date_et"]].append(r)
    out = {}
    for d, rs in by_day.items():
        out[d] = {
            "bars": len(rs),
            "bar_starts": [r["bar_start"] for r in rs],
            "open": rs[0]["open"],
            "high": max(r["high"] for r in rs),
            "low": min(r["low"] for r in rs),
            "close": rs[-1]["close"],
            "volume": sum(r["volume"] for r in rs),
        }
    return out


# -------------------------------------------------------------- check 1
def gap_audit(rows: list[dict], start: date = PANEL_START,
              end: date = PANEL_END) -> dict:
    daily = daily_aggregates(rows)
    sessions = sessions_between(start, end)
    exceptions = []
    for d in sessions:
        expected = expected_bar_starts(d)
        got = daily.get(d)
        if got is None:
            exceptions.append({"date": d.isoformat(), "problem": "session missing entirely",
                               "expected_bars": len(expected), "actual_bars": 0})
        elif got["bar_starts"] != expected:
            missing = [t.isoformat() for t in expected if t not in got["bar_starts"]]
            extra = [t.isoformat() for t in got["bar_starts"] if t not in expected]
            exceptions.append({"date": d.isoformat(), "problem": "bar-start mismatch",
                               "expected_bars": len(expected),
                               "actual_bars": got["bars"],
                               "missing_starts": missing, "extra_starts": extra})
    non_session = sorted(d.isoformat() for d in daily if d not in set(sessions))
    if non_session:
        exceptions.append({"problem": "bars on non-session dates", "dates": non_session})
    stamps = [r["timestamp_utc"] for r in rows]
    dupes = len(stamps) - len(set(stamps))
    if dupes:
        exceptions.append({"problem": "duplicate timestamps", "count": dupes})
    expected_total = sum(len(expected_bar_starts(d)) for d in sessions)
    return {
        "check": "1_gap_audit",
        "status": "PASS" if not exceptions else "FAIL",
        "sessions_expected": len(sessions),
        "sessions_present": sum(1 for d in sessions if d in daily),
        "bars_expected": expected_total,
        "bars_actual": len(rows),
        "exceptions": exceptions,
    }


# -------------------------------------------------------------- check 2
def volume_check(rows: list[dict]) -> dict:
    daily = daily_aggregates(rows)
    vols = sorted(v["volume"] for v in daily.values())
    median = statistics.median(vols) if vols else 0.0
    p10 = vols[len(vols) // 10] if vols else 0.0
    return {
        "check": "2_sip_vs_iex_volume",
        "status": "PASS" if median >= VOLUME_MEDIAN_PASS else "FAIL",
        "median_daily_volume": median,
        "p10_daily_volume": p10,
        "min_daily_volume": vols[0] if vols else 0.0,
        "pass_threshold_median": VOLUME_MEDIAN_PASS,
        "reading": ("Consolidated (SIP) scale" if median >= VOLUME_MEDIAN_PASS
                    else "NOT consolidated scale — consistent with a single-venue "
                         "(IEX-like) feed or a corrupted panel; do not run"),
    }


# -------------------------------------------------------------- check 3
def split_check(rows: list[dict]) -> dict:
    daily = daily_aggregates(rows)
    days = sorted(daily)
    hits, extremes = [], []
    for prev, cur in zip(days, days[1:]):
        for kind, ratio in (("open/prev_close", daily[cur]["open"] / daily[prev]["close"]),
                            ("close/prev_close", daily[cur]["close"] / daily[prev]["close"])):
            if any(lo <= ratio <= hi for lo, hi in SPLIT_BANDS):
                hits.append({"date": cur.isoformat(), "kind": kind,
                             "ratio": round(ratio, 4)})
            elif ratio > 1.5 or ratio < 0.667:
                extremes.append({"date": cur.isoformat(), "kind": kind,
                                 "ratio": round(ratio, 4),
                                 "note": "extreme overnight move — eyeball before running"})
    return {
        "check": "3_split_adjustment",
        "status": "PASS" if not hits else "FAIL",
        "split_band_hits": hits,
        "extreme_moves_to_eyeball": extremes,
        "note": "Panel starts after the last TSLA split (2022-08-25) and was "
                "requested with adjustment=split; any split-band ratio is a "
                "provenance defect.",
    }


# -------------------------------------------------------------- check 4
def load_cross_source(path: Path) -> dict[date, dict]:
    out = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["date"])
            out[d] = {k: float(r[k]) for k in ("open", "high", "low", "close")}
    return out


def sample_sessions(daily: dict, per_fold: int = 3) -> list[date]:
    """Deterministic spread: `per_fold` evenly spaced sessions per fold."""
    picked: list[date] = []
    for _, (s, e) in FOLDS.items():
        fold_days = sorted(d for d in daily if s <= d <= e)
        if not fold_days:
            continue
        if len(fold_days) <= per_fold:
            picked.extend(fold_days)
        else:
            step = len(fold_days) / per_fold
            picked.extend(fold_days[int(i * step)] for i in range(per_fold))
    return sorted(set(picked))


# ------------------------------------------- check 4 close leg (v4)
ET_ZONE = ZoneInfo("America/New_York")
TRADES_ENDPOINT = "https://data.alpaca.markets/v2/stocks/TSLA/trades"
_FRACTION_RE = re.compile(r"(\.\d{6})\d+")


def parse_trade_ts(raw: str) -> datetime:
    """Parse an Alpaca RFC3339 trade timestamp (nanosecond precision)
    to an aware datetime. Fractional seconds are truncated to
    microseconds — the R1b window is defined at whole-second
    granularity, so truncation cannot move a print across its edge."""
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    s = _FRACTION_RE.sub(r"\1", s, count=1)
    return datetime.fromisoformat(s)


def scheduled_close(session: date) -> datetime:
    """The session's scheduled close as an aware ET datetime — the
    EXCHANGE's scheduled close, where the official-close print
    occurs: 16:00 ET for a full session, 13:00 ET for an early close
    (NYSE_EARLY_CLOSES in the frozen nyse_calendar). Deliberately NOT
    derived from the panel's last retained bar: the frozen panel
    spec truncates early-close sessions to 10 bars (ending 12:00
    ET), but the closing auction still prints at the real 13:00 ET
    close — and the close leg verifies the feed, not a panel field."""
    t = time(13, 0) if session in NYSE_EARLY_CLOSES else time(16, 0)
    return datetime.combine(session, t, ET_ZONE)


def r1b_official_close(trades: list[dict], session: date) -> dict:
    """Addendum v4 Rule R1b: the SIP-side official close is the price
    of the trade carrying condition 'M' (Market Center Official
    Closing Price) on the listing exchange (Alpaca exchange code
    'Q', Nasdaq) with ET timestamp in [scheduled close, +1 minute).
    Exactly one such trade must exist; zero or more than one fails
    the close leg (no fallback, no substitution)."""
    start = scheduled_close(session)
    end = start + timedelta(minutes=1)
    hits = []
    for tr in trades:
        if tr.get("x") != "Q" or "M" not in (tr.get("c") or []):
            continue
        ts = parse_trade_ts(tr["t"]).astimezone(ET_ZONE)
        if start <= ts < end:
            hits.append(tr)
    out = {"candidates": len(hits), "price": None, "trade": None,
           "window_et": f"[{start.isoformat()}, {end.isoformat()})"}
    if len(hits) == 1:
        out["price"] = float(hits[0]["p"])
        out["trade"] = {"t": hits[0]["t"], "p": hits[0]["p"],
                        "s": hits[0]["s"], "x": hits[0]["x"],
                        "c": hits[0]["c"]}
    return out


def load_ticks_file(ticks_dir: Path, session: date) -> tuple:
    """Read one session's tick window from --ticks-dir: a JSON array
    of Alpaca trades (the tick-probe format). Returns (trades,
    provenance), or (None, provenance) when the file is absent."""
    path = ticks_dir / f"{session.isoformat()}.json"
    if not path.exists():
        return None, {"source": "file", "path": str(path), "present": False}
    raw = path.read_bytes()
    trades = json.loads(raw.decode("utf-8"))
    return trades, {"source": "file", "path": str(path), "present": True,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "n_trades": len(trades)}


def pull_ticks(session: date, key_id: str, secret: str) -> tuple:
    """Fresh gate-time pull per addendum v4 §4: Alpaca trades,
    feed=sip, window [scheduled close - 5 min, scheduled close
    + 10 min) ET — for a regular session, [15:55, 16:10) ET."""
    close = scheduled_close(session)
    start = close - timedelta(minutes=5)
    end = close + timedelta(minutes=10)
    params = {"start": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "end": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "feed": "sip", "limit": 10000}
    headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
    trades, token, pages = [], None, 0
    while True:
        p = dict(params)
        if token:
            p["page_token"] = token
        url = TRADES_ENDPOINT + "?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers=headers)
        body = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    _sleep(int(e.headers.get("Retry-After") or (2 ** attempt)))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt < 4:
                    _sleep(2 ** attempt)
                    continue
                raise
        pages += 1
        trades.extend(body.get("trades") or [])
        token = body.get("next_page_token")
        if not token:
            break
    digest = hashlib.sha256(
        json.dumps(trades, sort_keys=True).encode("utf-8")).hexdigest()
    return trades, {"source": "pull", "feed": "sip",
                    "window_et": f"[{start.isoformat()}, {end.isoformat()})",
                    "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
                    "pages": pages, "n_trades": len(trades),
                    "trades_sha256": digest}


def gather_ticks(samples: list, ticks_dir, pull: bool) -> dict | None:
    """Tick windows for the sampled sessions, from the configured
    source. Returns None when no tick source is configured (check 4
    is then NOT_RUN). A session whose data cannot be obtained gets
    trades=None, which the close leg scores as zero candidates — a
    finding, per the frozen absence discipline."""
    if ticks_dir is None and not pull:
        return None
    key_id = secret = None
    if pull:
        key_id = (os.environ.get("APCA_API_KEY_ID")
                  or os.environ.get("ALPACA_API_KEY_ID"))
        secret = (os.environ.get("APCA_API_SECRET_KEY")
                  or os.environ.get("ALPACA_API_SECRET_KEY"))
        if not key_id or not secret:
            raise SystemExit("--pull-ticks: Alpaca keys not found in the "
                             "environment (APCA_API_KEY_ID / "
                             "APCA_API_SECRET_KEY, or ALPACA_API_KEY_ID / "
                             "ALPACA_API_SECRET_KEY)")
    out = {}
    for d in samples:
        if ticks_dir is not None:
            trades, prov = load_ticks_file(ticks_dir, d)
        else:
            try:
                trades, prov = pull_ticks(d, key_id, secret)
            except Exception as e:  # recorded, never silently skipped
                trades, prov = None, {"source": "pull", "present": False,
                                      "error": f"{type(e).__name__}: {e}"}
        out[d] = {"trades": trades, "provenance": prov}
    return out


def cross_source_check(rows: list[dict], cross: dict | None,
                       tick_data: dict | None = None) -> dict:
    if cross is None:
        return {"check": "4_cross_source_spot_check", "status": "NOT_RUN",
                "reason": "no --cross-source file supplied; an unrun check "
                          "is not a passed check"}
    if tick_data is None:
        return {"check": "4_cross_source_spot_check", "status": "NOT_RUN",
                "reason": "no tick source supplied (--ticks-dir or "
                          "--pull-ticks); the addendum v4 close leg (Rule "
                          "R1b) is unrun, and an unrun leg is not a "
                          "passed leg"}
    daily = daily_aggregates(rows)
    samples = sample_sessions(daily)
    table, findings = [], []
    tick_provenance = {}
    for d in samples:
        ref = cross.get(d)
        if ref is None:
            findings.append({"date": d.isoformat(), "problem": "session absent from cross-source"})
            continue
        got = daily[d]
        entry = tick_data.get(d) or {"trades": None,
                                     "provenance": {"present": False,
                                                    "error": "no tick entry"}}
        tick_provenance[d.isoformat()] = entry["provenance"]
        r1b = (r1b_official_close(entry["trades"], d)
               if entry["trades"] is not None
               else {"candidates": 0, "price": None, "trade": None,
                     "window_et": None})
        row = {"date": d.isoformat(),
               "close_diff": (round(abs(r1b["price"] - ref["close"]), 4)
                              if r1b["price"] is not None else None),
               "high_diff": round(abs(got["high"] - ref["high"]), 4),
               "low_diff": round(abs(got["low"] - ref["low"]), 4),
               "open_diff": round(abs(got["open"] - ref["open"]), 4),
               "panel_close": got["close"],
               "r1b_price": r1b["price"],
               "r1b_candidates": r1b["candidates"],
               "auction_minus_panel": (round(r1b["price"] - got["close"], 4)
                                       if r1b["price"] is not None else None)}
        table.append(row)
        if r1b["candidates"] != 1:
            findings.append({**row, "problem": "close leg (R1b): expected exactly one "
                                              "official-close print ('M' on 'Q' in the "
                                              "scheduled-close minute), found "
                                              f"{r1b['candidates']}"})
        elif row["close_diff"] > 0.02:
            findings.append({**row, "problem": "close differs by > $0.02 "
                                              "(R1b official close vs cross-source)"})
        if row["high_diff"] > 0.05 or row["low_diff"] > 0.05:
            findings.append({**row, "problem": "high/low differ by > $0.05"})
    status = "PASS" if len(table) >= 10 and not findings else "FAIL"
    return {"check": "4_cross_source_spot_check", "status": status,
            "samples_compared": len(table), "samples_required": 10,
            "sample_table": table, "findings": findings,
            "tolerances": {"close_max_diff": 0.02, "high_low_max_diff": 0.05},
            "close_leg": "addendum v4 Rule R1b — SIP tick official-close print "
                         "(condition 'M', listing exchange 'Q', [scheduled close, "
                         "+1 min) ET) vs cross-source close; the panel's last-bar "
                         "close is a pre-auction trade, recorded as panel_close, "
                         "never compared",
            "tick_provenance": tick_provenance}


# -------------------------------------------------------------- check 5
def freeze(panel_path: Path, rows: list[dict], checks: list[dict],
           request_parameters: dict | None = None) -> dict:
    digest = hashlib.sha256(panel_path.read_bytes()).hexdigest()
    draft_path = panel_path.parent / "data_provenance.json"
    draft_hash_match = None
    if draft_path.exists():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            if draft.get("panel_sha256"):
                draft_hash_match = draft["panel_sha256"] == digest
        except (OSError, json.JSONDecodeError):
            draft_hash_match = None
    record = {
        "symbol": "TSLA",
        "timeframe": "15Min",
        "source": "Alpaca Market Data API (Basic plan, historical bars)",
        "endpoint": "https://data.alpaca.markets/v2/stocks/TSLA/bars",
        "request_parameters": request_parameters or {
            "timeframe": "15Min", "start": "2023-01-01T00:00:00Z",
            "end": "2026-11-01T00:00:00Z", "adjustment": "split",
            "feed": "sip", "sort": "asc", "limit": 10000},
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "first_bar_utc": rows[0]["timestamp_utc"] if rows else None,
        "last_bar_utc": rows[-1]["timestamp_utc"] if rows else None,
        "panel_file": panel_path.name,
        "panel_sha256": digest,
        "licence": "Alpaca/SIP data: personal use only, no redistribution. "
                   "This record is the committable artifact; the panel file "
                   "itself must NEVER be committed to git.",
        "verification": {c["check"]: c["status"] for c in checks},
    }
    status = "PASS"
    if draft_hash_match is False:
        status = "FAIL"
        record["freeze_warning"] = ("Panel hash differs from the download-time "
                                    "provenance draft — the panel changed "
                                    "after download. Do not re-pin silently; "
                                    "investigate or re-download.")
    return {"check": "5_sha256_freeze", "status": status,
            "panel_sha256": digest,
            "download_draft_hash_match": draft_hash_match,
            "provenance_record": record}


# -------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--panel", type=Path, required=True)
    ap.add_argument("--cross-source", type=Path, default=None,
                    help="CSV with date,open,high,low,close (daily, independent source)")
    ap.add_argument("--ticks-dir", type=Path, default=None,
                    help="directory of per-session tick windows "
                         "(<date>.json, Alpaca trades format) for the "
                         "addendum v4 close leg (Rule R1b)")
    ap.add_argument("--pull-ticks", action="store_true",
                    help="pull the tick windows fresh from the Alpaca "
                         "trades endpoint (feed=sip; keys from the "
                         "environment) instead of --ticks-dir")
    ap.add_argument("--provenance-out", type=Path, default=None,
                    help="also write the committable data_provenance.json here "
                         "(e.g. into the run PR); default: beside the panel")
    ap.add_argument("--report-out", type=Path, default=None,
                    help="verification report JSON (default: beside the panel)")
    args = ap.parse_args()

    panel_path = args.panel.expanduser()
    if not panel_path.exists():
        print(f"panel not found: {panel_path}", file=sys.stderr)
        return 5
    rows = load_panel(panel_path)
    cross = load_cross_source(args.cross_source.expanduser()) if args.cross_source else None

    tick_data = None
    if cross is not None:
        samples = sample_sessions(daily_aggregates(rows))
        tick_data = gather_ticks(samples,
                                 args.ticks_dir.expanduser() if args.ticks_dir else None,
                                 args.pull_ticks)

    checks = [
        gap_audit(rows),
        volume_check(rows),
        split_check(rows),
        cross_source_check(rows, cross, tick_data),
    ]
    checks.append(freeze(panel_path, rows, checks))
    record = checks[-1]["provenance_record"]

    verdicts = [c["status"] for c in checks]
    overall = "PASS" if all(v == "PASS" for v in verdicts) else (
        "INCOMPLETE" if "NOT_RUN" in verdicts and "FAIL" not in verdicts else "FAIL")
    record["verification"]["overall"] = overall

    prov_path = (args.provenance_out.expanduser() if args.provenance_out
                 else panel_path.parent / "data_provenance.json")
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    prov_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    report = {"panel": str(panel_path), "overall": overall, "checks": checks}
    report_path = (args.report_out.expanduser() if args.report_out
                   else panel_path.parent / "verification_report.json")
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    for c in checks:
        print(f"  [{c['status']:>7}] {c['check']}")
    print(f"OVERALL: {overall}")
    print(f"panel sha256: {record['panel_sha256']}")
    print(f"provenance record (committable): {prov_path}")
    print(f"full report: {report_path}")
    if overall != "PASS":
        print("The backtest must NOT run on this panel.", file=sys.stderr)
        return 5
    print("Panel verified. The declared backtest may proceed (once, per the addendum).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
