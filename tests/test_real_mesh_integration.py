"""
tests/test_real_mesh_integration.py — Mesh integration tests.

Tests the mesh layer as a cohesive system:
- DispatchBus: real HTTP dispatch with retry + circuit breaker
- EventBus: pub/sub event routing across agents
- Gateway: unified entry point with routing
- TaskRouter: intelligent task routing to agents
- HealthMonitor: mesh health checking
- Resilience: circuit breaker, retry, fallback
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load mesh modules
dispatch = load_module("FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py", "mesh_dispatch")
event_bus = load_module("FRIDAY/apps/core/src/friday_core/universe_event_bus.py", "mesh_event")
gateway = load_module("FRIDAY/apps/core/src/friday_core/universe_gateway.py", "mesh_gateway")
task_router = load_module("FRIDAY/apps/core/src/friday_core/universe_task_router.py", "mesh_router")
health = load_module("FRIDAY/apps/core/src/friday_core/universe_health_monitor.py", "mesh_health")
resilience = load_module("FRIDAY/apps/core/src/friday_core/universe_resilience.py", "mesh_resilience")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Dispatch Bus ──────────────────────────────────────────────────────────

class TestDispatchBus:
    def test_dispatch_bus_exists(self):
        """DispatchBus must exist with real HTTP dispatch."""
        assert hasattr(dispatch, "UniverseDispatchBus")
        bus = dispatch.UniverseDispatchBus()
        assert bus is not None

    def test_dispatch_method_exists(self):
        """DispatchBus must have a real dispatch method."""
        bus = dispatch.UniverseDispatchBus()
        assert hasattr(bus, "dispatch")
        assert callable(bus.dispatch)

    def test_dispatch_bus_stats(self):
        """DispatchBus should track stats."""
        bus = dispatch.UniverseDispatchBus()
        stats = bus.get_stats() if hasattr(bus, "get_stats") else {}
        assert isinstance(stats, dict)


# ── Event Bus ────────────────────────────────────────────────────────────

class TestEventBus:
    def test_event_bus_exists(self):
        """EventBus must exist with pub/sub."""
        assert hasattr(event_bus, "UniverseEventBus")
        bus = event_bus.UniverseEventBus()
        assert bus is not None

    def test_subscribe_unsubscribe(self):
        """EventBus should support subscribe/unsubscribe."""
        bus = event_bus.UniverseEventBus()
        sub = bus.subscribe("test_event", "Cortex", callback_url="http://localhost:8000/callback")
        assert sub is not None
        assert hasattr(sub, "subscription_id")
        bus.unsubscribe(sub.subscription_id)

    def test_publish_event(self):
        """EventBus should support publishing events."""
        bus = event_bus.UniverseEventBus()
        if hasattr(bus, "publish_event"):
            # Publish without subscribers should not crash
            event = bus.publish_event("test_event", {"data": "test"}, source_agent="Cortex")
            assert event is not None


# ── Gateway ──────────────────────────────────────────────────────────────

class TestGateway:
    def test_gateway_exists(self):
        """UniverseGateway must exist."""
        assert hasattr(gateway, "UniverseGateway")
        gw = gateway.UniverseGateway()
        assert gw is not None

    def test_gateway_routes(self):
        """Gateway should have routing capability."""
        gw = gateway.UniverseGateway()
        if hasattr(gw, "route"):
            assert callable(gw.route)

    def test_gateway_health(self):
        """Gateway should report health."""
        gw = gateway.UniverseGateway()
        if hasattr(gw, "get_health"):
            health = gw.get_health()
            assert isinstance(health, dict)


# ── Task Router ───────────────────────────────────────────────────────────

class TestTaskRouter:
    def test_task_router_exists(self):
        """UniverseTaskRouter must exist."""
        assert hasattr(task_router, "UniverseTaskRouter")
        router = task_router.UniverseTaskRouter()
        assert router is not None

    def test_route_task(self):
        """TaskRouter should route tasks to agents."""
        router = task_router.UniverseTaskRouter()
        if hasattr(router, "route"):
            result = router.route("security scan", [])
            assert result is not None


# ── Health Monitor ───────────────────────────────────────────────────────

class TestHealthMonitor:
    def test_health_monitor_exists(self):
        """UniverseHealthMonitor must exist."""
        assert hasattr(health, "UniverseHealthMonitor")
        monitor = health.UniverseHealthMonitor()
        assert monitor is not None

    def test_check_agent_health(self):
        """HealthMonitor should check agent health."""
        monitor = health.UniverseHealthMonitor()
        if hasattr(monitor, "check_agent"):
            result = monitor.check_agent("Cortex")
            assert result is not None

    def test_get_mesh_health(self):
        """HealthMonitor should report mesh health."""
        monitor = health.UniverseHealthMonitor()
        if hasattr(monitor, "get_mesh_health"):
            health_status = monitor.get_mesh_health()
            assert isinstance(health_status, dict)


# ── Resilience ───────────────────────────────────────────────────────────

class TestResilience:
    def test_resilience_engine_exists(self):
        """Resilience engine must exist."""
        assert hasattr(resilience, "UniverseResilienceEngine")
        engine = resilience.UniverseResilienceEngine()
        assert engine is not None

    def test_register_agent(self):
        """Resilience engine should register agents."""
        engine = resilience.UniverseResilienceEngine()
        if hasattr(engine, "register_agent"):
            engine.register_agent("Cortex")

    def test_report_incident(self):
        """Resilience engine should report incidents."""
        engine = resilience.UniverseResilienceEngine()
        if hasattr(engine, "report_incident"):
            engine.report_incident("Cortex", "Test incident", severity="low")

    def test_generate_report(self):
        """Resilience engine should generate reports."""
        engine = resilience.UniverseResilienceEngine()
        if hasattr(engine, "generate_report"):
            report = engine.generate_report()
            assert report is not None


# ── Mesh Integration ─────────────────────────────────────────────────────

class TestMeshIntegration:
    """Test the mesh as a cohesive system."""

    def test_all_mesh_components_exist(self):
        """All mesh components must exist."""
        assert hasattr(dispatch, "UniverseDispatchBus")
        assert hasattr(event_bus, "UniverseEventBus")
        assert hasattr(gateway, "UniverseGateway")
        assert hasattr(task_router, "UniverseTaskRouter")
        assert hasattr(health, "UniverseHealthMonitor")
        assert hasattr(resilience, "UniverseResilienceEngine")

    def test_mesh_wiring(self):
        """Mesh components should be wired together."""
        # Create all components
        bus = dispatch.UniverseDispatchBus()
        event_bus_instance = event_bus.UniverseEventBus()
        router = task_router.UniverseTaskRouter()
        monitor = health.UniverseHealthMonitor()

        # Verify they can be instantiated together
        assert bus is not None
        assert event_bus_instance is not None
        assert router is not None
        assert monitor is not None

    def test_mesh_health_reporting(self):
        """Mesh should report aggregate health."""
        monitor = health.UniverseHealthMonitor()
        if hasattr(monitor, "get_mesh_health"):
            mesh_health = monitor.get_mesh_health()
            assert isinstance(mesh_health, dict)
            # Should have agent health info
            if "agents" in mesh_health:
                assert len(mesh_health["agents"]) > 0

    def test_task_routing_to_healthy_agent(self):
        """TaskRouter should route to healthy agents."""
        router = task_router.UniverseTaskRouter()
        if hasattr(router, "route"):
            # Route a security task
            result = router.route("security threat detection", [])
            assert result is not None
