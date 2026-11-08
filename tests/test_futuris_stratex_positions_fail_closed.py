"""Root-CI regression for Futuris' Stratex portfolio-truth boundary.

The Stratex read API is the only source of confirmed open positions. If the
read credential is absent/rejected or the endpoint returns an empty snapshot,
Futuris must not insert example positions into the portfolio risk calculation.
"""

from pathlib import Path
import sys

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FUTURIS_ROOT = REPO_ROOT / "Futuris"
if str(FUTURIS_ROOT) not in sys.path:
    sys.path.insert(0, str(FUTURIS_ROOT))

from futuris.connectors.trading_bot import TradingBotConnector  # noqa: E402


@pytest.mark.asyncio
async def test_missing_stratex_read_key_returns_no_positions_without_network_call():
    class NoNetworkTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise AssertionError("No Stratex request is allowed without configured credentials")

    connector = TradingBotConnector(
        base_url="http://stratex.test",
        api_key=None,
        transport=NoNetworkTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "not_configured"


@pytest.mark.asyncio
async def test_stratex_unauthorized_is_not_retried_against_guessed_routes():
    requested_paths = []

    class UnauthorizedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            requested_paths.append(request.url.path)
            return httpx.Response(401, json={"error": "UNAUTHORIZED"})

    connector = TradingBotConnector(
        base_url="http://stratex.test",
        api_key="invalid-read-key",
        transport=UnauthorizedTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "unauthorized"
    assert requested_paths == ["/api/v1/positions"]


@pytest.mark.asyncio
async def test_verified_empty_stratex_snapshot_does_not_create_example_positions():
    class EmptyTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/positions"
            assert request.headers.get("x-api-key") == "explicit-read-key"
            return httpx.Response(200, json={"status": "OK", "data": []})

    connector = TradingBotConnector(
        base_url="http://stratex.test",
        api_key="explicit-read-key",
        transport=EmptyTransport(),
    )

    assert await connector.fetch_active_positions() == []
    assert connector.last_positions_status == "empty"
