"""
tests/test_real_http_api.py — Real HTTP API integration tests.

Tests the actual running API server with real HTTP requests:
- Health and status endpoints
- Decision, reasoning, memory endpoints
- Trading, security, forecast, content endpoints
- Cross-agent workflow endpoints

Priority 1: Real HTTP API verification — not mock
"""
import json
import time
import urllib.request
import urllib.error
import pytest

BASE_URL = "http://localhost:8000"
TIMEOUT = 10


def api_call(method: str, path: str, data: dict | None = None) -> dict:
    """Make a real HTTP API call."""
    url = f"{BASE_URL}{path}"
    data_bytes = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=data_bytes, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


@pytest.fixture(scope="module", autouse=True)
def check_server():
    """Check if server is running."""
    try:
        result = api_call("GET", "/health")
        assert result.get("status") == "healthy"
    except Exception as e:
        pytest.skip(f"API server not running: {e}")


class TestRealHTTPAPI:
    def test_health(self):
        result = api_call("GET", "/health")
        assert result["status"] == "healthy"
        assert result["engines"] == 10

    def test_status(self):
        result = api_call("GET", "/api/status")
        assert "decision_engine" in result
        assert "memory_engine" in result
        assert "trading_engine" in result
        assert "security_engine" in result

    def test_decision(self):
        result = api_call("POST", "/api/decision/decide", {
            "question": "Which option is best?",
            "options": [
                {"name": "OptionA", "scores": {"quality": 90, "cost": 70}},
                {"name": "OptionB", "scores": {"quality": 80, "cost": 85}},
            ],
            "criteria": [
                {"name": "quality", "weight": 0.5},
                {"name": "cost", "weight": 0.5},
            ]
        })
        assert "best_option" in result
        assert "ranking" in result
        assert "confidence" in result

    def test_memory_store_and_search(self):
        # Store
        store_result = api_call("POST", "/api/memory/store", {
            "content": "Stratex is a quantitative trading engine",
            "agent_origin": "Stratex",
            "tags": ["trading", "stratex"],
            "importance": 0.8,
        })
        assert store_result["status"] == "stored"

        # Search
        search_result = api_call("POST", "/api/memory/search", {
            "query": "trading engine",
            "limit": 5,
        })
        assert search_result["total"] >= 1

    def test_bayesian_reasoning(self):
        result = api_call("POST", "/api/reasoning/bayesian", {
            "hypothesis": "Market will rise",
            "prior": 0.4,
            "evidence": "Positive economic data",
            "likelihood": 0.7,
        })
        assert "posterior" in result
        assert result["posterior"] > 0.4  # Should increase

    def test_trading_backtest(self):
        prices = [100 + i * 0.5 + (i % 5) * 0.1 for i in range(60)]
        result = api_call("POST", "/api/trading/backtest", {
            "symbol": "TEST",
            "prices": prices,
            "strategy": "sma_cross",
            "initial_capital": 10000.0,
        })
        assert "total_return_pct" in result
        assert "sharpe_ratio" in result

    def test_code_analysis(self):
        code = "class MyClass:\n    def method(self):\n        return 42"
        result = api_call("POST", "/api/code/analyze", {
            "code": code,
            "language": "python",
        })
        assert "lines_of_code" in result
        assert "classes" in result

    def test_security_scan(self):
        result = api_call("POST", "/api/security/scan", {
            "code": 'password = "secret123"',
            "logs": "union select password from users",
        })
        assert result["vulnerabilities"] >= 1
        assert result["threats"] >= 1
        assert result["posture_score"] >= 0

    def test_forecast(self):
        series = [100 + i * 0.5 for i in range(30)]
        result = api_call("POST", "/api/forecast/ensemble", {
            "symbol": "TEST",
            "series": series,
        })
        assert "prediction" in result
        assert result["prediction"] > 0
        assert result["confidence"] > 0

    def test_content_predict(self):
        result = api_call("POST", "/api/content/predict", {
            "title": "How to Build AI Apps",
            "description": "Comprehensive tutorial on AI application development",
            "tags": ["ai", "tutorial"],
        })
        assert "engagement_score" in result
        assert result["predicted_views"] > 0


class TestRealHTTPWorkflows:
    def test_trading_workflow(self):
        prices = [100 + i * 0.5 + (i % 10) * 0.1 for i in range(80)]
        result = api_call("POST", "/api/workflow/trading", {
            "symbol": "TEST",
            "prices": prices,
        })
        assert result["status"] == "completed"
        assert result["steps"] == 5
        assert result["final_output"] in ("Execute", "Skip")

    def test_security_workflow(self):
        result = api_call("POST", "/api/workflow/security", {
            "code": 'password = "admin123"',
            "logs": "<script>alert(1)</script> union select",
        })
        assert result["status"] == "completed"
        assert result["steps"] == 5
        assert result["final_output"] in ("Block Immediately", "Monitor", "Investigate")

    def test_code_workflow(self):
        result = api_call("POST", "/api/workflow/code", {
            "topic": "function that adds two numbers",
        })
        assert result["status"] == "completed"
        assert result["steps"] == 5
        assert result["final_output"] in ("Deploy", "Refactor")

    def test_content_workflow(self):
        result = api_call("POST", "/api/workflow/content", {
            "topic": "AI Trends 2024",
        })
        assert result["status"] == "completed"
        assert result["steps"] == 4
        assert result["final_output"] in ("Publish Now", "Schedule")
