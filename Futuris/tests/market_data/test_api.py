"""API surface tests for GET /v1/market-data/ohlcv (TASK-IG-FUT-01).

The endpoint handler is called directly with the backbone stubbed --
the contract under test is the response shaping: real data is labelled
LIVE with its provider; unavailability is explicit and bar-free.
"""

from datetime import datetime, timezone

from futuris.api.routers import market_data as market_data_router
from futuris.core.enums import EvidenceClass
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar
from futuris.market_data.service import MarketDataBackbone

UTC = timezone.utc
NOW = datetime(2026, 1, 5, tzinfo=UTC)


class _StubProvider(MarketDataProvider):
    name = "stub"

    def __init__(self, result: MarketDataResult) -> None:
        self._result = result

    async def fetch_ohlcv(self, symbol, start, end, interval="1d"):
        return self._result


def _ok_result() -> MarketDataResult:
    source = "market_data:stub:BTC-USD"
    return MarketDataResult(
        status="ok", symbol="BTCUSDT", interval="1d", provider="stub",
        source=source,
        bars=[
            OHLCVBar(
                symbol="BTCUSDT", provider_symbol="BTC-USD", timestamp=NOW,
                open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0,
                provider="stub", source=source,
            )
        ],
        attempts=["stub: ok (1 bars)"], fetched_at=NOW,
    )


async def _call(monkeypatch, result: MarketDataResult):
    backbone = MarketDataBackbone([_StubProvider(result)])
    monkeypatch.setattr(
        market_data_router.MarketDataBackbone,
        "from_settings",
        classmethod(lambda cls: backbone),
    )
    return await market_data_router.get_ohlcv(
        user=object(), symbol="BTCUSDT", days=90, interval="1d"
    )


async def test_ok_response_is_labelled_live_with_provider(monkeypatch):
    response = await _call(monkeypatch, _ok_result())
    assert response.status == "ok"
    assert response.evidence_class is EvidenceClass.LIVE
    assert response.provider == "stub"
    assert response.source == "market_data:stub:BTC-USD"
    assert len(response.bars) == 1


async def test_unavailable_response_is_explicit_and_bar_free(monkeypatch):
    down = MarketDataResult.unavailable(
        symbol="BTCUSDT", interval="1d", detail="all configured providers down",
        fetched_at=NOW, attempts=["stub: unavailable"],
    )
    response = await _call(monkeypatch, down)
    assert response.status == "unavailable"
    assert response.evidence_class is None
    assert response.bars == []
    assert response.detail and "down" in response.detail
