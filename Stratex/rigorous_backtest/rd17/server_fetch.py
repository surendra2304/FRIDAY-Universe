#!/usr/bin/env python3
"""TASK-STR-RD-017 — one-shot live bundle fetcher (server-side / REST side).

Fetches ONE poll bundle of Binance public market data for the declared
crypto30 set and prints it to stdout as a single line:

    RD17BUNDLE {"fetched_at_ms": ..., "symbols": {...}, "errors": {...}}

No API keys, no accounts, GET requests only. Pure stdlib.

Input (stdin, one JSON object):
    {"symbols": ["BTCUSDT", ...],
     "since_ms": {"BTCUSDT": 1760000000000, ...}}   # per-symbol funding
                                                    # watermark (exclusive
                                                    # intent; endpoint is
                                                    # inclusive — the sim
                                                    # dedupes by print)

Per symbol the bundle carries:
    spot            spot price (api.binance.com, data-api.binance.vision
                    mirror as fallback; bundle records which served)
    mark            USD-M mark price (premiumIndex)
    last_funding_rate, next_funding_ms   (premiumIndex)
    prints          settled funding prints with fundingTime > since_ms
                    (endpoint may include the watermark print itself;
                    the sim dedupes), each with mark_at_print = close of
                    the 1-minute mark-price kline at the print timestamp
                    (null if that kline could not be fetched)

This script is transport-agnostic: on a host with direct Binance access
it is the sim's `rest` transport; the sim's `bridge` transport uploads
it to a fleet server once and runs it there via run_shell, because the
research sandbox's egress is geo-blocked by Binance.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

FAPI = "https://fapi.binance.com"
SPOT_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]
UA = {"User-Agent": "rd17-paper-sim/1.0 (public market data reader)"}
TIMEOUT = 12


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_marks(symbols):
    rows = get_json(FAPI + "/fapi/v1/premiumIndex")
    want = set(symbols)
    out = {}
    for r in rows:
        if r["symbol"] in want:
            out[r["symbol"]] = {
                "mark": float(r["markPrice"]),
                "index": float(r["indexPrice"]),
                "last_funding_rate": float(r["lastFundingRate"]),
                "next_funding_ms": int(r["nextFundingTime"]),
            }
    return out


def fetch_all_spot(symbols):
    want = set(symbols)
    last_err = None
    for host in SPOT_HOSTS:
        try:
            rows = get_json(host + "/api/v3/ticker/price")
            out = {r["symbol"]: float(r["price"]) for r in rows
                   if r["symbol"] in want}
            if out:
                return out, host
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"spot fetch failed on all hosts: {last_err}")


def fetch_prints(symbol, since_ms):
    url = (FAPI + f"/fapi/v1/fundingRate?symbol={symbol}"
           f"&startTime={int(since_ms)}&limit=100")
    rows = get_json(url)
    prints = []
    for r in rows:
        ft = int(r["fundingTime"])
        if ft <= since_ms:
            continue
        prints.append({"funding_time_ms": ft,
                       "rate": float(r["fundingRate"]),
                       "mark_at_print": None})
    if prints:
        # ONE batched kline-range call per symbol (not one call per
        # print — a catch-up after downtime could otherwise need
        # hundreds of calls and time out the transport). mark_at_print
        # = close of the 1-minute mark-price kline that OPENS at the
        # print's minute, per the declaration.
        try:
            first = prints[0]["funding_time_ms"]
            last = prints[-1]["funding_time_ms"]
            start = first - (first % 60000)
            k = get_json(FAPI + f"/fapi/v1/markPriceKlines?symbol={symbol}"
                         f"&interval=1m&startTime={start}"
                         f"&endTime={last + 60000}&limit=1000")
            closes = {int(row[0]): float(row[4]) for row in k}
            for p in prints:
                ft = p["funding_time_ms"]
                p["mark_at_print"] = closes.get(ft - (ft % 60000))
        except Exception:  # noqa: BLE001
            pass  # marks stay None -> engine falls back + flags approx
    return prints


def main():
    spec = json.loads(sys.stdin.read())
    symbols = spec["symbols"]
    since_ms = spec.get("since_ms", {})
    bundle = {"fetched_at_ms": int(time.time() * 1000),
              "symbols": {}, "errors": {}}
    marks, spot, spot_host = {}, {}, None
    try:
        marks = fetch_all_marks(symbols)
    except Exception as exc:  # noqa: BLE001
        bundle["errors"]["_marks"] = str(exc)[:300]
    try:
        spot, spot_host = fetch_all_spot(symbols)
    except Exception as exc:  # noqa: BLE001
        bundle["errors"]["_spot"] = str(exc)[:300]
    bundle["spot_source"] = spot_host

    def one(sym):
        entry = {}
        if sym in marks:
            entry.update(marks[sym])
        if sym in spot:
            entry["spot"] = spot[sym]
        try:
            entry["prints"] = fetch_prints(sym, int(since_ms.get(sym, 0)))
        except Exception as exc:  # noqa: BLE001
            entry["prints"] = []
            bundle["errors"][sym] = str(exc)[:300]
        return sym, entry

    with ThreadPoolExecutor(max_workers=8) as pool:
        for sym, entry in pool.map(one, symbols):
            bundle["symbols"][sym] = entry
    sys.stdout.write("RD17BUNDLE " + json.dumps(bundle) + "\n")


if __name__ == "__main__":
    main()
