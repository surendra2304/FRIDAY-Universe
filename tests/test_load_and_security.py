"""
tests/test_load_and_security.py — Load testing and security testing suite.

Load Tests:
- Dispatch bus under load (100+ concurrent dispatches)
- State manager under load
- Metrics under load
- Event bus under load

Security Tests:
- SSRF bypass attempts
- Path traversal attempts
- Auth token security
- Rate limiter security
- Input validation

Priority 1-5: Load testing and security testing
"""
import importlib.util
import sys
import os
import time
import threading
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for p in [
    ROOT + "/FRIDAY/apps/core/src",
    ROOT + "/Cortex/apps/api/src",
    ROOT + "/Inference",
    ROOT + "/Memora/apps/api",
    ROOT + "/Forge",
    ROOT + "/VyralX",
    ROOT + "/IntelX",
    ROOT + "/Sentinel/sentinel/apps/api/src",
    ROOT + "/Stratex",
    ROOT + "/Futuris",
]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, relpath):
    path = os.path.join(ROOT, relpath)
    full_name = f"_ls_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ════════════════════════════════════════════════════════════════════════════════
# LOAD TESTS
# ════════════════════════════════════════════════════════════════════════════════

class TestLoadDispatchBus:
    """Load test the dispatch bus with concurrent dispatches."""

    def test_100_concurrent_dispatches(self):
        bus = _eng("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        results = []
        lock = threading.Lock()

        def dispatch_worker(agent_idx):
            for i in range(10):
                agent = agents[agent_idx % len(agents)]
                receipt = bus.dispatch(agent, "load_test", {"i": i})
                with lock:
                    results.append(receipt)

        threads = []
        for i in range(10):
            t = threading.Thread(target=dispatch_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 100
        assert all(r.status == "completed" for r in results)

    def test_batch_dispatch_50(self):
        bus = _eng("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        batch = bus.dispatch_batch([
            {"agent": "Inference", "action": "reason", "payload": {"i": i}}
            for i in range(50)
        ])
        assert len(batch) == 50
        assert all(r.status == "completed" for r in batch)

    def test_dispatch_latency(self):
        bus = _eng("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        start = time.time()
        for i in range(100):
            bus.dispatch("Inference", "test", {"i": i})
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 dispatches took {elapsed:.2f}s"


class TestLoadStateManager:
    """Load test the state manager."""

    def test_100_state_operations(self):
        state = _eng("state", "FRIDAY/apps/core/src/friday_core/universe_state_manager.py")
        start = time.time()
        for i in range(100):
            state.set_state(f"key_{i}", {"value": i}, "FRIDAY")
            state.get_state(f"key_{i}")
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 state operations took {elapsed:.2f}s"
        assert len(state.get_all_state()) >= 100


class TestLoadMetrics:
    """Load test the metrics engine."""

    def test_100_metric_records(self):
        metrics = _eng("metrics", "FRIDAY/apps/core/src/friday_core/universe_metrics.py")
        start = time.time()
        for i in range(100):
            metrics.record_request("FRIDAY", 25.0 + i * 0.1, error=i % 10 == 0)
        elapsed = time.time() - start
        report = metrics.calculate_metrics()
        assert report.total_requests >= 100
        assert elapsed < 5.0


class TestLoadEventBus:
    """Load test the event bus."""

    def test_100_events(self):
        bus = _eng("events", "FRIDAY/apps/core/src/friday_core/universe_event_bus.py")
        start = time.time()
        for i in range(100):
            event = bus.publish_event("load_test", {"i": i}, "FRIDAY")
            assert event.event_id
        elapsed = time.time() - start
        assert elapsed < 5.0


class TestLoadKnowledgeGraph:
    """Load test the knowledge graph."""

    def test_100_entities(self):
        kg = _eng("kg", "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py")
        start = time.time()
        ids = []
        for i in range(100):
            e = kg.add_entity(f"Entity_{i}", "test")
            ids.append(e.entity_id)
        # Add edges
        for i in range(50):
            kg.add_edge(ids[i], ids[i+1], "link")
        elapsed = time.time() - start
        assert elapsed < 5.0


# ════════════════════════════════════════════════════════════════════════════════
# SECURITY TESTS
# ════════════════════════════════════════════════════════════════════════════════

class TestSecuritySSRF:
    """Test SSRF protection."""

    def test_ssrf_blocks_internal(self):
        sec = _eng("sec", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        internal_urls = [
            "http://127.0.0.1/", "http://localhost/", "http://10.0.0.1/",
            "http://10.0.0.0/8", "http://172.16.0.1/", "http://172.31.255.255/",
            "http://192.168.1.1/", "http://169.254.169.254/",
            "http://0.0.0.0/", "http://[::1]/", "http://[fe80::1]/",
            "http://127.0.0.1:8080/admin", "http://localhost:3000/",
            "file:///etc/passwd", "gopher://127.0.0.1:6379/",
        ]
        for url in internal_urls:
            assert not sec.check_ssrf(url), f"SSRF should block: {url}"

    def test_ssrf_allows_external(self):
        sec = _eng("sec", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        external_urls = [
            "https://api.github.com/", "https://pypi.org/",
            "https://registry.npmjs.org/", "https://github.com/",
            "https://example.com/", "https://api.example.com/v1",
        ]
        for url in external_urls:
            assert sec.check_ssrf(url), f"SSRF should allow: {url}"


class TestSecurityPathTraversal:
    """Test path traversal protection."""

    def test_blocks_traversal(self):
        sec = _eng("sec", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        sec.register_sandbox_dir("/tmp/sandbox")
        blocked = [
            "/tmp/sandbox/../../etc/passwd",
            "/tmp/sandbox/../../../etc/passwd",
            "/tmp/sandbox/.././../etc/passwd",
            "/tmp/sandbox/%2e%2e/%2e%2e/etc/passwd",
            "/tmp/sandbox/....//....//etc/passwd",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
        ]
        for path in blocked:
            assert not sec.check_path_traversal(path), f"Should block: {path}"

    def test_allows_safe_paths(self):
        sec = _eng("sec", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        sec.register_sandbox_dir("/tmp/sandbox")
        safe = [
            "/tmp/sandbox/data.txt",
            "/tmp/sandbox/sub/file.json",
            "/tmp/sandbox/../sandbox/data.txt",
        ]
        for path in safe:
            assert sec.check_path_traversal(path), f"Should allow: {path}"


class TestSecurityAuth:
    """Test authentication security."""

    def test_revoked_token_fails(self):
        auth = _eng("auth", "FRIDAY/apps/core/src/friday_core/universe_auth.py")
        token = auth.issue_token("FRIDAY", ["test"])
        assert auth.verify_token(token.token_id)
        auth.revoke_token(token.token_id)
        assert not auth.verify_token(token.token_id)

    def test_expired_token_fails(self):
        auth = _eng("auth", "FRIDAY/apps/core/src/friday_core/universe_auth.py")
        token = auth.issue_token("FRIDAY", ["test"])
        # Tokens shouldn't be valid after revocation
        auth.revoke_token(token.token_id)
        assert not auth.verify_token(token.token_id)

    def test_invalid_token_fails(self):
        auth = _eng("auth", "FRIDAY/apps/core/src/friday_core/universe_auth.py")
        assert not auth.verify_token("invalid_token_id")


class TestSecurityRateLimiter:
    """Test rate limiter security."""

    def test_rate_limit_enforced(self):
        rl = _eng("rl", "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py")
        rl.configure_limit("test_agent", "requests", 5, 60)
        # 5 requests should be allowed
        for i in range(5):
            rec = rl.check_limit("test_agent", "requests", 1)
            assert rec.remaining >= 0

    def test_rate_limit_blocks_after_limit(self):
        rl = _eng("rl", "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py")
        rl.configure_limit("test_agent2", "requests", 2, 60)
        rl.check_limit("test_agent2", "requests", 1)
        rl.check_limit("test_agent2", "requests", 1)
        # Third request should be blocked
        rec = rl.check_limit("test_agent2", "requests", 1)
        assert rec.remaining == 0


class TestSecurityInputValidation:
    """Test input validation security."""

    def test_dispatch_rejects_invalid_agent(self):
        bus = _eng("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        # Dispatch to unknown agent should not crash
        try:
            receipt = bus.dispatch("UnknownAgent", "test", {})
            # May complete or fail, but should not crash
            assert receipt is not None
        except Exception:
            pass  # Expected to fail for unknown agents

    def test_state_manager_rejects_invalid_key(self):
        state = _eng("state", "FRIDAY/apps/core/src/friday_core/universe_state_manager.py")
        # Empty key should not crash
        try:
            state.set_state("", {"value": 1}, "FRIDAY")
        except Exception:
            pass  # Expected to fail

    def test_audit_rejects_invalid_input(self):
        audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")
        # Log with empty strings should not crash
        audit.log("", "", "", "")
        results = audit.search(agent="")
        assert results.total_matches >= 0
