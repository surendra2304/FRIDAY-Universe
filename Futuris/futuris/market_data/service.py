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
from futuris.market_data.models import MarketDataResult, ProviderStatus

logger = get_logger("futuris.market_data.backbone")

#: Registry: backbone name -> (module, class). Imported lazily on build.
PROVIDER_REGISTRY: dict[str, tuple[str, str]] = {
    "yahoo_chart": ("futuris.market_data.providers.yahoo", "YahooChartProvider"),
    "stooq": ("futuris.market_data.providers.stooq", "StooqDailyProvider"),
    "openbb_sdk": ("futuris.market_data.providers.openbb_sdk", "OpenBBSDKProvider"),
}

#: Provider name -> status-surface kind (see ProviderStatus).
_PROVIDER_KIND: dict[str, str] = {
    "yahoo_chart": "http",
    "stooq": "http",
    "openbb_sdk": "sdk",
}

DEFAULT_PROVIDERS = "yahoo_chart,stooq"

#: OpenBB provider extension used when settings do not name one (free,
#: keyless -- the only class of extension the FREE-only rule allows by
#: default).
DEFAULT_OPENBB_PROVIDER = "yfinance"


def build_provider(name: str, *, obb_provider: str | None = None) -> MarketDataProvider:
    """Instantiate one registered provider by name (lazy import).

    ``obb_provider`` applies only to ``openbb_sdk``: it selects the
    OpenBB provider extension the SDK routes through. It is a setting,
    not a code edit, so the post-ARM adoption can change it by config.
    """
    key = name.strip()
    if key not in PROVIDER_REGISTRY:
        raise ValueError(
            f"unknown market-data provider {key!r}; registered: "
            f"{sorted(PROVIDER_REGISTRY)}"
        )
    module_path, class_name = PROVIDER_REGISTRY[key]
    module = importlib.import_module(module_path)
    provider_cls = getattr(module, class_name)
    if key == "openbb_sdk" and obb_provider:
        return provider_cls(obb_provider=obb_provider)
    return provider_cls()


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
        obb_provider = getattr(
            settings_obj, "FUTURIS_OPENBB_PROVIDER", DEFAULT_OPENBB_PROVIDER
        )
        return cls([build_provider(n, obb_provider=obb_provider) for n in names])

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


def provider_statuses(settings_obj=None) -> list[ProviderStatus]:
    """Local readiness of every configured provider, in configured order.

    The graceful-degradation surface for the data layer: an operator (or
    the ARM-day runbook) can confirm which providers this host can
    actually serve before any fetch is attempted. Only local
    preconditions are checked -- for ``openbb_sdk`` that is whether the
    SDK is installed (probed without importing it); network providers
    honestly report ``available=None`` because their availability is a
    per-fetch fact, never a guess. An unregistered configured name is
    reported as unavailable rather than raising, so the status surface
    itself can never take the service down.
    """
    if settings_obj is None:
        from futuris.infra.config import settings

        settings_obj = settings
    configured = getattr(
        settings_obj, "FUTURIS_MARKET_DATA_PROVIDERS", DEFAULT_PROVIDERS
    )
    names = [n for n in (p.strip() for p in configured.split(",")) if n]
    statuses: list[ProviderStatus] = []
    for name in names:
        kind = _PROVIDER_KIND.get(name, "http")
        if name not in PROVIDER_REGISTRY:
            statuses.append(
                ProviderStatus(
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    available=False,
                    detail=(
                        f"not a registered provider; registered: "
                        f"{sorted(PROVIDER_REGISTRY)}"
                    ),
                )
            )
        elif name == "openbb_sdk":
            from futuris.market_data.providers.openbb_sdk import sdk_available

            installed = sdk_available()
            statuses.append(
                ProviderStatus(
                    name=name,
                    kind="sdk",
                    available=installed,
                    detail=None
                    if installed
                    else (
                        "openbb SDK is not installed in this environment "
                        "(post-ARM adoption path; see docs/DATA_BACKBONE_IGFUT01.md)"
                    ),
                )
            )
        else:
            statuses.append(
                ProviderStatus(
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    available=None,
                    detail="network provider; availability is determined per fetch",
                )
            )
    return statuses


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
