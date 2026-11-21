"""TASK-STR-FWD-032 regression coverage: the retired Binance classic-testnet
venue must be unreachable from every live Stratex module.

The retired hosts are built from parts below so this file itself never
contains the literal host strings it scans for.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

STRATEX_DIR = Path(__file__).resolve().parents[1]

# Retired venue hosts, assembled so the literal never appears in this file.
_RETIRED_FUTURES_HOST = "testnet" + ".binancefuture.com"
_RETIRED_FUTURES_WS_HOST = "stream" + ".binancefuture.com"
_DEMO_FAPI = "https://demo-fapi.binance.com"
_DEMO_FAPI_URL = "https://demo-fapi.binance.com/fapi"
_DEMO_API = "https://demo-api.binance.com"
_DEMO_FSTREAM = "wss://demo-fstream.binance.com/ws"


def test_no_live_module_resolves_to_the_retired_venue():
    """Repo-wide guard: no Stratex .py file may name a retired-venue host
    except a refusal message that says the venue is retired."""
    hits = []
    for path in sorted(STRATEX_DIR.rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _RETIRED_FUTURES_HOST in line or _RETIRED_FUTURES_WS_HOST in line:
                hits.append((str(path.relative_to(STRATEX_DIR)), lineno, line.strip()))
    bad = [h for h in hits if "retired" not in h[2].lower()]
    assert not bad, f"live code still resolves to the retired venue: {bad}"
    assert hits, "expected at least the adapter refusal message to name the retired venue"


def test_config_hosts_are_demo_only_in_both_modes(tmp_path):
    """config.py FUTURES/BASE hosts resolve to Demo Trading whether the demo
    flag is on or off (checked in a hermetic subprocess so the import-time
    config validation cannot leak into this session)."""
    probe = (
        "import config\n"
        "assert config.FUTURES_BASE_URL == '" + _DEMO_FAPI + "', config.FUTURES_BASE_URL\n"
        "assert config.FUTURES_WS_URL == '" + _DEMO_FSTREAM + "', config.FUTURES_WS_URL\n"
        "assert config.BASE_URL == '" + _DEMO_API + "', config.BASE_URL\n"
        "assert config.WS_URL == 'wss://demo-api.binance.com/ws-api/v3', config.WS_URL\n"
        "print('hosts-ok')\n"
    )
    for demo_flag in ("true", "false"):
        env = dict(os.environ)
        env.update({
            "BINANCE_DEMO_TRADING": demo_flag,
            "TRADING_MODE": "PAPER",
            "LIVE_TRADING_ENABLED": "false",
            "ADVISORY_SHADOW_MODE": "True",
        })
        env.pop("BASE_URL", None)
        env.pop("FUTURES_BASE_URL", None)
        res = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(STRATEX_DIR), env=env,
            capture_output=True, text=True, timeout=60,
        )
        assert res.returncode == 0, f"demo={demo_flag}: {res.stdout}{res.stderr}"
        assert "hosts-ok" in res.stdout


def test_futures_adapter_refuses_testnet_and_unset_env(monkeypatch):
    """BINANCE_ENV=testnet, or an unset BINANCE_ENV, is refused fail-closed."""
    from exchanges.binance_futures_adapter import BinanceFuturesAdapter

    monkeypatch.setattr(BinanceFuturesAdapter, "_sync_time", lambda self: None)
    monkeypatch.setattr(BinanceFuturesAdapter, "_ensure_position_mode", lambda self: None)
    for key in ("BINANCE_ENV", "BINANCE_TESTNET", "TRADING_MODE",
                "LIVE_TRADING_ENABLED", "ALLOW_LIVE_TRADING"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(PermissionError, match="retired"):
        BinanceFuturesAdapter()
    monkeypatch.setenv("BINANCE_ENV", "testnet")
    with pytest.raises(PermissionError, match="retired"):
        BinanceFuturesAdapter()
    monkeypatch.setenv("BINANCE_ENV", "demo")
    adapter = BinanceFuturesAdapter()
    assert adapter.environment == "demo"
    assert adapter.base_url == _DEMO_FAPI


def test_venue_agent_fails_closed_without_demo(monkeypatch):
    """Signed clients require Demo Trading; the public client is demo-pinned."""
    import stratex_agents.venue.binance_futures_agent as binance_agent

    class FakeClient:
        def __init__(self, api_key, api_secret, *, testnet, ping):
            self.api_key = api_key
            self.api_secret = api_secret
            self.testnet = testnet
            self.ping = ping
            self.API_URL = "https://placeholder.invalid/api"
            self.FUTURES_URL = "https://placeholder.invalid/fapi"

    monkeypatch.setattr(binance_agent, "Client", FakeClient)
    monkeypatch.setenv("BINANCE_DEMO_TRADING", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    with pytest.raises(RuntimeError, match="BINANCE_DEMO_TRADING is not enabled"):
        binance_agent.BinanceFuturesAgent().create_client("FUTURES")
    public = binance_agent.BinanceFuturesAgent().create_public_client()
    assert public.FUTURES_URL == _DEMO_FAPI_URL
    assert public.stratex_environment == "demo_trading_public"


def test_portfolio_hub_probes_demo_first_and_never_the_retired_venue(monkeypatch):
    """The hub authenticates against demo-fapi first; the retired probe is gone."""
    from exchanges.unified_portfolio_hub import BinanceAccountClient

    seen: list[str] = []

    def fake_signed_request(self, base_url, endpoint):
        seen.append(base_url)
        if base_url == _DEMO_FAPI:
            return {}
        raise ConnectionError("not the demo venue")

    monkeypatch.setattr(BinanceAccountClient, "_signed_request", fake_signed_request)
    client = BinanceAccountClient(api_key="demo-key", secret_key="demo-secret")
    assert client.is_connected is True
    assert client.active_mode == "futures_demo"
    assert client.base_url == _DEMO_FAPI
    assert seen and seen[0] == _DEMO_FAPI
    assert all(_RETIRED_FUTURES_HOST not in url for url in seen)


def test_async_pipeline_defaults_to_demo_fapi():
    """AsyncMarketDataEngine no longer defaults to the retired venue."""
    from autonomy.async_pipeline import AsyncMarketDataEngine

    engine = AsyncMarketDataEngine()
    try:
        assert engine.base_url == _DEMO_FAPI
    finally:
        import asyncio

        asyncio.run(engine.close())


def test_binance_testnet_intent_is_rejected_at_validation():
    """TradeIntent no longer accepts the retired venue as an environment."""
    from stratex_agents.order_intent import TradeIntent

    with pytest.raises(ValueError, match="Binance Demo"):
        TradeIntent(
            venue="binance", symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.01, environment="binance_testnet",
            stop_loss=90.0, take_profit=110.0, strategy="test-strategy",
        )


def test_oms_requires_demo_trading_configured(tmp_path, monkeypatch):
    """The OMS fails closed when Demo Trading is not configured, instead of
    expecting a testnet environment."""
    from stratex_agents.oms import StratexOrderManager
    from stratex_agents.order_intent import TradeIntent
    from stratex_agents.order_store import OrderIntentStore

    monkeypatch.setenv("STRATEX_EXECUTION_MODE", "DEMO")
    monkeypatch.setenv("TRADING_MODE", "FUTURES")
    monkeypatch.setenv("TESTNET_ENABLED", "true")
    monkeypatch.setenv("STRATEX_ALLOWED_EXECUTION_VENUES", "binance")
    monkeypatch.delenv("BINANCE_DEMO_TRADING", raising=False)
    oms = StratexOrderManager(
        venues={"binance": None},
        authorize_intent=lambda intent: (True, "OK"),
        store=OrderIntentStore(str(tmp_path / "orders.sqlite3")),
    )
    intent = TradeIntent(
        venue="binance", symbol="BTCUSDT", side="BUY", order_type="MARKET",
        quantity=0.01, environment="binance_demo",
        stop_loss=98.0, take_profit=105.0, strategy="test-strat",
        client_order_id="stx-fwd032-001",
    )
    result = oms.submit(intent)
    assert result.status == "REJECTED"
    assert "BINANCE_DEMO_TRADING" in (result.reason or "")
