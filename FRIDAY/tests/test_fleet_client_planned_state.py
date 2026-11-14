"""TASK-REL-019: FRIDAY must surface a Forge plan_only result as a plan.

Forge (TASK-REL-019) now answers plan_only delegate calls with status
PLANNED and no receipt — receipts certify executed work only. Before this
mapping existed in the fleet client, a PLANNED response fell through to the
generic receipt gate and surfaced as DEGRADED "task completion is
unverified", which reads like a failure of a build that was never requested.
These tests pin the precise surfacing: DEGRADED (nothing was executed, so
never SUCCESS) with the plan-only reason stated plainly.
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

_PLANNED_BODY = {
    "task_id": "stub-envelope",
    "target_agent": "forge",
    "status": "PLANNED",
    "result": {
        "forge_task_id": "task_stub_plan",
        "goal": "write a palindrome function",
        "state": "PLANNED",
        "mode": "plan_only",
        "plan_stages": 8,
    },
    "summary": "Forge planned the goal; plan_only mode — nothing was executed.",
    "receipt": None,
}


class _PlannedForgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802 - stdlib handler name
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        body = json.dumps(_PLANNED_BODY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        pass


@pytest.fixture()
def stub_forge_planned(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PlannedForgeHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("FRIDAY_FORGE_URL", f"http://127.0.0.1:{port}")
    yield server
    server.shutdown()


def test_planned_response_surfaces_as_plan_not_unverified_completion(stub_forge_planned) -> None:
    fleet = FleetClient(settings=SimpleNamespace(forge_api_key="<redacted>"))
    envelope = TaskEnvelope(
        capability="forge.build",
        objective="write a palindrome function",
        action="build",
        target_agent="forge",
        payload={"goal": "write a palindrome function", "mode": "plan_only"},
    )

    async def dispatch():
        try:
            return await fleet.dispatch_task(envelope)
        finally:
            await fleet.aclose()

    result = asyncio.run(dispatch())

    assert result.status == TaskStatus.DEGRADED  # never SUCCESS: nothing ran
    assert result.error == "plan_only_no_execution"
    assert "plan only" in result.summary
    assert "unverified" not in result.summary.lower()
