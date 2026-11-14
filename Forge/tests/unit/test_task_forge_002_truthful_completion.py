"""TASK-FORGE-002 (GAP 5) regressions: failed verification must never report COMPLETED.

Before the fix, nodes only "failed" when execute_step RAISED -- a tester node that
returned status="failed" was recorded as a completed node, and run_task left a
COMPLETED task untouched even when the verification battery failed after every
repair route. The owner heard "completed" about a build whose tests failed.
All agents/providers here are labelled test doubles; no real endpoint is hit.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.models import TaskState
from app.memory.sqlite_test_backend import SQLiteTestDatabase
from app.memory.state_store import StateStore


class StubRegistry:
    """Labelled test double for the agent registry.

    Every role's execute_step succeeds without doing anything; the tester node
    can be scripted with a failed result to exercise the verification-gate
    handling without raising.
    """

    def __init__(self, tester_result: dict | None = None):
        self.tester_result = tester_result

    def create_agent(self, role_name):
        if role_name == "tester" and self.tester_result is not None:
            return SimpleNamespace(
                execute_step=AsyncMock(return_value=dict(self.tester_result))
            )
        return SimpleNamespace(
            execute_step=AsyncMock(return_value={"status": "success"})
        )


async def _make_orchestrator(temp_dir):
    # Explicit test-only SQLite backend: DatabaseManager is Oracle-only.
    db = SQLiteTestDatabase(temp_dir / "truthful.db")
    await db.init_db()
    store = StateStore(db)
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)
    return orchestrator, store


@pytest.mark.asyncio
async def test_failed_verification_gate_node_fails_the_task(temp_dir, monkeypatch):
    """A tester node returning status='failed' (without raising) must fail the
    task instead of being recorded as a completed node."""
    orchestrator, store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )

    orchestrator.registry = StubRegistry(
        tester_result={
            "status": "failed",
            "exit_code": 1,
            "stdout": "1 failed",
            "stderr": "FAILED test_main.py::test_add",
        }
    )
    monkeypatch.setattr(
        OrchestratorCore, "_verify_and_repair", AsyncMock(return_value=None)
    )

    final = await orchestrator.run_task(task.id, max_iterations=30)

    assert final.state == TaskState.FAILED
    event_types = [e.event_type for e in await store.get_audit_trail(task.id)]
    assert "node.failed" in event_types
    assert "task.completed" not in event_types


@pytest.mark.asyncio
async def test_failing_final_verification_demotes_completed_task(temp_dir, monkeypatch):
    """A build that finished every DAG node but fails the verification battery
    after the repair routes must NOT stay COMPLETED."""
    orchestrator, store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )
    orchestrator.registry = StubRegistry()

    verify = AsyncMock(
        return_value=SimpleNamespace(
            all_passed=False,
            passed_checks=0,
            total_checks=4,
            failed_checks=4,
            evidence=[],
            failure_reasons=["[TEST] pytest: exit=1"],
        )
    )
    monkeypatch.setattr(
        "app.verification.engine.VerificationEngine",
        lambda **kw: SimpleNamespace(verify_task=verify),
    )
    monkeypatch.setattr(
        "app.recovery.engine.RecoveryEngine",
        lambda **kw: SimpleNamespace(
            attempt_recovery=AsyncMock(return_value=(False, "no repair", None))
        ),
    )
    monkeypatch.setattr(
        "app.agents.coordinator.AgentCoordinator",
        lambda **kw: SimpleNamespace(
            review_and_repair=AsyncMock(
                return_value=SimpleNamespace(summary="clean", repairs=[], clean=True)
            )
        ),
    )

    final = await orchestrator.run_task(task.id, max_iterations=30)

    assert final.state == TaskState.FAILED
    assert verify.await_count == 1
    event_types = [e.event_type for e in await store.get_audit_trail(task.id)]
    assert "task.completed" in event_types  # it was reported complete first...
    assert "task.failed" in event_types  # ...and then demoted honestly.


@pytest.mark.asyncio
async def test_passing_verification_keeps_task_completed(temp_dir, monkeypatch):
    """The demotion must be one-directional: a passing battery keeps COMPLETED."""
    orchestrator, _store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )
    orchestrator.registry = StubRegistry()

    verify = AsyncMock(
        return_value=SimpleNamespace(
            all_passed=True,
            passed_checks=4,
            total_checks=4,
            failed_checks=0,
            evidence=[],
            failure_reasons=[],
        )
    )
    monkeypatch.setattr(
        "app.verification.engine.VerificationEngine",
        lambda **kw: SimpleNamespace(verify_task=verify),
    )

    final = await orchestrator.run_task(task.id, max_iterations=30)

    assert final.state == TaskState.COMPLETED
    assert verify.await_count == 1


@pytest.mark.asyncio
async def test_verification_infrastructure_crash_does_not_demote(temp_dir, monkeypatch):
    """A battery that crashes instead of reporting leaves the task state
    untouched -- only a report that RAN and failed demotes COMPLETED."""
    orchestrator, _store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )
    orchestrator.registry = StubRegistry()

    verify = AsyncMock(side_effect=RuntimeError("verification battery crashed"))
    monkeypatch.setattr(
        "app.verification.engine.VerificationEngine",
        lambda **kw: SimpleNamespace(verify_task=verify),
    )

    final = await orchestrator.run_task(task.id, max_iterations=30)

    assert final.state == TaskState.COMPLETED
