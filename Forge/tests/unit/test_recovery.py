"""
Unit tests for Debugger & Recovery Subsystem: Classifier, AntiLoopController, PatchApplicator, and RecoveryEngine.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.state_store import StateStore
from app.recovery.classifier import FailureClass, FailureClassifier
from app.recovery.engine import RecoveryEngine
from app.recovery.loop_guard import AntiLoopController
from app.verification.engine import VerificationEngine
from app.verification.evidence import CheckCategory, VerificationEvidence


def test_failure_classifier_categories():
    classifier = FailureClassifier()

    # Syntax Error
    ev_syntax = VerificationEvidence(
        check_name="syntax",
        category=CheckCategory.BUILD,
        exit_code=1,
        passed=False,
        stderr='File "src/math.py", line 12\n    def calc(\n             ^\nSyntaxError: invalid syntax',
    )
    diag_syntax = classifier.classify(ev_syntax)
    assert diag_syntax.failure_class == FailureClass.SYNTAX_ERROR
    assert diag_syntax.failing_file == "src/math.py"
    assert diag_syntax.failing_line == 12

    # Missing Module / Dependency
    ev_dep = VerificationEvidence(
        check_name="import_check",
        category=CheckCategory.BUILD,
        exit_code=1,
        passed=False,
        stderr="ModuleNotFoundError: No module named 'fastapi'",
    )
    diag_dep = classifier.classify(ev_dep)
    assert diag_dep.failure_class == FailureClass.DEPENDENCY_MISSING

    # Logic Bug / Test failure
    ev_test = VerificationEvidence(
        check_name="pytest",
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr="FAILED tests/test_calc.py::test_add - AssertionError: assert 4 == 5",
    )
    diag_test = classifier.classify(ev_test)
    assert diag_test.failure_class == FailureClass.LOGIC_BUG


def test_anti_loop_controller_retry_limits_and_hash_deduplication():
    controller = AntiLoopController(max_retries_per_class=2, max_total_retries=4)
    task_id = "task_loop_test"

    patch_a = "def add(a, b): return a + b"
    patch_b = "def add(a, b): return a + b + 0"

    # Attempt 1 (Permitted)
    allowed, _ = controller.can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_a)
    assert allowed is True
    controller.record_repair_attempt(task_id, FailureClass.SYNTAX_ERROR, patch_a)

    # Duplicate patch attempt (Blocked by hash deduplication)
    allowed_dup, reason_dup = controller.can_attempt_repair(
        task_id, FailureClass.SYNTAX_ERROR, patch_a
    )
    assert allowed_dup is False
    assert "Duplicate patch detected" in reason_dup

    # Attempt 2 with different patch (Permitted)
    allowed_b, _ = controller.can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_b)
    assert allowed_b is True
    controller.record_repair_attempt(task_id, FailureClass.SYNTAX_ERROR, patch_b)

    # Attempt 3 for same class (Blocked by max_retries_per_class=2)
    patch_c = "def add(a, b): return int(a) + int(b)"
    allowed_c, reason_c = controller.can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_c)
    assert allowed_c is False
    assert "Class recovery limit reached" in reason_c


@pytest.mark.asyncio
async def test_patch_applicator_and_recovery_flow(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    db_mgr = DatabaseManager(db_path=temp_dir / "test_recovery.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    verifier = VerificationEngine(engine=engine, wm=wm)
    recovery = RecoveryEngine(
        verifier=verifier,
        store=store,
        exec_engine=engine,
    )

    task_id = "task_recovery_flow"
    from app.memory.models import TaskEntity

    await store.create_task(
        TaskEntity(
            id=task_id,
            goal="Recovery flow test",
            workspace_path=str(wm.get_task_workspace_dir(task_id)),
        )
    )

    # Create file with broken syntax
    wm.write_project_file(task_id, "broken.py", "def foo(\n    return 42\n")

    # Run verification to produce failed evidence
    report = await verifier.verify_task(task_id)
    assert not report.all_passed

    # Attempt automated recovery
    failed_ev = next(e for e in report.evidence if not e.passed)
    recovered, _msg, patch = await recovery.attempt_recovery(task_id, failed_ev)

    assert recovered is True
    assert patch is not None
    assert patch.target_file == "broken.py"
