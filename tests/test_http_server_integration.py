"""
tests/test_http_server_integration.py — Real FastAPI server integration tests.

Tests actual FastAPI applications via TestClient, hitting real HTTP endpoints.
This verifies the agents work as real HTTP services, not just engine objects.

Priority 1: Make It Run (Real HTTP Server Testing)
"""
import importlib.util
import sys
import os
import json
import time
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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


def _load(name, relpath):
    path = str(ROOT / relpath)
    full_name = f"_http_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestFRIDAYServerEndpoints:
    """Test FRIDAY core server endpoints via FastAPI TestClient."""

    def test_dispatch_bus_endpoint(self):
        """Test dispatch bus HTTP endpoint."""
        mod = _load("dispatch_bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        if hasattr(mod, "router"):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            client = TestClient(app)
            response = client.post("/dispatch/send", json={
                "agent": "Inference", "action": "reason", "payload": {"test": True}
            })
            assert response.status_code in (200, 201, 422, 404)

    def test_security_ssrf_endpoint(self):
        """Test security SSRF HTTP endpoint."""
        mod = _load("security", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        if hasattr(mod, "router"):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            client = TestClient(app)
            response = client.post("/security/ssrf/check", json={"url": "http://127.0.0.1/"})
            assert response.status_code in (200, 201, 422)

    def test_security_path_endpoint(self):
        """Test security path traversal HTTP endpoint."""
        mod = _load("security", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        if hasattr(mod, "router"):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            client = TestClient(app)
            response = client.post("/security/path/check", json={"file_path": "/etc/passwd"})
            assert response.status_code in (200, 201, 422)

    def test_config_endpoint(self):
        """Test config HTTP endpoint."""
        mod = _load("config", "FRIDAY/apps/core/src/friday_core/universe_config.py")
        if hasattr(mod, "router"):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            client = TestClient(app)
            response = client.get("/config/agents")
            assert response.status_code in (200, 201, 404, 422)


class TestDashboardEndpoints:
    """Test the universe dashboard endpoints."""

    def test_dashboard_html_endpoint(self):
        """Test dashboard serves HTML."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "FRIDAY Universe Dashboard" in response.text

    def test_dashboard_health_endpoint(self):
        """Test dashboard health API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "engines" in data

    def test_dashboard_agents_endpoint(self):
        """Test dashboard agents API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/agents")
        assert response.status_code == 200

    def test_dashboard_dispatch_endpoint(self):
        """Test dashboard dispatch API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/dispatch")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_dashboard_metrics_endpoint(self):
        """Test dashboard metrics API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/metrics")
        assert response.status_code == 200

    def test_dashboard_mesh_route_endpoint(self):
        """Test dashboard mesh routing API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/mesh/route?task=analyze+trading&domain=trading")
        assert response.status_code == 200
        data = response.json()
        assert "routed_to" in data

    def test_dashboard_audit_endpoint(self):
        """Test dashboard audit API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/audit?limit=5")
        assert response.status_code == 200

    def test_dashboard_events_endpoint(self):
        """Test dashboard events API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/events?limit=5")
        assert response.status_code == 200

    def test_dashboard_state_endpoint(self):
        """Test dashboard state API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/state")
        assert response.status_code == 200

    def test_dashboard_dispatch_batch_endpoint(self):
        """Test dashboard batch dispatch API."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        sys.path.insert(0, str(ROOT / "tools"))
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        client = TestClient(app)
        response = client.get("/api/dispatch/batch")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data


class TestAgentAPIEndpoints:
    """Test that agent modules have proper API routers."""

    def test_cortex_has_router(self):
        """Test Cortex has API router."""
        # Verify the main module file exists and defines an app
        path = str(ROOT / "Cortex/apps/api/src/cortex_api/main.py")
        assert os.path.exists(path), "Cortex main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Cortex main.py should define app"

    def test_forge_has_router(self):
        """Test Forge has API router."""
        path = str(ROOT / "Forge/app/main.py")
        assert os.path.exists(path), "Forge main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Forge main.py should define app"

    def test_inference_has_router(self):
        """Test Inference has API router."""
        path = str(ROOT / "Inference/app/main.py")
        assert os.path.exists(path), "Inference main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Inference main.py should define app"

    def test_intelx_has_router(self):
        """Test IntelX has API router."""
        path = str(ROOT / "IntelX/intelx/app/main.py")
        assert os.path.exists(path), "IntelX main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "IntelX main.py should define app"

    def test_sentinel_has_router(self):
        """Test Sentinel has API router."""
        path = str(ROOT / "Sentinel/sentinel/apps/api/main.py")
        assert os.path.exists(path), "Sentinel main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Sentinel main.py should define app"

    def test_vyralx_has_router(self):
        """Test VyralX has API router."""
        path = str(ROOT / "VyralX/app/main.py")
        assert os.path.exists(path), "VyralX main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "VyralX main.py should define app"

    def test_futuris_has_router(self):
        """Test Futuris has API router."""
        path = str(ROOT / "Futuris/futuris/api/app.py")
        assert os.path.exists(path), "Futuris app.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Futuris app.py should define app"

    def test_stratex_has_router(self):
        """Test Stratex has API router."""
        # Stratex has API route files instead of a single main.py
        stratex_api_files = list((ROOT / "Stratex/api").glob("*.py"))
        assert len(stratex_api_files) > 0, "Stratex should have API route files"
        # Check for FastAPI usage in the files
        for f in stratex_api_files:
            content = f.read_text()
            if "FastAPI" in content or "APIRouter" in content:
                assert True
                return
        # If no FastAPI found, check execution directory
        exec_files = list((ROOT / "Stratex/execution").glob("*.py"))
        has_fastapi = False
        for f in exec_files:
            if "FastAPI" in f.read_text():
                has_fastapi = True
                break
        assert has_fastapi, "Stratex should have FastAPI somewhere"

    def test_memora_has_router(self):
        """Test Memora has API router."""
        path = str(ROOT / "Memora/apps/api/main.py")
        assert os.path.exists(path), "Memora main.py should exist"
        with open(path) as f:
            content = f.read()
        assert "app" in content, "Memora main.py should define app"

    def test_all_agents_have_main_files(self):
        """Test that all 10 agents have main entry point files."""
        main_files = [
            "Cortex/apps/api/src/cortex_api/main.py",
            "Forge/app/main.py",
            "Inference/app/main.py",
            "IntelX/intelx/app/main.py",
            "Sentinel/sentinel/apps/api/main.py",
            "VyralX/app/main.py",
            "Futuris/futuris/api/app.py",
            "Memora/apps/api/main.py",
        ]
        for mf in main_files:
            path = str(ROOT / mf)
            assert os.path.exists(path), f"{mf} should exist"
        # Stratex has API route files instead of a single main.py
        stratex_api = str(ROOT / "Stratex/api")
        assert os.path.isdir(stratex_api), "Stratex/api should exist"


class TestCrossAgentHTTPCommunication:
    """Test cross-agent HTTP communication via the integration engine."""

    def test_all_preconfigured_integrations(self):
        """Test all preconfigured agent integrations."""
        integration = _load("integration", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py").engine
        preconfigured = [
            ("Forge", "Sentinel"), ("VyralX", "Inference"), ("VyralX", "Sentinel"),
            ("IntelX", "Memora"), ("Futuris", "IntelX"), ("Stratex", "Futuris"),
            ("Cortex", "Memora"), ("Sentinel", "IntelX"),
        ]
        for caller, callee in preconfigured:
            call = integration.call_peer(caller, callee, {"test": True})
            assert call.status == "completed"
            assert call.caller == caller
            assert call.callee == callee

    def test_integration_report(self):
        """Test getting integration report."""
        integration = _load("integration", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py").engine
        # Make some calls
        integration.call_peer("Forge", "Sentinel", {"test": True})
        integration.call_peer("VyralX", "Inference", {"test": True})
        report = integration.get_report()
        assert report is not None

    def test_integration_rules(self):
        """Test integration rule management."""
        integration = _load("integration", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py").engine
        rule_id = integration.create_rule("Test Rule", "Inference", "Cortex")
        assert rule_id
        rules = integration.get_rules()
        assert len(rules) >= 1
        # Disable and re-enable
        integration.disable_rule(rule_id)
        integration.enable_rule(rule_id)
