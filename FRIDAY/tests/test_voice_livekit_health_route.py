"""TASK-OBS-011 — the LiveKit voice worker must answer GET /health on :8081.

Baseline (verified live 2026-11-23 ~13:12 IST, S1, FRIDAY-Voice.service
PID 2823815): livekit-agents 1.8.12 serves its health check only at GET /
(200 "OK"); GET /health is 404 "404: Not Found". The fleet convention —
and the watcher/Cortex probes — is GET /health, so the worker's liveness
was invisible to the standard probe. The SDK offers no hook to add routes,
so the fix aliases the SDK's own / handler onto /health (same handler
object, identical semantics by construction; no duplicated liveness logic).

These tests pin the alias:

- ``_add_health_alias`` finds the SDK's GET / route and registers GET
  /health with the same handler; a real HTTP round-trip on an ephemeral
  port proves /health answers exactly like / (and unknown paths still 404);
- the alias is idempotent and a no-op when there is no GET / route;
- ``_HealthAliasHttpServer.start`` registers the alias BEFORE the aiohttp
  runner freezes the router — a worker_started listener would be too late
  (``RuntimeError: Cannot register a resource into frozen router``,
  reproduced 2026-11-23 on the production venv);
- importing the worker module installs the subclass as the SDK's
  HttpServer, so the production worker serves /health without any change
  to the ``cli.run_app`` entrypoint.
"""

import asyncio

import aiohttp
from aiohttp import web

from friday.voice import livekit_worker as worker


async def _fetch_many(
    app: web.Application, paths: list[str]
) -> dict[str, tuple[int, str]]:
    """Serve ``app`` once on an ephemeral loopback port; GET each path.

    One server + one event loop for all paths: an aiohttp Application binds
    to the loop that first serves it, so separate ``asyncio.run`` calls on
    the same app raise "initialized with different loop".
    """
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    results: dict[str, tuple[int, str]] = {}
    try:
        async with aiohttp.ClientSession() as session:
            for path in paths:
                async with session.get(f"http://127.0.0.1:{port}{path}") as resp:
                    results[path] = (resp.status, await resp.text())
    finally:
        await runner.cleanup()
    return results


def _health_resources(app: web.Application, path: str) -> list:
    return [r for r in app.router.resources() if r.canonical == path]


async def _root_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK")


def test_add_health_alias_registers_health() -> None:
    """GET /health answers exactly like GET / (live round-trip)."""
    app = web.Application()
    app.add_routes([web.get("/", _root_handler)])
    assert worker._add_health_alias(app) is True
    assert len(_health_resources(app, "/health")) == 1

    results = asyncio.run(_fetch_many(app, ["/health", "/", "/nope"]))
    assert results["/health"] == (200, "OK")
    assert results["/"] == (200, "OK")
    assert results["/nope"][0] == 404


def test_add_health_alias_reuses_the_root_handler() -> None:
    """The /health route serves the SAME handler object as / (no copy)."""
    app = web.Application()
    app.add_routes([web.get("/", _root_handler)])
    worker._add_health_alias(app)
    root_handler = next(
        route.handler
        for resource in app.router.resources()
        if resource.canonical == "/"
        for route in resource
        if route.method == "GET"
    )
    health_handler = next(
        route.handler
        for resource in app.router.resources()
        if resource.canonical == "/health"
        for route in resource
        if route.method == "GET"
    )
    assert health_handler is root_handler


def test_add_health_alias_no_root_route() -> None:
    """No GET / route -> False, and no /health resource appears."""
    app = web.Application()
    app.add_routes([web.get("/worker", _root_handler)])
    assert worker._add_health_alias(app) is False
    assert _health_resources(app, "/health") == []


def test_add_health_alias_idempotent() -> None:
    """A second call is a no-op; exactly one /health resource exists."""
    app = web.Application()
    app.add_routes([web.get("/", _root_handler)])
    assert worker._add_health_alias(app) is True
    assert worker._add_health_alias(app) is False
    assert len(_health_resources(app, "/health")) == 1


async def _serve_alias_server() -> tuple[int, str, int, str, int, str]:
    """Start the subclass exactly as the SDK does; probe /, /health, /worker."""
    server = worker._HealthAliasHttpServer("127.0.0.1", 0)
    server.app.add_routes(
        [
            web.get("/", _root_handler),
            web.get("/worker", _root_handler),
        ]
    )
    await server.start()
    port = server.port
    assert port != 0
    try:
        async with aiohttp.ClientSession() as session:
            out = []
            for path in ("/", "/health", "/worker"):
                async with session.get(f"http://127.0.0.1:{port}{path}") as resp:
                    out.extend([resp.status, await resp.text()])
            return tuple(out)  # type: ignore[return-value]
    finally:
        await server.aclose()


def test_health_alias_server_start_registers_before_freeze() -> None:
    """The subclass path: /health live after start, / and /worker untouched."""
    root_status, root_body, health_status, health_body, worker_status, _ = (
        asyncio.run(_serve_alias_server())
    )
    assert (root_status, root_body) == (200, "OK")
    assert (health_status, health_body) == (200, "OK")
    assert worker_status == 200


def test_sdk_http_server_class_is_patched() -> None:
    """Importing the worker installs the subclass as the SDK HttpServer.

    The production entrypoint (``cli.run_app(_worker_options())``) is
    unchanged; the patch at import time is what makes the worker's own
    server carry /health. If this fails, the deployed worker serves /
    only and :8081/health 404s again.
    """
    from livekit.agents.utils import http_server as sdk_http_server

    assert sdk_http_server.HttpServer is worker._HealthAliasHttpServer
