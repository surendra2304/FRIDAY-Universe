from __future__ import annotations

import importlib
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

def test_browser_step_kind_execution():
    from friday_core.agent_runtime import FridayAgentRuntime, ExecutionStep

    runtime = FridayAgentRuntime()
    # Execute a task using step kind 'browser' without providing URL content
    step = ExecutionStep(tool="browser", arguments={"goal": "lookup pricing"}, kind="browser")
    result = runtime.execute("search pricing", [step])
    assert result.ok is True
    assert len(result.observations) >= 1
    assert "browsed:" in result.observations[0]


def test_approvals_http_route_and_trace():
    from friday_core.agent_runtime import FridayAgentRuntime, PermissionRule, router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Check trace has pending_approvals list
    resp = client.get("/v1/agent/trace")
    assert resp.status_code == 200
    data = resp.json()
    assert "pending_approvals" in data
    assert isinstance(data["pending_approvals"], list)


def test_trading_workflow_harness_verification_and_memory():
    from friday_core.universe_orchestrator import FullUniverseOrchestrator
    import tempfile

    orch = FullUniverseOrchestrator(state_dir=tempfile.mkdtemp())
    prices = [100.0, 101.5, 102.0, 101.8, 103.5, 104.0, 105.0]
    trades = [{"price": 104.0, "quantity": 10, "side": "buy"}]

    result = orch.run_deep_trading("BTCUSDT", prices, trades)
    actions = [s.action for s in result.steps]
    assert "harness_verification" in actions
    verification_step = next(s for s in result.steps if s.action == "harness_verification")
    assert verification_step.result["passed"] is True
    assert "checks" in verification_step.result
    assert "weight" in verification_step.result
    assert hasattr(result, "recalled_context") or "recalled_context" in result
    assert isinstance(result["recalled_context"], list)


def test_intel_workflow_harness_verification_and_memory():
    from friday_core.universe_orchestrator import FullUniverseOrchestrator
    import tempfile

    orch = FullUniverseOrchestrator(state_dir=tempfile.mkdtemp())
    indicators = [{"type": "ip", "value": "192.168.1.100", "description": "Suspicious login attempt"}]

    result = orch.run_deep_intel(indicators)
    actions = [s.action for s in result.steps]
    assert "harness_verification" in actions
    verification_step = next(s for s in result.steps if s.action == "harness_verification")
    assert verification_step.result["passed"] is True
    assert "checks" in verification_step.result
    assert "weight" in verification_step.result
    assert hasattr(result, "recalled_context") or "recalled_context" in result
    assert isinstance(result["recalled_context"], list)


def test_universe_task_router_resolves_friday_via_registry():
    from friday_core.universe_task_router import UniverseTaskRouter

    router = UniverseTaskRouter()
    # Task requiring browser_automation and agent_harness
    task = router.submit_task(
        "Automate browser task",
        required_capabilities=["browser_automation", "agent_harness"],
    )
    decision = router.route_task(task.task_id)
    assert decision.assigned_agent == "FRIDAY"
