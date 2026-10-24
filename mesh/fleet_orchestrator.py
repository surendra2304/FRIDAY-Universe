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
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

import httpx

from mesh.envelope import AgentEnvelope
from mesh.transport import MeshTransport


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
        """Return online agents that satisfy every required capability.

        Required capabilities are conjunctive: an agent that supports only one
        of several required capabilities must not be assigned the task.
        """
        required = set(task.capabilities_required)
        candidates = [
            agent
            for agent in self.registry.online_agents()
            if not required or required.issubset(set(agent.capabilities))
        ]

        # Prefer more trusted candidates, then break ties deterministically.
        candidates.sort(key=lambda agent: (-agent.trust_level, agent.name))
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


VoteProvider = Callable[[AgentInfo, str, list[str]], Awaitable[dict[str, Any]]]


class ConsensusEngine:
    """Collect real structured votes; delivery acknowledgements are not votes."""

    def __init__(
        self,
        registry: FleetRegistry,
        transport: MeshTransport,
        vote_provider: VoteProvider | None = None,
    ):
        self.registry = registry
        self.transport = transport
        # The provider must obtain an actual agent decision. Without one, the
        # mesh can dispatch vote requests but must not fabricate a vote.
        self.vote_provider = vote_provider

    async def gather_consensus(
        self,
        question: str,
        options: list[str],
        required_agents: list[str] | None = None,
        min_confidence: float = 0.7,
        min_votes: int = 2,
    ) -> ConsensusResult:
        """Return a decision only when real votes meet quorum and confidence.

        A transport status such as ACCEPTED_HTTP only confirms delivery to an
        endpoint. It is deliberately never interpreted as an agent's vote.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        if (
            not isinstance(options, list)
            or not options
            or any(not isinstance(option, str) or not option.strip() for option in options)
            or len(set(options)) != len(options)
        ):
            raise ValueError("options must be a non-empty list of unique strings")
        if (
            isinstance(min_confidence, bool)
            or not isinstance(min_confidence, (int, float))
            or not math.isfinite(min_confidence)
            or not 0.0 <= min_confidence <= 1.0
        ):
            raise ValueError("min_confidence must be between 0 and 1")
        if isinstance(min_votes, bool) or not isinstance(min_votes, int) or min_votes < 1:
            raise ValueError("min_votes must be a positive integer")

        if required_agents is None:
            required_agents = [
                agent.name
                for agent in self.registry.online_agents()
                if AgentCapability.REASONING in agent.capabilities
            ]

        votes: dict[str, list[tuple[str, float, int]]] = {option: [] for option in options}
        evidence: list[dict[str, Any]] = []
        seen_agents: set[str] = set()

        for requested_name in required_agents:
            agent_name = requested_name.upper()
            if agent_name in seen_agents:
                continue
            seen_agents.add(agent_name)
            agent = self.registry.get_agent(agent_name)
            if not agent or agent.status != AgentStatus.ONLINE:
                evidence.append({"agent": agent_name, "vote_received": False, "reason": "agent_not_online"})
                continue

            if self.vote_provider is None:
                envelope = AgentEnvelope(
                    from_agent="FLEET_ORCHESTRATOR",
                    to_agent=agent_name,
                    intent="consensus_vote",
                    payload={"question": question, "options": options},
                )
                try:
                    delivery = await self.transport.publish(envelope)
                    evidence.append({
                        "agent": agent_name,
                        "vote_received": False,
                        "reason": "no_structured_vote_provider",
                        "request_status": delivery.get("status", "UNKNOWN"),
                    })
                except Exception as exc:
                    evidence.append({
                        "agent": agent_name,
                        "vote_received": False,
                        "reason": f"request_failed:{type(exc).__name__}",
                    })
                continue

            try:
                raw_vote = await self.vote_provider(agent, question, options)
                if not isinstance(raw_vote, dict):
                    raise ValueError("vote response must be an object")
                option = raw_vote.get("option")
                confidence = raw_vote.get("confidence")
                if option not in votes:
                    raise ValueError("vote option is not in the offered options")
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence)
                    or not 0.0 <= confidence <= 1.0
                ):
                    raise ValueError("vote confidence must be between 0 and 1")
                votes[option].append((agent.name, float(confidence), agent.trust_level))
                evidence.append({
                    "agent": agent.name,
                    "vote_received": True,
                    "option": option,
                    "confidence": float(confidence),
                })
            except Exception as exc:
                evidence.append({
                    "agent": agent.name,
                    "vote_received": False,
                    "reason": f"invalid_or_unavailable_vote:{type(exc).__name__}",
                })

        actual_votes = [vote for option_votes in votes.values() for vote in option_votes]
        if not actual_votes:
            evidence.append({
                "consensus_reached": False,
                "reason": "no_structured_votes_received",
                "required_quorum": min_votes,
            })
            return ConsensusResult(
                decision="",
                confidence=0.0,
                agreeing_agents=[],
                dissenting_agents=[],
                evidence=evidence,
            )

        scores = {
            option: sum(confidence * trust for _, confidence, trust in option_votes)
            for option, option_votes in votes.items()
        }
        total_trust = sum(trust for _, _, trust in actual_votes)
        best_option = max(options, key=lambda option: scores[option])
        confidence = scores[best_option] / total_trust if total_trust else 0.0
        agreeing = [name for name, _, _ in votes[best_option]]
        dissenting = [
            name
            for option, option_votes in votes.items()
            if option != best_option
            for name, _, _ in option_votes
        ]
        reached = len(actual_votes) >= min_votes and confidence >= min_confidence
        evidence.append({
            "consensus_reached": reached,
            "candidate": best_option,
            "valid_vote_count": len(actual_votes),
            "required_quorum": min_votes,
            "confidence": confidence,
            "minimum_confidence": min_confidence,
        })

        return ConsensusResult(
            decision=best_option if reached else "",
            confidence=confidence,
            agreeing_agents=agreeing if reached else [],
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

    async def health_check(
        self,
        *,
        client: Any | None = None,
        timeout_sec: float = 3.0,
    ) -> dict[str, str]:
        """Probe each registered agent and report observed, not assumed, health.

        A caller may inject a compatible async HTTP client for tests. Network
        failures mark the agent offline; an HTTP response outside 2xx marks it
        degraded. No agent is marked online without a successful health probe.
        """
        if (
            isinstance(timeout_sec, bool)
            or not isinstance(timeout_sec, (int, float))
            or not math.isfinite(timeout_sec)
            or timeout_sec <= 0
        ):
            raise ValueError("timeout_sec must be a positive finite number")

        async def probe(client_instance: Any, agent_name: str) -> tuple[str, str]:
            agent = self.registry.get_agent(agent_name)
            if agent is None:
                return agent_name, AgentStatus.UNKNOWN.value.upper()
            if not agent.health_endpoint:
                status = AgentStatus.UNKNOWN
            else:
                try:
                    response = await client_instance.get(agent.health_endpoint)
                    status = (
                        AgentStatus.ONLINE
                        if 200 <= int(response.status_code) < 300
                        else AgentStatus.DEGRADED
                    )
                except (httpx.TimeoutException, httpx.RequestError):
                    status = AgentStatus.OFFLINE
                except Exception:
                    status = AgentStatus.OFFLINE
            self.registry.update_status(agent_name, status)
            return agent_name, status.value.upper()

        async def run_probes(client_instance: Any) -> dict[str, str]:
            outcomes = await asyncio.gather(
                *(probe(client_instance, name) for name in self.registry.AGENTS)
            )
            return dict(outcomes)

        if client is not None:
            return await run_probes(client)
        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as owned_client:
            return await run_probes(owned_client)

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
        """Request an emergency halt and report whether transport accepted it.

        Acceptance is not proof that the remote process actually stopped, so
        this method deliberately does not change observed health status. A
        subsequent health probe is responsible for recording OFFLINE status.
        """
        if not isinstance(agent, str) or not agent.strip():
            return False
        target = self.registry.get_agent(agent)
        if target is None:
            return False

        envelope = AgentEnvelope(
            from_agent="FLEET_SUPERVISOR",
            to_agent=target.name,
            intent="emergency_halt",
            payload={"reason": "Manual emergency halt"},
        )

        try:
            result = await self.transport.publish(envelope)
        except Exception:
            return False

        if not isinstance(result, dict):
            return False
        return result.get("status") in {
            "DELIVERED_LOCAL",
            "ACCEPTED_NATS",
            "ACCEPTED_HTTP",
        }


# Module-level singleton
fleet_orchestrator = FleetSupervisor()
