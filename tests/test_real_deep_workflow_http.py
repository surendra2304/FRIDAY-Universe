"""
tests/test_real_deep_workflow_http.py — HTTP API tests for deep workflows.

Tests 4 deep cross-agent workflow endpoints + dashboard.
Skips if server is not running.
"""
import pytest
import json
import time
import urllib.request


BASE = "http://127.0.0.1:8000"
TIMEOUT = 5


def _check_server():
    try:
        req = urllib.request.Request(f"{BASE}/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


SERVER_UP = _check_server()


def _post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _get(path, timeout=15):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class TestDeepWorkflowHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_deep_security_workflow(self):
        data = {"code": "password='x'\neval('1+1')", "logs": ["Failed login: admin"]}
        result = _post("/api/workflow/deep/security", data)
        assert result["status"] == "completed"
        assert result["complexity"] == "deep"
        assert result["steps"] >= 5
        assert result["final_output"] in ("Block Immediately", "Review")

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_deep_trading_workflow(self):
        data = {"symbol": "TEST", "prices": [100 + i for i in range(30)],
                "trades": [{"side": "buy", "quantity": 100}]}
        result = _post("/api/workflow/deep/trading", data)
        assert result["status"] == "completed"
        assert result["complexity"] == "deep"
        assert result["steps"] >= 5
        assert result["final_output"] in ("Buy", "Skip")

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_deep_intel_workflow(self):
        data = {"indicators": [
            {"value": "1.2.3.4", "type": "ip", "confidence": 0.8,
             "tags": ["malware"], "first_seen": time.time()}
        ]}
        result = _post("/api/workflow/deep/intel", data)
        assert result["status"] == "completed"
        assert result["complexity"] == "deep"
        assert result["steps"] >= 4
        assert result["final_output"] in ("Valid Intel", "Low Quality Intel")

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_deep_content_workflow(self):
        data = {"topic": "Test", "content_text": "Great educational video",
                "viewers": [{"age": 25, "gender": "male", "location": "US",
                             "interests": ["gaming"], "watch_time": 300, "spending": 50}]}
        result = _post("/api/workflow/deep/content", data)
        assert result["status"] == "completed"
        assert result["complexity"] == "deep"
        assert result["steps"] >= 4
        assert result["final_output"] in ("Publish", "Do Not Publish")

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_dashboard(self):
        result = _get("/api/dashboard")
        assert result["version"] == "3.0.0"
        assert "layers" in result
        assert "agents" in result
        assert len(result["agents"]) == 9
        assert result["dashboard"]["total_api_endpoints"] >= 50
