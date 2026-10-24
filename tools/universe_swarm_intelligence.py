"""
tools/universe_swarm_intelligence.py — Swarm intelligence and multi-agent coordination.

Provides:
- Swarm intelligence with collective decision-making
- Ant colony optimization for task routing
- Particle swarm optimization for resource allocation
- Swarm leader election
- Distributed consensus protocols (Paxos/Raft-inspired)
- Multi-agent coordination protocols (contract net, blackboard, publish-subscribe)
- Swarm pheromone trails for knowledge propagation

Priority 1-5: Making agents work as a coordinated swarm
"""
import importlib.util
import math
import random
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
    full_name = f"_swarm_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ── Ant Colony Optimization ──────────────────────────────────────────────────

@dataclass
class Pheromone:
    """A pheromone trail on an edge between agents."""
    source: str
    target: str
    strength: float = 1.0
    decay: float = 0.9
    timestamp: float = field(default_factory=time.time)


class AntColonyOptimizer:
    """Ant colony optimization for task routing in the swarm."""

    def __init__(self, agents: list[str], decay: float = 0.9,
                 alpha: float = 1.0, beta: float = 2.0):
        self._agents = agents
        self._decay = decay
        self._alpha = alpha
        self._beta = beta
        self._pheromones: dict[str, dict[str, Pheromone]] = {}
        for a in agents:
            self._pheromones[a] = {}
            for b in agents:
                if a != b:
                    self._pheromones[a][b] = Pheromone(a, b, 1.0, decay)

    def deposit_pheromone(self, source: str, target: str, amount: float):
        """Deposit pheromone on an edge."""
        if source in self._pheromones and target in self._pheromones[source]:
            self._pheromones[source][target].strength += amount
            self._pheromones[source][target].timestamp = time.time()

    def evaporate(self):
        """Evaporate pheromones."""
        for a_dict in self._pheromones.values():
            for ph in a_dict.values():
                ph.strength *= self._decay

    def choose_path(self, start: str, end: str, length: int = 3) -> list[str]:
        """Choose a path from start to end using ant colony optimization."""
        path = [start]
        current = start
        visited = {start}

        for _ in range(length - 1):
            neighbors = {a: self._pheromones[current][a].strength
                         for a in self._agents if a not in visited and a in self._pheromones[current]}
            if not neighbors:
                break
            # Convert to weights
            total = sum(neighbors.values())
            if total <= 0:
                next_agent = random.choice(list(neighbors.keys()))
            else:
                weights = [neighbors[a] / total for a in neighbors]
                next_agent = random.choices(list(neighbors.keys()), weights=weights)[0]

            path.append(next_agent)
            visited.add(next_agent)
            current = next_agent

        return path

    def optimize_route(self, tasks: list[dict], iterations: int = 10) -> list[list[str]]:
        """Optimize task routing over multiple iterations."""
        best_paths = []
        for iteration in range(iterations):
            self.evaporate()
            for task in tasks:
                start = task.get("from", self._agents[0])
                end = task.get("to", self._agents[-1])
                path = self.choose_path(start, end, length=task.get("length", 3))
                # Deposit pheromone based on path quality
                quality = task.get("quality", 1.0)
                for i in range(len(path) - 1):
                    self.deposit_pheromone(path[i], path[i + 1], quality)
                best_paths.append(path)
        return best_paths

    def get_best_edges(self, limit: int = 5) -> list[tuple[str, str, float]]:
        """Get the strongest pheromone edges."""
        edges = []
        for a, a_dict in self._pheromones.items():
            for b, ph in a_dict.items():
                edges.append((a, b, ph.strength))
        edges.sort(key=lambda e: e[2], reverse=True)
        return edges[:limit]


# ── Particle Swarm Optimization ──────────────────────────────────────────────

@dataclass
class Particle:
    """A particle in the swarm optimization."""
    position: list[float]
    velocity: list[float]
    best_position: list[float]
    best_score: float = float("inf")


class ParticleSwarmOptimizer:
    """Particle swarm optimization for resource allocation."""

    def __init__(self, dimensions: int, particles: int = 10,
                 inertia: float = 0.7, cognitive: float = 1.5,
                 social: float = 1.5):
        self._dimensions = dimensions
        self._inertia = inertia
        self._cognitive = cognitive
        self._social = social
        self._particles: list[Particle] = []
        self._global_best: list[float] = []
        self._global_best_score = float("inf")

        for _ in range(particles):
            pos = [random.uniform(0, 1) for _ in range(dimensions)]
            vel = [random.uniform(-0.1, 0.1) for _ in range(dimensions)]
            self._particles.append(Particle(
                position=pos, velocity=vel, best_position=pos[:],
            ))
        self._global_best = self._particles[0].position[:]

    def optimize(self, objective_func, iterations: int = 10) -> list[float]:
        """Run particle swarm optimization."""
        for _ in range(iterations):
            for particle in self._particles:
                score = objective_func(particle.position)
                if score < particle.best_score:
                    particle.best_score = score
                    particle.best_position = particle.position[:]
                if score < self._global_best_score:
                    self._global_best_score = score
                    self._global_best = particle.position[:]

                # Update velocity
                for d in range(self._dimensions):
                    cognitive = self._cognitive * random.uniform(0, 1) * (particle.best_position[d] - particle.position[d])
                    social = self._social * random.uniform(0, 1) * (self._global_best[d] - particle.position[d])
                    particle.velocity[d] = (self._inertia * particle.velocity[d]
                                            + cognitive + social)
                    particle.position[d] += particle.velocity[d]
                    # Clamp to [0, 1]
                    particle.position[d] = max(0.0, min(1.0, particle.position[d]))

        return self._global_best


# ── Distributed Consensus ─────────────────────────────────────────────────────

@dataclass
class ConsensusEntry:
    """An entry in the distributed consensus log."""
    index: int
    term: int
    value: Any
    committed: bool = False
    committed_at: float = 0.0


class DistributedConsensus:
    """Distributed consensus protocol (Raft-inspired)."""

    def __init__(self, nodes: list[str]):
        self._nodes = nodes
        self._log: list[ConsensusEntry] = []
        self._term = 0
        self._leader = ""
        self._commit_index = 0
        self._votes: dict[int, set[str]] = {}  # term -> set of voters

    def start_election(self) -> str:
        """Start a leader election."""
        self._term += 1
        self._leader = ""
        self._votes[self._term] = set()
        # Self-vote
        self._votes[self._term].add("FRIDAY")
        # Check if majority
        majority = len(self._nodes) // 2 + 1
        if len(self._votes[self._term]) >= majority:
            self._leader = "FRIDAY"
        return self._leader

    def vote(self, node: str, term: int) -> bool:
        """Vote for a candidate in an election."""
        if term > self._term:
            self._term = term
            self._leader = ""
            self._votes[term] = set()
        if term == self._term and node not in self._votes[term]:
            self._votes[term].add(node)
            majority = len(self._nodes) // 2 + 1
            if len(self._votes[term]) >= majority:
                self._leader = "FRIDAY"
                return True
        return False

    def append_entry(self, value: Any) -> ConsensusEntry:
        """Append an entry to the log (requires leader)."""
        if not self._leader:
            raise Exception("No leader elected")
        entry = ConsensusEntry(
            index=len(self._log), term=self._term, value=value,
        )
        self._log.append(entry)
        return entry

    def commit_entry(self, index: int):
        """Commit an entry."""
        if index < len(self._log):
            self._log[index].committed = True
            self._log[index].committed_at = time.time()
            self._commit_index = index

    def get_committed_value(self, index: int) -> Any:
        """Get a committed value."""
        if index < len(self._log) and self._log[index].committed:
            return self._log[index].value
        return None

    @property
    def leader(self) -> str:
        return self._leader

    @property
    def term(self) -> int:
        return self._term

    def get_log_status(self) -> list[dict]:
        """Get log status."""
        return [
            {"index": e.index, "term": e.term, "committed": e.committed,
             "value": str(e.value)[:30]}
            for e in self._log
        ]


# ── Multi-Agent Coordination ─────────────────────────────────────────────────

class ContractNetProtocol:
    """Contract Net Protocol for task distribution."""

    def __init__(self):
        self._managers: dict[str, dict] = {}
        self._bidders: dict[str, dict] = {}
        self._contracts: dict[str, dict] = {}
        self._audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")

    def announce_task(self, manager: str, task_id: str, description: str,
                      requirements: list[str] = None) -> str:
        """Announce a task for bidding."""
        announcement = {
            "task_id": task_id, "manager": manager,
            "description": description,
            "requirements": requirements or [],
            "announced_at": time.time(),
        }
        self._managers[task_id] = announcement
        self._bidders[task_id] = {}
        self._audit.log(manager, "task_announced", task_id, "success")
        return task_id

    def submit_bid(self, bidder: str, task_id: str, cost: float,
                   capabilities: list[str]) -> bool:
        """Submit a bid for a task."""
        if task_id not in self._managers:
            return False
        self._bidders[task_id][bidder] = {
            "cost": cost, "capabilities": capabilities,
            "submitted_at": time.time(),
        }
        return True

    def award_contract(self, task_id: str, winner: str) -> bool:
        """Award a contract to the winning bidder."""
        if task_id not in self._managers:
            return False
        if winner not in self._bidders.get(task_id, {}):
            return False

        self._contracts[task_id] = {
            "task_id": task_id, "manager": self._managers[task_id]["manager"],
            "winner": winner, "cost": self._bidders[task_id][winner]["cost"],
            "awarded_at": time.time(),
        }
        self._audit.log(winner, "contract_awarded", task_id, "success")
        return True

    def get_best_bid(self, task_id: str) -> dict:
        """Get the best (lowest cost) bid for a task."""
        bids = self._bidders.get(task_id, {})
        if not bids:
            return {}
        best = min(bids.items(), key=lambda x: x[1]["cost"])
        return {"bidder": best[0], "cost": best[1]["cost"],
                "capabilities": best[1]["capabilities"]}

    def get_contracts(self) -> list[dict]:
        """Get all awarded contracts."""
        return list(self._contracts.values())


class BlackboardSystem:
    """Blackboard system for shared state across agents."""

    def __init__(self):
        self._blackboard: dict[str, Any] = {}
        self._subscribers: dict[str, list] = {}
        self._audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")

    def write(self, agent: str, key: str, value: Any):
        """Write to the blackboard."""
        self._blackboard[key] = value
        self._audit.log(agent, "blackboard_write", key, "success")
        for callback in self._subscribers.get(key, []):
            try:
                callback(agent, key, value)
            except Exception:
                pass

    def read(self, key: str, default: Any = None) -> Any:
        """Read from the blackboard."""
        return self._blackboard.get(key, default)

    def subscribe(self, key: str, callback):
        """Subscribe to changes on a key."""
        self._subscribers.setdefault(key, []).append(callback)

    def get_all(self) -> dict:
        """Get all blackboard entries."""
        return self._blackboard


class PublishSubscribeBus:
    """Publish-Subscribe message bus for inter-agent communication."""

    def __init__(self):
        self._topics: dict[str, list[str]] = {}
        self._subscribers: dict[str, list] = {}
        self._messages: list[dict] = []
        self._max_messages = 1000
        self._audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")

    def subscribe(self, topic: str, subscriber: str) -> str:
        """Subscribe to a topic."""
        if topic not in self._topics:
            self._topics[topic] = []
        if subscriber not in self._topics[topic]:
            self._topics[topic].append(subscriber)
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = (topic, subscriber)
        self._audit.log(subscriber, "subscribed", topic, "success")
        return sub_id

    def publish(self, topic: str, publisher: str, message: Any) -> int:
        """Publish a message to a topic."""
        msg = {
            "topic": topic, "publisher": publisher,
            "message": message, "timestamp": time.time(),
        }
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        self._audit.log(publisher, "published", topic, "success")
        return len(self._messages)

    def get_topics(self) -> dict:
        """Get all topics and their subscribers."""
        return {t: subscribers for t, subscribers in self._topics.items()}

    def get_messages(self, topic: str = "", limit: int = 100) -> list[dict]:
        """Get messages, optionally filtered by topic."""
        if topic:
            messages = [m for m in self._messages if m["topic"] == topic]
        else:
            messages = self._messages
        return messages[-limit:]


# ── Swarm Intelligence Manager ────────────────────────────────────────────────

class SwarmIntelligenceManager:
    """Unified swarm intelligence manager."""

    def __init__(self, agents: list[str] = None):
        self._agents = agents or ["FRIDAY", "Inference", "Cortex", "Stratex",
                                   "Forge", "Sentinel", "IntelX", "VyralX", "Futuris", "Memora"]
        self._aco = AntColonyOptimizer(self._agents)
        self._pso = ParticleSwarmOptimizer(dimensions=len(self._agents))
        self._consensus = DistributedConsensus(self._agents)
        self._contract_net = ContractNetProtocol()
        self._blackboard = BlackboardSystem()
        self._pubsub = PublishSubscribeBus()

    @property
    def agents(self) -> list[str]:
        return self._agents

    @property
    def ant_colony(self) -> AntColonyOptimizer:
        return self._aco

    @property
    def particle_swarm(self) -> ParticleSwarmOptimizer:
        return self._pso

    @property
    def consensus(self) -> DistributedConsensus:
        return self._consensus

    @property
    def contract_net(self) -> ContractNetProtocol:
        return self._contract_net

    @property
    def blackboard(self) -> BlackboardSystem:
        return self._blackboard

    @property
    def pubsub(self) -> PublishSubscribeBus:
        return self._pubsub


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe Swarm Intelligence ===\n")

    swarm = SwarmIntelligenceManager()

    # Ant colony optimization
    print("Ant Colony Optimization:")
    tasks = [
        {"from": "FRIDAY", "to": "Stratex", "length": 4, "quality": 0.9},
        {"from": "FRIDAY", "to": "Cortex", "length": 3, "quality": 0.7},
        {"from": "Cortex", "to": "Forge", "length": 3, "quality": 0.6},
    ]
    paths = swarm.ant_colony.optimize_route(tasks, iterations=5)
    best_edges = swarm.ant_colony.get_best_edges(3)
    print(f"  Best edges: {[(a, b, round(s, 2)) for a, b, s in best_edges]}")

    # Particle swarm optimization
    print("\nParticle Swarm Optimization:")
    def objective(x):
        return sum((x[i] - 0.5) ** 2 for i in range(len(x)))
    result = swarm.particle_swarm.optimize(objective, iterations=10)
    print(f"  Optimal allocation: {[round(r, 3) for r in result]}")

    # Distributed consensus
    print("\nDistributed Consensus:")
    leader = swarm.consensus.start_election()
    print(f"  Leader: {leader} (term {swarm.consensus.term})")
    for node in swarm._agents:
        swarm.consensus.vote(node, swarm.consensus.term)
    print(f"  Leader after votes: {swarm.consensus.leader}")
    entry = swarm.consensus.append_entry("test_decision")
    swarm.consensus.commit_entry(entry.index)
    print(f"  Committed: {swarm.consensus.get_committed_value(entry.index)}")

    # Contract net
    print("\nContract Net Protocol:")
    swarm.contract_net.announce_task("FRIDAY", "task_1", "Analyze market", ["market_analysis"])
    swarm.contract_net.submit_bid("Inference", "task_1", 0.5, ["reasoning"])
    swarm.contract_net.submit_bid("Cortex", "task_1", 0.7, ["decision"])
    swarm.contract_net.submit_bid("Stratex", "task_1", 0.4, ["portfolio"])
    best = swarm.contract_net.get_best_bid("task_1")
    print(f"  Best bid: {best}")
    swarm.contract_net.award_contract("task_1", best["bidder"])

    # Blackboard
    print("\nBlackboard System:")
    swarm.blackboard.write("FRIDAY", "market_status", "bullish")
    swarm.blackboard.write("Cortex", "risk_level", "moderate")
    print(f"  Market: {swarm.blackboard.read('market_status')}")
    print(f"  Risk: {swarm.blackboard.read('risk_level')}")
    print(f"  All entries: {len(swarm.blackboard.get_all())}")

    # Publish-subscribe
    print("\nPublish-Subscribe Bus:")
    swarm.pubsub.subscribe("market_updates", "Stratex")
    swarm.pubsub.subscribe("market_updates", "Cortex")
    swarm.pubsub.publish("market_updates", "FRIDAY", "BTC up 5%")
    swarm.pubsub.publish("security_alerts", "Sentinel", "DDoS detected")
    print(f"  Topics: {swarm.pubsub.get_topics()}")
    print(f"  Messages: {len(swarm.pubsub.get_messages())}")

    print("\n=== Swarm Intelligence Ready ===")
