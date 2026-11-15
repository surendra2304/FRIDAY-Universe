"""MarketDataBackbone: the Futuris forecasting data backbone (TASK-IG-FUT-01).

An ordered registry of bounded providers behind one call. The first
provider that returns real data wins; every attempt is recorded on the
result, and when all providers fail the result is an explicit
``unavailable`` -- there is no synthetic fallback at this layer, by
design (FUT-005 provenance discipline).

This module is the interface the Stratex lane consumes:

* in-process: ``MarketDataBackbone.from_settings().get_ohlcv(...)``
  and ``to_observations(result)`` to feed the Futuris pipeline;
* over HTTP: ``GET /v1/market-data/ohlcv`` (see
  ``futuris/api/routers/market_data.py``).

Importing this module imports no provider runtime: provider classes are
imported lazily by the registry, and the OpenBB SDK provider in turn
imports ``openbb`` only inside its fetch (REL-048 footprint discipline).
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

from futuris.connectors.base import Observation
from futuris.infra.logging import get_logger
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult

logger = get_logger("futuris.market_data.backbone")

#: Registry: backbone name -> (module, class). Imported lazily on build.
PROVIDER_REGISTRY: dict[str, tuple[str, str]] = {
    "yahoo_chart": ("futuris.market_data.providers.yahoo", "YahooChartProvider"),
    "stooq": ("futuris.market_data.providers.stooq", "StooqDailyProvider"),
    "openbb_sdk": ("futuris.market_data.providers.openbb_sdk", "OpenBBSDKProvider"),
}

DEFAULT_PROVIDERS = "yahoo_chart,stooq"


def build_provider(name: str) -> MarketDataProvider:
    """Instantiate one registered provider by name (lazy import)."""
    key = name.strip()
    if key not in PROVIDER_REGISTRY:
        raise ValueError(
            f"unknown market-data provider {key!r}; registered: "
            f"{sorted(PROVIDER_REGISTRY)}"
        )
    module_path, class_name = PROVIDER_REGISTRY[key]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


class MarketDataBackbone:
    """Ordered provider failover for standardized OHLCV history."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("MarketDataBackbone needs at least one provider")
        self.providers = providers

    @classmethod
    def from_settings(cls, settings_obj=None) -> "MarketDataBackbone":
        """Build from ``FUTURIS_MARKET_DATA_PROVIDERS`` (comma-ordered)."""
        if settings_obj is None:
            from futuris.infra.config import settings

            settings_obj = settings
        configured = getattr(
            settings_obj, "FUTURIS_MARKET_DATA_PROVIDERS", DEFAULT_PROVIDERS
        )
        names = [n for n in (p.strip() for p in configured.split(",")) if n]
        return cls([build_provider(n) for n in names])

    async def get_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> MarketDataResult:
        """First real answer wins; total failure is an explicit unavailable."""
        attempts: list[str] = []
        reasons: list[str] = []
        for provider in self.providers:
            try:
                result = await provider.fetch_ohlcv(symbol, start, end, interval)
            except Exception as exc:  # a provider must refuse, not raise --
                # but the backbone never lets one provider's bug fabricate
                # or hide the outcome; it records and moves on.
                logger.warning(
                    "market_data_provider_raised",
                    provider=provider.name,
                    error=type(exc).__name__,
                )
                attempts.append(f"{provider.name}: raised {type(exc).__name__}")
                reasons.append(f"{provider.name}: raised {type(exc).__name__}")
                continue
            if result.attempts:
                attempts.extend(result.attempts)
            elif result.status == "ok":
                attempts.append(f"{provider.name}: ok")
            else:
                attempts.append(f"{provider.name}: unavailable")
            if result.status == "ok":
                result.attempts = attempts
                return result
            if result.detail:
                reasons.append(f"{provider.name}: {result.detail}")
        return MarketDataResult.unavailable(
            symbol=symbol.upper().strip(),
            interval=interval,
            detail="all configured market-data providers unavailable: "
            + "; ".join(reasons or attempts),
            fetched_at=datetime.now(UTC),
            attempts=attempts,
        )


def to_observations(result: MarketDataResult) -> list[Observation]:
    """Convert an ok result into Futuris pipeline observations.

    One observation per bar on the close series
    (``market:<SYMBOL>:close``); the full bar rides in ``tags`` so no
    fetched field is dropped. An unavailable result converts to an
    empty list -- absence, never invented points.
    """
    if result.status != "ok":
        return []
    observations: list[Observation] = []
    for bar in result.bars:
        observations.append(
            Observation(
                observed_at=bar.timestamp,
                source=bar.source,
                series_id=f"market:{bar.symbol}:close",
                value=bar.close,
                unit="price",
                tags={
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "volume": bar.volume,
                    "provider": bar.provider,
                    "provider_symbol": bar.provider_symbol,
                    "interval": result.interval,
                },
            )
        )
    return observations
