"""
TASK-FRG-007 (build-time optimisation) regression tests.

Two behaviours are pinned here:

1. VerificationEngine._run_checkers: the battery's read-only checkers run
   CONCURRENTLY, while checkers that execute/import the generated project
   (TestChecker, RuntimeChecker) run SERIALLY after them, in their original
   relative order. Evidence order and per-checker exception isolation are
   byte-for-byte the semantics of the old serial loop.

2. OrchestratorCore._verify_and_repair: when the post-repair
   re-verification is fully green, peer review is skipped (early exit) --
   the same "battery green means verification complete" rule the first-pass
   early return already applied. When the re-verification still fails,
   peer review runs exactly as before.
"""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.engine import VerificationEngine
from app.verification.evidence import (
    CheckCategory,
    VerificationEvidence,
    VerificationReport,
)


# --------------------------------------------------------------------------
# Fake checkers. The CLASS NAMES matter: _run_checkers classifies executors
# by class name, so the executing fakes are named exactly like the real
# TestChecker / RuntimeChecker.
# --------------------------------------------------------------------------


class _Recorder:
    def __init__(self):
        self.starts: dict[str, float] = {}
        self.ends: dict[str, float] = {}
        self.active_exec = 0
        self.max_active_exec = 0


class _FakeBase:
    name = "fake"
    category = CheckCategory.BUILD

    def __init__(self, rec: _Recorder, delay: float = 0.0, blow: bool = False):
        self.rec = rec
        self.delay = delay
        self.blow = blow

    async def _body(self):
        self.rec.starts[self.name] = time.perf_counter()
        try:
            if self.blow:
                raise RuntimeError(f"boom-{self.name}")
            await asyncio.sleep(self.delay)
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=self.delay * 1000.0,
            )
        finally:
            self.rec.ends[self.name] = time.perf_counter()

    async def run_check(self, task_id: str, engine) -> VerificationEvidence:
        return await self._body()


class StaticAlpha(_FakeBase):
    name = "Static Alpha"


class StaticBeta(_FakeBase):
    name = "Static Beta"


class StaticGamma(_FakeBase):
    name = "Static Gamma"


class TestChecker(_FakeBase):
    """Executing fake (name is the classification key)."""

    __test__ = False
    name = "Test Suite Runner"
    category = CheckCategory.TEST

    async def run_check(self, task_id: str, engine) -> VerificationEvidence:
        self.rec.active_exec += 1
        self.rec.max_active_exec = max(self.rec.max_active_exec, self.rec.active_exec)
        try:
            return await self._body()
        finally:
            self.rec.active_exec -= 1


class RuntimeChecker(_FakeBase):
    """Executing fake (name is the classification key)."""

    __test__ = False
    name = "Runtime Smoke"
    category = CheckCategory.RUNTIME

    async def run_check(self, task_id: str, engine) -> VerificationEvidence:
        self.rec.active_exec += 1
        self.rec.max_active_exec = max(self.rec.max_active_exec, self.rec.active_exec)
        try:
            return await self._body()
        finally:
            self.rec.active_exec -= 1


def _engine_with(checkers, temp_dir: Path) -> VerificationEngine:
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return VerificationEngine(engine=engine, wm=wm, custom_checkers=checkers)


@pytest.mark.asyncio
async def test_run_checkers_preserves_order_and_isolates_exceptions(temp_dir: Path):
    rec = _Recorder()
    checkers = [
        StaticAlpha(rec, delay=0.05),
        TestChecker(rec, delay=0.01),
        StaticBeta(rec, blow=True),
        RuntimeChecker(rec, delay=0.01),
        StaticGamma(rec, delay=0.01),
    ]
    verifier = _engine_with(checkers, temp_dir)

    evidence = await verifier._run_checkers("any-task")

    assert [e.check_name for e in evidence] == [
        "Static Alpha",
        "Test Suite Runner",
        "Static Beta",
        "Runtime Smoke",
        "Static Gamma",
    ]
    blown = evidence[2]
    assert blown.passed is False
    assert blown.exit_code == 1
    assert "boom-Static Beta" in blown.stderr
    assert all(e.passed for i, e in enumerate(evidence) if i != 2)


@pytest.mark.asyncio
async def test_statics_run_concurrently_executors_serial_and_last(temp_dir: Path):
    rec = _Recorder()
    checkers = [
        StaticAlpha(rec, delay=0.4),
        StaticBeta(rec, delay=0.4),
        StaticGamma(rec, delay=0.4),
        TestChecker(rec, delay=0.3),
        RuntimeChecker(rec, delay=0.3),
    ]
    verifier = _engine_with(checkers, temp_dir)

    t0 = time.perf_counter()
    evidence = await verifier._run_checkers("any-task")
    wall = time.perf_counter() - t0

    assert len(evidence) == 5 and all(e.passed for e in evidence)
    # Fully serial would cost 0.4*3 + 0.3*2 = 1.8s. Concurrency must beat
    # the two serial executors plus ONE static wave (~1.0s) by a margin.
    assert wall < 1.35, f"battery wall {wall:.2f}s -- statics did not overlap"
    # Executors never overlapped each other...
    assert rec.max_active_exec == 1
    # ...and no executor started before every static checker had finished.
    last_static_end = max(
        rec.ends[n] for n in ("Static Alpha", "Static Beta", "Static Gamma")
    )
    first_exec_start = min(rec.starts[n] for n in ("Test Suite Runner", "Runtime Smoke"))
    assert first_exec_start >= last_static_end - 0.05


@pytest.mark.asyncio
async def test_real_battery_still_passes_clean_workspace(temp_dir: Path):
    """The default battery on a known-good workspace must stay green and
    keep its 11-evidence shape (10 checkers + source integrity)."""
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)

    task_id = str(uuid4())
    wm.create_workspace(task_id)
    wm.write_project_file(
        task_id, "main.py", "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    wm.write_project_file(
        task_id, "test_main.py", "from main import add\ndef test_add():\n    assert add(2, 3) == 5\n"
    )

    report = await verifier.verify_task(task_id)
    assert report.all_passed is True
    assert report.total_checks == 11
    assert report.passed_checks == 11


# --------------------------------------------------------------------------
# Orchestrator early exit
# --------------------------------------------------------------------------


def _report(task_id: str, passed: int, total: int) -> VerificationReport:
    evidence = [
        VerificationEvidence(
            check_name=f"check-{i}",
            category=CheckCategory.BUILD,
            exit_code=0 if i < passed else 1,
            passed=i < passed,
            stderr="" if i < passed else "nope",
        )
        for i in range(total)
    ]
    return VerificationReport(
        task_id=task_id,
        all_passed=passed == total,
        total_checks=total,
        passed_checks=passed,
        failed_checks=total - passed,
        evidence=evidence,
    )


class _FakeStore:
    def __init__(self, task):
        self._task = task

    async def get_task(self, task_id):
        return self._task


class _FakeTask:
    id = "task-frg007"
    goal = "test goal"
    requirements: list[str] = []


@pytest.fixture
def patched_pipeline(monkeypatch):
    """Stub verify/recovery/coordinator so _verify_and_repair's control
    flow can be observed without a live battery or LLM."""
    state = {"reports": [], "coordinator_calls": 0}

    async def fake_verify(self, task_id, baseline_report=None):
        return state["reports"].pop(0)

    async def fake_recovery(self, task_id, evidence):
        return True, "repaired", None

    async def fake_review(self, task_id):
        state["coordinator_calls"] += 1

        class _Review:
            summary = "stub review"
            repairs = 0
            clean = False

        return _Review()

    monkeypatch.setattr(
        "app.verification.engine.VerificationEngine.verify_task", fake_verify
    )
    monkeypatch.setattr(
        "app.recovery.engine.RecoveryEngine.attempt_recovery", fake_recovery
    )
    monkeypatch.setattr(
        "app.agents.coordinator.AgentCoordinator.review_and_repair", fake_review
    )
    return state


def _orchestrator() -> OrchestratorCore:
    return OrchestratorCore(
        store=_FakeStore(_FakeTask()),
        wm=object(),
        analyzer=object(),
        planner=object(),
        registry=object(),
        engine=object(),
        ctx_manager=object(),
    )


@pytest.mark.asyncio
async def test_verify_and_repair_early_exits_when_repair_turns_battery_green(
    patched_pipeline,
):
    orch = _orchestrator()
    patched_pipeline["reports"] = [
        _report("task-frg007", passed=1, total=2),  # first battery: failing
        _report("task-frg007", passed=2, total=2),  # post-repair: green
    ]

    final = await orch._verify_and_repair("task-frg007")

    assert final is not None and final.all_passed is True
    assert patched_pipeline["coordinator_calls"] == 0, (
        "peer review must be skipped once the objective battery is green"
    )


@pytest.mark.asyncio
async def test_verify_and_repair_still_uses_peer_review_when_battery_red(
    patched_pipeline,
):
    orch = _orchestrator()
    patched_pipeline["reports"] = [
        _report("task-frg007", passed=1, total=2),  # first battery: failing
        _report("task-frg007", passed=1, total=2),  # post-repair: still red
    ]

    final = await orch._verify_and_repair("task-frg007")

    assert final is not None and final.all_passed is False
    assert patched_pipeline["coordinator_calls"] == 1, (
        "peer review must still run when the battery stays red after repair"
    )
