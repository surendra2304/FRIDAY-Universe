"""TASK-FRG-011: verdict-surface consistency for Forge builds.

Production evidence (TASK-FRG-003's acceptance battery, 2026-11-15):
Forge's verdict surfaces disagreed about the same build, three times.

* Pre-fix R3: in-graph gate FAILED, final manifest all_passed=True,
  delegate FAILED.
* Post-fix R1: task-status endpoint SUCCESS while the delegate manifest
  read PARTIAL_FAILURE.
* Post-fix R5: the in-graph tester gate's exit_code=2 verdict latched
  the task FAILED while the final verification battery passed 11/11
  all_passed and the delivered project reproduced 13/13 green -- a
  green deliverable branded FAILED.

Root causes pinned here: the in-graph gate is a point-in-time verdict
over a mid-build workspace while the final battery judges the settled
workspace after repair; run_task demoted COMPLETED -> FAILED on a
failing battery (TASK-FORGE-002) but had no counterpart for a passing
one, and the lifecycle matrix forbids FAILED -> COMPLETED outright;
the delegate then re-ran its own battery and mirrored state/manifest
by hand-rolled rules, and the status endpoint derived a third verdict
from whatever manifest happened to be on disk.

The fix (app/verification/verdict.py + OrchestratorCore.apply_final_verdict):
ONE derivation settles the task at finalization and stamps the verdict
on the task record and the manifest; every surface reads that verdict.
These tests pin the derivation's precedence table and reproduce the R5
divergence shape end to end: on main, the R5 test's task stays FAILED
with an all-passed battery; the delegate execute_now and status tests
report FAILED over a green manifest.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import delegate, tasks as tasks_api
from app.core.orchestrator import OrchestratorCore
from app.memory.models import TaskGraph, TaskMode, TaskNode, TaskState
from app.verification.evidence import (
    CheckCategory,
    VerificationEvidence,
    VerificationManifest,
    VerificationReport,
)
from app.verification.source_integrity import project_snapshot
from app.verification.verdict import BuildVerdict, derive_build_verdict

GATE_ERROR = "Verification gate 'Run Tests' returned status=failed (exit_code=2)"


# ---------------------------------------------------------------------------
# The derivation: the precedence table every surface now shares.
# ---------------------------------------------------------------------------


def test_derive_precedence_table():
    d = derive_build_verdict

    # A failing final battery caps every surface -- never SUCCESS.
    assert d(task_state="COMPLETED", battery_all_passed=False,
             battery_partial_failure=True).verdict is BuildVerdict.PARTIAL_FAILURE
    assert d(task_state="COMPLETED", battery_all_passed=False,
             battery_partial_failure=False).verdict is BuildVerdict.FAILED
    assert d(task_state="FAILED", battery_all_passed=False,
             battery_partial_failure=True).verdict is BuildVerdict.PARTIAL_FAILURE

    # Green battery + completed build -> SUCCESS.
    assert d(task_state="COMPLETED", battery_all_passed=True).verdict is BuildVerdict.SUCCESS

    # R5's shape: green final battery, only in-graph gate failures ->
    # SUCCESS, with the gate verdict named as superseded, never hidden.
    decision = d(task_state="FAILED", battery_all_passed=True,
                 gate_failure_reasons=[GATE_ERROR])
    assert decision.verdict is BuildVerdict.SUCCESS
    assert decision.superseded == (GATE_ERROR,)

    # A named hard failure can never be laundered by a green battery.
    decision = d(task_state="FAILED", battery_all_passed=True,
                 hard_failure_reasons=["Node 'Implement': boom"],
                 gate_failure_reasons=[GATE_ERROR])
    assert decision.verdict is BuildVerdict.FAILED
    assert decision.reasons == ("Node 'Implement': boom",)

    # TASK-REL-019's invariant: a FAILED task whose failure is NOT
    # positively identified as a gate verdict stays FAILED on a green
    # battery -- leftover artifacts verifying does not resurrect it.
    decision = d(task_state="FAILED", battery_all_passed=True,
                 recorded_error="node blew up")
    assert decision.verdict is BuildVerdict.FAILED
    assert decision.reasons == ("node blew up",)

    # No battery evidence: a completion claim is DEGRADED, never SUCCESS.
    assert d(task_state="COMPLETED").verdict is BuildVerdict.DEGRADED
    decision = d(task_state="FAILED", gate_failure_reasons=[GATE_ERROR])
    assert decision.verdict is BuildVerdict.FAILED
    assert decision.reasons == (GATE_ERROR,)

    # A passing battery not bound to the current files is DEGRADED.
    assert d(task_state="COMPLETED", battery_all_passed=True,
             snapshot_bound=False).verdict is BuildVerdict.DEGRADED

    # Stamps: authoritative for read surfaces, except a SUCCESS stamp
    # whose evidence is gone or unbound decays to DEGRADED.
    assert d(task_state="FAILED", stamped_verdict="FAILED",
             battery_all_passed=True).verdict is BuildVerdict.FAILED
    assert d(task_state="COMPLETED", stamped_verdict="SUCCESS",
             snapshot_bound=False).verdict is BuildVerdict.DEGRADED
    assert d(task_state="COMPLETED", stamped_verdict="SUCCESS",
             evidence_available=False).verdict is BuildVerdict.DEGRADED

    # States that are their own verdict / not yet final.
    assert d(task_state="CANCELLED").verdict is BuildVerdict.CANCELLED
    assert d(task_state="BLOCKED").verdict is BuildVerdict.BLOCKED
    assert d(task_state="RUNNING") is None

    # Battery-only surface (the delegate verify action).
    assert d(task_state=None, battery_all_passed=True).verdict is BuildVerdict.SUCCESS
    assert d(task_state=None, battery_all_passed=False,
             battery_partial_failure=True).verdict is BuildVerdict.PARTIAL_FAILURE


# ---------------------------------------------------------------------------
# Orchestrator finalization fixtures (REL-019-style fake store).
# ---------------------------------------------------------------------------


class _Store:
    def __init__(self, task, graph=None):
        self._task = task
        self._graph = graph
        self.events: list[tuple[str, dict]] = []

    async def get_task(self, task_id):
        return self._task

    async def update_task_state(self, task_id, state, progress_percentage=None,
                                error_message=None):
        self._task.state = state
        if progress_percentage is not None:
            self._task.progress_percentage = progress_percentage
        if error_message is not None:
            self._task.error_message = error_message
        return self._task

    async def record_event(self, task_id, event_type, payload=None):
        self.events.append((event_type, payload or {}))
        return SimpleNamespace(task_id=task_id, event_type=event_type)

    async def get_latest_task_graph_for_project(self, project_id):
        return self._graph

    async def save_task(self, task):
        self._task = task
        return task


class _WM:
    def __init__(self, base: Path):
        self.base = base
        for name in ("artifacts", "state", "project"):
            (base / name).mkdir(parents=True, exist_ok=True)

    def get_workspace_paths(self, task_id):
        return SimpleNamespace(
            root=self.base,
            project=self.base / "project",
            artifacts=self.base / "artifacts",
            state=self.base / "state",
            logs=self.base,
            cache=self.base,
        )

    def save_artifact(self, task_id, name, content):
        (self.base / "artifacts" / name).write_text(content, encoding="utf-8")


def _orchestrator(store, wm):
    return OrchestratorCore(
        store=store,
        wm=wm,
        analyzer=SimpleNamespace(),
        planner=SimpleNamespace(),
        registry=SimpleNamespace(),
        engine=SimpleNamespace(),
        ctx_manager=SimpleNamespace(),
    )


def _task(task_id, state, error_message=None):
    return SimpleNamespace(
        id=task_id,
        goal="CSV expense CLI: ledger.py, report.py, main.py",
        requirements=[],
        mode=TaskMode.AUTONOMOUS,
        state=state,
        error_message=error_message,
        metadata={},
        progress_percentage=100,
        created_at=datetime.now(UTC),
    )


def _report(task_id, *, passed, total, failed_names=()):
    evidence = []
    for i in range(total):
        if i < passed:
            evidence.append(VerificationEvidence(
                check_name=f"Check {i}", category=CheckCategory.BUILD,
                exit_code=0, passed=True))
        else:
            name = failed_names[i - passed] if i - passed < len(failed_names) else f"Check {i}"
            evidence.append(VerificationEvidence(
                check_name=name, category=CheckCategory.TEST,
                exit_code=1, passed=False, stderr="boom"))
    return VerificationReport(
        task_id=task_id,
        all_passed=(passed == total),
        total_checks=total,
        passed_checks=passed,
        failed_checks=total - passed,
        evidence=evidence,
    )


def _r5_graph(task_id):
    """FRG-003 R5's shape: every work node completed; the tester gate
    node failed mid-build with exit_code=2."""
    dev = TaskNode(
        id="n_dev", title="Implement ledger CLI", status=TaskState.COMPLETED,
        metadata={"node_type": "implementation"}, result={"status": "success"},
    )
    gate = TaskNode(
        id="n_gate", title="Run Tests", status=TaskState.FAILED,
        metadata={"node_type": "verification_gate"},
        error=GATE_ERROR, result={"status": "failed", "exit_code": 2},
    )
    return TaskGraph(
        id=f"graph_{task_id}", project_id=task_id, goal="CSV expense CLI",
        nodes={"n_dev": dev, "n_gate": gate},
    )


def _green_manifest(task_id, project: Path, *, stamped=None):
    stages = {
        f"Stage {i}": {"stage": "test", "command": "pytest", "exit_code": 0,
                        "passed": True, "duration_ms": 1.0,
                        "stdout_snippet": "", "stderr_snippet": "",
                        "artifacts": [], "timestamp": "2026-11-15T00:00:00Z"}
        for i in range(11)
    }
    data = {
        "task_id": task_id,
        "source_snapshot": project_snapshot(project),
        "overall_status": "PASSED",
        "all_passed": True,
        "partial_failure": False,
        "failure_summary": None,
        "total_stages": 11,
        "passed_stages": 11,
        "failed_stages": 0,
        "stages": stages,
        "evidence": [],
    }
    if stamped:
        data["build_verdict"] = stamped
    return data


# ---------------------------------------------------------------------------
# R5 reproduced: gate FAILED the task, final battery is green.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r5_gate_failure_superseded_by_green_final_battery(tmp_path):
    task = _task("task_r5", TaskState.FAILED, error_message=GATE_ERROR)
    store = _Store(task, _r5_graph("task_r5"))
    wm = _WM(tmp_path)
    (tmp_path / "project" / "ledger.py").write_text("x = 1\n", encoding="utf-8")
    wm.save_artifact(
        "task_r5", "verification_manifest.json",
        json.dumps(_green_manifest("task_r5", tmp_path / "project")),
    )
    orch = _orchestrator(store, wm)
    orch.step_task = AsyncMock(return_value=(task, []))
    orch._verify_and_repair = AsyncMock(
        return_value=_report("task_r5", passed=11, total=11)
    )

    final = await orch.run_task("task_r5")

    # On main this task stays FAILED while its battery is 11/11 green.
    assert final.state == TaskState.COMPLETED
    assert final.metadata["build_verdict"] == "SUCCESS"
    assert any("Run Tests" in s for s in final.metadata["verdict_superseded"])
    manifest = json.loads(
        (tmp_path / "artifacts" / "verification_manifest.json").read_text()
    )
    assert manifest["build_verdict"] == "SUCCESS"
    assert any("Run Tests" in s for s in manifest["superseded_checks"])
    event_types = [ev for ev, _ in store.events]
    assert "task.verdict_reconciled" in event_types
    assert "task.verdict_settled" in event_types


@pytest.mark.asyncio
async def test_failing_final_battery_still_demotes_completed(tmp_path):
    """TASK-FORGE-002 GAP 5, preserved: a red battery demotes COMPLETED,
    and the stamp keeps the PARTIAL distinction the state cannot."""
    graph = TaskGraph(
        id="graph_t", project_id="task_dem",
        goal="CSV expense CLI",
        nodes={
            "n_dev": TaskNode(id="n_dev", title="Implement",
                              status=TaskState.COMPLETED,
                              metadata={"node_type": "implementation"}),
            "n_gate": TaskNode(id="n_gate", title="Run Tests",
                               status=TaskState.COMPLETED,
                               metadata={"node_type": "verification_gate"}),
        },
    )
    task = _task("task_dem", TaskState.COMPLETED)
    store = _Store(task, graph)
    orch = _orchestrator(store, _WM(tmp_path))
    orch.step_task = AsyncMock(return_value=(task, []))
    orch._verify_and_repair = AsyncMock(return_value=_report(
        "task_dem", passed=9, total=11,
        failed_names=["Test Suite Runner", "Security Scan"],
    ))

    final = await orch.run_task("task_dem")

    assert final.state == TaskState.FAILED
    assert final.metadata["build_verdict"] == "PARTIAL_FAILURE"
    assert any("Test Suite Runner" in r for r in final.metadata["verdict_reasons"])
    failed_events = [p for ev, p in store.events if ev == "task.failed"]
    assert failed_events and failed_events[0]["verification_gate"] is True


@pytest.mark.asyncio
async def test_green_battery_never_overrides_failed_build_node(tmp_path):
    """A build that itself broke stays FAILED on a green battery, with
    the broken node named -- the battery cannot launder it."""
    graph = TaskGraph(
        id="graph_t", project_id="task_hard", goal="CSV expense CLI",
        nodes={
            "n_dev": TaskNode(id="n_dev", title="Implement ledger CLI",
                              status=TaskState.FAILED,
                              metadata={"node_type": "implementation"},
                              error="SyntaxError: invalid syntax in ledger.py"),
            "n_gate": TaskNode(id="n_gate", title="Run Tests",
                               status=TaskState.COMPLETED,
                               metadata={"node_type": "verification_gate"}),
        },
    )
    task = _task("task_hard", TaskState.FAILED,
                 error_message="SyntaxError: invalid syntax in ledger.py")
    store = _Store(task, graph)
    orch = _orchestrator(store, _WM(tmp_path))
    orch.step_task = AsyncMock(return_value=(task, []))
    orch._verify_and_repair = AsyncMock(
        return_value=_report("task_hard", passed=11, total=11)
    )

    final = await orch.run_task("task_hard")

    assert final.state == TaskState.FAILED
    assert final.metadata["build_verdict"] == "FAILED"
    assert any("Implement ledger CLI" in r for r in final.metadata["verdict_reasons"])


@pytest.mark.asyncio
async def test_fallback_stub_stays_failed_on_green_battery(tmp_path):
    graph = TaskGraph(
        id="graph_t", project_id="task_stub", goal="CSV expense CLI",
        nodes={
            "n_dev": TaskNode(id="n_dev", title="Implement",
                              status=TaskState.COMPLETED,
                              metadata={"node_type": "implementation"},
                              result={"status": "success", "fallback_stub": True}),
        },
    )
    task = _task("task_stub", TaskState.FAILED,
                 error_message="TASK FAILED: Fell back to stub generation.")
    store = _Store(task, graph)
    orch = _orchestrator(store, _WM(tmp_path))
    orch.step_task = AsyncMock(return_value=(task, []))
    orch._verify_and_repair = AsyncMock(
        return_value=_report("task_stub", passed=11, total=11)
    )

    final = await orch.run_task("task_stub")

    assert final.state == TaskState.FAILED
    assert final.metadata["build_verdict"] == "FAILED"
    assert any("stub" in r.lower() for r in final.metadata["verdict_reasons"])


# ---------------------------------------------------------------------------
# Delegate surfaces read the same verdict.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_endpoint_agrees_with_settled_r5_verdict(tmp_path, monkeypatch):
    task = _task("task_r5s", TaskState.FAILED, error_message=GATE_ERROR)
    store = _Store(task, _r5_graph("task_r5s"))
    wm = _WM(tmp_path)
    (tmp_path / "project" / "ledger.py").write_text("x = 1\n", encoding="utf-8")
    wm.save_artifact(
        "task_r5s", "verification_manifest.json",
        json.dumps(_green_manifest("task_r5s", tmp_path / "project")),
    )
    orch = _orchestrator(store, wm)
    settled = await orch.apply_final_verdict(
        "task_r5s", _report("task_r5s", passed=11, total=11)
    )
    assert settled.state == TaskState.COMPLETED

    monkeypatch.setattr(
        delegate.workspace_manager, "get_workspace_paths", wm.get_workspace_paths
    )
    result = await delegate.get_task_status("task_r5s", store=store)

    assert result.status == "SUCCESS"
    assert result.result["build_verdict"] == "SUCCESS"
    assert any("Run Tests" in s for s in result.result["verdict_superseded"])
    assert result.error is None


@pytest.mark.asyncio
async def test_status_endpoint_legacy_r5_shape_derives_success(tmp_path, monkeypatch):
    """A pre-FRG-011 task record (FAILED, no stamp) with a green manifest
    and a gate-only failure history derives the same SUCCESS verdict --
    on main this endpoint answered FAILED over the all-passed manifest
    it embedded in the same response."""
    task = _task("task_legacy", TaskState.FAILED, error_message=GATE_ERROR)
    store = _Store(task, _r5_graph("task_legacy"))
    wm = _WM(tmp_path)
    (tmp_path / "project" / "ledger.py").write_text("x = 1\n", encoding="utf-8")
    wm.save_artifact(
        "task_legacy", "verification_manifest.json",
        json.dumps(_green_manifest("task_legacy", tmp_path / "project")),
    )
    monkeypatch.setattr(
        delegate.workspace_manager, "get_workspace_paths", wm.get_workspace_paths
    )

    result = await delegate.get_task_status("task_legacy", store=store)

    assert result.status == "SUCCESS"
    assert result.verification_manifest["all_passed"] is True
    assert any("Run Tests" in s for s in result.result["verdict_superseded"])


@pytest.mark.asyncio
async def test_status_endpoint_partial_manifest_stays_partial(tmp_path, monkeypatch):
    """Regression guard (both directions): a partial battery never
    surfaces as SUCCESS, whatever the stored state says."""
    task = _task("task_part", TaskState.COMPLETED)
    store = _Store(task, _r5_graph("task_part"))
    wm = _WM(tmp_path)
    (tmp_path / "project" / "ledger.py").write_text("x = 1\n", encoding="utf-8")
    manifest = _green_manifest("task_part", tmp_path / "project")
    manifest["all_passed"] = False
    manifest["partial_failure"] = True
    manifest["overall_status"] = "PARTIAL_FAILURE"
    manifest["failure_summary"] = "2 stages failed"
    manifest["failed_stages"] = 2
    manifest["passed_stages"] = 9
    for i, stage in enumerate(manifest["stages"].values()):
        if i >= 9:
            stage["passed"] = False
            stage["exit_code"] = 1
    wm.save_artifact("task_part", "verification_manifest.json", json.dumps(manifest))
    monkeypatch.setattr(
        delegate.workspace_manager, "get_workspace_paths", wm.get_workspace_paths
    )

    result = await delegate.get_task_status("task_part", store=store)

    assert result.status == "PARTIAL_FAILURE"


@pytest.mark.asyncio
async def test_background_finalize_reports_the_settled_verdict(tmp_path, monkeypatch):
    """TASK-FRG-038: execute_now no longer re-runs the battery on the
    request; the re-run + settle now happens in the supervised background
    body (the flags ride _schedule_execution). The R5 shape must still
    settle to the one verdict there: on main this shape answered FAILED
    (mirroring the gate-latched state) over an all-passed re-run manifest."""
    task = _task("task_exec", TaskState.FAILED, error_message=GATE_ERROR)
    store = _Store(task, _r5_graph("task_exec"))
    wm = _WM(tmp_path)
    (tmp_path / "project" / "ledger.py").write_text("x = 1\n", encoding="utf-8")
    real_orch = _orchestrator(store, wm)
    fake_orch = SimpleNamespace(
        run_task=AsyncMock(return_value=task),
        apply_final_verdict=real_orch.apply_final_verdict,
        store=store,
    )
    report = _report("task_exec", passed=11, total=11)
    manifest = VerificationManifest(
        task_id="task_exec", overall_status="PASSED", all_passed=True,
        partial_failure=False, total_stages=11, passed_stages=11,
        failed_stages=0, stages={}, evidence=[],
    )
    monkeypatch.setattr(tasks_api, "StateStore", lambda db: store)
    monkeypatch.setattr(tasks_api, "OrchestratorCore", lambda store: fake_orch)
    monkeypatch.setattr(
        tasks_api, "verification_engine",
        SimpleNamespace(
            verify_task=AsyncMock(return_value=report),
            generate_manifest=lambda tid, rep: manifest,
        ),
    )
    monkeypatch.setattr(
        tasks_api, "ProgressTracker", SimpleNamespace(get_tracker=lambda tid: None)
    )
    dispatched: list[tuple[str, str]] = []

    async def _dispatch(webhook_url, task_id, event, data):
        dispatched.append((task_id, event))

    monkeypatch.setattr(
        tasks_api, "webhook_dispatcher", SimpleNamespace(dispatch_event=_dispatch)
    )
    memora_calls: list[dict] = []

    async def _record(**kwargs):
        memora_calls.append(kwargs)

    monkeypatch.setattr(
        tasks_api, "get_memora_client",
        lambda: SimpleNamespace(a_record_interaction=_record),
    )

    await tasks_api._run_task_body(
        "task_exec", "https://example.invalid/hook",
        require_sentinel=False, memora_goal="CSV expense CLI",
    )

    assert store._task.state == TaskState.COMPLETED
    assert store._task.metadata["build_verdict"] == "SUCCESS"
    assert dispatched == [("task_exec", "task_completed")]
    assert len(memora_calls) == 1
    assert memora_calls[0]["event_type"] == "swe_build_verified"
