"""
tests/test_workflow_engine.py — Tests for the workflow engine and capability discovery.

Tests multi-agent workflows, capability discovery, and task templates.

Priority 1-5: Workflow orchestration and capability discovery
"""
import importlib.util
import sys
import os
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

sys.path.insert(0, str(ROOT / "tools"))


def _load(name, relpath):
    path = str(ROOT / relpath)
    full_name = f"_wftest_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCapabilityDiscovery:
    """Test agent capability discovery."""

    def test_registry_loads(self):
        """Test that the capability registry loads."""
        from universe_workflow_engine import CapabilityRegistry
        reg = CapabilityRegistry()
        agents = reg.all_agents()
        assert len(agents) >= 9

    def test_discover_trading(self):
        """Test discovering trading capabilities."""
        from universe_workflow_engine import CapabilityRegistry
        reg = CapabilityRegistry()
        # Register a test agent with trading capability
        reg.register("TestAgent", ["trading", "analysis"], "http://localhost:8000")
        agents = reg.discover("trading")
        assert "TestAgent" in agents

    def test_discover_all(self):
        """Test discovering all capabilities."""
        from universe_workflow_engine import CapabilityRegistry
        reg = CapabilityRegistry()
        reg.register("Agent1", ["trading", "security"])
        reg.register("Agent2", ["security", "memory"])
        reg.register("Agent3", ["trading", "memory"])
        all_caps = reg.discover_all()
        assert "trading" in all_caps
        assert "security" in all_caps
        assert "memory" in all_caps

    def test_get_agent_info(self):
        """Test getting agent info."""
        from universe_workflow_engine import CapabilityRegistry
        reg = CapabilityRegistry()
        reg.register("TestAgent", ["test"], "http://localhost:8000", "http://localhost:8000/health")
        info = reg.get_agent("TestAgent")
        assert info is not None
        assert info.agent_name == "TestAgent"
        assert "test" in info.capabilities

    def test_health_check(self):
        """Test capability registry health check."""
        from universe_workflow_engine import CapabilityRegistry
        reg = CapabilityRegistry()
        reg.register("TestAgent", ["test"], "http://localhost:8000")
        health = reg.health_check()
        assert "TestAgent" in health


class TestWorkflowEngine:
    """Test the workflow engine."""

    def test_create_workflow(self):
        """Test creating a workflow."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Test Workflow", "A test workflow")
        assert wf.workflow_id
        assert wf.name == "Test Workflow"

    def test_add_step(self):
        """Test adding steps to a workflow."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Test")
        step = engine.add_step(wf.workflow_id, "Test Step", "Inference", "reason", {"query": "test"})
        assert step.step_id
        assert step.agent == "Inference"

    def test_execute_workflow(self):
        """Test executing a workflow."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Test Execution")
        engine.add_step(wf.workflow_id, "Step 1", "Inference", "reason", {})
        engine.add_step(wf.workflow_id, "Step 2", "Cortex", "decide", {})
        result = engine.execute_workflow(wf.workflow_id)
        assert result.status in ("completed", "failed")
        assert len(result.steps) == 2

    def test_run_trading_analysis_workflow(self):
        """Test the trading analysis workflow template."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.run_trading_analysis()
        assert wf.status == "completed"
        assert len(wf.steps) == 3
        for step in wf.steps:
            assert step.status == "completed"

    def test_run_security_scan_workflow(self):
        """Test the security scan workflow template."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.run_security_scan()
        assert wf.status == "completed"
        assert len(wf.steps) == 3

    def test_run_content_creation_workflow(self):
        """Test the content creation workflow template."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.run_content_creation()
        assert wf.status == "completed"
        assert len(wf.steps) == 3

    def test_run_code_development_workflow(self):
        """Test the code development workflow template."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.run_code_development()
        assert wf.status == "completed"
        assert len(wf.steps) == 3

    def test_run_forecast_pipeline_workflow(self):
        """Test the forecast pipeline workflow template."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.run_forecast_pipeline()
        assert wf.status == "completed"
        assert len(wf.steps) == 3

    def test_all_workflows_completed(self):
        """Test that all 5 workflow templates complete successfully."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        workflows = [
            engine.run_trading_analysis(),
            engine.run_security_scan(),
            engine.run_content_creation(),
            engine.run_code_development(),
            engine.run_forecast_pipeline(),
        ]
        for wf in workflows:
            assert wf.status == "completed"
            assert all(s.status == "completed" for s in wf.steps)

    def test_get_workflow(self):
        """Test getting a workflow by ID."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Test Get")
        retrieved = engine.get_workflow(wf.workflow_id)
        assert retrieved is not None
        assert retrieved.workflow_id == wf.workflow_id

    def test_get_all_workflows(self):
        """Test getting all workflows."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        for i in range(3):
            engine.create_workflow(f"WF {i}")
        all_wf = engine.get_all_workflows()
        assert len(all_wf) >= 3


class TestWorkflowDependencies:
    """Test workflow step dependencies."""

    def test_step_dependencies(self):
        """Test that steps can depend on other steps."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Dep Workflow")
        step1 = engine.add_step(wf.workflow_id, "Step 1", "Inference", "reason", {})
        step2 = engine.add_step(wf.workflow_id, "Step 2", "Cortex", "decide", {},
                                depends_on=[step1.step_id])
        assert step2.depends_on == [step1.step_id]
        result = engine.execute_workflow(wf.workflow_id)
        assert result.status == "completed"

    def test_complex_dependency_chain(self):
        """Test a complex dependency chain."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Chain Workflow")
        s1 = engine.add_step(wf.workflow_id, "Analyze", "Inference", "analyze", {})
        s2 = engine.add_step(wf.workflow_id, "Decide", "Cortex", "decide", {}, [s1.step_id])
        s3 = engine.add_step(wf.workflow_id, "Execute", "Stratex", "trade", {}, [s2.step_id])
        s4 = engine.add_step(wf.workflow_id, "Store", "Memora", "recall", {}, [s3.step_id])
        result = engine.execute_workflow(wf.workflow_id)
        assert result.status == "completed"
        assert len(result.steps) == 4

    def test_workflow_with_failure(self):
        """Test that workflow handles step failures."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Failure Test")
        engine.add_step(wf.workflow_id, "Valid Step", "Inference", "reason", {})
        # Try to dispatch to unknown agent
        engine.add_step(wf.workflow_id, "Invalid Step", "UnknownAgent", "test", {})
        result = engine.execute_workflow(wf.workflow_id)
        # Workflow should complete (dispatch bus handles unknown agents)
        assert result.status in ("completed", "failed")


class TestWorkflowMetrics:
    """Test workflow execution metrics."""

    def test_step_timing(self):
        """Test that step timing is recorded."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Timing Test")
        engine.add_step(wf.workflow_id, "Step", "Inference", "reason", {})
        result = engine.execute_workflow(wf.workflow_id)
        step = result.steps[0]
        assert step.started_at > 0
        assert step.completed_at > 0
        assert step.completed_at >= step.started_at

    def test_workflow_completion_time(self):
        """Test that workflow completion time is recorded."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Completion Test")
        engine.add_step(wf.workflow_id, "Step 1", "Inference", "reason", {})
        engine.add_step(wf.workflow_id, "Step 2", "Cortex", "decide", {})
        result = engine.execute_workflow(wf.workflow_id)
        assert result.completed_at > 0
        assert result.created_at < result.completed_at

    def test_workflow_results(self):
        """Test that step results are recorded."""
        from universe_workflow_engine import UniverseWorkflowEngine
        engine = UniverseWorkflowEngine()
        wf = engine.create_workflow("Results Test")
        engine.add_step(wf.workflow_id, "Step", "Inference", "reason", {"query": "test"})
        result = engine.execute_workflow(wf.workflow_id)
        step = result.steps[0]
        assert step.result is not None
        assert "Inference" in step.result
