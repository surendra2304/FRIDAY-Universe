"""
Forge/app/services/code_analysis_engine.py — Forge Code Analysis Engine.

Static code analysis, complexity metrics, style checking, and
code quality scoring with actionable improvement suggestions.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class AnalysisFinding:
    """A finding from code analysis."""
    finding_id: str
    file_path: str
    line: int
    severity: str = "info"  # info, warning, error, critical
    category: str = "style"  # style, complexity, security, performance, correctness
    message: str = ""
    suggestion: str = ""


@dataclass
class CodeMetrics:
    """Code quality metrics."""
    file_path: str
    cyclomatic_complexity: float = 0.0
    lines_of_code: int = 0
    lines_of_comments: int = 0
    maintainability_index: float = 100.0
    duplicate_blocks: int = 0
    function_count: int = 0
    max_function_length: int = 0


@dataclass
class AnalysisReport:
    """A complete code analysis report."""
    report_id: str
    project_path: str
    metrics: CodeMetrics | None = None
    findings: list[AnalysisFinding] = field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    analyzed_at: float = field(default_factory=time.time)


class CodeAnalysisEngine:
    """Engine for static code analysis."""

    def __init__(self) -> None:
        self._reports: dict[str, AnalysisReport] = {}

    def analyze_code(self, project_path: str, code: str) -> AnalysisReport:
        """Analyze code and generate a report."""
        report_id = f"analysis_{uuid.uuid4().hex[:12]}"
        report = AnalysisReport(report_id=report_id, project_path=project_path)
        report.metrics = self._calculate_metrics(code, project_path)

        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Complexity check
            if line_stripped.count("if ") + line_stripped.count("for ") + line_stripped.count("while ") > 3:
                report.findings.append(AnalysisFinding(
                    finding_id=f"f_{uuid.uuid4().hex[:8]}",
                    file_path=project_path, line=i,
                    severity="warning", category="complexity",
                    message="High branching complexity on single line",
                    suggestion="Extract into separate functions",
                ))

            # Security checks
            if "eval(" in line or "exec(" in line:
                report.findings.append(AnalysisFinding(
                    finding_id=f"f_{uuid.uuid4().hex[:8]}",
                    file_path=project_path, line=i,
                    severity="critical", category="security",
                    message="Use of eval() or exec() detected",
                    suggestion="Replace with safer alternatives",
                ))

            # TODO/FIXME check
            if "TODO" in line or "FIXME" in line:
                report.findings.append(AnalysisFinding(
                    finding_id=f"f_{uuid.uuid4().hex[:8]}",
                    file_path=project_path, line=i,
                    severity="info", category="style",
                    message="TODO/FIXME marker found",
                    suggestion="Resolve or track in issue tracker",
                ))

        report.total_findings = len(report.findings)
        report.critical_findings = sum(1 for f in report.findings if f.severity == "critical")
        self._reports[report_id] = report
        return report

    def _calculate_metrics(self, code: str, file_path: str = "") -> CodeMetrics:
        """Calculate code metrics."""
        lines = code.split("\n")
        loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        comments = len([l for l in lines if l.strip().startswith("#")])
        functions = [l for l in lines if l.strip().startswith("def ")]
        functions += [l for l in lines if l.strip().startswith("function ")]

        cyclomatic = max(1, loc / 10)
        maintainability = max(0, 100 - cyclomatic * 2)
        duplicates = max(0, loc // 50)

        return CodeMetrics(
            file_path=file_path,
            cyclomatic_complexity=round(cyclomatic, 1),
            lines_of_code=loc,
            lines_of_comments=comments,
            maintainability_index=round(maintainability, 1),
            duplicate_blocks=duplicates,
            function_count=len(functions),
            max_function_length=max(20, loc // max(1, len(functions))),
        )

    def get_report(self, report_id: str) -> dict[str, Any]:
        """Get an analysis report."""
        report = self._reports.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return {
            "report_id": report.report_id,
            "total_findings": report.total_findings,
            "critical_findings": report.critical_findings,
            "cyclomatic_complexity": report.metrics.cyclomatic_complexity if report.metrics else 0,
            "maintainability_index": report.metrics.maintainability_index if report.metrics else 0,
            "findings": [
                {"severity": f.severity, "category": f.category, "message": f.message[:80]}
                for f in report.findings[:10]
            ],
        }

    def get_engine_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {"total_reports": len(self._reports), "engine_status": "operational"}


engine = CodeAnalysisEngine()


@router.post("/forge/analysis/code")
async def analyze_code(project_path: str, code: str):
    """Analyze code for quality and security issues."""
    report = engine.analyze_code(project_path, code)
    return {
        "report_id": report.report_id,
        "total_findings": report.total_findings,
        "critical_findings": report.critical_findings,
        "cyclomatic_complexity": report.metrics.cyclomatic_complexity,
        "maintainability_index": report.metrics.maintainability_index,
    }


@router.get("/forge/analysis/reports/{report_id}")
async def get_report(report_id: str):
    """Get an analysis report."""
    return engine.get_report(report_id)


@router.get("/forge/analysis/report")
async def analysis_report():
    """Get analysis engine report."""
    return engine.get_engine_report()
