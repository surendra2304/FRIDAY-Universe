"""
tests/test_swarm_intelligence.py — Tests for swarm intelligence and coordination.

Tests ant colony optimization, particle swarm optimization, distributed
consensus, contract net protocol, blackboard system, and pub/sub bus.

Priority 3-5: Swarm Intelligence, Coordination, Optimization
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

import universe_swarm_intelligence as si_mod


class TestAntColonyOptimizer:
    """Test the ant colony optimizer."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.aco = si_mod.AntColonyOptimizer(["FRIDAY", "Cortex", "Stratex", "Forge"])

    def test_deposit_pheromone(self):
        self.aco.deposit_pheromone("FRIDAY", "Cortex", 0.5)
        ph = self.aco._pheromones["FRIDAY"]["Cortex"]
        assert ph.strength > 1.0

    def test_evaporate(self):
        self.aco.deposit_pheromone("FRIDAY", "Cortex", 1.0)
        before = self.aco._pheromones["FRIDAY"]["Cortex"].strength
        self.aco.evaporate()
        after = self.aco._pheromones["FRIDAY"]["Cortex"].strength
        assert after < before

    def test_choose_path(self):
        path = self.aco.choose_path("FRIDAY", "Forge", length=3)
        assert path[0] == "FRIDAY"
        assert len(path) == 3

    def test_optimize_route(self):
        tasks = [{"from": "FRIDAY", "to": "Forge", "length": 3, "quality": 0.8}]
        paths = self.aco.optimize_route(tasks, iterations=3)
        assert len(paths) == 3

    def test_get_best_edges(self):
        self.aco.deposit_pheromone("FRIDAY", "Cortex", 2.0)
        self.aco.deposit_pheromone("Cortex", "Stratex", 1.5)
        edges = self.aco.get_best_edges(2)
        assert len(edges) == 2
        assert edges[0][2] >= edges[1][2]


class TestParticleSwarmOptimizer:
    """Test the particle swarm optimizer."""

    def test_optimize(self):
        pso = si_mod.ParticleSwarmOptimizer(dimensions=3, particles=5)
        def objective(x):
            return sum((x[i] - 0.5) ** 2 for i in range(len(x)))
        result = pso.optimize(objective, iterations=5)
        assert len(result) == 3
        assert all(0 <= r <= 1 for r in result)

    def test_optimize_finds_optimum(self):
        pso = si_mod.ParticleSwarmOptimizer(dimensions=2, particles=10)
        def objective(x):
            return (x[0] - 0.3) ** 2 + (x[1] - 0.7) ** 2
        result = pso.optimize(objective, iterations=20)
        assert abs(result[0] - 0.3) < 0.1
        assert abs(result[1] - 0.7) < 0.1


class TestDistributedConsensus:
    """Test the distributed consensus protocol."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.consensus = si_mod.DistributedConsensus(
            ["FRIDAY", "Cortex", "Stratex", "Forge", "Sentinel", "IntelX"]
        )

    def test_start_election(self):
        leader = self.consensus.start_election()
        assert leader == ""  # No majority yet
        assert self.consensus.term == 1

    def test_vote_for_leader(self):
        self.consensus.start_election()
        for node in ["FRIDAY", "Cortex", "Stratex", "Forge", "Sentinel"]:
            self.consensus.vote(node, 1)
        assert self.consensus.leader == "FRIDAY"

    def test_append_entry(self):
        self.consensus.start_election()
        for node in ["FRIDAY", "Cortex", "Stratex", "Forge", "Sentinel"]:
            self.consensus.vote(node, 1)
        entry = self.consensus.append_entry("test_value")
        assert entry.index == 0
        assert entry.value == "test_value"

    def test_append_without_leader(self):
        with pytest.raises(Exception):
            self.consensus.append_entry("test")

    def test_commit_entry(self):
        self.consensus.start_election()
        for node in ["FRIDAY", "Cortex", "Stratex", "Forge", "Sentinel"]:
            self.consensus.vote(node, 1)
        entry = self.consensus.append_entry("committed_value")
        self.consensus.commit_entry(entry.index)
        assert self.consensus.get_committed_value(entry.index) == "committed_value"

    def test_get_log_status(self):
        self.consensus.start_election()
        for node in ["FRIDAY", "Cortex", "Stratex", "Forge", "Sentinel"]:
            self.consensus.vote(node, 1)
        entry = self.consensus.append_entry("value1")
        self.consensus.commit_entry(entry.index)
        log = self.consensus.get_log_status()
        assert len(log) == 1
        assert log[0]["committed"] is True


class TestContractNetProtocol:
    """Test the contract net protocol."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.cnp = si_mod.ContractNetProtocol()

    def test_announce_task(self):
        task_id = self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        assert task_id == "task_1"
        assert "task_1" in self.cnp._managers

    def test_submit_bid(self):
        self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        result = self.cnp.submit_bid("Cortex", "task_1", 0.5, ["decision"])
        assert result is True

    def test_submit_bid_unknown_task(self):
        result = self.cnp.submit_bid("Cortex", "unknown", 0.5, [])
        assert result is False

    def test_award_contract(self):
        self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        self.cnp.submit_bid("Cortex", "task_1", 0.5, [])
        result = self.cnp.award_contract("task_1", "Cortex")
        assert result is True

    def test_award_contract_no_bidder(self):
        self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        result = self.cnp.award_contract("task_1", "NonBidder")
        assert result is False

    def test_get_best_bid(self):
        self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        self.cnp.submit_bid("Cortex", "task_1", 0.7, [])
        self.cnp.submit_bid("Stratex", "task_1", 0.4, [])
        best = self.cnp.get_best_bid("task_1")
        assert best["bidder"] == "Stratex"
        assert best["cost"] == 0.4

    def test_get_contracts(self):
        self.cnp.announce_task("FRIDAY", "task_1", "Analyze")
        self.cnp.submit_bid("Cortex", "task_1", 0.5, [])
        self.cnp.award_contract("task_1", "Cortex")
        contracts = self.cnp.get_contracts()
        assert len(contracts) == 1


class TestBlackboardSystem:
    """Test the blackboard system."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bb = si_mod.BlackboardSystem()

    def test_write_read(self):
        self.bb.write("FRIDAY", "key1", "value1")
        assert self.bb.read("key1") == "value1"

    def test_read_default(self):
        assert self.bb.read("nonexistent", "default") == "default"

    def test_write_notification(self):
        notified = []
        self.bb.subscribe("key1", lambda a, k, v: notified.append(v))
        self.bb.write("FRIDAY", "key1", "value1")
        assert len(notified) == 1
        assert notified[0] == "value1"

    def test_get_all(self):
        self.bb.write("FRIDAY", "k1", "v1")
        self.bb.write("Cortex", "k2", "v2")
        all_entries = self.bb.get_all()
        assert len(all_entries) == 2


class TestPublishSubscribeBus:
    """Test the publish-subscribe bus."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ps = si_mod.PublishSubscribeBus()

    def test_subscribe(self):
        sub_id = self.ps.subscribe("topic1", "FRIDAY")
        assert sub_id.startswith("sub_")

    def test_publish(self):
        count = self.ps.publish("topic1", "FRIDAY", "message")
        assert count >= 1

    def test_get_topics(self):
        self.ps.subscribe("topic1", "FRIDAY")
        self.ps.subscribe("topic1", "Cortex")
        self.ps.subscribe("topic2", "Stratex")
        topics = self.ps.get_topics()
        assert "topic1" in topics
        assert len(topics["topic1"]) == 2

    def test_get_messages(self):
        self.ps.publish("topic1", "FRIDAY", "msg1")
        self.ps.publish("topic2", "Cortex", "msg2")
        all_msgs = self.ps.get_messages()
        assert len(all_msgs) == 2
        topic1_msgs = self.ps.get_messages("topic1")
        assert len(topic1_msgs) == 1

    def test_get_messages_limit(self):
        for i in range(10):
            self.ps.publish("topic", "FRIDAY", f"msg{i}")
        msgs = self.ps.get_messages(limit=3)
        assert len(msgs) == 3


class TestSwarmIntelligenceManager:
    """Test the unified swarm intelligence manager."""

    def test_init(self):
        swarm = si_mod.SwarmIntelligenceManager()
        assert len(swarm.agents) >= 10

    def test_components(self):
        swarm = si_mod.SwarmIntelligenceManager()
        assert swarm.ant_colony is not None
        assert swarm.particle_swarm is not None
        assert swarm.consensus is not None
        assert swarm.contract_net is not None
        assert swarm.blackboard is not None
        assert swarm.pubsub is not None

    def test_full_pipeline(self):
        swarm = si_mod.SwarmIntelligenceManager()
        # ACO
        paths = swarm.ant_colony.optimize_route(
            [{"from": "FRIDAY", "to": "Cortex", "length": 3}], iterations=2)
        assert len(paths) == 2
        # PSO
        result = swarm.particle_swarm.optimize(lambda x: sum(x), iterations=3)
        assert len(result) >= 1
        # Consensus
        swarm.consensus.start_election()
        for node in swarm.agents:
            swarm.consensus.vote(node, 1)
        assert swarm.consensus.leader == "FRIDAY"
        # Contract net
        swarm.contract_net.announce_task("FRIDAY", "t1", "test")
        swarm.contract_net.submit_bid("Cortex", "t1", 0.5, [])
        assert swarm.contract_net.get_best_bid("t1")["bidder"] == "Cortex"