"""
tests/test_real_dashboard_http.py — HTTP API tests for dashboard endpoints.

Tests dashboard, benchmarks, alerts, and agents endpoints.
Skips if server is not running.
"""
import pytest
import json
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


def _get(path, timeout=15):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class TestDashboardHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_dashboard(self):
        result = _get("/api/dashboard")
        assert result["version"] == "3.0.0"
        assert len(result["agents"]) == 9
        assert "alerts" in result
        assert "pipeline" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_dashboard_agents(self):
        result = _get("/api/dashboard/agents")
        assert len(result["agents"]) == 9
        assert all(a["status"] in ("healthy", "degraded", "unhealthy") for a in result["agents"])

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_dashboard_alerts(self):
        result = _get("/api/dashboard/alerts")
        assert "alerts" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_dashboard_benchmarks(self):
        result = _get("/api/dashboard/benchmarks", timeout=30)
        assert len(result) == 5
        assert all("ops_per_second" in b for b in result.values())
