"""
TASK-FRG-005 regression tests: repair-loop convergence hardening.

Each test pins a failure measured by the FRG-005 planted-defect stress
battery (12 seeded projects driven through the production repair sequence):

* a file whose body is written at its header's indentation level raised
  IndentationError and NO repair route could fix it -- the deterministic
  repertoire had no candidate and every model route refuses unparseable
  sources;
* "cannot import name 'x' from 'y'" classified with failing_file=None, so
  the patch routes aimed at an arbitrary first project file;
* the orchestrator's recovery loop worked from the first battery's frozen
  evidence list: it spent attempts on checks that already passed, and a
  defect exposed only by an earlier fix never got an attempt.

Fail-on-main / pass-with-fix is asserted per test where the behaviour
changed; the signature-gate test is a characterization test (passes on
both) pinning the measured c10 dead end as a deliberate policy.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.models import TaskEntity
from app.memory.sqlite_test_backend import SQLiteTestDatabase
from app.memory.state_store import StateStore
from app.recovery.classifier import FailureClass, FailureClassifier
from app.recovery.syntax_repair import _repair_python_source
from app.verification.evidence import (
    CheckCategory,
    VerificationEvidence,
    VerificationReport,
)


# ----------------------------------------------------------------------
# deterministic syntax repair: the IndentationError dead end
# ----------------------------------------------------------------------

def test_expected_indented_block_is_repaired():
    source = (
        "def letter_grade(score):\n"
        "    if score >= 90:\n"
        "    return \"A\"\n"
        "    return \"B\"\n"
    )
    fixed = _repair_python_source(source)
    assert fixed is not None
    namespace: dict = {}
    exec(compile(fixed, "main.py", "exec"), namespace)
    assert namespace["letter_grade"](95) == "A"
    assert namespace["letter_grade"](40) == "B"


def test_valid_source_is_not_rewritten_by_indentation_candidate():
    source = (
        "def f(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    return 2\n"
    )
    assert _repair_python_source(source) is None


def test_inconsistent_indentation_stays_unrepaired():
    # The continuation line's level matches no plausible block structure;
    # a guessed candidate would be a coin flip, so none may be produced.
    source = (
        "def f(x):\n"
        "    if x:\n"
        "    a = 1\n"
        "        b = 2\n"
        "    return a\n"
    )
    assert _repair_python_source(source) is None


# ----------------------------------------------------------------------
# classifier: import-error targeting
# ----------------------------------------------------------------------

def _evidence(stderr: str) -> VerificationEvidence:
    return VerificationEvidence(
        check_name="Pytest Test Suite Runner",
        category=CheckCategory.TEST,
        exit_code=1,
        passed=False,
        stderr=stderr,
    )


def test_cannot_import_name_targets_the_importing_file():
    stderr = (
        "test_main.py:1: in <module>\n"
        "    from main import checkout\n"
        "main.py:1: in <module>\n"
        "    from helpers import compute_total\n"
        "E   ImportError: cannot import name 'compute_total' from 'helpers' "
        "(/workspaces/task_x/project/helpers.py)\n"
    )
    diagnosis = FailureClassifier().classify(_evidence(stderr))
    assert diagnosis.failure_class == FailureClass.DEPENDENCY_MISSING
    assert diagnosis.failing_file == "main.py"
    assert diagnosis.importing_file == "main.py"


def test_missing_module_keeps_create_target_and_names_importer():
    stderr = (
        "main.py:1: in <module>\n"
        "    from string_utils import slugify\n"
        "E   ModuleNotFoundError: No module named 'string_utils'\n"
    )
    diagnosis = FailureClassifier().classify(_evidence(stderr))
    assert diagnosis.failure_class == FailureClass.DEPENDENCY_MISSING
    # The create route's contract (TASK-REL-028) is untouched...
    assert diagnosis.failing_file == "string_utils.py"
    # ...and the patch routes gain the fallback fix site.
    assert diagnosis.importing_file == "main.py"


# ----------------------------------------------------------------------
# characterization: the signature-preservation gate (battery case c10)
# ----------------------------------------------------------------------

def test_signature_change_is_rejected_by_repair_validation():
    from app.agents.repair import validate_replacement

    original = "def greet(name):\n    return f\"Hello, {name}!\"\n"
    candidate = (
        "def greet(first, last):\n"
        "    return f\"Hello, {first} {last}!\"\n"
    )
    # A build whose tests call greet(first=..., last=...) can therefore
    # never be repaired by the model routes: the only correct fix is the
    # one change validation forbids. Pinned deliberately -- relaxing this
    # gate is a separate, reviewed policy decision, not a drive-by.
    assert validate_replacement(original, candidate) == "signature_changed:greet"


# ----------------------------------------------------------------------
# orchestrator: evidence refresh in _verify_and_repair
# ----------------------------------------------------------------------

def _report(task_id: str, failures: list[VerificationEvidence]) -> VerificationReport:
    total = 11
    return VerificationReport(
        task_id=task_id,
        all_passed=not failures,
        total_checks=total,
        passed_checks=total - len(failures),
        failed_checks=len(failures),
        evidence=failures,
    )


def _failure(check: str, category: CheckCategory, stderr: str) -> VerificationEvidence:
    return VerificationEvidence(
        check_name=check,
        category=category,
        exit_code=1,
        passed=False,
        stderr=stderr,
    )


async def _make_orchestrator(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    wm.create_workspace("fixture")
    engine = ExecutionEngine(wm=wm)
    db = SQLiteTestDatabase(tmp_path / "orch.db")
    await db.init_db()
    store = StateStore(db)
    await store.create_task(
        TaskEntity(
            id="fixture",
            goal="fixture goal",
            requirements=[],
            workspace_path=str(wm.get_task_workspace_dir("fixture")),
        )
    )
    from app.core.orchestrator import OrchestratorCore

    return OrchestratorCore(store=store, wm=wm, engine=engine)


def _install_fakes(monkeypatch, reports, attempt_behaviour):
    """Replace the verification/recovery engines the orchestrator builds.

    reports: list of VerificationReport returned in order by verify_task.
    attempt_behaviour: fn(evidence) -> (recovered, message, patch).
    Returns the list of evidence objects attempt_recovery was called with.
    """
    import app.agents.coordinator as coordinator_module
    import app.recovery.engine as recovery_module
    import app.verification.engine as verification_module
    from app.agents.coordinator import ReviewOutcome

    attempts: list[VerificationEvidence] = []
    queue = list(reports)

    class FakeVerificationEngine:
        def __init__(self, engine=None, wm=None):
            pass

        async def verify_task(self, task_id, baseline_report=None):
            return queue.pop(0) if len(queue) > 1 else queue[0]

    class FakeRecoveryEngine:
        def __init__(self, exec_engine=None, verifier=None, store=None):
            pass

        async def attempt_recovery(self, task_id, evidence):
            attempts.append(evidence)
            return attempt_behaviour(evidence)

    class FakeCoordinator:
        def __init__(self, engine, max_rounds=2, goal="", requirements=None):
            pass

        async def review_and_repair(self, task_id):
            return ReviewOutcome(rounds=0, clean=True)

    monkeypatch.setattr(verification_module, "VerificationEngine", FakeVerificationEngine)
    monkeypatch.setattr(recovery_module, "RecoveryEngine", FakeRecoveryEngine)
    monkeypatch.setattr(coordinator_module, "AgentCoordinator", FakeCoordinator)
    return attempts


@pytest.mark.asyncio
async def test_recovery_loop_stops_after_first_full_recovery(tmp_path, monkeypatch):
    """Battery c1 shape: four checks fail from one root defect; the first
    repair turns the battery green. The frozen-evidence loop still spent
    three more attempts on the stale failures; the refreshed loop spends
    exactly one."""
    from app.recovery.repair import RepairPatch

    task_id = "fixture"
    syntax = "SyntaxError: expected ':'"
    r0 = _report(task_id, [
        _failure("Build & Syntax Check", CheckCategory.BUILD, syntax),
        _failure("Ruff / Static Code Linter", CheckCategory.BUILD, syntax),
        _failure("Pytest Test Suite Runner", CheckCategory.TEST, syntax),
        _failure("Runtime CLI / Service Smoke Check", CheckCategory.BUILD, syntax),
    ])
    green = _report(task_id, [])

    def behaviour(evidence):
        patch = RepairPatch(
            target_file="main.py",
            replacement_snippet="def add(a, b):\n    return a + b\n",
            explanation="fix",
            patch_type="rewrite",
        )
        return True, "recovered", patch

    attempts = _install_fakes(monkeypatch, [r0, green], behaviour)
    orch = await _make_orchestrator(tmp_path)
    final = await orch._verify_and_repair(task_id)
    assert final is not None and final.all_passed
    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_recovery_loop_attempts_defect_exposed_by_earlier_fix(tmp_path, monkeypatch):
    """Battery c9 shape: a syntax error masks a logic bug (the tests cannot
    run). Fixing the syntax must earn the newly-visible logic failure its
    own recovery attempt in the same _verify_and_repair call, and the
    partial fix must count as progress rather than 'no recovery'."""
    from app.recovery.repair import RepairPatch

    task_id = "fixture"
    r0 = _report(task_id, [
        _failure("Build & Syntax Check", CheckCategory.BUILD,
                 "File \"calc.py\", line 1\nSyntaxError: expected ':'"),
        _failure("Pytest Test Suite Runner", CheckCategory.TEST,
                 "SyntaxError: expected ':'"),
    ])
    r1 = _report(task_id, [
        _failure("Pytest Test Suite Runner", CheckCategory.TEST,
                 "FAILED test_main.py::test_discount - AssertionError: assert 199.1 == 180.0"),
    ])
    green = _report(task_id, [])

    def behaviour(evidence):
        patch = RepairPatch(
            target_file="calc.py",
            replacement_snippet="def total(prices):\n    return sum(prices)\n",
            explanation="fix",
            patch_type="rewrite",
        )
        if "AssertionError" in (evidence.stderr or ""):
            return True, "recovered", patch
        if "SyntaxError" in (evidence.stderr or ""):
            return False, "applied but re-verification failed", patch
        return False, "no patch", None

    attempts = _install_fakes(monkeypatch, [r0, r1, green], behaviour)
    orch = await _make_orchestrator(tmp_path)
    final = await orch._verify_and_repair(task_id)
    assert final is not None and final.all_passed
    attempted_stderrs = [a.stderr for a in attempts]
    assert any("SyntaxError" in s for s in attempted_stderrs)
    assert any("AssertionError" in s for s in attempted_stderrs), (
        "the logic failure exposed by the syntax fix never got a recovery attempt"
    )
