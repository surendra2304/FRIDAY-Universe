"""
tests/test_cross_reasoning.py — Tests for cross-agent reasoning and self-learning.

Tests Theory of Mind, metacognition, analogy, counterfactual reasoning,
debate, and agent self-learning from experiences.

Priority 3-5: Reasoning, Learning, Self-Improvement
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

import universe_cross_reasoning as cr_mod


class TestTheoryOfMind:
    """Test the Theory of Mind module."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tom = cr_mod.TheoryOfMind()

    def test_observe(self):
        state = self.tom.observe("FRIDAY", "Cortex", "invest in crypto", "maximize returns", "buy")
        assert "invest in crypto" in state.beliefs
        assert "maximize returns" in state.desires
        assert "buy" in state.intentions

    def test_get_state(self):
        self.tom.observe("FRIDAY", "Cortex", "invest")
        state = self.tom.get_state("FRIDAY", "Cortex")
        assert state.agent == "Cortex"
        assert len(state.beliefs) >= 1

    def test_get_state_empty(self):
        state = self.tom.get_state("FRIDAY", "UnknownAgent")
        assert state.agent == "UnknownAgent"
        assert state.beliefs == []

    def test_predict_action_intention(self):
        self.tom.observe("FRIDAY", "Cortex", "belief", "desire", "intention")
        prediction = self.tom.predict_action("FRIDAY", "Cortex")
        assert "intention" in prediction

    def test_predict_action_desire(self):
        self.tom.observe("FRIDAY", "Cortex", "belief", "desire", "")
        prediction = self.tom.predict_action("FRIDAY", "Cortex")
        assert "desire" in prediction.lower()

    def test_predict_action_unknown(self):
        prediction = self.tom.predict_action("FRIDAY", "UnknownAgent")
        assert "unknown" in prediction.lower()

    def test_shared_beliefs(self):
        self.tom.observe("FRIDAY", "Cortex", "crypto is good")
        self.tom.observe("Stratex", "Cortex", "crypto is good")
        self.tom.observe("FRIDAY", "Forge", "code is good")
        shared = self.tom.get_shared_beliefs(["FRIDAY", "Stratex"])
        assert "crypto is good" in shared

    def test_multiple_observations(self):
        self.tom.observe("FRIDAY", "Cortex", "belief1")
        self.tom.observe("FRIDAY", "Cortex", "belief2")
        state = self.tom.get_state("FRIDAY", "Cortex")
        assert len(state.beliefs) == 2


class TestCrossAgentReasoner:
    """Test the cross-agent reasoner."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.reasoner = cr_mod.CrossAgentReasoner()

    def test_metacognition(self):
        step = self.reasoner.reason_metacognition("FRIDAY", "market", "initial reasoning")
        assert step.reasoning_type == "metacognition"
        assert step.agent == "FRIDAY"
        assert len(step.conclusion) > 0

    def test_theory_of_mind_reasoning(self):
        step = self.reasoner.reason_theory_of_mind("FRIDAY", "Cortex", "belief")
        assert step.reasoning_type == "theory_of_mind"
        assert step.agent == "FRIDAY"

    def test_analogy(self):
        step = self.reasoner.reason_analogy("Cortex", "stocks", "crypto", "treat similarly")
        assert step.reasoning_type == "analogy"
        assert step.agent == "Cortex"

    def test_counterfactual(self):
        step = self.reasoner.reason_counterfactual("Futuris", "premise", "alternative")
        assert step.reasoning_type == "counterfactual"
        assert step.agent == "Futuris"

    def test_reasoning_chain(self):
        self.reasoner.reason_metacognition("FRIDAY", "topic", "reasoning")
        self.reasoner.reason_analogy("Cortex", "a", "b", "c")
        chain = self.reasoner.get_reasoning_chain()
        assert len(chain) == 2

    def test_reasoning_chain_filter(self):
        self.reasoner.reason_metacognition("FRIDAY", "topic", "reasoning")
        self.reasoner.reason_analogy("Cortex", "a", "b", "c")
        chain = self.reasoner.get_reasoning_chain("FRIDAY")
        assert len(chain) == 1
        assert chain[0].agent == "FRIDAY"

    def test_debate(self):
        debate = self.reasoner.debate("topic", "position", ["FRIDAY", "Cortex"], rounds=2)
        assert debate["topic"] == "topic"
        assert len(debate["rounds"]) == 2
        assert len(debate["rounds"][0]["statements"]) == 2

    def test_debate_multiple_rounds(self):
        debate = self.reasoner.debate("topic", "position", ["FRIDAY", "Cortex", "Sentinel"], rounds=3)
        assert len(debate["rounds"]) == 3
        for r in debate["rounds"]:
            assert len(r["statements"]) == 3

    def test_get_debates(self):
        self.reasoner.debate("t1", "p1", ["FRIDAY"])
        self.reasoner.debate("t2", "p2", ["Cortex"])
        assert len(self.reasoner.get_debates()) == 2


class TestAgentSelfLearner:
    """Test the agent self-learner."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.learner = cr_mod.AgentSelfLearner()

    def test_record_experience(self):
        exp = self.learner.record_experience("FRIDAY", "situation", "action", "outcome", 0.8)
        assert exp.agent == "FRIDAY"
        assert exp.reward == 0.8

    def test_recommend_action(self):
        self.learner.record_experience("FRIDAY", "market crash", "increase cash", "good", 0.8)
        rec = self.learner.recommend_action("FRIDAY", "market crash")
        assert rec == "increase cash"

    def test_recommend_action_unknown(self):
        rec = self.learner.recommend_action("FRIDAY", "unknown situation")
        assert "unknown" in rec.lower()

    def test_recommend_action_similar(self):
        self.learner.record_experience("FRIDAY", "market crash scenario", "increase cash", "good", 0.7)
        rec = self.learner.recommend_action("FRIDAY", "market crash")
        assert rec == "increase cash"

    def test_get_agent_policy(self):
        self.learner.record_experience("FRIDAY", "s1", "a1", "o1", 0.5)
        self.learner.record_experience("FRIDAY", "s1", "a2", "o2", -0.5)
        policy = self.learner.get_agent_policy("FRIDAY")
        assert len(policy) == 2

    def test_get_lessons(self):
        self.learner.record_experience("FRIDAY", "s", "a1", "good", 0.8)
        self.learner.record_experience("FRIDAY", "s", "a2", "bad", -0.8)
        lessons = self.learner.get_lessons("FRIDAY")
        assert len(lessons) == 2

    def test_learning_report_agent(self):
        self.learner.record_experience("FRIDAY", "s1", "a1", "o1", 0.5)
        self.learner.record_experience("FRIDAY", "s2", "a2", "o2", 0.7)
        report = self.learner.get_learning_report("FRIDAY")
        assert report["agent"] == "FRIDAY"
        assert report["experiences"] == 2
        assert report["average_reward"] > 0

    def test_learning_report_all(self):
        self.learner.record_experience("FRIDAY", "s1", "a1", "o1", 0.5)
        self.learner.record_experience("Cortex", "s2", "a2", "o2", 0.7)
        report = self.learner.get_learning_report()
        assert report["agents"] == 2
        assert report["total_experiences"] == 2