"""
tests/test_integration.py — FRIDAY Universe Cross-Agent Integration Tests.

Tests that verify cross-agent communication, mesh health, context sharing,
adaptive routing, error handling, self-improvement, and memory consolidation
all work together.
"""
import pytest
import time


class TestMeshHealth:
    """Test mesh health monitoring."""

    def test_health_monitor_initializes(self):
        from mesh.universe_health import UniverseHealthMonitor, AGENT_REGISTRY
        monitor = UniverseHealthMonitor()
        assert len(AGENT_REGISTRY) == 10  # All 10 agents

    def test_agent_health_check(self):
        from mesh.universe_health import UniverseHealthMonitor, AGENT_REGISTRY
        monitor = UniverseHealthMonitor()
        # Will fail gracefully since agents aren't running
        import asyncio
        health = asyncio.run(monitor.check_agent("friday", AGENT_REGISTRY["friday"]))
        assert health.agent == "friday"
        assert health.status in ("healthy", "degraded", "offline")

    def test_mesh_health_aggregates(self):
        from mesh.universe_health import UniverseHealthMonitor
        monitor = UniverseHealthMonitor()
        import asyncio
        mesh = asyncio.run(monitor.check_all_agents())
        assert mesh.total_agents == 10
        assert mesh.mesh_health in ("healthy", "degraded", "critical")


class TestUniverseStatus:
    """Test universe status dashboard."""

    def test_status_dashboard_initializes(self):
        from mesh.universe_status import UniverseStatusDashboard
        dashboard = UniverseStatusDashboard()
        assert dashboard._status == {}

    def test_status_collection(self):
        from mesh.universe_status import UniverseStatusDashboard
        dashboard = UniverseStatusDashboard()
        import asyncio
        asyncio.run(dashboard.collect_agent_status("friday", "http://localhost:10000"))
        assert "friday" in dashboard._status

    def test_status_report(self):
        from mesh.universe_status import UniverseStatusDashboard
        dashboard = UniverseStatusDashboard()
        import asyncio
        status = asyncio.run(dashboard.get_full_status())
        assert "universe" in status
        assert "agents" in status
        assert "topology" in status


class TestCrossAgentContext:
    """Test cross-agent context sharing."""

    def test_share_context(self):
        from mesh.cross_agent_context import CrossAgentContextEngine
        engine = CrossAgentContextEngine()
        share = engine.share_context(
            from_agent="stratex",
            to_agent="futuris",
            content="Market data: BTC trending up",
            category="knowledge",
            importance=0.8,
        )
        assert share.from_agent == "stratex"
        assert share.to_agent == "futuris"
        assert share.shared_at > 0

    def test_broadcast_context(self):
        from mesh.cross_agent_context import CrossAgentContextEngine
        engine = CrossAgentContextEngine()
        shares = engine.broadcast_context(
            from_agent="friday",
            content="System alert: high load on Forge",
            category="alert",
        )
        assert len(shares) == 9  # All agents except sender

    def test_context_graph(self):
        from mesh.cross_agent_context import CrossAgentContextEngine
        engine = CrossAgentContextEngine()
        engine.share_context("a", "b", "test", "knowledge", 0.5)
        engine.share_context("b", "c", "test2", "knowledge", 0.7)
        graph = engine.get_context_graph()
        assert "a" in graph.nodes
        assert "b" in graph.nodes
        assert "c" in graph.nodes

    def test_context_impact(self):
        from mesh.cross_agent_context import CrossAgentContextEngine
        engine = CrossAgentContextEngine()
        for i in range(5):
            engine.share_context("agent1", "agent2", f"content {i}", "knowledge", 0.6)
        impact = engine.assess_impact("agent1", "agent2")
        assert impact.shares_count == 5
        assert impact.knowledge_gain > 0

    def test_context_request_fulfill(self):
        from mesh.cross_agent_context import CrossAgentContextEngine
        engine = CrossAgentContextEngine()
        request = engine.request_context("cortex", "intelx", "market research")
        engine.fulfill_request(request.request_id, "Research results here")
        assert request.status == "fulfilled"
        assert request.fulfilled_content == "Research results here"


class TestAdaptiveRouter:
    """Test adaptive task routing."""

    def test_register_agents(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("stratex", ["trading", "analysis"])
        router.register_agent("forge", ["code", "testing"])
        router.register_agent("vyralx", ["content", "youtube"])
        assert len(router._agents) == 3

    def test_route_task_by_capability(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("stratex", ["trading", "analysis"])
        router.register_agent("forge", ["code", "testing"])
        decision = router.route_task("trading")
        assert decision.selected_agent == "stratex"
        assert decision.score > 0

    def test_route_task_by_load(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("agent_a", ["task"])
        router.register_agent("agent_b", ["task"])
        router.update_agent_status("agent_a", "online", 0.9, 8, 0.5)
        router.update_agent_status("agent_b", "online", 0.1, 1, 0.8)
        decision = router.route_task("task")
        assert decision.selected_agent == "agent_b"  # Lower load wins

    def test_route_with_no_available(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("offline_agent", ["task"])
        router.update_agent_status("offline_agent", "offline", 0.0, 0, 0.0)
        decision = router.route_task("task")
        assert decision.selected_agent == ""

    def test_record_result_updates_success_rate(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("agent", ["task"])
        decision = router.route_task("task")
        for _ in range(5):
            router.record_result(decision.task_id, "success")
        capability = router._agents["agent"]
        assert capability.success_rate > 0.5

    def test_routing_report(self):
        from mesh.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.register_agent("agent", ["task"])
        router.route_task("task")
        report = router.get_routing_report()
        assert "total_routed" in report
        assert "agent_stats" in report


class TestUnifiedErrors:
    """Test unified error handling."""

    def test_error_catalog_complete(self):
        from mesh.unified_errors import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        catalog = handler.get_error_catalog()
        assert "AUTH_INVALID_KEY" in catalog
        assert "RESOURCE_NOT_FOUND" in catalog
        assert "MESH_AGENT_OFFLINE" in catalog
        assert "TRADE_RISK_LIMIT" in catalog
        assert len(catalog) > 30

    def test_create_error_envelope(self):
        from mesh.unified_errors import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        envelope = handler.create_error("agent", "RESOURCE_NOT_FOUND")
        result = envelope.to_dict()
        assert result["status"] == "error"
        assert result["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert "metadata" in result

    def test_create_success_envelope(self):
        from mesh.unified_errors import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        envelope = handler.create_success({"result": "ok"})
        result = envelope.to_dict()
        assert result["status"] == "success"
        assert result["data"]["result"] == "ok"

    def test_error_logging(self):
        from mesh.unified_errors import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        for _ in range(5):
            handler.create_error("agent", "AUTH_INVALID_KEY")
        logs = handler.get_error_logs()
        assert len(logs) >= 5

    def test_error_stats(self):
        from mesh.unified_errors import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        handler.create_error("a", "AUTH_INVALID_KEY")
        handler.create_error("b", "RESOURCE_NOT_FOUND")
        stats = handler.get_error_stats()
        assert stats["total_errors"] == 2


class TestSelfImprovement:
    """Test self-improvement loop."""

    def test_detect_issue(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        issue = engine.detect_issue(
            source="sentinel",
            severity="high",
            category="security",
            description="Vulnerability in dependency",
            file_path="test.py",
        )
        assert issue.status == "open"
        assert issue.severity == "high"

    def test_create_fix_plan(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        issue = engine.detect_issue("sentinel", "high", "security", "test issue")
        plan = engine.create_fix_plan(issue.issue_id, ["step1", "step2"], 2.0)
        assert plan.issue_id == issue.issue_id
        assert len(plan.steps) == 2

    def test_apply_fix(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        issue = engine.detect_issue("forge", "high", "bug", "test bug")
        plan = engine.create_fix_plan(issue.issue_id, ["fix"], 1.0)
        result = engine.apply_fix(issue.issue_id, plan.plan_id, ["changed code"], True)
        assert result.status == "success"
        assert issue.status == "verified"

    def test_apply_fix_failed(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        issue = engine.detect_issue("forge", "high", "bug", "test bug")
        plan = engine.create_fix_plan(issue.issue_id, ["fix"], 1.0)
        result = engine.apply_fix(issue.issue_id, plan.plan_id, ["changed code"], False)
        assert result.status == "failed"
        assert issue.status == "failed"

    def test_deploy_fix(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        issue = engine.detect_issue("forge", "medium", "bug", "test")
        plan = engine.create_fix_plan(issue.issue_id, ["fix"], 1.0)
        engine.apply_fix(issue.issue_id, plan.plan_id, ["changes"], True)
        result = engine.deploy_fix(issue.issue_id)
        assert result["status"] == "deployed"

    def test_auto_improvement_cycle(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        result = engine.run_auto_improvement()
        assert "cycle" in result
        assert result["cycle"]["issues_detected"] >= 2
        assert result["cycle"]["issues_deployed"] >= 2

    def test_improvement_report(self):
        from mesh.self_improvement_loop import SelfImprovementEngine
        engine = SelfImprovementEngine()
        engine.run_auto_improvement()
        report = engine.get_improvement_report()
        assert report["total_cycles"] >= 1
        assert report["total_fixed"] >= 2


class TestAutomatedConsolidation:
    """Test automated memory consolidation."""

    def test_add_memory(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        memory = engine.add_memory("m1", "content here", "namespace1")
        assert memory.memory_id == "m1"

    def test_find_duplicates(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        engine.add_memory("m1", "the quick brown fox jumps over the lazy dog", "ns")
        engine.add_memory("m2", "the quick brown fox jumps over the lazy dog", "ns")
        groups = engine.find_duplicates()
        assert len(groups) == 1
        assert groups[0].similarity > 0.9

    def test_find_stale(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        # Add old memory
        memory = engine.add_memory("m1", "old content", "ns", importance=0.2)
        memory.timestamp = time.time() - 90 * 86400  # 90 days ago
        stale = engine.find_stale(max_age_days=30.0)
        assert len(stale) >= 1

    def test_find_conflicts(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        engine.add_memory("m1", "the market always goes up", "ns", importance=0.8)
        engine.add_memory("m2", "the market never goes up", "ns", importance=0.3)
        conflicts = engine.find_conflicts()
        assert len(conflicts) >= 1

    def test_run_consolidation(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        engine.add_memory("m1", "the quick brown fox", "ns")
        engine.add_memory("m2", "the quick brown fox", "ns")
        result = engine.run_consolidation()
        assert result["report"]["duplicates_found"] >= 1

    def test_consolidation_report(self):
        from mesh.automated_consolidation import AutomatedConsolidationEngine
        engine = AutomatedConsolidationEngine()
        engine.run_consolidation()
        report = engine.get_consolidation_report()
        assert "total_memories" in report
        assert "duplicates_found" in report


class TestEndToEndIntegration:
    """Test that all mesh modules work together."""

    def test_all_mesh_modules_importable(self):
        """Verify all mesh modules can be imported."""
        from mesh.universe_health import UniverseHealthMonitor
        from mesh.universe_status import UniverseStatusDashboard
        from mesh.cross_agent_context import CrossAgentContextEngine
        from mesh.adaptive_router import AdaptiveRouter
        from mesh.unified_errors import UnifiedErrorHandler
        from mesh.self_improvement_loop import SelfImprovementEngine
        from mesh.automated_consolidation import AutomatedConsolidationEngine

        # Verify all can instantiate
        UniverseHealthMonitor()
        UniverseStatusDashboard()
        CrossAgentContextEngine()
        AdaptiveRouter()
        UnifiedErrorHandler()
        SelfImprovementEngine()
        AutomatedConsolidationEngine()

    def test_cross_module_workflow(self):
        """Test a workflow spanning multiple mesh modules."""
        from mesh.adaptive_router import AdaptiveRouter
        from mesh.cross_agent_context import CrossAgentContextEngine
        from mesh.unified_errors import UnifiedErrorHandler
        from mesh.self_improvement_loop import SelfImprovementEngine

        router = AdaptiveRouter()
        context = CrossAgentContextEngine()
        errors = UnifiedErrorHandler()
        improvement = SelfImprovementEngine()

        # Register agents
        router.register_agent("stratex", ["trading"])
        router.register_agent("futuris", ["prediction"])

        # Route a task
        decision = router.route_task("trading")
        assert decision.selected_agent == "stratex"

        # Share context from the result
        context.share_context(
            "stratex", "futuris",
            "Market analysis: BTC bullish",
            "knowledge", 0.8,
        )

        # Record result
        router.record_result(decision.task_id, "success")

        # Detect improvement opportunity
        issue = improvement.detect_issue("monitoring", "low", "optimization", "Consider ensemble")
        plan = improvement.create_fix_plan(issue.issue_id, ["test ensemble"], 1.0)
        improvement.apply_fix(issue.issue_id, plan.plan_id, ["added ensemble"], True)

        # All modules should work together without errors
        assert router.get_routing_report()["total_routed"] >= 1
        assert context.get_context_report()["total_shares"] >= 1
        assert errors.get_error_stats()["total_errors"] == 0
        assert improvement.get_improvement_report()["total_fixed"] >= 1
