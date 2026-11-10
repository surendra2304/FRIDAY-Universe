"""In-process TEST DOUBLE for the nine remote FRIDAY agents.

This is NOT a real-fleet verification. It exists so the dispatch bus and the workflow engine can
be tested without a running fleet, and it enforces the same wire contract the real agents serve,
so a wrong route, a malformed envelope or an unsupported action fails a test instead of passing.

Contract (verified against the live agents):
  POST /<agent>/v1/task/execute   full envelope: task_id, agent, action, payload, priority (str),
                                  source_agent. VyralX instead serves POST /vyralx/api/v1/tasks.
  GET  /<agent>/health            200

Modes, selected with FRIDAY_TEST_FLEET:
  stub (default)  start this double and point FRIDAY_DISPATCH_<NAME>_URL at it. Refuses to run if
                  any FRIDAY_DISPATCH_<NAME>_URL is already set, so stub and real peers are never mixed.
  live            use real agents. Requires all nine FRIDAY_DISPATCH_<NAME>_URL variables.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AGENTS = {
    "inference": "Inference", "memora": "Memora", "stratex": "Stratex",
    "futuris": "Futuris", "intelx": "IntelX", "forge": "Forge",
    "sentinel": "Sentinel", "cortex": "Cortex", "vyralx": "VyralX",
}
FLEET_URL_VARS = [f"FRIDAY_DISPATCH_{slug.upper()}_URL" for slug in AGENTS]
TASK_ROUTE = "/v1/task/execute"
VYRALX_ROUTE = "/api/v1/tasks"

# Actions the repository's dispatch and workflow tests send to each agent. Anything else is rejected.
ACTIONS = {
    "Inference": {"analyze", "health_check", "reason", "test"},
    "Memora": {"recall"},
    "Stratex": {"analyze", "analyze_market", "get_market_data", "trade"},
    "Futuris": {"analyze", "forecast"},
    "IntelX": {"analyze"},
    "Forge": {"analyze", "build", "develop_feature"},
    "Sentinel": {"analyze", "scan", "scan_threats"},
    "Cortex": {"decide", "decision", "execute"},
    "VyralX": {"analyze", "create", "create_content", "share_knowledge"},
}
UNIVERSAL_ACTIONS = {"load_test"}
ENVELOPE_FIELDS = (
    ("task_id", str), ("agent", str), ("action", str),
    ("payload", dict), ("priority", str), ("source_agent", str),
)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    wbufsize = 65536  # send headers and body in one write (two small writes stall on Nagle + delayed ACK)
    disable_nagle_algorithm = True

    def log_message(self, *args):  # keep test output quiet
        return

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self):
        parts = self.path.split("?", 1)[0].strip("/").split("/", 1)
        return parts[0], "/" + (parts[1] if len(parts) > 1 else "")

    def do_GET(self):
        slug, route = self._route()
        if slug in AGENTS and route == "/health":
            return self._send(200, {"status": "ok", "stub": True})
        self._send(404, {"error": "route_not_found", "stub": True})

    def do_POST(self):
        slug, route = self._route()
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if slug not in AGENTS:
            return self._send(404, {"error": "unknown_agent", "stub": True})
        agent = AGENTS[slug]
        expected = VYRALX_ROUTE if agent == "VyralX" else TASK_ROUTE
        if route != expected:
            return self._send(404, {"error": "route_not_found", "expected": expected, "stub": True})
        try:
            body = json.loads(raw or b"null")
        except ValueError:
            return self._send(400, {"error": "invalid_json", "stub": True})
        if not isinstance(body, dict):
            return self._send(422, {"status": "REJECTED", "error": "body_must_be_object", "stub": True})
        if agent == "VyralX":  # the VyralX API receives only the task payload
            return self._send(200, {"status": "SUCCESS", "result": {"agent": agent, "ok": True, "stub": True}})
        problems = [f"{k} must be {t.__name__}" for k, t in ENVELOPE_FIELDS if not isinstance(body.get(k), t)]
        if problems:
            return self._send(422, {"status": "REJECTED", "error": "invalid_envelope", "details": problems, "stub": True})
        if body["agent"] != agent:
            return self._send(422, {"status": "REJECTED", "error": "agent_mismatch", "stub": True})
        action = body["action"]
        if action not in ACTIONS[agent] | UNIVERSAL_ACTIONS:
            return self._send(422, {"status": "REJECTED", "error": "unsupported_action", "action": action, "stub": True})
        self._send(200, {
            "task_id": body["task_id"], "target_agent": slug, "status": "SUCCESS",
            "result": {"agent": agent, "action": action, "ok": True, "stub": True},
        })


class StubFleetServer(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True


def start_stub_fleet():
    """Start the double on an ephemeral port and return (server, port)."""
    server = StubFleetServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def configure_fleet(environ):
    """Apply FRIDAY_TEST_FLEET to `environ`. Returns (mode, server_or_None). Raises ValueError on misuse."""
    mode = (environ.get("FRIDAY_TEST_FLEET") or "stub").strip().lower()
    present = [v for v in FLEET_URL_VARS if environ.get(v)]
    if mode == "stub":
        # A nested pytest run (a test that shells out to pytest) inherits the parent's stub; reuse it.
        inherited = environ.get("FRIDAY_TEST_FLEET_STUB_PORT")
        if present and inherited and all(
            environ.get(f"FRIDAY_DISPATCH_{slug.upper()}_URL") == f"http://127.0.0.1:{inherited}/{slug}"
            for slug in AGENTS
        ):
            return "stub", None
        if present:
            raise ValueError(
                "FRIDAY_TEST_FLEET=stub but these are already set: " + ", ".join(present)
                + ". Unset them, or set FRIDAY_TEST_FLEET=live to test against real agents. "
                "Stub and real peers are never mixed."
            )
        server, port = start_stub_fleet()
        for slug in AGENTS:
            environ[f"FRIDAY_DISPATCH_{slug.upper()}_URL"] = f"http://127.0.0.1:{port}/{slug}"
        environ["FRIDAY_TEST_FLEET_STUB_PORT"] = str(port)
        return "stub", server
    if mode == "live":
        missing = [v for v in FLEET_URL_VARS if not environ.get(v)]
        if missing:
            raise ValueError("FRIDAY_TEST_FLEET=live requires all nine URLs; missing: " + ", ".join(missing))
        return "live", None
    raise ValueError(f"FRIDAY_TEST_FLEET must be 'stub' or 'live', got {mode!r}")
