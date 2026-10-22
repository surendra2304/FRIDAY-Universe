"""Universal Forge Delegation API for FRIDAY Universe Protocol."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.tasks import get_orchestrator, get_state_store
from app.core.logging import get_logger
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import workspace_manager
from app.integrations.memora_client import get_memora_client
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore
from app.verification.engine import verification_engine
from app.verification.evidence import VerificationManifest, VerificationReport

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
    status: str = "SUCCESS"  # SUCCESS, FAILED, PARTIAL_FAILURE, RUNNING, CANCELLED
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    error: str | None = None
    execution_time_ms: int = 0
    verification_manifest: dict[str, Any] | None = None


async def _dispatch_webhook_callback(callback_url: str, result: TaskResultModel) -> None:
    """Send asynchronous webhook callback notification upon task outcome."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(callback_url, json=result.model_dump(mode="json"))
            logger.info(f"Successfully dispatched callback webhook to {callback_url}")
    except Exception as exc:
        logger.warning(f"Failed to dispatch callback webhook to {callback_url}: {exc}")


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
            return TaskResultModel(
                task_id=envelope.task_id,
                target_agent="forge",
                status="SUCCESS",
                result={"active_tasks": len(tasks), "engine_status": "ONLINE"},
                summary=f"Forge SWE engine online, {len(tasks)} recent tasks in queue",
                execution_time_ms=lat,
            )

        if action == "cancel":
            target_id = envelope.payload.get("task_id") or envelope.task_id
            await store.update_task_state(target_id, state=TaskState.CANCELLED)
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

            if manifest.all_passed:
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
                task_status = "PARTIAL_FAILURE" if manifest.partial_failure else "FAILED"
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

        # Execute synchronously if requested
        if execute_now:
            completed_task = await orchestrator.run_task(task.id)
            report = await verification_engine.verify_task(task.id)
            manifest = verification_engine.generate_manifest(task.id, report)
            manifest_dict = manifest.model_dump(mode="json")

            # Check pre-delivery Sentinel gate if required
            if require_sentinel:
                from app.verification.security_scanner import OutputSecurityScanner

                paths = workspace_manager.get_workspace_paths(task.id)
                if paths:
                    scanner = OutputSecurityScanner(paths.project)
                    scan_report = scanner.scan_all()
                    if scan_report.blocks_delivery or scan_report.critical_count > 0:
                        lat = int((time.time() - t0) * 1000)
                        res = TaskResultModel(
                            task_id=task.id,
                            target_agent="forge",
                            status="FAILED",
                            error=f"Sentinel Gate Failure: {scan_report.critical_count} critical findings detected.",
                            summary="Blocked by Sentinel security review gate.",
                            verification_manifest=manifest_dict,
                            execution_time_ms=lat,
                        )
                        if callback_url:
                            asyncio.create_task(_dispatch_webhook_callback(callback_url, res))
                        return res

            # Memora writeback ONLY if verification completely passed
            if manifest.all_passed:
                try:
                    memora = get_memora_client()
                    await memora.a_record_interaction(
                        user_input=f"Engineering build: {goal}",
                        agent_output=f"Successfully synthesized and verified goal in task {task.id}",
                        agent_name="forge",
                        event_type="swe_build_verified",
                        tags=["forge", "verified", "production_pass"],
                        metadata={"task_id": task.id, "stages": manifest.total_stages},
                    )
                    logger.info(f"Recorded verified build experience to Memora for task {task.id}")
                except Exception as mem_err:
                    logger.warning(f"Memora writeback non-fatal warning: {mem_err}")

            lat = int((time.time() - t0) * 1000)

            # Check for partial failure: code synthesized but verification checks failed
            if not manifest.all_passed:
                task_status = "PARTIAL_FAILURE" if manifest.partial_failure else "FAILED"
                res = TaskResultModel(
                    task_id=task.id,
                    target_agent="forge",
                    status=task_status,
                    result={
                        "forge_task_id": task.id,
                        "goal": task.goal,
                        "state": completed_task.state.value if hasattr(completed_task.state, "value") else str(completed_task.state),
                        "manifest": manifest_dict,
                    },
                    summary=f"Code generation finished, but verification failed: {manifest.failure_summary}",
                    error=manifest.failure_summary,
                    verification_manifest=manifest_dict,
                    execution_time_ms=lat,
                )
                if callback_url:
                    asyncio.create_task(_dispatch_webhook_callback(callback_url, res))
                return res

            res = TaskResultModel(
                task_id=task.id,
                target_agent="forge",
                status="SUCCESS",
                result={
                    "forge_task_id": task.id,
                    "goal": task.goal,
                    "state": completed_task.state.value if hasattr(completed_task.state, "value") else str(completed_task.state),
                    "manifest": manifest_dict,
                },
                summary=f"Forge successfully synthesized and verified goal (Task ID: {task.id})",
                verification_manifest=manifest_dict,
                execution_time_ms=lat,
            )
            if callback_url:
                asyncio.create_task(_dispatch_webhook_callback(callback_url, res))
            return res

        lat = int((time.time() - t0) * 1000)
        return TaskResultModel(
            task_id=envelope.task_id,
            target_agent="forge",
            status="SUCCESS",
            result={
                "forge_task_id": task.id,
                "goal": task.goal,
                "state": task.state.value if hasattr(task.state, "value") else str(task.state),
                "plan_stages": len(plan.stages) if hasattr(plan, "stages") else 0,
            },
            summary=f"Forge accepted engineering goal '{goal[:60]}...' (Task ID: {task.id})",
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
            except Exception:
                manifest_data = None

    task_state_str = task.state.value if hasattr(task.state, "value") else str(task.state)

    status_str = "RUNNING"
    if task.state == TaskState.COMPLETED:
        status_str = "SUCCESS"
    elif task.state == TaskState.FAILED:
        status_str = "PARTIAL_FAILURE" if (manifest_data and manifest_data.get("partial_failure")) else "FAILED"
    elif task.state == TaskState.CANCELLED:
        status_str = "CANCELLED"
    elif task.state == TaskState.BLOCKED:
        status_str = "BLOCKED"

    return TaskResultModel(
        task_id=task_id,
        target_agent="forge",
        status=status_str,
        result={
            "goal": task.goal,
            "state": task_state_str,
            "progress_percentage": task.progress_percentage,
            "created_at": task.created_at.isoformat() if hasattr(task.created_at, "isoformat") else str(task.created_at),
        },
        summary=f"Task '{task_id}' is currently {task_state_str} ({task.progress_percentage}%)",
        error=task.error_message,
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

    await store.update_task_state(task_id, state=TaskState.CANCELLED)
    await store.record_event(
        task_id=task_id,
        event_type="task.cancelled",
        payload={"reason": "User or peer agent requested cancellation."},
    )

    return TaskResultModel(
        task_id=task_id,
        target_agent="forge",
        status="CANCELLED",
        summary=f"Task '{task_id}' has been cancelled.",
    )
