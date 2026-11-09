"""
tests/conftest.py — Central pytest configuration.

Sets up sys.path for all test modules and provides shared fixtures.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add all agent package paths to sys.path
PATHS = [
    ROOT,  # repo root for mesh package
    ROOT + "/FRIDAY/apps/core/src",
    ROOT + "/Cortex/apps/api/src",
    ROOT + "/Inference",
    ROOT + "/Memora/apps/api",
    ROOT + "/Memora/apps",
    ROOT + "/Memora",
    ROOT + "/Forge",
    ROOT + "/VyralX",
    ROOT + "/IntelX",
    ROOT + "/Sentinel/sentinel/apps/api/src",
    ROOT + "/Sentinel",
    ROOT + "/Stratex",
    ROOT + "/Futuris",
]

for p in PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# DATABASE_URL isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="module")
def _restore_database_url_after_module():
    """Some modules swap DATABASE_URL for their own backend. Restore the value that was in
    place before each module so later modules (for example the Inference app import) see
    the CI or runtime setting instead of a missing variable."""
    sentinel = object()
    original = os.environ.get("DATABASE_URL", sentinel)
    yield
    if original is sentinel:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original


# ---------------------------------------------------------------------------
# Stub fleet: a protocol-compliant fake of the nine remote agents
# ---------------------------------------------------------------------------
# The dispatch bus and workflow engine make real HTTP calls to the fleet. CI has no fleet, so
# these tests would always fail. The stub answers POST /<agent>/v1/task/execute (and VyralX's
# /vyralx/api/v1/tasks) with a SUCCESS envelope and GET /health with 200. Set
# FRIDAY_TEST_REAL_FLEET=1, or any FRIDAY_DISPATCH_<NAME>_URL, to use real agents instead.
_FLEET_AGENTS = {
    "inference": "Inference", "memora": "Memora", "stratex": "Stratex",
    "futuris": "Futuris", "intelx": "IntelX", "forge": "Forge",
    "sentinel": "Sentinel", "cortex": "Cortex", "vyralx": "VyralX",
}


class _StubFleetHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        return

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"status": "ok"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}
        slug = self.path.strip("/").split("/", 1)[0]
        agent = _FLEET_AGENTS.get(slug, slug)
        action = body.get("action", "task") if isinstance(body, dict) else "task"
        task_id = body.get("task_id", "stub") if isinstance(body, dict) else "stub"
        self._send(200, {
            "task_id": task_id, "target_agent": slug, "status": "SUCCESS",
            "result": {"agent": agent, "action": action, "ok": True},
        })


class _StubFleetServer(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True


def _start_stub_fleet():
    if os.environ.get("FRIDAY_TEST_REAL_FLEET") == "1":
        return None
    server = _StubFleetServer(("127.0.0.1", 0), _StubFleetHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    for slug in _FLEET_AGENTS:
        os.environ.setdefault(f"FRIDAY_DISPATCH_{slug.upper()}_URL", f"http://127.0.0.1:{port}/{slug}")
    return server


_STUB_FLEET = _start_stub_fleet()
