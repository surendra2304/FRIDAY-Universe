"""
mesh/fleet_orchestrator.py — FRIDAY Universe Fleet Orchestrator.

Provides high-level coordination primitives for the 10-agent mesh:
1. FleetRegistry: Discovery and health tracking for all agents
2. TaskRouter: Routes tasks to appropriate agents based on capabilities
3. ConsensusEngine: Multi-agent consensus for high-stakes decisions
4. FleetSupervisor: Monitors and manages the entire fleet
5. CrossAgentMemory: Coordinated memory access across agents
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from mesh.envelope import AgentEnvelope, verify_envelope
from mesh.transport import MeshTransport, TransportMode, AGENT_AUTH_MAP


class AgentCapability(str, Enum):
    TRADING = "trading"
    RESEARCH = "research"
    SOFTWARE = "software"
    WEB = "web"
    SECURITY = "security"
    MEMORY = "memory"
    FORECASTING = "forecasting"
    VIDEO = "video"
    REASONING = "reasoning"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class AgentInfo:
    """Information about a fleet agent."""
    name: str
    capabilities: list[AgentCapability]
    status: AgentStatus = AgentStatus.UNKNOWN
    last_heartbeat: float = 0.0
    health_endpoint: str = ""
    trust_level: int = 3
    version: str = "1.0.0"


@dataclass
class FleetTask:
    """A task to be executed by the fleet."""
    id: str
    description: str
    capabilities_required: list[AgentCapability]
    priority: int = 5
    status: str = "PENDING"
    assigned_agent: str = ""
    result: Any = None
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ConsensusResult:
    """Result of a multi-agent consensus."""
    decision: str
    confidence: float
    agreeing_agents: list[str] = field(default_factory=list)
    dissenting_agents: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


class FleetRegistry:
    """Registry of all agents in the FRIDAY Universe fleet."""

    AGENTS = {
        "FRIDAY": {
            "capabilities": [AgentCapability.REASONING],
            "health_endpoint": "http://friday:10000/health",
            "trust_level": 5,
        },
        "INFERENCE": {
            "capabilities": [AgentCapability.REASONING],
            "health_endpoint": "http://inference:8000/health",
            "trust_level": 4,
        },
        "STRATEX": {
            "capabilities": [AgentCapability.TRADING, AgentCapability.REASONING],
            "health_endpoint": "http://stratex:8000/health",
            "trust_level": 4,
        },
        "INTELX": {
            "capabilities": [AgentCapability.RESEARCH, AgentCapability.REASONING],
            "health_endpoint": "http://intelx:8000/health",
            "trust_level": 4,
        },
        "FUTURIS": {
            "capabilities": [AgentCapability.FORECASTING, AgentCapability.REASONING],
            "health_endpoint": "http://futuris:8000/health",
            "trust_level": 3,
        },
        "CORTEX": {
            "capabilities": [AgentCapability.WEB],
            "health_endpoint": "http://cortex:8000/health",
            "trust_level": 3,
        },
        "FORGE": {
            "capabilities": [AgentCapability.SOFTWARE],
            "health_endpoint": "http://forge:8000/health",
            "trust_level": 4,
        },
        "SENTINEL": {
            "capabilities": [AgentCapability.SECURITY],
            "health_endpoint": "http://sentinel:8000/health",
            "trust_level": 5,
        },
        "MEMORA": {
            "capabilities": [AgentCapability.MEMORY],
            "health_endpoint": "http://memora:8000/health",
            "trust_level": 4,
        },
        "VYRALX": {
            "capabilities": [AgentCapability.VIDEO],
            "health_endpoint": "http://vyralx:8000/health",
            "trust_level": 3,
        },
    }

    def __init__(self):
        self.agents: dict[str, AgentInfo] = {}
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        for name, config in self.AGENTS.items():
            self.agents[name] = AgentInfo(
                name=name,
                capabilities=config["capabilities"],
                health_endpoint=config["health_endpoint"],
                trust_level=config["trust_level"],
            )

    def get_agent(self, name: str) -> AgentInfo | None:
        return self.agents.get(name.upper())

    def get_agents_by_capability(self, capability: AgentCapability) -> list[AgentInfo]:
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities
        ]

    def update_status(self, name: str, status: AgentStatus) -> None:
        agent = self.get_agent(name)
        if agent:
            agent.status = status
            agent.last_heartbeat = time.time()

    def all_agents(self) -> list[AgentInfo]:
        return list(self.agents.values())

    def online_agents(self) -> list[AgentInfo]:
        return [a for a in self.agents.values() if a.status == AgentStatus.ONLINE]


class TaskRouter:
    """Routes tasks to appropriate agents based on capabilities."""

    def __init__(self, registry: FleetRegistry):
        self.registry = registry

    def route_task(self, task: FleetTask) -> list[AgentInfo]:
        """Find agents that can handle a task."""
        candidates = []

        for capability in task.capabilities_required:
            capable_agents = self.registry.get_agents_by_capability(capability)
            for agent in capable_agents:
                if agent.status == AgentStatus.ONLINE:
                    if agent not in candidates:
                        candidates.append(agent)

        # Sort by trust level (higher trust first)
        candidates.sort(key=lambda a: a.trust_level, reverse=True)

        return candidates

    def assign_task(self, task: FleetTask) -> AgentInfo | None:
        """Assign a task to the best available agent."""
        candidates = self.route_task(task)

        if not candidates:
            return None

        # Pick the highest trust agent
        best_agent = candidates[0]
        task.assigned_agent = best_agent.name
        task.status = "ASSIGNED"

        return best_agent


class ConsensusEngine:
    """Multi-agent consensus for high-stakes decisions."""

    def __init__(self, registry: FleetRegistry, transport: MeshTransport):
        self.registry = registry
        self.transport = transport

    async def gather_consensus(
        self,
        question: str,
        options: list[str],
        required_agents: list[str] | None = None,
        min_confidence: float = 0.7,
    ) -> ConsensusResult:
        """Gather consensus from multiple agents."""
        if required_agents is None:
            # Default: use all online agents with reasoning capability
            required_agents = [
                a.name for a in self.registry.online_agents()
                if AgentCapability.REASONING in a.capabilities
            ]

        votes: dict[str, list[str]] = {opt: [] for opt in options}
        confidences: dict[str, float] = {opt: 0.0 for opt in options}
        evidence: list[dict[str, Any]] = []

        for agent_name in required_agents:
            agent = self.registry.get_agent(agent_name)
            if not agent or agent.status != AgentStatus.ONLINE:
                continue

            # Create envelope for consensus request
            envelope = AgentEnvelope(
                from_agent="FLEET_ORCHESTRATOR",
                to_agent=agent_name,
                intent="consensus_vote",
                payload={
                    "question": question,
                    "options": options,
                },
            )

            # Send to agent (in production, this would be async HTTP)
            try:
                result = await self.transport.publish(envelope)
                if result.get("status") in ("ACCEPTED_HTTP", "ACCEPTED_NATS", "DELIVERED_LOCAL"):
                    # Simulate vote (in production, parse agent response)
                    # For now, use a heuristic based on agent trust
                    for opt in options:
                        conf = agent.trust_level / 5.0
                        votes[opt].append(agent_name)
                        confidences[opt] += conf
                    evidence.append({
                        "agent": agent_name,
                        "trust_level": agent.trust_level,
                        "voted": True,
                    })
            except Exception as e:
                evidence.append({
                    "agent": agent_name,
                    "error": str(e),
                    "voted": False,
                })

        # Determine winning option
        best_option = max(confidences, key=confidences.get)
        total_confidence = sum(confidences.values())

        if total_confidence > 0:
            normalized_confidence = confidences[best_option] / total_confidence
        else:
            normalized_confidence = 0.0

        agreeing = votes[best_option]
        dissenting = [
            name for opt in votes if opt != best_option
            for name in votes[opt]
        ]

        return ConsensusResult(
            decision=best_option,
            confidence=normalized_confidence,
            agreeing_agents=agreeing,
            dissenting_agents=dissenting,
            evidence=evidence,
        )


class FleetSupervisor:
    """Supervises the entire FRIDAY Universe fleet."""

    def __init__(self, transport: MeshTransport | None = None):
        self.registry = FleetRegistry()
        self.transport = transport or MeshTransport()
        self.router = TaskRouter(self.registry)
        self.consensus = ConsensusEngine(self.registry, self.transport)
        self.active_tasks: dict[str, FleetTask] = {}

    async def health_check(self) -> dict[str, str]:
        """Check health of all agents."""
        results = {}

        for agent_name in self.registry.AGENTS:
            agent = self.registry.get_agent(agent_name)
            if not agent:
                results[agent_name] = "UNKNOWN"
                continue

            # In production, this would make HTTP health checks
            # For now, mark as ONLINE
            self.registry.update_status(agent_name, AgentStatus.ONLINE)
            results[agent_name] = "ONLINE"

        return results

    async def submit_task(self, task: FleetTask) -> AgentInfo | None:
        """Submit a task to the fleet."""
        agent = self.router.assign_task(task)

        if agent:
            self.active_tasks[task.id] = task

        return agent

    async def get_fleet_status(self) -> dict[str, Any]:
        """Get overall fleet status."""
        agents = self.registry.all_agents()

        return {
            "total_agents": len(agents),
            "online_agents": len(self.registry.online_agents()),
            "agents": [
                {
                    "name": a.name,
                    "status": a.status.value,
                    "capabilities": [c.value for c in a.capabilities],
                    "trust_level": a.trust_level,
                }
                for a in agents
            ],
            "active_tasks": len(self.active_tasks),
        }

    async def emergency_halt(self, agent: str) -> bool:
        """Emergency halt an agent."""
        envelope = AgentEnvelope(
            from_agent="FLEET_SUPERVISOR",
            to_agent=agent,
            intent="emergency_halt",
            payload={"reason": "Manual emergency halt"},
        )

        try:
            result = await self.transport.publish(envelope)
            self.registry.update_status(agent, AgentStatus.OFFLINE)
            return True
        except Exception as e:
            return False


# Module-level singleton
fleet_orchestrator = FleetSupervisor()
