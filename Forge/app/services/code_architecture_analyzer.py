"""
Forge/app/services/code_architecture_analyzer.py — Forge Code Architecture Analyzer.

Architecture pattern detection, dependency graph analysis,
design quality scoring, and architectural compliance checking.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ArchComponent:
    """An architectural component."""
    component_id: str
    name: str
    type: str = "module"  # module, service, controller, model, middleware, repository
    dependencies: list[str] = field(default_factory=list)
    cycle_count: int = 0
    complexity: float = 0.0


@dataclass
class ArchPattern:
    """An architectural pattern detected."""
    pattern_id: str
    pattern_name: str
    description: str = ""
    compliance: float = 0.0
    violations: list[str] = field(default_factory=list)


@dataclass
class ArchScore:
    """Architectural quality score."""
    score_id: str
    project_path: str
    total_components: int = 0
    cohesion_score: float = 0.0
    coupling_score: float = 0.0
    layering_score: float = 0.0
    overall_score: float = 0.0
    grade: str = "B"  # A, B, C, D, F


class CodeArchitectureAnalyzer:
    """Engine for code architecture analysis."""

    def __init__(self) -> None:
        self._components: dict[str, ArchComponent] = {}
        self._patterns: list[ArchPattern] = []
        self._scores: list[ArchScore] = []

    def add_component(self, name: str, component_type: str = "module",
                      dependencies: list[str] | None = None,
                      complexity: float = 0.5) -> ArchComponent:
        """Add an architectural component."""
        component_id = f"comp_{uuid.uuid4().hex[:12]}"
        component = ArchComponent(
            component_id=component_id, name=name, type=component_type,
            dependencies=dependencies or [], complexity=complexity,
        )
        self._components[component_id] = component
        return component

    def detect_patterns(self, project_path: str) -> list[ArchPattern]:
        """Detect architectural patterns."""
        patterns = []
        # MVC pattern
        mvc = ArchPattern(
            pattern_id=f"pat_{uuid.uuid4().hex[:8]}",
            pattern_name="MVC",
            description="Model-View-Controller separation",
        )
        types = [c.type for c in self._components.values()]
        if "controller" in types and "model" in types:
            mvc.compliance = 0.7
        patterns.append(mvc)

        # Layered architecture
        layered = ArchPattern(
            pattern_id=f"pat_{uuid.uuid4().hex[:8]}",
            pattern_name="Layered",
            description="Presentation, business, data layers",
        )
        if "middleware" in types and "repository" in types:
            layered.compliance = 0.6
        patterns.append(layered)

        # Dependency injection
        di = ArchPattern(
            pattern_id=f"pat_{uuid.uuid4().hex[:8]}",
            pattern_name="Dependency Injection",
            description="Inversion of control",
        )
        total_deps = sum(len(c.dependencies) for c in self._components.values())
        if total_deps > 0:
            avg_deps = total_deps / len(self._components)
            di.compliance = max(0.0, 1.0 - avg_deps / 10.0)
        patterns.append(di)

        self._patterns = patterns
        return patterns

    def calculate_score(self, project_path: str) -> ArchScore:
        """Calculate architectural quality score."""
        score_id = f"score_{uuid.uuid4().hex[:12]}"
        score = ArchScore(score_id=score_id, project_path=project_path)
        score.total_components = len(self._components)

        total_deps = sum(len(c.dependencies) for c in self._components.values())
        max_deps = score.total_components * (score.total_components - 1)
        score.coupling_score = 1.0 - (total_deps / max(1, max_deps))

        score.cohesion_score = sum(
            1.0 if c.type == "controller" else 0.5 for c in self._components.values()
        ) / max(1, score.total_components)

        score.layering_score = 0.8 if len(set(c.type for c in self._components.values())) > 3 else 0.4
        score.overall_score = (score.cohesion_score * 0.3 + score.coupling_score * 0.4 +
                               score.layering_score * 0.3) * 100

        if score.overall_score >= 80:
            score.grade = "A"
        elif score.overall_score >= 70:
            score.grade = "B"
        elif score.overall_score >= 60:
            score.grade = "C"
        elif score.overall_score >= 40:
            score.grade = "D"
        else:
            score.grade = "F"

        self._scores.append(score)
        return score

    def get_components(self, component_type: str | None = None) -> list[dict[str, Any]]:
        """Get architectural components."""
        components = list(self._components.values())
        if component_type:
            components = [c for c in components if c.type == component_type]
        return [
            {"name": c.name, "type": c.type, "dependency_count": len(c.dependencies),
             "complexity": c.complexity}
            for c in components
        ]

    def get_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {
            "total_components": len(self._components),
            "total_patterns": len(self._patterns),
            "total_scores": len(self._scores),
            "engine_status": "operational",
        }


engine = CodeArchitectureAnalyzer()


@router.post("/forge/architecture/components")
async def add_component(name: str, component_type: str = "module",
                        dependencies: list[str] | None = None, complexity: float = 0.5):
    """Add an architectural component."""
    component = engine.add_component(name, component_type, dependencies, complexity)
    return {"component_id": component.component_id, "name": component.name, "type": component.type}


@router.post("/forge/architecture/detect")
async def detect_patterns(project_path: str):
    """Detect architectural patterns."""
    patterns = engine.detect_patterns(project_path)
    return {
        "project_path": project_path,
        "pattern_count": len(patterns),
        "patterns": [
            {"name": p.pattern_name, "compliance": p.compliance}
            for p in patterns
        ],
    }


@router.post("/forge/architecture/score")
async def calculate_score(project_path: str):
    """Calculate architectural quality score."""
    score = engine.calculate_score(project_path)
    return {
        "project_path": project_path,
        "overall_score": score.overall_score,
        "grade": score.grade,
        "cohesion": score.cohesion_score,
        "coupling": score.coupling_score,
        "layering": score.layering_score,
    }


@router.get("/forge/architecture/components")
async def get_components(component_type: str | None = None):
    """Get architectural components."""
    return {"components": engine.get_components(component_type)}


@router.get("/forge/architecture/report")
async def architecture_report():
    """Get architecture analyzer report."""
    return engine.get_report()
