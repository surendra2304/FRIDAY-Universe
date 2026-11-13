"""
tests/test_multi_exchange.py — Unit & Integration Tests for Multi-Exchange Trading Architecture.

Verifies:
1. BaseExchange & Adapter Symbol Normalization (BTCUSDT, BTC-USDT, BTC/USD).
2. Exchange Implementations (Binance, Bybit, OKX, Coinbase) balance, orderbook, ticker, order execution, and fee structures.
3. UnifiedPortfolioManager equity aggregation, cross-exchange position consolidation, net asset exposure, and allocation drift detection.
4. MultiExchangeRouter optimal venue selection and automatic failover handling.
5. MultiExchangeHealthMonitor latency tracking and per-venue circuit breakers.
6. CrossExchangeArbitrageScanner spatial price spread calculation and funding rate opportunity detection.
"""

import pytest

from exchange_router import MultiExchangeRouter
from exchanges.exchange_implementations import (
    BinanceExchangeAdapter,
    BybitExchangeAdapter,
    CoinbaseExchangeAdapter,
    OKXExchangeAdapter,
)
from exchanges.health_monitor import MultiExchangeHealthMonitor
from portfolio.unified_portfolio import UnifiedPortfolioManager
from strategies.arb_scanner import CrossExchangeArbitrageScanner


class FakeBinanceClient:
    """Test double for python-binance Client (unit-test isolation, not production data)."""
    def get_account(self):
        return {"balances": [{"asset": "USDT", "free": "1000.0", "locked": "50.0"}]}

    def get_ticker(self, symbol):
        # Test-double market data: since TASK-TRUST-001 the adapter no longer
        # fabricates a ~60,490 ticker when a read fails, so every read path a
        # test exercises must be backed by an explicit double.
        return {"bidPrice": "60490.0", "askPrice": "60510.0", "lastPrice": "60500.0", "volume": "15000.0"}

    def get_order_book(self, symbol, limit=20):
        return {
            "bids": [[60490.0, 1.5], [60480.0, 3.0]],
            "asks": [[60510.0, 1.2], [60520.0, 2.5]],
        }

    def futures_account_positions(self):
        return [{
            "symbol": "BTCUSDT", "positionAmt": "0.05", "entryPrice": "60000.0",
            "markPrice": "60500.0", "unRealizedProfit": "25.0", "leverage": "2"
        }]

    def futures_create_order(self, **kwargs):
        """Test double: records the order and reports a venue-style response."""
        self.last_order = kwargs
        return {
            "orderId": 9001,
            "status": "FILLED",
            "executedQty": kwargs.get("quantity", 0.0),
            "avgPrice": kwargs.get("price", 60500.0),
            "price": kwargs.get("price", 60500.0),
        }

    def futures_cancel_order(self, **kwargs):
        """Test double: records the cancellation and reports venue-style success."""
        self.last_cancel = kwargs
        return {}


class FakeCcxtClient:
    """Test double for ccxt coinbase client."""
    def fetch_balance(self):
        return {"total": {"USD": 1000.0}, "free": {"USD": 1000.0}, "used": {"USD": 0.0}}

    def fetch_ticker(self, symbol):
        return {"bid": 60520.0, "ask": 60540.0, "last": 60530.0, "quoteVolume": 5000.0}

    def fetch_order_book(self, symbol, limit=20):
        return {"bids": [[60520.0, 0.8]], "asks": [[60540.0, 0.9]]}

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        return {"id": "CB_TEST_1", "status": "closed", "filled": amount,
                "average": price or 60530.0, "fee": {"cost": 0.36}}

    def market(self, symbol):
        return {"maker": 0.004, "taker": 0.006}


class FakeCcxtVenueClient:
    """Test double for ccxt-style venue clients (bybit/okx) — deterministic test data.

    Since TASK-TRUST-001 the bybit/okx adapters no longer fabricate balances,
    positions or tickers, so tests that exercise aggregation across venues must
    supply their own explicit test doubles here.
    """

    def __init__(self, positions=None):
        self._positions = positions or []

    def fetch_balance(self):
        return {"USDT": {"free": 800.0, "used": 200.0, "total": 1000.0}}

    def fetch_positions(self):
        return list(self._positions)

    def fetch_ticker(self, symbol):
        return {"bid": 60520.0, "ask": 60540.0, "last": 60530.0, "baseVolume": 12000.0}

    def fetch_order_book(self, symbol, limit=20):
        return {
            "bids": [[60520.0, 0.8], [60510.0, 1.5]],
            "asks": [[60540.0, 0.9], [60550.0, 1.4]],
        }


# Test-double position (ccxt fetch_positions shape) standing in for the ETH/USDT
# position the bybit adapter used to fabricate before TASK-TRUST-001.
FAKE_BYBIT_ETH_POSITION = {
    "symbol": "ETH/USDT",
    "contracts": 2.0,
    "side": "long",
    "entryPrice": 3000.0,
    "markPrice": 3050.0,
    "unrealizedPnl": 100.0,
    "leverage": 3.0,
}


@pytest.fixture
def mock_exchanges():
    exchanges = {
        "binance": BinanceExchangeAdapter(),
        "bybit": BybitExchangeAdapter(),
        "okx": OKXExchangeAdapter(),
        "coinbase": CoinbaseExchangeAdapter()
    }
    # Inject test-double API clients so live-call paths are exercised deterministically.
    # Adapters without a configured client honestly report no data since TASK-TRUST-001
    # (they never fabricate balances/tickers/positions), so every venue whose data the
    # assertions consume needs an explicit double here.
    exchanges["binance"]._client = FakeBinanceClient()
    exchanges["bybit"]._ccxt_client = FakeCcxtVenueClient(positions=[FAKE_BYBIT_ETH_POSITION])
    exchanges["bybit"].api_key = "test-bybit-key"
    exchanges["okx"]._ccxt_client = FakeCcxtVenueClient()
    exchanges["okx"].api_key = "test-okx-key"
    exchanges["coinbase"]._client = FakeCcxtClient()
    exchanges["coinbase"].is_connected = True
    return exchanges


def test_symbol_normalization(mock_exchanges):
    bn = mock_exchanges["binance"]
    okx = mock_exchanges["okx"]

    assert bn.normalize_symbol("BTCUSDT") == "BTC/USDT"
    assert bn.normalize_symbol("ETH-USDT") == "ETH/USDT"
    assert okx.denormalize_symbol("BTC/USDT") == "BTC-USDT"


def test_exchange_implementations_data(mock_exchanges):
    """Every venue is backed by an injected test double: reads return that
    double's data, never adapter-fabricated values (TASK-TRUST-001 contract)."""
    for ex_id, ex in mock_exchanges.items():
        bals = ex.get_balance()
        assert len(bals) > 0

        ticker = ex.get_ticker("BTC/USDT")
        assert ticker.bid > 0
        assert ticker.ask >= ticker.bid

        ob = ex.get_orderbook("BTC/USDT")
        assert len(ob["bids"]) > 0
        assert len(ob["asks"]) > 0

        maker_fee, taker_fee = ex.get_trading_fees("BTC/USDT")
        assert taker_fee >= maker_fee


def test_adapters_without_credentials_return_no_fabricated_data():
    """Adapters with no credentials must return empty data, never fake balances/positions."""
    bare_binance = BinanceExchangeAdapter()
    assert bare_binance.get_balance() == {}
    assert bare_binance.get_positions() == []

    # TASK-TRUST-001: the ccxt-based adapters now share the same honest contract.
    for adapter_cls in (BybitExchangeAdapter, OKXExchangeAdapter):
        bare = adapter_cls()
        assert bare.get_balance() == {}
        assert bare.get_positions() == []


def test_unified_portfolio_manager(mock_exchanges):
    mgr = UnifiedPortfolioManager(mock_exchanges)

    # Combined Equity
    eq_res = mgr.get_unified_equity()
    assert eq_res["total_portfolio_equity"] > 0
    assert "binance" in eq_res["exchange_breakdown"]
    assert "bybit" in eq_res["exchange_breakdown"]

    # Positions & Net Exposure
    pos_res = mgr.get_cross_exchange_positions()
    assert pos_res["total_positions_count"] >= 2
    assert "BTC/USDT" in pos_res["net_asset_exposures"]
    assert "ETH/USDT" in pos_res["net_asset_exposures"]

    # Allocation drift check
    drift, drift_map = mgr.check_allocation_drift(threshold_pct=0.01)
    assert isinstance(drift, bool)
    assert len(drift_map) == 4


def test_multi_exchange_router_and_failover(mock_exchanges, monkeypatch):
    # Hermetic order-path gate: the adapter refuses orders in PAPER/LIVE modes,
    # so pin TESTNET explicitly instead of depending on the local .env file.
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    router = MultiExchangeRouter(mock_exchanges)

    # Best venue routing — quotes come from the injected test doubles; the
    # router raises RuntimeError instead of inventing a price when no venue
    # returns real data (TASK-TRUST-001).
    venue, price, fee = router.find_best_execution_venue("BTC/USDT", "BUY", 0.1)
    assert venue in mock_exchanges
    assert price > 0

    # Order execution: FILLED is reported by the injected fake venue client,
    # never fabricated by the adapter itself (see test_live_trading_guard.py).
    res = router.route_and_execute_order("BTC/USDT", "BUY", "LIMIT", 0.1, price=60500.0)
    assert res.status == "FILLED"
    assert res.executed_qty == 0.1


def test_health_monitor_and_circuit_breaker():
    monitor = MultiExchangeHealthMonitor(["binance", "bybit"])

    # Heartbeat success
    monitor.record_heartbeat("binance", 40.0, is_success=True)
    assert monitor.metrics["binance"].status == "HEALTHY"

    # Heartbeat failures triggering circuit breaker
    for _ in range(3):
        monitor.record_heartbeat("bybit", 500.0, is_success=False)

    assert monitor.metrics["bybit"].circuit_breaker_active is True
    assert monitor.metrics["bybit"].status == "CIRCUIT_BREAKER_TRIPPED"

    # Reset
    monitor.reset_circuit_breaker("bybit")
    assert monitor.metrics["bybit"].circuit_breaker_active is False


def test_cross_exchange_arbitrage_scanner(mock_exchanges):
    scanner = CrossExchangeArbitrageScanner(mock_exchanges, min_net_profit_pct=0.001)

    # Spatial Arbitrage
    opps = scanner.scan_spatial_arbitrage("BTC/USDT")
    assert isinstance(opps, list)
    if opps:
        assert opps[0].buy_price > 0
        assert opps[0].sell_price > 0

    # Funding rate arbitrage
    funding = scanner.scan_funding_rate_arbitrage("BTC/USDT")
    assert isinstance(funding, list)
    if funding:
        assert funding[0]["funding_rate_8h_pct"] > 0
