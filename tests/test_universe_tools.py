"""
tests/test_universe_tools.py — Tests for universe tooling (persistence, integrations, dashboard).

Priority 2-5: Real Dependencies, Dashboard, Deployment, External Integrations
"""
import os
import sys
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


class TestPersistence:
    """Test SQLite-backed persistence backends."""

    def test_state_manager(self):
        from universe_persistence import SQLiteStateManager
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            sm = SQLiteStateManager(os.path.join(tmp, "state.db"))
            sm.set_state("key1", {"value": 42}, "FRIDAY")
            result = sm.get_state("key1")
            assert result["value"]["value"] == 42
            assert result["version"] == 1

    def test_audit_trail(self):
        from universe_persistence import SQLiteAuditTrail
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            at = SQLiteAuditTrail(os.path.join(tmp, "audit.db"))
            at.log("FRIDAY", "dispatch", "Inference", "success")
            at.log("Cortex", "decide", "budget", "success")
            results = at.search(agent="FRIDAY")
            assert results["total_matches"] >= 1

    def test_event_bus(self):
        from universe_persistence import SQLiteEventBus
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            eb = SQLiteEventBus(os.path.join(tmp, "events.db"))
            event = eb.publish("test", {"data": "test"}, "Cortex")
            assert event["event_id"]
            events = eb.get_events(event_type="test")
            assert len(events) >= 1

    def test_metrics(self):
        from universe_persistence import SQLiteMetrics
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            m = SQLiteMetrics(os.path.join(tmp, "metrics.db"))
            m.record_request("FRIDAY", 25.0)
            m.record_request("Stratex", 150.0, error=True)
            report = m.get_report()
            assert report["total_requests"] == 2
            assert report["total_errors"] == 1

    def test_persistence_manager(self):
        from universe_persistence import UniversePersistence
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            perm = UniversePersistence(tmp)
            health = perm.health_check()
            assert health["sqlite_state"]
            assert health["sqlite_audit"]
            assert health["sqlite_events"]
            assert health["sqlite_metrics"]

    def test_state_persistence_across_instances(self):
        from universe_persistence import SQLiteStateManager
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "state.db")
            sm1 = SQLiteStateManager(db)
            sm1.set_state("persistent_key", {"value": 99}, "FRIDAY")
            # New instance should see the data
            sm2 = SQLiteStateManager(db)
            result = sm2.get_state("persistent_key")
            assert result["value"]["value"] == 99

    def test_audit_persistence_across_instances(self):
        from universe_persistence import SQLiteAuditTrail
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "audit.db")
            at1 = SQLiteAuditTrail(db)
            at1.log("FRIDAY", "test", "target", "success")
            at2 = SQLiteAuditTrail(db)
            results = at2.search(agent="FRIDAY")
            assert results["total_matches"] >= 1


class TestExternalIntegrations:
    """Test external integration adapters."""

    def test_rest_client_creation(self):
        from universe_external_integrations import RESTClient
        client = RESTClient("https://api.example.com", "test-key")
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"

    def test_github_integration(self):
        from universe_external_integrations import GitHubIntegration
        gh = GitHubIntegration(token="test", repo="test/repo")
        assert gh.repo == "test/repo"

    def test_github_no_repo(self):
        from universe_external_integrations import GitHubIntegration
        gh = GitHubIntegration()
        result = gh.get_repo()
        assert "error" in result

    def test_slack_integration(self):
        from universe_external_integrations import SlackIntegration
        slack = SlackIntegration(webhook_url="https://hooks.slack.com/test")
        assert slack.webhook_url == "https://hooks.slack.com/test"

    def test_webhook_subscribe(self):
        from universe_external_integrations import WebhookIntegration
        wh = WebhookIntegration()
        sub = wh.subscribe("agent_event", "https://example.com/webhook")
        assert sub["url"] == "https://example.com/webhook"

    def test_webhook_unsubscribe(self):
        from universe_external_integrations import WebhookIntegration
        wh = WebhookIntegration()
        wh.subscribe("agent_event", "https://example.com/webhook")
        result = wh.unsubscribe("agent_event", "https://example.com/webhook")
        assert result

    def test_oci_integration(self):
        from universe_external_integrations import OCIIntegration
        oci = OCIIntegration(
            tenancy_ocid="ocid1.tenancy",
            user_ocid="ocid1.user",
            fingerprint="aa:bb:cc:dd",
            region="us-ashburn-1"
        )
        assert oci.available

    def test_oci_not_configured(self):
        from universe_external_integrations import OCIIntegration
        oci = OCIIntegration()
        assert not oci.available

    def test_oci_object_storage_url(self):
        from universe_external_integrations import OCIIntegration
        oci = OCIIntegration(region="us-ashburn-1")
        url = oci.get_object_storage_url("bucket", "namespace", "file.txt")
        assert "objectstorage" in url

    def test_integrations_manager(self):
        from universe_external_integrations import UniverseIntegrations
        manager = UniverseIntegrations()
        health = manager.health_check()
        assert "github" in health
        assert "slack" in health
        assert "webhooks" in health
        assert "oci" in health

    def test_notification(self):
        from universe_external_integrations import UniverseIntegrations
        manager = UniverseIntegrations()
        manager.webhooks.subscribe("agent_event", "https://httpbin.org/post")
        result = manager.notify("FRIDAY", "Test notification", "info")
        assert "webhooks" in result


class TestDashboard:
    """Test dashboard module loads and has endpoints."""

    def test_dashboard_module_loads(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_dash_test", str(ROOT / "tools" / "universe_dashboard.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_dash_test"] = mod
        spec.loader.exec_module(mod)
        assert mod.app is not None
        assert hasattr(mod.app, "routes")

    def test_dashboard_html_contains_key_elements(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_dash_test2", str(ROOT / "tools" / "universe_dashboard.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_dash_test2"] = mod
        spec.loader.exec_module(mod)
        html = mod.DASHBOARD_HTML
        assert "FRIDAY Universe Dashboard" in html
        assert "agent" in html.lower()
        assert "dispatch" in html.lower()
        assert "metrics" in html.lower()

    def test_dashboard_has_api_routes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_dash_test3", str(ROOT / "tools" / "universe_dashboard.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_dash_test3"] = mod
        spec.loader.exec_module(mod)
        routes = [r.path for r in mod.app.routes]
        assert "/api/health" in routes
        assert "/api/agents" in routes
        assert "/api/dispatch" in routes
        assert "/api/metrics" in routes
        assert "/api/audit" in routes
        assert "/api/events" in routes
        assert "/api/mesh/route" in routes
        assert "/api/state" in routes
        assert "/" in routes
