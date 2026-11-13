"""
tests/test_binance_futures_live_gate.py — TASK-TRUST-001 regression coverage.

Locks in the fail-closed live-trading contract for BinanceFuturesAdapter,
which (unlike the adapters in exchange_implementations.py, TASK-STR-001) had
NO code-level live gate: live vs demo/testnet was purely an env decision, so
BINANCE_ENV unset + BINANCE_TESTNET=false resolved the adapter to the live
fapi.binance.com endpoint silently.

Contract now enforced:
1. TRADING_MODE=LIVE / LIVE_TRADING_ENABLED=1 is permanently blocked
   (construction and every order/cancel path).
2. A live-endpoint adapter (fapi.binance.com) cannot even be CONSTRUCTED
   without explicit ALLOW_LIVE_TRADING=true — before any network activity.
3. demo/testnet construction is unaffected.
4. place_order / cancel_order / cancel_algo_order re-check the gate
   (defense in depth) so a post-construction live flip cannot trade.

No production exchange is contacted: network calls are patched out.
"""

import pytest

from exchanges.binance_futures_adapter import BinanceFuturesAdapter

_ENV_KEYS = (
    "TRADING_MODE",
    "LIVE_TRADING_ENABLED",
    "ALLOW_LIVE_TRADING",
    "BINANCE_ENV",
    "BINANCE_TESTNET",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
)


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def adapter_cls(monkeypatch):
    """BinanceFuturesAdapter with all network activity patched out."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(BinanceFuturesAdapter, "_sync_time", lambda self: None)
    monkeypatch.setattr(BinanceFuturesAdapter, "_ensure_position_mode", lambda self: None)
    return BinanceFuturesAdapter


def test_env_unset_with_testnet_false_resolves_refused(adapter_cls, monkeypatch):
    """THE latent live path: BINANCE_ENV unset + testnet=False used to resolve to live."""
    monkeypatch.setenv("BINANCE_TESTNET", "false")
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter_cls(testnet=False)


def test_binance_env_live_refused_without_optin(adapter_cls, monkeypatch):
    monkeypatch.setenv("BINANCE_ENV", "live")
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter_cls()


def test_binance_env_live_refused_even_when_testnet_kwarg_true(adapter_cls, monkeypatch):
    """BINANCE_ENV=live must dominate the constructor kwarg (keys are not interchangeable)."""
    monkeypatch.setenv("BINANCE_ENV", "live")
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter_cls(testnet=True)


def test_trading_mode_live_permanently_blocked(adapter_cls, monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter_cls()


def test_live_trading_enabled_flag_blocked(adapter_cls, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "1")
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter_cls()


def test_live_construction_allowed_only_with_explicit_optin(adapter_cls, monkeypatch):
    """With the owner's explicit opt-in a live-endpoint adapter may exist
    (construction only — orders still need the venue keys and the daemon's
    own gates; the endpoint resolution is now auditable, never silent)."""
    monkeypatch.setenv("BINANCE_ENV", "live")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    adapter = adapter_cls()
    assert adapter.environment == "live"
    assert adapter.base_url == "https://fapi.binance.com"


def test_demo_construction_unchanged(adapter_cls, monkeypatch):
    monkeypatch.setenv("BINANCE_ENV", "demo")
    adapter = adapter_cls()
    assert adapter.environment == "demo"
    assert adapter.base_url == "https://demo-fapi.binance.com"


def test_testnet_construction_unchanged(adapter_cls, monkeypatch):
    monkeypatch.setenv("BINANCE_ENV", "testnet")
    adapter = adapter_cls()
    assert adapter.environment == "testnet"
    assert adapter.base_url == "https://testnet.binancefuture.com"


def _demo_adapter(adapter_cls):
    return adapter_cls()


def test_place_order_refuses_post_construction_live_flip(adapter_cls, monkeypatch):
    """Defense in depth: flipping .environment to live after construction
    cannot route orders to the live endpoint."""
    adapter = _demo_adapter(adapter_cls)
    adapter.environment = "live"
    with pytest.raises(PermissionError, match="live-endpoint order refused"):
        adapter.place_order("BTCUSDT", "BUY", "MARKET", 0.01)


def test_cancel_paths_refuse_post_construction_live_flip(adapter_cls):
    adapter = _demo_adapter(adapter_cls)
    adapter.environment = "live"
    with pytest.raises(PermissionError, match="live-endpoint order refused"):
        adapter.cancel_order("BTCUSDT", "1")
    with pytest.raises(PermissionError, match="live-endpoint order refused"):
        adapter.cancel_algo_order(12345)


def test_order_path_rechecks_trading_mode(adapter_cls, monkeypatch):
    """TRADING_MODE can change after construction; every order path re-checks."""
    adapter = _demo_adapter(adapter_cls)
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter.place_order("BTCUSDT", "BUY", "MARKET", 0.01)
    with pytest.raises(PermissionError, match="permanently blocked"):
        adapter.cancel_order("BTCUSDT", "1")
