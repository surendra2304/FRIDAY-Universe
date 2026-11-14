"""
tests/test_oanda_practice_guard.py — TASK-STR-SAFETY-001 (HOLE 3 + HOLE 2 pins).

HOLE 3: exchanges/oanda_adapter.OandaExchangeAdapter.place_order() had NO
guard at all beyond the practice flag used to pick the base URL — an
adapter resolved to the live environment (practice=False + OANDA_PRACTICE
false) would place REAL orders. It now mirrors the BinanceFuturesAdapter
gate: order placement requires the environment to be UNAMBIGUOUSLY
practice — practice flag set AND practice host — else PermissionError,
logged, before any HTTP.

HOLE 2 pins: ALLOW_LIVE_TRADING=true ALONE must not unlock any live order
path (the code-level config.py invariant must also be flipped by a human
editing source). The Coinbase case lives here because it has no testnet
at all; Binance futures/spot cases live in test_binance_futures_live_gate
and test_live_trading_guard.

No network: every HTTP entry point is stubbed.
"""

import pytest

from exchanges.oanda_adapter import OandaExchangeAdapter

_ENV_KEYS = ("OANDA_PRACTICE", "ALLOW_LIVE_TRADING", "TRADING_MODE")


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class _Recorder:
    """Stands in for the adapter's _request; records and returns a fill."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint))
        if endpoint.endswith("/orders"):
            return {"orderFillTransaction": {"id": "fill-1", "price": "1.0850", "units": "100"}}
        return {}


def _live_adapter(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("OANDA_PRACTICE", "false")
    adapter = OandaExchangeAdapter(api_key="k", account_id="acct-1", practice=False)
    assert adapter.practice is False
    assert "api-fxtrade" in adapter.base_url
    return adapter


# ---------------------------------------------------------------------------
# HOLE 3 — the OANDA practice-only gate
# ---------------------------------------------------------------------------

def test_practice_adapter_places_orders(monkeypatch):
    _clear_env(monkeypatch)
    adapter = OandaExchangeAdapter(api_key="k", account_id="acct-1")
    assert adapter.practice is True
    recorder = _Recorder()
    adapter._request = recorder
    result = adapter.place_order("EUR_USD", "BUY", "MARKET", 100)
    assert result is not None
    assert recorder.calls and recorder.calls[0][0] == "POST"
    assert recorder.calls[0][1].endswith("/orders")


def test_live_adapter_place_order_refused_before_http(monkeypatch):
    adapter = _live_adapter(monkeypatch)
    recorder = _Recorder()
    adapter._request = recorder
    with pytest.raises(PermissionError, match="practice"):
        adapter.place_order("EUR_USD", "BUY", "MARKET", 100)
    assert recorder.calls == []  # refused before any HTTP


def test_live_adapter_stop_loss_update_refused(monkeypatch):
    """update_trade_stop_loss creates an order (POST /orders) — gated too."""
    adapter = _live_adapter(monkeypatch)
    recorder = _Recorder()
    adapter._request = recorder
    with pytest.raises(PermissionError, match="practice"):
        adapter.update_trade_stop_loss("EUR_USD", "trade-1", 1.0800)
    assert recorder.calls == []


def test_practice_adapter_stop_loss_update_allowed(monkeypatch):
    _clear_env(monkeypatch)
    adapter = OandaExchangeAdapter(api_key="k", account_id="acct-1")
    recorder = _Recorder()
    adapter._request = recorder
    assert adapter.update_trade_stop_loss("EUR_USD", "trade-1", 1.0800) is True
    # The method reads instrument/pricing data first; the order-creating
    # POST to /orders is the call that must be present.
    assert any(m == "POST" and e.endswith("/orders") for m, e in recorder.calls)


def test_tampered_base_url_refused(monkeypatch):
    """A practice-flagged adapter whose base_url is flipped to the live
    host after construction must still refuse (both conditions required)."""
    _clear_env(monkeypatch)
    adapter = OandaExchangeAdapter(api_key="k", account_id="acct-1")
    adapter.base_url = "https://api-fxtrade.oanda.com/v3"
    recorder = _Recorder()
    adapter._request = recorder
    with pytest.raises(PermissionError):
        adapter.place_order("EUR_USD", "BUY", "MARKET", 100)
    assert recorder.calls == []


def test_cleared_practice_flag_refused(monkeypatch):
    _clear_env(monkeypatch)
    adapter = OandaExchangeAdapter(api_key="k", account_id="acct-1")
    adapter.practice = False  # URL still practice — flag alone vetoes
    recorder = _Recorder()
    adapter._request = recorder
    with pytest.raises(PermissionError):
        adapter.place_order("EUR_USD", "BUY", "MARKET", 100)
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# HOLE 3b — portfolio_v2 OandaClient (orphaned transplant) gets the same gate
# ---------------------------------------------------------------------------

def test_portfolio_v2_live_client_refused():
    from portfolio_v2.oanda_client import OandaClient

    client = OandaClient("token", environment="live")
    called = []
    client._request = lambda *a, **k: called.append(a) or {}
    with pytest.raises(PermissionError, match="practice"):
        client.create_order("acct", {"order": {}})
    with pytest.raises(PermissionError, match="practice"):
        client.modify_trade_protective_orders("acct", "t1", stop_loss=1.0)
    assert called == []


def test_portfolio_v2_practice_client_unaffected():
    from portfolio_v2.oanda_client import OandaClient

    client = OandaClient("token", environment="practice")
    client._request = lambda *a, **k: {"ok": True}
    assert client.create_order("acct", {"order": {}}) == {"ok": True}


# ---------------------------------------------------------------------------
# HOLE 2 pin — env opt-in alone unlocks nothing (Coinbase has no testnet)
# ---------------------------------------------------------------------------

def test_coinbase_env_optin_alone_still_refused(monkeypatch):
    from exchanges.exchange_implementations import CoinbaseExchangeAdapter

    _clear_env(monkeypatch)
    monkeypatch.setenv("TRADING_MODE", "TESTNET")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    adapter = CoinbaseExchangeAdapter(api_key="k", secret_key="s")
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter.place_order("BTC/USD", "BUY", "MARKET", 0.01)
    with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
        adapter.cancel_order("BTC/USD", "ORDER-1")
