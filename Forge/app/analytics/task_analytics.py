"""
Task History and Performance Analytics Subsystem for Project FORGE.
Aggregates task metrics, project category durations, success rates, and failure distributions.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.memory.db import DatabaseManager, db_manager
from app.memory.models import TaskEntity, TaskState
from app.memory.state_store import StateStore

logger = get_logger("analytics.task_analytics")


class AnalyticsSummary(BaseModel):
    """Overall aggregate metrics for FORGE task execution."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_tasks: int = 0
    success_rate_percentage: float = 0.0
    average_duration_seconds: float = 0.0
    total_budget_spent_usd: float = 0.0


class TypePerformance(BaseModel):
    """Performance metrics segmented by project category."""

    project_type: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    success_rate_percentage: float = 0.0
    average_duration_seconds: float = 0.0
    average_budget_usd: float = 0.0


class FailureAnalysis(BaseModel):
    """Distribution of failure classes and root causes."""

    total_failures: int = 0
    failure_types: dict[str, int] = Field(default_factory=dict)
    recent_failure_reasons: list[dict[str, Any]] = Field(default_factory=list)


class TaskAnalyticsService:
    """Queries task store and generates real-time analytics for FRIDAY management."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or db_manager
        self.store = StateStore(self.db)

    def _infer_project_type(self, goal: str) -> str:
        """Categorize task goal into project type."""
        g = goal.lower()
        if any(
            k in g
            for k in ["website", "landing", "html", "portfolio", "css", "frontend", "dashboard"]
        ):
            return "website"
        elif any(
            k in g for k in ["fastapi", "rest api", "backend", "database", "sqlite", "service"]
        ):
            return "api"
        elif any(k in g for k in ["cli", "command-line", "terminal", "todo"]):
            return "cli"
        elif any(k in g for k in ["full-stack", "fullstack"]):
            return "fullstack"
        else:
            return "script"

    # Every state that is *not* a terminal one counts as active. Deriving active
    # as total - completed - failed used to silently book CANCELLED, BLOCKED and
    # PENDING tasks as "active".
    NON_ACTIVE_STATES = frozenset(
        {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.BLOCKED}
    )

    async def get_summary(self) -> AnalyticsSummary:
        """Compute high-level system summary."""
        tasks = await self.store.list_tasks(limit=1000)
        if not tasks:
            return AnalyticsSummary()

        total = len(tasks)
        completed = sum(1 for t in tasks if t.state == TaskState.COMPLETED)
        failed = sum(1 for t in tasks if t.state == TaskState.FAILED)
        active = sum(1 for t in tasks if t.state not in self.NON_ACTIVE_STATES)

        durations = []
        for t in tasks:
            if t.state in [TaskState.COMPLETED, TaskState.FAILED] and t.created_at and t.updated_at:
                durations.append((t.updated_at - t.created_at).total_seconds())

        avg_dur = sum(durations) / len(durations) if durations else 0.0
        budget_spent = sum(t.budget_consumed for t in tasks)
        success_pct = (completed / total * 100.0) if total > 0 else 0.0

        return AnalyticsSummary(
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            active_tasks=active,
            success_rate_percentage=round(success_pct, 1),
            average_duration_seconds=round(avg_dur, 2),
            total_budget_spent_usd=round(budget_spent, 4),
        )

    async def get_type_performance(self) -> list[TypePerformance]:
        """Compute performance breakdowns across project types."""
        tasks = await self.store.list_tasks(limit=1000)
        types_map: dict[str, list[TaskEntity]] = {
            "website": [],
            "cli": [],
            "api": [],
            "script": [],
            "fullstack": [],
        }

        for t in tasks:
            ptype = self._infer_project_type(t.goal)
            types_map.setdefault(ptype, []).append(t)

        results = []
        for ptype, ptasks in types_map.items():
            if not ptasks:
                continue
            total = len(ptasks)
            completed = sum(1 for t in ptasks if t.state == TaskState.COMPLETED)
            failed = sum(1 for t in ptasks if t.state == TaskState.FAILED)
            success_pct = (completed / total * 100.0) if total > 0 else 0.0

            durations = [
                (t.updated_at - t.created_at).total_seconds()
                for t in ptasks
                if t.created_at and t.updated_at
            ]
            avg_dur = sum(durations) / len(durations) if durations else 0.0
            avg_budget = sum(t.budget_consumed for t in ptasks) / total if total > 0 else 0.0

            results.append(
                TypePerformance(
                    project_type=ptype,
                    total_tasks=total,
                    completed_tasks=completed,
                    failed_tasks=failed,
                    success_rate_percentage=round(success_pct, 1),
                    average_duration_seconds=round(avg_dur, 2),
                    average_budget_usd=round(avg_budget, 4),
                )
            )

        return results

    async def get_failure_analysis(self) -> FailureAnalysis:
        """Analyze failure categories and root causes."""
        tasks = await self.store.list_tasks(limit=1000)
        failed_tasks = [t for t in tasks if t.state == TaskState.FAILED]

        distribution: dict[str, int] = {
            "fallback_stub": 0,
            "verification_failure": 0,
            "runtime_error": 0,
            "security_violation": 0,
            "other": 0,
        }
        recent_reasons = []

        for t in failed_tasks:
            msg = t.error_message or "Unknown failure"
            msg_lower = msg.lower()

            if "fallback" in msg_lower or "stub" in msg_lower:
                distribution["fallback_stub"] += 1
            elif "verification" in msg_lower or "check" in msg_lower:
                distribution["verification_failure"] += 1
            elif "runtime" in msg_lower or "crash" in msg_lower:
                distribution["runtime_error"] += 1
            elif "security" in msg_lower:
                distribution["security_violation"] += 1
            else:
                distribution["other"] += 1

            recent_reasons.append(
                {
                    "task_id": t.id,
                    "goal": t.goal,
                    "error": msg,
                    "failed_at": t.updated_at.isoformat() if t.updated_at else None,
                }
            )

        return FailureAnalysis(
            total_failures=len(failed_tasks),
            failure_types=distribution,
            recent_failure_reasons=recent_reasons[:20],
        )


task_analytics_service = TaskAnalyticsService()
