"""Asset panels + dataset loading for TASK-STR-RD-002.

Panels are the judgement units of the mega-grid: a configuration is
judged pooled over one panel at one timeframe. Data comes ONLY from the
verified caches built in Stage A:

- crypto: Binance Vision monthly archives through the harness
  data_feed cache contract (per-zip SHA-256, canonical CSV SHA-256,
  gap audit) — files in the RD-002 cache dir.
- forex / commodities / indices: Yahoo Finance chart API (real
  exchange/broker quotes) cached in the same contract by the Stage A
  fetcher (source recorded per series in its sidecar manifest).

Derived timeframes follow the harness rule (UTC-aligned, complete
buckets only, parent hash recorded): 4h/1d from 1h; 1wk from 1d
(>=4 of 5 weekday bars for traded classes, 7/7 for crypto).

Fold profiles: STANDARD = the harness W1..W5. LATE = W2..W5, used only
where the source's history genuinely starts after 2024-07-01 (Yahoo 1h
depth is ~2 years); the profile is recorded on every row it touches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data_feed import Dataset, load_dataset, resample_dataset

CACHE = Path("/home/hatch/workspace/str-rd2/cache2")

CRYPTO30 = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT",
            "TRXUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "UNIUSDT",
            "ETCUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
            "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT", "HBARUSDT",
            "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT"]
CRYPTO12 = CRYPTO30[:12]
CRYPTO6 = CRYPTO30[:6]

FOREX28 = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
           "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY",
           "CADJPY", "CHFJPY", "EURAUD", "EURNZD", "GBPAUD", "AUDNZD",
           "NZDJPY", "USDSEK", "USDNOK", "USDMXN", "USDZAR", "USDTRY",
           "USDCNH", "USDSGD", "USDHKD", "EURPLN"]
FOREX12 = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
           "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF"]

COMM7 = ["GOLD", "SILVER", "WTI", "BRENT", "NATGAS", "COPPER", "PLATINUM"]
IDX7 = ["SPX", "NDX", "DJI", "RUT", "FTSE", "NIKKEI", "DAX"]
IDX3 = ["SPX", "NDX", "DJI"]

PANELS: dict[str, list[str]] = {
    "crypto30": CRYPTO30, "crypto12": CRYPTO12, "crypto6": CRYPTO6,
    "forex28": FOREX28, "forex12": FOREX12,
    "comm7": COMM7, "idx7": IDX7, "idx3": IDX3,
}

# Which timeframes each panel can honestly serve (Stage A coverage).
PANEL_TFS: dict[str, list[str]] = {
    "crypto30": ["1d", "4h", "1h", "1wk"],
    "crypto12": ["1d", "4h", "1h", "15m"],
    "crypto6": ["1d", "4h", "1h", "15m", "5m"],
    "forex28": ["1d", "1wk"],
    "forex12": ["1d", "1wk", "4h", "1h"],
    "comm7": ["1d", "1wk", "4h", "1h"],
    "idx7": ["1d", "1wk"],
    "idx3": ["1d", "1wk", "4h", "1h"],
}

_BINANCE_RANGES = {"1h": ("2022-01", "2026-10"),
                   "15m": ("2023-10", "2026-10"),
                   "5m": ("2024-01", "2026-10")}

STANDARD = ["W1", "W2", "W3", "W4", "W5"]
LATE = ["W2", "W3", "W4", "W5"]


def fold_profile(panel: str, tf: str) -> list[str]:
    """Yahoo-1h-derived intraday panels start ~2024-11 -> LATE folds."""
    if panel.startswith(("forex12", "comm", "idx3")) and tf in ("1h", "4h"):
        return LATE
    return STANDARD


def _yahoo_dataset(symbol: str, tf: str) -> Dataset:
    base_tf = "1d" if tf in ("1d", "1wk") else "1h"
    f = CACHE / f"YH_{symbol}_{base_tf}.csv"
    meta = json.loads(f.with_suffix(".csv.json").read_text())
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC")
    ds = Dataset(symbol, base_tf, df, meta)
    if tf == base_tf:
        return ds
    if tf == "4h":
        return resample_dataset(ds, "4h")
    if tf == "1wk":
        return _to_weekly(ds)
    raise ValueError(f"cannot derive {tf} from Yahoo {base_tf}")


def _to_weekly(ds: Dataset) -> Dataset:
    traded = not ds.symbol.endswith("USDT")
    agg = ds.df.resample("7D", origin="start_day").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"})
    counts = ds.df["close"].resample("7D", origin="start_day").count()
    need = 4 if traded else 7
    agg = agg[counts >= need].dropna()
    manifest = {
        "source": f"resampled_from:{ds.manifest.get('source')}",
        "derived_from_csv_sha256": ds.manifest.get("csv_sha256"),
        "derived_from": ds.key, "symbol": ds.symbol, "timeframe": "1wk",
        "resample_rule": f"7D origin=start_day, buckets with >={need} daily bars",
        "rows": int(len(agg)),
        "first_bar_utc": agg.index[0].isoformat() if len(agg) else None,
        "last_bar_utc": agg.index[-1].isoformat() if len(agg) else None,
    }
    return Dataset(ds.symbol, "1wk", agg, manifest)


def _crypto_dataset(symbol: str, tf: str) -> Dataset:
    if tf in ("1d", "4h", "1wk"):
        s, e = _BINANCE_RANGES["1h"]
        base = load_dataset(symbol, "1h", s, e, cache_dir=CACHE)
        if tf == "1wk":
            return _to_weekly(Dataset(symbol, "1d",
                                      resample_dataset(base, "1d").df,
                                      resample_dataset(base, "1d").manifest))
        return resample_dataset(base, tf)
    s, e = _BINANCE_RANGES[tf]
    return load_dataset(symbol, tf, s, e, cache_dir=CACHE)


def load_panel(panel: str, tf: str) -> dict[str, Dataset]:
    """Load every series of a panel at a timeframe. Series whose cache
    file is absent are SKIPPED and must be reported by the caller via
    panel_coverage(); a series that exists but fails verification raises
    (the harness cache contract) — never silently substituted."""
    out: dict[str, Dataset] = {}
    for sym in PANELS[panel]:
        try:
            if panel.startswith("crypto"):
                out[sym] = _crypto_dataset(sym, tf)
            else:
                out[sym] = _yahoo_dataset(sym, tf)
        except FileNotFoundError:
            continue
    return out


def panel_coverage() -> list[dict]:
    """Stage A coverage table: one row per cached series file."""
    rows = []
    for sidecar in sorted(CACHE.glob("*.csv.json")):
        meta = json.loads(sidecar.read_text())
        ga = meta.get("gap_audit") or {}
        rows.append({
            "series": meta.get("symbol"), "timeframe": meta.get("timeframe"),
            "source": meta.get("source"),
            "rows": meta.get("rows"),
            "first_bar_utc": meta.get("first_bar_utc"),
            "last_bar_utc": meta.get("last_bar_utc"),
            "missing_bars": ga.get("missing_bars"),
            "csv_sha256": (meta.get("csv_sha256") or "")[:16],
        })
    return rows
