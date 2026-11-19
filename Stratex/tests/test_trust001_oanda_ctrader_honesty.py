"""
tests/test_trust001_oanda_ctrader_honesty.py — TASK-TRUST-001 regression coverage.

One contract locked in (a second, for the OANDA adapter's
get_positions unrealizedPL reporting, was removed in TASK-REL-054
together with the OANDA venue):
1. CTraderFixAdapter is demo-first and fail-closed: defaults point at the
   demo FIX endpoint, credentials are never defaulted (the hardcoded
   "stratex" password fallback and the live account id default are gone),
   the LIVE endpoint requires ALLOW_LIVE_TRADING=true, and logon without
   credentials refuses.

No network: connection helpers are patched out.
"""

import pytest

import config  # collection-time import (clean env): config validates the
# environment at import, so tests must not first-import it mid-test.


_ENV_KEYS = (
    "CTRADER_FIX_HOST",
    "CTRADER_FIX_PORT",
    "CTRADER_FIX_SENDER_COMP_ID",
    "CTRADER_FIX_ACCOUNT_ID",
    "CTRADER_FIX_PASSWORD",
    "CTRADER_FIX_ENABLED",
    "ALLOW_LIVE_TRADING",
)

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
