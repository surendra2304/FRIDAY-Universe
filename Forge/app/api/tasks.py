"""
Enhanced Task Management API for Project FORGE & FRIDAY Integration.
Provides full task lifecycle, inspection, logging, artifact download, cancellation, and soft-archive endpoints.
"""

import asyncio
import json
import mimetypes
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.agents.project_types import detect_project_type
from app.api.schemas import (
    ArtifactResponse,
    FileInspection,
    LogEntry,
    TaskActionRequest,
    TaskActionResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskInspectResponse,
    TaskLogsResponse,
    TaskResponse,
    TaskSummaryResponse,
)
from app.api.webhooks import webhook_dispatcher
from app.api.websocket import ws_manager
from app.core.logging import get_logger
from app.core.orchestrator import OrchestratorCore
from app.core.progress_tracker import ProgressTracker
from app.core.workspace import canonical_path, workspace_manager
from app.execution.dependency_manager import DependencyManager
from app.memory.db import db_manager
from app.memory.models import TaskState
from app.memory.state_store import StateStore
from app.memory.task_lifecycle import InvalidStateTransitionError, TaskStateMachine


def _as_utc(value: datetime) -> datetime:
    """Normalize a possibly naive datetime to UTC for comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


logger = get_logger("api.tasks")
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

def _parse_concurrency_limit(
    raw_value: str | None, *, default: int = 3, maximum: int = 32
) -> int:
    """Parse an operator-configured worker limit without breaking application startup."""
    if (
        isinstance(default, bool)
        or not isinstance(default, int)
        or isinstance(maximum, bool)
        or not isinstance(maximum, int)
        or default < 1
        or maximum < default
    ):
        raise ValueError("default and maximum must be positive ordered integers")
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value.strip())
    except ValueError:
        logger.warning(
            "FORGE_MAX_CONCURRENT_TASKS must be an integer; using default %d",
            default,
        )
        return default
    if value < 1:
        logger.warning(
            "FORGE_MAX_CONCURRENT_TASKS must be positive; using default %d",
            default,
        )
        return default
    if value > maximum:
        logger.warning(
            "FORGE_MAX_CONCURRENT_TASKS exceeds safe maximum; clamping to %d",
            maximum,
        )
        return maximum
    return value



def get_state_store() -> StateStore:
    return StateStore(db_manager)


# Background execution registry. Keyed by task_id so a duplicate submission
# cannot start two concurrent loops for the same task.
# Bounded cache of task_id -> project category. detect_project_type() scans the
# goal against a keyword table and is pure, so memoising it is safe and removes
# the dominant per-request cost of GET /api/tasks.
_project_type_cache: dict[str, str] = {}
_PROJECT_TYPE_CACHE_MAX = 2048

_running_tasks: dict[str, asyncio.Task] = {}
_running_tasks_guard = asyncio.Lock()

# Bound concurrent autonomous pipelines: each can spawn subprocesses and LLM calls.
# Excess submissions wait on this semaphore instead of an unbounded worker pool.
MAX_CONCURRENT_TASKS = _parse_concurrency_limit(
    os.environ.get("FORGE_MAX_CONCURRENT_TASKS")
)
_execution_slots = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


async def _run_task_supervised(task_id: str, webhook_url: str | None) -> None:
    """Drive a task to a terminal state, reporting progress over the websocket."""
    async with _execution_slots:
        await _run_task_body(task_id, webhook_url)


async def _run_task_body(task_id: str, webhook_url: str | None) -> None:
    store = StateStore(db_manager)
    tracker = ProgressTracker.get_tracker(task_id)
    try:
        orchestrator = OrchestratorCore(store=store)
        final = await orchestrator.run_task(task_id)
        if tracker:
            await tracker.complete_task(success=final.state == TaskState.COMPLETED)
        if webhook_url:
            await webhook_dispatcher.dispatch_event(
                webhook_url=webhook_url,
                task_id=task_id,
                event="task_completed" if final.state == TaskState.COMPLETED else "task_failed",
                data={"state": final.state.value, "error": final.error_message},
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f"Background execution failed for task {task_id}: {exc}", exc_info=True)
        try:
            await store.update_task_state(task_id, TaskState.FAILED, error_message=str(exc))
        except Exception:
            pass
        if webhook_url:
            try:
                await webhook_dispatcher.dispatch_event(
                    webhook_url=webhook_url,
                    task_id=task_id,
                    event="task_failed",
                    data={"error": str(exc)},
                )
            except Exception:
                pass
    finally:
        async with _running_tasks_guard:
            _running_tasks.pop(task_id, None)


@tasks_router.get("/queue", summary="Background Execution Queue Status")
async def execution_queue_status() -> dict[str, Any]:
    """Report what is executing and what is waiting.

    Autonomous pipelines are expensive (each spawns subprocesses), so
    submissions beyond FORGE_MAX_CONCURRENT_TASKS wait rather than pile onto a
    single worker. Without this endpoint a user submitting the 20th task had no
    way to tell whether it was stuck or merely queued.
    """
    running: list[str] = []
    waiting: list[str] = []
    for tid, task_obj in list(_running_tasks.items()):
        if task_obj.done():
            continue
        # A task holding a slot is "running"; one blocked on the semaphore has
        # not started its body yet. asyncio cannot tell us which directly, so we
        # ask the coroutine for its current frame name.
        coro = task_obj.get_coro()
        frames = getattr(coro, "cr_frame", None)
        if frames is not None and frames.f_code.co_name == "_run_task_body":
            running.append(tid)
        else:
            waiting.append(tid)
    return {
        "max_concurrent": MAX_CONCURRENT_TASKS,
        "running": sorted(running),
        "waiting": sorted(waiting),
        "running_count": len(running),
        "waiting_count": len(waiting),
    }


def _schedule_execution(task_id: str, webhook_url: str | None = None) -> None:
    """Start (or reuse) the background execution loop for a task."""
    existing = _running_tasks.get(task_id)
    if existing is not None and not existing.done():
        logger.info(f"Task {task_id} is already executing; not starting a second loop")
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(f"No running event loop; task {task_id} will not execute")
        return
    _running_tasks[task_id] = loop.create_task(_run_task_supervised(task_id, webhook_url))


def get_task_lifecycle(store: StateStore = Depends(get_state_store)) -> TaskStateMachine:
    return TaskStateMachine(store)


def get_orchestrator(store: StateStore = Depends(get_state_store)) -> OrchestratorCore:
    return OrchestratorCore(store=store)


@tasks_router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Engineering Task",
)
async def create_task(
    request: TaskCreateRequest,
    orchestrator: OrchestratorCore = Depends(get_orchestrator),
    store: StateStore = Depends(get_state_store),
) -> TaskResponse:
    """Intake, analyze, and provision a new autonomous engineering task."""
    metadata = {}
    if request.task_metadata:
        metadata = request.task_metadata.model_dump(mode="json")
    else:
        metadata = {"priority": "normal", "tags": [], "archived": False}

    if request.webhook_url and "webhook_url" not in metadata:
        metadata["webhook_url"] = request.webhook_url

    task, _ = await orchestrator.intake_and_plan(
        goal=request.goal,
        requirements=request.requirements,
        mode=request.mode,
        repo_url=request.repo_url,
        local_path=request.local_path,
        max_budget=request.max_budget,
    )

    # Attach task metadata
    task.metadata.update(metadata)
    await store.save_task(task)

    # Initialize progress tracker for task
    ptype = detect_project_type(task.goal, task.requirements).category.value
    ProgressTracker.get_or_create(task.id, project_type=ptype)

    # Actually run it. This endpoint used to call intake_and_plan() and stop, so
    # every task submitted over HTTP sat in READY forever -- the API was a
    # write-only task board, not an autonomous engine. The execution loop now
    # runs as a supervised background task and the endpoint returns immediately.
    _schedule_execution(task.id, task.metadata.get("webhook_url"))

    # Optional webhook dispatch
    webhook_url = task.metadata.get("webhook_url")
    if webhook_url:
        await webhook_dispatcher.dispatch_event(
            webhook_url=webhook_url,
            task_id=task.id,
            event="task_started",
            data={"goal": task.goal, "state": task.state.value, "metadata": task.metadata},
        )

    # Broadcast task creation via WebSocket
    await ws_manager.broadcast_global(
        {
            "event": "task.created",
            "task_id": task.id,
            "goal": task.goal,
            "state": task.state.value,
            "metadata": task.metadata,
        }
    )

    return TaskResponse(
        id=task.id,
        goal=task.goal,
        requirements=task.requirements,
        mode=task.mode,
        workspace_path=task.workspace_path,
        max_budget=task.max_budget,
        budget_consumed=task.budget_consumed,
        state=task.state,
        progress_percentage=task.progress_percentage,
        error_message=task.error_message,
        metadata=task.metadata,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@tasks_router.get("", response_model=list[TaskSummaryResponse], summary="List Tasks")
async def list_tasks(
    status: TaskState | None = Query(default=None, description="Filter by lifecycle state"),
    limit: int = Query(default=50, ge=1, le=500, description="Max tasks to return"),
    since_timestamp: datetime | None = Query(
        default=None, description="Filter tasks updated after timestamp"
    ),
    include_archived: bool = Query(default=False, description="Include soft-archived tasks"),
    store: StateStore = Depends(get_state_store),
) -> list[TaskSummaryResponse]:
    """Retrieve summarized list of engineering tasks with optional status and time filtering."""
    # The store-level LIMIT must not pre-empt the caller's filters. Fetching
    # exactly `limit` rows and then dropping archived / stale ones returned
    # fewer results (often none) even when matches existed further down the
    # ordering. Fetch a bounded superset, filter, then truncate to `limit`.
    #
    # The superset is only widened when a post-LIMIT filter is actually active:
    # widening unconditionally made GET /api/tasks?limit=10 scan 500 rows and run
    # project-type detection on every one (measured p50 255ms under sustained
    # load, p99 3.0s).
    needs_superset = since_timestamp is not None or not include_archived
    fetch_limit = min(max(limit * 5, limit + 50), 2000) if needs_superset else limit
    tasks = await store.list_tasks(state=status, limit=fetch_limit, since_timestamp=since_timestamp)
    summaries: list[TaskSummaryResponse] = []

    for t in tasks:
        is_archived = t.metadata.get("archived", False)
        if not include_archived and is_archived:
            continue

        if since_timestamp and t.updated_at and t.updated_at < since_timestamp:
            continue

        if len(summaries) >= limit:
            break

        # Project type is derived from the goal text, which never changes for a
        # given task. Recomputing it on every list call made each request O(rows
        # x keyword scan) and serialized on the event loop: 10 concurrent readers
        # on one worker measured 398ms p50 / 562ms p99 for limit=10. Cache by
        # task id and fall back to the persisted value when available.
        ptype = _project_type_cache.get(t.id)
        if ptype is None:
            ptype = t.metadata.get("project_type")
        if ptype is None:
            ptype = detect_project_type(t.goal, t.requirements).category.value
            if len(_project_type_cache) >= _PROJECT_TYPE_CACHE_MAX:
                _project_type_cache.clear()
            _project_type_cache[t.id] = ptype
        priority = t.metadata.get("priority", "normal")

        summaries.append(
            TaskSummaryResponse(
                id=t.id,
                goal=t.goal,
                state=t.state,
                progress_percentage=t.progress_percentage,
                project_type=ptype,
                priority=priority,
                created_at=t.created_at,
                updated_at=t.updated_at,
                archived=is_archived,
            )
        )

    return summaries


@tasks_router.get("/{task_id}", response_model=TaskDetailResponse, summary="Get Task Details & ETA")
async def get_task(
    task_id: str,
    store: StateStore = Depends(get_state_store),
) -> TaskDetailResponse:
    """Retrieve fine-grained task status, current DAG stage, and dynamic ETA estimation."""
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
        )

    paths = workspace_manager.get_workspace_paths(task_id)
    workspace_dirs = {}
    if paths:
        workspace_dirs = {
            "root": str(paths.root),
            "project": str(paths.project),
            "artifacts": str(paths.artifacts),
            "logs": str(paths.logs),
            "state": str(paths.state),
            "cache": str(paths.cache),
        }

    # Retrieve progress tracker snapshot if active
    tracker = ProgressTracker.get_tracker(task_id)
    current_stage = None
    est_remaining = None
    est_completion = None
    if tracker:
        snapshot = tracker.get_snapshot()
        current_stage = snapshot.current_stage.value
        est_remaining = snapshot.estimated_remaining_seconds
        est_completion = snapshot.estimated_completion_at

    # Check fallback stub flag or provenance
    provenance_summary = task.metadata.get("provenance_summary")
    if not provenance_summary and paths and (paths.state / "FALLBACK_STUB.json").exists():
        provenance_summary = "Fallback Stub Generation Detected"

    checkpoints = await store.list_checkpoints(task_id)
    # list_checkpoints orders by step_number ASC, so the LAST entry is the most
    # recent checkpoint. Indexing [0] here reported step 1 forever.
    latest_cp = checkpoints[-1].id if checkpoints else None

    return TaskDetailResponse(
        id=task.id,
        goal=task.goal,
        requirements=task.requirements,
        mode=task.mode,
        workspace_path=task.workspace_path,
        max_budget=task.max_budget,
        budget_consumed=task.budget_consumed,
        state=task.state,
        progress_percentage=task.progress_percentage,
        error_message=task.error_message,
        metadata=task.metadata,
        workspace_dirs=workspace_dirs,
        current_stage=current_stage,
        estimated_remaining_seconds=est_remaining,
        estimated_completion_at=est_completion,
        provenance_summary=provenance_summary,
        latest_checkpoint_id=latest_cp,
        checkpoints_count=len(checkpoints),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@tasks_router.get(
    "/{task_id}/logs", response_model=TaskLogsResponse, summary="Get Structured Execution Logs"
)
async def get_task_logs(
    task_id: str,
    level: str | None = Query(
        default=None, description="Filter log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    tail_lines: int = Query(default=100, ge=1, le=1000, description="Number of recent log lines"),
    since_timestamp: str | None = Query(
        default=None, description="Filter log lines since ISO timestamp"
    ),
    store: StateStore = Depends(get_state_store),
) -> TaskLogsResponse:
    """Retrieve structured execution and build logs from task sandbox."""
    paths = workspace_manager.get_workspace_paths(task_id)
    if not paths or not paths.logs.exists():
        return TaskLogsResponse(task_id=task_id, total_lines=0, logs=[])

    # `since_timestamp` used to be accepted and then ignored entirely.
    parsed_since = None
    if since_timestamp:
        try:
            parsed_since = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid since_timestamp '{since_timestamp}'; expected ISO-8601.",
            )

    log_files = list(paths.logs.glob("*.log"))
    entries: list[LogEntry] = []

    for lf in log_files:
        try:
            lines = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in lines:
                if not line.strip():
                    continue

                # Infer log level
                entry_level = "INFO"
                if "DEBUG" in line.upper():
                    entry_level = "DEBUG"
                elif "WARNING" in line.upper() or "WARN" in line.upper():
                    entry_level = "WARNING"
                elif (
                    "ERROR" in line.upper() or "FAIL" in line.upper() or "EXCEPTION" in line.upper()
                ):
                    entry_level = "ERROR"

                if level and entry_level != level.upper():
                    continue

                # Only apply the timestamp filter when the line actually carries a
                # parseable timestamp; lines without one are kept (they cannot be
                # proven stale) but reported as timestamp=None.
                entry_ts = None
                head = line[:64]
                for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        entry_ts = datetime.strptime(head[: len(fmt) + 12], fmt)
                        break
                    except ValueError:
                        continue
                if entry_ts is None:
                    try:
                        entry_ts = datetime.fromisoformat(head.split(" ")[0].rstrip(","))
                    except ValueError:
                        entry_ts = None

                if (
                    parsed_since is not None
                    and entry_ts is not None
                    and _as_utc(entry_ts) < _as_utc(parsed_since)
                ):
                    continue

                entries.append(
                    LogEntry(
                        timestamp=entry_ts.isoformat() if entry_ts is not None else None,
                        level=entry_level,
                        message=line,
                    )
                )
        except Exception:
            pass

    selected = entries[-tail_lines:] if len(entries) > tail_lines else entries
    return TaskLogsResponse(
        task_id=task_id,
        total_lines=len(entries),
        logs=selected,
    )


@tasks_router.get(
    "/{task_id}/inspect", response_model=TaskInspectResponse, summary="Deep Task Inspection"
)
async def inspect_task(
    task_id: str,
    store: StateStore = Depends(get_state_store),
) -> TaskInspectResponse:
    """Perform deep inspection of files, verification breakdown, dependencies, and artifacts."""
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
        )

    paths = workspace_manager.get_workspace_paths(task_id)
    files_created: list[FileInspection] = []
    artifacts_list: list[str] = []
    dependencies: list[str] = []
    verification_summary = {}

    if paths:
        # Inspect created project files
        if paths.project.exists():
            for f in paths.project.glob("**/*"):
                if f.is_file():
                    try:
                        content = f.read_text(encoding="utf-8", errors="ignore")
                        lines = len(content.splitlines())
                        files_created.append(
                            FileInspection(
                                path=str(f.relative_to(paths.project)),
                                size_bytes=f.stat().st_size,
                                lines_count=lines,
                            )
                        )
                    except Exception:
                        pass

            # Detect dependencies
            dep_mgr = DependencyManager()
            dependencies = sorted(list(dep_mgr.detect_workspace_dependencies(paths.project)))

        # Inspect artifacts
        if paths.artifacts.exists():
            for art in paths.artifacts.glob("*"):
                if art.is_file():
                    artifacts_list.append(art.name)

        # Inspect verification reports
        report_file = paths.artifacts / "completion_report.json"
        if report_file.exists():
            try:
                data = json.loads(report_file.read_text(encoding="utf-8"))
                verification_summary = data.get("verification_summary", {})
            except Exception:
                pass

    provenance = task.metadata.get("provenance", {})

    return TaskInspectResponse(
        task_id=task.id,
        goal=task.goal,
        state=task.state,
        files_created=files_created,
        verification_summary=verification_summary,
        dependencies=dependencies,
        artifacts=artifacts_list,
        provenance=provenance,
    )


@tasks_router.get(
    "/{task_id}/artifacts",
    response_model=list[ArtifactResponse],
    summary="List Downloadable Artifacts",
)
async def list_task_artifacts(
    task_id: str,
    store: StateStore = Depends(get_state_store),
) -> list[ArtifactResponse]:
    """List all available delivery and verification artifacts for a task."""
    paths = workspace_manager.get_workspace_paths(task_id)
    if not paths or not paths.artifacts.exists():
        return []

    results = []
    for art in paths.artifacts.glob("*"):
        if art.is_file():
            mime, _ = mimetypes.guess_type(art.name)
            results.append(
                ArtifactResponse(
                    id=art.stem,
                    task_id=task_id,
                    name=art.name,
                    path=str(art),
                    file_type=mime or "application/octet-stream",
                    size_bytes=art.stat().st_size,
                    created_at=datetime.fromtimestamp(art.stat().st_ctime),
                )
            )

    return results


@tasks_router.get("/{task_id}/artifacts/{filename}", summary="Download Artifact File")
async def download_task_artifact(
    task_id: str,
    filename: str,
):
    """Download a specific artifact file (e.g. completion report, screenshot)."""
    paths = workspace_manager.get_workspace_paths(task_id)
    if not paths or not paths.artifacts.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifacts directory not found."
        )

    # Defense in depth: the artifact must resolve to a file that is strictly
    # contained in this task's artifacts directory. Without this check a
    # traversal filename (e.g. "../../pyproject.toml") escapes the sandbox and
    # streams an arbitrary host file to the caller.
    artifacts_root = canonical_path(paths.artifacts)
    artifact_file = canonical_path(artifacts_root / filename)
    try:
        artifact_file.relative_to(artifacts_root)
    except ValueError as exc:
        logger.warning(
            f"Blocked artifact path traversal attempt for task '{task_id}': '{filename}'"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        ) from exc

    if not artifact_file.exists() or not artifact_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact '{filename}' not found."
        )

    mime, _ = mimetypes.guess_type(filename)
    return FileResponse(
        path=str(artifact_file),
        filename=filename,
        media_type=mime or "application/octet-stream",
    )


async def execute_task_cancellation(
    task_id: str,
    reason: str,
    lifecycle: TaskStateMachine,
    store: StateStore,
) -> TaskActionResponse:
    """Cancel a task and fire every side effect a cancellation should have:
    state transition, progress-tracker close-out, WebSocket broadcast, and
    webhook dispatch.

    This used to live inline inside `tasks_router`'s `/{task_id}/cancel`
    handler, while `app/api/routes.py` registered a second, independent
    `cancel_task` for the exact same logical path -- one that only called
    `lifecycle.cancel()` and skipped the progress tracker, WebSocket
    broadcast, and webhook dispatch entirely. Because FastAPI resolves
    overlapping routes by registration order, `/api/tasks/{id}/cancel` and
    `/api/v1/tasks/{id}/cancel` silently ran *different* handlers: live
    testing confirmed cancelling the same task via the v1 path never
    notified webhooks or WebSocket subscribers, while the non-v1 path did.
    Factoring the real implementation out here and having both routers call
    it removes the possibility of the two paths ever diverging again.
    """
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
        )

    prev_state = task.state

    try:
        await lifecycle.transition(
            task_id=task_id,
            to_state=TaskState.CANCELLED,
            reason=reason,
        )

        # Notify progress tracker and WebSockets
        tracker = ProgressTracker.get_tracker(task_id)
        if tracker:
            await tracker.complete_task(success=False, error=reason)

        await ws_manager.broadcast_to_task(
            task_id,
            {
                "event": "task.cancelled",
                "task_id": task_id,
                "previous_state": prev_state.value,
                "current_state": TaskState.CANCELLED.value,
                "reason": reason,
            },
        )
        await ws_manager.broadcast_global(
            {
                "event": "task.cancelled",
                "task_id": task_id,
                "reason": reason,
            }
        )

        webhook_url = task.metadata.get("webhook_url")
        if webhook_url:
            await webhook_dispatcher.dispatch_event(
                webhook_url=webhook_url,
                task_id=task_id,
                event="task_failed" if reason else "task_completed",
                data={"status": "CANCELLED", "reason": reason},
            )

        return TaskActionResponse(
            task_id=task_id,
            previous_state=prev_state,
            current_state=TaskState.CANCELLED,
            message=f"Task cancelled successfully: {reason}",
            checkpoint_id=None,
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@tasks_router.post(
    "/{task_id}/cancel", response_model=TaskActionResponse, summary="Cancel Running Task"
)
async def cancel_task(
    task_id: str,
    request: TaskActionRequest | None = None,
    lifecycle: TaskStateMachine = Depends(get_task_lifecycle),
    store: StateStore = Depends(get_state_store),
) -> TaskActionResponse:
    """Gracefully cancel a running task and cleanup background resources."""
    reason = (request.reason if request and request.reason else "Cancelled via FRIDAY management API")
    return await execute_task_cancellation(task_id, reason, lifecycle, store)


@tasks_router.delete("/{task_id}", summary="Archive Task (Soft Delete)")
async def archive_task(
    task_id: str,
    store: StateStore = Depends(get_state_store),
):
    """Soft-archive a task while preserving all sandbox files on disk."""
    task = await store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
        )

    task.metadata["archived"] = True
    task.metadata["archived_at"] = datetime.now(UTC).isoformat()
    await store.save_task(task)

    logger.info(f"Task '{task_id}' archived successfully.")
    return {
        "status": "success",
        "task_id": task_id,
        "archived": True,
        "message": f"Task '{task_id}' has been archived and removed from active task listings.",
    }
