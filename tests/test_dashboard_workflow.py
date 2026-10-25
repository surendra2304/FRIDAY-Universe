"""
tests/test_dashboard_workflow.py — Tests for dashboard workflow and self-improvement endpoints.

Tests all new dashboard API endpoints added for workflows, self-improvement,
knowledge sharing, and decision propagation.

Priority 3-5: Dashboard, Workflows, Self-Improvement
"""
import sys
import os
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


class TestDashboardWorkflowEndpoints:
    """Test dashboard workflow API endpoints."""

    def _get_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        return TestClient(app)

    def test_workflow_capabilities(self):
        client = self._get_client()
        response = client.get("/api/workflow/capabilities")
        assert response.status_code == 200

    def test_workflow_agents(self):
        client = self._get_client()
        response = client.get("/api/workflow/agents")
        assert response.status_code == 200

    def test_workflow_run_trading(self):
        client = self._get_client()
        response = client.get("/api/workflow/run/trading")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "steps_completed" in data

    def test_workflow_run_security(self):
        client = self._get_client()
        response = client.get("/api/workflow/run/security")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_workflow_run_content(self):
        client = self._get_client()
        response = client.get("/api/workflow/run/content")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_workflow_run_code(self):
        client = self._get_client()
        response = client.get("/api/workflow/run/code")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_workflow_run_forecast(self):
        client = self._get_client()
        response = client.get("/api/workflow/run/forecast")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_workflow_run_all(self):
        client = self._get_client()
        response = client.get("/api/workflow/all")
        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert data["count"] >= 5
        for wf in data["workflows"]:
            assert wf["status"] == "completed"
            assert wf["steps_completed"] == wf["total_steps"]


class TestDashboardSelfImprovementEndpoints:
    """Test dashboard self-improvement API endpoints."""

    def _get_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import universe_dashboard
        app = FastAPI()
        app.include_router(universe_dashboard.app.router)
        return TestClient(app)

    def test_self_improvement_report(self):
        client = self._get_client()
        response = client.get("/api/self-improvement/report")
        assert response.status_code == 200

    def test_self_improvement_cycle(self):
        client = self._get_client()
        response = client.get("/api/self-improvement/cycle/FRIDAY")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_knowledge_all(self):
        client = self._get_client()
        response = client.get("/api/knowledge/all")
        assert response.status_code == 200

    def test_knowledge_retrieve(self):
        client = self._get_client()
        response = client.get("/api/knowledge/retrieve/Cortex")
        assert response.status_code == 200

    def test_decisions_all(self):
        client = self._get_client()
        response = client.get("/api/decisions/all")
        assert response.status_code == 200

    def test_decisions_agent(self):
        client = self._get_client()
        response = client.get("/api/decisions/agent/Forge")
        assert response.status_code == 200