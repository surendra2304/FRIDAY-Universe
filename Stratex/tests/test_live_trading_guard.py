"""
tests/test_live_trading_guard.py — TASK-STR-001 regression coverage.

Locks in the fail-closed live-trading contract for exchanges/exchange_implementations.py:

1. TRADING_MODE=LIVE / LIVE_TRADING_ENABLED=1 blocks every adapter's order path
   (PermissionError, the permanent invariant shared with stratex_ccxt_adapter).
2. PAPER / RESEARCH_MODE refuse real venue orders.
3. Binance/Bybit/OKX never fabricate FILLED orders: without a configured client
   they raise instead of inventing a fill.
4. Bybit/OKX raise honestly (real execution not implemented) instead of faking.
5. Coinbase (no testnet venue) requires explicit ALLOW_LIVE_TRADING=true.
6. BINANCE_TESTNET routes the python-binance client to testnet by default; a
   live-endpoint client is only built with explicit ALLOW_LIVE_TRADING=true.

All venue clients here are clearly-labelled test doubles; no production
exchange is contacted by this suite.
"""

import sys
import types

import pytest

from exchanges.exchange_implementations import (
    BinanceExchangeAdapter,
    BybitExchangeAdapter,
    CoinbaseExchangeAdapter,
    OKXExchangeAdapter,
)

ALL_ADAPTERS = [
    BinanceExchangeAdapter,
    BybitExchangeAdapter,
    OKXExchangeAdapter,
    CoinbaseExchangeAdapter,
]

_ENV_KEYS = (
    "TRADING_MODE",
    "LIVE_TRADING_ENABLED",
    "ALLOW_LIVE_TRADING",
    "BINANCE_TESTNET",
    "RESEARCH_MODE",
    # TASK-TRUST-001 hermeticity: adapters fall back to these env vars when
    # constructed with empty keys, so a .env loaded earlier in the same pytest
    # session (dashboard import chain) used to leak real demo credentials into
    # "unconfigured adapter" tests and change their behavior.
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_ENV",
)


def _clear_env(monkeypatch):
    """Isolate the guard from ambient env; every test pins the safety flags itself."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_live_trading_mode_is_permanently_blocked(monkeypatch, adapter_cls):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter_cls().place_order("BTC/USDT", "BUY", "MARKET", 0.01)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_live_trading_enabled_env_is_permanently_blocked(monkeypatch, adapter_cls):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "1")
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter_cls().place_order("BTC/USDT", "BUY", "MARKET", 0.01)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_paper_and_research_modes_refuse_real_orders(monkeypatch, adapter_cls):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "PAPER")
    with pytest.raises(PermissionError, match="STRATEX_ORDER_BLOCKED"):
        adapter_cls().place_order("BTC/USDT", "BUY", "MARKET", 0.01)

    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("RESEARCH_MODE", "1")
    with pytest.raises(PermissionError, match="STRATEX_ORDER_BLOCKED"):
        adapter_cls().place_order("BTC/USDT", "BUY", "MARKET", 0.01)


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_unconfigured_adapters_never_fabricate_fills(monkeypatch, adapter_cls):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    adapter = adapter_cls(api_key="", secret_key="")
    with pytest.raises((RuntimeError, PermissionError)):
        adapter.place_order("BTC/USDT", "BUY", "MARKET", 0.01)


def test_bybit_and_okx_refuse_instead_of_fabricating(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    for cls in (BybitExchangeAdapter, OKXExchangeAdapter):
        with pytest.raises(RuntimeError, match="refusing to fabricate"):
            cls().place_order("BTC/USDT", "BUY", "MARKET", 0.01)
        with pytest.raises(RuntimeError, match="refusing to fabricate"):
            cls().cancel_order("BTC/USDT", "ORDER-1")


def test_coinbase_requires_explicit_live_authorization(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    adapter = CoinbaseExchangeAdapter(api_key="test-key", secret_key="test-secret")

    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter.place_order("BTC/USD", "BUY", "MARKET", 0.01)
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter.cancel_order("BTC/USD", "ORDER-1")


# ---------------------------------------------------------------------------
# Binance client routing: testnet by default; live only with explicit opt-in.
# ---------------------------------------------------------------------------


class _RecordingBinanceClient:
    """Test double for binance.client.Client — records kwargs, contacts nothing."""

    instances: list["_RecordingBinanceClient"] = []

    def __init__(self, api_key, secret_key, testnet=False):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.orders: list[dict] = []
        self.cancelled: list[dict] = []
        _RecordingBinanceClient.instances.append(self)

    def futures_create_order(self, **kwargs):
        self.orders.append(kwargs)
        return {
            "orderId": 4242,
            "status": "FILLED",
            "executedQty": kwargs["quantity"],
            "avgPrice": kwargs.get("price", 60500.0),
            "price": kwargs.get("price", 60500.0),
        }

    def futures_cancel_order(self, **kwargs):
        self.cancelled.append(kwargs)
        return {}


@pytest.fixture
def fake_binance_module(monkeypatch):
    """Install a fake binance.client module for the lazy import in _get_client."""
    _RecordingBinanceClient.instances = []
    binance_mod = types.ModuleType("binance")
    client_mod = types.ModuleType("binance.client")
    client_mod.Client = _RecordingBinanceClient
    binance_mod.client = client_mod
    monkeypatch.setitem(sys.modules, "binance", binance_mod)
    monkeypatch.setitem(sys.modules, "binance.client", client_mod)
    return _RecordingBinanceClient


def test_binance_client_defaults_to_testnet(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    client = adapter._get_client()
    assert isinstance(client, fake_binance_module)
    assert client.testnet is True


def test_binance_live_endpoints_refused_without_opt_in(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    assert adapter._get_client() is None  # live-endpoint client refused
    assert fake_binance_module.instances == []  # nothing was constructed
    with pytest.raises(RuntimeError, match="Refusing to fabricate"):
        adapter.place_order("BTC/USDT", "BUY", "MARKET", 0.01)


def test_binance_live_endpoints_require_explicit_opt_in(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    client = adapter._get_client()
    assert client is not None
    assert client.testnet is False  # explicit owner opt-in enables live routing


def test_binance_order_routes_through_client(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("BINANCE_TESTNET", "true")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    res = adapter.place_order("BTC/USDT", "BUY", "LIMIT", 0.02, price=61000.0)
    client = adapter._get_client()
    assert client.orders == [{
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": 0.02,
        "price": 61000.0,
    }]
    assert res.status == "FILLED"  # reported by the (fake) venue, not fabricated
    assert res.exchange == "binance"
    assert res.order_id == "4242"
    assert res.executed_qty == 0.02


def test_binance_stop_order_passes_stop_price(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    adapter.place_order("BTC/USDT", "SELL", "STOP", 0.02, stop_price=59000.0)
    assert adapter._get_client().orders[0]["stopPrice"] == 59000.0


def test_binance_cancel_is_real_or_refused_never_fabricated(monkeypatch, fake_binance_module):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    adapter = BinanceExchangeAdapter(api_key="test-key", secret_key="test-secret")
    assert adapter.cancel_order("BTC/USDT", "123") is True
    assert adapter._get_client().cancelled[0]["orderId"] == "123"

    bare = BinanceExchangeAdapter(api_key="", secret_key="")
    with pytest.raises(RuntimeError, match="Refusing to fabricate"):
        bare.cancel_order("BTC/USDT", "123")
