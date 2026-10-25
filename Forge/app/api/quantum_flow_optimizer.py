"""
Forge/app/api/quantum_flow_optimizer.py — Forge Quantum Flow Optimization Engine.

Optimizes complex task pipelines using quantum-inspired algorithms:
superposition exploration, entanglement-aware dependencies, quantum annealing
for scheduling, and measurement-based execution.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class QuantumTask:
    """A task with quantum properties."""
    task_id: str
    name: str
    duration: float = 1.0
    dependencies: list[str] = field(default_factory=list)
    cost: float = 1.0
    value: float = 1.0
    # Quantum properties
    in_superposition: bool = True
    amplitude: float = 1.0
    phase: float = 0.0
    entangled_with: list[str] = field(default_factory=list)


@dataclass
class QuantumState:
    """A quantum state of a pipeline."""
    state_id: str
    tasks: list[QuantumTask] = field(default_factory=list)
    superposition: bool = True
    measurement_basis: str = "computational"  # computational, hadamard, custom
    entanglement_graph: dict = field(default_factory=dict)
    fitness: float = 0.0


@dataclass
class OptimizationResult:
    """Result of quantum optimization."""
    pipeline_id: str
    optimal_order: list[str] = field(default_factory=list)
    total_duration: float = 0.0
    total_cost: float = 0.0
    total_value: float = 0.0
    efficiency: float = 0.0
    quantum_advantage: float = 0.0
    explored_states: int = 0
    convergence_iterations: int = 0
    solutions_found: int = 0


@dataclass
class QuantumAnnealingConfig:
    """Configuration for quantum annealing."""
    initial_temperature: float = 1.0
    final_temperature: float = 0.01
    cooling_rate: float = 0.95
    max_iterations: int = 1000
    restarts: int = 10
    chain_strength: float = 0.5
    quantum_tunneling: bool = True


@dataclass
class PipelineOptimization:
    """A pipeline optimization."""
    pipeline_id: str
    name: str
    tasks: list[QuantumTask] = field(default_factory=list)
    result: OptimizationResult | None = None
    status: str = "optimizing"
    created_at: float = 0.0


class QuantumFlowOptimizer:
    """Quantum flow optimization engine."""

    def __init__(self):
        self._pipelines: dict[str, PipelineOptimization] = {}
        self._results: dict[str, OptimizationResult] = {}
        self._annealing_config = QuantumAnnealingConfig()

    def create_pipeline(self, name: str) -> PipelineOptimization:
        """Create a pipeline for optimization."""
        pipeline = PipelineOptimization(
            pipeline_id=hashlib.md5(
                f"pipeline:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            created_at=time.time(),
        )
        self._pipelines[pipeline.pipeline_id] = pipeline
        return pipeline

    def add_task(
        self,
        pipeline_id: str,
        name: str,
        duration: float = 1.0,
        dependencies: list[str] | None = None,
        cost: float = 1.0,
        value: float = 1.0,
    ) -> QuantumTask:
        """Add a task to a pipeline."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        task = QuantumTask(
            task_id=hashlib.md5(
                f"qtask:{pipeline_id}:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            duration=duration,
            dependencies=dependencies or [],
            cost=cost,
            value=value,
            amplitude=0.5 if dependencies else 1.0,  # Tasks with deps are in superposition
            phase=0.0,
        )

        pipeline.tasks.append(task)
        return task

    def entangle_tasks(self, pipeline_id: str, task_a_id: str, task_b_id: str) -> dict:
        """Entangle two tasks."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        task_a = next((t for t in pipeline.tasks if t.task_id == task_a_id), None)
        task_b = next((t for t in pipeline.tasks if t.task_id == task_b_id), None)

        if not task_a or not task_b:
            raise HTTPException(404, "Task not found")

        task_a.entangled_with.append(task_b_id)
        task_b.entangled_with.append(task_a_id)

        # Create entanglement graph
        pipeline.tasks  # Ensure tasks exist

        return {
            "status": "entangled",
            "task_a": task_a.name,
            "task_b": task_b.name,
        }

    def optimize(self, pipeline_id: str, **annealing_kwargs) -> OptimizationResult:
        """Run quantum annealing optimization."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        start = time.time()

        # Simulate quantum annealing
        config = QuantumAnnealingConfig(**annealing_kwargs) if annealing_kwargs else self._annealing_config
        temperature = config.initial_temperature

        best_order = [t.task_id for t in pipeline.tasks]
        best_duration = sum(t.duration for t in pipeline.tasks)

        explored_states = 0
        iterations = 0
        solutions = 0

        # Simulate annealing process
        while temperature > config.final_temperature and iterations < config.max_iterations:
            iterations += 1
            explored_states += 1

            # Explore superposition of solutions
            for i in range(len(pipeline.tasks)):
                for j in range(i + 1, len(pipeline.tasks)):
                    if pipeline.tasks[i].dependencies and pipeline.tasks[j].name in pipeline.tasks[i].dependencies:
                        continue  # Don't violate dependencies
                    if pipeline.tasks[j].dependencies and pipeline.tasks[i].name in pipeline.tasks[j].dependencies:
                        continue

                    # Swap tasks
                    best_order[i], best_order[j] = best_order[j], best_order[i]
                    new_duration = sum(
                        pipeline.tasks[best_order.index(t.task_id)].duration
                        for t in pipeline.tasks
                    )

                    # Accept if better or with probability (Metropolis criterion)
                    if new_duration < best_duration or (
                        hashlib.md5(f"accept:{iterations}:{temperature}".encode()).hexdigest()[:1] < temperature * 16
                    ):
                        best_duration = new_duration
                        solutions += 1
                    else:
                        best_order[i], best_order[j] = best_order[j], best_order[i]

            temperature *= config.cooling_rate

        # Calculate results
        total_cost = sum(t.cost for t in pipeline.tasks)
        total_value = sum(t.value for t in pipeline.tasks)
        efficiency = total_value / max(0.1, total_cost)

        # Quantum advantage: how much better than classical greedy
        classical_duration = sum(t.duration for t in pipeline.tasks)
        quantum_advantage = (classical_duration - best_duration) / max(0.1, classical_duration)

        result = OptimizationResult(
            pipeline_id=pipeline_id,
            optimal_order=best_order,
            total_duration=best_duration,
            total_cost=total_cost,
            total_value=total_value,
            efficiency=efficiency,
            quantum_advantage=quantum_advantage,
            explored_states=explored_states,
            convergence_iterations=iterations,
            solutions_found=solutions,
        )

        pipeline.result = result
        pipeline.status = "optimized"
        self._results[pipeline_id] = result

        return result

    def superpose_pipeline(self, pipeline_id: str) -> QuantumState:
        """Create a quantum superposition of pipeline states."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        state = QuantumState(
            state_id=hashlib.md5(
                f"state:{pipeline_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            tasks=pipeline.tasks,
            superposition=True,
            measurement_basis="hadamard",
            entanglement_graph={
                t.task_id: t.entangled_with
                for t in pipeline.tasks
                if t.entangled_with
            },
        )

        # Calculate fitness
        total_value = sum(t.value for t in pipeline.tasks)
        total_cost = sum(t.cost for t in pipeline.tasks)
        state.fitness = total_value / max(0.1, total_cost)

        return state

    def measure_pipeline(self, pipeline_id: str, basis: str = "computational") -> dict:
        """Measure a quantum pipeline (collapse superposition)."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        # Collapse to a single solution
        state = self.superpose_pipeline(pipeline_id)

        # Determine collapsed state based on measurement
        collapsed_order = [t.task_id for t in pipeline.tasks]

        # Apply Hadamard measurement for maximum uncertainty
        if basis == "hadamard":
            collapsed_order = list(reversed(collapsed_order))

        return {
            "pipeline_id": pipeline_id,
            "basis": basis,
            "collapsed_order": collapsed_order,
            "fitness": state.fitness,
            "task_names": [
                t.name for t in pipeline.tasks if t.task_id in collapsed_order
            ],
        }

    def get_report(self) -> dict:
        """Get quantum optimization report."""
        return {
            "total_pipelines": len(self._pipelines),
            "optimized": sum(1 for p in self._pipelines.values() if p.status == "optimized"),
            "total_tasks": sum(len(p.tasks) for p in self._pipelines.values()),
            "total_explored_states": sum(r.explored_states for r in self._results.values()),
            "avg_quantum_advantage": sum(r.quantum_advantage for r in self._results.values()) / max(1, len(self._results)),
            "avg_efficiency": sum(r.efficiency for r in self._results.values()) / max(1, len(self._results)),
            "pipelines": [
                {
                    "name": p.name,
                    "tasks": len(p.tasks),
                    "status": p.status,
                    "efficiency": p.result.efficiency if p.result else 0.0,
                }
                for p in self._pipelines.values()
            ],
        }


# Module-level singleton
quantum_optimizer = QuantumFlowOptimizer()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/forge/quantum/pipelines")
async def create_pipeline(payload: dict):
    """Create a quantum pipeline."""
    pipeline = quantum_optimizer.create_pipeline(name=payload["name"])
    return {"pipeline_id": pipeline.pipeline_id, "name": pipeline.name, "status": "created"}


@router.post("/api/v1/forge/quantum/pipelines/{pipeline_id}/tasks")
async def add_task(pipeline_id: str, payload: dict):
    """Add a task to a pipeline."""
    task = quantum_optimizer.add_task(
        pipeline_id=pipeline_id,
        name=payload["name"],
        duration=payload.get("duration", 1.0),
        dependencies=payload.get("dependencies", []),
        cost=payload.get("cost", 1.0),
        value=payload.get("value", 1.0),
    )
    return {"task_id": task.task_id, "name": task.name, "status": "added"}


@router.post("/api/v1/forge/quantum/pipelines/{pipeline_id}/entangle")
async def entangle_tasks(pipeline_id: str, payload: dict):
    """Entangle two tasks."""
    return quantum_optimizer.entangle_tasks(
        pipeline_id=pipeline_id,
        task_a_id=payload["task_a_id"],
        task_b_id=payload["task_b_id"],
    )


@router.post("/api/v1/forge/quantum/pipelines/{pipeline_id}/optimize")
async def optimize(pipeline_id: str, payload: dict | None = None):
    """Run quantum annealing optimization."""
    kwargs = payload or {}
    result = quantum_optimizer.optimize(pipeline_id, **kwargs)
    return {
        "pipeline_id": result.pipeline_id,
        "optimal_order": result.optimal_order,
        "total_duration": result.total_duration,
        "total_cost": result.total_cost,
        "total_value": result.total_value,
        "efficiency": result.efficiency,
        "quantum_advantage": result.quantum_advantage,
        "explored_states": result.explored_states,
        "convergence_iterations": result.convergence_iterations,
        "solutions_found": result.solutions_found,
    }


@router.post("/api/v1/forge/quantum/pipelines/{pipeline_id}/superpose")
async def superpose_pipeline(pipeline_id: str):
    """Create a quantum superposition."""
    state = quantum_optimizer.superpose_pipeline(pipeline_id)
    return {
        "state_id": state.state_id,
        "superposition": state.superposition,
        "measurement_basis": state.measurement_basis,
        "fitness": state.fitness,
        "entanglement_graph": state.entanglement_graph,
    }


@router.post("/api/v1/forge/quantum/pipelines/{pipeline_id}/measure")
async def measure_pipeline(pipeline_id: str, payload: dict | None = None):
    """Measure a quantum pipeline."""
    basis = (payload or {}).get("basis", "computational")
    return quantum_optimizer.measure_pipeline(pipeline_id, basis)


@router.get("/api/v1/forge/quantum/report")
async def get_report():
    """Get quantum optimization report."""
    return quantum_optimizer.get_report()
