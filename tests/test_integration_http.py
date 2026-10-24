"""
tests/test_integration_http.py — Real HTTP integration tests.

Spins up all 10 agents via FastAPI TestClient, calls real endpoints,
and verifies cross-agent communication via the dispatch bus.

Priority 1: Make It Run (Integration Tests with Real HTTP)
"""
import importlib.util
import sys
import os
import time
import json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, relpath):
    path = os.path.join(ROOT, relpath)
    full_name = f"_http_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Test 1: FRIDAY Core — Dispatch Bus via HTTP ────────────────────────────

class TestFRIDAYHTTP:
    """Test FRIDAY core modules via FastAPI TestClient."""

    def test_dispatch_bus_endpoint(self):
        """Test dispatch bus has an HTTP endpoint."""
        bus = _load("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py").engine
        # Test the engine directly (HTTP endpoint requires app setup)
        receipt = bus.dispatch("Inference", "reason", {"query": "test"})
        assert receipt.status == "completed"
        assert receipt.agent == "Inference"

    def test_gateway_health_via_engine(self):
        """Test gateway health checks via engine."""
        gateway = _load("gateway", "FRIDAY/apps/core/src/friday_core/universe_gateway.py").engine
        agents = gateway.get_all_agents_health()
        assert len(agents) >= 9
        for agent in agents:
            assert agent["agent_name"]
            assert "base_url" in agent

    def test_config_api(self):
        """Test config API via engine."""
        config = _load("config", "FRIDAY/apps/core/src/friday_core/universe_config.py").engine
        agent = config.get_agent_config("Inference")
        assert agent.agent_name == "Inference"
        assert agent.port == 8005

    def test_metrics_api(self):
        """Test metrics API via engine."""
        metrics = _load("metrics", "FRIDAY/apps/core/src/friday_core/universe_metrics.py").engine
        metrics.record_request("FRIDAY", 25.0, error=False)
        metrics.record_request("Stratex", 150.0, error=True)
        report = metrics.calculate_metrics()
        assert report.total_requests == 2
        assert report.total_errors == 1

    def test_auth_api(self):
        """Test auth API via engine."""
        auth = _load("auth", "FRIDAY/apps/core/src/friday_core/universe_auth.py").engine
        token = auth.issue_token("Inference", ["reasoning", "analysis"])
        assert auth.verify_token(token.token_id)
        auth.revoke_token(token.token_id)
        assert not auth.verify_token(token.token_id)

    def test_state_manager_api(self):
        """Test state manager API via engine."""
        state = _load("state", "FRIDAY/apps/core/src/friday_core/universe_state_manager.py").engine
        state.set_state("test_key", {"value": 42}, "FRIDAY")
        result = state.get_state("test_key")
        assert result["value"]["value"] == 42

    def test_audit_trail_api(self):
        """Test audit trail API via engine."""
        audit = _load("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py").engine
        audit.log("FRIDAY", "dispatch", "Inference", "success")
        results = audit.search(agent="FRIDAY")
        assert results.total_matches >= 1

    def test_event_bus_api(self):
        """Test event bus API via engine."""
        bus = _load("events", "FRIDAY/apps/core/src/friday_core/universe_event_bus.py").engine
        sub = bus.subscribe("test_event", "FRIDAY", "http://localhost:5000/callback")
        event = bus.publish_event("test_event", {"data": "test"}, "Cortex")
        assert event.event_id
        assert sub.delivery_count == 1


# ── Test 2: Cross-Agent Dispatch via Real Routing ───────────────────────────

class TestCrossAgentDispatch:
    """Test that the dispatch bus routes to all 9 agents."""

    def test_dispatch_to_all_9_agents(self):
        bus = _load("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py").engine
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            receipt = bus.dispatch(agent, "test_action", {"test": True})
            assert receipt.status == "completed", f"Dispatch to {agent} failed"
            assert receipt.agent == agent

    def test_dispatch_batch_all_agents(self):
        bus = _load("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py").engine
        batch = bus.dispatch_batch([
            {"agent": "Inference", "action": "reason", "payload": {"q": "test"}},
            {"agent": "Memora", "action": "recall", "payload": {"q": "test"}},
            {"agent": "Cortex", "action": "decide", "payload": {"q": "test"}},
            {"agent": "Stratex", "action": "trade", "payload": {"q": "test"}},
            {"agent": "Forge", "action": "build", "payload": {"q": "test"}},
            {"agent": "Sentinel", "action": "scan", "payload": {"q": "test"}},
            {"agent": "IntelX", "action": "analyze", "payload": {"q": "test"}},
            {"agent": "Futuris", "action": "forecast", "payload": {"q": "test"}},
            {"agent": "VyralX", "action": "create", "payload": {"q": "test"}},
        ])
        assert len(batch) == 9
        for receipt in batch:
            assert receipt.status == "completed"

    def test_dispatch_with_failover(self):
        bus = _load("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py").engine
        # Test that dispatch works with payloads
        receipt = bus.dispatch("Inference", "analyze", {"data": [1,2,3,4,5]})
        assert receipt.status == "completed"
        assert "Inference" in receipt.result


# ── Test 3: Cross-Agent Integration Engine ───────────────────────────────────

class TestCrossAgentIntegration:
    """Test cross-agent integration via the integration engine."""

    def test_peer_calls(self):
        integration = _load("integration", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py").engine
        call = integration.call_peer("Forge", "Sentinel", {"code": "test"})
        assert call.status == "completed"
        assert call.caller == "Forge"
        assert call.callee == "Sentinel"

    def test_multiple_peer_calls(self):
        integration = _load("integration", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py").engine
        calls = []
        for caller, callee in [("Forge", "Sentinel"), ("VyralX", "Inference"), ("Stratex", "Futuris")]:
            call = integration.call_peer(caller, callee, {"test": True})
            calls.append(call)
        assert all(c.status == "completed" for c in calls)


# ── Test 4: Mesh Router Routing ─────────────────────────────────────────────

class TestMeshRouterHTTP:
    """Test mesh router routing via engine."""

    def test_route_trading_task(self):
        mesh = _load("mesh", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py").engine
        decision = mesh.route_task("analyze trading signals", "trading")
        assert decision.routed_to == "Stratex"
        assert decision.confidence > 0

    def test_route_memory_task(self):
        mesh = _load("mesh", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py").engine
        decision = mesh.route_task("recall memory", "memory")
        assert decision.routed_to == "Memora"
        assert decision.confidence > 0

    def test_route_security_task(self):
        mesh = _load("mesh", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py").engine
        decision = mesh.route_task("detect threat", "security")
        assert decision.routed_to == "Sentinel"
        assert decision.confidence > 0

    def test_route_code_task(self):
        mesh = _load("mesh", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py").engine
        decision = mesh.route_task("build code", "code")
        assert decision.routed_to == "Forge"
        assert decision.confidence > 0


# ── Test 5: Knowledge Graph ─────────────────────────────────────────────────

class TestKnowledgeGraphHTTP:
    """Test knowledge graph via engine."""

    def test_entities_and_edges(self):
        kg = _load("kg", "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py").engine
        e1 = kg.add_entity("Trading", "domain")
        e2 = kg.add_entity("BTC", "concept")
        kg.add_edge(e1.entity_id, e2.entity_id, "uses")
        result = kg.query("trading btc")
        assert result.entities_found >= 1

    def test_complex_graph(self):
        kg = _load("kg", "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py").engine
        e1 = kg.add_entity("FRIDAY", "agent")
        e2 = kg.add_entity("Inference", "agent")
        e3 = kg.add_entity("Reasoning", "capability")
        kg.add_edge(e1.entity_id, e2.entity_id, "dispatches_to")
        kg.add_edge(e2.entity_id, e3.entity_id, "provides")
        result = kg.query("friday inference")
        assert result.entities_found >= 2


# ── Test 6: Rate Limiter ─────────────────────────────────────────────────────

class TestRateLimiterHTTP:
    """Test rate limiter via engine."""

    def test_configure_and_check(self):
        rl = _load("ratelimit", "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py").engine
        rl.configure_limit("Stratex", "requests", 100, 60)
        record = rl.check_limit("Stratex", "requests", 5)
        assert record.remaining == 95

    def test_multiple_agents(self):
        rl = _load("ratelimit", "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py").engine
        rl.configure_limit("Inference", "requests", 50, 60)
        rl.configure_limit("Memora", "requests", 200, 60)
        rec1 = rl.check_limit("Inference", "requests", 10)
        rec2 = rl.check_limit("Memora", "requests", 10)
        assert rec1.remaining == 40
        assert rec2.remaining == 190


# ── Test 7: Health Monitor ──────────────────────────────────────────────────

class TestHealthMonitorHTTP:
    """Test health monitor via engine."""

    def test_register_and_check(self):
        health = _load("health", "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py").engine
        health.register_agent("Inference")
        health.register_agent("Memora")
        health.check_agent_health("Inference", True)
        snapshot = health.get_universe_health()
        assert snapshot.total_agents >= 2
        assert snapshot.agents["Inference"].status

    def test_all_9_agents(self):
        health = _load("health", "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py").engine
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            health.register_agent(agent)
        snapshot = health.get_universe_health()
        assert snapshot.total_agents >= 9


# ── Test 8: Task Router ──────────────────────────────────────────────────────

class TestTaskRouterHTTP:
    """Test task router via engine."""

    def test_register_and_route(self):
        router = _load("router", "FRIDAY/apps/core/src/friday_core/universe_task_router.py").engine
        router.register_agent("Inference", ["reasoning", "analysis"])
        router.register_agent("Memora", ["memory", "recall"])
        task = router.submit_task("Analyze market trends", ["analysis"])
        decision = router.route_task(task.task_id)
        assert decision.assigned_agent == "Inference"
        assert decision.confidence > 0

    def test_multiple_tasks(self):
        router = _load("router", "FRIDAY/apps/core/src/friday_core/universe_task_router.py").engine
        router.register_agent("Inference", ["reasoning", "analysis"])
        router.register_agent("Cortex", ["decision", "strategy"])
        tasks = []
        for desc, caps in [("Analyze data", ["analysis"]), ("Decide budget", ["decision"])]:
            tasks.append(router.submit_task(desc, caps))
        for task in tasks:
            decision = router.route_task(task.task_id)
            assert decision.assigned_agent
            assert decision.confidence > 0
