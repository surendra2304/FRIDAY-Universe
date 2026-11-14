"""TASK-REL-019: Forge task-status truthfulness across ALL modes.

Round-2/TASK-REL-011 fixed the autonomous delegate path (accepted tasks now
execute and report RUNNING). The audit behind this file found the remaining
surface still lying:

* task.mode was stored at intake and read NOWHERE — a plan_only task ran
  the full autonomous pipeline and could return SUCCESS with a completion
  receipt; a verify_only task built code it was only asked to check.
* routes.py's POST /tasks (bare mount + /api/v1 mount, shadowing the
  canonical handler) never scheduled execution at all.
* The delegate status endpoint reported PENDING/READY/VERIFYING as
  "RUNNING".
* The delegate execute_now branch consulted only the re-run verification
  manifest, so a task that ended FAILED could still be reported SUCCESS.
* The delegate cancel action wrote CANCELLED directly, bypassing the
  lifecycle machine: phantom tasks "cancelled" successfully and COMPLETED
  tasks could be flipped to CANCELLED.
* The stale-task reconciler would have expired a delivered plan_only plan
  (resting in READY by design) to CANCELLED after 24h.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api import delegate, routes as routes_api, tasks as tasks_api
from app.api.delegate import TaskEnvelopeModel
from app.api.schemas import TaskCreateRequest
from app.core.orchestrator import OrchestratorCore
from app.memory.models import TaskMode, TaskState


def test_plan_stage_count_reads_taskgraph_nodes():
    assert delegate._plan_stage_count(SimpleNamespace(nodes={"a": 1, "b": 2})) == 2
    assert delegate._plan_stage_count(SimpleNamespace(stages=[1, 2, 3])) == 3
    assert delegate._plan_stage_count(SimpleNamespace()) == 0


# --------------------------------------------------------------------------
# Delegate: plan_only
# --------------------------------------------------------------------------

def _intake(task_id="task_mode_1", goal="Build a palindrome checker"):
    task = SimpleNamespace(id=task_id, goal=goal, state=TaskState.READY)
    # TaskGraph's real shape: stages live in a `nodes` dict.
    plan = SimpleNamespace(nodes={"n1": object(), "n2": object(), "n3": object()})
    return task, plan


@pytest.mark.asyncio
async def test_delegate_plan_only_returns_planned_and_schedules_nothing(monkeypatch):
    scheduled: list[str] = []
    monkeypatch.setattr(delegate, "_schedule_execution", lambda tid, url=None: scheduled.append(tid))
    task, plan = _intake()
    orchestrator = SimpleNamespace(
        intake_and_plan=AsyncMock(return_value=(task, plan)),
        run_task=AsyncMock(side_effect=AssertionError("plan_only must never execute")),
    )
    envelope = TaskEnvelopeModel(
        task_id="env-plan",
        source_agent="friday",
        action="build",
        payload={"goal": "Build a palindrome checker", "mode": "plan_only"},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    assert result.status == "PLANNED"  # never SUCCESS for a plan
    assert result.result["state"] == "PLANNED"
    assert result.result["mode"] == "plan_only"
    assert result.result["plan_stages"] == 3  # counted from TaskGraph.nodes
    assert result.result["forge_task_id"] == "task_mode_1"
    assert result.receipt is None  # receipts certify executed work only
    assert scheduled == []
    orchestrator.run_task.assert_not_called()


@pytest.mark.asyncio
async def test_delegate_plan_only_ignores_execute_now(monkeypatch):
    scheduled: list[str] = []
    monkeypatch.setattr(delegate, "_schedule_execution", lambda tid, url=None: scheduled.append(tid))
    task, plan = _intake()
    orchestrator = SimpleNamespace(
        intake_and_plan=AsyncMock(return_value=(task, plan)),
        run_task=AsyncMock(side_effect=AssertionError("plan_only must never execute")),
    )
    envelope = TaskEnvelopeModel(
        task_id="env-plan-now",
        source_agent="friday",
        action="build",
        payload={"goal": "Build a palindrome checker", "mode": "plan_only", "execute_now": True},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    assert result.status == "PLANNED"
    assert result.receipt is None
    assert scheduled == []
    orchestrator.run_task.assert_not_called()


@pytest.mark.asyncio
async def test_delegate_verify_only_still_schedules_execution(monkeypatch):
    scheduled: list[str] = []
    monkeypatch.setattr(delegate, "_schedule_execution", lambda tid, url=None: scheduled.append(tid))
    task, plan = _intake()
    orchestrator = SimpleNamespace(intake_and_plan=AsyncMock(return_value=(task, plan)))
    envelope = TaskEnvelopeModel(
        task_id="env-verify",
        source_agent="friday",
        action="build",
        payload={"goal": "Check the converter", "mode": "verify_only"},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    # verify_only DOES schedule — the runner's verify-only path runs just
    # the battery. What it must never do is report success at intake.
    assert scheduled == ["task_mode_1"]
    assert result.status == "RUNNING"
    assert result.receipt is None


# --------------------------------------------------------------------------
# Delegate: execute_now terminal-state gate
# --------------------------------------------------------------------------

def _manifest(all_passed=True, partial_failure=False):
    return SimpleNamespace(
        all_passed=all_passed,
        partial_failure=partial_failure,
        failure_summary="" if all_passed else "stages failed",
        total_stages=3,
        model_dump=lambda mode=None: {"all_passed": all_passed, "stages": {}},
    )


def _patch_verification(monkeypatch, manifest):
    engine = SimpleNamespace(
        verify_task=AsyncMock(return_value=SimpleNamespace(all_passed=manifest.all_passed)),
        generate_manifest=lambda task_id, report: manifest,
    )
    monkeypatch.setattr(delegate, "verification_engine", engine)
    monkeypatch.setattr(delegate, "_task_artifact_paths", lambda task_id: [])
    monkeypatch.setattr(
        delegate,
        "get_memora_client",
        lambda: SimpleNamespace(a_record_interaction=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_delegate_execute_now_failed_task_is_not_success(monkeypatch):
    _patch_verification(monkeypatch, _manifest(all_passed=True))
    task, plan = _intake()
    failed_task = SimpleNamespace(
        id=task.id, goal=task.goal, state=TaskState.FAILED, error_message="node blew up"
    )
    orchestrator = SimpleNamespace(
        intake_and_plan=AsyncMock(return_value=(task, plan)),
        run_task=AsyncMock(return_value=failed_task),
    )
    envelope = TaskEnvelopeModel(
        task_id="env-fail",
        source_agent="friday",
        action="build",
        payload={"goal": "Build a palindrome checker", "execute_now": True},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    # The leftover artifacts happened to verify; the task still FAILED and
    # must be reported as such — never SUCCESS, never with a receipt.
    assert result.status == "FAILED"
    assert result.result["state"] == "FAILED"
    assert result.receipt is None
    assert "node blew up" in (result.error or "")


@pytest.mark.asyncio
async def test_delegate_execute_now_completed_task_still_success(monkeypatch):
    _patch_verification(monkeypatch, _manifest(all_passed=True))
    task, plan = _intake()
    done_task = SimpleNamespace(
        id=task.id, goal=task.goal, state=TaskState.COMPLETED, error_message=None
    )
    orchestrator = SimpleNamespace(
        intake_and_plan=AsyncMock(return_value=(task, plan)),
        run_task=AsyncMock(return_value=done_task),
    )
    envelope = TaskEnvelopeModel(
        task_id="env-ok",
        source_agent="friday",
        action="build",
        payload={"goal": "Build a palindrome checker", "execute_now": True},
    )
    result = await delegate.delegate_task(envelope, orchestrator=orchestrator, store=SimpleNamespace())

    assert result.status == "SUCCESS"
    assert result.result["state"] == "COMPLETED"
    assert result.receipt is not None


# --------------------------------------------------------------------------
# Delegate: cancel goes through the lifecycle machine
# --------------------------------------------------------------------------

class _CancelStore:
    def __init__(self, task):
        self._task = task

    async def get_task(self, task_id):
        return self._task if self._task and self._task.id == task_id else None

    async def update_task_state(self, task_id, state, progress_percentage=None, error_message=None):
        self._task.state = state
        return self._task

    async def record_event(self, task_id, event_type, payload=None):
        return SimpleNamespace(task_id=task_id, event_type=event_type)


def _cancel_envelope(task_id):
    return TaskEnvelopeModel(
        task_id="env-cancel",
        source_agent="friday",
        action="cancel",
        payload={"task_id": task_id},
    )


@pytest.mark.asyncio
async def test_delegate_cancel_missing_task_reports_error():
    store = _CancelStore(None)
    result = await delegate.delegate_task(
        _cancel_envelope("task_ghost"), orchestrator=SimpleNamespace(), store=store
    )
    assert result.status == "ERROR"  # not a phantom CANCELLED
    assert "not found" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_delegate_cancel_completed_task_is_refused():
    task = SimpleNamespace(
        id="task_done", state=TaskState.COMPLETED, metadata={}, error_message=None
    )
    store = _CancelStore(task)
    result = await delegate.delegate_task(
        _cancel_envelope("task_done"), orchestrator=SimpleNamespace(), store=store
    )
    assert result.status == "ERROR"
    assert task.state == TaskState.COMPLETED  # the verified record is untouched


@pytest.mark.asyncio
async def test_delegate_cancel_ready_task_cancels():
    task = SimpleNamespace(
        id="task_ready", state=TaskState.READY, metadata={}, error_message=None
    )
    store = _CancelStore(task)
    result = await delegate.delegate_task(
        _cancel_envelope("task_ready"), orchestrator=SimpleNamespace(), store=store
    )
    assert result.status == "CANCELLED"
    assert task.state == TaskState.CANCELLED


# --------------------------------------------------------------------------
# Delegate: status endpoint state mapping
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,mode,expected",
    [
        (TaskState.PENDING, TaskMode.AUTONOMOUS, "PENDING"),
        (TaskState.READY, TaskMode.AUTONOMOUS, "PENDING"),
        (TaskState.READY, TaskMode.PLAN_ONLY, "PLANNED"),
        (TaskState.PENDING, TaskMode.PLAN_ONLY, "PLANNED"),
        (TaskState.RUNNING, TaskMode.AUTONOMOUS, "RUNNING"),
        (TaskState.VERIFYING, TaskMode.AUTONOMOUS, "VERIFYING"),
        (TaskState.VERIFYING, TaskMode.VERIFY_ONLY, "VERIFYING"),
        (TaskState.BLOCKED, TaskMode.AUTONOMOUS, "BLOCKED"),
        (TaskState.CANCELLED, TaskMode.AUTONOMOUS, "CANCELLED"),
    ],
)
async def test_status_endpoint_reports_actual_state(tmp_path, monkeypatch, state, mode, expected):
    monkeypatch.setattr(
        delegate.workspace_manager,
        "get_workspace_paths",
        lambda _: SimpleNamespace(artifacts=tmp_path),
    )
    task = SimpleNamespace(
        state=state,
        mode=mode,
        goal="Build converter",
        progress_percentage=0,
        created_at=datetime.now(UTC),
        error_message=None,
    )
    result = await delegate.get_task_status(
        "task_status_probe", store=SimpleNamespace(get_task=AsyncMock(return_value=task))
    )
    assert result.status == expected
    assert result.result["state"] == state.value
    assert result.result["mode"] == mode.value


@pytest.mark.asyncio
async def test_status_endpoint_tolerates_modeless_records(tmp_path, monkeypatch):
    # Task records written before modes existed have no .mode attribute;
    # status polling must not crash on them.
    monkeypatch.setattr(
        delegate.workspace_manager,
        "get_workspace_paths",
        lambda _: SimpleNamespace(artifacts=tmp_path),
    )
    task = SimpleNamespace(
        state=TaskState.READY,
        goal="Legacy task",
        progress_percentage=0,
        created_at=datetime.now(UTC),
        error_message=None,
    )
    result = await delegate.get_task_status(
        "task_legacy", store=SimpleNamespace(get_task=AsyncMock(return_value=task))
    )
    assert result.status == "PENDING"
    assert result.result["mode"] == ""


# --------------------------------------------------------------------------
# Orchestrator: run_task honours the mode (choke point for every caller)
# --------------------------------------------------------------------------

class _OrchestratorStore:
    def __init__(self, task):
        self._task = task
        self.events: list[tuple[str, str]] = []

    async def get_task(self, task_id):
        return self._task

    async def update_task_state(self, task_id, state, progress_percentage=None, error_message=None):
        self._task.state = state
        if error_message is not None:
            self._task.error_message = error_message
        return self._task

    async def record_event(self, task_id, event_type, payload=None):
        self.events.append((task_id, event_type))
        return SimpleNamespace(task_id=task_id, event_type=event_type)


def _orchestrator(store):
    return OrchestratorCore(
        store=store,
        wm=SimpleNamespace(),
        analyzer=SimpleNamespace(),
        planner=SimpleNamespace(),
        registry=SimpleNamespace(),
        engine=SimpleNamespace(),
        ctx_manager=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_run_task_plan_only_never_executes():
    task = SimpleNamespace(
        id="t_plan", mode=TaskMode.PLAN_ONLY, state=TaskState.READY, error_message=None
    )
    store = _OrchestratorStore(task)
    orchestrator = _orchestrator(store)
    orchestrator.step_task = AsyncMock(side_effect=AssertionError("plan_only executed a step"))

    final = await orchestrator.run_task("t_plan")

    assert final.state == TaskState.READY  # rests as a delivered plan
    assert ("t_plan", "task.plan_only") in store.events


@pytest.mark.asyncio
@pytest.mark.parametrize("all_passed,expected", [(True, TaskState.COMPLETED), (False, TaskState.FAILED)])
async def test_run_task_verify_only_runs_battery_only(monkeypatch, all_passed, expected):
    task = SimpleNamespace(
        id="t_verify", mode=TaskMode.VERIFY_ONLY, state=TaskState.READY, error_message=None
    )
    store = _OrchestratorStore(task)
    orchestrator = _orchestrator(store)
    orchestrator.step_task = AsyncMock(side_effect=AssertionError("verify_only executed a build step"))

    class _FakeVerificationEngine:
        def __init__(self, engine=None, wm=None):
            pass

        async def verify_task(self, task_id):
            return SimpleNamespace(all_passed=all_passed, failure_reasons=[])

        def generate_manifest(self, task_id, report):
            return SimpleNamespace(
                total_stages=2, failure_summary="" if all_passed else "battery failed"
            )

    monkeypatch.setattr("app.verification.engine.VerificationEngine", _FakeVerificationEngine)

    final = await orchestrator.run_task("t_verify")

    assert final.state == expected
    if not all_passed:
        assert "battery failed" in (final.error_message or "")


# --------------------------------------------------------------------------
# POST /tasks (canonical) + reconciler: plan_only is a delivered plan
# --------------------------------------------------------------------------

def _create_request(mode):
    return TaskCreateRequest(goal="Build a palindrome checker", mode=mode)


def _created_task(mode):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id="task_create_1",
        goal="Build a palindrome checker",
        requirements=[],
        mode=mode,
        workspace_path="/tmp/ws",
        max_budget=10.0,
        budget_consumed=0.0,
        state=TaskState.READY,
        progress_percentage=0,
        error_message=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,should_schedule",
    [(TaskMode.PLAN_ONLY, False), (TaskMode.AUTONOMOUS, True), (TaskMode.VERIFY_ONLY, True)],
)
async def test_tasks_api_create_schedules_unless_plan_only(monkeypatch, mode, should_schedule):
    scheduled: list[str] = []
    monkeypatch.setattr(tasks_api, "_schedule_execution", lambda tid, url=None: scheduled.append(tid))
    task = _created_task(mode)
    orchestrator = SimpleNamespace(intake_and_plan=AsyncMock(return_value=(task, SimpleNamespace())))
    store = SimpleNamespace(save_task=AsyncMock())

    await tasks_api.create_task(_create_request(mode), orchestrator=orchestrator, store=store)

    assert (scheduled == ["task_create_1"]) is should_schedule


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,should_schedule",
    [(TaskMode.PLAN_ONLY, False), (TaskMode.AUTONOMOUS, True), (TaskMode.VERIFY_ONLY, True)],
)
async def test_routes_api_create_schedules_unless_plan_only(monkeypatch, mode, should_schedule):
    scheduled: list[str] = []
    monkeypatch.setattr(routes_api, "_schedule_execution", lambda tid, url=None: scheduled.append(tid))
    task = _created_task(mode)
    orchestrator = SimpleNamespace(intake_and_plan=AsyncMock(return_value=(task, SimpleNamespace())))

    await routes_api.create_task(
        _create_request(mode), settings=SimpleNamespace(), orchestrator=orchestrator
    )

    assert (scheduled == ["task_create_1"]) is should_schedule


@pytest.mark.asyncio
async def test_reconcile_never_expires_a_delivered_plan(monkeypatch):
    stale_plan = SimpleNamespace(
        id="t_plan_stale",
        state=TaskState.READY,
        mode=TaskMode.PLAN_ONLY,
        created_at=datetime.now(UTC) - timedelta(hours=96),
    )
    stale_work = SimpleNamespace(
        id="t_work_stale",
        state=TaskState.READY,
        mode=TaskMode.AUTONOMOUS,
        created_at=datetime.now(UTC) - timedelta(hours=96),
    )

    class _Store:
        def __init__(self, tasks):
            self._tasks = {t.id: t for t in tasks}
            self.events = []

        async def list_tasks(self, state=None, limit=50):
            return [t for t in self._tasks.values() if state is None or t.state == state][:limit]

        async def get_task(self, task_id):
            return self._tasks.get(task_id)

        async def update_task_state(self, task_id, state, progress_percentage=None, error_message=None):
            self._tasks[task_id].state = state
            return self._tasks[task_id]

        async def record_event(self, task_id, event_type, payload=None):
            self.events.append((task_id, event_type))
            return SimpleNamespace(task_id=task_id, event_type=event_type)

    store = _Store([stale_plan, stale_work])
    monkeypatch.setattr(tasks_api, "get_state_store", lambda: store)

    expired = await tasks_api.reconcile_stale_tasks(ttl_hours=24)

    assert expired == 1  # only the genuine zombie work task
    assert stale_work.state == TaskState.CANCELLED
    assert stale_plan.state == TaskState.READY  # a delivered plan is not a zombie
