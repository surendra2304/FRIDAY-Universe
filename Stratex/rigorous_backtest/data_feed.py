"""Provenance-checked historical candle feed (Binance Vision public archive).

Data source: Binance's official public data archive (data.binance.vision),
USDT-M futures monthly klines. Every dataset carries a provenance manifest:
source, symbol, timeframe, fetch time, per-file SHA-256, canonical CSV
SHA-256, row count, first/last timestamps and a gap audit against the
expected bar grid.

HARD RULE: if any file cannot be fetched, parsed or verified, this module
raises DataUnavailable. It never fabricates, interpolates or substitutes
candles. A market that cannot be loaded is UNTESTABLE, full stop.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ARCHIVE_BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
SOURCE_NAME = "binance_vision_futures_um_monthly_klines"

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


class DataUnavailable(RuntimeError):
    """Raised when real candle data cannot be obtained or verified."""


def _fetch_bytes(url: str, timeout: int = 90, attempts: int = 3) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - retried, then hard-fail
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise DataUnavailable(f"fetch failed after {attempts} attempts: {url}: {last_exc}")


def _month_range(start: str, end: str) -> list[tuple[int, int]]:
    """Inclusive (year, month) list between 'YYYY-MM' bounds."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


@dataclass
class Dataset:
    symbol: str
    timeframe: str
    df: pd.DataFrame  # columns: open, high, low, close, volume; UTC DatetimeIndex (bar open)
    manifest: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.symbol}_{self.timeframe}"


def _parse_kline_csv(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise DataUnavailable("empty kline CSV")
    if lines[0].startswith("open_time"):
        lines = lines[1:]
    rows = []
    for ln in lines:
        parts = ln.split(",")
        if len(parts) < 6:
            raise DataUnavailable(f"malformed kline row: {ln[:80]}")
        ts = int(parts[0])
        # Binance archive switched some series from ms to us timestamps.
        if ts > 10**15:
            ts //= 1000
        rows.append((ts, float(parts[1]), float(parts[2]), float(parts[3]),
                     float(parts[4]), float(parts[5])))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df


def gap_audit(df: pd.DataFrame, timeframe: str) -> dict:
    """Count missing bars vs the regular grid. Gaps are REPORTED, never filled."""
    if df.empty:
        return {"expected_bars": 0, "actual_bars": 0, "missing_bars": 0, "gap_spans": []}
    step = pd.Timedelta(minutes=_TF_MINUTES[timeframe])
    expected = int((df.index[-1] - df.index[0]) / step) + 1
    missing = expected - len(df)
    spans = []
    if missing > 0:
        diffs = df.index.to_series().diff()
        gap_idx = diffs[diffs > step].index
        for ts in gap_idx:
            prev = df.index[df.index.get_loc(ts) - 1]
            spans.append({
                "after": prev.isoformat(),
                "before": ts.isoformat(),
                "missing_bars": int((ts - prev) / step) - 1,
            })
    return {"expected_bars": expected, "actual_bars": len(df),
            "missing_bars": missing, "gap_spans": spans[:50]}


def load_dataset(symbol: str, timeframe: str, start_month: str, end_month: str,
                 cache_dir: Path | None = None) -> Dataset:
    """Load one symbol/timeframe series from the Binance Vision archive.

    Months are 'YYYY-MM' inclusive bounds. Raises DataUnavailable on any
    fetch/parse/integrity problem. When cache_dir is given, verified data is
    cached with a provenance sidecar and re-verified (hash + identity) on
    every subsequent read, mirroring the hardened research cache contract.
    """
    cache_file = None
    sidecar = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{symbol}_{timeframe}_{start_month}_{end_month}.csv"
        sidecar = cache_file.with_suffix(".csv.json")
        if cache_file.exists():
            if not sidecar.exists():
                raise DataUnavailable(f"cache {cache_file} lacks provenance sidecar; refusing unverified data")
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            blob = cache_file.read_bytes()
            if hashlib.sha256(blob).hexdigest() != meta.get("csv_sha256"):
                raise DataUnavailable(f"cache hash mismatch for {cache_file}; refusing")
            if meta.get("symbol") != symbol or meta.get("timeframe") != timeframe:
                raise DataUnavailable(f"cache identity mismatch for {cache_file}; refusing")
            df = pd.read_csv(io.BytesIO(blob), index_col=0, parse_dates=True)
            if getattr(df.index, "tz", None) is None:
                df.index = df.index.tz_localize("UTC")
            return Dataset(symbol, timeframe, df, meta)

    frames = []
    file_hashes = {}
    for (y, m) in _month_range(start_month, end_month):
        fname = f"{symbol}-{timeframe}-{y:04d}-{m:02d}.zip"
        url = f"{ARCHIVE_BASE}/{symbol}/{timeframe}/{fname}"
        blob = _fetch_bytes(url)
        file_hashes[fname] = hashlib.sha256(blob).hexdigest()
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile as exc:
            raise DataUnavailable(f"bad zip from {url}: {exc}") from exc
        members = [n for n in zf.namelist() if n.endswith(".csv")]
        if len(members) != 1:
            raise DataUnavailable(f"unexpected zip contents from {url}: {zf.namelist()}")
        frames.append(_parse_kline_csv(zf.read(members[0])))

    if not frames:
        raise DataUnavailable(f"no data fetched for {symbol} {timeframe}")
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    if df.empty:
        raise DataUnavailable(f"empty dataset for {symbol} {timeframe}")

    canonical = df.to_csv().encode("utf-8")
    manifest = {
        "source": SOURCE_NAME,
        "archive_base": ARCHIVE_BASE,
        "symbol": symbol,
        "timeframe": timeframe,
        "months": f"{start_month}..{end_month}",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip_sha256": file_hashes,
        "csv_sha256": hashlib.sha256(canonical).hexdigest(),
        "rows": int(len(df)),
        "first_bar_utc": df.index[0].isoformat(),
        "last_bar_utc": df.index[-1].isoformat(),
        "gap_audit": gap_audit(df, timeframe),
    }
    if cache_file is not None and sidecar is not None:
        # Best-effort cache; a failed write never invalidates fetched data,
        # but a written cache is re-verified on read (above).
        try:
            cache_file.write_bytes(canonical)
            sidecar.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except OSError:
            pass
    return Dataset(symbol, timeframe, df, manifest)


def resample_dataset(ds: Dataset, target_tf: str) -> Dataset:
    """Resample a verified dataset to a coarser timeframe (documented derivation).

    Only exact-multiple resamples aligned to UTC boundaries are allowed
    (e.g. 1h -> 4h). Partial buckets at the edges are dropped. The derived
    dataset's manifest records the parent dataset's hash.
    """
    src_min = _TF_MINUTES[ds.timeframe]
    dst_min = _TF_MINUTES[target_tf]
    if dst_min % src_min != 0 or dst_min <= src_min:
        raise DataUnavailable(f"cannot resample {ds.timeframe} -> {target_tf}")
    rule = f"{dst_min}min"
    agg = ds.df.resample(rule, origin="start_day").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    bars_per_bucket = dst_min // src_min
    counts = ds.df["close"].resample(rule, origin="start_day").count()
    agg = agg[counts == bars_per_bucket].dropna()
    manifest = {
        "source": f"resampled_from:{SOURCE_NAME}",
        "derived_from_csv_sha256": ds.manifest.get("csv_sha256"),
        "derived_from": ds.key,
        "symbol": ds.symbol,
        "timeframe": target_tf,
        "resample_rule": f"{rule} origin=start_day, complete buckets only",
        "fetched_at_utc": ds.manifest.get("fetched_at_utc"),
        "rows": int(len(agg)),
        "first_bar_utc": agg.index[0].isoformat() if len(agg) else None,
        "last_bar_utc": agg.index[-1].isoformat() if len(agg) else None,
        "gap_audit": gap_audit(agg, target_tf),
    }
    return Dataset(ds.symbol, target_tf, agg, manifest)
