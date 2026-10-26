"""
Forge — Real Engines API Router

Wires real_code_analysis, real_optimization_advanced, and real_robotics into the Forge API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

real_engines_router = APIRouter(tags=["Real Engines"], prefix="/api/v1/real-engines")


def _import_mods():
    mods: dict[str, Any] = {}
    try:
        from app.agents.real_code_analysis import (
            CodeMetrics, ComplexityAnalyzer, PatternDetector,
            SecurityAnalyzer, PerformanceAnalyzer, CodeReviewer,
        )
        mods["code_analysis"] = {
            "metrics": CodeMetrics, "complexity": ComplexityAnalyzer,
            "patterns": PatternDetector, "security": SecurityAnalyzer,
            "performance": PerformanceAnalyzer, "reviewer": CodeReviewer,
        }
    except ImportError:
        try:
            from Forge.app.agents.real_code_analysis import (
                CodeMetrics, ComplexityAnalyzer, PatternDetector,
                SecurityAnalyzer, PerformanceAnalyzer, CodeReviewer,
            )
            mods["code_analysis"] = {
                "metrics": CodeMetrics, "complexity": ComplexityAnalyzer,
                "patterns": PatternDetector, "security": SecurityAnalyzer,
                "performance": PerformanceAnalyzer, "reviewer": CodeReviewer,
            }
        except Exception:
            pass

    try:
        from app.agents.real_optimization_advanced import (
            OptimizationEngine, CacheOptimizer, MemoryOptimizer,
            ParallelismOptimizer, ProfileAnalyzer, BenchmarkRunner,
        )
        mods["optimization"] = {
            "engine": OptimizationEngine, "cache": CacheOptimizer,
            "memory": MemoryOptimizer, "parallelism": ParallelismOptimizer,
            "profiler": ProfileAnalyzer, "benchmark": BenchmarkRunner,
        }
    except ImportError:
        try:
            from Forge.app.agents.real_optimization_advanced import (
                OptimizationEngine, CacheOptimizer, MemoryOptimizer,
                ParallelismOptimizer, ProfileAnalyzer, BenchmarkRunner,
            )
            mods["optimization"] = {
                "engine": OptimizationEngine, "cache": CacheOptimizer,
                "memory": MemoryOptimizer, "parallelism": ParallelismOptimizer,
                "profiler": ProfileAnalyzer, "benchmark": BenchmarkRunner,
            }
        except Exception:
            pass

    try:
        from app.agents.real_robotics import (
            RobotArm, JointController, PathPlanner, CollisionDetector,
            GraspPlanner, TrajectoryOptimizer, SimulationEngine,
        )
        mods["robotics"] = {
            "arm": RobotArm, "joint": JointController, "path": PathPlanner,
            "collision": CollisionDetector, "grasp": GraspPlanner,
            "trajectory": TrajectoryOptimizer, "simulation": SimulationEngine,
        }
    except ImportError:
        try:
            from Forge.app.agents.real_robotics import (
                RobotArm, JointController, PathPlanner, CollisionDetector,
                GraspPlanner, TrajectoryOptimizer, SimulationEngine,
            )
            mods["robotics"] = {
                "arm": RobotArm, "joint": JointController, "path": PathPlanner,
                "collision": CollisionDetector, "grasp": GraspPlanner,
                "trajectory": TrajectoryOptimizer, "simulation": SimulationEngine,
            }
        except Exception:
            pass

    return mods


_MODS: dict[str, Any] = {}


def get_mods():
    if not _MODS:
        _MODS.update(_import_mods())
    return _MODS


@real_engines_router.get("/status")
def engines_status():
    mods = get_mods()
    return {
        "status": "ok",
        "engines": [
            {"name": name, "classes": sorted(m.keys()), "loaded": True}
            for name, m in mods.items()
        ],
    }


@real_engines_router.post("/code-analysis")
def code_analysis(body: dict):
    mods = get_mods()
    if "code_analysis" not in mods:
        raise HTTPException(503, "Code analysis module not available")

    code = body.get("code", "")
    metrics = mods["code_analysis"]["metrics"]()
    result = metrics.analyze(code) if hasattr(metrics, "analyze") else {"lines": len(code.splitlines())}
    return {"status": "ok", "result": result}


@real_engines_router.post("/code-review")
def code_review(body: dict):
    mods = get_mods()
    if "code_analysis" not in mods:
        raise HTTPException(503, "Code analysis module not available")

    code = body.get("code", "")
    reviewer = mods["code_analysis"]["reviewer"]()
    result = reviewer.review(code) if hasattr(reviewer, "review") else {"issues": []}
    return {"status": "ok", "result": result}


@real_engines_router.post("/optimize")
def optimize(body: dict):
    mods = get_mods()
    if "optimization" not in mods:
        raise HTTPException(503, "Optimization module not available")

    code = body.get("code", "")
    engine = mods["optimization"]["engine"]()
    result = engine.optimize(code) if hasattr(engine, "optimize") else {"status": "ok"}
    return {"status": "ok", "result": result}


@real_engines_router.post("/robotics/simulate")
def robotics_simulate(body: dict):
    mods = get_mods()
    if "robotics" not in mods:
        raise HTTPException(503, "Robotics module not available")

    sim = mods["robotics"]["simulation"]()
    result = sim.run(body.get("config", {})) if hasattr(sim, "run") else {"status": "ok"}
    return {"status": "ok", "result": result}


@real_engines_router.post("/robotics/path")
def robotics_path(body: dict):
    mods = get_mods()
    if "robotics" not in mods:
        raise HTTPException(503, "Robotics module not available")

    start = body.get("start", [0, 0, 0])
    end = body.get("end", [1, 1, 1])
    planner = mods["robotics"]["path"]()
    result = planner.plan(start, end) if hasattr(planner, "plan") else {"path": []}
    return {"status": "ok", "result": result}
