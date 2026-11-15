"""Stooq daily-bars provider (TASK-IG-FUT-01).

Stooq publishes free daily OHLCV history as plain CSV with no API key.
It is the backbone's second real origin: tiny payloads, stdlib-parseable,
and an independent failure domain from Yahoo. Daily bars only -- other
intervals are refused honestly rather than resampled (a resampled bar
would be derived data wearing a measured label).

Honesty contract: any transport error, non-200 response, malformed CSV,
or empty series yields an ``unavailable`` result with the reason.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

import httpx

from futuris.infra.logging import get_logger
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar

logger = get_logger("futuris.market_data.stooq")

_CSV_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def to_stooq_symbol(symbol: str) -> str:
    """Map a canonical Futuris symbol to Stooq's naming (``btcusd``)."""
    clean = symbol.upper().strip()
    if clean.endswith("USDT"):
        clean = clean[: -len("USDT")] + "USD"
    return clean.lower()


class StooqDailyProvider(MarketDataProvider):
    """Free daily OHLCV from Stooq's CSV endpoint (no API key)."""

    name = "stooq"

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
        if interval != "1d":
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"stooq serves daily bars only, not interval {interval!r}",
                fetched_at=fetched_at,
            )
        provider_symbol = to_stooq_symbol(symbol)
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                resp = await client.get(
                    _CSV_URL.format(symbol=provider_symbol),
                    headers={"User-Agent": "Futuris-MarketData/1.0"},
                )
        except Exception as exc:  # transport-level failure: honest refusal
            logger.warning("stooq_fetch_failed", symbol=symbol, error=type(exc).__name__)
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"stooq request failed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )
        if resp.status_code != 200:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"stooq returned HTTP {resp.status_code}",
                fetched_at=fetched_at,
            )

        source = self.source_label(provider_symbol)
        bars: list[OHLCVBar] = []
        try:
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                day = datetime.strptime(row["Date"].strip(), "%Y-%m-%d").replace(
                    tzinfo=UTC
                )
                if day < start or day > end:
                    continue
                volume_raw = (row.get("Volume") or "").strip()
                bars.append(
                    OHLCVBar(
                        symbol=symbol.upper().strip(),
                        provider_symbol=provider_symbol,
                        timestamp=day,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(volume_raw) if volume_raw not in ("", "-") else None,
                        provider=self.name,
                        source=source,
                    )
                )
        except Exception as exc:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"stooq payload malformed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )
        if not bars:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail="stooq returned no bars for the window",
                fetched_at=fetched_at,
            )
        bars.sort(key=lambda b: b.timestamp)
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
