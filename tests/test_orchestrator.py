"""
tests/test_orchestrator.py — Tests for multi-agent orchestration and event streaming.

Tests orchestration plans, event bus, circuit breaker, consensus engine,
agent health monitoring, and real-time event streaming.

Priority 3-5: Orchestration, Events, Consensus
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

import universe_orchestrator as orch_mod


class TestEventBus:
    """Test the real-time event bus."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bus = orch_mod.EventBus()

    def test_subscribe_publish(self):
        received = []
        self.bus.subscribe("test_event", lambda e: received.append(e))
        self.bus.publish("test_event", "test_source", {"key": "value"})
        assert len(received) == 1
        assert received[0].source == "test_source"

    def test_unsubscribe(self):
        received = []
        sub_id = self.bus.subscribe("test_event", lambda e: received.append(e))
        self.bus.unsubscribe("test_event", sub_id)
        self.bus.publish("test_event", "test_source", {"key": "value"})
        assert len(received) == 0

    def test_event_history(self):
        for i in range(5):
            self.bus.publish("test", f"source_{i}", {"i": i})
        history = self.bus.get_history()
        assert len(history) == 5

    def test_event_history_filter(self):
        self.bus.publish("type_a", "s1", {})
        self.bus.publish("type_b", "s2", {})
        self.bus.publish("type_a", "s3", {})
        history = self.bus.get_history("type_a")
        assert len(history) == 2

    def test_stream_format(self):
        self.bus.publish("test", "s1", {"key": "value"})
        stream = self.bus.stream()
        assert len(stream) == 1
        assert stream[0].startswith("data: ")
        assert "test" in stream[0]

    def test_history_limit(self):
        for i in range(10):
            self.bus.publish("test", f"s{i}", {"i": i})
        history = self.bus.get_history(limit=3)
        assert len(history) == 3


class TestCircuitBreaker:
    """Test the circuit breaker."""

    def test_closed_state(self):
        cb = orch_mod.CircuitBreaker()
        assert cb.state == orch_mod.CircuitBreaker.CLOSED

    def test_opens_after_failures(self):
        cb = orch_mod.CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            try:
                cb.call(lambda: 1/0)
            except Exception:
                pass
        assert cb.state == orch_mod.CircuitBreaker.OPEN

    def test_success_resets_counter(self):
        cb = orch_mod.CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == orch_mod.CircuitBreaker.CLOSED

    def test_half_open_after_timeout(self):
        cb = orch_mod.CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == orch_mod.CircuitBreaker.OPEN
        import time; time.sleep(0.02)
        # Should transition to half-open on next call
        try:
            cb.call(lambda: 1/0)
        except Exception:
            pass
        # Still open because failure
        assert cb.state == orch_mod.CircuitBreaker.OPEN


class TestAgentOrchestrator:
    """Test the agent orchestrator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.orch = orch_mod.AgentOrchestrator()

    def test_create_plan(self):
        plan = self.orch.create_plan(
            "Test Plan", "A test plan",
            tasks=[{"agent": "Inference", "type": "reasoning", "description": "Test"}],
        )
        assert plan.plan_id.startswith("plan_")
        assert len(plan.tasks) == 1

    def test_execute_plan_sequential(self):
        plan = self.orch.create_plan(
            "Test Plan", "A test plan",
            tasks=[
                {"agent": "Inference", "type": "reasoning", "description": "Test1"},
                {"agent": "Cortex", "type": "decision", "description": "Test2"},
            ],
        )
        self.orch.execute_plan(plan.plan_id)
        assert plan.status == "completed"
        assert all(t.status == "completed" for t in plan.tasks)

    def test_execute_plan_fan_out(self):
        plan = self.orch.create_plan(
            "Parallel Plan", "A parallel plan",
            tasks=[
                {"agent": "Inference", "type": "reasoning", "description": "Test1"},
                {"agent": "Cortex", "type": "decision", "description": "Test2"},
                {"agent": "Stratex", "type": "portfolio", "description": "Test3"},
            ],
            fan_out=True,
            fan_in=True,
        )
        self.orch.execute_plan(plan.plan_id)
        assert plan.status == "completed"
        assert plan.aggregated_result is not None
        assert plan.aggregated_result["count"] == 3

    def test_get_all_plans(self):
        self.orch.create_plan("Plan1", "Test", [{"agent": "Inference", "type": "reasoning", "description": "Test"}])
        self.orch.create_plan("Plan2", "Test", [{"agent": "Cortex", "type": "decision", "description": "Test"}])
        assert len(self.orch.get_all_plans()) == 2

    def test_agent_health(self):
        plan = self.orch.create_plan(
            "Health Test", "Test",
            tasks=[{"agent": "Inference", "type": "reasoning", "description": "Test"}],
        )
        self.orch.execute_plan(plan.plan_id)
        health = self.orch.get_agent_health("Inference")
        assert health["status"] == "success"
        assert health["circuit_state"] == "closed"

    def test_event_bus_integration(self):
        received = []
        self.orch.event_bus.subscribe("plan_created", lambda e: received.append(e))
        self.orch.create_plan("Event Test", "Test",
                              tasks=[{"agent": "Inference", "type": "reasoning", "description": "Test"}])
        assert len(received) == 1


class TestConsensusEngine:
    """Test the consensus engine."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.consensus = orch_mod.ConsensusEngine()

    def test_propose_decision(self):
        decision = self.consensus.propose_decision("Test Topic", "FRIDAY", "Test decision")
        assert decision.decision_id.startswith("cons_")
        assert decision.status == "pending"
        assert "FRIDAY" in decision.votes

    def test_vote_approve(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        self.consensus.vote(decision.decision_id, "Cortex", "approve")
        assert decision.voter_count == 2
        assert decision.approver_count == 2

    def test_vote_reject(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        self.consensus.vote(decision.decision_id, "Cortex", "reject")
        assert decision.voter_count == 2
        assert decision.approver_count == 1

    def test_consensus_approved(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        self.consensus.vote(decision.decision_id, "Cortex", "approve")
        self.consensus.vote(decision.decision_id, "Stratex", "approve")
        self.consensus.vote(decision.decision_id, "IntelX", "approve")
        assert decision.status == "approved"

    def test_consensus_rejected(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        self.consensus.vote(decision.decision_id, "Cortex", "reject")
        self.consensus.vote(decision.decision_id, "Stratex", "reject")
        self.consensus.vote(decision.decision_id, "IntelX", "approve")
        assert decision.status == "rejected"

    def test_double_vote_not_allowed(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        result = self.consensus.vote(decision.decision_id, "Cortex", "approve")
        result2 = self.consensus.vote(decision.decision_id, "Cortex", "reject")
        assert result is True
        assert result2 is False

    def test_get_pending_decisions(self):
        decision = self.consensus.propose_decision("Topic", "FRIDAY", "Decision")
        pending = self.consensus.get_pending_decisions()
        assert len(pending) == 1
        assert pending[0].decision_id == decision.decision_id