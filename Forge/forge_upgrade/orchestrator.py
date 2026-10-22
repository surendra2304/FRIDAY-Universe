from __future__ import annotations

import logging
from dataclasses import dataclass

from .audit import AuditLog
from .budget import BudgetController
from .dag import DagScheduler
from .models import PlanGraph, TaskBudget, TaskPhase
from .plan_guard import PlanGuard

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    completed: bool
    phase: TaskPhase
    message: str
    progress: float


class ForgeController:
    """Safety-first orchestration reference path for integration into FORGE."""

    def __init__(self, graph: PlanGraph, budget: TaskBudget | None = None):
        self.graph = graph
        self.scheduler = DagScheduler(graph)
        self.scheduler.validate()
        guard = PlanGuard().validate(graph)
        if not guard.passed:
            raise ValueError("plan guard failed: " + "; ".join(guard.errors))
        self.budget = BudgetController(budget or TaskBudget())
        self.audit = AuditLog()

    def next_wave(self):
        wave = self.scheduler.ready()
        for node in wave:
            self.scheduler.mark_running(node.node_id)
        return wave

    def mark_success(self, node_id: str) -> None:
        self.scheduler.mark_passed(node_id)
        # Record proven pattern into Memora
        try:
            from forge_upgrade.memora_client import memora_client
            memora_client.learn_from_outcome(
                agent_name="forge",
                task_name=node_id,
                status="success",
                actions_taken=f"node:{node_id}",
                domain="code_synthesis"
            )
        except Exception as exc:
            logger.warning("Memora success learning write failed for Forge node %s (%s)", node_id, type(exc).__name__)

    def mark_failure(self, node_id: str, error: str) -> None:
        self.scheduler.mark_failed(node_id, error)
        # Learn from failed node execution into Memora Experience memory
        try:
            from forge_upgrade.memora_client import memora_client
            memora_client.learn_from_outcome(
                agent_name="forge",
                task_name=node_id,
                status="failure",
                error_log=error,
                actions_taken=f"node:{node_id}",
                domain="code_synthesis"
            )
        except Exception as exc:
            logger.warning("Memora failure learning write failed for Forge node %s (%s)", node_id, type(exc).__name__)

    def get_self_upgrade_guidelines(self, node_id: str) -> str:
        """Retrieve self-upgraded rules from past failures to guide code generation for this node."""
        try:
            from forge_upgrade.memora_client import memora_client
            return memora_client.build_self_upgrade_context("forge", node_id, domain="code_synthesis")
        except Exception as exc:
            logger.warning("Memora guideline recall failed for Forge node %s (%s)", node_id, type(exc).__name__)
            return ""

    def finish(self) -> RunResult:
        if self.scheduler.failed():
            res = RunResult(
                False, TaskPhase.FAILED, "one or more nodes failed", self.scheduler.progress()
            )
        elif self.scheduler.complete():
            res = RunResult(True, TaskPhase.COMPLETE, "all nodes passed", 1.0)
        else:
            res = RunResult(
                False, TaskPhase.IMPLEMENT, "run still in progress", self.scheduler.progress()
            )

        # Record task lifecycle event to Memora
        try:
            from forge_upgrade.memora_client import memora_client
            memora_client.record_interaction(
                agent_name="forge",
                user_input=f"DAG Plan {self.graph.title if hasattr(self.graph, 'title') else 'Task'}",
                agent_output=f"Phase: {res.phase.value} | Progress: {res.progress * 100:.1f}% | Message: {res.message}",
                event_type="software_task"
            )
        except Exception as exc:
            logger.warning("Memora task receipt write failed for Forge (%s)", type(exc).__name__)

        return res
