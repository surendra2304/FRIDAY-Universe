"""Root-CI regression for Futuris' Stratex portfolio-truth boundary.

Load the exact connector source while stubbing unrelated Futuris package imports.
This keeps the root validation job focused on the connector contract instead of
importing the entire forecasting stack (which has its own heavy dependencies).
"""

import importlib.util
import logging
from pathlib import Path
import sys
import types

import httpx
import pytest


@pytest.fixture
def trading_bot_connector(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "Futuris" / "futuris" / "connectors" / "trading_bot.py"

    # Build only the package/import surface required by this connector module.
    for name in ("futuris", "futuris.connectors", "futuris.core", "futuris.infra"):
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)

    base = types.ModuleType("futuris.connectors.base")
    base.BaseConnector = type("BaseConnector", (), {})
    base.Observation = object
    monkeypatch.setitem(sys.modules, "futuris.connectors.base", base)

    enums = types.ModuleType("futuris.core.enums")
    enums.SignalClass = types.SimpleNamespace(TELEMETRY=types.SimpleNamespace(value="telemetry"))
    monkeypatch.setitem(sys.modules, "futuris.core.enums", enums)

    log_module = types.ModuleType("futuris.infra.logging")
    log_module.get_logger = logging.getLogger
    monkeypatch.setitem(sys.modules, "futuris.infra.logging", log_module)

    config = types.ModuleType("futuris.infra.config")
    config.settings = types.SimpleNamespace(
        STRATEX_URL="http://stratex.test",
        STRATEX_API_KEY=None,
    )
    monkeypatch.setitem(sys.modules, "futuris.infra.config", config)

    spec = importlib.util.spec_from_file_location("_futuris_trading_bot_under_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module.TradingBotConnector


@pytest.mark.asyncio
async def test_missing_stratex_read_key_returns_no_positions_without_network_call(trading_bot_connector):
    class NoNetworkTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise AssertionError("No Stratex request is allowed without configured credentials")

    connector = trading_bot_connector(
        base_url="http://stratex.test",
        api_key=None,
        transport=NoNetworkTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "not_configured"


@pytest.mark.asyncio
async def test_stratex_unauthorized_is_not_retried_against_guessed_routes(trading_bot_connector):
    requested_paths = []

    class UnauthorizedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            requested_paths.append(request.url.path)
            return httpx.Response(401, json={"error": "UNAUTHORIZED"})

    connector = trading_bot_connector(
        base_url="http://stratex.test",
        api_key="invalid-read-key",
        transport=UnauthorizedTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "unauthorized"
    assert requested_paths == ["/api/v1/positions"]


@pytest.mark.asyncio
async def test_verified_empty_stratex_snapshot_does_not_create_example_positions(trading_bot_connector):
    class EmptyTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/positions"
            assert request.headers.get("x-api-key") == "explicit-read-key"
            return httpx.Response(200, json={"status": "OK", "data": []})

    connector = trading_bot_connector(
        base_url="http://stratex.test",
        api_key="explicit-read-key",
        transport=EmptyTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "empty"
