"""
tests/test_self_improvement.py — Tests for self-improvement, knowledge sharing,
and decision propagation engines.

Priority 5: Make It Real (Self-Improvement, Knowledge Sharing, Decision Propagation)
"""
import sys
import os
import time
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


class TestSelfImprovement:
    """Test the self-improvement engine."""

    def test_detect_issue(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        issue = si.detect_issue("FRIDAY", "performance", "high", "Latency exceeding threshold")
        assert issue.issue_id
        assert issue.agent == "FRIDAY"
        assert issue.category == "performance"
        assert issue.severity == "high"

    def test_create_fix_plan(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        issue = si.detect_issue("FRIDAY", "bug", "critical", "Null pointer exception")
        plan = si.create_fix_plan(issue.issue_id, ["Analyze bug", "Fix code", "Test fix"])
        assert plan.plan_id
        assert plan.issue_id == issue.issue_id
        assert len(plan.steps) == 3

    def test_apply_fix(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        issue = si.detect_issue("Cortex", "logic", "medium", "Incorrect decision logic")
        plan = si.create_fix_plan(issue.issue_id, ["Fix logic"])
        result = si.apply_fix(plan.plan_id)
        assert result["status"] == "applied"

    def test_deploy_fix(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        issue = si.detect_issue("Stratex", "trading", "high", "Loss in trading algorithm")
        plan = si.create_fix_plan(issue.issue_id, ["Fix algorithm"])
        si.apply_fix(plan.plan_id)
        result = si.deploy_fix(plan.plan_id)
        assert result["status"] == "deployed"

    def test_improvement_cycle(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        si.detect_issue("Forge", "build", "medium", "Build failure")
        si.detect_issue("Forge", "test", "low", "Test coverage gap")
        cycle = si.run_improvement_cycle("Forge")
        assert cycle["status"] == "completed"
        assert cycle["issues"] == 2
        assert cycle["plans_applied"] == 2

    def test_improvement_report(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        si.detect_issue("Inference", "accuracy", "high", "Low accuracy")
        issue = si.detect_issue("Memora", "memory", "medium", "Memory leak")
        plan = si.create_fix_plan(issue.issue_id, ["Fix leak"])
        si.apply_fix(plan.plan_id)
        si.deploy_fix(plan.plan_id)
        report = si.get_improvement_report()
        assert report["total_issues"] >= 2
        assert report["total_fix_plans"] >= 1
        assert report["fixes_deployed"] >= 1

    def test_multiple_improvement_cycles(self):
        from universe_self_improvement import AgentSelfImprovement
        si = AgentSelfImprovement()
        for i in range(3):
            si.detect_issue("Cortex", "decision", "medium", f"Issue {i}")
            si.run_improvement_cycle("Cortex")
        report = si.get_improvement_report()
        assert report["improvement_cycles"] >= 3


class TestKnowledgeSharing:
    """Test the knowledge sharing engine."""

    def test_share_knowledge(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        item = ks.share_knowledge("Inference", "Cortex", "pattern", "Bayesian inference works well")
        assert item.item_id
        assert item.source_agent == "Inference"
        assert item.target_agent == "Cortex"

    def test_retrieve_knowledge(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        ks.share_knowledge("Inference", "Cortex", "pattern", "Bayesian inference")
        ks.share_knowledge("Stratex", "Cortex", "market", "Bullish trend")
        ks.share_knowledge("Futuris", "Memora", "forecast", "Economic growth")
        cortex_knowledge = ks.retrieve_knowledge("Cortex")
        assert len(cortex_knowledge) >= 2

    def test_retrieve_by_type(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        ks.share_knowledge("Inference", "Cortex", "pattern", "Bayesian inference")
        ks.share_knowledge("Stratex", "Cortex", "market", "Bullish trend")
        ks.share_knowledge("Futuris", "Cortex", "pattern", "Quantum forecasting")
        pattern_knowledge = ks.retrieve_knowledge("Cortex", ktype="pattern")
        assert len(pattern_knowledge) == 2

    def test_retrieve_by_tags(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        ks.share_knowledge("Inference", "Cortex", "pattern", "Bayesian", ["math", "probability"])
        ks.share_knowledge("Stratex", "Cortex", "market", "Trend", ["finance", "trading"])
        math_knowledge = ks.retrieve_knowledge("Cortex", tags=["math"])
        assert len(math_knowledge) == 1

    def test_broadcast_knowledge(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        items = ks.broadcast_knowledge("Cortex", "strategy", "Risk management priority")
        assert len(items) >= 8  # All 9 other agents
        for item in items:
            assert item.source_agent == "Cortex"
            assert item.target_agent != "Cortex"

    def test_knowledge_graph(self):
        from universe_self_improvement import KnowledgeSharingEngine
        ks = KnowledgeSharingEngine()
        ks.share_knowledge("Inference", "Cortex", "pattern", "Test 1")
        ks.share_knowledge("Stratex", "Futuris", "market", "Test 2")
        ks.broadcast_knowledge("Cortex", "strategy", "Test 3")
        all_knowledge = ks.get_knowledge_graph()
        assert len(all_knowledge) >= 10


class TestDecisionPropagation:
    """Test the decision propagation engine."""

    def test_create_decision(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        decision = dp.create_decision("Cortex", "budget", "Increase budget by 20%", ["Forge", "Inference"])
        assert decision.decision_id
        assert decision.source_agent == "Cortex"
        assert len(decision.impact) == 2

    def test_propagate_decision(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        decision = dp.create_decision("Cortex", "budget", "Increase budget", ["Forge", "Inference"])
        dp.propagate_decision(decision.decision_id)
        assert "Forge" in decision.propagated_to
        assert "Inference" in decision.propagated_to

    def test_propagate_to_specific_agents(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        decision = dp.create_decision("Cortex", "strategy", "New strategy", ["Forge"])
        dp.propagate_decision(decision.decision_id, ["Sentinel", "IntelX"])
        assert "Sentinel" in decision.propagated_to
        assert "IntelX" in decision.propagated_to

    def test_get_decisions_for_agent(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        dec1 = dp.create_decision("Cortex", "budget", "Increase budget", ["Forge"])
        dec2 = dp.create_decision("Stratex", "trading", "New trading rules", ["Forge"])
        dp.propagate_decision(dec1.decision_id)
        dp.propagate_decision(dec2.decision_id)
        forge_decisions = dp.get_decisions_for_agent("Forge")
        assert len(forge_decisions) >= 2

    def test_get_all_decisions(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        dp.create_decision("Cortex", "budget", "Increase budget")
        dp.create_decision("Stratex", "trading", "New rules")
        dp.create_decision("Forge", "build", "New pipeline")
        all_decisions = dp.get_all_decisions()
        assert len(all_decisions) == 3

    def test_decision_propagation_chain(self):
        from universe_self_improvement import DecisionPropagationEngine
        dp = DecisionPropagationEngine()
        # Cortex decides -> affects Forge and Inference
        dec = dp.create_decision("Cortex", "strategy", "Shift to AI-first", ["Forge", "Inference"])
        dp.propagate_decision(dec.decision_id)
        # Forge then makes a decision that affects Sentinel
        dec2 = dp.create_decision("Forge", "build", "New CI pipeline", ["Sentinel"])
        dp.propagate_decision(dec2.decision_id)
        sentinel_decisions = dp.get_decisions_for_agent("Sentinel")
        assert len(sentinel_decisions) == 1
        forge_decisions = dp.get_decisions_for_agent("Forge")
        assert len(forge_decisions) >= 2  # 1 from Cortex + 1 from Forge itself