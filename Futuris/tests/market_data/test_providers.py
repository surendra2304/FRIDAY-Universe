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


# The SDK-present contract, exercised through a fake ``openbb`` module:
# the real SDK cannot be installed on this fleet (measured ~996 MB peak
# RSS on import), so these tests pin the exact standardization contract
# the ARM-day install must satisfy -- frames in, backbone bars out, and
# every failure an explicit unavailable with zero bars.


class _FakeOBBject:
    """Minimal stand-in for an OpenBB OBBject: provider + to_dataframe."""

    def __init__(self, frame, provider: str = "yfinance") -> None:
        self._frame = frame
        self.provider = provider

    def to_dataframe(self):
        return self._frame


def _install_fake_openbb(monkeypatch, historical) -> None:
    import importlib.machinery
    import types

    module = types.ModuleType("openbb")
    module.__spec__ = importlib.machinery.ModuleSpec("openbb", loader=None)
    module.obb = types.SimpleNamespace(
        equity=types.SimpleNamespace(
            price=types.SimpleNamespace(historical=historical)
        )
    )
    monkeypatch.setitem(sys.modules, "openbb", module)


def _daily_frame():
    import pandas as pd

    frame = pd.DataFrame(
        {
            "open": [100.0, 102.0],
            "high": [110.0, 112.0],
            "low": [95.0, 97.0],
            "close": [105.0, 108.0],
            "volume": [1000.0, float("nan")],
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
    )
    frame.index.name = "date"
    return frame


def test_openbb_sdk_available_probe(monkeypatch):
    from futuris.market_data.providers.openbb_sdk import sdk_available

    monkeypatch.setitem(sys.modules, "openbb", None)
    assert sdk_available() is False
    _install_fake_openbb(monkeypatch, lambda **kwargs: None)
    assert sdk_available() is True


def test_openbb_sdk_available_probe_does_not_import_openbb(monkeypatch):
    from futuris.market_data.providers.openbb_sdk import sdk_available

    # Regression: the probe exists to avoid importing the SDK (measured
    # at ~996 MB peak RSS), so it must use find_spec only -- calling it
    # must never leave ``openbb`` loaded in sys.modules as a side effect.
    monkeypatch.delitem(sys.modules, "openbb", raising=False)
    sdk_available()
    assert "openbb" not in sys.modules


async def test_openbb_sdk_present_standardizes_bars(monkeypatch):
    seen: dict = {}

    def historical(**kwargs):
        seen.update(kwargs)
        return _FakeOBBject(_daily_frame())

    _install_fake_openbb(monkeypatch, historical)
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert result.provider == "openbb_sdk"
    # Source label carries OpenBB's own provider attribution.
    assert result.source == "market_data:openbb_sdk:yfinance"
    assert seen["provider"] == "yfinance"
    assert seen["interval"] == "1d"
    assert len(result.bars) == 2
    first, second = result.bars
    assert first.symbol == "BTCUSDT" and first.provider_symbol == "BTCUSDT"
    assert first.close == 105.0 and first.volume == 1000.0
    assert first.timestamp.tzinfo is not None
    # NaN volume becomes None -- never a NaN bar field.
    assert second.volume is None


async def test_openbb_sdk_present_intraday_timestamp_frame(monkeypatch):
    import pandas as pd

    frame = pd.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [95.0],
            "close": [105.0],
            "volume": [1000.0],
        },
        index=pd.to_datetime(["2026-01-02T09:30:00"]),
    )
    frame.index.name = "timestamp"
    _install_fake_openbb(monkeypatch, lambda **kwargs: _FakeOBBject(frame))
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1h")
    assert result.status == "ok"
    assert len(result.bars) == 1
    assert result.bars[0].timestamp.hour == 9


async def test_openbb_sdk_present_drops_nan_close_rows(monkeypatch):
    frame = _daily_frame()
    frame.loc[frame.index[1], "close"] = float("nan")
    _install_fake_openbb(monkeypatch, lambda **kwargs: _FakeOBBject(frame))
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    # The NaN-close slot is dropped, not standardized into a bar.
    assert len(result.bars) == 1
    assert result.bars[0].close == 105.0


async def test_openbb_sdk_present_empty_frame_is_unavailable(monkeypatch):
    frame = _daily_frame().iloc[0:0]
    _install_fake_openbb(monkeypatch, lambda **kwargs: _FakeOBBject(frame))
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert "no bars" in (result.detail or "")


async def test_openbb_sdk_present_fetch_failure_is_unavailable(monkeypatch):
    def historical(**kwargs):
        raise RuntimeError("upstream down")

    _install_fake_openbb(monkeypatch, historical)
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert "fetch failed" in (result.detail or "")


async def test_openbb_sdk_present_malformed_frame_is_unavailable(monkeypatch):
    frame = _daily_frame().drop(columns=["close"])
    _install_fake_openbb(monkeypatch, lambda **kwargs: _FakeOBBject(frame))
    provider = OpenBBSDKProvider()
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert "malformed" in (result.detail or "")


async def test_openbb_sdk_present_uses_configured_obb_provider(monkeypatch):
    seen: dict = {}

    def historical(**kwargs):
        seen.update(kwargs)
        return _FakeOBBject(_daily_frame(), provider="fmp")

    _install_fake_openbb(monkeypatch, historical)
    provider = OpenBBSDKProvider(obb_provider="fmp")
    result = await provider.fetch_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert seen["provider"] == "fmp"
    assert result.source == "market_data:openbb_sdk:fmp"
