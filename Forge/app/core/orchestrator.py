"""
Orchestrator Core for Project FORGE.
Owns the end-to-end task lifecycle, coordinating Task Analyzer, Planner, Agent Registry, and Execution Engine.
"""

import asyncio
import re
from pathlib import Path
from secrets import token_hex
from typing import Any

from app.agents.registry import AgentRegistry, agent_registry
from app.core.analyzer import TaskAnalyzer, task_analyzer
from app.core.context import ContextManager, context_manager
from app.core.logging import get_logger
from app.core.progress_tracker import ProgressTracker
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.engine import ExecutionEngine, execution_engine
from app.memory.db import db_manager
from app.memory.models import (
    TaskEntity,
    TaskGraph,
    TaskMode,
    TaskState,
)
from app.memory.state_store import StateStore
from app.memory.task_lifecycle import TaskStateMachine
from app.monitoring.production_monitor import production_monitor
from app.planning.graph import ExecutableTaskDAG
from app.planning.planner import PlannerEngine, planner_engine
from app.planning.tree import PipelineStage

_STAGE_BY_NAME = {stage.value: stage for stage in PipelineStage}

logger = get_logger("core.orchestrator")

# Serializes task-id allocation across ALL OrchestratorCore instances in this
# process. OrchestratorCore is constructed fresh per HTTP request (see
# app.api.tasks.get_orchestrator), so an instance attribute would do nothing
# to stop concurrent requests from racing each other -- it has to be
# module-level to actually protect the critical section below.
#
# Without this lock, live load testing reproduced the following with 100%
# reliability: 20 concurrent POST /api/tasks all read the same count_tasks()
# total before any of them had inserted, so all 20 computed the identical
# task_id. Whichever one's INSERT won the DB race kept that id; the rest
# detected the UNIQUE collision and silently persisted under a *different*
# randomized id -- but every downstream step (record_event, planner.plan,
# lifecycle.transition) kept using the original, stale `task_id` local
# variable, not the corrected one. The net effect: all 20 HTTP responses
# reported the single winning task's id and goal back to the caller, 19 of
# the 20 real task rows were silently orphaned in PENDING forever (never
# planned, never transitioned to READY, never executed), and their
# workspaces were never cleanly separated either, since `create_workspace()`
# was also called with the pre-retry, possibly-shared id.
_TASK_ID_ALLOC_LOCK = asyncio.Lock()


async def _finalize_tracker(task_id: str, success: bool) -> None:
    """Close out the ProgressTracker for a finished task (best effort)."""
    tracker = ProgressTracker.get_tracker(task_id)
    if tracker is None:
        return
    try:
        await tracker.complete_task(success=success)
    except Exception:
        logger.debug(f"Progress tracker finalization failed for task {task_id}", exc_info=True)


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_text(value: str) -> str:
    """Remove characters that cannot survive a prompt, a filename or a subprocess.

    Newlines and tabs are legitimate in a goal and are kept; NUL and the other
    control characters are not, and they are what actually break the run.
    """
    if not isinstance(value, str):
        return ""
    cleaned = _CONTROL_CHARS.sub("", value)
    return cleaned.strip()


class OrchestratorCore:
    """
    Central conductor of FORGE.
    Orchestrates: Request Intake -> Task Analyzer -> Planner -> State Machine -> Agent Dispatch -> Verification.
    """

    def __init__(
        self,
        store: StateStore | None = None,
        wm: WorkspaceManager | None = None,
        analyzer: TaskAnalyzer | None = None,
        planner: PlannerEngine | None = None,
        registry: AgentRegistry | None = None,
        engine: ExecutionEngine | None = None,
        ctx_manager: ContextManager | None = None,
    ):
        self.store = store or StateStore(db_manager)
        self.wm = wm or workspace_manager
        self.analyzer = analyzer or task_analyzer
        self.planner = planner or planner_engine
        self.registry = registry or agent_registry
        self.engine = engine or execution_engine
        self.context_manager = ctx_manager or context_manager
        self.lifecycle = TaskStateMachine(self.store)

    async def intake_and_plan(
        self,
        goal: str,
        requirements: list[str] | None = None,
        mode: TaskMode = TaskMode.AUTONOMOUS,
        max_budget: float = 10.0,
        custom_workspace: str | None = None,
        repo_url: str | None = None,
        local_path: str | Path | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[TaskEntity, TaskGraph]:
        """
        Intake a user request, create isolated workspace (with optional git clone or local copy),
        run Task Analyzer, synthesize TaskGraph DAG, and transition task to READY.
        """
        from app.memory.models import generate_task_id

        req_list = requirements or []
        # `context` (e.g. the CLI's {"memory_context": ...}) used to be accepted
        # and then dropped on the floor, so Memora recall never reached planning.
        intake_context = dict(context or {})

        # A goal is free text from a user. A NUL byte or other control character
        # survives every downstream prompt and eventually raises
        # ValueError: embedded null byte from an unrelated node -- verified live,
        # where a goal containing \x00 crashed the release_engineer node and
        # failed an otherwise successful build. Strip it once, here, so nothing
        # downstream has to defend against it.
        goal = _sanitize_text(goal)

        # Determine the id, workspace, and DB row for the new task as a single
        # atomic unit (see _TASK_ID_ALLOC_LOCK above for why this has to be
        # process-wide, not per-instance).
        #
        # The old sequence was derived from COUNT(*) and then "checked" with
        # get_task() in a loop -- a textbook check-then-act race: two
        # concurrent submissions both counted N tasks, both produced
        # task{N+1}<timestamp>, both saw get_task() return None, and the second
        # INSERT died with sqlite3.IntegrityError. A per-id retry-with-suffix
        # was added to stop that from surfacing as a 500, but it only fixed the
        # DB row: everything downstream of the insert (record_event,
        # planner.plan, lifecycle.transition, and the TaskResponse returned to
        # the caller) kept referring to the original `task_id` local variable,
        # not the corrected `task.id`. Live load testing showed the result:
        # all concurrent callers got back the one task that happened to win
        # the original id, while every other real submission was silently
        # orphaned in PENDING with a DAG and workspace that nothing ever
        # pointed back to. The lock below makes the collision essentially
        # impossible in the common single-process deployment; the retry path
        # is kept as defense-in-depth for multi-process deployments sharing
        # one SQLite file, and now correctly resyncs `task_id` and the
        # workspace to whatever id actually got persisted.
        async with _TASK_ID_ALLOC_LOCK:
            if hasattr(self.store, "count_tasks"):
                total_count = await self.store.count_tasks()
            else:
                tasks = await self.store.list_tasks(limit=1000)
                total_count = len(tasks)
            task_seq = total_count + 1
            task_id = generate_task_id(task_seq)
            attempts = 0
            while await self.store.get_task(task_id):
                task_seq += 1
                task_id = generate_task_id(task_seq)
                attempts += 1
                if attempts > 50:
                    # Fall back to a collision-proof id rather than looping forever.
                    task_id = generate_task_id(task_seq) + f"x{token_hex(3)}"
                    break
            logger.info(f"Orchestrator intaking task '{task_id}': {goal[:80]}...")

            # 1. Provision isolated workspace under workspaces/<task_id>/
            custom_base = Path(custom_workspace) if custom_workspace else None
            ws_paths = self.wm.create_workspace(
                task_id,
                custom_base=custom_base,
                repo_url=repo_url,
                local_path=local_path,
            )

            # 2. Persist initial task in PENDING state
            task = TaskEntity(
                id=task_id,
                goal=goal,
                requirements=req_list,
                mode=mode,
                workspace_path=str(ws_paths.root.resolve()),
                max_budget=max_budget,
                state=TaskState.PENDING,
                progress_percentage=0,
            )
            try:
                await self.store.create_task(task)
            except Exception as exc:
                # Last-resort guard against a lost race (e.g. another process
                # sharing this SQLite file): retry once with a guaranteed-unique
                # id before surfacing the error to the caller.
                if "UNIQUE" not in str(exc).upper():
                    raise
                logger.warning(f"Task id collision on '{task_id}'; retrying with a unique id")
                task.id = generate_task_id(task_seq) + f"x{token_hex(4)}"
                # The workspace already provisioned above was created under the
                # stale, collided id. Re-provision it under the real id so
                # `task.workspace_path` -- and everything that later writes
                # generated files there -- actually matches the persisted row,
                # instead of silently sharing a directory with whichever task
                # won the original id.
                ws_paths = self.wm.create_workspace(
                    task.id,
                    custom_base=custom_base,
                    repo_url=repo_url,
                    local_path=local_path,
                )
                task.workspace_path = str(ws_paths.root.resolve())
                await self.store.create_task(task)
            # Resync the local id used by every downstream step (events,
            # planning, lifecycle transition) to whatever id was *actually*
            # persisted. Without this line, a retry above silently detaches
            # the rest of this function from the task it just created.
            task_id = task.id
        # Feed the production monitor: record_task_event() had no callers, so the
        # task-failure-rate alert in check_alerts() could never fire.
        production_monitor.record_task_event("submitted")
        await self.store.record_event(
            task_id=task_id,
            event_type="task.created",
            payload={
                "goal": goal,
                "mode": mode.value,
                "max_budget": max_budget,
                "repo_url": repo_url,
                "local_path": str(local_path) if local_path else None,
            },
        )

        # 3. Call Task Analyzer
        analysis = await self.analyzer.analyze(goal, req_list)
        await self.store.record_event(
            task_id=task_id,
            event_type="task.analyzed",
            payload=analysis.model_dump(mode="json"),
        )

        # Check if project workspace already contains existing files
        has_existing_codebase = False
        try:
            has_existing_codebase = any(ws_paths.project.iterdir())
        except Exception:
            has_existing_codebase = False

        # 4. Route to Planner: Synthesize tree and executable DAG
        tree = await self.planner.plan(
            task_id=task_id,
            goal=goal,
            requirements=req_list,
            has_existing_codebase=has_existing_codebase,
            context=intake_context or None,
        )
        dag = ExecutableTaskDAG.from_tree(tree)
        dag_errors = dag.validate()
        if dag_errors:
            error_msg = f"Planning failed due to invalid DAG: {'; '.join(dag_errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        saved_graph = await self.store.save_task_graph(dag.graph)

        await self.store.record_event(
            task_id=task_id,
            event_type="plan.created",
            payload={
                "nodes_count": len(saved_graph.nodes),
                "edges_count": len(saved_graph.edges),
                "goal": goal,
            },
        )

        # 5. Transition task state from PENDING to READY
        ready_task = await self.lifecycle.transition(
            task_id=task_id,
            to_state=TaskState.READY,
            reason="Analysis and 8-stage DAG planning complete",
        )

        return ready_task, saved_graph

    async def step_task(self, task_id: str) -> tuple[TaskEntity, list[str]]:
        """
        Execute the next available batch of ready nodes in the DAG.
        """
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        if task.state in [TaskState.COMPLETED, TaskState.CANCELLED, TaskState.BLOCKED]:
            return task, []

        # Ensure task is marked RUNNING
        if task.state != TaskState.RUNNING:
            task = await self.lifecycle.transition(
                task_id, TaskState.RUNNING, reason="Executing ready DAG wave"
            )

        graph = await self.store.get_latest_task_graph_for_project(task_id)
        if not graph:
            raise ValueError(f"Task graph for task '{task_id}' not found")

        dag = ExecutableTaskDAG(graph)
        ready_nodes = dag.get_ready_nodes()
        executed_nodes: list[str] = []

        if not ready_nodes:
            if dag.is_completed():
                # Check if any file was generated using fallback_stub mode
                has_fallback_stub = False
                fallback_reason = "TASK FAILED: Fell back to stub generation. Please check API keys and try again."
                try:
                    paths = self.wm.get_workspace_paths(task_id)
                    if paths and (paths.state / "FALLBACK_STUB.json").exists():
                        has_fallback_stub = True
                except Exception:
                    pass

                if not has_fallback_stub:
                    for n in dag.graph.nodes.values():
                        if (
                            n.result
                            and isinstance(n.result, dict)
                            and n.result.get("fallback_stub")
                        ):
                            has_fallback_stub = True
                            break

                if has_fallback_stub:
                    task = await self.lifecycle.transition(
                        task_id,
                        TaskState.FAILED,
                        error_message=fallback_reason,
                        progress_percentage=100,
                    )
                    await self.store.record_event(
                        task_id=task_id,
                        event_type="task.failed",
                        payload={"reason": fallback_reason, "fallback_stub": True},
                    )
                    production_monitor.record_task_event("failed")
                    await _finalize_tracker(task_id, success=False)
                else:
                    task = await self.lifecycle.transition(
                        task_id, TaskState.COMPLETED, progress_percentage=100
                    )
                    await self.store.record_event(task_id=task_id, event_type="task.completed")
                    production_monitor.record_task_event("completed")
                    await _finalize_tracker(task_id, success=True)
            return task, []

        # Execute all ready nodes concurrently in parallel wave
        async def _execute_single_node(
            node,
        ) -> tuple[str, bool, dict[str, Any] | None, str | None, str]:
            role_name = node.assigned_agent or "developer"
            agent = self.registry.create_agent(role_name)
            dag.mark_running(node.id)

            # Drive the fine-grained progress tracker. ProgressTracker.start_stage
            # / complete_stage had no callers anywhere in the codebase, so every
            # snapshot froze at current_stage=Project, progress_percentage=0.
            tracker = ProgressTracker.get_or_create(task_id)
            stage_name = node.metadata.get("stage")
            stage = _STAGE_BY_NAME.get(stage_name)
            if stage is not None:
                try:
                    await tracker.start_stage(stage, details={"node": node.title})
                except Exception:
                    logger.debug("Progress tracker start_stage failed", exc_info=True)

            logger.info(
                f"[Parallel Wave] Dispatching node '{node.title}' to specialist agent '{role_name}' in task {task_id}"
            )

            context = self.context_manager.build_agent_context(
                task_id=task_id,
                role_name=role_name,
                node_title=node.title,
                base_context={"goal": task.goal if task else "", "metadata": node.metadata},
                engine=self.engine,
            )

            try:
                result = await agent.execute_step(
                    task_id=task_id,
                    node_title=node.title,
                    context=context,
                    engine=self.engine,
                )
                if stage is not None:
                    try:
                        await tracker.complete_stage(stage, details={"node": node.title})
                    except Exception:
                        logger.debug("Progress tracker complete_stage failed", exc_info=True)
                return node.id, True, result, None, role_name
            except Exception as e:
                logger.error(f"Execution error on node '{node.title}': {e}")
                return node.id, False, None, str(e), role_name

        wave_tasks = [_execute_single_node(node) for node in ready_nodes]
        wave_results = await asyncio.gather(*wave_tasks)

        has_failed = False
        first_error = ""

        for nid, success, res, err, role in wave_results:
            node = dag.graph.nodes[nid]
            if success:
                dag.mark_completed(nid, result=res)
                executed_nodes.append(nid)
                if res and isinstance(res, dict):
                    self.context_manager.record_step_result(task_id, nid, role, res)
                    if "stdout" in res or "exit_code" in res:
                        self.context_manager.record_terminal_output(
                            task_id=task_id,
                            command=res.get("command", f"{role} execution"),
                            exit_code=res.get("exit_code", 0),
                            stdout=res.get("stdout", ""),
                            stderr=res.get("stderr", ""),
                            role=role,
                        )
                await self.store.record_event(
                    task_id=task_id,
                    event_type="node.completed",
                    payload={"node_id": nid, "title": node.title, "agent": role},
                )
                # Checkpoint upon completing verification gate or milestone
                if node.metadata.get("node_type") in ["verification_gate", "milestone"]:
                    await self.lifecycle.checkpoint(
                        task_id=task_id,
                        state_data={"completed_node": nid, "stage": node.metadata.get("stage")},
                        description=f"Checkpoint at gate: {node.title}",
                    )
            else:
                has_failed = True
                first_error = err or "Unknown error"
                dag.mark_failed(nid, error=first_error)
                await self.store.record_event(
                    task_id=task_id,
                    event_type="node.failed",
                    payload={"node_id": nid, "error": first_error},
                )

        # Update saved graph and task progress
        await self.store.save_task_graph(dag.graph)

        # Finding 27 (critical, live-reproduced): a concurrent pause() or
        # cancel() can land on this task while the wave above was still
        # executing (an agent's execute_step() can take a real LLM call, a
        # file write, or any other await -- plenty of time for a user to
        # hit pause/cancel from another request). Those calls persist
        # BLOCKED/CANCELLED immediately, but every write that follows here
        # used to stamp a *new* state derived from the stale, pre-wave
        # `task` object (or compute a fresh COMPLETED/FAILED of its own)
        # straight over whatever had since been persisted -- silently
        # undoing the user's pause or cancel the instant the in-flight wave
        # finished. Live repro: pausing (or cancelling) a task while its
        # single in-flight node was still executing left the task
        # persisted as BLOCKED/CANCELLED for the duration of that await,
        # but step_task()'s own return value -- and the row in the DB --
        # flipped straight back to RUNNING once the wave completed, and
        # run_task()'s loop (which only stops on a terminal/BLOCKED state)
        # happily kept executing a task the user believed they had
        # cancelled. Re-read the live state now and, if it has moved to
        # BLOCKED or CANCELLED behind our back, respect that and stop
        # here instead of resurrecting it.
        current = await self.store.get_task(task_id)
        if current and current.state in (TaskState.CANCELLED, TaskState.BLOCKED):
            logger.info(
                f"Task {task_id} was {current.state.value} by a concurrent request while its "
                "DAG wave was executing; not overwriting with a post-wave state."
            )
            return current, executed_nodes

        if has_failed:
            task = await self.lifecycle.transition(
                task_id=task_id,
                to_state=TaskState.FAILED,
                error_message=first_error,
            )
            production_monitor.record_task_event("failed")
            await _finalize_tracker(task_id, success=False)
            return task, executed_nodes

        progress = dag.get_progress_percentage()

        if dag.is_completed():
            has_fallback_stub = False
            fallback_reason = (
                "TASK FAILED: Fell back to stub generation. Please check API keys and try again."
            )
            try:
                paths = self.wm.get_workspace_paths(task_id)
                if paths and (paths.state / "FALLBACK_STUB.json").exists():
                    has_fallback_stub = True
            except Exception:
                pass

            if not has_fallback_stub:
                for n in dag.graph.nodes.values():
                    if n.result and isinstance(n.result, dict) and n.result.get("fallback_stub"):
                        has_fallback_stub = True
                        break

            if has_fallback_stub:
                task = await self.lifecycle.transition(
                    task_id,
                    TaskState.FAILED,
                    error_message=fallback_reason,
                    progress_percentage=100,
                )
                await self.store.record_event(
                    task_id=task_id,
                    event_type="task.failed",
                    payload={"reason": fallback_reason, "fallback_stub": True},
                )
                production_monitor.record_task_event("failed")
            else:
                task = await self.lifecycle.transition(
                    task_id, TaskState.COMPLETED, progress_percentage=100
                )
                await self.store.record_event(task_id=task_id, event_type="task.completed")
                production_monitor.record_task_event("completed")
        else:
            updated_task = await self.store.update_task_state(
                task_id, state=task.state, progress_percentage=progress
            )
            if updated_task:
                task = updated_task

        return task, executed_nodes

    async def run_task(self, task_id: str, max_iterations: int = 20) -> TaskEntity:
        """
        Run the full autonomous task execution loop until completion or terminal state.

        This is the engine's own completion path, so it must also run the
        objective verification battery and the self-repair loop. Previously only
        the CLI called VerificationEngine, which meant any task driven through
        the API (or any other embedder) reached a terminal state without ever
        being verified: no verification_report.json, no record_verification()
        telemetry, and no recovery attempt.
        """
        iterations = 0
        while iterations < max_iterations:
            iterations += 1
            task, executed = await self.step_task(task_id)
            if task.state in [
                TaskState.COMPLETED,
                TaskState.FAILED,
                TaskState.CANCELLED,
                TaskState.BLOCKED,
            ]:
                break
            if not executed:
                break

        await self._verify_and_repair(task_id)
        task = await self.store.get_task(task_id) or task
        return task

    async def _verify_and_repair(self, task_id: str) -> None:
        """Run the verification battery and attempt self-repair on failures."""
        try:
            from app.verification.engine import VerificationEngine

            # The orchestrator's own execution engine and workspace manager are
            # passed explicitly. Constructing VerificationEngine() with no
            # arguments makes it fall back to the module-level singletons, which
            # belong to whatever workspace the process was configured with at
            # import time -- so any orchestrator built with an injected
            # WorkspaceManager (tests, embders, isolated runs) verified and
            # repaired the wrong directory. Proven live: an isolated run's task
            # reached FAILED with zero verification events recorded against it.
            engine = VerificationEngine(engine=self.engine, wm=self.wm)
            report = await engine.verify_task(task_id)
            logger.info(
                f"Verification for '{task_id}': "
                f"{report.passed_checks}/{report.total_checks} passed"
            )
            if report.all_passed:
                return

            from app.recovery.engine import RecoveryEngine

            recovery = RecoveryEngine(exec_engine=self.engine, verifier=engine)
            recovered_any = False
            for evidence in report.evidence:
                if evidence.passed:
                    continue
                recovered, message, _patch = await recovery.attempt_recovery(task_id, evidence)
                if recovered:
                    recovered_any = True
                    logger.info(f"Self-repair succeeded for '{task_id}': {message}")
                else:
                    logger.warning(f"Self-repair did not fix '{task_id}': {message}")
            if recovered_any:
                await engine.verify_task(task_id)

            # Peer review: specialist agents inspect each other's output and the
            # fixers act on it. This is the collaboration loop that makes the
            # run a team rather than a queue of independent specialists.
            try:
                from app.agents.coordinator import AgentCoordinator

                coordinator = AgentCoordinator(engine=self.engine, max_rounds=2)
                review = await coordinator.review_and_repair(task_id)
                logger.info(
                    f"Peer review for '{task_id}': {review.summary} "
                    f"(repairs={review.repairs})"
                )
                if review.clean:
                    logger.info(f"Peer review cleared all findings for '{task_id}'")
            except Exception as exc:
                logger.warning(f"Peer review failed for '{task_id}': {exc}")
        except Exception as exc:
            # Verification is a reporting gate, not a reason to kill a finished
            # task: log loudly and leave the task in its terminal state.
            logger.error(f"Verification/repair failed for '{task_id}': {exc}", exc_info=True)


orchestrator = OrchestratorCore()
