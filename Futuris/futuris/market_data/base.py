"""Provider contract for the Futuris market-data backbone (TASK-IG-FUT-01).

A provider is a bounded adapter over one real data origin. The contract
is intentionally narrow -- historical OHLCV bars in, standardized result
out -- because that is the shape Futuris's forecast inputs consume, and
it is the shape the OpenBB Platform standardizes.

Implementations must obey three rules:

1. **Real data or an honest refusal.** On any failure return
   ``MarketDataResult.unavailable(...)`` with the reason. Never invent,
   interpolate, or backfill bars.
2. **Lazy and bounded.** Import nothing heavy at module import time; a
   provider module must be importable for registry/introspection without
   paying its runtime cost (the OpenBB SDK provider imports ``openbb``
   only inside its fetch method).
3. **Labelled output.** Every bar's ``source`` names this provider and
   the provider-side symbol, so ``futuris.connectors.provenance`` can
   derive the evidence class from what actually fed a forecast.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from futuris.market_data.models import MarketDataResult


class MarketDataProvider(ABC):
    """Abstract base for backbone providers."""

    #: Registry name; also the middle segment of every source label.
    name: str = "abstract"

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> MarketDataResult:
        """Fetch standardized OHLCV bars for ``symbol`` in [start, end].

        Returns ``status="ok"`` with real bars, or an ``unavailable``
        result explaining why no real data could be produced.
        """
        raise NotImplementedError

    def source_label(self, provider_symbol: str) -> str:
        """Provenance label for data this provider fetched."""
        return f"market_data:{self.name}:{provider_symbol}"
