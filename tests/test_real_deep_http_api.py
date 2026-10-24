"""
tests/test_real_deep_http_api.py — HTTP API tests for deep engines.

Tests all 21 deep API endpoints against a live server.
Skips if server is not running.
"""
import pytest
import json
import time
import urllib.request
import urllib.error


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


@pytest.fixture(scope="module")
def server_check():
    if not SERVER_UP:
        pytest.skip("Deep API server not running on port 8000")
    return True


def _post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


# ── Health ────────────────────────────────────────────────────────────────

class TestDeepHTTPHealth:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_health(self):
        result = _get("/health")
        assert result["status"] == "healthy"
        assert result["engines"] >= 7


# ── Cortex Deep ──────────────────────────────────────────────────────────

class TestCortexDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_recommend(self):
        data = {
            "user_id": "user1",
            "item_features": {"item1": {"f0": 0.8}, "item2": {"f0": 0.6}},
            "item_interactions": {"user1": ["item1"], "user2": ["item2"]},
        }
        result = _post("/api/deep/recommend", data)
        assert "recommendations" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_predict(self):
        X = [{"f0": float(i)} for i in range(20)]
        y = [float(i * 2) for i in range(20)]
        data = {"model_id": "m1", "features": {"f0": 10.0},
                "training_data": X, "targets": y}
        result = _post("/api/deep/predict", data)
        assert "prediction" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_foresight(self):
        data = {"topic": "AI Market", "factors": ["regulation", "adoption"]}
        result = _post("/api/deep/foresight", data)
        assert "scenarios" in result


# ── Stratex Deep ────────────────────────────────────────────────────────

class TestStratexDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_sentiment(self):
        data = {"symbol": "AAPL", "text": "Apple stock surged with strong growth"}
        result = _post("/api/deep/sentiment", data)
        assert "score" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_orderflow(self):
        data = {"symbol": "TEST", "trades": [
            {"side": "buy", "quantity": 100}, {"side": "sell", "quantity": 50},
        ]}
        result = _post("/api/deep/orderflow", data)
        assert "imbalance" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_patterns(self):
        data = {"symbol": "TEST", "prices": [100 + i * 0.5 for i in range(30)]}
        result = _post("/api/deep/patterns", data)
        assert "patterns" in result


# ── Forge Deep ─────────────────────────────────────────────────────────

class TestForgeDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_security_scan(self):
        data = {"code": "password = 'secret'\neval('1+1')", "filename": "test.py"}
        result = _post("/api/deep/security-scan", data)
        assert "findings" in result
        assert "summary" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_deps(self):
        data = {"requirements": {"django": "==2.0.0", "flask": "==1.1.0"}}
        result = _post("/api/deep/deps", data)
        assert "total" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_refactor(self):
        data = {"code": "# TODO: fix\ndef f(): pass", "filename": "test.py"}
        result = _post("/api/deep/refactor", data)
        assert "suggestions" in result


# ── Sentinel Deep ───────────────────────────────────────────────────────

class TestSentinelDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_vuln_mgmt(self):
        data = {"cve_id": "CVE-2024-0001", "severity": "high",
                "name": "Test", "description": "Test", "score": 7.5, "component": "App"}
        result = _post("/api/deep/vuln-mgmt", data)
        assert "summary" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_compliance(self):
        data = {"framework": "CIS"}
        result = _post("/api/deep/compliance", data)
        assert "score" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_incidents(self):
        data = {"incident_type": "data_breach"}
        result = _post("/api/deep/incidents", data)
        assert "steps" in result


# ── IntelX Deep ──────────────────────────────────────────────────────────

class TestIntelXDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_threat_forecast(self):
        history = [{"timestamp": time.time() - i * 86400, "indicators": ["malware"]} for i in range(10)]
        data = {"threat_type": "malware", "history": history}
        result = _post("/api/deep/threat-forecast", data)
        assert "probability" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_intel_quality(self):
        data = {"source_id": "src1", "indicators": [
            {"value": "1.2.3.4", "type": "ip", "confidence": 0.8,
             "tags": ["malware"], "first_seen": time.time()}
        ], "feedback": []}
        result = _post("/api/deep/intel-quality", data)
        assert "grade" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_disinfo(self):
        data = {"text": "Shocking secret they don't want you to know!"}
        result = _post("/api/deep/disinfo", data)
        assert "is_disinformation" in result


# ── Futuris Deep ─────────────────────────────────────────────────────────

class TestFuturisDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_ensemble(self):
        data = {"model_forecasts": {"m1": 100, "m2": 110}, "weights": {"m1": 0.5, "m2": 0.5}}
        result = _post("/api/deep/ensemble", data)
        assert "ensemble_forecast" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_forecast(self):
        data = {"series": [100 + i for i in range(30)], "method": "auto", "horizon": 5}
        result = _post("/api/deep/forecast", data)
        assert "forecast" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_stress(self):
        data = {"baseline": 10000, "scenarios": []}
        result = _post("/api/deep/stress", data)
        assert "scenarios" in result


# ── VyralX Deep ─────────────────────────────────────────────────────────

class TestVyralXDeepHTTP:
    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_audience(self):
        data = {"viewers": [
            {"age": 25, "gender": "male", "location": "US",
             "interests": ["gaming"], "watch_time": 300, "spending": 50}
        ]}
        result = _post("/api/deep/audience", data)
        assert "summary" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_growth(self):
        data = {"channel_stats": {"subscribers": 5000, "engagement_rate": 0.05}}
        result = _post("/api/deep/growth", data)
        assert "strategies" in result

    @pytest.mark.skipif(not SERVER_UP, reason="Server not running")
    def test_moderation(self):
        data = {"content_id": "c1", "text": "This is a great educational video"}
        result = _post("/api/deep/moderation", data)
        assert "action" in result
