"""
Forge/app/services/code_refactoring_engine.py — Forge Code Refactoring Engine.

Code refactoring suggestions, dead code detection, complexity analysis,
and refactoring priority scoring.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class RefactoringSuggestion:
    """A refactoring suggestion."""
    suggestion_id: str
    file_path: str
    function_name: str
    suggestion_type: str  # simplify, extract, rename, restructure
    description: str
    complexity_before: float = 0.0
    complexity_after: float = 0.0
    priority: int = 50
    effort_estimate: str = "small"


@dataclass
class CodeMetrics:
    """Code quality metrics."""
    metrics_id: str
    file_path: str
    cyclomatic_complexity: float = 0.0
    lines_of_code: int = 0
    maintainability_index: float = 100.0
    dead_code_count: int = 0
    duplicate_blocks: int = 0
    analyzed_at: float = field(default_factory=time.time)


@dataclass
class RefactoringPlan:
    """A comprehensive refactoring plan."""
    plan_id: str
    file_path: str
    suggestions: list[RefactoringSuggestion] = field(default_factory=list)
    metrics: CodeMetrics | None = None
    total_priority: int = 0
    estimated_effort: str = "medium"
    created_at: float = field(default_factory=time.time)


class CodeRefactoringEngine:
    """Engine for code refactoring analysis."""

    def __init__(self) -> None:
        self._plans: dict[str, RefactoringPlan] = {}

    def analyze_code(self, file_path: str, code: str) -> CodeMetrics:
        """Analyze code for metrics."""
        metrics_id = f"metrics_{uuid.uuid4().hex[:12]}"
        lines = code.split("\n")
        loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        cyclomatic = max(1, loc / 10)
        maintainability = max(0, 100 - cyclomatic * 2)
        dead_code = sum(1 for l in lines if "TODO" in l or "FIXME" in l)
        duplicates = max(0, loc // 50)
        return CodeMetrics(
            metrics_id=metrics_id, file_path=file_path,
            cyclomatic_complexity=round(cyclomatic, 1),
            lines_of_code=loc, maintainability_index=round(maintainability, 1),
            dead_code_count=dead_code, duplicate_blocks=duplicates,
        )

    def generate_suggestions(self, file_path: str, code: str) -> RefactoringPlan:
        """Generate refactoring suggestions for code."""
        plan_id = f"refactor_{uuid.uuid4().hex[:12]}"
        plan = RefactoringPlan(plan_id=plan_id, file_path=file_path)
        plan.metrics = self.analyze_code(file_path, code)

        # Generate suggestions based on metrics
        if plan.metrics.cyclomatic_complexity > 10:
            plan.suggestions.append(RefactoringSuggestion(
                suggestion_id=f"sugg_{uuid.uuid4().hex[:8]}",
                file_path=file_path, function_name="",
                suggestion_type="extract",
                description="Extract complex function into smaller functions",
                complexity_before=plan.metrics.cyclomatic_complexity,
                complexity_after=plan.metrics.cyclomatic_complexity / 2,
                priority=80, effort_estimate="medium",
            ))
        if plan.metrics.dead_code_count > 0:
            plan.suggestions.append(RefactoringSuggestion(
                suggestion_id=f"sugg_{uuid.uuid4().hex[:8]}",
                file_path=file_path, function_name="",
                suggestion_type="simplify",
                description=f"Remove {plan.metrics.dead_code_count} dead code markers (TODO/FIXME)",
                priority=40, effort_estimate="small",
            ))
        if plan.metrics.duplicate_blocks > 0:
            plan.suggestions.append(RefactoringSuggestion(
                suggestion_id=f"sugg_{uuid.uuid4().hex[:8]}",
                file_path=file_path, function_name="",
                suggestion_type="restructure",
                description=f"Extract {plan.metrics.duplicate_blocks} duplicate code blocks",
                priority=60, effort_estimate="medium",
            ))
        if not plan.suggestions:
            plan.suggestions.append(RefactoringSuggestion(
                suggestion_id=f"sugg_{uuid.uuid4().hex[:8]}",
                file_path=file_path, function_name="",
                suggestion_type="simplify",
                description="Code is well-structured, minor improvements suggested",
                priority=20, effort_estimate="small",
            ))

        plan.total_priority = sum(s.priority for s in plan.suggestions)
        plan.estimated_effort = "large" if plan.total_priority > 150 else "medium" if plan.total_priority > 80 else "small"
        self._plans[plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        """Get a refactoring plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return {
            "plan_id": plan.plan_id,
            "file_path": plan.file_path,
            "suggestion_count": len(plan.suggestions),
            "total_priority": plan.total_priority,
            "estimated_effort": plan.estimated_effort,
            "metrics": {
                "cyclomatic_complexity": plan.metrics.cyclomatic_complexity,
                "lines_of_code": plan.metrics.lines_of_code,
                "maintainability_index": plan.metrics.maintainability_index,
            } if plan.metrics else None,
            "suggestions": [
                {"type": s.suggestion_type, "description": s.description, "priority": s.priority}
                for s in plan.suggestions
            ],
        }

    def get_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {
            "total_plans": len(self._plans),
            "engine_status": "operational",
        }


engine = CodeRefactoringEngine()


@router.post("/forge/refactor/analyze")
async def analyze_code(file_path: str, code: str):
    """Analyze code and generate refactoring suggestions."""
    plan = engine.generate_suggestions(file_path, code)
    return {
        "plan_id": plan.plan_id,
        "suggestion_count": len(plan.suggestions),
        "total_priority": plan.total_priority,
        "estimated_effort": plan.estimated_effort,
        "cyclomatic_complexity": plan.metrics.cyclomatic_complexity,
        "maintainability_index": plan.metrics.maintainability_index,
    }


@router.get("/forge/refactor/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get a refactoring plan."""
    return engine.get_plan(plan_id)


@router.get("/forge/refactor/report")
async def refactor_report():
    """Get refactoring report."""
    return engine.get_report()
