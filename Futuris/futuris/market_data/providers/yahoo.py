"""Yahoo Finance chart API provider (TASK-IG-FUT-01).

Reads the public Yahoo Finance chart endpoint -- the same keyless data
origin the OpenBB ``yfinance`` provider wraps -- over Futuris's existing
``httpx`` dependency. No API key, no new dependency.

Honesty contract: any transport error, non-200 response, malformed
payload, or empty series yields an ``unavailable`` result with the
reason. Null OHLC slots in Yahoo's payload (suspended/holiday bars) are
dropped, never interpolated.
"""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

import httpx

from futuris.infra.logging import get_logger
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar

logger = get_logger("futuris.market_data.yahoo")

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

#: Yahoo chart intervals this provider will request.
SUPPORTED_INTERVALS = ("1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo")


def to_yahoo_symbol(symbol: str) -> str:
    """Map a canonical Futuris symbol to Yahoo's naming.

    ``BTCUSDT`` -> ``BTC-USD``; an already provider-shaped symbol
    (contains ``-``, ``=`` or ``^``) passes through unchanged.
    """
    clean = symbol.upper().strip()
    if any(ch in clean for ch in ("-", "=", "^", ".")):
        return clean
    for quote in ("USDT", "USDC", "USD"):
        if clean.endswith(quote) and len(clean) > len(quote):
            return f"{clean[: -len(quote)]}-USD"
    return clean


class YahooChartProvider(MarketDataProvider):
    """Keyless OHLCV from Yahoo Finance's public chart endpoint."""

    name = "yahoo_chart"

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def fetch_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> MarketDataResult:
        fetched_at = datetime.now(UTC)
        if interval not in SUPPORTED_INTERVALS:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"yahoo_chart does not support interval {interval!r}",
                fetched_at=fetched_at,
            )
        provider_symbol = to_yahoo_symbol(symbol)
        params = {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": interval,
            "events": "history",
        }
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                resp = await client.get(
                    _CHART_URL.format(symbol=provider_symbol),
                    params=params,
                    headers={"User-Agent": "Futuris-MarketData/1.0"},
                )
        except Exception as exc:  # transport-level failure: honest refusal
            logger.warning(
                "yahoo_chart_fetch_failed", symbol=symbol, error=type(exc).__name__
            )
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"yahoo_chart request failed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )
        if resp.status_code != 200:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"yahoo_chart returned HTTP {resp.status_code}",
                fetched_at=fetched_at,
            )
        try:
            payload = resp.json()
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            opens, highs = quote["open"], quote["high"]
            lows, closes = quote["low"], quote["close"]
            volumes = quote.get("volume") or [None] * len(timestamps)
        except Exception as exc:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"yahoo_chart payload malformed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )

        source = self.source_label(provider_symbol)
        bars: list[OHLCVBar] = []
        try:
            for idx, ts in enumerate(timestamps):
                o, h, low_, c = opens[idx], highs[idx], lows[idx], closes[idx]
                if o is None or h is None or low_ is None or c is None:
                    continue  # suspended/holiday slot: drop, never fabricate
                bars.append(
                    OHLCVBar(
                        symbol=symbol.upper().strip(),
                        provider_symbol=provider_symbol,
                        timestamp=datetime.fromtimestamp(int(ts), tz=UTC),
                        open=float(o),
                        high=float(h),
                        low=float(low_),
                        close=float(c),
                        volume=float(volumes[idx]) if volumes[idx] is not None else None,
                        provider=self.name,
                        source=source,
                    )
                )
        except Exception as exc:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"yahoo_chart payload malformed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )
        if not bars:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail="yahoo_chart returned no usable bars for the window",
                fetched_at=fetched_at,
            )
        return MarketDataResult(
            status="ok",
            symbol=symbol.upper().strip(),
            interval=interval,
            provider=self.name,
            source=source,
            bars=bars,
            attempts=[f"{self.name}: ok ({len(bars)} bars)"],
            fetched_at=fetched_at,
        )
