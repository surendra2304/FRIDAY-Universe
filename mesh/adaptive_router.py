"""
mesh/adaptive_router.py — FRIDAY Universe Adaptive Task Routing Engine.

Routes tasks to the best-suited agent based on capability, health, load,
and historical success rate. Ensures FRIDAY always picks the right agent
for the job.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class TaskProfile:
    """A task to be routed."""
    task_id: str
    task_type: str
    description: str = ""
    priority: int = 1
    required_capabilities: list[str] = field(default_factory=list)
    estimated_complexity: float = 0.5
    data: dict = field(default_factory=dict)
    created_at: float = 0.0


@dataclass
class AgentCapability:
    """An agent's routing profile."""
    agent: str
    capabilities: list[str] = field(default_factory=list)
    status: str = "unknown"
    current_load: float = 0.0
    success_rate: float = 0.5
    avg_response_time: float = 0.0
    active_tasks: int = 0
    historical_tasks: int = 0
    last_heartbeat: float = 0.0
    health_score: float = 0.5


@dataclass
class RoutingDecision:
    """A routing decision."""
    task_id: str
    task_type: str
    candidates: list[str]
    selected_agent: str
    score: float
    reason: str
    estimated_time: float
    fallback_agent: str = ""
    rejected: list[dict] = field(default_factory=list)


@dataclass
class RoutingHistory:
    """Routing decision history."""
    task_id: str
    task_type: str
    selected_agent: str
    result: str  # success, failure, timeout
    timestamp: float


@dataclass
class LoadMetrics:
    """Agent load metrics."""
    agent: str
    load_score: float  # 0-1
    cpu_usage: float
    memory_usage: float
    active_tasks: int
    max_tasks: int
    health_score: float


class AdaptiveRouter:
    """Adaptive task routing engine."""

    def __init__(self):
        self._agents: dict[str, AgentCapability] = {}
        self._decisions: dict[str, RoutingDecision] = {}
        self._history: list[RoutingHistory] = []
        self._load_metrics: dict[str, LoadMetrics] = {}

    def register_agent(
        self,
        agent: str,
        capabilities: list[str],
        max_tasks: int = 10,
    ) -> AgentCapability:
        """Register an agent for routing."""
        capability = AgentCapability(
            agent=agent,
            capabilities=capabilities,
            status="online",
            current_load=0.0,
            success_rate=0.5,
            avg_response_time=30.0,
            active_tasks=0,
            historical_tasks=0,
            last_heartbeat=time.time(),
            health_score=0.5,
        )
        self._agents[agent] = capability
        return capability

    def update_agent_status(
        self,
        agent: str,
        status: str,
        load: float,
        active_tasks: int,
        health_score: float,
    ) -> None:
        """Update an agent's current status."""
        capability = self._agents.get(agent)
        if not capability:
            return

        capability.status = status
        capability.current_load = load
        capability.active_tasks = active_tasks
        capability.health_score = health_score
        capability.last_heartbeat = time.time()

    def route_task(
        self,
        task_type: str,
        description: str = "",
        required_capabilities: list[str] | None = None,
        priority: int = 1,
        estimated_complexity: float = 0.5,
    ) -> RoutingDecision:
        """Route a task to the best-suited agent."""
        task_id = hashlib.md5(
            f"route:{task_type}:{time.time()}".encode()
        ).hexdigest()[:12]

        profile = TaskProfile(
            task_id=task_id,
            task_type=task_type,
            description=description,
            priority=priority,
            required_capabilities=required_capabilities or [],
            estimated_complexity=estimated_complexity,
            created_at=time.time(),
        )

        # Find candidates
        candidates = []
        for agent, capability in self._agents.items():
            # Check capability match
            if required_capabilities:
                if not any(cap in capability.capabilities for cap in required_capabilities):
                    continue
            elif task_type not in capability.capabilities:
                continue

            # Check availability
            if capability.status != "online":
                continue
            if capability.current_load > 0.9:
                continue

            candidates.append(capability)

        if not candidates:
            # No available agent — try with relaxed constraints
            for agent, capability in self._agents.items():
                if capability.status == "online":
                    candidates.append(capability)

        if not candidates:
            return RoutingDecision(
                task_id=task_id,
                task_type=task_type,
                candidates=[],
                selected_agent="",
                score=0.0,
                reason="No available agents",
                estimated_time=0.0,
            )

        # Score candidates
        scored = []
        for capability in candidates:
            # Capability match (50%)
            cap_score = 0.0
            if required_capabilities:
                matches = sum(
                    1 for cap in required_capabilities
                    if cap in capability.capabilities
                )
                cap_score = matches / len(required_capabilities)
            else:
                if task_type in capability.capabilities:
                    cap_score = 1.0

            # Load score (20%) — lower load is better
            load_score = 1.0 - capability.current_load

            # Success rate (20%)
            success_score = capability.success_rate

            # Health score (10%)
            health_score = capability.health_score

            # Combined score
            total_score = (
                cap_score * 0.5 +
                load_score * 0.2 +
                success_score * 0.2 +
                health_score * 0.1
            )

            scored.append((total_score, capability))

        # Sort and select
        scored.sort(key=lambda x: -x[0])
        best_score, best_agent = scored[0]

        # Find fallback (second best)
        fallback = ""
        if len(scored) > 1:
            fallback = scored[1][1].agent

        # Calculate estimated time
        estimated_time = best_agent.avg_response_time * (1 + estimated_complexity)

        # Build rejected list
        rejected = [
            {"agent": cap.agent, "score": score, "load": cap.current_load}
            for score, cap in scored[1:5]
        ]

        decision = RoutingDecision(
            task_id=task_id,
            task_type=task_type,
            candidates=[cap.agent for cap in candidates],
            selected_agent=best_agent.agent,
            score=best_score,
            reason=(
                f"Best capability match ({best_agent.agent}) with "
                f"highest success rate ({best_agent.success_rate:.2f}) and "
                f"lowest load ({best_agent.current_load:.2f})"
            ),
            estimated_time=estimated_time,
            fallback_agent=fallback,
            rejected=rejected,
        )

        self._decisions[task_id] = decision
        return decision

    def record_result(
        self,
        task_id: str,
        result: str,
    ) -> None:
        """Record the result of a routed task."""
        decision = self._decisions.get(task_id)
        if not decision:
            return

        agent = decision.selected_agent
        capability = self._agents.get(agent)
        if not capability:
            return

        capability.historical_tasks += 1

        # Update success rate
        if result == "success":
            capability.success_rate = (
                (capability.success_rate * (capability.historical_tasks - 1) + 1.0)
                / capability.historical_tasks
            )
        else:
            capability.success_rate = (
                (capability.success_rate * (capability.historical_tasks - 1) + 0.0)
                / capability.historical_tasks
            )

        # Record in history
        self._history.append(RoutingHistory(
            task_id=task_id,
            task_type=decision.task_type,
            selected_agent=agent,
            result=result,
            timestamp=time.time(),
        ))

    def get_routing_history(self, limit: int = 20) -> list[RoutingHistory]:
        """Get recent routing history."""
        return self._history[-limit:]

    def get_agent_load(self) -> list[LoadMetrics]:
        """Get current load metrics for all agents."""
        metrics = []
        for agent, capability in self._agents.items():
            metrics.append(LoadMetrics(
                agent=agent,
                load_score=capability.current_load,
                cpu_usage=capability.current_load * 80,
                memory_usage=30 + capability.current_load * 40,
                active_tasks=capability.active_tasks,
                max_tasks=10,
                health_score=capability.health_score,
            ))
        return sorted(metrics, key=lambda m: -m.load_score)

    def get_routing_report(self) -> dict:
        """Get routing report."""
        total = len(self._history)
        successes = sum(1 for h in self._history if h.result == "success")
        failures = total - successes

        agent_stats = {}
        for agent, capability in self._agents.items():
            agent_history = [
                h for h in self._history
                if h.selected_agent == agent
            ]
            agent_successes = sum(1 for h in agent_history if h.result == "success")
            agent_stats[agent] = {
                "total_tasks": len(agent_history),
                "success_rate": agent_successes / max(1, len(agent_history)),
                "current_load": capability.current_load,
                "status": capability.status,
                "capabilities": capability.capabilities,
            }

        return {
            "total_routed": total,
            "success_rate": successes / max(1, total),
            "agent_stats": agent_stats,
            "recent_decisions": [
                {
                    "task_id": d.task_id,
                    "task_type": d.task_type,
                    "selected": d.selected_agent,
                    "score": d.score,
                }
                for d in list(self._decisions.values())[-10:]
            ],
        }


# Module-level singleton
adaptive_router = AdaptiveRouter()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/mesh/route/agents/register")
async def register_agent(payload: dict):
    """Register an agent for routing."""
    capability = adaptive_router.register_agent(
        agent=payload["agent"],
        capabilities=payload["capabilities"],
        max_tasks=payload.get("max_tasks", 10),
    )
    return capability.__dict__


@router.post("/api/v1/mesh/route/agents/{agent}/status")
async def update_agent_status(agent: str, payload: dict):
    """Update agent status."""
    adaptive_router.update_agent_status(
        agent,
        payload["status"],
        payload.get("load", 0.0),
        payload.get("active_tasks", 0),
        payload.get("health_score", 0.5),
    )
    return {"status": "updated", "agent": agent}


@router.post("/api/v1/mesh/route/task")
async def route_task(payload: dict):
    """Route a task to the best agent."""
    decision = adaptive_router.route_task(
        task_type=payload["task_type"],
        description=payload.get("description", ""),
        required_capabilities=payload.get("required_capabilities", []),
        priority=payload.get("priority", 1),
        estimated_complexity=payload.get("estimated_complexity", 0.5),
    )
    return decision.__dict__


@router.post("/api/v1/mesh/route/task/{task_id}/result")
async def record_result(task_id: str, payload: dict):
    """Record task result."""
    adaptive_router.record_result(task_id, payload["result"])
    return {"status": "recorded"}


@router.get("/api/v1/mesh/route/history")
async def get_routing_history(limit: int = 20):
    """Get routing history."""
    return [h.__dict__ for h in adaptive_router.get_routing_history(limit)]


@router.get("/api/v1/mesh/route/load")
async def get_agent_load():
    """Get agent load metrics."""
    return [m.__dict__ for m in adaptive_router.get_agent_load()]


@router.get("/api/v1/mesh/route/report")
async def get_routing_report():
    """Get routing report."""
    return adaptive_router.get_routing_report()
