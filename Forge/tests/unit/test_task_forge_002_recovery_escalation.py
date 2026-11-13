"""TASK-FORGE-002 (GAP 4) regressions: the recovery escalation must carry the objective.

Before the fix, _escalate_repair_to_agent built the Debugger context WITHOUT
goal/requirements, so repair_with_inference rejected every escalation with
'missing_objective' and the Inference-backed repair could never fire from
verification-failure recovery. Route 1's LLM branch was also structurally dead:
nothing ever called set_provider, so _synthesize_patch_for_diagnosis skipped its
provider branch on every production run. All provider/agent calls here are
labelled test doubles; no real endpoint is hit.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.models import TaskEntity
from app.memory.sqlite_test_backend import SQLiteTestDatabase
from app.memory.state_store import StateStore
from app.recovery.classifier import FailureClassifier
from app.recovery.engine import RecoveryEngine
from app.verification.evidence import CheckCategory, VerificationEvidence


async def _make_recovery(tmp_path: Path, goal: str, requirements: list[str]):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    wm.write_project_file("fixture", "calc.py", "def add(a, b):\n    return a - b\n")
    engine = ExecutionEngine(wm=wm)

    # Explicit test-only SQLite backend: DatabaseManager is Oracle-only.
    db = SQLiteTestDatabase(tmp_path / "recovery.db")
    await db.init_db()
    store = StateStore(db)
    await store.create_task(
        TaskEntity(
            id="fixture",
            goal=goal,
            requirements=requirements,
            workspace_path=str(wm.get_task_workspace_dir("fixture")),
        )
    )
    recovery = RecoveryEngine(exec_engine=engine, store=store)
    return recovery, engine


def _logic_bug_diagnosis():
    evidence = VerificationEvidence(
        check_name="pytest",
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="FAILED tests/test_calc.py::test_add - AssertionError: assert 0 == 2",
    )
    return FailureClassifier().classify(evidence), evidence


@pytest.mark.asyncio
async def test_agent_escalation_context_carries_goal_and_requirements(tmp_path, monkeypatch):
    """Route 3 must hand the Debugger the task's goal and requirements, not a
    context that repair_with_inference rejects as missing_objective."""
    from app.agents import roles

    recovery, _engine = await _make_recovery(
        tmp_path, "CSV converter with unittest", ["quoted commas"]
    )
    diagnosis, evidence = _logic_bug_diagnosis()

    captured = {}

    class FakeDebugger:
        def __init__(self, provider=None):
            self.provider = provider

        async def execute_step(self, task_id, node_title, context, engine):
            captured.update(context)
            return {"fixed_files": []}

    monkeypatch.setattr(roles, "DebuggerRole", FakeDebugger)

    patch = await recovery._escalate_repair_to_agent("fixture", diagnosis, evidence)

    assert patch is None  # the stub fixed nothing; escalation reports honestly
    assert captured["goal"] == "CSV converter with unittest"
    assert captured["requirements"] == ["quoted commas"]
    assert "logic_bug" in captured["error"]
    assert captured["target_file"] == "calc.py"


@pytest.mark.asyncio
async def test_synthesis_route_calls_inference_repair_with_goal_when_no_provider(
    tmp_path, monkeypatch
):
    """Route 1 with provider=None must reach the Inference-backed repair with the
    persisted objective; an accepted repair comes back as a sound patch."""
    from app.agents import repair as repair_module

    recovery, engine = await _make_recovery(
        tmp_path, "calculator adds numbers", ["positive sums"]
    )
    assert recovery.provider is None  # production state: set_provider has no caller
    diagnosis, _evidence = _logic_bug_diagnosis()

    seen = {}

    async def fake_repair(task_id, context, eng, role="debugger"):
        seen.update(context)
        eng.fs.create_file(
            task_id=task_id,
            relative_path=context["target_file"],
            content="def add(a, b):\n    return a + b\n",
            role=role,
        )
        return {"status": "success", "fixed_files": [context["target_file"]], "rejections": []}

    monkeypatch.setattr(repair_module, "repair_with_inference", fake_repair)

    patch = await recovery._synthesize_patch_for_diagnosis("fixture", diagnosis)

    assert patch is not None
    assert patch.target_file == seen["target_file"]
    assert patch.replacement_snippet == "def add(a, b):\n    return a + b\n"
    assert patch.original_snippet == "def add(a, b):\n    return a - b\n"
    assert seen["goal"] == "calculator adds numbers"
    assert seen["requirements"] == ["positive sums"]
    assert "logic_bug" in seen["error"]
    assert seen["project_files"] == [seen["target_file"]]
