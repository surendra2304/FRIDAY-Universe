"""TASK-IG2-STR-02: selective CCXT extra-venue adapter tests (no network)."""
import pytest

from Stratex.stratex_ccxt_adapter.extra_venues import (
    EXTRA_VENUES, ExtraVenueAdapter, LiveTradingRefused, UnsupportedVenue)


class FakeExchange:
    def __init__(self):
        self.sandbox = None
        self.orders = []

    def set_sandbox_mode(self, enabled):
        self.sandbox = enabled

    def fetch_ticker(self, symbol):
        return {"last": 100.0, "bid": 99.9, "ask": 100.1, "timestamp": 1}

    def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        return [[1, 10.0, 11.0, 9.0, 10.5, 123.0]]

    def fetch_balance(self):
        return {"total": {"USDT": 1000.0, "BTC": 0.5, "info": "x"}}

    def create_order(self, symbol, type, side, amount, price=None):
        self.orders.append((symbol, type, side, amount, price))
        return {"id": "t-1"}


def test_gap_venue_ok_and_pinned():
    fx = FakeExchange()
    a = ExtraVenueAdapter("kraken", exchange=fx)
    assert fx.sandbox is True
    t = a.fetch_ticker("BTC/USDT")
    assert (t.last, t.bid, t.ask) == (100.0, 99.9, 100.1)
    candles = a.fetch_ohlcv("BTC/USDT")
    assert candles[0].close == 10.5 and candles[0].venue == "kraken"
    assert a.fetch_balance() == {"USDT": 1000.0, "BTC": 0.5}


@pytest.mark.parametrize("venue", ["binance", "bybit", "okx", "coinbase", "oanda"])
def test_native_and_oanda_refused(venue):
    with pytest.raises(UnsupportedVenue):
        ExtraVenueAdapter(venue, exchange=FakeExchange())


def test_unknown_venue_refused():
    with pytest.raises(UnsupportedVenue):
        ExtraVenueAdapter("someobscureexchange", exchange=FakeExchange())


def test_live_mode_refused():
    with pytest.raises(LiveTradingRefused):
        ExtraVenueAdapter("kraken", sandbox=False, exchange=FakeExchange())


def test_no_testnet_venue_refused():
    no_testnet = [v for v, m in EXTRA_VENUES.items() if not m["testnet"]]
    assert no_testnet  # registry documents at least one such venue (mexc)
    with pytest.raises(LiveTradingRefused):
        ExtraVenueAdapter(no_testnet[0], exchange=FakeExchange())


def test_order_requires_confirm_and_goes_testnet():
    fx = FakeExchange()
    a = ExtraVenueAdapter("kucoin", exchange=fx)
    with pytest.raises(LiveTradingRefused):
        a.create_testnet_order("BTC/USDT", "buy", 0.01)
    out = a.create_testnet_order("BTC/USDT", "buy", 0.01, 50000.0,
                                 confirm_testnet=True)
    assert out["testnet"] is True and out["type"] == "limit"
    assert fx.orders == [("BTC/USDT", "limit", "buy", 0.01, 50000.0)]
