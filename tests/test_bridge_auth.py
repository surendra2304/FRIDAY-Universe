"""Regression tests for the FRIDAY bridge's shared-secret ASGI middleware."""
import asyncio

import pytest

from bridge.auth import BridgeAuthMiddleware


class RecordingApp:
    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [],
        })
        await send({"type": "http.response.body", "body": b""})


def invoke(middleware, path="/mcp", headers=(), method="GET"):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": list(headers),
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    asyncio.run(middleware(scope, receive, send))
    status = next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status, body


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/bridge",
        "/bridge/mcp",
        "/mcp",
        "/mcp/",
        "/messages",
        "/messages/session-123",
        "/sse",
        "/sse/",
    ],
)
def test_protected_transport_paths_reject_missing_header(path):
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "test-secret")

    status, body = invoke(middleware, path=path)

    assert status == 401
    assert b"Unauthorized" in body
    assert downstream.called is False


def test_missing_runtime_secret_fails_closed_with_503():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "")

    status, body = invoke(middleware, path="/mcp")

    assert status == 503
    assert b"not configured" in body
    assert downstream.called is False


def test_wrong_secret_is_rejected():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "expected")

    status, _ = invoke(
        middleware,
        path="/messages",
        headers=[(b"x-friday-bridge-key", b"wrong")],
    )

    assert status == 401
    assert downstream.called is False


def test_correct_secret_allows_request():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "expected")

    status, _ = invoke(
        middleware,
        path="/mcp",
        headers=[(b"x-friday-bridge-key", b"expected")],
    )

    assert status == 204
    assert downstream.called is True


def test_health_endpoint_remains_public_when_secret_is_unset():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "")

    status, _ = invoke(middleware, path="/health")

    assert status == 204
    assert downstream.called is True


def test_cors_preflight_bypasses_auth_and_reaches_cors_middleware():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "")

    status, _ = invoke(middleware, path="/mcp", method="OPTIONS")

    assert status == 204
    assert downstream.called is True


def test_non_bridge_route_is_not_blocked():
    downstream = RecordingApp()
    middleware = BridgeAuthMiddleware(downstream, secret_provider=lambda: "")

    status, _ = invoke(middleware, path="/favicon.ico")

    assert status == 204
    assert downstream.called is True
