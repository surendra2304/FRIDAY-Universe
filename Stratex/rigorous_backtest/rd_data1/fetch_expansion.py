"""Fetch provenanced expansion series for TASK-STR-DATA-001.

Expansion universe: OANDA instruments NOT in RD-002's panels
(rd2/panels.py forex28/forex12/comm7/idx7). Source: Yahoo Finance chart
API — the RD-002 Stage-A source for every non-crypto series (forex =
composite indicative quotes; indices = cash exchange data; softs and
palladium = front-month futures proxies, disclosed per series in
results_data1/inventory.json).

Cache contract is identical to RD-002's: canonical CSV + sidecar JSON
manifest (source, yahoo_symbol, csv_sha256, response_sha256, rows,
null-OHLC drops counted — never filled — first/last bar, gap audit).
The sidecars produced by the 2026-11-15 probe are shipped in
results_data1/manifests.json; re-running this fetcher must reproduce
the same csv_sha256 for every completed bar (the final, possibly
partial, bar of a live fetch may differ — drop it at load if its date
is after the last completed session).

Usage:
  python3 -m rigorous_backtest.rd_data1.fetch_expansion --out-dir /path/to/cache
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
P1_DAILY = 1514764800          # 2018-01-01 UTC (RD-002 Stage-A window)
P2 = 1794787200                # 2026-11-16 UTC

# symbol -> (yahoo_symbol, oanda_instrument, asset_class)
SERIES: dict[str, tuple[str, str, str]] = {}
_FX_NEW = ["AUDCAD", "AUDCHF", "AUDHKD", "AUDSGD", "CADCHF", "CADHKD",
           "CADSGD", "CHFHKD", "CHFZAR", "EURCAD", "EURCZK", "EURDKK",
           "EURHKD", "EURHUF", "EURNOK", "EURSEK", "EURSGD", "EURTRY",
           "EURZAR", "GBPCAD", "GBPCHF", "GBPHKD", "GBPNZD", "GBPPLN",
           "GBPSGD", "GBPZAR", "HKDJPY", "NZDCAD", "NZDCHF", "NZDHKD",
           "NZDSGD", "SGDCHF", "SGDJPY", "TRYJPY", "USDCZK", "USDDKK",
           "USDHUF", "USDNOK", "USDPLN", "USDTHB", "ZARJPY"]
for _s in _FX_NEW:
    SERIES[_s] = (f"{_s}=X", f"{_s[:3]}_{_s[3:]}", "fx_cross_minor_exotic")
SERIES["PALLADIUM"] = ("PA=F", "XPD_USD", "metal_futures_proxy")
SERIES["CORN"] = ("ZC=F", "CORN_USD", "soft_futures_proxy")
SERIES["SOYBN"] = ("ZS=F", "SOYBN_USD", "soft_futures_proxy")
SERIES["SUGAR"] = ("SB=F", "SUGAR_USD", "soft_futures_proxy")
SERIES["WHEAT"] = ("ZW=F", "WHEAT_USD", "soft_futures_proxy")
for _s, _y, _o in [("AU200", "^AXJO", "AU200_AUD"), ("CH20", "^SSMI", "CH20_CHF"),
                   ("CHINAH", "^HSCE", "CHINAH_HKD"), ("EU50", "^STOXX50E", "EU50_EUR"),
                   ("FR40", "^FCHI", "FR40_EUR"), ("HK33", "^HSI", "HK33_HKD"),
                   ("NL25", "^AEX", "NL25_EUR"), ("SG30", "^STI", "SG30_SGD"),
                   ("ESPIX", "^IBEX", "ESPIX_EUR")]:
    SERIES[_s] = (_y, _o, "index_cfd")


def _fetch(url: str, attempts: int = 4) -> bytes:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - retried, then hard-fail
            last = exc
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"fetch failed after {attempts} attempts: {last}")


def fetch_one(symbol: str, yahoo: str, oanda: str, interval: str,
              out_dir: Path) -> dict:
    now = int(datetime.now(timezone.utc).timestamp())
    p1 = P1_DAILY if interval == "1d" else now - 729 * 86400
    q = urllib.parse.urlencode({"period1": p1, "period2": P2,
                                "interval": interval, "includePrePost": "false"})
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(yahoo, safe='')}?{q}")
    raw = _fetch(url)
    payload = json.loads(raw)
    result = payload["chart"]["result"][0]
    ts = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame({"open": quote["open"], "high": quote["high"],
                       "low": quote["low"], "close": quote["close"],
                       "volume": quote.get("volume")},
                      index=pd.to_datetime(ts, unit="s", utc=True))
    n_raw = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    dropped = n_raw - len(df)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df["volume"] = df["volume"].fillna(0.0)
    buf = io.StringIO()
    df.to_csv(buf, index_label="ts")
    csv_bytes = buf.getvalue().encode()
    csv_path = out_dir / f"YH_{symbol}_{interval}.csv"
    csv_path.write_bytes(csv_bytes)
    idx = df.index
    if interval == "1d":
        grid = pd.date_range(idx[0].normalize(), idx[-1].normalize(), freq="B")
        missing = int(len(grid) - len(df))
        note = "Mon-Fri grid; market holidays count as missing (upper bound)"
    else:
        diffs = idx.to_series().diff()
        big = diffs[diffs > pd.Timedelta(hours=2)]
        missing = int(sum(int(d / pd.Timedelta(hours=1)) - 1 for d in big))
        note = ("gaps = inter-bar jumps > 2h (weekends + holidays + outages "
                "combined); cash indices trade session hours only")
    manifest = {
        "source": "yahoo_finance_chart_api",
        "yahoo_symbol": result["meta"].get("symbol") or yahoo,
        "symbol": symbol, "timeframe": interval,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": int(len(df)), "null_ohlc_rows_dropped": int(dropped),
        "first_bar_utc": idx[0].isoformat(), "last_bar_utc": idx[-1].isoformat(),
        "gap_audit": {"missing_bars": missing, "grid_note": note},
        "oanda_instrument": oanda,
    }
    csv_path.with_suffix(".csv.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = args.only.split(",") if args.only else list(SERIES)
    for name in names:
        yahoo, oanda, _cls = SERIES[name]
        for interval in ("1d", "1h"):
            m = fetch_one(name, yahoo, oanda, interval, out_dir)
            print(f"[fetch] {name} {interval}: {m['rows']} bars "
                  f"{m['first_bar_utc']} -> {m['last_bar_utc']} "
                  f"dropped={m['null_ohlc_rows_dropped']}", flush=True)
            time.sleep(1.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
