"""TASK-REL-104 — tests for scripts/live_probe.py (hermetic, stdlib stub gateway).

No live host is touched: a local HTTP server mimics the Inference gateway
(GET /v1/health, POST /v1/mesh/ping/{agent_id}, POST /v1/task/execute)
with the exact response shapes the live code returns, so the probe's
parsing, pass/fail logic and exit codes are exercised end to end.
"""

import importlib.util
import io
import json
import os
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "live_probe.py")


def load_live_probe():
    spec = importlib.util.spec_from_file_location("live_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubGateway:
    """In-process fake Inference gateway. Knobs: fail_ping, fail_execute,
    gateway_down — each a set of agent ids (or 'gateway' for /v1/health)."""

    def __init__(self, fail_ping=frozenset(), fail_execute=frozenset(), gateway_down=False):
        self.fail_ping = set(fail_ping)
        self.fail_execute = set(fail_execute)
        self.gateway_down = gateway_down
        self.execute_calls = []
        self.ping_calls = []
        handler = self._make_handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def _make_handler(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output clean
                pass

            def _send(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/v1/health":
                    if stub.gateway_down:
                        self._send(503, {"status": "unhealthy", "service": "inference"})
                    else:
                        self._send(200, {
                            "status": "healthy",
                            "service": "inference",
                            "version": "stub",
                            "registered_roles": [],
                        })
                else:
                    self._send(404, {"detail": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode())
                except json.JSONDecodeError:
                    payload = {}
                if self.path.startswith("/v1/mesh/ping/"):
                    agent = self.path.rsplit("/", 1)[-1]
                    stub.ping_calls.append(agent)
                    if agent in stub.fail_ping:
                        self._send(200, {
                            "agent_id": agent,
                            "target_url": f"http://stub/{agent}/health",
                            "reachable": False,
                            "status_code": None,
                            "latency_ms": 2.0,
                            "authenticated_ping": True,
                        })
                    else:
                        self._send(200, {
                            "agent_id": agent,
                            "target_url": f"http://stub/{agent}/health",
                            "reachable": True,
                            "status_code": 200,
                            "latency_ms": 12.3,
                            "authenticated_ping": True,
                        })
                elif self.path == "/v1/task/execute":
                    target = payload.get("target_agent", "?")
                    stub.execute_calls.append(target)
                    if target in stub.fail_execute:
                        self._send(200, {
                            "task_id": payload.get("task_id"),
                            "target_agent": "inference",
                            "status": "ERROR",
                            "result": {},
                            "summary": "",
                            "error": "stub provider failure",
                            "execution_time_ms": 45,
                        })
                    else:
                        self._send(200, {
                            "task_id": payload.get("task_id"),
                            "target_agent": "inference",
                            "status": "SUCCESS",
                            "result": {
                                "response": "OK",
                                "confidence": 0.0,
                                "model_used": "stub-model",
                                "provider_used": "stub",
                            },
                            "summary": "Execution completed via stub/stub-model",
                            "execution_time_ms": 87,
                            "receipt": {
                                "requested_action": payload.get("action"),
                                "target": "inference",
                                "authorization_decision": "AUTHORIZED",
                                "execution_timestamp": "2026-11-27T00:00:00+00:00",
                                "result": {
                                    "model_used": "stub-model",
                                    "provider_used": "stub",
                                },
                                "verification_evidence": {
                                    "source": "inference.v1.task.execute",
                                    "task_id": payload.get("task_id"),
                                    "model_used": "stub-model",
                                    "provider_used": "stub",
                                    "token_usage": {},
                                    "latency_ms": 87,
                                },
                                "failure_reason": None,
                            },
                        })
                else:
                    self._send(404, {"detail": "not found"})

        return Handler


def run_probe(monkeypatch, gateway, extra_args=None):
    module = load_live_probe()
    monkeypatch.setenv("INFERENCE_API_KEY", "dummy-key-for-test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(["--gateway", gateway] + (extra_args or []))
    return code, json.loads(buf.getvalue())


@pytest.fixture()
def stub():
    gateway = StubGateway()
    yield gateway
    gateway.stop()


def test_all_agents_pass(monkeypatch, stub):
    code, evidence = run_probe(monkeypatch, stub.url)
    assert code == 0
    assert evidence["ok"] is True
    assert evidence["passed"] == 10 and evidence["failed"] == 0
    assert {r["agent"] for r in evidence["agents"]} == {
        "friday", "inference", "memora", "stratex", "futuris",
        "intelx", "forge", "sentinel", "cortex", "vyralx",
    }
    for record in evidence["agents"]:
        assert record["pass"] is True
        assert record["health"]["reachable"] is True
        # Leg B receipt always names target "inference" (in-gateway reasoning).
        assert record["execute"]["receipt_target"] == "inference"
        assert record["execute"]["result_status"] == "SUCCESS"
        assert record["execute"]["content_receipt"] == "OK"
    # One execute call per agent, one ping per peer (9), inference via /v1/health.
    assert len(stub.execute_calls) == 10
    assert len(stub.ping_calls) == 9


def test_one_agent_ping_down_fails_run(monkeypatch, stub):
    stub.fail_ping = {"stratex"}
    code, evidence = run_probe(monkeypatch, stub.url)
    assert code == 1
    assert evidence["ok"] is False
    assert evidence["passed"] == 9 and evidence["failed"] == 1
    failed = [r for r in evidence["agents"] if not r["pass"]]
    assert [r["agent"] for r in failed] == ["stratex"]
    assert failed[0]["health"]["reachable"] is False


def test_execute_error_fails_agent(monkeypatch, stub):
    stub.fail_execute = {"memora"}
    code, evidence = run_probe(monkeypatch, stub.url)
    assert code == 1
    memora = next(r for r in evidence["agents"] if r["agent"] == "memora")
    assert memora["pass"] is False
    assert memora["execute"]["result_status"] == "ERROR"


def test_health_only_skips_execute(monkeypatch, stub):
    code, evidence = run_probe(monkeypatch, stub.url, ["--health-only"])
    assert code == 0
    assert evidence["ok"] is True
    assert stub.execute_calls == []
    for record in evidence["agents"]:
        assert record["execute"] is None


def test_gateway_down_exits_2(monkeypatch):
    stub = StubGateway(gateway_down=True)
    try:
        code, evidence = run_probe(monkeypatch, stub.url)
    finally:
        stub.stop()
    assert code == 2
    assert evidence["ok"] is False
    assert evidence["agents"] == []
    assert evidence["gateway_health"]["reachable"] is False


def test_unknown_agent_exits_2(monkeypatch, stub):
    module = load_live_probe()
    monkeypatch.setenv("INFERENCE_API_KEY", "dummy-key-for-test")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(["--gateway", stub.url, "--agents", "friday,nope"])
    assert code == 2
    assert buf.getvalue() == ""  # usage error goes to stderr, no JSON emitted


def test_no_api_key_skips_execute_leg(monkeypatch, stub):
    module = load_live_probe()
    monkeypatch.delenv("INFERENCE_API_KEY", raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(["--gateway", stub.url, "--agents", "friday,memora"])
    evidence = json.loads(buf.getvalue())
    assert code == 1  # health passes, execute skipped without a key
    for record in evidence["agents"]:
        assert record["health"]["reachable"] is True
        assert record["execute"]["result_status"] == "SKIPPED"


def test_agent_subset(monkeypatch, stub):
    code, evidence = run_probe(monkeypatch, stub.url, ["--agents", "friday,inference"])
    assert code == 0
    assert [r["agent"] for r in evidence["agents"]] == ["friday", "inference"]
    assert len(stub.ping_calls) == 1  # only friday is a peer; inference uses /v1/health


# --- TASK-REL-119: public mode (no key, GET /{agent}/health + one real GET) ---

class PublicStubGateway:
    """In-process fake public gateway. Knobs: fail_health, fail_real (agent
    ids), gateway_down. Serves GET /health, GET /{agent}/health and the
    leg-B paths from the module's PUBLIC_REAL_REQUEST map."""

    def __init__(self, fail_health=frozenset(), fail_real=frozenset(), gateway_down=False):
        self.fail_health = set(fail_health)
        self.fail_real = set(fail_real)
        self.gateway_down = gateway_down
        self.health_calls = []
        self.real_calls = []
        handler = self._make_handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def _make_handler(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, payload, ctype="application/json"):
                body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                module = load_live_probe()
                if self.path == "/health":
                    if stub.gateway_down:
                        self._send(503, {"overall": "degraded"})
                    else:
                        self._send(200, {"overall": "healthy"})
                    return
                parts = self.path.strip("/").split("/")
                if len(parts) == 2 and parts[1] == "health":
                    agent = parts[0]
                    stub.health_calls.append(agent)
                    if agent in stub.fail_health:
                        self._send(503, {"status": "degraded", "service": agent})
                    else:
                        self._send(200, {"status": "healthy", "service": agent})
                    return
                real = {a: p for a, p in module.PUBLIC_REAL_REQUEST.items()}
                for agent, path in real.items():
                    if self.path == path:
                        stub.real_calls.append(agent)
                        if agent in stub.fail_real:
                            self._send(404, {"detail": "not found"})
                        elif path.endswith("/"):
                            if agent == "vyralx":
                                self._send(200, b"<html><title>VyralX Control Room</title></html>", "text/html; charset=utf-8")
                            else:
                                self._send(200, {"status": "ok", "service": agent})
                        else:
                            self._send(200, {"status": "ok", "service": agent})
                        return
                self._send(404, {"detail": "not found"})

        return Handler


def run_public_probe(monkeypatch, gateway, extra_args=None):
    module = load_live_probe()
    monkeypatch.delenv("INFERENCE_API_KEY", raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(["--public", "--gateway", gateway] + (extra_args or []))
    return code, json.loads(buf.getvalue())


@pytest.fixture()
def public_stub():
    gateway = PublicStubGateway()
    yield gateway
    gateway.stop()


def test_public_all_agents_pass_no_key(monkeypatch, public_stub):
    code, evidence = run_public_probe(monkeypatch, public_stub.url)
    assert code == 0
    assert evidence["ok"] is True
    assert evidence["mode"] == "public"
    assert evidence["task"] == "TASK-REL-119"
    assert evidence["passed"] == 10 and evidence["failed"] == 0
    assert {r["agent"] for r in evidence["agents"]} == {
        "friday", "inference", "memora", "stratex", "futuris",
        "intelx", "forge", "sentinel", "cortex", "vyralx",
    }
    for record in evidence["agents"]:
        assert record["pass"] is True
        assert record["health"]["reachable"] is True
        assert record["health"]["via"].startswith("GET /")
        assert record["execute"]["result_status"] == "SUCCESS"
    assert len(public_stub.health_calls) == 10
    assert len(public_stub.real_calls) == 10


def test_public_one_agent_degraded_fails_run(monkeypatch, public_stub):
    public_stub.fail_health = {"stratex"}
    code, evidence = run_public_probe(monkeypatch, public_stub.url)
    assert code == 1
    assert evidence["ok"] is False
    assert evidence["passed"] == 9 and evidence["failed"] == 1
    failed = [r for r in evidence["agents"] if not r["pass"]]
    assert [r["agent"] for r in failed] == ["stratex"]
    assert failed[0]["health"]["status_code"] == 503
    assert failed[0]["health"]["reachable"] is False


def test_public_real_request_failure_fails_agent(monkeypatch, public_stub):
    public_stub.fail_real = {"intelx"}
    code, evidence = run_public_probe(monkeypatch, public_stub.url)
    assert code == 1
    intelx = next(r for r in evidence["agents"] if r["agent"] == "intelx")
    assert intelx["pass"] is False
    assert intelx["health"]["reachable"] is True
    assert intelx["execute"]["result_status"] == "FAILED"


def test_public_health_only_skips_real_request(monkeypatch, public_stub):
    code, evidence = run_public_probe(monkeypatch, public_stub.url, ["--health-only"])
    assert code == 0
    assert evidence["ok"] is True
    assert public_stub.real_calls == []
    for record in evidence["agents"]:
        assert record["execute"] is None


def test_public_gateway_down_exits_2(monkeypatch):
    stub = PublicStubGateway(gateway_down=True)
    try:
        code, evidence = run_public_probe(monkeypatch, stub.url)
    finally:
        stub.stop()
    assert code == 2
    assert evidence["ok"] is False
    assert evidence["agents"] == []
    assert evidence["gateway_health"]["reachable"] is False
