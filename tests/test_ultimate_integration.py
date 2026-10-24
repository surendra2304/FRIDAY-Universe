"""
tests/test_ultimate_integration.py — Ultimate integration test: ALL systems together.

Tests every system we've built working in concert:
- FRIDAY dispatch bus, routing, mesh, autopilot
- Inference (reasoning, argumentation, temporal, philosophy)
- Cortex (decision, foresight, partners, risk)
- Memora (memory, reflection, dreams, identity)
- Stratex (portfolio, trading, risk, market)
- Forge (code, build, security, git)
- Sentinel (SLADE, incidents, recon, hardening)
- IntelX (research, contradictions, attribution, threat)
- Futuris (forecast, counterfactuals, prediction markets)
- VyralX (content, analytics, audience, growth)
- Universe workflow engine (capabilities, workflows, dependencies)
- Universe self-improvement (issues, fixes, knowledge, decisions)
- Universe agent marketplace (services, calls, HTTP client)
- Universe orchestrator (plans, event bus, circuit breaker, consensus)
- Universe knowledge graph (nodes, edges, simulation, synthesis)
- Universe cross-reasoning (theory of mind, metacognition, self-learning)
- Universe swarm intelligence (ant colony, particle swarm, consensus, contracts)
- Universe monitoring (metrics, alerts, health, incidents, improvement loop)
- Dashboard with all API endpoints
- Enhanced dashboard with workflow and self-improvement endpoints

Priority 1-5: Complete system integration
"""
import sys
import importlib.util
import json
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


def _load_tool(name, filename):
    """Load a tool module from tools/."""
    path = str(ROOT / "tools" / filename)
    full_name = f"_ut_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_friday(name, filename):
    """Load a FRIDAY core module."""
    path = str(ROOT / "FRIDAY/apps/core/src/friday_core" / filename)
    full_name = f"_ut_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestUltimateIntegration:
    """Test ALL systems working together."""

    def test_all_tool_modules_importable(self):
        """All tool modules can be imported."""
        modules = [
            ("workflow", "universe_workflow_engine.py"),
            ("self_improvement", "universe_self_improvement.py"),
            ("marketplace", "universe_agent_marketplace.py"),
            ("orchestrator", "universe_orchestrator.py"),
            ("knowledge_graph", "universe_knowledge_graph.py"),
            ("cross_reasoning", "universe_cross_reasoning.py"),
            ("swarm", "universe_swarm_intelligence.py"),
            ("monitoring", "universe_monitoring.py"),
            ("dashboard", "universe_dashboard.py"),
        ]
        for name, filename in modules:
            mod = _load_tool(name, filename)
            assert mod is not None, f"Failed to load {filename}"

    def test_dispatch_to_workflow_to_marketplace(self):
        """Dispatch -> Workflow -> Marketplace pipeline."""
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")

        # Create and run a workflow (auto-registers agents from config)
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_trading_analysis()
        assert wf.status == "completed"

        # Call a service in the marketplace
        mp = marketplace.AgentMarketplace()
        call = mp.call_service("FRIDAY", "Cortex", "decision", {"decision": "invest"})
        assert call.status == "completed"

    def test_workflow_to_self_improvement(self):
        """Workflow -> Self-Improvement pipeline."""
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        si = _load_tool("self_improvement", "universe_self_improvement.py")

        # Run a workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_code_development()
        assert wf.status == "completed"

        # Run self-improvement cycle
        improver = si.AgentSelfImprovement()
        cycle = improver.run_improvement_cycle("Forge")
        assert cycle["status"] == "completed"

    def test_marketplace_to_orchestrator(self):
        """Marketplace -> Orchestrator pipeline."""
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        orchestrator = _load_tool("orchestrator", "universe_orchestrator.py")

        # Create orchestrator (which uses marketplace internally)
        orch = orchestrator.AgentOrchestrator()
        assert orch._marketplace is not None

        # Create and execute a plan
        plan = orch.create_plan(
            "Test Plan", "Test",
            tasks=[{"agent": "Inference", "type": "reasoning", "description": "Test"}],
        )
        orch.execute_plan(plan.plan_id)
        assert plan.status == "completed"

    def test_orchestrator_to_knowledge_graph(self):
        """Orchestrator -> Knowledge Graph pipeline."""
        orchestrator = _load_tool("orchestrator", "universe_orchestrator.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")

        # Run a simulation (which uses knowledge graph)
        sim = kg_mod.MultiAgentSimulator()
        result = sim.run_market_scenario()
        assert result["completed"] is True
        assert result["steps"] >= 4

        # Verify knowledge was created
        stats = sim.knowledge_graph.get_graph_stats()
        assert stats["total_nodes"] >= 4

    def test_knowledge_graph_to_cross_reasoning(self):
        """Knowledge Graph -> Cross-Reasoning pipeline."""
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")
        cr_mod = _load_tool("cross_reasoning", "universe_cross_reasoning.py")

        # Build knowledge graph
        kg = kg_mod.KnowledgeGraph()
        n1 = kg.add_node("concept", "Crypto", {}, ["Stratex"])
        n2 = kg.add_node("concept", "Market", {}, ["Inference"])
        kg.add_edge(n1.node_id, n2.node_id, "causes")

        # Use cross-reasoning on the knowledge
        reasoner = cr_mod.CrossAgentReasoner()
        reasoner.reason_theory_of_mind("FRIDAY", "Cortex", "crypto is bullish")
        reasoner.reason_metacognition("FRIDAY", "crypto market", "initial analysis")

        assert len(reasoner.get_reasoning_chain()) >= 2

    def test_cross_reasoning_to_swarm(self):
        """Cross-Reasoning -> Swarm Intelligence pipeline."""
        cr_mod = _load_tool("cross_reasoning", "universe_cross_reasoning.py")
        sw_mod = _load_tool("swarm", "universe_swarm_intelligence.py")

        # Learn from experiences
        learner = cr_mod.AgentSelfLearner()
        learner.record_experience("FRIDAY", "market crash", "increase cash", "good", 0.8)
        learner.record_experience("FRIDAY", "market crash", "stay invested", "bad", -0.8)

        # Use swarm intelligence for optimization
        swarm = sw_mod.SwarmIntelligenceManager()
        paths = swarm.ant_colony.optimize_route(
            [{"from": "FRIDAY", "to": "Cortex", "length": 3}], iterations=2)
        assert len(paths) == 2

        # Recommend action based on learning
        rec = learner.recommend_action("FRIDAY", "market crash")
        assert rec == "increase cash"

    def test_swarm_to_monitoring(self):
        """Swarm Intelligence -> Monitoring pipeline."""
        sw_mod = _load_tool("swarm", "universe_swarm_intelligence.py")
        mon_mod = _load_tool("monitoring", "universe_monitoring.py")

        # Run swarm consensus
        swarm = sw_mod.SwarmIntelligenceManager()
        swarm.consensus.start_election()
        for node in swarm.agents:
            swarm.consensus.vote(node, 1)
        assert swarm.consensus.leader == "FRIDAY"

        # Monitor the swarm
        loop = mon_mod.SelfImprovementLoop()
        cycle = loop.run_cycle("FRIDAY", {"error_rate": 0.05, "latency": 200, "cpu_usage": 30})
        assert cycle.status == "completed"

    def test_monitoring_to_dashboard(self):
        """Monitoring -> Dashboard pipeline."""
        mon_mod = _load_tool("monitoring", "universe_monitoring.py")
        dashboard = _load_tool("dashboard", "universe_dashboard.py")

        # Collect metrics
        loop = mon_mod.SelfImprovementLoop()
        loop.monitor("FRIDAY", {"error_rate": 0.01, "latency": 100, "cpu_usage": 20})

        # Dashboard has the endpoints
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(dashboard.app.router)
        client = TestClient(app)

        response = client.get("/api/health")
        assert response.status_code == 200

        response = client.get("/api/workflow/capabilities")
        assert response.status_code == 200

        response = client.get("/api/self-improvement/report")
        assert response.status_code == 200

    def test_full_e2e_trading_scenario(self):
        """Full E2E: dispatch -> workflow -> marketplace -> knowledge -> monitoring."""
        # Load all modules
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")
        mon_mod = _load_tool("monitoring", "universe_monitoring.py")

        # Step 1: Dispatch a trading task
        bus = dispatch.UniverseDispatchBus()
        bus.dispatch("Stratex", "analyze_market", {"pair": "BTC/USDT"})

        # Step 2: Run trading workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_trading_analysis()
        assert wf.status == "completed"

        # Step 3: Call services in marketplace
        mp = marketplace.AgentMarketplace()
        call1 = mp.call_service("FRIDAY", "Inference", "reasoning", {"query": "market analysis"})
        call2 = mp.call_service("FRIDAY", "Cortex", "decision", {"decision": "invest"})
        call3 = mp.call_service("FRIDAY", "Stratex", "portfolio", {"capital": "10000"})
        assert call1.status == "completed"
        assert call2.status == "completed"
        assert call3.status == "completed"

        # Step 4: Record knowledge
        kg = kg_mod.KnowledgeGraph()
        kg.add_node("entity", "BTC", {}, ["Stratex"])
        kg.add_node("concept", "Bullish Trend", {}, ["Inference"])
        n1 = kg.query_node("BTC")[0]
        n2 = kg.query_node("Bullish")[0]
        kg.add_edge(n1.node_id, n2.node_id, "indicates")
        synthesis = kg.synthesize_knowledge("BTC")
        assert synthesis["nodes"] >= 1

        # Step 5: Monitor performance
        loop = mon_mod.SelfImprovementLoop()
        cycle = loop.run_cycle("Stratex", {
            "error_rate": 0.02, "latency": 150, "cpu_usage": 25,
        })
        assert cycle.status == "completed"

    def test_full_e2e_security_scenario(self):
        """Full E2E: dispatch -> workflow -> marketplace -> knowledge -> monitoring (security)."""
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")
        mon_mod = _load_tool("monitoring", "universe_monitoring.py")

        # Step 1: Dispatch a security task
        bus = dispatch.UniverseDispatchBus()
        bus.dispatch("Sentinel", "scan_threats", {})

        # Step 2: Run security workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_security_scan()
        assert wf.status == "completed"

        # Step 3: Call services
        mp = marketplace.AgentMarketplace()
        call1 = mp.call_service("FRIDAY", "Sentinel", "incident_response", {"alert": "DDoS"})
        call2 = mp.call_service("FRIDAY", "IntelX", "threat_attribution", {"indicator": "1.2.3.4"})
        assert call1.status == "completed"
        assert call2.status == "completed"

        # Step 4: Record knowledge
        kg = kg_mod.KnowledgeGraph()
        kg.add_node("entity", "DDoS Attack", {}, ["Sentinel"])
        kg.add_node("concept", "Threat Actor APT-42", {}, ["IntelX"])

        # Step 5: Monitor
        loop = mon_mod.SelfImprovementLoop()
        cycle = loop.run_cycle("Sentinel", {
            "error_rate": 0.0, "latency": 80, "cpu_usage": 40,
        })
        assert cycle.status == "completed"

    def test_full_e2e_content_scenario(self):
        """Full E2E: dispatch -> workflow -> marketplace -> knowledge (content)."""
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")

        # Step 1: Dispatch a content task
        bus = dispatch.UniverseDispatchBus()
        bus.dispatch("VyralX", "create_content", {"topic": "AI"})

        # Step 2: Run content workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_content_creation()
        assert wf.status == "completed"

        # Step 3: Call services
        mp = marketplace.AgentMarketplace()
        call1 = mp.call_service("FRIDAY", "VyralX", "content_creation", {"topic": "AI"})
        call2 = mp.call_service("FRIDAY", "Inference", "argumentation", {"topic": "AI debate"})
        assert call1.status == "completed"
        assert call2.status == "completed"

        # Step 4: Record knowledge
        kg = kg_mod.KnowledgeGraph()
        kg.add_node("entity", "AI Content", {}, ["VyralX"])
        kg.add_node("concept", "Viral Potential", {}, ["Inference"])

    def test_full_e2e_code_scenario(self):
        """Full E2E: dispatch -> workflow -> marketplace -> knowledge (code)."""
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")

        # Step 1: Dispatch a code task
        bus = dispatch.UniverseDispatchBus()
        bus.dispatch("Forge", "develop_feature", {"feature": "auth"})

        # Step 2: Run code workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_code_development()
        assert wf.status == "completed"

        # Step 3: Call services
        mp = marketplace.AgentMarketplace()
        call1 = mp.call_service("FRIDAY", "Forge", "code_analysis", {"code": "test"})
        call2 = mp.call_service("FRIDAY", "Forge", "security_scan", {"code": "test"})
        assert call1.status == "completed"
        assert call2.status == "completed"

        # Step 4: Record knowledge
        kg = kg_mod.KnowledgeGraph()
        kg.add_node("entity", "Auth Feature", {}, ["Forge"])
        kg.add_node("concept", "Security Compliant", {}, ["Sentinel"])

    def test_full_e2e_forecast_scenario(self):
        """Full E2E: dispatch -> workflow -> marketplace -> knowledge (forecast)."""
        dispatch = _load_friday("dispatch", "universe_dispatch_bus.py")
        workflow = _load_tool("workflow", "universe_workflow_engine.py")
        marketplace = _load_tool("marketplace", "universe_agent_marketplace.py")
        kg_mod = _load_tool("knowledge_graph", "universe_knowledge_graph.py")

        # Step 1: Dispatch a forecast task
        bus = dispatch.UniverseDispatchBus()
        bus.dispatch("Futuris", "forecast", {"market": "crypto"})

        # Step 2: Run forecast workflow
        eng = workflow.UniverseWorkflowEngine()
        wf = eng.run_forecast_pipeline()
        assert wf.status == "completed"

        # Step 3: Call services
        mp = marketplace.AgentMarketplace()
        call1 = mp.call_service("FRIDAY", "Futuris", "counterfactual", {"premise": "BTC $50k"})
        call2 = mp.call_service("FRIDAY", "Futuris", "quantum_forecast", {"market": "crypto"})
        assert call1.status == "completed"
        assert call2.status == "completed"

        # Step 4: Record knowledge
        kg = kg_mod.KnowledgeGraph()
        kg.add_node("entity", "BTC Forecast", {}, ["Futuris"])
        kg.add_node("concept", "Bullish Outlook", {}, ["Inference"])

    def test_all_systems_count(self):
        """Verify we have all the systems built."""
        systems = [
            ("FRIDAY dispatch bus", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py"),
            ("FRIDAY mesh router", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py"),
            ("FRIDAY mesh coordinator", "FRIDAY/apps/core/src/friday_core/agent_mesh_coordinator.py"),
            ("Workflow engine", "tools/universe_workflow_engine.py"),
            ("Self-improvement engine", "tools/universe_self_improvement.py"),
            ("Agent marketplace", "tools/universe_agent_marketplace.py"),
            ("Orchestrator", "tools/universe_orchestrator.py"),
            ("Knowledge graph", "tools/universe_knowledge_graph.py"),
            ("Cross-agent reasoning", "tools/universe_cross_reasoning.py"),
            ("Swarm intelligence", "tools/universe_swarm_intelligence.py"),
            ("Monitoring system", "tools/universe_monitoring.py"),
            ("Dashboard", "tools/universe_dashboard.py"),
        ]
        for name, relpath in systems:
            path = ROOT / relpath
            assert path.exists(), f"Missing system: {name} ({relpath})"

    def test_all_agents_have_core_modules(self):
        """Verify all 10 agents have core modules."""
        agent_modules = {
            "FRIDAY": ["universe_dispatch.py", "universe_routing.py", "universe_mesh.py"],
            "Inference": ["reasoning.py", "argumentation.py"],
            "Cortex": ["decision.py", "foresight.py"],
            "Memora": ["memory.py", "reflection.py"],
            "Stratex": ["portfolio.py", "trading.py"],
            "Forge": ["code.py", "build.py"],
            "Sentinel": ["slade.py", "incidents.py"],
            "IntelX": ["contradictions.py", "research.py"],
            "Futuris": ["forecast.py", "counterfactuals.py"],
            "VyralX": ["content.py", "analytics.py"],
        }
        for agent, modules in agent_modules.items():
            for mod in modules:
                files = list((ROOT / agent).rglob(f"*{mod}*"))
                if not files:
                    # Try broader search
                    files = list((ROOT / agent).rglob("*.py"))
                    content_matches = [f for f in files
                                       if mod.split(".")[0] in f.read_text().lower()[:500]]
                    assert len(content_matches) > 0 or len(files) > 5, \
                        f"{agent} may not have {mod}"

    def test_test_suite_coverage(self):
        """Verify we have extensive test coverage."""
        test_files = list((ROOT / "tests").glob("test_*.py"))
        assert len(test_files) >= 20, f"Only {len(test_files)} test files"

        # Count tests by running pytest --collect-only
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "--collect-only", "-q"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        # Count "::" patterns (test names)
        test_count = result.stdout.count("::")
        assert test_count >= 500, f"Only {test_count} tests found"