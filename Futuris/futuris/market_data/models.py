"""Standardized market-data records (TASK-IG-FUT-01).

The shapes here deliberately mirror the OpenBB Platform's data model --
a provider returns an ``OBBject``-style envelope whose ``results`` are
standardized records with provider attribution attached -- so that the
real OpenBB SDK can be dropped in behind the same interface later (see
``providers/openbb_sdk.py`` and ``docs/DATA_BACKBONE_IGFUT01.md``).

Provenance discipline (FUT-005 / REL-018) binds absolutely:

* every bar carries the provider that produced it and a ``source`` label
  naming the real origin system;
* a provider that cannot fetch returns ``status="unavailable"`` with an
  empty result list and a stated reason -- it NEVER fabricates bars,
  interpolates missing values, or substitutes placeholder prices.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OHLCVBar(BaseModel):
    """One standardized OHLCV bar (OpenBB ``EquityHistorical``-style fields)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., description="Canonical Futuris symbol (e.g. BTCUSDT).")
    provider_symbol: str = Field(
        ..., description="Symbol as named at the provider (e.g. BTC-USD at Yahoo)."
    )
    timestamp: datetime = Field(..., description="Bar open time, UTC.")
    open: float
    high: float
    low: float
    close: float
    volume: float | None = Field(
        default=None, description="Traded volume; None when the provider reports none."
    )
    provider: str = Field(..., description="Backbone provider name (e.g. yahoo_chart).")
    source: str = Field(
        ...,
        description="Full provenance label, e.g. 'market_data:yahoo_chart:BTC-USD'.",
    )


class MarketDataResult(BaseModel):
    """OBBject-style envelope: standardized results + provider attribution.

    ``status`` is ``"ok"`` only when ``bars`` holds real fetched data.
    Any failure -- network, HTTP error, malformed payload, empty series,
    uninstalled optional SDK -- is reported as ``"unavailable"`` with the
    reason in ``detail`` and an empty ``bars`` list.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unavailable"]
    symbol: str = Field(..., description="Canonical Futuris symbol requested.")
    interval: str = Field(..., description="Bar interval requested (e.g. 1d, 1h).")
    provider: str | None = Field(
        default=None,
        description="Provider that produced the bars; None when none could.",
    )
    source: str | None = Field(
        default=None,
        description="Provenance label of the producing provider; None when unavailable.",
    )
    bars: list[OHLCVBar] = Field(default_factory=list)
    detail: str | None = Field(
        default=None, description="Why the data is unavailable, when it is."
    )
    attempts: list[str] = Field(
        default_factory=list,
        description="Per-provider attempt outcomes, in the order tried.",
    )
    fetched_at: datetime = Field(..., description="When the fetch was performed, UTC.")

    @classmethod
    def unavailable(
        cls,
        *,
        symbol: str,
        interval: str,
        detail: str,
        fetched_at: datetime,
        attempts: list[str] | None = None,
    ) -> "MarketDataResult":
        """Build an honest empty result: no bars, a named reason."""
        return cls(
            status="unavailable",
            symbol=symbol,
            interval=interval,
            provider=None,
            source=None,
            bars=[],
            detail=detail,
            attempts=attempts or [],
            fetched_at=fetched_at,
        )
