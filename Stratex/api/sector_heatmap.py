"""
api/sector_heatmap.py — Live sector heatmap for the Stratex dashboard
(TASK-IG2-WEB-04, OpenTerminal pattern ADAPT).

OpenTerminal's transferable lesson is a one-glance sector tile view built
entirely on free public market data. This blueprint computes sector
performance from free Stooq daily quotes (no API key, no subscription):
each sector is a basket of liquid US names plus its SPDR sector ETF, the
sector change is the mean of the members' latest daily % changes, and the
dashboard renders it as coloured tiles.

Honesty rules (fleet standard):
- A symbol whose quote cannot be fetched is reported as unavailable, never
  guessed. A sector with no available members reports change=None and the
  UI renders a neutral "unavailable" tile — no invented numbers.
- Responses carry `as_of`, `source` and a per-symbol breakdown so the tile
  can always be traced back to the quotes it was computed from.
- Results are cached in-process for CACHE_TTL_SECONDS; the fleet's RAM cap
  makes a cache of a few KB the right size, and Stooq is never polled per
  dashboard request.

Stdlib only (urllib/csv/threading) + Flask, matching the dashboard's
existing blueprint pattern. Registered in dashboard.py core_blueprints.
"""

from __future__ import annotations

import csv
import io
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from flask import Blueprint, jsonify

sector_heatmap_bp = Blueprint("sector_heatmap", __name__, url_prefix="/api/v1")

STOOQ_DAILY_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
FETCH_TIMEOUT_SECONDS = 4.0
CACHE_TTL_SECONDS = 60.0
MAX_WORKERS = 8

# Sector baskets: (display symbol, Stooq symbol). Stooq uses lowercase
# tickers with a .us suffix for US listings; crypto pairs have no suffix.
SECTORS: dict[str, list[tuple[str, str]]] = {
    "Technology": [("XLK", "xlk.us"), ("AAPL", "aapl.us"), ("MSFT", "msft.us"), ("NVDA", "nvda.us")],
    "Financials": [("XLF", "xlf.us"), ("JPM", "jpm.us"), ("BAC", "bac.us")],
    "Healthcare": [("XLV", "xlv.us"), ("UNH", "unh.us"), ("LLY", "lly.us")],
    "Energy": [("XLE", "xle.us"), ("XOM", "xom.us"), ("CVX", "cvx.us")],
    "Consumer Discretionary": [("XLY", "xly.us"), ("AMZN", "amzn.us"), ("TSLA", "tsla.us")],
    "Consumer Staples": [("XLP", "xlp.us"), ("WMT", "wmt.us"), ("PG", "pg.us")],
    "Industrials": [("XLI", "xli.us"), ("CAT", "cat.us"), ("HON", "hon.us")],
    "Materials": [("XLB", "xlb.us"), ("LIN", "lin.us")],
    "Utilities": [("XLU", "xlu.us"), ("NEE", "nee.us")],
    "Real Estate": [("XLRE", "xlre.us"), ("PLD", "pld.us")],
    "Communication": [("XLC", "xlc.us"), ("META", "meta.us"), ("GOOGL", "googl.us")],
    "Crypto": [("BTC/USD", "btcusd"), ("ETH/USD", "ethusd")],
}


def parse_stooq_daily(csv_text: str) -> tuple[float, float] | None:
    """Return (latest_close, previous_close) from a Stooq daily CSV.

    Stooq returns rows oldest-first with a header; days with no trading
    carry 'N/D' fields and are skipped. Returns None when fewer than two
    usable closes exist (the change would be invented, so we refuse).
    """
    closes: list[float] = []
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            raw = (row.get("Close") or "").strip()
            if not raw or raw == "N/D":
                continue
            try:
                closes.append(float(raw))
            except ValueError:
                continue
    except (csv.Error, AttributeError):
        return None
    if len(closes) < 2:
        return None
    return closes[-1], closes[-2]


def pct_change(latest: float, previous: float) -> float | None:
    """Daily % change, or None when the base is unusable."""
    if previous == 0:
        return None
    return (latest - previous) / previous * 100.0


def aggregate_sector(members: list[dict]) -> float | None:
    """Mean of available member changes; None when no member has data."""
    changes = [m["change_pct"] for m in members if m.get("change_pct") is not None]
    if not changes:
        return None
    return sum(changes) / len(changes)


def _fetch_symbol_change(stooq_symbol: str, opener=urllib.request.urlopen) -> float | None:
    """Fetch one symbol's daily % change from Stooq; None on any failure."""
    url = STOOQ_DAILY_URL.format(symbol=stooq_symbol)
    request = urllib.request.Request(url, headers={"User-Agent": "FRIDAY-Stratex/heatmap"})
    try:
        with opener(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    parsed = parse_stooq_daily(text)
    if parsed is None:
        return None
    return pct_change(*parsed)


def build_heatmap(fetch=_fetch_symbol_change) -> dict:
    """Compute the full heatmap payload. `fetch` is injectable for tests."""
    symbols = sorted({stooq for basket in SECTORS.values() for _, stooq in basket})
    changes: dict[str, float | None] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for symbol, change in zip(symbols, pool.map(fetch, symbols)):
            changes[symbol] = change

    sectors = []
    for name, basket in SECTORS.items():
        members = [
            {
                "symbol": display,
                "change_pct": (round(changes[stooq], 3) if changes.get(stooq) is not None else None),
            }
            for display, stooq in basket
        ]
        sector_change = aggregate_sector(members)
        sectors.append(
            {
                "sector": name,
                "change_pct": (round(sector_change, 3) if sector_change is not None else None),
                "members_available": sum(1 for m in members if m["change_pct"] is not None),
                "members_total": len(members),
                "members": members,
            }
        )
    # Strongest first; sectors without data sink to the bottom, named as such.
    sectors.sort(key=lambda s: (s["change_pct"] is None, -(s["change_pct"] or 0.0)))
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "stooq (free daily quotes)",
        "sectors": sectors,
    }


_cache: dict = {"payload": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def get_heatmap() -> dict:
    """Cached heatmap payload; refetches at most once per TTL window."""
    now = time.monotonic()
    with _cache_lock:
        if _cache["payload"] is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
            return _cache["payload"]
    payload = build_heatmap()
    with _cache_lock:
        _cache["payload"] = payload
        _cache["fetched_at"] = time.monotonic()
    return payload


@sector_heatmap_bp.route("/market/sector-heatmap", methods=["GET"])
def sector_heatmap():
    """GET /api/v1/market/sector-heatmap — sector tiles for the dashboard."""
    return jsonify(get_heatmap())
