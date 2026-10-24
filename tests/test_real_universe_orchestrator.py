"""
tests/test_real_universe_orchestrator.py — Functional tests for universe orchestrator.

Tests the unified orchestrator across all 3 layers:
- DeepWorkflowEngine: full cross-agent workflows
- FullUniverseOrchestrator: orchestration and dashboard
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


orch = load_module("FRIDAY/apps/core/src/friday_core/universe_orchestrator.py", "orchestrator")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestDeepSecurityWorkflow:
    def test_full_security_workflow(self):
        engine = orch.DeepWorkflowEngine()
        code = "password = 'secret'\neval('1+1')\nsubprocess.run(cmd, shell=True)"
        logs = ["User login from 192.168.1.1", "Failed login: admin"]

        result = engine.run_full_security_workflow(code, logs)
        assert result.status == "completed"
        assert result.complexity == "deep"
        assert len(result.steps) >= 5
        assert result.final_output in ("Block Immediately", "Review")

    def test_security_workflow_finds_vulns(self):
        engine = orch.DeepWorkflowEngine()
        code = "password = 'secret'\neval('1+1')"
        result = engine.run_full_security_workflow(code, [])

        # Verify deep steps were executed
        assert any(s.action == "code_security_scan" for s in result.steps)
        assert any(s.action == "vulnerability_management" for s in result.steps)
        assert any(s.action == "compliance_audit" for s in result.steps)


class TestDeepTradingWorkflow:
    def test_full_trading_workflow(self):
        engine = orch.DeepWorkflowEngine()
        prices = [100 + i * 0.5 for i in range(30)]
        trades = [{"side": "buy", "quantity": 100}] * 10

        result = engine.run_full_trading_workflow("TEST", prices, trades)
        assert result.status == "completed"
        assert result.complexity == "deep"
        assert len(result.steps) >= 5

    def test_trading_workflow_deep_steps(self):
        engine = orch.DeepWorkflowEngine()
        prices = [100 + i * 0.5 for i in range(30)]
        trades = [{"side": "buy", "quantity": 100}]

        result = engine.run_full_trading_workflow("TEST", prices, trades)

        # Verify all deep steps executed
        actions = [s.action for s in result.steps]
        assert "sentiment_analysis" in actions
        assert "order_flow_analysis" in actions
        assert "pattern_recognition" in actions
        assert "forecast" in actions
        assert "stress_test" in actions


class TestDeepIntelWorkflow:
    def test_full_intel_workflow(self):
        engine = orch.DeepWorkflowEngine()
        indicators = [
            {"value": "1.2.3.4", "type": "ip", "confidence": 0.8,
             "tags": ["malware"], "first_seen": time.time()},
            {"value": "bad.com", "type": "domain", "confidence": 0.7,
             "tags": ["phishing"], "first_seen": time.time()},
        ]

        result = engine.run_full_intel_workflow(indicators)
        assert result.status == "completed"
        assert result.complexity == "deep"
        assert len(result.steps) >= 4
        assert result.final_output in ("Valid Intel", "Low Quality Intel")

    def test_intel_workflow_quality_check(self):
        engine = orch.DeepWorkflowEngine()
        indicators = [
            {"value": "1.2.3.4", "type": "ip", "confidence": 0.8,
             "tags": ["malware"], "first_seen": time.time()},
        ]
        result = engine.run_full_intel_workflow(indicators)
        actions = [s.action for s in result.steps]
        assert "intel_quality_check" in actions
        assert "threat_forecast" in actions
        assert "supply_chain_analysis" in actions


class TestDeepContentWorkflow:
    def test_full_content_workflow(self):
        engine = orch.DeepWorkflowEngine()
        viewers = [
            {"age": 25, "gender": "male", "location": "US",
             "interests": ["gaming"], "watch_time": 300, "spending": 50},
        ]
        result = engine.run_full_content_workflow("Test Topic", "Great educational content", viewers)
        assert result.status == "completed"
        assert result.complexity == "deep"
        assert len(result.steps) >= 4
        assert result.final_output in ("Publish", "Do Not Publish")

    def test_content_workflow_moderation(self):
        engine = orch.DeepWorkflowEngine()
        viewers = [{"age": 30, "gender": "female", "location": "UK",
                    "interests": ["music"], "watch_time": 200, "spending": 30}]
        result = engine.run_full_content_workflow("Test", "This is shit and that guy is an asshole", viewers)
        assert result.final_output == "Do Not Publish"


class TestFullUniverseOrchestrator:
    @pytest.fixture
    def engine(self, temp_state):
        return orch.FullUniverseOrchestrator(state_dir=os.path.join(temp_state, "orch"))

    def test_deep_security(self, engine):
        result = engine.run_deep_security("password='x'\neval('1+1')", ["login failed"])
        assert result.status == "completed"
        assert result.complexity == "deep"

    def test_deep_trading(self, engine):
        prices = [100 + i for i in range(30)]
        result = engine.run_deep_trading("TEST", prices, [{"side": "buy", "quantity": 100}])
        assert result.status == "completed"

    def test_deep_intel(self, engine):
        indicators = [{"value": "1.2.3.4", "type": "ip", "confidence": 0.8,
                       "tags": ["malware"], "first_seen": time.time()}]
        result = engine.run_deep_intel(indicators)
        assert result.status == "completed"

    def test_deep_content(self, engine):
        viewers = [{"age": 25, "gender": "male", "location": "US",
                    "interests": ["gaming"], "watch_time": 300, "spending": 50}]
        result = engine.run_deep_content("Test", "Great content", viewers)
        assert result.status == "completed"

    def test_dashboard(self, engine):
        dashboard = engine.get_universe_dashboard()
        assert dashboard["version"] == "3.0.0"
        assert "layers" in dashboard
        assert "agents" in dashboard
        assert len(dashboard["agents"]) == 9
        assert dashboard["total_api_endpoints"] >= 50

    def test_stats_persistence(self, engine):
        engine.run_deep_security("eval('1+1')", [])
        assert engine._stats["total_workflows"] == 1
        assert engine._stats["total_steps"] >= 5
        assert engine._stats["successful_workflows"] == 1
