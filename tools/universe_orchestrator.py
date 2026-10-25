"""
tools/universe_orchestrator.py — Multi-agent orchestration and event streaming.

Provides:
- Agent orchestrator for complex multi-agent workflows
- Real-time event streaming (SSE-compatible generator)
- Cross-agent consensus engine
- Task fan-out/fan-in patterns
- Agent health monitoring
- Circuit breaker for inter-agent calls
- Real-time event bus with pub/sub

Priority 1-5: Making agents work as a real integrated system
"""
import importlib.util
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, relpath):
    path = str(ROOT / relpath)
    full_name = f"_orch_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ── Event Bus ─────────────────────────────────────────────────────────────────

@dataclass
class Event:
    """An event in the real-time event stream."""
    event_id: str
    event_type: str
    source: str
    payload: dict
    timestamp: float = field(default_factory=time.time)
    version: int = 1


class EventBus:
    """Real-time event bus with pub/sub support."""

    def __init__(self):
        self._subscribers: dict[str, list] = {}
        self._history: list[Event] = []
        self._max_history = 1000
        self._event_id = 0

    def subscribe(self, event_type: str, callback) -> str:
        """Subscribe to an event type."""
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscribers.setdefault(event_type, []).append((sub_id, callback))
        return sub_id

    def unsubscribe(self, event_type: str, sub_id: str):
        """Unsubscribe from an event type."""
        subs = self._subscribers.get(event_type, [])
        self._subscribers[event_type] = [(s, c) for s, c in subs if s != sub_id]

    def publish(self, event_type: str, source: str, payload: dict) -> Event:
        """Publish an event to all subscribers."""
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type, source=source, payload=payload,
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        for sub_id, callback in self._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception:
                pass

        return event

    def get_history(self, event_type: str = "", limit: int = 100) -> list[Event]:
        """Get event history."""
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def stream(self, event_type: str = "", limit: int = 100) -> list[str]:
        """Get events in SSE-compatible format."""
        events = self.get_history(event_type, limit)
        lines = []
        for e in events:
            data = json.dumps({
                "event_id": e.event_id,
                "event_type": e.event_type,
                "source": e.source,
                "payload": e.payload,
                "timestamp": e.timestamp,
            })
            lines.append("data: " + data + "\n\n")
        return lines


# ── Circuit Breaker ──────────────────────────────────────────────────────────

class CircuitBreaker:
    """Circuit breaker for inter-agent calls."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._last_failure_time = 0.0

    def call(self, func):
        """Execute a function with circuit breaker protection."""
        if self._state == self.OPEN:
            if time.time() - self._last_failure_time > self._recovery_timeout:
                self._state = self.HALF_OPEN
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def record_success(self):
        self._success_count += 1
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED
        self._failure_count = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._state = self.OPEN

    @property
    def state(self) -> str:
        return self._state


# ── Agent Orchestrator ───────────────────────────────────────────────────────

@dataclass
class OrchestrationTask:
    """A task in an orchestration workflow."""
    task_id: str
    agent: str
    task_type: str
    description: str
    payload: dict
    status: str = "pending"
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    timeout: float = 30.0


@dataclass
class OrchestrationPlan:
    """A plan for orchestrating multiple agents."""
    plan_id: str
    name: str
    description: str
    tasks: list[OrchestrationTask]
    fan_out: bool = False  # Whether to run tasks in parallel
    fan_in: bool = False  # Whether to aggregate results
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    aggregated_result: Any = None


class AgentOrchestrator:
    """Orchestrator for complex multi-agent workflows."""

    def __init__(self):
        self._marketplace = None
        try:
            import universe_agent_marketplace as mp
            self._marketplace = mp.AgentMarketplace()
        except Exception:
            self._marketplace = None
        self._event_bus = EventBus()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._plans: dict[str, OrchestrationPlan] = {}
        self._agent_health: dict[str, dict] = {}

    def _breaker(self, agent: str) -> CircuitBreaker:
        if agent not in self._circuit_breakers:
            self._circuit_breakers[agent] = CircuitBreaker()
        return self._circuit_breakers[agent]

    def create_plan(self, name: str, description: str,
                    tasks: list[dict], fan_out: bool = False,
                    fan_in: bool = False) -> OrchestrationPlan:
        """Create an orchestration plan."""
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        plan = OrchestrationPlan(
            plan_id=plan_id, name=name, description=description,
            tasks=[], fan_out=fan_out, fan_in=fan_in,
        )
        for t in tasks:
            task = OrchestrationTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                agent=t.get("agent", "FRIDAY"),
                task_type=t.get("type", "execute"),
                description=t.get("description", ""),
                payload=t.get("payload", {}),
                timeout=t.get("timeout", 30.0),
            )
            plan.tasks.append(task)
        self._plans[plan_id] = plan
        self._event_bus.publish("plan_created", "Orchestrator", {"plan_id": plan_id, "name": name})
        return plan

    def execute_plan(self, plan_id: str) -> OrchestrationPlan:
        """Execute an orchestration plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.status = "running"
        plan.started_at = time.time()
        self._event_bus.publish("plan_started", "Orchestrator", {"plan_id": plan_id})

        if plan.fan_out:
            self._execute_fan_out(plan)
        else:
            self._execute_sequential(plan)

        if plan.fan_in:
            self._aggregate_results(plan)

        plan.status = "completed"
        plan.completed_at = time.time()
        self._event_bus.publish("plan_completed", "Orchestrator", {"plan_id": plan_id})
        return plan

    def _execute_sequential(self, plan: OrchestrationPlan):
        for task in plan.tasks:
            task.status = "running"
            task.started_at = time.time()
            self._event_bus.publish("task_started", "Orchestrator",
                                     {"task_id": task.task_id, "agent": task.agent})
            result = self._call_agent(task.agent, task.task_type, task.payload, task.timeout)
            task.status = "completed" if result else "failed"
            task.result = result
            task.completed_at = time.time()
            self._event_bus.publish("task_completed", "Orchestrator",
                                     {"task_id": task.task_id, "status": task.status})

    def _execute_fan_out(self, plan: OrchestrationPlan):
        """Execute all tasks in parallel (simulated)."""
        for task in plan.tasks:
            task.status = "running"
            task.started_at = time.time()
            result = self._call_agent(task.agent, task.task_type, task.payload, task.timeout)
            task.status = "completed" if result else "failed"
            task.result = result
            task.completed_at = time.time()

    def _aggregate_results(self, plan: OrchestrationPlan):
        """Aggregate results from fan-in."""
        results = [t.result for t in plan.tasks if t.status == "completed"]
        if results:
            plan.aggregated_result = {
                "count": len(results),
                "results": results,
                "summary": str(results)[:100],
            }

    def _call_agent(self, agent: str, task_type: str, payload: dict,
                    timeout: float) -> Any:
        """Call an agent with circuit breaker protection."""
        def _do_call():
            if self._marketplace:
                call = self._marketplace.call_service(
                    "Orchestrator", agent, task_type, payload
                )
                self._agent_health[agent] = {
                    "last_call": time.time(),
                    "status": "success" if call.status == "completed" else "failed",
                    "circuit_state": self._breaker(agent).state,
                }
                return call.result if call.status == "completed" else None
            return f"Simulated call to {agent}.{task_type}"

        try:
            return self._breaker(agent).call(_do_call)
        except Exception as e:
            self._agent_health[agent] = {
                "last_call": time.time(),
                "status": "circuit_open",
                "error": str(e),
            }
            return None

    def get_plan(self, plan_id: str) -> OrchestrationPlan:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_all_plans(self) -> list[OrchestrationPlan]:
        """Get all plans."""
        return list(self._plans.values())

    def get_agent_health(self, agent: str) -> dict:
        """Get health status for an agent."""
        h = self._agent_health.get(agent, {})
        cb = self._breaker(agent)
        h["circuit_state"] = cb.state
        h["failure_count"] = cb._failure_count
        return h

    def get_all_health(self) -> dict:
        """Get health for all agents."""
        agents = set(self._marketplace._services.keys()) if self._marketplace else set()
        agent_names = set()
        if self._marketplace:
            for svc in self._marketplace._services.values():
                agent_names.add(svc.agent)
        agent_names.update(self._agent_health.keys())
        return {a: self.get_agent_health(a) for a in agent_names}

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus


# ── Consensus Engine ──────────────────────────────────────────────────────────

@dataclass
class ConsensusDecision:
    """A decision reached by consensus."""
    decision_id: str
    topic: str
    decision: str
    votes: dict[str, str]  # agent -> vote (approve/reject/abstain)
    voter_count: int = 0
    approver_count: int = 0
    status: str = "pending"  # pending/approved/rejected
    decided_at: float = 0.0


class ConsensusEngine:
    """Cross-agent consensus engine for decision making."""

    def __init__(self):
        self._decisions: dict[str, ConsensusDecision] = {}
        self._quorum = 3  # Minimum agents needed for consensus

    def propose_decision(self, topic: str, proposer: str,
                         description: str) -> ConsensusDecision:
        """Propose a decision for consensus."""
        decision_id = f"cons_{uuid.uuid4().hex[:12]}"
        decision = ConsensusDecision(
            decision_id=decision_id, topic=topic,
            decision=description, votes={},
        )
        decision.votes[proposer] = "approve"
        decision.voter_count = 1
        decision.approver_count = 1
        self._decisions[decision_id] = decision
        return decision

    def vote(self, decision_id: str, agent: str, vote: str) -> bool:
        """Vote on a decision."""
        decision = self._decisions.get(decision_id)
        if not decision:
            return False
        if agent in decision.votes:
            return False  # Already voted

        decision.votes[agent] = vote
        decision.voter_count += 1
        if vote == "approve":
            decision.approver_count += 1

        # Check for consensus
        if decision.voter_count >= self._quorum:
            if decision.approver_count > decision.voter_count / 2:
                decision.status = "approved"
                decision.decided_at = time.time()
            else:
                decision.status = "rejected"
                decision.decided_at = time.time()

        return True

    def get_decision(self, decision_id: str) -> ConsensusDecision:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)

    def get_all_decisions(self) -> list[ConsensusDecision]:
        """Get all decisions."""
        return list(self._decisions.values())

    def get_pending_decisions(self) -> list[ConsensusDecision]:
        """Get pending decisions."""
        return [d for d in self._decisions.values() if d.status == "pending"]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe Orchestrator ===\n")

    orch = AgentOrchestrator()
    consensus = ConsensusEngine()

    # Event bus demo
    print("Event Bus:")
    received = []
    orch.event_bus.subscribe("task_completed", lambda e: received.append(e))

    # Create and execute a plan
    print("\nOrchestration Plans:")
    plan = orch.create_plan(
        "Multi-Agent Analysis",
        "Run analysis across multiple agents",
        tasks=[
            {"agent": "Inference", "type": "reasoning", "description": "Analyze question",
             "payload": {"query": "market trends"}},
            {"agent": "Cortex", "type": "decision", "description": "Make decision",
             "payload": {"decision": "invest"}},
            {"agent": "Stratex", "type": "portfolio", "description": "Optimize portfolio",
             "payload": {"capital": "10000"}},
        ],
        fan_out=True,
        fan_in=True,
    )
    print(f"  Plan created: {plan.plan_id} ({len(plan.tasks)} tasks)")

    orch.execute_plan(plan.plan_id)
    print(f"  Plan status: {plan.status}")
    print(f"  Tasks completed: {sum(1 for t in plan.tasks if t.status == 'completed')}/{len(plan.tasks)}")
    print(f"  Aggregated result: {plan.aggregated_result}")
    print(f"  Events received: {len(received)}")

    # Circuit breaker demo
    print("\nCircuit Breaker:")
    print(f"  Inference state: {orch._breaker('Inference').state}")

    # Health check
    print("\nAgent Health:")
    health = orch.get_all_health()
    for agent, h in sorted(health.items()):
        print(f"  {agent}: circuit={h.get('circuit_state', 'unknown')} status={h.get('status', 'unknown')}")

    # Consensus demo
    print("\nConsensus Engine:")
    cons = consensus.propose_decision("Investment Strategy", "FRIDAY",
                                       "Alloc 30% to crypto")
    print(f"  Proposed: {cons.topic} by {cons.votes}")
    consensus.vote(cons.decision_id, "Cortex", "approve")
    consensus.vote(cons.decision_id, "Stratex", "approve")
    consensus.vote(cons.decision_id, "IntelX", "reject")
    print(f"  After votes: {cons.status} ({cons.approver_count}/{cons.voter_count})")

    # Event stream
    print("\nEvent Stream (SSE format):")
    stream = orch.event_bus.stream(limit=3)
    for s in stream:
        print(f"  {s.strip()}")

    print("\n=== Orchestrator Ready ===")
