"""
tools/universe_knowledge_graph.py — Cross-agent knowledge graph and multi-agent simulation.

Provides:
- Knowledge graph with entities, relationships, and reasoning
- Multi-agent simulation engine for testing agent interactions
- Cross-agent inference and reasoning
- Pattern detection across agent histories
- Knowledge synthesis from multiple agent perspectives
- Conflict detection and resolution in shared knowledge

Priority 1-5: Making agents share and reason about knowledge
"""
import importlib.util
import json
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
    full_name = f"_kg_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""
    node_id: str
    node_type: str  # entity, concept, event, agent, skill
    label: str
    properties: dict
    source_agents: list[str]
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeEdge:
    """An edge in the knowledge graph."""
    edge_id: str
    source: str
    target: str
    relation: str  # related_to, causes, enables, contradicts, refines
    properties: dict
    source_agents: list[str]
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)


class KnowledgeGraph:
    """Cross-agent knowledge graph for shared reasoning."""

    def __init__(self):
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}
        self._agent_knowledge: dict[str, list[str]] = {}  # agent -> node_ids
        self._audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")

    def add_node(self, node_type: str, label: str, properties: dict = None,
                 source_agents: list[str] = None, confidence: float = 1.0) -> KnowledgeNode:
        """Add a node to the knowledge graph."""
        node_id = f"node_{uuid.uuid4().hex[:12]}"
        node = KnowledgeNode(
            node_id=node_id, node_type=node_type, label=label,
            properties=properties or {},
            source_agents=source_agents or ["FRIDAY"],
            confidence=confidence,
        )
        self._nodes[node_id] = node

        for agent in node.source_agents:
            self._agent_knowledge.setdefault(agent, []).append(node_id)

        self._audit.log("KnowledgeGraph", "node_added", label, "success", node_id)
        return node

    def add_edge(self, source: str, target: str, relation: str,
                 properties: dict = None, source_agents: list[str] = None,
                 confidence: float = 1.0) -> KnowledgeEdge:
        """Add an edge to the knowledge graph."""
        if source not in self._nodes or target not in self._nodes:
            raise ValueError("Source or target node not found")

        edge_id = f"edge_{uuid.uuid4().hex[:12]}"
        edge = KnowledgeEdge(
            edge_id=edge_id, source=source, target=target,
            relation=relation, properties=properties or {},
            source_agents=source_agents or ["FRIDAY"], confidence=confidence,
        )
        self._edges[edge_id] = edge

        self._audit.log("KnowledgeGraph", "edge_added", relation, "success", edge_id)
        return edge

    def query_node(self, label: str, node_type: str = "") -> list[KnowledgeNode]:
        """Query nodes by label and type."""
        results = []
        for node in self._nodes.values():
            if label.lower() in node.label.lower() or label.lower() == node.label.lower():
                if not node_type or node.node_type == node_type:
                    results.append(node)
        return results

    def query_by_agent(self, agent: str) -> list[KnowledgeNode]:
        """Get all nodes contributed by an agent."""
        return [self._nodes[nid] for nid in self._agent_knowledge.get(agent, [])]

    def find_related(self, node_id: str, depth: int = 1) -> list[KnowledgeNode]:
        """Find nodes related to a given node."""
        related = []
        visited = {node_id}
        current_level = [node_id]

        for _ in range(depth):
            next_level = []
            for nid in current_level:
                for edge in self._edges.values():
                    if edge.source == nid and edge.target not in visited:
                        related.append(self._nodes[edge.target])
                        visited.add(edge.target)
                        next_level.append(edge.target)
                    elif edge.target == nid and edge.source not in visited:
                        related.append(self._nodes[edge.source])
                        visited.add(edge.source)
                        next_level.append(edge.source)
            current_level = next_level

        return related

    def detect_conflicts(self) -> list[dict]:
        """Detect conflicting knowledge (contradicts relations)."""
        conflicts = []
        for edge in self._edges.values():
            if edge.relation == "contradicts":
                source_node = self._nodes[edge.source]
                target_node = self._nodes[edge.target]
                conflicts.append({
                    "type": "contradiction",
                    "node_a": source_node.label,
                    "node_b": target_node.label,
                    "source_agents": edge.source_agents,
                })
        return conflicts

    def synthesize_knowledge(self, topic: str) -> dict:
        """Synthesize knowledge about a topic from all agents."""
        nodes = self.query_node(topic)
        if not nodes:
            return {"topic": topic, "nodes": 0, "synthesis": "No knowledge found"}

        all_related = []
        for node in nodes:
            related = self.find_related(node.node_id, depth=2)
            all_related.extend(related)

        synthesis = {
            "topic": topic,
            "nodes": len(nodes),
            "related": len(all_related),
            "contributing_agents": list(set(
                a for n in nodes for a in n.source_agents
            )),
            "summary": f"{len(nodes)} nodes about '{topic}' from {len(set(a for n in nodes for a in n.source_agents))} agents",
        }
        return synthesis

    def get_graph_stats(self) -> dict:
        """Get graph statistics."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": self._count_by_type(self._nodes),
            "edges_by_relation": self._count_by_relation(self._edges),
            "agents": list(self._agent_knowledge.keys()),
        }

    def _count_by_type(self, nodes):
        counts = {}
        for node in nodes.values():
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts

    def _count_by_relation(self, edges):
        counts = {}
        for edge in edges.values():
            counts[edge.relation] = counts.get(edge.relation, 0) + 1
        return counts


# ── Multi-Agent Simulation Engine ─────────────────────────────────────────────

@dataclass
class SimulationStep:
    """A single step in a simulation."""
    step_id: int
    timestamp: float
    agent: str
    action: str
    target: str
    payload: dict
    result: Any


class MultiAgentSimulator:
    """Multi-agent simulation engine for testing interactions."""

    def __init__(self):
        self._kg = KnowledgeGraph()
        self._steps: list[SimulationStep] = []
        self._scenario = ""
        self._running = False
        self._agents: list[str] = ["FRIDAY", "Inference", "Cortex", "Stratex", "Forge",
                                    "Sentinel", "IntelX", "VyralX", "Futuris", "Memora"]
        self._event_bus = None

    def set_scenario(self, scenario: str, description: str = ""):
        """Set the simulation scenario."""
        self._scenario = scenario
        self._description = description

    def add_agent(self, agent: str):
        """Add an agent to the simulation."""
        if agent not in self._agents:
            self._agents.append(agent)

    def step(self, agent: str, action: str, target: str, payload: dict = None) -> SimulationStep:
        """Execute one simulation step."""
        step = SimulationStep(
            step_id=len(self._steps), timestamp=time.time(),
            agent=agent, action=action, target=target,
            payload=payload or {}, result={"status": "completed"},
        )
        self._steps.append(step)

        # Update knowledge graph
        if action == "share_knowledge":
            self._kg.add_node(
                "knowledge", payload.get("topic", "unknown"),
                {"content": payload.get("content", ""), "action": action},
                source_agents=[agent],
            )
        elif action == "analyze":
            self._kg.add_node(
                "analysis", payload.get("topic", "analysis"),
                {"result": payload.get("result", ""), "action": action},
                source_agents=[agent],
            )
        elif action == "decision":
            self._kg.add_node(
                "decision", payload.get("decision", "decision"),
                {"context": payload.get("context", ""), "action": action},
                source_agents=[agent],
            )

        return step

    def run_simulation(self, steps: list[dict]) -> dict:
        """Run a full simulation with multiple steps."""
        self._running = True
        self._steps = []

        for step_data in steps:
            self.step(
                step_data.get("agent", "FRIDAY"),
                step_data.get("action", "execute"),
                step_data.get("target", ""),
                step_data.get("payload", {}),
            )

        self._running = False
        return {
            "scenario": self._scenario,
            "steps": len(self._steps),
            "agents_involved": sorted(set(s.agent for s in self._steps)),
            "knowledge_nodes": self._kg.get_graph_stats()["total_nodes"],
            "completed": True,
        }

    def run_market_scenario(self):
        """Run a market analysis scenario."""
        self.set_scenario("Market Analysis", "Analyze market and make decisions")
        steps = [
            {"agent": "Inference", "action": "analyze", "target": "market",
             "payload": {"topic": "crypto market", "result": "bullish trend detected"}},
            {"agent": "Stratex", "action": "analyze", "target": "portfolio",
             "payload": {"topic": "crypto portfolio", "result": "allocate 30% to BTC"}},
            {"agent": "Cortex", "action": "decision", "target": "strategy",
             "payload": {"decision": "increase crypto allocation", "context": "bullish"}},
            {"agent": "Futuris", "action": "analyze", "target": "forecast",
             "payload": {"topic": "BTC forecast", "result": "bullish for 90 days"}},
            {"agent": "FRIDAY", "action": "share_knowledge", "target": "all",
             "payload": {"topic": "market consensus", "content": "bullish"}},
        ]
        return self.run_simulation(steps)

    def run_security_scenario(self):
        """Run a security incident scenario."""
        self.set_scenario("Security Incident", "Respond to security threats")
        steps = [
            {"agent": "Sentinel", "action": "analyze", "target": "threat",
             "payload": {"topic": "threat alert", "result": "DDoS attack detected"}},
            {"agent": "IntelX", "action": "analyze", "target": "attribution",
             "payload": {"topic": "threat actor", "result": "attributed to APT-42"}},
            {"agent": "Cortex", "action": "decision", "target": "response",
             "payload": {"decision": "activate incident response", "context": "DDoS"}},
            {"agent": "Forge", "action": "analyze", "target": "code",
             "payload": {"topic": "vulnerability", "result": "CVE-2024-1234 found"}},
            {"agent": "FRIDAY", "action": "share_knowledge", "target": "all",
             "payload": {"topic": "security alert", "content": "DDoS + CVE"}},
        ]
        return self.run_simulation(steps)

    def run_content_scenario(self):
        """Run a content creation scenario."""
        self.set_scenario("Content Creation", "Create and distribute content")
        steps = [
            {"agent": "VyralX", "action": "analyze", "target": "topic",
             "payload": {"topic": "AI trends", "result": "viral potential high"}},
            {"agent": "Inference", "action": "analyze", "target": "arguments",
             "payload": {"topic": "AI arguments", "result": "strong pro arguments"}},
            {"agent": "VyralX", "action": "share_knowledge", "target": "content",
             "payload": {"topic": "AI content", "content": "AI is transforming everything"}},
            {"agent": "Cortex", "action": "decision", "target": "publish",
             "payload": {"decision": "publish content", "context": "viral potential"}},
        ]
        return self.run_simulation(steps)

    def get_simulation_report(self) -> dict:
        """Get a report of the last simulation."""
        if not self._steps:
            return {"status": "no_simulation_run"}

        return {
            "scenario": self._scenario,
            "description": getattr(self, "_description", ""),
            "total_steps": len(self._steps),
            "agents_involved": sorted(set(s.agent for s in self._steps)),
            "actions": sorted(set(s.action for s in self._steps)),
            "knowledge_stats": self._kg.get_graph_stats(),
            "conflicts": self._kg.detect_conflicts(),
            "synthesis": self._kg.synthesize_knowledge("market") if self._scenario == "Market Analysis" else self._kg.synthesize_knowledge("threat") if self._scenario == "Security Incident" else self._kg.synthesize_knowledge("content"),
        }

    @property
    def knowledge_graph(self) -> KnowledgeGraph:
        return self._kg


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe Knowledge Graph & Simulator ===\n")

    # Build a knowledge graph
    kg = KnowledgeGraph()
    print("Knowledge Graph:")
    n1 = kg.add_node("entity", "Cryptocurrency", {"type": "asset"}, ["Stratex"])
    n2 = kg.add_node("entity", "Bitcoin", {"type": "crypto"}, ["Stratex", "Inference"])
    n3 = kg.add_node("concept", "Market Trend", {"direction": "bullish"}, ["Inference"])
    n4 = kg.add_node("concept", "Risk Management", {"level": "high"}, ["Cortex"])
    kg.add_edge(n1.node_id, n2.node_id, "includes", {"note": "BTC is a crypto"})
    kg.add_edge(n2.node_id, n3.node_id, "causes", {"note": "BTC drives trends"})
    kg.add_edge(n3.node_id, n4.node_id, "requires", {"note": "bullish requires risk mgmt"})

    stats = kg.get_graph_stats()
    print(f"  Nodes: {stats['total_nodes']}, Edges: {stats['total_edges']}")
    print(f"  By type: {stats['nodes_by_type']}")
    print(f"  By relation: {stats['edges_by_relation']}")

    synthesis = kg.synthesize_knowledge("Bitcoin")
    print(f"  Synthesis: {synthesis['summary']}")

    # Run simulations
    sim = MultiAgentSimulator()
    print("\nSimulations:")

    for scenario_name, scenario_func in [
        ("Market", sim.run_market_scenario),
        ("Security", sim.run_security_scenario),
        ("Content", sim.run_content_scenario),
    ]:
        result = scenario_func()
        print(f"  {scenario_name}: {result['steps']} steps, {result['agents_involved']} agents, {result['knowledge_nodes']} KG nodes")

    print("\nSimulation Report:")
    report = sim.get_simulation_report()
    print(f"  Scenario: {report['scenario']}")
    print(f"  Agents: {report['agents_involved']}")
    print(f"  KG nodes: {report['knowledge_stats']['total_nodes']}")
    print(f"  Conflicts: {len(report['conflicts'])}")

    print("\n=== Knowledge Graph & Simulator Ready ===")
