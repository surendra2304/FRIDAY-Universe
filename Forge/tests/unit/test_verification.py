"""
Unit tests for Verification Engine & Objective Checkers.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import (
    BuildChecker,
    TestChecker,
)
from app.verification.engine import VerificationEngine


@pytest.fixture
def verification_context(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return {"wm": wm, "engine": engine, "task_id": "test_verify_01"}


@pytest.mark.asyncio
async def test_build_checker_valid_and_invalid_syntax(verification_context):
    wm: WorkspaceManager = verification_context["wm"]
    engine: ExecutionEngine = verification_context["engine"]
    task_id = "test_syntax_task"

    # Valid Python file
    wm.write_project_file(task_id, "calculator.py", "def add(a, b):\n    return a + b\n")
    checker = BuildChecker()
    evidence_valid = await checker.run_check(task_id, engine)
    assert evidence_valid.passed is True
    assert evidence_valid.exit_code == 0

    # Invalid Python file (SyntaxError)
    wm.write_project_file(task_id, "bad_syntax.py", "def broken_func(\n    return 42\n")
    evidence_invalid = await checker.run_check(task_id, engine)
    assert evidence_invalid.passed is False
    assert evidence_invalid.exit_code == 1
    assert len(evidence_invalid.issues) >= 1


@pytest.mark.asyncio
async def test_test_checker_passes_and_fails(verification_context):
    wm: WorkspaceManager = verification_context["wm"]
    engine: ExecutionEngine = verification_context["engine"]
    task_id = "test_test_task"

    # Passing test file
    wm.write_project_file(task_id, "test_math.py", "def test_sum():\n    assert 1 + 1 == 2\n")
    test_checker = TestChecker()
    ev_pass = await test_checker.run_check(task_id, engine)
    assert ev_pass.passed is True
    assert ev_pass.exit_code == 0

    # Failing test file
    wm.write_project_file(task_id, "test_failing.py", "def test_fail():\n    assert 1 == 2\n")
    ev_fail = await test_checker.run_check(task_id, engine)
    assert ev_fail.passed is False
    assert ev_fail.exit_code != 0


@pytest.mark.asyncio
async def test_verification_engine_battery(verification_context):
    wm: WorkspaceManager = verification_context["wm"]
    engine: ExecutionEngine = verification_context["engine"]
    task_id = "test_engine_battery"

    wm.write_project_file(task_id, "main.py", "def run():\n    return 'OK'\n")
    wm.write_project_file(
        task_id, "test_main.py", "from main import run\ndef test_run():\n    assert run() == 'OK'\n"
    )

    verifier = VerificationEngine(engine=engine, wm=wm)
    report = await verifier.verify_task(task_id)

    assert report.total_checks >= 3
    assert report.all_passed is True
    assert (wm.get_task_workspace_dir(task_id) / "artifacts" / "verification_report.json").exists()
