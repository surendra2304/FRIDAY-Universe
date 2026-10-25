"""
Forge/app/services/code_complexity_quantifier.py — Forge Code Complexity Quantifier.

Cyclomatic complexity, cognitive complexity, code metric quantification,
and complexity trend analysis.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ComplexityMetrics:
    """Complexity metrics for code."""
    file_path: str
    cyclomatic: float = 0.0
    cognitive: float = 0.0
    lines_of_code: int = 0
    lines_of_comments: int = 0
    functions: int = 0
    classes: int = 0
    maintainability_index: float = 0.0
    halstead_volume: float = 0.0


@dataclass
class ComplexityTrend:
    """Complexity trend over time."""
    trend_id: str
    file_path: str
    data_points: list[dict] = field(default_factory=list)
    direction: str = "stable"  # increasing, decreasing, stable
    rate_of_change: float = 0.0


@dataclass
class ComplexityReport:
    """A comprehensive complexity report."""
    report_id: str
    project_path: str
    total_files: int = 0
    avg_cyclomatic: float = 0.0
    avg_cognitive: float = 0.0
    avg_maintainability: float = 0.0
    high_risk_files: list[str] = field(default_factory=list)
    complexity_grade: str = "B"
    generated_at: float = field(default_factory=time.time)


class CodeComplexityQuantifier:
    """Engine for code complexity quantification."""

    def __init__(self) -> None:
        self._metrics: dict[str, ComplexityMetrics] = {}
        self._trends: dict[str, ComplexityTrend] = {}
        self._reports: list[ComplexityReport] = []

    def analyze(self, file_path: str, code: str) -> ComplexityMetrics:
        """Analyze code complexity."""
        metrics = ComplexityMetrics(file_path=file_path)
        lines = code.split("\n")
        metrics.lines_of_code = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        metrics.lines_of_comments = len([l for l in lines if l.strip().startswith("#")])
        metrics.functions = len([l for l in lines if l.strip().startswith("def ")])
        metrics.classes = len([l for l in lines if l.strip().startswith("class ")])

        # Cyclomatic complexity
        decision_points = 0
        for line in lines:
            decision_points += line.count("if ") + line.count("for ") + line.count("while ")
            decision_points += line.count("elif ") + line.count("except ") + line.count("and ") + line.count("or ")
        metrics.cyclomatic = max(1, 1 + decision_points)

        # Cognitive complexity (simplified)
        metrics.cognitive = metrics.cyclomatic * 1.2

        # Maintainability index
        loc = max(1, metrics.lines_of_code)
        mi = max(0, 171 - 5.2 * math.log(metrics.cyclomatic + 1) - 0.23 * metrics.cyclomatic - 16.2 * math.log(loc))
        metrics.maintainability_index = max(0.0, mi * 1.71 / 171 * 100)

        # Halstead volume (simplified)
        tokens = code.split()
        unique_tokens = len(set(tokens))
        metrics.halstead_volume = len(tokens) * unique_tokens if tokens else 0

        self._metrics[file_path] = metrics
        return metrics

    def track_trend(self, file_path: str, cyclomatic: float,
                    cognitive: float = 0.0) -> ComplexityTrend:
        """Track complexity trend."""
        trend_id = f"trend_{uuid.uuid4().hex[:12]}"
        trend = ComplexityTrend(trend_id=trend_id, file_path=file_path)

        if file_path in self._trends:
            existing = self._trends[file_path]
            trend.data_points = existing.data_points + [
                {"cyclomatic": cyclomatic, "cognitive": cognitive, "time": time.time()}
            ]
            trend_data = trend.data_points
        else:
            trend.data_points = [{"cyclomatic": cyclomatic, "cognitive": cognitive, "time": time.time()}]
            trend_data = trend.data_points

        if len(trend_data) >= 2:
            recent = trend_data[-1]["cyclomatic"]
            older = trend_data[0]["cyclomatic"]
            if older > 0:
                trend.rate_of_change = (recent - older) / older
                trend.direction = (
                    "increasing" if trend.rate_of_change > 0.1
                    else "decreasing" if trend.rate_of_change < -0.1
                    else "stable"
                )

        self._trends[file_path] = trend
        return trend

    def generate_report(self, project_path: str) -> ComplexityReport:
        """Generate a complexity report."""
        report_id = f"cx_{uuid.uuid4().hex[:12]}"
        report = ComplexityReport(report_id=report_id, project_path=project_path)
        report.total_files = len(self._metrics)

        if self._metrics:
            avg_cyclo = sum(m.cyclomatic for m in self._metrics.values()) / len(self._metrics)
            avg_cog = sum(m.cognitive for m in self._metrics.values()) / len(self._metrics)
            avg_mi = sum(m.maintainability_index for m in self._metrics.values()) / len(self._metrics)
            report.avg_cyclomatic = round(avg_cyclo, 1)
            report.avg_cognitive = round(avg_cog, 1)
            report.avg_maintainability = round(avg_mi, 1)
            report.high_risk_files = [
                path for path, m in self._metrics.items() if m.cyclomatic > 15
            ]

            if report.avg_maintainability >= 80:
                report.complexity_grade = "A"
            elif report.avg_maintainability >= 65:
                report.complexity_grade = "B"
            elif report.avg_maintainability >= 50:
                report.complexity_grade = "C"
            elif report.avg_maintainability >= 35:
                report.complexity_grade = "D"
            else:
                report.complexity_grade = "F"

        self._reports.append(report)
        return report

    def get_metrics(self, file_path: str) -> dict[str, Any]:
        """Get complexity metrics."""
        metrics = self._metrics.get(file_path)
        if not metrics:
            raise HTTPException(status_code=404, detail="Metrics not found")
        return {
            "file_path": file_path,
            "cyclomatic": metrics.cyclomatic,
            "cognitive": metrics.cognitive,
            "lines_of_code": metrics.lines_of_code,
            "maintainability": metrics.maintainability_index,
        }

    def get_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {
            "total_files": len(self._metrics),
            "total_trends": len(self._trends),
            "total_reports": len(self._reports),
            "engine_status": "operational",
        }


engine = CodeComplexityQuantifier()


@router.post("/forge/complexity/analyze")
async def analyze(file_path: str, code: str):
    """Analyze code complexity."""
    metrics = engine.analyze(file_path, code)
    engine.track_trend(file_path, metrics.cyclomatic, metrics.cognitive)
    return {
        "file_path": file_path,
        "cyclomatic": metrics.cyclomatic,
        "cognitive": metrics.cognitive,
        "maintainability": metrics.maintainability_index,
    }


@router.post("/forge/complexity/report")
async def generate_report(project_path: str):
    """Generate complexity report."""
    report = engine.generate_report(project_path)
    return {
        "report_id": report.report_id,
        "total_files": report.total_files,
        "avg_cyclomatic": report.avg_cyclomatic,
        "avg_maintainability": report.avg_maintainability,
        "grade": report.complexity_grade,
        "high_risk_files": report.high_risk_files[:3],
    }


@router.get("/forge/complexity/metrics/{file_path}")
async def get_metrics(file_path: str):
    """Get complexity metrics."""
    return engine.get_metrics(file_path)


@router.get("/forge/complexity/report")
async def complexity_report():
    """Get complexity quantifier report."""
    return engine.get_report()
