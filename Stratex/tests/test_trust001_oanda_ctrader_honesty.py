"""
tests/test_trust001_oanda_ctrader_honesty.py — TASK-TRUST-001 regression coverage.

Two contracts locked in:

1. OANDA get_positions reports the REAL per-side unrealizedPL that the
   account payload already carries (previously every position reported
   0.0 because of a wrong "OANDA provides it separately" comment).
2. CTraderFixAdapter is demo-first and fail-closed: defaults point at the
   demo FIX endpoint, credentials are never defaulted (the hardcoded
   "stratex" password fallback and the live account id default are gone),
   the LIVE endpoint requires ALLOW_LIVE_TRADING=true, and logon without
   credentials refuses.

No network: connection helpers are patched out.
"""

import pytest

import config  # collection-time import (clean env): config validates the
# environment at import, so tests must not first-import it mid-test.
from exchanges.oanda_adapter import OandaExchangeAdapter


_ENV_KEYS = (
    "CTRADER_FIX_HOST",
    "CTRADER_FIX_PORT",
    "CTRADER_FIX_SENDER_COMP_ID",
    "CTRADER_FIX_ACCOUNT_ID",
    "CTRADER_FIX_PASSWORD",
    "CTRADER_FIX_ENABLED",
    "ALLOW_LIVE_TRADING",
)

FAKE_ACCOUNT = {
    "account": {
        "positions": [
            {
                "instrument": "EUR_USD",
                "long": {"units": "10000", "averagePrice": "1.0850",
                         "unrealizedPL": "42.50", "marginRate": "0.0333"},
                "short": {"units": "0", "averagePrice": "0", "unrealizedPL": "0.0"},
            },
            {
                "instrument": "USD_JPY",
                "long": {"units": "0", "averagePrice": "0", "unrealizedPL": "0.0"},
                "short": {"units": "5000", "averagePrice": "152.10",
                          "unrealizedPL": "-17.25", "marginRate": "0.04"},
            },
        ]
    }
}


@pytest.fixture
def oanda(monkeypatch):
    for key in ("OANDA_API_KEY", "OANDA_ACCOUNT_ID", "OANDA_PRACTICE"):
        monkeypatch.delenv(key, raising=False)
    adapter = OandaExchangeAdapter(api_key="test-key", account_id="test-acct")
    monkeypatch.setattr(adapter, "_get_account", lambda: FAKE_ACCOUNT)
    monkeypatch.setattr(
        OandaExchangeAdapter, "get_current_price", lambda self, symbol: 1.0875
    )
    return adapter


def test_oanda_positions_report_real_unrealized_pnl(oanda):
    positions = oanda.get_positions()
    by_symbol = {p.symbol: p for p in positions}
    assert set(by_symbol) == {"EURUSD", "USDJPY"}
    assert by_symbol["EURUSD"].unrealized_pnl == pytest.approx(42.50)
    assert by_symbol["USDJPY"].unrealized_pnl == pytest.approx(-17.25)
    assert by_symbol["EURUSD"].side == "LONG"
    assert by_symbol["USDJPY"].side == "SHORT"


def test_oanda_positions_never_report_zero_when_pnl_exists(oanda):
    """The old behaviour reported 0.0 for every position — regression lock."""
    for p in oanda.get_positions():
        assert p.unrealized_pnl != 0.0


def test_oanda_empty_account_returns_empty_list(oanda, monkeypatch):
    monkeypatch.setattr(oanda, "_get_account", lambda: {"account": {"positions": []}})
    assert oanda.get_positions() == []


def test_oanda_unconfigured_returns_empty_list(monkeypatch):
    for key in ("OANDA_API_KEY", "OANDA_ACCOUNT_ID"):
        monkeypatch.delenv(key, raising=False)
    adapter = OandaExchangeAdapter()
    assert adapter.get_positions() == []


class TestCTraderFixDefaults:
    def _adapter(self, monkeypatch):
        from exchanges.ctrader_fix_adapter import CTraderFixAdapter

        for key in _ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        return CTraderFixAdapter()

    def test_default_host_is_demo_not_live(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.host == "demo.cfixapi.com"

    def test_no_default_account_id_or_password(self, monkeypatch):
        """The live account id and the hardcoded 'stratex' password are gone."""
        adapter = self._adapter(monkeypatch)
        assert adapter.sender_comp_id == ""
        assert adapter.account_id == ""
        assert adapter.password == ""

    def test_env_overrides_still_work(self, monkeypatch):
        monkeypatch.setenv("CTRADER_FIX_HOST", "demo.cfixapi.com")
        monkeypatch.setenv("CTRADER_FIX_SENDER_COMP_ID", "demo4.icmarkets.10128706")
        monkeypatch.setenv("CTRADER_FIX_ACCOUNT_ID", "10128706")
        monkeypatch.setenv("CTRADER_FIX_PASSWORD", "from-env-only")
        from exchanges.ctrader_fix_adapter import CTraderFixAdapter

        adapter = CTraderFixAdapter()
        assert adapter.host == "demo.cfixapi.com"
        assert adapter.account_id == "10128706"
        assert adapter.password == "from-env-only"


class TestCTraderFixFailClosed:
    def _patch_network(self, monkeypatch):
        from exchanges.ctrader_fix_adapter import CTraderFixAdapter

        monkeypatch.setattr(CTraderFixAdapter, "_load_symbol_map", lambda self, path: None)
        return CTraderFixAdapter

    def test_logon_refused_without_credentials(self, monkeypatch):
        cls = self._patch_network(monkeypatch)
        for key in _ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        adapter = cls()
        with pytest.raises(RuntimeError, match="credentials not configured"):
            adapter._ensure_connection()

    def test_live_endpoint_refused_without_optin(self, monkeypatch):
        cls = self._patch_network(monkeypatch)
        monkeypatch.setenv("CTRADER_FIX_HOST", "live.cfixapi.com")
        monkeypatch.setenv("CTRADER_FIX_SENDER_COMP_ID", "some-comp")
        monkeypatch.setenv("CTRADER_FIX_ACCOUNT_ID", "some-acct")
        monkeypatch.setenv("CTRADER_FIX_PASSWORD", "some-pass")
        adapter = cls()
        with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
            adapter._ensure_connection()

    def test_live_endpoint_refused_with_env_optin_alone(self, monkeypatch):
        """TASK-STR-SAFETY-001: ALLOW_LIVE_TRADING=true ALONE must NOT open
        the live FIX gate — the code-level config.py invariant must also
        be flipped by a human code edit."""
        cls = self._patch_network(monkeypatch)
        monkeypatch.setenv("CTRADER_FIX_HOST", "live.cfixapi.com")
        monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
        monkeypatch.setenv("CTRADER_FIX_SENDER_COMP_ID", "some-comp")
        monkeypatch.setenv("CTRADER_FIX_ACCOUNT_ID", "some-acct")
        monkeypatch.setenv("CTRADER_FIX_PASSWORD", "some-pass")
        adapter = cls()
        with pytest.raises(PermissionError, match="ALLOW_LIVE_TRADING=true"):
            adapter._ensure_connection()

    def test_live_endpoint_allowed_with_explicit_optin(self, monkeypatch):
        """With BOTH gates open — ALLOW_LIVE_TRADING=true AND the code-level
        LIVE_TRADING_ENABLED invariant in config.py flipped — the adapter
        may connect to live; credentials must still be explicit (network
        patched, no real dial)."""
        from exchanges.ctrader_fix_adapter import CTraderFixError

        cls = self._patch_network(monkeypatch)
        monkeypatch.setenv("CTRADER_FIX_HOST", "live.cfixapi.com")
        monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
        monkeypatch.setattr(config, "LIVE_TRADING_ENABLED", True)
        monkeypatch.setenv("CTRADER_FIX_SENDER_COMP_ID", "some-comp")
        monkeypatch.setenv("CTRADER_FIX_ACCOUNT_ID", "some-acct")
        monkeypatch.setenv("CTRADER_FIX_PASSWORD", "some-pass")
        adapter = cls()
        # No credentials refused; the gate passed, so a connection attempt
        # would now start — patch it out and assert we got past the gate.
        monkeypatch.setattr(
            "exchanges.ctrader_fix_adapter.socket.create_connection",
            lambda *a, **k: (_ for _ in ()).throw(CTraderFixError("no-dial-in-test")),
        )
        with pytest.raises((CTraderFixError, OSError)):
            adapter._ensure_connection()

    def test_demo_endpoint_with_credentials_passes_gate(self, monkeypatch):
        """Demo host + explicit credentials reach the connection attempt."""
        from exchanges.ctrader_fix_adapter import CTraderFixError

        cls = self._patch_network(monkeypatch)
        monkeypatch.setenv("CTRADER_FIX_SENDER_COMP_ID", "demo-comp")
        monkeypatch.setenv("CTRADER_FIX_ACCOUNT_ID", "demo-acct")
        monkeypatch.setenv("CTRADER_FIX_PASSWORD", "demo-pass")
        adapter = cls()
        monkeypatch.setattr(
            "exchanges.ctrader_fix_adapter.socket.create_connection",
            lambda *a, **k: (_ for _ in ()).throw(CTraderFixError("no-dial-in-test")),
        )
        with pytest.raises((CTraderFixError, OSError)):
            adapter._ensure_connection()
