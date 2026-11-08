"""Fail-closed shared-secret authentication for the FRIDAY engineering bridge.

The bridge is exposed through public ingress. This middleware protects MCP,
SSE and message endpoints while leaving the liveness endpoint available to
fleet monitoring. The secret is supplied only through the process environment
(or an OCI Vault-backed environment integration), never from repository files.
"""
from __future__ import annotations

import hmac
import json
import os
from typing import Any, Awaitable, Callable


class BridgeAuthMiddleware:
    """Pure ASGI middleware requiring X-FRIDAY-BRIDGE-KEY on bridge routes."""

    HEADER_NAME = b"x-friday-bridge-key"
    SECRET_ENV = "FRIDAY_BRIDGE_SHARED_SECRET"

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        secret_provider: Callable[[], str] | None = None,
    ) -> None:
        self.app = app
        self.secret_provider = secret_provider or (
            lambda: os.environ.get(self.SECRET_ENV, "")
        )

    @staticmethod
    def _is_protected_path(path: str) -> bool:
        normalized = path.rstrip("/") or "/"
        if normalized == "/":
            return True  # The bridge maps the root path to the MCP transport.
        protected_prefixes = ("/bridge", "/mcp", "/messages", "/sse")
        return any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in protected_prefixes
        )

    @staticmethod
    async def _reject(
        send: Callable[..., Awaitable[None]],
        status: int,
        detail: str,
        *,
        authenticate: bool = False,
    ) -> None:
        body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        if authenticate:
            headers.append((b"www-authenticate", b'BridgeSharedSecret realm="friday-bridge"'))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", "/"))

        # Keep CORS preflight working; it carries no application operation.
        if method == "OPTIONS" or not self._is_protected_path(path):
            await self.app(scope, receive, send)
            return

        try:
            expected = self.secret_provider()
        except Exception:
            expected = ""

        if not isinstance(expected, str) or not expected.strip():
            await self._reject(
                send,
                503,
                "Bridge authentication is not configured",
            )
            return

        headers = dict(scope.get("headers", []))
        supplied = headers.get(self.HEADER_NAME, b"")
        expected_bytes = expected.encode("utf-8")

        if not supplied or not hmac.compare_digest(supplied, expected_bytes):
            await self._reject(
                send,
                401,
                "Unauthorized",
                authenticate=True,
            )
            return

        await self.app(scope, receive, send)
