"""
Forge/app/services/code_merge_conflict_resolver.py — Forge Code Merge Conflict Resolver.

Automated merge conflict detection, conflict resolution strategies,
branch divergence analysis, and merge safety scoring.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ConflictHunk:
    """A conflicting hunk in a merge."""
    hunk_id: str
    file_path: str
    line_start: int = 0
    line_end: int = 0
    our_content: str = ""
    their_content: str = ""
    base_content: str = ""
    resolution: str = "unresolved"  # unresolved, ours, theirs, merged


@dataclass
class MergeConflict:
    """A merge conflict."""
    conflict_id: str
    file_path: str
    branch_a: str
    branch_b: str
    hunks: list[ConflictHunk] = field(default_factory=list)
    severity: str = "low"  # low, medium, high, critical
    resolved: bool = False


@dataclass
class MergeSafetyReport:
    """Merge safety assessment."""
    report_id: str
    merge_id: str
    total_conflicts: int = 0
    total_files: int = 0
    risk_score: float = 0.0
    risk_level: str = "low"
    recommendations: list[str] = field(default_factory=list)


class CodeMergeConflictResolver:
    """Engine for automated merge conflict resolution."""

    def __init__(self) -> None:
        self._conflicts: dict[str, MergeConflict] = {}
        self._reports: list[MergeSafetyReport] = []

    def detect_conflict(self, file_path: str, branch_a: str, branch_b: str,
                        hunks: list[dict]) -> MergeConflict:
        """Detect a merge conflict."""
        conflict_id = f"cf_{uuid.uuid4().hex[:12]}"
        conflict = MergeConflict(
            conflict_id=conflict_id, file_path=file_path,
            branch_a=branch_a, branch_b=branch_b,
        )

        for hunk in hunks:
            ch = ConflictHunk(
                hunk_id=f"h_{uuid.uuid4().hex[:8]}",
                file_path=file_path,
                line_start=hunk.get("line_start", 0),
                line_end=hunk.get("line_end", 0),
                our_content=hunk.get("our_content", ""),
                their_content=hunk.get("their_content", ""),
                base_content=hunk.get("base_content", ""),
            )
            conflict.hunks.append(ch)

        # Determine severity
        if len(conflict.hunks) > 5:
            conflict.severity = "critical"
        elif len(conflict.hunks) > 3:
            conflict.severity = "high"
        elif len(conflict.hunks) > 1:
            conflict.severity = "medium"
        else:
            conflict.severity = "low"

        self._conflicts[conflict_id] = conflict
        return conflict

    def resolve_hunk(self, conflict_id: str, hunk_id: str,
                     resolution: str = "merged",
                     merged_content: str = "") -> ConflictHunk:
        """Resolve a conflict hunk."""
        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        for hunk in conflict.hunks:
            if hunk.hunk_id == hunk_id:
                hunk.resolution = resolution
                if resolution == "merged":
                    hunk.our_content = merged_content or hunk.our_content
                conflict.resolved = all(h.resolution != "unresolved" for h in conflict.hunks)
                return hunk

        raise HTTPException(status_code=404, detail="Hunk not found")

    def assess_merge_safety(self, merge_id: str) -> MergeSafetyReport:
        """Assess merge safety."""
        report_id = f"ms_{uuid.uuid4().hex[:12]}"
        report = MergeSafetyReport(report_id=report_id, merge_id=merge_id)

        conflicts = list(self._conflicts.values())
        report.total_conflicts = len(conflicts)
        report.total_files = len(set(c.file_path for c in conflicts))

        # Calculate risk score
        risk = 0.0
        for conflict in conflicts:
            if conflict.severity == "critical":
                risk += 30.0
            elif conflict.severity == "high":
                risk += 20.0
            elif conflict.severity == "medium":
                risk += 10.0
            else:
                risk += 5.0
        report.risk_score = min(100.0, risk)

        if report.risk_score > 70:
            report.risk_level = "critical"
        elif report.risk_score > 40:
            report.risk_level = "high"
        elif report.risk_score > 20:
            report.risk_level = "medium"
        else:
            report.risk_level = "low"

        report.recommendations = [
            "Review all critical conflicts manually",
            "Add merge tests to CI pipeline",
            "Consider feature flags for complex changes",
            "Schedule code review for high-risk files",
        ] if report.risk_score > 40 else [
            "Merge appears safe",
            "Run tests after merge",
        ]

        self._reports.append(report)
        return report

    def get_conflicts(self, severity: str | None = None) -> list[dict[str, Any]]:
        """Get merge conflicts."""
        conflicts = list(self._conflicts.values())
        if severity:
            conflicts = [c for c in conflicts if c.severity == severity]
        return [
            {"file_path": c.file_path, "branch_a": c.branch_a,
             "branch_b": c.branch_b, "hunk_count": len(c.hunks),
             "severity": c.severity, "resolved": c.resolved}
            for c in conflicts
        ]

    def get_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {
            "total_conflicts": len(self._conflicts),
            "resolved_conflicts": sum(1 for c in self._conflicts.values() if c.resolved),
            "total_reports": len(self._reports),
            "engine_status": "operational",
        }


engine = CodeMergeConflictResolver()


@router.post("/forge/merge/conflicts")
async def detect_conflict(file_path: str, branch_a: str, branch_b: str, hunks: list[dict]):
    """Detect a merge conflict."""
    conflict = engine.detect_conflict(file_path, branch_a, branch_b, hunks)
    return {
        "conflict_id": conflict.conflict_id,
        "file_path": file_path,
        "hunk_count": len(conflict.hunks),
        "severity": conflict.severity,
    }


@router.post("/forge/merge/resolve")
async def resolve_hunk(conflict_id: str, hunk_id: str, resolution: str = "merged",
                       merged_content: str = ""):
    """Resolve a conflict hunk."""
    hunk = engine.resolve_hunk(conflict_id, hunk_id, resolution, merged_content)
    return {"hunk_id": hunk.hunk_id, "resolution": hunk.resolution}


@router.post("/forge/merge/safety")
async def assess_merge_safety(merge_id: str):
    """Assess merge safety."""
    report = engine.assess_merge_safety(merge_id)
    return {
        "report_id": report.report_id,
        "risk_score": report.risk_score,
        "risk_level": report.risk_level,
        "recommendations": report.recommendations,
    }


@router.get("/forge/merge/conflicts")
async def get_conflicts(severity: str | None = None):
    """Get merge conflicts."""
    return {"conflicts": engine.get_conflicts(severity)}


@router.get("/forge/merge/report")
async def merge_report():
    """Get merge conflict resolver report."""
    return engine.get_report()
