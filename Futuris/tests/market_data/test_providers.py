"""Provider contract tests for the market-data backbone (TASK-IG-FUT-01).

Every provider is exercised through an in-memory httpx transport: real
payload shapes, real parsing -- and every failure mode must come back
as an explicit ``unavailable`` with zero bars, never fabricated data.
"""

import sys
from datetime import datetime, timezone

import httpx

from futuris.market_data.providers.openbb_sdk import OpenBBSDKProvider
from futuris.market_data.providers.stooq import StooqDailyProvider, to_stooq_symbol
from futuris.market_data.providers.yahoo import YahooChartProvider, to_yahoo_symbol

UTC = timezone.utc

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 10, tzinfo=UTC)


def transport_returning(response: httpx.Response) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: response)


# ---------------------------------------------------------------- Yahoo


def test_yahoo_symbol_mapping():
    assert to_yahoo_symbol("BTCUSDT") == "BTC-USD"
    assert to_yahoo_symbol("ethusdt") == "ETH-USD"
    assert to_yahoo_symbol("BTC-USD") == "BTC-USD"
    assert to_yahoo_symbol("^GSPC") == "^GSPC"


def _yahoo_payload() -> dict:
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [1767225600, 1767312000, 1767398400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, None, 102.0],
                                "high": [110.0, None, 112.0],
                                "low": [95.0, None, 97.0],
                                "close": [105.0, None, 108.0],
                                "volume": [1000, None, 1200],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


async def test_yahoo_success_drops_null_slots_never_fabricates():
    import json

    provider = YahooChartProvider(
        transport=transport_returning(
            httpx.Response(200, content=json.dumps(_yahoo_payload()))
        )
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert result.provider == "yahoo_chart"
    assert result.source == "market_data:yahoo_chart:BTC-USD"
    # The null middle bar is dropped -- not interpolated, not carried.
    assert len(result.bars) == 2
    assert [b.close for b in result.bars] == [105.0, 108.0]
    assert result.bars[0].provider_symbol == "BTC-USD"
    assert result.bars[0].volume == 1000.0


async def test_yahoo_http_error_is_unavailable_with_no_bars():
    provider = YahooChartProvider(
        transport=transport_returning(httpx.Response(503, text="down"))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert "503" in (result.detail or "")


async def test_yahoo_malformed_payload_is_unavailable():
    provider = YahooChartProvider(
        transport=transport_returning(httpx.Response(200, text="<html>nope</html>"))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []


async def test_yahoo_bad_interval_is_unavailable():
    provider = YahooChartProvider(
        transport=transport_returning(httpx.Response(200, text="{}"))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "3d")
    assert result.status == "unavailable"
    assert "interval" in (result.detail or "")


# ---------------------------------------------------------------- Stooq


def test_stooq_symbol_mapping():
    assert to_stooq_symbol("BTCUSDT") == "btcusd"
    assert to_stooq_symbol("EURUSD") == "eurusd"


_STOOQ_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2025-12-31,10,11,9,10.5,100\n"
    "2026-01-02,20,22,19,21.5,200\n"
    "2026-01-05,30,33,29,31.5,-\n"
)


async def test_stooq_success_filters_to_window():
    provider = StooqDailyProvider(
        transport=transport_returning(httpx.Response(200, text=_STOOQ_CSV))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert result.source == "market_data:stooq:btcusd"
    # 2025-12-31 is outside the requested window and excluded.
    assert [b.close for b in result.bars] == [21.5, 31.5]
    assert result.bars[1].volume is None  # "-" reported as absent, not zero


async def test_stooq_refuses_intraday_interval():
    provider = StooqDailyProvider(
        transport=transport_returning(httpx.Response(200, text=_STOOQ_CSV))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1h")
    assert result.status == "unavailable"
    assert "daily" in (result.detail or "")


async def test_stooq_http_error_is_unavailable():
    provider = StooqDailyProvider(
        transport=transport_returning(httpx.Response(404, text="no"))
    )
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []


# ------------------------------------------------------------- OpenBB SDK


async def test_openbb_sdk_absent_is_unavailable_and_names_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "openbb", None)
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert "not installed" in (result.detail or "")


async def test_openbb_sdk_bad_interval_is_unavailable():
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "3d")
    assert result.status == "unavailable"
