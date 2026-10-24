"""
tests/test_knowledge_graph.py — Tests for knowledge graph and multi-agent simulation.

Tests node/edge management, querying, conflict detection, synthesis,
graph statistics, and multi-agent simulation scenarios.

Priority 3-5: Knowledge Graph, Simulation, Integration
"""
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

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

import universe_knowledge_graph as kg_mod


class TestKnowledgeGraph:
    """Test the knowledge graph."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.kg = kg_mod.KnowledgeGraph()

    def test_add_node(self):
        node = self.kg.add_node("entity", "TestEntity", {"key": "value"})
        assert node.node_id.startswith("node_")
        assert node.node_type == "entity"
        assert node.label == "TestEntity"

    def test_add_edge(self):
        n1 = self.kg.add_node("entity", "A", {})
        n2 = self.kg.add_node("entity", "B", {})
        edge = self.kg.add_edge(n1.node_id, n2.node_id, "related_to")
        assert edge.edge_id.startswith("edge_")
        assert edge.relation == "related_to"

    def test_add_edge_invalid_node(self):
        with pytest.raises(ValueError):
            self.kg.add_edge("nonexistent", "also_nonexistent", "related_to")

    def test_query_node(self):
        self.kg.add_node("entity", "Cryptocurrency", {})
        self.kg.add_node("entity", "Bitcoin", {})
        self.kg.add_node("concept", "Market", {})
        results = self.kg.query_node("crypto")
        assert len(results) == 1
        assert results[0].label == "Cryptocurrency"

    def test_query_by_type(self):
        self.kg.add_node("entity", "Cryptocurrency", {})
        self.kg.add_node("concept", "Market", {})
        results = self.kg.query_node("cryptocurrency", "entity")
        assert len(results) == 1
        results_type = self.kg.query_node("market", "entity")
        assert len(results_type) == 0

    def test_query_by_agent(self):
        self.kg.add_node("entity", "A", {}, source_agents=["Cortex"])
        self.kg.add_node("entity", "B", {}, source_agents=["Stratex"])
        cortex_nodes = self.kg.query_by_agent("Cortex")
        assert len(cortex_nodes) == 1
        assert cortex_nodes[0].label == "A"

    def test_find_related(self):
        n1 = self.kg.add_node("entity", "A", {})
        n2 = self.kg.add_node("entity", "B", {})
        n3 = self.kg.add_node("entity", "C", {})
        self.kg.add_edge(n1.node_id, n2.node_id, "related_to")
        self.kg.add_edge(n2.node_id, n3.node_id, "related_to")
        related = self.kg.find_related(n1.node_id, depth=2)
        assert len(related) == 2

    def test_detect_conflicts(self):
        n1 = self.kg.add_node("concept", "Idea1", {})
        n2 = self.kg.add_node("concept", "Idea2", {})
        self.kg.add_edge(n1.node_id, n2.node_id, "contradicts")
        conflicts = self.kg.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["node_a"] == "Idea1"
        assert conflicts[0]["node_b"] == "Idea2"

    def test_no_conflicts(self):
        n1 = self.kg.add_node("concept", "Idea1", {})
        n2 = self.kg.add_node("concept", "Idea2", {})
        self.kg.add_edge(n1.node_id, n2.node_id, "related_to")
        conflicts = self.kg.detect_conflicts()
        assert len(conflicts) == 0

    def test_synthesize_knowledge(self):
        self.kg.add_node("entity", "Bitcoin", {}, source_agents=["Stratex"])
        n2 = self.kg.add_node("concept", "Market", {}, source_agents=["Inference"])
        self.kg.add_edge(self.kg.query_node("Bitcoin")[0].node_id, n2.node_id, "related_to")
        synthesis = self.kg.synthesize_knowledge("Bitcoin")
        assert synthesis["nodes"] >= 1
        assert "Stratex" in synthesis["contributing_agents"]

    def test_graph_stats(self):
        n1 = self.kg.add_node("entity", "A", {})
        n2 = self.kg.add_node("concept", "B", {})
        self.kg.add_edge(n1.node_id, n2.node_id, "related_to")
        stats = self.kg.get_graph_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["nodes_by_type"]["entity"] == 1
        assert stats["nodes_by_type"]["concept"] == 1


class TestMultiAgentSimulator:
    """Test the multi-agent simulator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.sim = kg_mod.MultiAgentSimulator()

    def test_step(self):
        step = self.sim.step("FRIDAY", "execute", "target", {"key": "value"})
        assert step.step_id == 0
        assert step.agent == "FRIDAY"
        assert step.action == "execute"

    def test_run_simulation(self):
        steps = [
            {"agent": "FRIDAY", "action": "execute", "target": "test", "payload": {}},
            {"agent": "Cortex", "action": "execute", "target": "test", "payload": {}},
        ]
        result = self.sim.run_simulation(steps)
        assert result["steps"] == 2
        assert result["completed"] is True
        assert "FRIDAY" in result["agents_involved"]

    def test_run_market_scenario(self):
        result = self.sim.run_market_scenario()
        assert result["steps"] >= 4
        assert "Inference" in result["agents_involved"]
        assert "Stratex" in result["agents_involved"]

    def test_run_security_scenario(self):
        result = self.sim.run_security_scenario()
        assert result["steps"] >= 4
        assert "Sentinel" in result["agents_involved"]
        assert "IntelX" in result["agents_involved"]

    def test_run_content_scenario(self):
        result = self.sim.run_content_scenario()
        assert result["steps"] >= 3
        assert "VyralX" in result["agents_involved"]

    def test_simulation_report(self):
        self.sim.run_market_scenario()
        report = self.sim.get_simulation_report()
        assert report["scenario"] == "Market Analysis"
        assert report["total_steps"] >= 4
        assert "knowledge_stats" in report
        assert "conflicts" in report

    def test_add_agent(self):
        self.sim.add_agent("NewAgent")
        assert "NewAgent" in self.sim._agents

    def test_knowledge_graph_integration(self):
        self.sim.step("Inference", "analyze", "market", {"topic": "crypto", "result": "bullish"})
        stats = self.sim.knowledge_graph.get_graph_stats()
        assert stats["total_nodes"] >= 1
