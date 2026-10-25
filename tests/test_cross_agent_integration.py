"""
tests/test_cross_agent_integration.py — Cross-agent integration tests.

Tests FRIDAY dispatch to all 9 specialists, specialist-to-specialist
peer calls, security hardening, and authentication across the universe.
"""
import sys
import os
import py_compile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../FRIDAY/apps/core/src"))


class TestCrossAgentDispatch:
    """Tests for FRIDAY dispatch bus to all 9 specialists."""

    SPECIALISTS = [
        "Inference", "Memora", "Stratex", "Forge", "Cortex",
        "Sentinel", "IntelX", "Futuris", "VyralX",
    ]

    def test_dispatch_bus_module_compiles(self):
        """Test that the dispatch bus module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        py_compile.compile(path, doraise=True)

    def test_dispatch_bus_registers_all_agents(self):
        """Test that the dispatch bus registers all 9 specialists."""
        try:
            from friday_core.universe_dispatch_bus import engine as dispatch_engine
            status = dispatch_engine.get_all_agent_status()
            agent_names = {s["agent_name"] for s in status}
            for specialist in self.SPECIALISTS:
                assert specialist in agent_names, f"{specialist} not registered in dispatch bus"
        except ImportError:
            pytest.skip("Dispatch bus not available")

    def test_dispatch_bus_report(self):
        """Test dispatch bus report."""
        try:
            from friday_core.universe_dispatch_bus import engine as dispatch_engine
            report = dispatch_engine.get_report()
            assert report["total_agents"] >= 9
            assert report["engine_status"] == "operational"
        except ImportError:
            pytest.skip("Dispatch bus not available")

    def test_dispatch_to_each_specialist(self):
        """Test dispatching to each specialist."""
        try:
            from friday_core.universe_dispatch_bus import engine as dispatch_engine
            for specialist in self.SPECIALISTS:
                receipt = dispatch_engine.dispatch(
                    specialist, "test_action", {"test": True}
                )
                assert receipt.status == "completed"
                assert receipt.agent == specialist
        except ImportError:
            pytest.skip("Dispatch bus not available")


class TestCrossAgentIntegration:
    """Tests for specialist-to-specialist peer calls."""

    INTEGRATIONS = [
        ("Forge", "Sentinel"),
        ("VyralX", "Inference"),
        ("VyralX", "Sentinel"),
        ("IntelX", "Memora"),
        ("Futuris", "IntelX"),
        ("Stratex", "Futuris"),
        ("Cortex", "Memora"),
        ("Sentinel", "IntelX"),
    ]

    def test_integration_module_compiles(self):
        """Test that the integration module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py")
        py_compile.compile(path, doraise=True)

    def test_default_integrations_registered(self):
        """Test that all default integrations are registered."""
        try:
            from friday_core.cross_agent_integration import engine as integration_engine
            integrations = integration_engine.get_integrations()
            for caller, callee in self.INTEGRATIONS:
                found = any(
                    i["caller"] == caller and i["callee"] == callee
                    for i in integrations
                )
                assert found, f"Integration {caller} -> {callee} not registered"
        except ImportError:
            pytest.skip("Integration engine not available")

    def test_peer_calls(self):
        """Test making peer calls between agents."""
        try:
            from friday_core.cross_agent_integration import engine as integration_engine
            for caller, callee in self.INTEGRATIONS[:4]:
                call = integration_engine.call_peer(caller, callee, {"test": True})
                assert call.status == "completed"
                assert call.caller == caller
                assert call.callee == callee
        except ImportError:
            pytest.skip("Integration engine not available")

    def test_integration_report(self):
        """Test integration report."""
        try:
            from friday_core.cross_agent_integration import engine as integration_engine
            report = integration_engine.get_report()
            assert report["total_integrations"] >= 8
            assert report["engine_status"] == "operational"
        except ImportError:
            pytest.skip("Integration engine not available")


class TestSecurityHardening:
    """Tests for security hardening across all agents."""

    def test_security_module_compiles(self):
        """Test that the security hardening module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        py_compile.compile(path, doraise=True)

    def test_ssrf_blocks_localhost(self):
        """Test SSRF protection blocks localhost."""
        try:
            from friday_core.security_hardening import engine as security_engine
            assert not security_engine.check_ssrf("http://127.0.0.1:8000/api")
            assert not security_engine.check_ssrf("http://localhost:8000")
        except ImportError:
            pytest.skip("Security engine not available")

    def test_ssrf_blocks_cloud_metadata(self):
        """Test SSRF protection blocks cloud metadata."""
        try:
            from friday_core.security_hardening import engine as security_engine
            assert not security_engine.check_ssrf("http://169.254.169.254/latest/meta-data/")
        except ImportError:
            pytest.skip("Security engine not available")

    def test_ssrf_allows_public_urls(self):
        """Test SSRF protection allows public URLs."""
        try:
            from friday_core.security_hardening import engine as security_engine
            assert security_engine.check_ssrf("https://api.example.com/data")
        except ImportError:
            pytest.skip("Security engine not available")

    def test_path_traversal_blocks_escape(self):
        """Test path traversal protection."""
        try:
            from friday_core.security_hardening import engine as security_engine
            security_engine.register_sandbox_dir("/tmp/sandbox")
            assert not security_engine.check_path_traversal("/tmp/sandbox/../etc/passwd")
        except ImportError:
            pytest.skip("Security engine not available")

    def test_input_validation_blocks_scripts(self):
        """Test input validation blocks script tags."""
        try:
            from friday_core.security_hardening import engine as security_engine
            assert not security_engine.check_input("<script>alert('xss')</script>")
            assert not security_engine.check_input("javascript:alert(1)")
        except ImportError:
            pytest.skip("Security engine not available")

    def test_security_report(self):
        """Test security hardening report."""
        try:
            from friday_core.security_hardening import engine as security_engine
            report = security_engine.get_report()
            assert report["engine_status"] == "operational"
            assert report["policies_enabled"] >= 5
        except ImportError:
            pytest.skip("Security engine not available")


class TestUniverseAuth:
    """Tests for universe authentication."""

    def test_auth_module_compiles(self):
        """Test that the auth module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_auth.py")
        py_compile.compile(path, doraise=True)

    def test_default_agents_registered(self):
        """Test that all default agents are registered."""
        try:
            from friday_core.universe_auth import engine as auth_engine
            agents = auth_engine.list_agents()
            agent_names = {a["agent_name"] for a in agents}
            for agent in ["FRIDAY", "Inference", "Memora", "Stratex", "Forge",
                          "Cortex", "Sentinel", "IntelX", "Futuris", "VyralX"]:
                assert agent in agent_names, f"{agent} not registered in auth"
        except ImportError:
            pytest.skip("Auth engine not available")

    def test_agent_capabilities(self):
        """Test agent capabilities."""
        try:
            from friday_core.universe_auth import engine as auth_engine
            assert auth_engine.verify_capability("FRIDAY", "orchestration")
            assert auth_engine.verify_capability("Inference", "reasoning")
            assert auth_engine.verify_capability("Stratex", "trading")
            assert not auth_engine.verify_capability("Inference", "trading")
        except ImportError:
            pytest.skip("Auth engine not available")

    def test_token_issue_and_verify(self):
        """Test token issue and verification."""
        try:
            from friday_core.universe_auth import engine as auth_engine
            token = auth_engine.issue_token("FRIDAY")
            assert auth_engine.verify_token(token.token_id)
            auth_engine.revoke_token(token.token_id)
            assert not auth_engine.verify_token(token.token_id)
        except ImportError:
            pytest.skip("Auth engine not available")

    def test_auth_report(self):
        """Test authentication report."""
        try:
            from friday_core.universe_auth import engine as auth_engine
            report = auth_engine.get_report()
            assert report["total_agents"] >= 10
            assert report["engine_status"] == "operational"
        except ImportError:
            pytest.skip("Auth engine not available")


class TestErrorEnvelope:
    """Tests for unified error handling."""

    def test_error_envelope_compiles(self):
        """Test that the error envelope module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/error_envelope.py")
        py_compile.compile(path, doraise=True)

    def test_error_codes_defined(self):
        """Test that standard error codes are defined."""
        try:
            from friday_core.error_envelope import ERROR_CODES
            assert 400 in ERROR_CODES
            assert 401 in ERROR_CODES
            assert 404 in ERROR_CODES
            assert 500 in ERROR_CODES
            assert 503 in ERROR_CODES
        except ImportError:
            pytest.skip("Error envelope not available")


class TestUniverseGateway:
    """Tests for unified API gateway."""

    def test_gateway_compiles(self):
        """Test that the gateway module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_gateway.py")
        py_compile.compile(path, doraise=True)

    def test_gateway_registers_all_agents(self):
        """Test that the gateway registers all agents."""
        try:
            from friday_core.universe_gateway import engine as gateway_engine
            agents = gateway_engine.get_all_agents_health()
            assert len(agents) >= 9
        except ImportError:
            pytest.skip("Gateway not available")

    def test_gateway_report(self):
        """Test gateway report."""
        try:
            from friday_core.universe_gateway import engine as gateway_engine
            report = gateway_engine.get_report()
            assert report["total_agents"] >= 9
            assert report["engine_status"] == "operational"
        except ImportError:
            pytest.skip("Gateway not available")


class TestUniverseConfig:
    """Tests for unified configuration."""

    def test_config_compiles(self):
        """Test that the config module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_config.py")
        py_compile.compile(path, doraise=True)

    def test_config_registers_all_agents(self):
        """Test that config registers all agents."""
        try:
            from friday_core.universe_config import engine as config_engine
            agents = config_engine.get_all_agents()
            assert len(agents) >= 10
        except ImportError:
            pytest.skip("Config not available")

    def test_config_validation(self):
        """Test config validation."""
        try:
            from friday_core.universe_config import engine as config_engine
            results = config_engine.validate_config()
            assert results["total_agents"] >= 10
            assert results["valid_agents"] >= 10
        except ImportError:
            pytest.skip("Config not available")


class TestUniverseMetrics:
    """Tests for universe-level monitoring."""

    def test_metrics_compiles(self):
        """Test that the metrics module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_metrics.py")
        py_compile.compile(path, doraise=True)

    def test_metrics_registers_agents(self):
        """Test that metrics registers all agents."""
        try:
            from friday_core.universe_metrics import engine as metrics_engine
            for agent in ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                          "Sentinel", "IntelX", "Futuris", "VyralX"]:
                metrics_engine.record_request(agent, 100.0, error=False)
            report = metrics_engine.calculate_metrics()
            assert report.total_requests >= 9
        except ImportError:
            pytest.skip("Metrics not available")

    def test_prometheus_format(self):
        """Test Prometheus metrics format."""
        try:
            from friday_core.universe_metrics import engine as metrics_engine
            metrics_engine.record_request("FRIDAY", 50.0, error=False)
            prometheus_text = metrics_engine.get_prometheus_metrics()
            assert "agent_requests_total" in prometheus_text
            assert "agent_health_score" in prometheus_text
        except ImportError:
            pytest.skip("Metrics not available")


class TestUniverseHealthMonitor:
    """Tests for universe health monitoring."""

    def test_health_monitor_compiles(self):
        """Test that the health monitor module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py")
        py_compile.compile(path, doraise=True)

    def test_health_monitor_registers_agents(self):
        """Test that health monitor registers all agents."""
        try:
            from friday_core.universe_health_monitor import engine as health_engine
            snapshot = health_engine.get_universe_health()
            assert snapshot.total_agents >= 9
            assert snapshot.overall_score >= 0
        except ImportError:
            pytest.skip("Health monitor not available")


class TestAgentMeshRouter:
    """Tests for agent mesh routing."""

    def test_mesh_router_compiles(self):
        """Test that the mesh router module compiles."""
        path = os.path.join(os.path.dirname(__file__), "..",
                            "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py")
        py_compile.compile(path, doraise=True)

    def test_mesh_router_routes_tasks(self):
        """Test that mesh router routes tasks to agents."""
        try:
            from friday_core.agent_mesh_router import engine as mesh_engine
            decision = mesh_engine.route_task("analyze trading signals", "trading")
            assert decision.routed_to == "Stratex"
            assert decision.confidence > 0
        except ImportError:
            pytest.skip("Mesh router not available")

    def test_mesh_router_report(self):
        """Test mesh router report."""
        try:
            from friday_core.agent_mesh_router import engine as mesh_engine
            report = mesh_engine.get_report()
            assert report["total_agents"] >= 9
            assert report["engine_status"] == "operational"
        except ImportError:
            pytest.skip("Mesh router not available")
