"""
tests/test_agent_marketplace.py — Tests for agent marketplace and inter-agent communication.

Tests service discovery, registration, invocation, rate limiting,
HTTP client, and marketplace reporting.

Priority 3-5: Marketplace, HTTP, Integration
"""
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)

import universe_agent_marketplace as mp_mod


class TestServiceDiscovery:
    """Test service discovery in the marketplace."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.marketplace = mp_mod.AgentMarketplace()

    def test_default_services_registered(self):
        services = self.marketplace.discover_services()
        assert len(services) >= 30  # At least 30 default services

    def test_discover_by_agent(self):
        services = self.marketplace.discover_services(agent="Inference")
        assert len(services) >= 3
        for svc in services:
            assert svc.agent == "Inference"

    def test_discover_by_name(self):
        services = self.marketplace.discover_services(service_name="reasoning")
        assert len(services) >= 1
        for svc in services:
            assert svc.service_name == "reasoning"

    def test_discover_by_capability(self):
        services = self.marketplace.discover_by_capability("security")
        assert len(services) >= 2  # At least 2 security services

    def test_all_agents_have_services(self):
        services = self.marketplace.discover_services()
        agents = set(svc.agent for svc in services)
        assert "FRIDAY" in agents
        assert "Inference" in agents
        assert "Cortex" in agents
        assert "Forge" in agents


class TestServiceRegistration:
    """Test service registration and unregistration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.marketplace = mp_mod.AgentMarketplace()

    def test_register_service(self):
        svc = self.marketplace.register_service(
            "TestAgent", "test_service", "A test service", "/api/test", 0.5
        )
        assert svc.service_id.startswith("svc_")
        assert svc.agent == "TestAgent"
        assert svc.available is True

    def test_register_and_discover(self):
        self.marketplace.register_service(
            "TestAgent", "custom_service", "Custom", "/api/custom", 0.1
        )
        services = self.marketplace.discover_services(service_name="custom_service")
        assert len(services) == 1

    def test_unregister_service(self):
        svc = self.marketplace.register_service(
            "TestAgent", "temp", "Temp", "/api/temp", 0.0
        )
        result = self.marketplace.unregister_service(svc.service_id)
        assert result is True
        services = self.marketplace.discover_services(service_name="temp")
        assert len(services) == 0

    def test_unregister_nonexistent(self):
        result = self.marketplace.unregister_service("svc_nonexistent")
        assert result is False


class TestServiceCall:
    """Test inter-agent service calls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.marketplace = mp_mod.AgentMarketplace()

    def test_call_service(self):
        call = self.marketplace.call_service(
            "FRIDAY", "Inference", "reasoning", {"query": "test"}
        )
        assert call.status == "completed"
        assert call.caller == "FRIDAY"
        assert call.callee == "Inference"
        assert call.result is not None and len(call.result) > 0

    def test_call_nonexistent_service(self):
        call = self.marketplace.call_service(
            "FRIDAY", "Inference", "nonexistent_service", {}
        )
        assert call.status == "failed"
        assert "not found" in call.error

    def test_call_nonexistent_agent(self):
        call = self.marketplace.call_service(
            "FRIDAY", "NonexistentAgent", "test", {}
        )
        assert call.status == "failed"

    def test_call_history(self):
        self.marketplace.call_service("FRIDAY", "Cortex", "decision", {"decision": "test"})
        self.marketplace.call_service("Stratex", "Futuris", "quantum_forecast", {})
        history = self.marketplace.get_call_history()
        assert len(history) == 2

    def test_call_history_by_agent(self):
        self.marketplace.call_service("FRIDAY", "Cortex", "decision", {})
        self.marketplace.call_service("Stratex", "Futuris", "quantum_forecast", {})
        history = self.marketplace.get_call_history(agent="FRIDAY")
        assert len(history) == 1
        assert history[0].caller == "FRIDAY"


class TestMarketplaceReport:
    """Test marketplace reporting."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.marketplace = mp_mod.AgentMarketplace()

    def test_report(self):
        report = self.marketplace.get_marketplace_report()
        assert report["total_services"] >= 30
        assert report["total_calls"] == 0
        assert report["completed_calls"] == 0
        assert report["failed_calls"] == 0

    def test_report_after_calls(self):
        self.marketplace.call_service("FRIDAY", "Inference", "reasoning", {})
        self.marketplace.call_service("FRIDAY", "Cortex", "decision", {})
        report = self.marketplace.get_marketplace_report()
        assert report["total_calls"] == 2
        assert report["completed_calls"] == 2

    def test_services_by_agent_in_report(self):
        report = self.marketplace.get_marketplace_report()
        assert "services_by_agent" in report
        assert "Inference" in report["services_by_agent"]
        assert "FRIDAY" in report["services_by_agent"]


class TestInterAgentHTTPClient:
    """Test the inter-agent HTTP client."""

    def test_http_client_base_urls(self):
        client = mp_mod.InterAgentHTTPClient()
        assert len(client._base_urls) >= 10
        assert "FRIDAY" in client._base_urls
        assert "Cortex" in client._base_urls

    def test_http_client_set_base_url(self):
        client = mp_mod.InterAgentHTTPClient()
        client.set_base_url("TestAgent", "http://localhost:9999/")
        assert client._base_urls["TestAgent"] == "http://localhost:9999"

    def test_http_client_call_log(self):
        client = mp_mod.InterAgentHTTPClient()
        assert len(client.get_call_log()) == 0
        client.clear_log()
        assert len(client.get_call_log()) == 0

    def test_http_client_unreachable_agent(self):
        client = mp_mod.InterAgentHTTPClient()
        client.set_base_url("TestAgent", "http://127.0.0.1:99999")
        result = client.get("TestAgent", "/api/test")
        assert "error" in result