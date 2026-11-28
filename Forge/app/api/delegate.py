"""Universal Forge Delegation API for FRIDAY Universe Protocol."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.tasks import (
    _schedule_execution,
    execute_task_cancellation,
    get_orchestrator,
    get_state_store,
)
from app.core.logging import get_logger
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import workspace_manager
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore
from app.memory.task_lifecycle import TaskStateMachine
from app.verification.engine import verification_engine
from app.verification.evidence import VerificationManifest, VerificationReport
from app.verification.source_integrity import snapshot_matches

logger = get_logger("api.delegate")
delegate_router = APIRouter(prefix="/forge", tags=["FRIDAY Universe Forge Delegation"])


class TaskEnvelopeModel(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    source_agent: str = Field(default="friday")
    target_agent: str = Field(default="forge")
    action: str = Field(default="build")
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default="normal")
    created_at: str | None = None
    trace_id: str | None = None


class TaskResultModel(BaseModel):
    task_id: str
    target_agent: str = "forge"
    # SUCCESS, FAILED, PARTIAL_FAILURE, RUNNING, PENDING, PLANNED, VERIFYING,
    # BLOCKED, CANCELLED, DEGRADED, ERROR
    status: str = "SUCCESS"
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    error: str | None = None
    execution_time_ms: int = 0
    verification_manifest: dict[str, Any] | None = None
    #: FRIDAY's mesh certifies completion only from a receipt naming the
    #: dispatched action, this agent as target, and non-empty evidence.
    receipt: dict[str, Any] | None = None


def _forge_receipt(
    *,
    requested_action: str,
    result: dict[str, Any],
    verification_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "requested_action": requested_action,
        "target": "forge",
        "authorization_decision": "AUTHORIZED",
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "verification_evidence": verification_evidence,
        "failure_reason": None,
    }


def _plan_stage_count(plan: Any) -> int:
    """Stage count of an intake plan.

    TaskGraph carries its stages as ``nodes`` (a dict); the delegate used to
    read a nonexistent ``stages`` attribute and therefore always reported
    plan_stages 0 — including for plans that were actually produced.
    """
    nodes = getattr(plan, "nodes", None)
    if nodes is not None:
        return len(nodes)
    stages = getattr(plan, "stages", None)
    return len(stages) if stages is not None else 0


def _task_mode_value(task: Any) -> str:
    """The task's mode as a plain string ('' when the record predates modes)."""
    mode = getattr(task, "mode", None)
    return str(getattr(mode, "value", mode) or "")


def _task_artifact_paths(task_id: str) -> list[str]:
    """Return bounded real paths only; never advertise deleted temp artifacts.

    Omit Git/config/cache/dependency trees and any symlink escaping the task.
    Existence is evidence of a file, not evidence that its behavior is correct.
    """
    import os

    paths = workspace_manager.get_workspace_paths(task_id)
    if not paths or not getattr(paths, "project", None) or not getattr(paths, "root", None):
        return []
    root = paths.root.resolve()
    found: list[str] = []

    def add(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return
        parts = resolved.relative_to(root).parts
        if any(part.startswith(".") or part in {"__pycache__", "node_modules", "venv", "env", "site-packages"}
               for part in parts):
            return
        name = str(resolved)
        if name not in found:
            found.append(name)

    for name in ("verification_manifest.json", "completion_report.json", "COMPLETION_REPORT.md"):
        add(paths.artifacts / name)
    for directory, dirs, files in os.walk(paths.project, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in {
            "__pycache__", "node_modules", "venv", "env", "site-packages"})
        for name in sorted(files):
            if name.startswith("."):
                continue
            add(Path(directory) / name)
            if len(found) >= 40:
                return found
    return found


def _task_primary_source(task_id: str) -> dict[str, Any] | None:
    """TASK-REL-023: the primary generated source file, content included.

    The delegate result otherwise carries only artifact PATHS, so a caller
    asking "show me the code" could never be shown any — FRIDAY's chat
    reply could name files but not display them (round 3, 2026-11-14:
    the palindrome build's working main.py never reached the user).
    Returns the project's entry source file (main.py preferred, else the
    largest top-level source file; tests/docs excluded) with its content
    bounded to 8000 chars, or None when no source file exists. Content is
    the file's real bytes — on failure paths this is the code Forge
    produced BEFORE the failure, and callers must present it as such.
    """
    paths = workspace_manager.get_workspace_paths(task_id)
    if not paths or not getattr(paths, "project", None):
        return None
    project = paths.project
    try:
        candidates = [
            p for p in project.iterdir()
            if p.is_file()
            and p.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".sh"}
            and not p.name.startswith("test_")
            and p.name != "conftest.py"
        ]
    except OSError:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.name != "main.py", -p.stat().st_size))
    chosen = candidates[0]
    try:
        content = chosen.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    truncated = len(content) > 8000
    return {
        "path": str(chosen),
        "name": chosen.name,
        "content": content[:8000],
        "truncated": truncated,
    }


@delegate_router.post("/delegate", response_model=TaskResultModel, status_code=status.HTTP_200_OK)
async def delegate_task(
    envelope: TaskEnvelopeModel,
    orchestrator: OrchestratorCore = Depends(get_orchestrator),
    store: StateStore = Depends(get_state_store),
) -> TaskResultModel:
    """Execute software engineering delegation from FRIDAY or any peer agent."""
    t0 = time.time()
    action = envelope.action.lower().strip()
    logger.info(f"[FORGE_DELEGATE] Received action '{action}' from '{envelope.source_agent}'")

    try:
        if action in ("status", "health", "ping"):
            tasks = await store.list_tasks(limit=5)
            lat = int((time.time() - t0) * 1000)
            result_body = {"active_tasks": len(tasks), "engine_status": "ONLINE"}
            return TaskResultModel(
                task_id=envelope.task_id,
                target_agent="forge",
                status="SUCCESS",
                result=result_body,
                summary=f"Forge SWE engine online, {len(tasks)} recent tasks in queue",
                execution_time_ms=lat,
                receipt=_forge_receipt(
                    requested_action=action,
                    result=result_body,
                    verification_evidence={
                        "source": "forge.api.v1.forge.delegate",
                        "task_id": envelope.task_id,
                        "queue_snapshot_size": len(tasks),
                        "engine_status": "ONLINE",
                    },
                ),
            )

        if action == "cancel":
            target_id = envelope.payload.get("task_id") or envelope.task_id
            # TASK-REL-019: this used to write CANCELLED straight through
            # update_task_state — no existence check, no transition
            # validation — so it reported CANCELLED for tasks that do not
            # exist and could flip a COMPLETED, verification-certified task
            # to CANCELLED, falsifying its record. Route through the same
            # canonical lifecycle cancellation the /tasks endpoints use and
            # report its verdict honestly.
            try:
                await execute_task_cancellation(
                    target_id,
                    "Cancelled via FRIDAY delegate",
                    TaskStateMachine(store),
                    store,
                )
            except HTTPException as http_exc:
                lat = int((time.time() - t0) * 1000)
                return TaskResultModel(
                    task_id=target_id,
                    target_agent="forge",
                    status="ERROR",
                    summary=f"Task '{target_id}' was not cancelled: {http_exc.detail}",
                    error=str(http_exc.detail),
                    execution_time_ms=lat,
                )
            lat = int((time.time() - t0) * 1000)
            return TaskResultModel(
                task_id=target_id,
                target_agent="forge",
                status="CANCELLED",
                summary=f"Task '{target_id}' has been cancelled.",
                execution_time_ms=lat,
            )

        if action in ("test", "verify"):
            target_id = envelope.payload.get("task_id") or envelope.task_id
            report: VerificationReport = await verification_engine.verify_task(target_id)
            manifest: VerificationManifest = verification_engine.generate_manifest(target_id, report)

            lat = int((time.time() - t0) * 1000)
            manifest_dict = manifest.model_dump(mode="json")

            # TASK-FRG-011: a battery-only verdict, derived by the same
            # function every other surface uses (no task state is settled
            # or consulted by this action).
            from app.verification.verdict import derive_build_verdict

            decision = derive_build_verdict(
                task_state=None,
                battery_all_passed=manifest.all_passed,
                battery_partial_failure=manifest.partial_failure,
                battery_failure_reasons=(
                    [manifest.failure_summary] if manifest.failure_summary else []
                ),
            )
            if decision is not None and decision.verdict.value == "SUCCESS":
                return TaskResultModel(
                    task_id=target_id,
                    target_agent="forge",
                    status="SUCCESS",
                    result=manifest_dict,
                    summary=f"All {manifest.total_stages} verification stages passed.",
                    verification_manifest=manifest_dict,
                    execution_time_ms=lat,
                )
            else:
                task_status = decision.verdict.value if decision is not None else "FAILED"
                return TaskResultModel(
                    task_id=target_id,
                    target_agent="forge",
                    status=task_status,
                    result=manifest_dict,
                    summary=f"Verification failed: {manifest.failure_summary}",
                    error=manifest.failure_summary,
                    verification_manifest=manifest_dict,
                    execution_time_ms=lat,
                )

        # Engineering synthesis action: build / fix / refactor / review
        goal = str(
            envelope.payload.get("goal")
            or envelope.payload.get("prompt")
            or envelope.payload.get("task")
            or str(envelope.payload)
        )
        requirements = envelope.payload.get("requirements", [])
        if isinstance(requirements, str):
            requirements = [requirements]

        local_path = envelope.payload.get("local_path")
        repo_url = envelope.payload.get("repo_url") or envelope.payload.get("repository")
        mode_raw = envelope.payload.get("mode", "autonomous")
        mode_map = {
            "autonomous": TaskMode.AUTONOMOUS,
            "interactive": TaskMode.INTERACTIVE,
            "plan_only": TaskMode.PLAN_ONLY,
            "verify_only": TaskMode.VERIFY_ONLY,
        }
        mode = mode_map.get(str(mode_raw).lower(), TaskMode.AUTONOMOUS)
        execute_now = bool(envelope.payload.get("execute_now", False))
        require_sentinel = bool(envelope.payload.get("require_sentinel_gate", False))
        callback_url = envelope.payload.get("callback_url")

        # Validate repository URL if provided
        if repo_url:
            workspace_manager.validate_repository_url(repo_url)

        task, plan = await orchestrator.intake_and_plan(
            goal=goal,
            requirements=requirements,
            mode=mode,
            repo_url=repo_url,
            local_path=local_path,
        )

        # TASK-REL-019: plan_only means plan ONLY. The mode used to be
        # accepted and then ignored everywhere — the task executed in full
        # (background path) or even returned SUCCESS with a completion
        # receipt (execute_now path) for work the caller explicitly asked
        # not to run. Return the plan as PLANNED: never scheduled, never
        # executed, no receipt (receipts certify executed work only).
        if mode == TaskMode.PLAN_ONLY:
            lat = int((time.time() - t0) * 1000)
            return TaskResultModel(
                task_id=envelope.task_id,
                target_agent="forge",
                status="PLANNED",
                result={
                    "forge_task_id": task.id,
                    "goal": task.goal,
                    "state": "PLANNED",
                    "mode": mode.value,
                    "plan_stages": _plan_stage_count(plan),
                },
                summary=(
                    f"Forge planned engineering goal '{goal[:60]}...' (Task ID: {task.id}); "
                    "plan_only mode — nothing was executed."
                ),
                execution_time_ms=lat,
            )


        # TASK-REL-011: accepting a task must mean executing it. This path
        # used to return SUCCESS at intake and park the task in READY
        # forever — production accumulated 141 such zombies, callers were
        # told work was done that never ran, and FRIDAY's receipt
        # verification failed with "the peer returned no receipt". Schedule
        # the same supervised background execution POST /tasks uses and
        # report the honest RUNNING state; completion is observable via the
        # status endpoint and the completion webhook when a callback_url
        # was supplied.
        # TASK-FRG-038: execute_now used to await the whole DAG + battery
        # inline on this request while live Forge runs a single worker
        # (--workers 1): two live reproductions wedged /health for ~9m20s
        # and 482s (Leg B run 1 + re-run). Route execute_now through the
        # same supervised background execution; the caller's
        # post-completion flags (Sentinel gate, Memora writeback) ride
        # the runner, not the request — see _run_task_body. Completion is
        # observable via GET /tasks/{id}/status and the completion
        # webhook; no receipt is issued at intake (receipts certify
        # executed work only, TASK-REL-019). Callers that need the result
        # synchronously must poll or wait for the webhook — the FRIDAY
        # bus polling adoption is a coordinator ruling, still owed.
        _schedule_execution(
            task.id,
            callback_url,
            require_sentinel=require_sentinel if execute_now else False,
            memora_goal=goal if execute_now else None,
        )
        lat = int((time.time() - t0) * 1000)
        return TaskResultModel(
            task_id=envelope.task_id,
            target_agent="forge",
            status="RUNNING",
            result={
                "forge_task_id": task.id,
                "goal": task.goal,
                "state": "RUNNING",
                "plan_stages": _plan_stage_count(plan),
            },
            summary=f"Forge accepted engineering goal '{goal[:60]}...' (Task ID: {task.id}) and scheduled it for execution; status is RUNNING, not complete.",
            execution_time_ms=lat,
        )

    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        logger.error(f"[FORGE_DELEGATE] Error: {e}")
        return TaskResultModel(
            task_id=envelope.task_id,
            target_agent="forge",
            status="ERROR",
            error=str(e),
            execution_time_ms=lat,
        )


@delegate_router.get("/tasks/{task_id}/status", response_model=TaskResultModel, status_code=status.HTTP_200_OK)
async def get_task_status(
    task_id: str,
    store: StateStore = Depends(get_state_store),
) -> TaskResultModel:
    """Retrieve detailed real-time task status and verification manifest."""
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    # Check for verification manifest artifact
    manifest_data = None
    paths = workspace_manager.get_workspace_paths(task_id)
    if paths:
        manifest_file = paths.artifacts / "verification_manifest.json"
        if manifest_file.exists():
            import json
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                if not isinstance(manifest_data, dict):
                    manifest_data = None
            except Exception:
                manifest_data = None

    task_state_str = task.state.value if hasattr(task.state, "value") else str(task.state)

    status_str = "RUNNING"
    verification_error = None
    verdict_reasons: list[str] = []
    verdict_superseded: list[str] = []
    if task.state == TaskState.VERIFYING:
        # TASK-REL-019: every non-terminal state used to fall through to the
        # RUNNING default, so a task still queued (PENDING/READY) — or a
        # plan_only task resting in READY as a delivered plan — polled as
        # "RUNNING" forever. Report the state the task is actually in.
        status_str = "VERIFYING"
    elif task.state == TaskState.RUNNING:
        status_str = "RUNNING"
    elif task.state in (TaskState.PENDING, TaskState.READY):
        status_str = "PLANNED" if _task_mode_value(task) == TaskMode.PLAN_ONLY.value else "PENDING"
    elif task.state in (TaskState.COMPLETED, TaskState.FAILED):
        # TASK-FRG-011: terminal build states report the ONE derived
        # verdict (app/verification/verdict.py) -- the same derivation
        # that settled the task at finalization -- instead of this
        # endpoint's own third set of rules, which let it disagree with
        # the delegate response and the manifest it embedded (a FAILED
        # status over an all-passed manifest; a SUCCESS over a partial
        # one). Inputs: the saved manifest's effective battery outcome
        # (keeping this endpoint's per-stage exit-code strictness), the
        # graph's named failures, the fallback-stub marker, the snapshot
        # binding, and the finalization stamp -- trusted only when the
        # saved manifest carries the same stamp, because a later battery
        # re-run regenerates the manifest unstamped and supersedes it.
        from app.verification.verdict import (
            derive_build_verdict,
            failure_reasons_from_graph,
            stamped_verdict_of,
        )

        stages = manifest_data.get("stages") if isinstance(manifest_data, dict) else None
        battery_all_passed = None
        battery_partial = None
        battery_reasons: list[str] = []
        if isinstance(manifest_data, dict) and isinstance(stages, dict) and stages:
            battery_all_passed = bool(
                manifest_data.get("all_passed") is True
                and not manifest_data.get("failed_stages")
                and all(
                    isinstance(stage, dict)
                    and stage.get("passed") is True
                    and type(stage.get("exit_code")) is int
                    and stage["exit_code"] == 0
                    for stage in stages.values()
                )
            )
            battery_partial = bool(manifest_data.get("partial_failure"))
            if manifest_data.get("failure_summary"):
                battery_reasons = [str(manifest_data["failure_summary"])]
        elif isinstance(manifest_data, dict):
            # A manifest exists but carries no usable stage evidence:
            # it does not certify the build (pinned behaviour from
            # test_delegate_verification_status — a COMPLETED state
            # must not paper over it). That is a failing battery
            # input, not missing evidence.
            battery_all_passed = False
            battery_partial = bool(manifest_data.get("partial_failure"))
            battery_reasons = [
                str(
                    manifest_data.get("failure_summary")
                    or "Saved verification does not certify task completion."
                )
            ]

        snapshot_bound = None
        if battery_all_passed:
            project = getattr(paths, "project", None) if paths else None
            snapshot_bound = bool(
                project is not None
                and snapshot_matches(project, manifest_data.get("source_snapshot"))
            )

        hard_reasons: list[str] = []
        gate_reasons: list[str] = []
        graph_getter = getattr(store, "get_latest_task_graph_for_project", None)
        if graph_getter is not None:
            try:
                graph = await graph_getter(task_id)
            except Exception:
                graph = None
            if graph is not None:
                hard_reasons, gate_reasons = failure_reasons_from_graph(graph)
        if paths is not None:
            try:
                if (paths.state / "FALLBACK_STUB.json").exists():
                    hard_reasons.append(
                        "TASK FAILED: Fell back to stub generation. "
                        "Please check API keys and try again."
                    )
            except Exception:
                pass

        stamped = stamped_verdict_of(task)
        if not (
            isinstance(manifest_data, dict)
            and manifest_data.get("build_verdict") == stamped
        ):
            stamped = None

        decision = derive_build_verdict(
            task_state=task.state,
            battery_all_passed=battery_all_passed,
            battery_partial_failure=battery_partial,
            battery_failure_reasons=battery_reasons,
            hard_failure_reasons=hard_reasons,
            gate_failure_reasons=gate_reasons,
            stamped_verdict=stamped,
            stamped_reasons=(
                manifest_data.get("verdict_reasons") or [] if stamped else []
            ),
            stamped_superseded=(
                manifest_data.get("superseded_checks") or [] if stamped else []
            ),
            recorded_error=task.error_message,
            snapshot_bound=snapshot_bound,
            evidence_available=manifest_data is not None,
        )
        if decision is not None:
            status_str = decision.verdict.value
            verdict_reasons = list(decision.reasons)
            verdict_superseded = list(decision.superseded)
            if decision.reasons:
                verification_error = "; ".join(decision.reasons)
    elif task.state == TaskState.CANCELLED:
        status_str = "CANCELLED"
    elif task.state == TaskState.BLOCKED:
        status_str = "BLOCKED"

    summary = f"Task '{task_id}' execution state {task_state_str}; verification status {status_str}."
    if verdict_superseded:
        summary += (
            " Superseded in-graph gate verdict(s): "
            + "; ".join(verdict_superseded)
            + "."
        )

    return TaskResultModel(
        task_id=task_id,
        target_agent="forge",
        status=status_str,
        result={
            "goal": task.goal,
            "state": task_state_str,
            "mode": _task_mode_value(task),
            "progress_percentage": task.progress_percentage,
            "build_verdict": status_str,
            "verdict_reasons": verdict_reasons,
            "verdict_superseded": verdict_superseded,
            "artifacts": _task_artifact_paths(task_id),
            "created_at": task.created_at.isoformat() if hasattr(task.created_at, "isoformat") else str(task.created_at),
        },
        summary=summary,
        error=None if status_str == "SUCCESS" else (verification_error or task.error_message),
        verification_manifest=manifest_data,
    )


@delegate_router.post("/tasks/{task_id}/cancel", response_model=TaskResultModel, status_code=status.HTTP_200_OK)
async def cancel_task(
    task_id: str,
    store: StateStore = Depends(get_state_store),
) -> TaskResultModel:
    """Cancel an ongoing task and record cancellation."""
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    # TASK-REL-019: this route used to write CANCELLED straight through
    # update_task_state, so a COMPLETED, verification-certified task could
    # be flipped to CANCELLED, falsifying its record. Route through the
    # canonical lifecycle cancellation like every other cancel path; its
    # HTTP 409 for illegal transitions propagates as this endpoint's
    # verdict, and the record stays untouched.
    await execute_task_cancellation(
        task_id,
        "Cancelled via delegate REST route",
        TaskStateMachine(store),
        store,
    )

    return TaskResultModel(
        task_id=task_id,
        target_agent="forge",
        status="CANCELLED",
        summary=f"Task '{task_id}' has been cancelled.",
    )


# --- Fleet task contract (TASK-FRG-002) -------------------------------------
# The fleet dispatch bus posts every specialist task to POST /v1/task/execute
# (FRIDAY/apps/core/.../universe_dispatch_bus.py), but Forge only served
# /api/v1/forge/delegate, so a FRIDAY-chat code task died at the bus with
# "Action 'build' not found on Forge". This router is a thin adapter over the
# delegate execution path: the fleet payload maps 1:1 onto TaskEnvelopeModel
# (the bus's extra `agent` / `timeout_sec` fields are ignored), and
# delegate_task does the work. Auth is the app's global API-key middleware
# (same as /delegate); nothing is exempted here.
task_contract_router = APIRouter(prefix="/v1", tags=["FRIDAY Universe Forge Task Contract"])


@task_contract_router.post("/task/execute", response_model=TaskResultModel, status_code=status.HTTP_200_OK)
async def task_execute(
    envelope: TaskEnvelopeModel,
    orchestrator: OrchestratorCore = Depends(get_orchestrator),
    store: StateStore = Depends(get_state_store),
) -> TaskResultModel:
    """Fleet contract entrypoint: execute a task dispatched by FRIDAY."""
    return await delegate_task(envelope, orchestrator, store)
