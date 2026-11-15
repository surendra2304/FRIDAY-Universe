"""TASK-COR-006 — Cortex failure-recovery patterns.

Drives the real ``Orchestrator.run_cognitive_loop`` (no mocks of the loop)
with a scripted lead agent proposing a 3-step plan on a real ToolBus, and
fails the middle sub-task in each distinct way. The invariant under test is
the fleet's worst historical failure mode: a plan must NEVER report overall
success when a step silently failed — and a healthy plan must not be marked
failed either.

Also covers the governed-operations envelope: a FAILED execution record must
not be "measured" into a fabricated achieved lift.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.abspath("packages/core/src"))
sys.path.insert(0, os.path.abspath("packages/event_schema/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))
sys.path.insert(0, os.path.abspath("packages/ai_universe_adapter/src"))
sys.path.insert(0, os.path.abspath("packages/tool_runtime/src"))
sys.path.insert(0, os.path.abspath("packages/integrations/src"))
sys.path.insert(0, os.path.abspath("packages/policy_engine/src"))
sys.path.insert(0, os.path.abspath("packages/workflow_engine/src"))

from cortex_agents import AgentInput, AgentOutput, AgentRegistry, ProposedAction, SpecialistAgent
from cortex_core import Orchestrator
from cortex_event_schema import Actor, ActorType, EventSchema
from cortex_tool_runtime import SideEffectLevel, Tool, ToolBus

ACTIONS = ["step_alpha", "step_beta", "step_gamma"]


class _PlanAgent(SpecialistAgent):
    def __init__(self, actions: list[str]):
        super().__init__(agent_id="agent_growth", domain="growth", capabilities=list(actions))
        self._actions = actions

    async def process(self, input_data: AgentInput) -> AgentOutput:
        return AgentOutput(
            agent_id=self.agent_id,
            decision="EXECUTE_PLAN",
            reasoning_summary="staging plan",
            confidence=0.9,
            proposed_actions=[
                ProposedAction(action_type=a, target="staging", params={"step": a}, rationale="test step")
                for a in self._actions
            ],
            expected_outcomes={"conversion_lift_pct": 5.0},
        )


def _event() -> EventSchema:
    return EventSchema(
        event_id="evt_cor006_test",
        tenant_id="tenant_alpha",
        site_id="site_beta",
        type="pricing_view",
        occurred_at=datetime.now(UTC),
        actor=Actor(type=ActorType.VISITOR, id="vis_123"),
        source="web-sdk",
        data={"plan": "enterprise"},
    )


def _ok(params, ctx):
    return {"ok": True, "detail": "completed"}


def _raises(params, ctx):
    raise RuntimeError("step exploded")


def _error_status(params, ctx):
    return {"status": "error", "error": "downstream provider returned 503"}


def _empty(params, ctx):
    return {}


def _none(params, ctx):
    return None


async def _hangs(params, ctx):
    await asyncio.sleep(60)
    return {"ok": True}


def _orchestrator(executors: dict, *, timeout: float = 30.0, level: SideEffectLevel = SideEffectLevel.READ):
    bus = ToolBus()
    for name, fn in executors.items():
        bus.register_tool(Tool(name=name, side_effect_level=level), fn)
    registry = AgentRegistry()
    registry.register(_PlanAgent(ACTIONS))
    return Orchestrator(agent_registry=registry, tool_bus=bus, step_timeout_seconds=timeout)


def _plan(beta, *, alpha=_ok, gamma=_ok):
    return {"step_alpha": alpha, "step_beta": beta, "step_gamma": gamma}


@pytest.mark.asyncio
async def test_healthy_plan_reports_success_and_verified():
    result = await _orchestrator(_plan(_ok)).run_cognitive_loop(_event())
    assert result["status"] == "success"
    assert result["executed_actions"] == 3
    assert result["failed_actions"] == 0
    verify = next(t for t in result["trace"] if t["phase"] == "7.Verify")
    assert verify["status"] == "verified"


@pytest.mark.asyncio
async def test_exception_mid_plan_is_partial_not_loop_fatal():
    orchestrator = _orchestrator(_plan(_raises))
    result = await orchestrator.run_cognitive_loop(_event())
    assert result["status"] == "partial"
    assert result["executed_actions"] == 2
    assert result["failed_actions"] == 1
    beta = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert beta["status"] == "error"
    # The completed steps are reported and the audit trail exists.
    assert len(orchestrator.audit_records) == 1
    assert orchestrator.audit_records[0].changes["verification"] == "failed"


@pytest.mark.asyncio
async def test_timeout_mid_plan_is_bounded_and_partial():
    orchestrator = _orchestrator(_plan(_hangs), timeout=0.5)
    result = await asyncio.wait_for(orchestrator.run_cognitive_loop(_event()), timeout=10)
    assert result["status"] == "partial"
    beta = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert beta["status"] == "timeout"


@pytest.mark.asyncio
async def test_error_status_return_is_not_silent_success():
    result = await _orchestrator(_plan(_error_status)).run_cognitive_loop(_event())
    assert result["status"] == "partial"
    beta = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert beta["status"] == "error_result"


@pytest.mark.asyncio
@pytest.mark.parametrize("beta", [_empty, _none], ids=["empty_dict", "none"])
async def test_empty_result_is_not_silent_success(beta):
    result = await _orchestrator(_plan(beta)).run_cognitive_loop(_event())
    assert result["status"] == "partial"
    outcome = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert outcome["status"] == "empty_result"


@pytest.mark.asyncio
async def test_all_steps_failing_reports_failed():
    result = await _orchestrator(_plan(_raises, alpha=_raises, gamma=_raises)).run_cognitive_loop(_event())
    assert result["status"] == "failed"
    assert result["executed_actions"] == 0
    assert result["failed_actions"] == 3


@pytest.mark.asyncio
async def test_flaky_read_step_is_retried_once_and_recovers():
    calls = {"n": 0}

    def flaky(params, ctx):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient blip")
        return {"ok": True}

    result = await _orchestrator(_plan(flaky)).run_cognitive_loop(_event())
    assert result["status"] == "success"
    beta = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert beta["attempts"] == 2


@pytest.mark.asyncio
async def test_side_effecting_step_is_never_blindly_retried():
    calls = {"n": 0}

    def counting_raise(params, ctx):
        calls["n"] += 1
        raise RuntimeError("maybe applied, maybe not")

    # SENSITIVE = side-effecting but below the bus's fail-closed idempotency
    # tiers (HIGH_IMPACT/DANGEROUS never reach the executor without Redis).
    orchestrator = _orchestrator(_plan(counting_raise), level=SideEffectLevel.SENSITIVE)
    # Drive the step executor directly (policy gating is phase 5's concern).
    from cortex_core.resilience import global_health_registry
    from cortex_tool_runtime import Execution

    execution = Execution(
        request_id="exec_cor006",
        tool_name="step_beta",
        actor={"type": "agent", "id": "agent_growth"},
        reason="test",
        params={},
        idempotency_key="idemp_cor006_beta",
    )
    tool = orchestrator.tool_bus.get_tool("step_beta")
    outcome, _res = await orchestrator._execute_step(execution, tool, global_health_registry.circuit("tools"))
    assert outcome["status"] == "error"
    assert outcome["attempts"] == 1
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_bus_blocked_envelope_is_a_step_failure():
    class BlockedBus(ToolBus):
        async def execute(self, tool_name, params, execution=None):  # noqa: ANN001
            if tool_name == "step_beta":
                return {"status": "blocked", "reason": "idempotency_guard_unavailable", "tool": tool_name}
            return await super().execute(tool_name, params, execution)

    bus = BlockedBus()
    for name, fn in _plan(_ok).items():
        bus.register_tool(Tool(name=name, side_effect_level=SideEffectLevel.READ), fn)
    registry = AgentRegistry()
    registry.register(_PlanAgent(ACTIONS))
    result = await Orchestrator(agent_registry=registry, tool_bus=bus).run_cognitive_loop(_event())
    assert result["status"] == "partial"
    beta = next(o for o in result["step_outcomes"] if o["tool"] == "step_beta")
    assert beta["status"] == "blocked"


@pytest.mark.asyncio
async def test_failed_governed_execution_is_not_measured_into_a_lift():
    import cortex_api.friday_router as fr
    from cortex_core.governed_operations import ExecutionRecord, GovernedOperationsEngine, global_governed_engine

    def failed_execute(self, approval_id, idempotency_key, tool_bus, dry_run=False):  # noqa: ANN001
        appr = self.approvals[approval_id]
        rec = ExecutionRecord(
            execution_id="exec_cor006_failed",
            approval_id=approval_id,
            property_id=appr.property_id,
            action=appr.action_type,
            params=appr.params,
            idempotency_key=idempotency_key,
            status="FAILED",
            dry_run=dry_run,
            classification="REAL_EXECUTION",
            snapshot_before=None,
            result={"status": "failed", "error": "provider 503 on apply"},
            executed_at=datetime.now(UTC),
        )
        self.executions[rec.execution_id] = rec
        return rec

    original = GovernedOperationsEngine.execute
    GovernedOperationsEngine.execute = failed_execute
    try:
        envelope = fr.FridayTaskEnvelope(
            task_id="cor006_gov_task",
            action="execute_operation",
            payload={
                "property_id": "site_storefront",
                "operation": "banner_injection",
                "approved": True,
                "approver_id": "supervisor_token",
                "params": {"variant": "promo"},
            },
        )
        resp = await fr.process_task_envelope(envelope)
    finally:
        GovernedOperationsEngine.execute = original
        global_governed_engine.executions.pop("exec_cor006_failed", None)

    assert resp.result["execution"]["status"] == "FAILED"
    assert resp.result["measurement"] is None
    assert "FAILED to execute" in resp.summary
    assert "Achieved lift" not in resp.summary
