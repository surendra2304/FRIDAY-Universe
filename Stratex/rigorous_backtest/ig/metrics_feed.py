"""Binance Vision futures METRICS loader for TASK-STR-RD-022.

Downloads the daily metrics archives (open interest + positioning
ratios) from data.binance.vision, verifies every zip against its
published .CHECKSUM (SHA-256) — the RD-003 manifest discipline —
parses sum_open_interest, and builds the causal asof open-interest
value at each price bar's close.

Free and keyless. Stdlib only. Downloads are cached as raw zips
under an optional cache dir (best-effort: a cache write failure
never fails the load, mirroring the programme loader's sandbox
behaviour); every load re-verifies the checksum of the bytes it
actually parsed, cached or fresh.

A snapshot is used ONLY at or after its own create_time: the asof
at a bar close returns the last snapshot with create_time <= bar
close, plus its age in minutes, so the signal module can enforce
the declared 30-minute staleness cap. No interpolation anywhere.
"""
from __future__ import annotations

import csv
import hashlib
import io
import urllib.request
import zipfile
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone

BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
_UA = {"User-Agent": "friday-str-rd-022-metrics/1.0"}


def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def verify_checksum(raw: bytes, checksum_text: str) -> bool:
    """True iff the published .CHECKSUM content's SHA-256 matches
    the zip bytes. The checksum file format is '<sha256>  <name>'."""
    parts = checksum_text.strip().split()
    if not parts:
        return False
    return parts[0].lower() == hashlib.sha256(raw).hexdigest()


def parse_metrics_csv(text: str) -> list[tuple[datetime, float]]:
    """Parse one daily metrics CSV -> sorted [(create_time_utc,
    sum_open_interest)]. Rows with unparseable values are dropped
    (they can only make a bar unevaluable downstream, never invent
    data)."""
    out: list[tuple[datetime, float]] = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            ts = datetime.strptime(
                row["create_time"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            out.append((ts, float(row["sum_open_interest"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    return out


def parse_metrics_zip(raw: bytes) -> list[tuple[datetime, float]]:
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    if len(names) != 1:
        raise ValueError(f"metrics zip must hold exactly one CSV, got {names}")
    return parse_metrics_csv(zf.read(names[0]).decode("utf-8"))


def download_metrics_day(symbol: str, day: date,
                         cache_dir=None) -> tuple[list[tuple[datetime, float]], str]:
    """Download (or read from cache) one daily metrics archive,
    VERIFY its published checksum, and return (snapshots, sha256).
    Raises on any checksum mismatch or unreadable archive — the
    run's panel gate treats a raise as a missing file and reports
    it; it never substitutes data."""
    fname = f"{symbol}-metrics-{day.isoformat()}.zip"
    url = f"{BASE}/{symbol}/{fname}"
    raw = None
    if cache_dir is not None:
        cached = cache_dir / fname
        if cached.exists():
            raw = cached.read_bytes()
    if raw is None:
        raw = _fetch(url)
        if cache_dir is not None:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / fname).write_bytes(raw)
            except OSError:
                pass  # best-effort cache (sandbox write gate)
    checksum_text = _fetch(url + ".CHECKSUM").decode("utf-8")
    if not verify_checksum(raw, checksum_text):
        raise ValueError(f"CHECKSUM MISMATCH for {fname}")
    return parse_metrics_zip(raw), hashlib.sha256(raw).hexdigest()


def load_metrics_series(symbol: str, start: date, end: date,
                        cache_dir=None) -> tuple[list[tuple[datetime, float]], dict]:
    """Load every daily archive in [start, end] inclusive.

    Returns (snapshots, manifest) where manifest records the file
    count, the missing/failed days (a day whose download or
    checksum fails is MISSING — reported, never filled), and each
    loaded file's SHA-256."""
    snapshots: list[tuple[datetime, float]] = []
    manifest = {"symbol": symbol, "start": start.isoformat(),
                "end": end.isoformat(), "files": {}, "missing_days": []}
    day = start
    while day <= end:
        try:
            snaps, sha = download_metrics_day(symbol, day, cache_dir)
            snapshots.extend(snaps)
            manifest["files"][day.isoformat()] = sha
        except Exception:
            manifest["missing_days"].append(day.isoformat())
        day += timedelta(days=1)
    snapshots.sort(key=lambda x: x[0])
    total_days = (end - start).days + 1
    manifest["total_days"] = total_days
    manifest["missing_fraction"] = len(manifest["missing_days"]) / total_days
    return snapshots, manifest


def oi_at_bar_close(snapshots: list[tuple[datetime, float]],
                    bar_close_times: list[datetime],
                    ) -> list[tuple[float, float] | None]:
    """Causal asof join: for each bar close, the (open interest,
    snapshot age in minutes) of the LAST snapshot with
    create_time <= bar close — or None when no snapshot exists at
    or before the close. A snapshot after the close is never used."""
    snap_times = [s[0] for s in snapshots]
    out: list[tuple[float, float] | None] = []
    for close in bar_close_times:
        i = bisect_right(snap_times, close) - 1
        if i < 0:
            out.append(None)
        else:
            ts, val = snapshots[i]
            age_min = (close - ts).total_seconds() / 60.0
            out.append((val, age_min))
    return out
