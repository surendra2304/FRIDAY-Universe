"""Integration: multi-exchange routing & failover under the TASK-TRUST-001
honest-data contract.

The pre-sweep version of this file relied on adapters fabricating a ~60,500
best price and a 2,700 USDT balance when no venue was configured; since
TASK-TRUST-001 the router raises RuntimeError and balances are honestly
empty, so these tests assert that contract explicitly and exercise routing
with injected test-double clients instead.
"""

import pytest

from exchanges.exchange_implementations import (
    BinanceExchangeAdapter,
    BybitExchangeAdapter,
    OKXExchangeAdapter,
)
from execution.router import MultiExchangeRouter
from portfolio.unified import UnifiedPortfolioManager


class FakeBinanceRoutingClient:
    """Test double for python-binance Client covering the router's read paths."""

    def get_ticker(self, symbol):
        return {"bidPrice": "60490.0", "askPrice": "60510.0", "lastPrice": "60500.0", "volume": "15000.0"}

    def get_order_book(self, symbol, limit=20):
        return {
            "bids": [[60490.0, 1.5], [60480.0, 3.0]],
            "asks": [[60510.0, 1.2], [60520.0, 2.5]],
        }


class FakeCcxtRoutingClient:
    """Test double for ccxt-style clients covering the router's read paths."""

    def fetch_ticker(self, symbol):
        return {"bid": 60520.0, "ask": 60540.0, "last": 60530.0, "baseVolume": 12000.0}

    def fetch_order_book(self, symbol, limit=20):
        return {
            "bids": [[60520.0, 0.8], [60510.0, 1.5]],
            "asks": [[60540.0, 0.9], [60550.0, 1.4]],
        }


def _bare_adapters():
    """Build adapters with no venue client at all.

    _init_ccxt() eagerly constructs a real ccxt client object even with empty
    keys, and the router's read paths would then hit live public endpoints on a
    networked machine; a client of None is the honest 'nothing configured' state.
    """
    exchanges = {
        'binance': BinanceExchangeAdapter(),
        'bybit': BybitExchangeAdapter(),
        'okx': OKXExchangeAdapter()
    }
    for ex in exchanges.values():
        if hasattr(ex, "_ccxt_client"):
            ex._ccxt_client = None
    return exchanges


def test_unconfigured_venues_report_honest_no_data(monkeypatch):
    """No venue has credentials: honest zero equity and a router that refuses
    to invent a best price (the pre-sweep code fabricated 60500.0)."""
    # Strip any locally configured Binance credentials so the adapters are
    # genuinely unconfigured regardless of the developer's .env file.
    for var in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
        monkeypatch.delenv(var, raising=False)

    exchanges = _bare_adapters()
    pm = UnifiedPortfolioManager(exchanges)
    eq = pm.get_unified_equity()
    assert len(eq['exchange_breakdown']) == 3
    assert eq['total_portfolio_equity'] == 0  # honest: nothing is configured

    router = MultiExchangeRouter(exchanges)
    with pytest.raises(RuntimeError):
        router.find_best_execution_venue(
            symbol='BTC/USDT',
            side='BUY',
            quantity=0.1
        )


def test_multi_exchange_routing_and_failover():
    """With two venues backed by real (test-double) quotes, the router picks
    the cheaper venue and fails over to the other when it is marked unhealthy."""
    exchanges = _bare_adapters()
    # Inject test doubles so two venues return deterministic quotes; okx stays
    # unconfigured and must be skipped, not fabricated.
    exchanges['binance']._client = FakeBinanceRoutingClient()
    exchanges['bybit']._ccxt_client = FakeCcxtRoutingClient()

    router = MultiExchangeRouter(exchanges)
    best_ex, best_price, cost, slip = router.find_best_execution_venue(
        symbol='BTC/USDT',
        side='BUY',
        quantity=0.1
    )
    assert best_ex in ['binance', 'bybit']  # only venues with real quotes
    assert best_price > 0
    assert cost > 0

    # Simulate failover: the venue that just answered is marked unhealthy, the
    # router must route to the other quoted venue instead of failing.
    router.unhealthy_exchanges.append(best_ex)
    second_ex, second_price, _, _ = router.find_best_execution_venue(
        symbol='BTC/USDT',
        side='BUY',
        quantity=0.1
    )
    assert second_ex != best_ex
    assert second_ex in ['binance', 'bybit']
    assert second_price > 0
