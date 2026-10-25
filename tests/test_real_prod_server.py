"""
tests/test_real_prod_server.py — Functional tests for production server.

Tests real working production features:
- SecurityHardener: security hardening checks
- AuditLogger: audit logging with persistence
- RateLimiter: rate limiting
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


prod = load_module("FRIDAY/apps/core/src/friday_core/universe_prod_server.py", "prod_server")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestSecurityHardener:
    def test_security_checks(self):
        hardener = prod.SecurityHardener()
        checks = hardener.run_checks()
        assert len(checks) == 10
        assert all(c.check_id.startswith("SEC-") for c in checks)

    def test_security_score(self):
        hardener = prod.SecurityHardener()
        checks = hardener.run_checks()
        score = hardener.get_security_score(checks)
        assert 0 <= score["score"] <= 100
        assert score["total_checks"] == 10
        assert score["passed"] > 0


class TestAuditLogger:
    @pytest.fixture
    def engine(self, temp_state):
        return prod.AuditLogger(state_dir=os.path.join(temp_state, "audit"))

    def test_log_entry(self, engine):
        entry = engine.log("test_action", "test_agent", {"key": "value"})
        assert entry.action == "test_action"
        assert entry.agent == "test_agent"
        assert entry.level == "info"

    def test_get_entries(self, engine):
        for i in range(5):
            engine.log(f"action_{i}", "agent", {"i": i})
        entries = engine.get_entries(limit=10)
        assert len(entries) == 5

    def test_filter_by_level(self, engine):
        engine.log("info_action", "agent", {}, level="info")
        engine.log("warn_action", "agent", {}, level="warning")
        engine.log("error_action", "agent", {}, level="error")

        warnings = engine.get_entries(limit=10, level="warning")
        assert len(warnings) == 1
        assert warnings[0]["action"] == "warn_action"

    def test_state_persistence(self, temp_state):
        audit_dir = os.path.join(temp_state, "audit")
        engine1 = prod.AuditLogger(state_dir=audit_dir)
        engine1.log("persistent", "agent", {})

        engine2 = prod.AuditLogger(state_dir=audit_dir)
        entries = engine2.get_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "persistent"


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = prod.RateLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            allowed, remaining = rl.check("client1")
            assert allowed is True
            assert remaining == 5 - i - 1

    def test_blocks_over_limit(self):
        rl = prod.RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            rl.check("client1")
        allowed, remaining = rl.check("client1")
        assert allowed is False
        assert remaining == 0

    def test_separate_clients(self):
        rl = prod.RateLimiter(max_requests=2, window_seconds=60)
        rl.check("client1")
        rl.check("client1")
        allowed1, _ = rl.check("client1")
        allowed2, _ = rl.check("client2")
        assert allowed1 is False
        assert allowed2 is True


class TestProductionEndpoints:
    @pytest.fixture
    def client(self, temp_state):
        from fastapi.testclient import TestClient
        return TestClient(prod.app)

    def test_security_checks_endpoint(self, client):
        resp = client.get("/api/security/checks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["checks"]) == 10
        assert 0 <= data["summary"]["score"] <= 100

    def test_audit_endpoint(self, client):
        resp = client.post("/api/security/audit", json={
            "action": "test", "agent": "test", "details": {"x": 1}
        })
        assert resp.status_code == 200
        entry_id = resp.json()["entry_id"]
        assert entry_id.startswith("audit_")

        resp = client.get("/api/security/audit")
        assert resp.status_code == 200

    def test_rate_limit_endpoint(self, client):
        resp = client.get("/api/security/rate-limit/test_client")
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed" in data
        assert "remaining" in data
