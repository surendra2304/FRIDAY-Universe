"""
market_data_fallback.py — Free market-data fallback chain (TASK-IG2-STR-10).

Pattern adopted from OpenTerminal (ErTasselli, MIT, reference-only): stitch
market data from FREE public endpoints with ordered fallback chains per
data type, so a single dead free endpoint degrades Stratex/Futuris data
instead of blinding it.

Chains (all free, no API keys):
- crypto_price : Binance public ticker -> CoinGecko simple/price -> DexScreener
- equity_price : Nasdaq quote API -> Stooq CSV -> Yahoo chart API
- fx_price     : Stooq CSV -> Yahoo chart API
- macro_series : FRED fredgraph CSV (keyless) — single source, cached

Behaviour:
- Providers are tried in order; the first success wins and is cached as
  last-good (in memory, optionally persisted to a small JSON file).
- If every provider fails, the last-good value is returned with
  ``stale=True`` and its age; only when nothing was ever fetched does the
  chain raise :class:`AllProvidersFailed`.
- Every result names its provider — callers can see exactly which free
  endpoint served a number (the fleet's verification standard).
- Transport is injectable (``fetch_text``) so the whole chain is
  unit-testable without network. DEMO-ONLY context: read-only market data,
  no trading endpoints, no credentials anywhere in this module.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional

try:
    from logger import get_logger
except Exception:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore
        return logging.getLogger(name)


logger = get_logger("market_data_fallback")

USER_AGENT = "FRIDAY-Stratex-Research/1.0 (+free public data)"


class AllProvidersFailed(RuntimeError):
    """Every provider in the chain failed and no last-good value exists."""


@dataclass
class PriceQuote:
    symbol: str
    price: float
    provider: str
    fetched_at: float
    stale: bool = False
    currency: str = "USD"
    extra: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.extra is None:
            self.extra = {}

    @property
    def age_s(self) -> float:
        return max(0.0, time.time() - self.fetched_at)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Transport (injectable)
# ---------------------------------------------------------------------------

def default_fetch_text(url: str, timeout: float = 12.0) -> str:
    import requests  # already a Stratex dependency

    resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _get_json(fetch: Callable[[str], str], url: str) -> Any:
    return json.loads(fetch(url))


# ---------------------------------------------------------------------------
# Provider implementations: each returns a PriceQuote or raises.
# Symbol conventions: crypto uses Binance-style 'BTCUSDT' (or bare 'BTC');
# equities use the ticker ('AAPL'); FX uses pairs ('USDJPY' or 'USD/JPY').
# ---------------------------------------------------------------------------

_COINGECKO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
                  "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin",
                  "LTC": "litecoin", "LINK": "chainlink", "AVAX": "avalanche-2",
                  "MATIC": "matic-network", "DOT": "polkadot"}


def _crypto_base(symbol: str) -> str:
    sym = symbol.upper().replace("/", "")
    for quote in ("USDT", "USDC", "USD"):
        if sym.endswith(quote):
            return sym[: -len(quote)]
    return sym


def binance_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    sym = symbol.upper().replace("/", "")
    if sym in _COINGECKO_IDS:  # bare base symbol -> default USDT pair
        sym = sym + "USDT"
    data = _get_json(fetch, f"https://api.binance.com/api/v3/ticker/price?symbol={sym}")
    return PriceQuote(symbol=symbol.upper(), price=float(data["price"]),
                      provider="binance", fetched_at=time.time())


def coingecko_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    base = _crypto_base(symbol)
    cg_id = _COINGECKO_IDS.get(base)
    if not cg_id:
        raise ValueError(f"no CoinGecko id mapping for {base}")
    data = _get_json(fetch, "https://api.coingecko.com/api/v3/simple/price"
                            f"?ids={cg_id}&vs_currencies=usd")
    return PriceQuote(symbol=symbol.upper(), price=float(data[cg_id]["usd"]),
                      provider="coingecko", fetched_at=time.time())


def dexscreener_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    base = _crypto_base(symbol)
    data = _get_json(fetch, f"https://api.dexscreener.com/latest/dex/search?q={base}")
    best: Optional[dict[str, Any]] = None
    for pair in data.get("pairs") or []:
        if (pair.get("baseToken") or {}).get("symbol", "").upper() != base:
            continue
        if best is None or float((pair.get("liquidity") or {}).get("usd") or 0) > \
                float((best.get("liquidity") or {}).get("usd") or 0):
            best = pair
    if not best:
        raise ValueError(f"no DexScreener pair for {base}")
    return PriceQuote(symbol=symbol.upper(), price=float(best["priceUsd"]),
                      provider="dexscreener", fetched_at=time.time(),
                      extra={"pair": best.get("pairAddress", "")})


def nasdaq_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    sym = symbol.upper()
    data = _get_json(fetch, f"https://api.nasdaq.com/api/quote/{sym}/info?assetclass=stocks")
    primary = ((data.get("data") or {}).get("primaryData") or {})
    raw = str(primary.get("lastSalePrice") or "").replace("$", "").replace(",", "")
    if not raw:
        raise ValueError(f"Nasdaq returned no price for {sym}")
    return PriceQuote(symbol=sym, price=float(raw), provider="nasdaq",
                      fetched_at=time.time())


def stooq_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    """Stooq free CSV quotes: equities as AAPL.US, FX as USDJPY, indices ^SPX."""
    sym = symbol.upper().replace("/", "")
    if len(sym) == 6 and sym.isalpha():  # FX pair like USDJPY
        code = sym.lower()
    elif sym.startswith("^"):
        code = sym.lower()
    else:
        code = sym.lower() + ".us"
    text = fetch(f"https://stooq.com/q/l/?s={code}&f=sd2t2ohlcv&h&e=csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or rows[0].get("Close") in (None, "", "N/D"):
        raise ValueError(f"Stooq returned no quote for {symbol}")
    return PriceQuote(symbol=symbol.upper(), price=float(rows[0]["Close"]),
                      provider="stooq", fetched_at=time.time(),
                      extra={"date": rows[0].get("Date", ""), "time": rows[0].get("Time", "")})


def yahoo_price(symbol: str, fetch: Callable[[str], str]) -> PriceQuote:
    sym = symbol.upper()
    if len(sym) == 6 and sym.isalpha() and "/" not in symbol:
        sym = sym + "=X"  # FX pair convention on Yahoo
    data = _get_json(fetch, f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}")
    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError(f"Yahoo returned no chart for {symbol}")
    price = (result.get("meta") or {}).get("regularMarketPrice")
    if price is None:
        raise ValueError(f"Yahoo chart has no price for {symbol}")
    return PriceQuote(symbol=symbol.upper(), price=float(price), provider="yahoo",
                      fetched_at=time.time())


def fred_series_latest(series_id: str, fetch: Callable[[str], str]) -> tuple[str, float]:
    """Latest observation of a FRED series via the keyless fredgraph CSV."""
    text = fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")
    rows = [r for r in csv.DictReader(io.StringIO(text))
            if r.get(series_id) not in (None, "", ".")]
    if not rows:
        raise ValueError(f"FRED returned no data for {series_id}")
    last = rows[-1]
    return last["DATE"], float(last[series_id])


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

ProviderFn = Callable[[str, Callable[[str], str]], PriceQuote]

CHAINS: dict[str, list[ProviderFn]] = {
    "crypto_price": [binance_price, coingecko_price, dexscreener_price],
    "equity_price": [nasdaq_price, stooq_price, yahoo_price],
    "fx_price": [stooq_price, yahoo_price],
}


class FallbackChain:
    """Ordered provider fallback with last-good caching per (kind, symbol)."""

    def __init__(self, fetch_text: Callable[[str], str] = default_fetch_text,
                 cache_path: Optional[str] = None,
                 chains: Optional[dict[str, list[ProviderFn]]] = None):
        self.fetch_text = fetch_text
        self.cache_path = cache_path
        self.chains = chains or CHAINS
        self._cache: dict[str, PriceQuote] = {}
        self._load_cache()

    # -- cache ---------------------------------------------------------------
    def _key(self, kind: str, symbol: str) -> str:
        return f"{kind}:{symbol.upper()}"

    def _load_cache(self) -> None:
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, encoding="utf-8") as fh:
                    for key, row in json.load(fh).items():
                        self._cache[key] = PriceQuote(**row)
            except (json.JSONDecodeError, OSError, TypeError):
                logger.warning("[FALLBACK] cache file unreadable; starting empty")

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump({k: q.to_dict() for k, q in self._cache.items()}, fh)
        except OSError as exc:
            logger.warning(f"[FALLBACK] cache save failed: {exc}")

    # -- queries ---------------------------------------------------------------
    def get_price(self, kind: str, symbol: str) -> PriceQuote:
        """First live provider wins; else last-good (stale); else raise."""
        providers = self.chains.get(kind)
        if not providers:
            raise ValueError(f"unknown data kind {kind!r}; known: {sorted(self.chains)}")
        errors: list[str] = []
        for provider in providers:
            try:
                quote = provider(symbol, self.fetch_text)
                self._cache[self._key(kind, symbol)] = quote
                self._save_cache()
                return quote
            except Exception as exc:  # try the next free provider
                errors.append(f"{provider.__name__}: {exc}")
        cached = self._cache.get(self._key(kind, symbol))
        if cached is not None:
            logger.warning(f"[FALLBACK] all providers failed for {kind}/{symbol} "
                           f"({'; '.join(errors)}); serving last-good from "
                           f"{cached.provider} aged {cached.age_s:.0f}s")
            return PriceQuote(symbol=cached.symbol, price=cached.price,
                              provider=cached.provider, fetched_at=cached.fetched_at,
                              stale=True, currency=cached.currency,
                              extra=dict(cached.extra))
        raise AllProvidersFailed(f"{kind}/{symbol}: " + "; ".join(errors))

    def get_crypto_price(self, symbol: str) -> PriceQuote:
        return self.get_price("crypto_price", symbol)

    def get_equity_price(self, symbol: str) -> PriceQuote:
        return self.get_price("equity_price", symbol)

    def get_fx_price(self, symbol: str) -> PriceQuote:
        return self.get_price("fx_price", symbol)

    def get_macro_latest(self, series_id: str) -> dict[str, Any]:
        """FRED latest value with last-good behaviour via the price cache."""
        try:
            date, value = fred_series_latest(series_id, self.fetch_text)
            quote = PriceQuote(symbol=series_id, price=value, provider="fred",
                               fetched_at=time.time(), extra={"date": date})
            self._cache[self._key("macro_series", series_id)] = quote
            self._save_cache()
            return {"series": series_id, "date": date, "value": value,
                    "provider": "fred", "stale": False}
        except Exception as exc:
            cached = self._cache.get(self._key("macro_series", series_id))
            if cached is not None:
                return {"series": series_id, "date": cached.extra.get("date", ""),
                        "value": cached.price, "provider": "fred", "stale": True}
            raise AllProvidersFailed(f"macro_series/{series_id}: fred: {exc}") from exc
