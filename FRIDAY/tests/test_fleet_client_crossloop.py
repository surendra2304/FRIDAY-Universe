"""TASK-REL-011: the shared FleetClient must work from more than one loop.

Live round-2 evidence (2026-11-14 17:07 IST): a Forge coding task died with
"RuntimeError: <asyncio.locks.Event object ...> is bound to a different event
loop" and FRIDAY reported Forge unreachable — while Forge's own journal shows
it received and executed the task. The shared singleton's single
httpx.AsyncClient had bound its connection pool to FRIDAY's main loop
(endpoint polling), and the tool wrapper dispatches from a fresh
asyncio.run() loop. One client per event loop is the fix; these tests pin it.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from friday.core.task_envelope import TaskEnvelope, TaskStatus
from friday.ecosystem.fleet_client import FleetClient

_RECEIPT_BODY = {
    "task_id": "stub-envelope",
    "target_agent": "forge",
    "status": "SUCCESS",
    "result": {"forge_task_id": "task_stub", "verified": True},
    "summary": "stub ok",
    "receipt": {
        "requested_action": "build",
        "target": "forge",
        "authorization_decision": "AUTHORIZED",
        "execution_timestamp": "2026-11-14T00:00:00+00:00",
        "result": {"ok": True},
        "verification_evidence": {"checked": "stub"},
        "failure_reason": None,
    },
}


class _StubForgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive: pool reuse is the hazard

    def do_POST(self):  # noqa: N802 - stdlib handler name
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        body = json.dumps(_RECEIPT_BODY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        pass


@pytest.fixture()
def stub_forge(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubForgeHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("FRIDAY_FORGE_URL", f"http://127.0.0.1:{port}")
    yield server
    server.shutdown()


def _envelope() -> TaskEnvelope:
    return TaskEnvelope(
        capability="forge.build",
        objective="write a palindrome function",
        action="build",
        target_agent="forge",
        payload={"goal": "write a palindrome function", "execute_now": True},
    )


def _fleet() -> FleetClient:
    return FleetClient(settings=SimpleNamespace(forge_api_key="stub-key"))


def test_shared_client_is_cached_per_event_loop(stub_forge) -> None:
    fleet = _fleet()

    async def grab():
        return fleet.get_shared_client()

    first_loop_client = asyncio.run(grab())
    assert asyncio.run(grab()) is not first_loop_client  # new loop, new pool
    asyncio.run(fleet.aclose())


def test_dispatch_succeeds_from_a_second_loop(stub_forge) -> None:
    """Endpoint-style first use must not poison tool-style dispatch."""
    fleet = _fleet()

    async def dispatch():
        return await fleet.dispatch_task(_envelope())

    first = asyncio.run(dispatch())
    assert first.status is TaskStatus.SUCCESS, first.error

    second = asyncio.run(dispatch())
    assert second.status is TaskStatus.SUCCESS, second.error
    asyncio.run(fleet.aclose())


def test_dispatch_from_tool_loop_while_main_loop_stays_alive(stub_forge) -> None:
    """The exact production shape: a long-lived main loop uses the client,
    then a sync tool wrapper dispatches via asyncio.run() on another loop."""
    fleet = _fleet()
    main_loop = asyncio.new_event_loop()
    thread = threading.Thread(target=main_loop.run_forever, daemon=True)
    thread.start()
    try:
        fut = asyncio.run_coroutine_threadsafe(fleet.dispatch_task(_envelope()), main_loop)
        main_result = fut.result(timeout=30)
        assert main_result.status is TaskStatus.SUCCESS, main_result.error

        tool_result = asyncio.run(fleet.dispatch_task(_envelope()))
        assert tool_result.status is TaskStatus.SUCCESS, tool_result.error
    finally:
        main_loop.call_soon_threadsafe(main_loop.stop)
        thread.join(timeout=10)
    asyncio.run(fleet.aclose())


def test_circuit_breaker_survives_cross_loop_use() -> None:
    """Breakers sit on the same singleton and are awaited from both loop
    families; their lock must not bind to the first loop either."""
    from friday.core.resilience import AsyncCircuitBreaker

    breaker = AsyncCircuitBreaker(service_name="forge", failure_threshold=2, recovery_time_seconds=60.0)

    async def fail_twice():
        assert await breaker.can_execute() is True
        await breaker.record_failure()
        await breaker.record_failure()

    async def check_open():
        return await breaker.can_execute()

    asyncio.run(fail_twice())
    # State carries across loops, and consulting it from a fresh loop works.
    assert asyncio.run(check_open()) is False
