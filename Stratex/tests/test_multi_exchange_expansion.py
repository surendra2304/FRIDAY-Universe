import pytest

from exchanges.base_exchange import UnifiedOrderResult
from exchanges.exchange_implementations import (
    BinanceExchangeAdapter,
    BybitExchangeAdapter,
    CoinbaseExchangeAdapter,
    OKXExchangeAdapter,
)
from exchanges.health import MultiExchangeHealthMonitor
from execution.router import MultiExchangeRouter
from portfolio.unified import UnifiedPortfolioManager, UnifiedRiskLimits


def test_symbol_normalization():
    ex = BinanceExchangeAdapter()
    assert ex.normalize_symbol('BTCUSDT') == 'BTC/USDT'
    assert ex.normalize_symbol('ETHUSDC') == 'ETH/USDC'
    assert ex.normalize_symbol('SOL-USDT') == 'SOL/USDT'
    assert ex.normalize_symbol('XBTUSD') == 'BTC/USD'
    assert ex.denormalize_symbol('BTC/USDT') == 'BTCUSDT'

def test_okx_symbol_denormalization():
    ex = OKXExchangeAdapter()
    assert ex.denormalize_symbol('BTC/USDT') == 'BTC-USDT'

def test_exchange_capabilities():
    binance = BinanceExchangeAdapter()
    cb = CoinbaseExchangeAdapter()
    assert binance.capabilities.supports_futures is True
    assert binance.capabilities.supports_shorting is True
    assert cb.capabilities.supports_futures is False

class FakeBinanceClient:
    """Test double for python-binance Client (unit-test isolation, not production data)."""
    def get_account(self):
        return {"balances": [{"asset": "USDT", "free": "5000.0", "locked": "500.0"}, {"asset": "BTC", "free": "0.05", "locked": "0.0"}]}

    def futures_account_positions(self):
        return [{
            "symbol": "BTCUSDT", "positionAmt": "0.05", "entryPrice": "60000.0",
            "markPrice": "60500.0", "unRealizedProfit": "25.0", "leverage": "2"
        }]

    def get_ticker(self, symbol=""):
        return {"bidPrice": "60490.0", "askPrice": "60510.0", "lastPrice": "60500.0", "volume": "15000.0"}

    def get_order_book(self, symbol="", limit=20):
        return {
            "bids": [[60490.0, 1.5], [60480.0, 3.0], [60470.0, 5.0]],
            "asks": [[60510.0, 1.2], [60520.0, 2.5], [60530.0, 4.0]],
        }

    def futures_klines(self, symbol="", interval="15m", limit=100):
        return [
            [1700000000000 + i * 900000, "60100.0", "60200.0", "60050.0", "60150.0", "120.0", 0, 0, 0, 0, 0, 0]
            for i in range(limit)
        ]

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
    """Test double for a ccxt venue client (unit-test isolation, not production data)."""

    def __init__(self):
        self.last_order = None

    def fetch_balance(self):
        """ccxt-shaped balance that satisfies every adapter's reader.

        Coinbase reads the canonical top-level "total"/"free"/"used" maps,
        while Bybit/OKX iterate per-currency entries — provide both.
        """
        balance = {
            "USDT": {"free": 1200.0, "used": 80.0, "total": 1280.0},
            "BTC": {"free": 0.02, "used": 0.0, "total": 0.02},
        }
        balance["free"] = {"USDT": 1200.0, "BTC": 0.02}
        balance["used"] = {"USDT": 80.0, "BTC": 0.0}
        balance["total"] = {"USDT": 1280.0, "BTC": 0.02}
        return balance

    def fetch_positions(self):
        return [{
            "symbol": "BTC/USDT:USDT", "side": "long", "contracts": 0.5,
            "entryPrice": 60100.0, "markPrice": 60500.0,
            "unrealizedPnl": 200.0, "leverage": 3,
        }]

    def fetch_ticker(self, symbol):
        return {"bid": 60495.0, "ask": 60515.0, "last": 60505.0, "baseVolume": 12000.0}

    def fetch_order_book(self, symbol, limit=20):
        return {
            "bids": [[60495.0, 2.0], [60485.0, 4.0]],
            "asks": [[60515.0, 1.8], [60525.0, 3.0]],
        }

    def fetch_ohlcv(self, symbol, timeframe="15m", limit=100):
        return [
            [1700000000000 + i * 900000, 60100.0, 60200.0, 60050.0, 60150.0, 110.0]
            for i in range(limit)
        ]

    def create_order(self, symbol, order_type, side, quantity, price, params):
        self.last_order = {"symbol": symbol, "type": order_type, "side": side, "quantity": quantity}
        return {"id": "CB_TEST_1", "status": "open", "filled": quantity,
                "average": price or 60500.0, "fee": {"cost": 0.0}}


def _doubles_for(cls):
    """Attach the right labelled test double to an adapter instance."""
    ex = cls()
    if isinstance(ex, BinanceExchangeAdapter):
        ex._client = FakeBinanceClient()
    elif isinstance(ex, CoinbaseExchangeAdapter):
        # Coinbase paths read self._client via _get_client (both keys required).
        ex.api_key = "test-key"
        ex.secret_key = "test-secret"
        ex._client = FakeCcxtClient()
    else:
        # Bybit/OKX paths read self._ccxt_client directly; balances only engage
        # the client when api_key is truthy.
        ex.api_key = "test-key"
        ex.secret_key = "test-secret"
        ex._ccxt_client = FakeCcxtClient()
    return ex


def _force_unconfigured(ex):
    """Strip every credential/client so the adapter is truly 'no venue configured'.

    Defensive against ambient env: with a .env leaked into the process (e.g.
    the dashboard import chain), bare adapters pick up real demo keys and
    keyless ccxt clients can reach public endpoints — the tests below pin the
    no-client contract, so both paths are explicitly closed.
    """
    ex.api_key = ""
    ex.secret_key = ""
    ex._client = None
    ex._ccxt_client = None
    return ex


CCXT_ADAPTERS = [BybitExchangeAdapter, OKXExchangeAdapter, CoinbaseExchangeAdapter]


def test_real_read_paths_with_test_doubles():
    """With a labelled test double the adapters return real-shaped data."""
    ex = _doubles_for(BinanceExchangeAdapter)
    assert len(ex.get_balance()) > 0
    t = ex.get_ticker('BTC/USDT')
    assert t.bid > 0 and t.ask > 0
    ob = ex.get_orderbook('BTC/USDT')
    assert len(ob['bids']) > 0 and len(ob['asks']) > 0
    hist = ex.get_historical_data('BTC/USDT')
    assert len(hist) > 0 and all(c["close"] > 0 for c in hist)
    assert len(ex.get_fees('BTC/USDT')) == 2

    for cls in CCXT_ADAPTERS:
        ex = _doubles_for(cls)
        assert len(ex.get_balance()) > 0
        t = ex.get_ticker('BTC/USDT')
        assert t.bid > 0 and t.ask > 0
        ob = ex.get_orderbook('BTC/USDT')
        assert len(ob['bids']) > 0 and len(ob['asks']) > 0
        hist = ex.get_historical_data('BTC/USDT')
        assert len(hist) > 0


def test_bare_adapters_refuse_to_fabricate_market_data():
    """TASK-TRUST-001: read paths fail honestly instead of inventing prices.

    The previous behaviour returned hardcoded BTC tickers (~60,490), fake
    order books, fake balances (USDT 2,700 / USD 1,000), a fabricated Bybit
    ETH position and synthetic ascending candles when no venue was reachable.
    """
    for cls in [BinanceExchangeAdapter] + CCXT_ADAPTERS:
        ex = _force_unconfigured(cls())
        with pytest.raises(RuntimeError, match="No real ticker"):
            ex.get_ticker('BTC/USDT')
        with pytest.raises(RuntimeError, match="No real order book"):
            ex.get_orderbook('BTC/USDT')
        with pytest.raises(RuntimeError, match="No real candles"):
            ex.get_historical_data('BTC/USDT')
        assert ex.get_balance() == {}
        assert ex.get_positions() == []


def test_bare_adapter_incomplete_payload_is_not_silently_faked():
    """A venue response missing fields must raise, never fall back to defaults."""
    ex = BinanceExchangeAdapter()
    ex._client = FakeBinanceClient()
    ex._client.get_ticker = lambda symbol="": {"bidPrice": "60490.0"}  # missing ask/last
    with pytest.raises(RuntimeError, match="No real ticker"):
        ex.get_ticker('BTC/USDT')


def test_order_placement():
    ex = BinanceExchangeAdapter()
    # Test-double venue client so the order path is exercised deterministically.
    ex._client = FakeBinanceClient()
    res = ex.place_order('BTC/USDT', 'BUY', 'MARKET', 0.01)
    assert res.status == 'FILLED'
    assert res.executed_qty == 0.01
    assert ex._client.last_order['symbol'] == 'BTCUSDT'
    assert ex._client.last_order['side'] == 'BUY'

    # Without a venue client the adapter must refuse instead of fabricating a fill.
    bare = BinanceExchangeAdapter()
    with pytest.raises(RuntimeError, match='Refusing to fabricate'):
        bare.place_order('BTC/USDT', 'BUY', 'MARKET', 0.01)

def test_unified_portfolio_aggregation():
    exchanges = {
        'binance': BinanceExchangeAdapter(),
        'bybit': BybitExchangeAdapter(),
        'okx': OKXExchangeAdapter(),
        'coinbase': CoinbaseExchangeAdapter()
    }
    # Labelled test doubles for every venue: no adapter fabricates balances or
    # positions any more (TASK-TRUST-001), so aggregation needs real-shaped data.
    for ex in exchanges.values():
        if isinstance(ex, BinanceExchangeAdapter):
            ex._client = FakeBinanceClient()
        else:
            ex._ccxt_client = FakeCcxtClient()
    pm = UnifiedPortfolioManager(exchanges)
    eq = pm.get_unified_equity()
    assert eq['total_portfolio_equity'] > 0
    assert 'binance' in eq['exchange_breakdown']

    pos = pm.get_cross_exchange_positions()
    assert pos['total_positions_count'] >= 1
    assert 'BTC/USDT' in pos['net_asset_exposures']


def test_unified_portfolio_reports_zero_without_any_venue():
    """Honest zero: no venue data must aggregate to an honest empty portfolio."""
    exchanges = {name: _force_unconfigured(cls()) for name, cls in [
        ('binance', BinanceExchangeAdapter), ('bybit', BybitExchangeAdapter),
        ('okx', OKXExchangeAdapter), ('coinbase', CoinbaseExchangeAdapter)]}
    pm = UnifiedPortfolioManager(exchanges)
    eq = pm.get_unified_equity()
    assert eq['total_portfolio_equity'] == 0.0
    pos = pm.get_cross_exchange_positions()
    assert pos['total_positions_count'] == 0


def test_unified_risk_limits():
    exchanges = {'binance': BinanceExchangeAdapter()}
    exchanges['binance']._client = FakeBinanceClient()
    pm = UnifiedPortfolioManager(
        exchanges,
        risk_limits=UnifiedRiskLimits(
            max_total_portfolio_risk_pct=0.75,
            max_asset_exposure_pct=0.60
        )
    )
    allowed, msg = pm.validate_global_risk_limits('BTC/USDT', 'BUY', 500.0)
    assert allowed is True
    blocked, b_msg = pm.validate_global_risk_limits('BTC/USDT', 'BUY', 50000.0)
    assert blocked is False

def test_health_monitor_circuit_breaker():
    hm = MultiExchangeHealthMonitor(['binance', 'bybit', 'okx'])
    assert hm.is_exchange_available('okx') is True
    for _ in range(5):
        hm.record_heartbeat('okx', latency_ms=1000.0, is_success=False)
    assert hm.is_exchange_available('okx') is False
    assert hm.get_flow_allocation_multiplier('okx') == 0.0
    hm.reset_circuit_breaker('okx')
    assert hm.is_exchange_available('okx') is True

def _fake_venue_fill(exchange_name):
    """Adapter-level test double so router split coverage keeps working (labelled mock)."""
    def fill(symbol, side, order_type, quantity, price=None, stop_price=None):
        return UnifiedOrderResult(
            order_id=f"{exchange_name.upper()}_TEST_{quantity}",
            symbol=symbol,
            side=side.upper(),
            order_type=order_type.upper(),
            price=price or 60500.0,
            quantity=quantity,
            status='FILLED',
            executed_qty=quantity,
            avg_price=price or 60500.0,
            fee_paid=0.0,
            exchange=exchange_name,
        )
    return fill


def test_intelligent_order_router():
    exchanges = {
        'binance': BinanceExchangeAdapter(),
        'bybit': BybitExchangeAdapter(),
        'okx': OKXExchangeAdapter(),
        'coinbase': CoinbaseExchangeAdapter()
    }
    # Test doubles only: binance via the fake venue client; the others via
    # adapter-level doubles so the split path stays covered. The production
    # adapters refuse to fabricate (asserted below and in test_live_trading_guard.py).
    exchanges['binance']._client = FakeBinanceClient()
    exchanges['bybit'].place_order = _fake_venue_fill('bybit')
    exchanges['okx'].place_order = _fake_venue_fill('okx')
    exchanges['coinbase'].place_order = _fake_venue_fill('coinbase')
    hm = MultiExchangeHealthMonitor(list(exchanges.keys()))
    router = MultiExchangeRouter(exchanges, health_monitor=hm, large_order_threshold_usd=10000.0)

    # Standard order
    res = router.route_and_execute_order('BTC/USDT', 'BUY', 'MARKET', 0.05)
    assert res.status == 'FILLED'
    assert res.executed_qty == 0.05

    # Large order split
    split_res = router.route_and_execute_order('BTC/USDT', 'BUY', 'MARKET', 0.5)
    assert split_res.exchange == 'MULTI_VENUE'
    assert len(router.split_orders_history) >= 1

    # Unmocked adapters must refuse real execution honestly instead of faking fills.
    with pytest.raises(RuntimeError, match='refusing to fabricate'):
        BybitExchangeAdapter().place_order('BTC/USDT', 'BUY', 'MARKET', 0.01)
    with pytest.raises(RuntimeError, match='refusing to fabricate'):
        OKXExchangeAdapter().place_order('BTC/USDT', 'BUY', 'MARKET', 0.01)
    with pytest.raises(PermissionError, match='ALLOW_LIVE_TRADING=true'):
        CoinbaseExchangeAdapter().place_order('BTC/USD', 'BUY', 'MARKET', 0.01)


def test_router_refuses_best_price_without_any_real_quote():
    """TASK-TRUST-001: no venue data means no fabricated 60500.0 fallback."""
    exchanges = {name: _force_unconfigured(cls()) for name, cls in [
        ('binance', BinanceExchangeAdapter), ('bybit', BybitExchangeAdapter),
        ('okx', OKXExchangeAdapter), ('coinbase', CoinbaseExchangeAdapter)]}
    hm = MultiExchangeHealthMonitor(list(exchanges.keys()))
    router = MultiExchangeRouter(exchanges, health_monitor=hm)
    with pytest.raises(RuntimeError, match='refusing to fabricate a best-execution price'):
        router.find_best_execution_venue('BTC/USDT', 'BUY', 0.05)

def test_multiexchange_api_routes():
    from dashboard import app
    client = app.test_client()
    assert client.get('/api/multiexchange/status').status_code == 200
    assert client.get('/api/multiexchange/portfolio').status_code == 200
    # The router route reports an honest NO_DATA envelope when no venue has
    # real quotes (never a fabricated best price).
    resp = client.get('/api/multiexchange/router')
    assert resp.status_code == 200
    assert resp.get_json().get("status") in ("OK", "NO_DATA")
    assert client.get('/api/multiexchange/health').status_code == 200
