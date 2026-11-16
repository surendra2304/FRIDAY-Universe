"""TASK-IG2-STR-10 — free market-data fallback chain tests (fake transport)."""

import pytest

from market_data_fallback import (
    AllProvidersFailed,
    FallbackChain,
    PriceQuote,
    fred_series_latest,
)


class FakeTransport:
    """URL-substring routed fake fetch_text; routes can be marked dead."""

    def __init__(self):
        self.dead: set[str] = set()
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        for marker in self.dead:
            if marker in url:
                raise ConnectionError(f"{marker} down")
        if "api.binance.com" in url:
            return '{"symbol": "BTCUSDT", "price": "97000.50"}'
        if "coingecko" in url:
            return '{"bitcoin": {"usd": 96900.0}}'
        if "dexscreener" in url:
            return ('{"pairs": [{"baseToken": {"symbol": "BTC"}, "priceUsd": "96800.0",'
                    ' "liquidity": {"usd": 1000000}, "pairAddress": "0xabc"}]}')
        if "api.nasdaq.com" in url:
            return '{"data": {"primaryData": {"lastSalePrice": "$231.45"}}}'
        if "stooq.com" in url and "aapl" in url:
            return ("Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                    "AAPL.US,2026-11-13,22:00:00,230.0,232.0,229.0,231.0,123456\n")
        if "stooq.com" in url and "usdjpy" in url:
            return ("Symbol,Date,Time,Open,High,Low,Close,Volume\n"
                    "USDJPY,2026-11-16,10:00:00,159.0,160.0,158.5,159.7,0\n")
        if "yahoo" in url:
            return '{"chart": {"result": [{"meta": {"regularMarketPrice": 230.5}}]}}'
        if "fred.stlouisfed.org" in url:
            return "DATE,CPIAUCSL\n2026-09-01,310.5\n2026-10-01,311.2\n"
        raise AssertionError(f"unexpected URL {url}")


def test_crypto_primary_provider_wins():
    chain = FallbackChain(fetch_text=FakeTransport())
    quote = chain.get_crypto_price("BTCUSDT")
    assert quote.provider == "binance" and quote.price == 97000.50 and not quote.stale


def test_crypto_falls_back_in_order():
    transport = FakeTransport()
    transport.dead.add("binance")
    chain = FallbackChain(fetch_text=transport)
    quote = chain.get_crypto_price("BTC")
    assert quote.provider == "coingecko" and quote.price == 96900.0
    transport.dead.add("coingecko")
    quote = chain.get_crypto_price("BTCUSDT")
    assert quote.provider == "dexscreener" and quote.price == 96800.0


def test_equity_chain_nasdaq_then_stooq_then_yahoo():
    transport = FakeTransport()
    chain = FallbackChain(fetch_text=transport)
    assert chain.get_equity_price("AAPL").provider == "nasdaq"
    transport.dead.add("nasdaq")
    quote = chain.get_equity_price("AAPL")
    assert quote.provider == "stooq" and quote.price == 231.0
    transport.dead.add("stooq")
    quote = chain.get_equity_price("AAPL")
    assert quote.provider == "yahoo" and quote.price == 230.5


def test_fx_via_stooq():
    chain = FallbackChain(fetch_text=FakeTransport())
    quote = chain.get_fx_price("USDJPY")
    assert quote.provider == "stooq" and quote.price == 159.7


def test_last_good_served_stale_when_all_providers_die():
    transport = FakeTransport()
    chain = FallbackChain(fetch_text=transport)
    fresh = chain.get_crypto_price("BTCUSDT")
    transport.dead.update({"binance", "coingecko", "dexscreener"})
    stale = chain.get_crypto_price("BTCUSDT")
    assert stale.stale is True and stale.price == fresh.price
    assert stale.provider == "binance"


def test_all_providers_failed_without_cache_raises():
    transport = FakeTransport()
    transport.dead.update({"binance", "coingecko", "dexscreener"})
    chain = FallbackChain(fetch_text=transport)
    with pytest.raises(AllProvidersFailed):
        chain.get_crypto_price("ETHUSDT")


def test_unknown_kind_rejected():
    chain = FallbackChain(fetch_text=FakeTransport())
    with pytest.raises(ValueError):
        chain.get_price("options_chain", "AAPL")


def test_fred_series_latest_skips_missing_values():
    text = "DATE,DGS10\n2026-11-12,4.40\n2026-11-13,.\n"
    date, value = fred_series_latest("DGS10", lambda url: text)
    assert (date, value) == ("2026-11-12", 4.40)


def test_macro_latest_and_stale_fallback():
    transport = FakeTransport()
    chain = FallbackChain(fetch_text=transport)
    latest = chain.get_macro_latest("CPIAUCSL")
    assert latest == {"series": "CPIAUCSL", "date": "2026-10-01", "value": 311.2,
                      "provider": "fred", "stale": False}
    transport.dead.add("fred")
    stale = chain.get_macro_latest("CPIAUCSL")
    assert stale["stale"] is True and stale["value"] == 311.2


def test_cache_persists_to_file(tmp_path):
    cache = tmp_path / "cache.json"
    chain = FallbackChain(fetch_text=FakeTransport(), cache_path=str(cache))
    chain.get_crypto_price("BTCUSDT")
    transport = FakeTransport()
    transport.dead.update({"binance", "coingecko", "dexscreener"})
    reloaded = FallbackChain(fetch_text=transport, cache_path=str(cache))
    quote = reloaded.get_crypto_price("BTCUSDT")
    assert quote.stale is True and quote.price == 97000.50


def test_price_quote_age_and_dict():
    quote = PriceQuote(symbol="X", price=1.0, provider="p", fetched_at=0.0)
    assert quote.age_s > 0 and quote.to_dict()["provider"] == "p"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
