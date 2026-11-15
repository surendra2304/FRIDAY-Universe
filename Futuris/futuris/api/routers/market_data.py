"""Market-data backbone API (TASK-IG-FUT-01).

``GET /v1/market-data/ohlcv`` is the HTTP face of the Futuris
market-data backbone -- the interface the Stratex lane consumes for
standardized, provenance-labelled OHLCV history.

Response discipline (FUT-005): when data was really fetched, the payload
says so (``status="ok"``, ``evidence_class="LIVE"``, the producing
provider and its source label). When no provider could produce real
data, the payload is ``status="unavailable"`` with an empty ``bars``
list and the reason in ``detail`` -- never placeholder bars.
"""

from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from futuris.core.enums import EvidenceClass
from futuris.infra.auth import RequireViewer
from futuris.market_data.models import OHLCVBar
from futuris.market_data.service import MarketDataBackbone

router = APIRouter(prefix="/v1/market-data", tags=["Market Data Backbone"])


class MarketDataResponse(BaseModel):
    """Backbone answer with its provenance worn on the outside."""

    status: str = Field(..., description="ok | unavailable")
    symbol: str
    interval: str
    provider: str | None = None
    source: str | None = None
    evidence_class: EvidenceClass | None = Field(
        default=None,
        description="LIVE when bars are real fetched data; null when unavailable.",
    )
    bars: list[OHLCVBar] = Field(default_factory=list)
    detail: str | None = None
    attempts: list[str] = Field(default_factory=list)
    fetched_at: datetime


@router.get("/ohlcv", response_model=MarketDataResponse, summary="Standardized OHLCV history")
async def get_ohlcv(
    user: RequireViewer,
    symbol: str = Query("BTCUSDT", description="Canonical symbol, e.g. BTCUSDT, EURUSD"),
    days: int = Query(90, ge=1, le=730, description="Lookback window in days"),
    interval: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|1d|1wk|1mo)$"),
) -> MarketDataResponse:
    """Fetch OHLCV history through the backbone's ordered providers."""
    _ = user
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    result = await MarketDataBackbone.from_settings().get_ohlcv(
        symbol=symbol, start=start, end=end, interval=interval
    )
    return MarketDataResponse(
        status=result.status,
        symbol=result.symbol,
        interval=result.interval,
        provider=result.provider,
        source=result.source,
        evidence_class=EvidenceClass.LIVE if result.status == "ok" else None,
        bars=result.bars,
        detail=result.detail,
        attempts=result.attempts,
        fetched_at=result.fetched_at,
    )
