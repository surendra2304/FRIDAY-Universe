#!/usr/bin/env python3
"""pull_history.py — fetch max OHLCV history from Binance for backtests.

Runs ON THE SERVER (sandbox IP is banned). Polite: one request at a time,
sleep between calls. Saves parquet per (symbol, timeframe) to
/opt/friday_universe/backtest_data/.

Daily: full history (futures first, spot fallback pre-2019).
1h: last 4 years. 15m: last 18 months.
"""
import json
import os
import sys
import time

import pandas as pd
import requests

OUT = "/opt/friday_universe/backtest_data"
SPOT = "https://api.binance.com"
FAPI = "https://fapi.binance.com"

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "TRXUSDT",
]

LIMITS = {"1d": None, "1h": 4 * 365 * 24, "15m": 18 * 30 * 24 * 4}  # in bars


def fetch_all(base, path, symbol, interval, max_bars, session):
    """Paginate klines from `start` forward until exhausted or max_bars."""
    out, start_time = [], 0
    if max_bars:
        earliest_ms = int((time.time() * 1000) - max_bars * interval_ms(interval))
        start_time = earliest_ms
    while True:
        params = {"symbol": symbol, "interval": interval, "startTime": start_time,
                  "limit": 1000}
        r = session.get(base + path, params=params, timeout=30)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 1000:
            break
        start_time = rows[-1][0] + interval_ms(interval)
        time.sleep(0.35)
    return out


def interval_ms(iv):
    return {"1d": 86_400_000, "1h": 3_600_000, "15m": 900_000}[iv]


def to_df(rows):
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qv", "trades", "tbb", "tbq", "ig"])
    df = df[["open_time", "open", "high", "low", "close", "volume"]].astype(float)
    df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[["open", "high", "low", "close", "volume"]]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def main():
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "stratex-backtest/1.0"
    manifest = {}
    for symbol in SYMBOLS:
        for iv, cap in LIMITS.items():
            dest = f"{OUT}/{symbol}_{iv}.csv"
            if os.path.exists(dest):
                df_old = pd.read_parquet(dest)
                manifest[f"{symbol}_{iv}"] = f"{len(df_old)} bars {df_old.index[0].date()}->{df_old.index[-1].date()} (cached)"
                continue
            # try futures first, then spot (longer history)
            rows = []
            try:
                rows = fetch_all(FAPI, "/fapi/v1/klines", symbol, iv, cap, s)
            except Exception as e:
                print(f"  fapi {symbol} {iv}: {e}", flush=True)
            time.sleep(0.4)
            if iv == "1d" and len(rows) < 500:  # thin: extend back via spot
                try:
                    spot_rows = fetch_all(SPOT, "/api/v3/klines", symbol, iv, cap, s)
                    # spot covers earlier; merge on index
                    if spot_rows:
                        rows = spot_rows + [r for r in rows
                                            if r[0] > spot_rows[-1][0]]
                except Exception as e:
                    print(f"  spot {symbol} {iv}: {e}", flush=True)
                time.sleep(0.4)
            df = to_df(rows)
            if df is None or len(df) < 100:
                print(f"  SKIP {symbol} {iv}: only {0 if df is None else len(df)} bars", flush=True)
                continue
            if cap:  # keep only the most recent `cap` bars
                df = df.iloc[-cap:]
            df.to_csv(dest)
            manifest[f"{symbol}_{iv}"] = f"{len(df)} bars {df.index[0].date()}->{df.index[-1].date()}"
            print(f"  {symbol} {iv}: {manifest[f'{symbol}_{iv}']}", flush=True)
    print("MANIFEST", json.dumps(manifest, indent=0))


if __name__ == "__main__":
    main()
