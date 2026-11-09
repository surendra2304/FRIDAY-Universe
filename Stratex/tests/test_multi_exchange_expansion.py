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


def test_exchange_implementations_data():
    for ex_cls in [BinanceExchangeAdapter, BybitExchangeAdapter, OKXExchangeAdapter, CoinbaseExchangeAdapter]:
        ex = ex_cls()
        if isinstance(ex, BinanceExchangeAdapter):
            ex._client = FakeBinanceClient()
        bals = ex.get_balance()
        assert len(bals) > 0
        t = ex.get_ticker('BTC/USDT')
        assert t.bid > 0 and t.ask > 0
        ob = ex.get_orderbook('BTC/USDT')
        assert len(ob['bids']) > 0 and len(ob['asks']) > 0
        fees = ex.get_fees('BTC/USDT')
        assert len(fees) == 2
        hist = ex.get_historical_data('BTC/USDT')
        assert len(hist) > 0

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
    exchanges['binance']._client = FakeBinanceClient()
    pm = UnifiedPortfolioManager(exchanges)
    eq = pm.get_unified_equity()
    assert eq['total_portfolio_equity'] > 0
    assert 'binance' in eq['exchange_breakdown']

    pos = pm.get_cross_exchange_positions()
    assert pos['total_positions_count'] >= 2
    assert 'BTC/USDT' in pos['net_asset_exposures']

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

def test_multiexchange_api_routes():
    from dashboard import app
    client = app.test_client()
    assert client.get('/api/multiexchange/status').status_code == 200
    assert client.get('/api/multiexchange/portfolio').status_code == 200
    assert client.get('/api/multiexchange/router').status_code == 200
    assert client.get('/api/multiexchange/health').status_code == 200
