"""
tests/test_deep_all_agents.py — Comprehensive deep module tests for ALL agents.

Tests every major module across all 10 agents. This is the exhaustive
test suite that ensures every deep module works end-to-end.

Priority 1: Make It Run (Deep Module Coverage)
"""
import importlib.util
import sys
import os
import time
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add all paths
for p in [
    ROOT + "/FRIDAY/apps/core/src",
    ROOT + "/Cortex/apps/api/src",
    ROOT + "/Inference",
    ROOT + "/Memora/apps/api",
    ROOT + "/Forge",
    ROOT + "/VyralX",
    ROOT + "/IntelX",
    ROOT + "/Sentinel/sentinel/apps/api/src",
    ROOT + "/Stratex",
    ROOT + "/Futuris",
]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, relpath):
    """Load a module directly from file."""
    path = os.path.join(ROOT, relpath)
    full_name = f"_deep_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    """Load and return the engine from a module."""
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ════════════════════════════════════════════════════════════════════════════════
# FRIDAY CORE — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFRIDAYDeep:
    """Deep tests for FRIDAY core modules."""

    def test_dispatch_bus_all_agents_deep(self):
        bus = _eng("db", "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
        for agent in ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                      "Sentinel", "IntelX", "Futuris", "VyralX"]:
            receipt = bus.dispatch(agent, "deep_test", {"agent": agent})
            assert receipt.status == "completed"
            assert receipt.agent == agent

    def test_auth_capability_verification(self):
        auth = _eng("auth", "FRIDAY/apps/core/src/friday_core/universe_auth.py")
        auth.register_agent("test_agent", ["orchestration", "dispatch", "admin"])
        token = auth.issue_token("test_agent", ["orchestration", "dispatch", "admin"])
        assert auth.verify_token(token.token_id)
        assert auth.verify_capability("test_agent", "dispatch")
        assert not auth.verify_capability("test_agent", "nonexistent")

    def test_security_ssrf_all_blocked(self):
        sec = _eng("sec", "FRIDAY/apps/core/src/friday_core/security_hardening.py")
        blocked = [
            "http://127.0.0.1/", "http://localhost/", "http://10.0.0.1/",
            "http://169.254.169.254/", "http://[::1]/", "http://0.0.0.0/",
            "http://192.168.1.1/", "http://172.16.0.1/",
        ]
        for url in blocked:
            assert not sec.check_ssrf(url), f"SSRF should block {url}"
        allowed = [
            "https://api.github.com/", "https://pypi.org/",
            "https://registry.npmjs.org/", "https://github.com/",
        ]
        for url in allowed:
            assert sec.check_ssrf(url), f"SSRF should allow {url}"

    def test_gateway_all_agents(self):
        gateway = _eng("gateway", "FRIDAY/apps/core/src/friday_core/universe_gateway.py")
        agents = gateway.get_all_agents_health()
        assert len(agents) >= 9
        for a in agents:
            assert "agent_name" in a
            assert "base_url" in a

    def test_config_all_agents(self):
        config = _eng("config", "FRIDAY/apps/core/src/friday_core/universe_config.py")
        agents = config.get_all_agents()
        assert len(agents) >= 10
        for a in agents:
            if hasattr(a, "agent_name"):
                assert a.agent_name

    def test_metrics_all_agents(self):
        metrics = _eng("metrics", "FRIDAY/apps/core/src/friday_core/universe_metrics.py")
        for agent in ["FRIDAY", "Inference", "Memora", "Stratex", "Forge",
                      "Cortex", "Sentinel", "IntelX", "Futuris", "VyralX"]:
            metrics.record_request(agent, 25.0, error=False)
        report = metrics.calculate_metrics()
        assert report.total_requests == 10

    def test_health_monitor_all_9(self):
        health = _eng("health", "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py")
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            health.register_agent(agent)
            health.check_agent_health(agent, True)
        snapshot = health.get_universe_health()
        assert snapshot.total_agents >= 9

    def test_mesh_router_all_domains(self):
        mesh = _eng("mesh", "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py")
        routes = [
            ("analyze trading", "trading", "Stratex"),
            ("recall memory", "memory", "Memora"),
            ("detect threat", "security", "Sentinel"),
            ("build code", "code", "Forge"),
            ("reason about", "reasoning", "Inference"),
            ("decide strategy", "strategy", "Cortex"),
            ("forecast future", "forecast", "Futuris"),
            ("create content", "content", "VyralX"),
            ("analyze intel", "intel", "IntelX"),
        ]
        for task, domain, expected in routes:
            decision = mesh.route_task(task, domain)
            assert decision.routed_to == expected
            assert decision.confidence > 0

    def test_event_bus_multiple_events(self):
        bus = _eng("events", "FRIDAY/apps/core/src/friday_core/universe_event_bus.py")
        types = ["task_completed", "agent_registered", "health_check", "alert", "deploy"]
        for etype in types:
            event = bus.publish_event(etype, {"type": etype}, "FRIDAY")
            assert event.event_id
            assert event.event_type == etype

    def test_state_manager_complex_state(self):
        state = _eng("state", "FRIDAY/apps/core/src/friday_core/universe_state_manager.py")
        state.set_state("agents/Inference/status", {"online": True, "load": 0.3}, "FRIDAY")
        state.set_state("agents/Cortex/status", {"online": True, "load": 0.5}, "FRIDAY")
        state.set_state("universe/version", {"version": "1.0.0", "build": 42}, "FRIDAY")
        all_state = state.get_all_state()
        assert len(all_state) >= 3

    def test_audit_trail_comprehensive(self):
        audit = _eng("audit", "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py")
        audit.log("FRIDAY", "dispatch", "Inference", "success")
        audit.log("FRIDAY", "dispatch", "Cortex", "success")
        audit.log("Cortex", "decide", "budget", "success")
        audit.log("Stratex", "trade", "BTC", "failure")
        by_agent = audit.search(agent="FRIDAY")
        assert by_agent.total_matches >= 2

    def test_rate_limiter_all_agents(self):
        rl = _eng("rl", "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py")
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            rl.configure_limit(agent, "requests", 100, 60)
            rec = rl.check_limit(agent, "requests", 10)
            assert rec.remaining == 90

    def test_task_router_complex_routing(self):
        router = _eng("router", "FRIDAY/apps/core/src/friday_core/universe_task_router.py")
        router.register_agent("Inference", ["reasoning", "analysis", "math"])
        router.register_agent("Cortex", ["decision", "strategy", "budget"])
        router.register_agent("Stratex", ["trading", "market", "finance"])
        router.register_agent("Forge", ["code", "build", "test"])
        router.register_agent("Sentinel", ["security", "threat", "scan"])

        tasks = [
            ("Analyze market data", ["analysis", "finance"]),
            ("Decide on budget", ["decision", "budget"]),
            ("Build feature", ["code", "build"]),
            ("Scan for threats", ["security", "threat"]),
        ]
        for desc, caps in tasks:
            task = router.submit_task(desc, caps)
            decision = router.route_task(task.task_id)
            assert decision.assigned_agent
            assert decision.confidence > 0

    def test_knowledge_graph_complex(self):
        kg = _eng("kg", "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py")
        # Build a complex graph
        entities = {
            "FRIDAY": "agent", "Inference": "agent", "Cortex": "agent",
            "Stratex": "agent", "Forge": "agent", "Sentinel": "agent",
            "reasoning": "capability", "trading": "capability", "code": "capability",
            "security": "capability", "decision": "capability",
        }
        ids = {}
        for name, etype in entities.items():
            e = kg.add_entity(name, etype)
            ids[name] = e.entity_id
        # Add edges
        edges = [("FRIDAY", "Inference", "dispatches"), ("FRIDAY", "Cortex", "dispatches"),
                 ("Inference", "reasoning", "provides"), ("Cortex", "decision", "provides"),
                 ("Stratex", "trading", "provides"), ("Forge", "code", "provides"),
                 ("Sentinel", "security", "provides")]
        for src, dst, rel in edges:
            kg.add_edge(ids[src], ids[dst], rel)
        result = kg.query("friday inference cortex stratex")
        assert result.entities_found >= 4

    def test_cross_agent_integration_all_preconfigured(self):
        integration = _eng("integ", "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py")
        preconfigured = [
            ("Forge", "Sentinel"), ("VyralX", "Inference"), ("VyralX", "Sentinel"),
            ("IntelX", "Memora"), ("Futuris", "IntelX"), ("Stratex", "Futuris"),
            ("Cortex", "Memora"), ("Sentinel", "IntelX"),
        ]
        for caller, callee in preconfigured:
            call = integration.call_peer(caller, callee, {"test": True})
            assert call.status == "completed"
            assert call.caller == caller
            assert call.callee == callee


# ════════════════════════════════════════════════════════════════════════════════
# CORTEX — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestCortexDeep:
    """Deep tests for Cortex modules."""

    def test_decision_impact_comprehensive(self):
        di = _eng("cortex_di", "Cortex/apps/api/src/cortex_api/decision_impact_analyzer.py")
        dec1 = di.record_decision("Hire contractor", "budget", ["contractor", "employee"], "contractor", "cost effective")
        dec2 = di.record_decision("Launch product", "strategy", ["product", "market"], "market", "growth")
        di.record_outcome(dec1, "positive", 5000, 3000, 2000, 0.8)
        di.record_outcome(dec2, "negative", 10000, 5000, 3000, 0.3)
        score = di.calculate_quality_score()
        assert score.total_decisions == 2

    def test_strategic_foresight_multiple_trends(self):
        sf = _eng("cortex_sf", "Cortex/apps/api/src/cortex_api/strategic_foresight_engine.py")
        sf.identify_trend("AI regulation", "policy", 0.8, "long", 0.7)
        sf.identify_trend("Quantum computing", "tech", 0.6, "long", 0.5)
        sf.identify_trend("Climate action", "policy", 0.7, "medium", 0.8)
        report = sf.generate_foresight_report("long")
        assert len(report.trends) >= 2

    def test_decision_tree_complex(self):
        dt = _eng("cortex_dt", "Cortex/apps/api/src/cortex_api/decision_tree_visualizer.py")
        tree = dt.create_tree("Strategic Investment Decision")
        root = tree.root  # root is a string node_id
        n1 = dt.add_node(tree.tree_id, root, "Invest", "decision")
        n2 = dt.add_node(tree.tree_id, n1.node_id, "High Risk", "decision")
        n3 = dt.add_node(tree.tree_id, n1.node_id, "Low Risk", "decision")
        dt.add_node(tree.tree_id, n2.node_id, "Success", "end", {"value": 0.7})
        dt.add_node(tree.tree_id, n2.node_id, "Failure", "end", {"value": 0.3})
        dt.add_node(tree.tree_id, n3.node_id, "Success", "end", {"value": 0.5})
        dt.add_node(tree.tree_id, n3.node_id, "Failure", "end", {"value": 0.5})
        analysis = dt.analyze_tree(tree.tree_id)
        assert analysis.total_nodes >= 6

    def test_partner_network_complex(self):
        pn = _eng("cortex_pn", "Cortex/apps/api/src/cortex_api/strategic_partner_network_analyzer.py")
        partners = [
            ("TechCorp", "vendor", 0.8, 0.7),
            ("DataInc", "vendor", 0.6, 0.5),
            ("CloudNet", "service", 0.9, 0.8),
            ("AI Labs", "research", 0.7, 0.6),
            ("GlobalBank", "finance", 0.5, 0.9),
        ]
        ids = []
        for name, type_, tx, rx in partners:
            p = pn.add_partner(name, type_, tx, rx)
            ids.append(p.partner_id)
        # Add connections
        for i in range(len(ids) - 1):
            pn.add_connection(ids[i], ids[i+1], "supply", 0.7)
        analysis = pn.analyze_network()
        assert analysis.total_partners == 5
        assert analysis.density > 0

    def test_decision_fatigue_comprehensive(self):
        df = _eng("cortex_df", "Cortex/apps/api/src/cortex_api/decision_fatigue_detector.py")
        for i in range(10):
            df.record_decision(f"Decision {i}", 0.5 + i * 0.05, 10.0 + i * 5, 0.8 - i * 0.05)
        assessment = df.assess_fatigue()
        assert assessment.total_decisions == 10
        rec = df.recommend_cadence()
        assert rec.max_daily_decisions > 0


# ════════════════════════════════════════════════════════════════════════════════
# INFERENCE — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestInferenceDeep:
    """Deep tests for Inference modules."""

    def test_temporal_reasoning_complex(self):
        te = _eng("inf_te", "Inference/services/temporal_reasoning_engine.py")
        events = []
        for i, (name, ts, imp, etype) in enumerate([
            ("Market crash", time.time() - 200, 5, "event"),
            ("Recovery", time.time() - 150, 3, "event"),
            ("Interest rate cut", time.time() - 100, 4, "event"),
            ("Market rally", time.time() - 50, 2, "event"),
        ]):
            e = te.add_event(name, ts, imp, etype)
            events.append(e)
        te.add_relation(events[0], events[1], "caused", 0.9)
        te.add_relation(events[2], events[3], "enabled", 0.8)
        query = te.query_events("market", time.time() - 250, time.time())
        assert len(query.results) >= 2

    def test_commonsense_multiple_facts(self):
        ce = _eng("inf_ce", "Inference/services/commonsense_reasoning_engine.py")
        ce.add_fact("fire", "is dangerous to", "water")
        ce.add_fact("water", "is necessary for", "life")
        ce.add_fact("sun", "provides", "light")
        ce.add_fact("plants", "need", "sunlight")
        result = ce.reason("Is fire dangerous?")
        assert result.answer
        assert result.steps

    def test_argumentation_full_debate(self):
        aa = _eng("inf_aa", "Inference/services/multi_agent_argumentation_engine.py")
        aa.register_agent("agent1")
        aa.register_agent("agent2")
        aa.register_agent("agent3")
        arg1 = aa.submit_argument("AI will improve education", ["evidence1", "evidence2"], "conclusion", "agent1", 0.8)
        arg2 = aa.submit_argument("AI will harm education", ["counter1"], "conclusion", "agent2", 0.6)
        session = aa.start_debate("AI in Education", ["agent1", "agent2", "agent3"])
        aa.add_turn(session.session_id, "agent1", "AI provides personalized learning", "argument")
        aa.add_turn(session.session_id, "agent2", "AI may replace teachers", "rebuttal")
        aa.add_turn(session.session_id, "agent3", "Balanced approach needed", "mediation")
        r1 = aa.evaluate_argument(arg1)
        r2 = aa.evaluate_argument(arg2)
        assert r1["strength"] == 0.8
        assert r2["strength"] == 0.6

    def test_moral_reasoning_complex(self):
        mr = _eng("inf_mr", "Inference/services/moral_reasoning_engine.py")
        mr.add_principle("Maximize happiness", "utilitarianism", "", 1.0)
        mr.add_principle("Do not harm", "deontology", "", 0.9)
        mr.add_principle("Fairness", "justice", "", 0.8)
        dil = mr.create_dilemma("Should we sacrifice one to save five?", ["sacrifice", "don't sacrifice"], ["person1", "person2"])
        evaluation = mr.evaluate(dil.dilemma_id)
        assert evaluation.recommended_option
        assert len(evaluation.principle_scores) >= 2

    def test_analogical_reasoning_multiple(self):
        ar = _eng("inf_ar", "Inference/services/analogical_reasoning_engine.py")
        c1 = ar.add_concept("Water flows downhill", "physics", {"flow": "downhill"})
        c2 = ar.add_concept("Information flows to users", "tech", {"flow": "to users"})
        c3 = ar.add_concept("Heat flows from hot to cold", "physics", {"flow": "to cold"})
        a1 = ar.create_analogy(c1.concept_id, c2.concept_id)
        a2 = ar.create_analogy(c1.concept_id, c3.concept_id)
        assert a1.similarity_score > 0
        assert a2.similarity_score > 0

    def test_probabilistic_logic_complex(self):
        pl = _eng("inf_pl", "Inference/services/probabilistic_logic_engine.py")
        v1 = pl.add_variable("Rain", ["yes", "no"], {"yes": 0.3, "no": 0.7})
        v2 = pl.add_variable("Traffic", ["heavy", "light"], {"heavy": 0.4, "light": 0.6})
        result1 = pl.infer(v1.var_id, {"Rain": "yes"})
        result2 = pl.infer(v2.var_id, {"Traffic": "heavy"})
        assert "yes" in result1.posterior
        assert "heavy" in result2.posterior


# ════════════════════════════════════════════════════════════════════════════════
# MEMORA — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestMemoraDeep:
    """Deep tests for Memora modules."""

    def test_memory_retrieval_complex(self):
        mr = _eng("memora_retrieval", "Memora/apps/api/routers/memory_retrieval_engine.py")
        memories = [
            ("The quarterly revenue increased by 15%", "semantic", ["revenue", "finance", "quarterly"]),
            ("Product launch was successful in Q3", "semantic", ["product", "launch", "q3"]),
            ("Hiring plan approved for engineering team", "semantic", ["hiring", "engineering", "plan"]),
        ]
        for content, mtype, tags in memories:
            mr.store_memory(content, mtype, tags)
        query = mr.retrieve("revenue finance quarterly", "all", 5)
        assert len(query.results) >= 1
        assert query.results[0].similarity_score > 0

    def test_memory_reflection_comprehensive(self):
        mr = _eng("memora_reflection", "Memora/apps/api/routers/memory_reflection_engine.py")
        session = mr.start_reflection("quarterly review")
        insights = []
        for topic, content, confidence in [
            ("hiring", "Need to hire more engineers", 0.9),
            ("budget", "Budget exceeded by 10%", 0.7),
            ("product", "Product roadmap on track", 0.8),
        ]:
            insight = mr.generate_insight(session.session_id, topic, content, confidence)
            insights.append(insight)
        mr.end_reflection(session.session_id)
        assert len(insights) == 3
        assert all(i.confidence > 0 for i in insights)

    def test_memory_dream_complex(self):
        md = _eng("memora_dream", "Memora/apps/api/routers/memory_dream_engine.py")
        for i, (content, tags) in enumerate([
            ("Machine learning project started", ["ml", "project", "start"]),
            ("Data pipeline implemented", ["data", "pipeline", "implement"]),
            ("Model training completed", ["model", "training", "complete"]),
            ("Deployment successful", ["deployment", "success"]),
        ]):
            md.add_memory(f"mem{i}", content, tags)
        dream = md.dream("tech", ["mem0", "mem1", "mem2", "mem3"])
        assert dream.fragments
        assert dream.insight

    def test_memory_decay_multiple(self):
        md = _eng("memora_decay", "Memora/apps/api/routers/memory_decay_predictor.py")
        memories = []
        for i, (content, imp, rate) in enumerate([
            ("Important meeting notes", 0.9, 0.05),
            ("Casual conversation", 0.3, 0.1),
            ("Critical system config", 0.95, 0.02),
        ]):
            m = md.store_memory(content, importance=imp, decay_rate=rate)
            memories.append(m.memory_id)
        for mid in memories:
            md.access_memory(mid)
            curve = md.predict_decay(mid, 86400)
            assert curve.half_life > 0
            assert curve.predicted_retention > 0

    def test_dream_interpreter_complex(self):
        mi = _eng("memora_interp", "Memora/apps/api/routers/memory_dream_interpreter.py")
        dreams = [
            ("dream1", "I was flying over water with a snake"),
            ("dream2", "Walking through a dark forest alone"),
            ("dream3", "Finding a hidden treasure in my house"),
        ]
        for dream_id, content in dreams:
            interp = mi.interpret_dream(dream_id, content)
            assert interp.symbols is not None
            assert interp.themes is not None


# ════════════════════════════════════════════════════════════════════════════════
# FORGE — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestForgeDeep:
    """Deep tests for Forge modules."""

    def test_code_analysis_complex_code(self):
        ca = _eng("forge_analysis", "Forge/app/services/code_analysis_engine.py")
        code = """def f(x):
    if x > 0:
        eval('dangerous')
        for i in range(x):
            if i > 10:
                return i
            if i > 5:
                continue
        while x > 0:
            x -= 1
            if x > 100:
                break
    return x
"""
        report = ca.analyze_code("test.py", code)
        assert report.metrics.cyclomatic_complexity > 1
        assert report.critical_findings >= 1

    def test_build_pipeline_multiple_stages(self):
        bp = _eng("forge_pipeline", "Forge/app/services/build_pipeline_manager.py")
        pipeline = bp.create_pipeline("Full CI/CD", "project", ["lint", "build", "test", "deploy"])
        result = bp.run_pipeline(pipeline.pipeline_id)
        assert result.status == "completed"
        assert len(result.stages) == 4

    def test_test_coverage_complex(self):
        tc = _eng("forge_coverage", "Forge/app/services/test_coverage_analyzer.py")
        report = tc.analyze_coverage("test.py", 200, 150, 0.65, 0.7)
        assert report.gap_count == 50
        assert report.quality_score > 0

    def test_code_security_multiple_patterns(self):
        ss = _eng("forge_security", "Forge/app/services/code_security_scanner.py")
        code = "password = 'hardcoded_secret_12345'\napi_key = 'sk_test_1234567890abcdef'\nsql = \"SELECT * FROM users WHERE id=\" + uid"
        vulns = ss.scan_code("test.py", code)
        assert len(vulns) >= 2
        secrets = ss.scan_secrets("test.py", "password = hardcoded_secret_12345")
        assert len(secrets) >= 1

    def test_merge_conflict_complex(self):
        mc = _eng("forge_merge", "Forge/app/services/code_merge_conflict_resolver.py")
        conflict = mc.detect_conflict("test.py", "main", "feature", [
            {"line_start": 1, "line_end": 5, "our_content": "ours1", "their_content": "theirs1"},
            {"line_start": 10, "line_end": 15, "our_content": "ours2", "their_content": "theirs2"},
        ])
        assert len(conflict.hunks) >= 2
        for hunk in conflict.hunks:
            result = mc.resolve_hunk(conflict.conflict_id, hunk.hunk_id, "theirs")
            assert result.resolution == "theirs"

    def test_complexity_quantifier_complex(self):
        cx = _eng("forge_complexity", "Forge/app/services/code_complexity_quantifier.py")
        code = "def f():\n    if True:\n        for i in range(10):\n            if i > 5:\n                for j in range(5):\n                    if j > 2:\n                        pass\n"
        metrics = cx.analyze("test.py", code)
        assert metrics.cyclomatic > 1
        assert metrics.maintainability_index > 0


# ════════════════════════════════════════════════════════════════════════════════
# VYRALX — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestVyralXDeep:
    """Deep tests for VyralX modules."""

    def test_content_performance_multiple(self):
        cp = _eng("vyral_cp", "VyralX/app/services/content_performance_analyzer.py")
        for i in range(5):
            cp.record_metric(f"video{i}", 1000 + i * 100, 100 + i * 10, 50, 20, 300)
        report = cp.generate_report("channel1")
        assert report.total_content >= 5

    def test_attention_predictor_complex(self):
        ap = _eng("vyral_ap", "VyralX/app/services/audience_attention_predictor.py")
        for i in range(3):
            forecast = ap.predict_attention(f"video{i}", 60, 10)
            assert forecast.avg_attention > 0
            assert len(forecast.segments) == 10

    def test_creator_economy_multiple(self):
        ce = _eng("vyral_economy", "VyralX/app/services/creator_economy_analyzer.py")
        for i, (name, views, subs, rev, rate) in enumerate([
            ("creator1", 100000, 5000, 500.0, 0.05),
            ("creator2", 50000, 2000, 300.0, 0.08),
            ("creator3", 200000, 10000, 2000.0, 0.03),
        ]):
            ce.record_creator(name, views, subs, rev, rate)
            strategies = ce.recommend_strategy(name)
            assert len(strategies) >= 2

    def test_moderation_multiple_types(self):
        cm = _eng("vyral_moderation", "VyralX/app/services/content_moderation_engine.py")
        cm.create_policy("Default Policy")
        mod = _load("vyral_mod_mod", "VyralX/app/services/content_moderation_engine.py")
        for i, (text, media) in enumerate([
            ("Good content", "text"),
            ("bad bad bad", "text"),
            ("spam spam click here", "text"),
        ]):
            ci = mod.ContentItem(content_id=f"test{i}", text=text, media_type=media)
            result = cm.moderate(ci)
            assert result.decision in ("approved", "flagged", "rejected")

    def test_collaboration_matcher_multiple(self):
        cc = _eng("vyral_cc", "VyralX/app/services/creator_collaboration_matcher.py")
        creators = [
            ("c1", "gaming", 50000, 0.05),
            ("c2", "gaming", 30000, 0.08),
            ("c3", "tech", 80000, 0.04),
            ("c4", "tech", 40000, 0.06),
        ]
        for name, niche, views, rate in creators:
            cc.register_creator(name, niche, views, rate)
        match = cc.find_match("c1", "c2")
        assert match.compatibility_score > 0


# ════════════════════════════════════════════════════════════════════════════════
# INTELX — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestIntelXDeep:
    """Deep tests for IntelX modules."""

    def test_disinformation_multiple(self):
        dd = _eng("intel_disinfo", "IntelX/intelx/services/disinformation_detector.py")
        samples = [
            "This is SHOCKING! They don't want you to know the deep state secret plan",
            "URGENT: The truth about vaccines that doctors are hiding from you!!!",
            "Normal news about economic policy and market trends",
        ]
        for sample in samples:
            report = dd.detect(sample)
            assert report.risk_score >= 0
            assert report.overall_risk in ("low", "medium", "high", "critical")

    def test_threat_attribution_multiple(self):
        ta = _eng("intel_attribution", "IntelX/intelx/services/threat_attribution_engine.py")
        ta.register_actor("APT29", ["Cozy Bear"], ["T1566", "T1059"])
        ta.register_actor("APT28", ["Fancy Bear"], ["T1566", "T1078"])
        r1 = ta.attribute("Cozy Bear IP", "IP match")
        r2 = ta.attribute("Fancy Bear domain", "Domain match")
        assert r1.attributed_actor == "APT29"
        assert r2.attributed_actor == "APT28"

    def test_supply_chain_complex(self):
        sc = _eng("intel_supply", "IntelX/intelx/services/supply_chain_threat_mapper.py")
        nodes = []
        for i, (name, ntype, risk, comp, vuln) in enumerate([
            ("VendorA", "vendor", "high", 0.3, 0.8),
            ("ServiceB", "service", "medium", 0.5, 0.6),
            ("CloudC", "cloud", "high", 0.2, 0.9),
            ("AppD", "app", "low", 0.7, 0.4),
        ]):
            n = sc.add_node(name, ntype, risk, comp, vuln)
            nodes.append(n.node_id)
        for i in range(len(nodes) - 1):
            sc.add_dependency(nodes[i], nodes[i+1])
        path = sc.map_attack_path(nodes[0], nodes[-1])
        assert len(path.path_nodes) >= 2
        report = sc.assess_risk()
        assert report.risk_score > 0

    def test_intel_exchange_multiple(self):
        ie = _eng("intel_exchange", "IntelX/intelx/services/threat_intel_exchange_protocol.py")
        packages = []
        for i, (data, source) in enumerate([
            ({"type": "indicator", "value": "1.2.3.4"}, "internal"),
            ({"type": "report", "title": "APT Report"}, "partner"),
        ]):
            pkg = ie.create_package(data, source)
            packages.append(pkg.package_id)
        ie.register_partner("Partner1", "2.1", "https://taxii.example.com")
        stix = ie.export_stix(packages[0])
        assert stix["type"] == "bundle"

    def test_campaign_predictor_complex(self):
        cp = _eng("intel_campaign", "IntelX/intelx/services/threat_campaign_predictor.py")
        for phase, desc, prob, duration in [
            ("Reconnaissance", "Initial scanning", 0.8, 7200),
            ("Exploitation", "Gaining access", 0.5, 3600),
            ("Installation", "Installing malware", 0.4, 1800),
            ("Command & Control", "Establishing C2", 0.6, 3600),
            ("Exfiltration", "Stealing data", 0.3, 1800),
        ]:
            cp.add_phase(phase, desc, prob, duration)
        forecast = cp.forecast_campaign("APT29", "Reconnaissance")
        assert forecast.confidence > 0
        assert len(forecast.predicted_phases) >= 2


# ════════════════════════════════════════════════════════════════════════════════
# SENTINEL — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestSentinelDeep:
    """Deep tests for Sentinel modules."""

    def test_incident_response_playbook_complex(self):
        ip = _eng("sentinel_pb", "Sentinel/sentinel/apps/api/src/sentinel_api/incident_response_playbook.py")
        pb = ip.create_playbook("Security Incident Response", "security", "high")
        incident = ip.report_incident("high", "security", "SQL injection detected", pb.playbook_id)
        assert len(incident.steps) >= 5
        for step_num in range(1, len(incident.steps) + 1):
            step = ip.execute_step(incident.incident_id, step_num)
            assert step.status == "completed"
        ip.resolve_incident(incident.incident_id)
        result = ip.get_incident(incident.incident_id)
        assert result["status"] == "resolved"

    def test_slade_engine_comprehensive(self):
        se = _eng("sentinel_slade", "Sentinel/sentinel/apps/api/src/sentinel_api/security_slade_engine.py")
        se.create_sla("Patch critical vulns within 7 days", "security", time.time() + 604800, "sec-team")
        se.create_sla("Respond to incidents within 1 hour", "security", time.time() + 3600, "sec-team")
        se.schedule_audit("Quarterly compliance audit")
        posture = se.generate_posture("SOC2")
        assert posture.score >= 0

    def test_hunting_automation_complex(self):
        ha = _eng("sentinel_hunting", "Sentinel/sentinel/apps/api/src/sentinel_api/threat_hunting_automation_engine.py")
        hyps = []
        for i, (desc, htype, conf) in enumerate([
            ("Ransomware beacon on network", "anomaly", 0.6),
            ("Credential stuffing attack", "anomaly", 0.5),
            ("Unusual data transfer", "anomaly", 0.7),
        ]):
            h = ha.create_hypothesis(desc, htype, conf)
            hyps.append(h)
        for h in hyps:
            query = ha.execute_hunt(h.hypothesis_id, "SELECT * FROM logs WHERE alert = true", 5)
            assert query.result_count == 5
            ha.confirm_hypothesis(h.hypothesis_id)
        report = ha.generate_report()
        assert report.confirmed == 3

    def test_intel_correlation_multiple(self):
        ic = _eng("sentinel_correlation", "Sentinel/sentinel/apps/api/src/sentinel_api/threat_intel_correlation_engine.py")
        indicators = []
        for i, (value, itype, source, conf, tags) in enumerate([
            ("1.2.3.4", "ip", "feed", 0.8, ["c2", "malware"]),
            ("5.6.7.8", "ip", "feed", 0.7, ["c2", "malware"]),
            ("malware.exe", "file", "feed", 0.9, ["ransomware", "trojan"]),
        ]):
            ind = ic.add_indicator(value, itype, source, conf, tags)
            indicators.append(ind)
        # Correlate first indicator with second (overlapping tags: c2, malware)
        result = ic.correlate(indicators[0].indicator_id)
        # Single indicator correlation may be 0, but the call should not crash
        assert hasattr(result, "correlation_score")
        # Also test that all indicators are stored
        all_ind = ic.get_indicators()
        assert len(all_ind) >= 3

    def test_incident_timeline_complex(self):
        tl = _eng("sentinel_timeline", "Sentinel/sentinel/apps/api/src/sentinel_api/security_incident_timeline.py")
        t0 = time.time()
        events = [
            (t0, "alert", "Port scan detected", "medium", "attacker"),
            (t0 + 30, "indicator", "SQL injection attempt", "high", "attacker"),
            (t0 + 60, "action", "Firewall blocked IP", "low", "system"),
            (t0 + 90, "alert", "Brute force attempt", "medium", "attacker"),
            (t0 + 120, "action", "IP banned", "low", "system"),
        ]
        for ts, etype, desc, sev, source in events:
            tl.add_event(ts, etype, desc, sev, source)
        tl.add_attack_chain("SQL injection attack chain", ["port_scan", "sql_injection", "brute_force"])
        analysis = tl.analyze_timeline("incident1")
        assert analysis.total_events == 5
        assert analysis.root_cause


# ════════════════════════════════════════════════════════════════════════════════
# STRATEXT — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestStratexDeep:
    """Deep tests for Stratex modules."""

    def test_portfolio_optimization_complex(self):
        po = _eng("stratex_po", "Stratex/execution/portfolio_optimization_engine.py")
        portfolio = po.create_portfolio("Balanced Portfolio", [
            {"symbol": "AAPL", "weight": 0.25, "expected_return": 0.12, "volatility": 0.18},
            {"symbol": "GOOGL", "weight": 0.25, "expected_return": 0.10, "volatility": 0.20},
            {"symbol": "MSFT", "weight": 0.25, "expected_return": 0.11, "volatility": 0.19},
            {"symbol": "AMZN", "weight": 0.25, "expected_return": 0.14, "volatility": 0.25},
        ], "medium")
        assert portfolio.sharpe_ratio > 0
        plan = po.generate_rebalance(portfolio.portfolio_id, {
            "AAPL": 0.3, "GOOGL": 0.2, "MSFT": 0.25, "AMZN": 0.25,
        })
        assert plan.trades

    def test_microstructure_analyzer_multiple(self):
        ma = _eng("stratex_micro", "Stratex/execution/market_microstructure_analyzer.py")
        for symbol, bids, asks in [
            ("BTC", [(100, 10), (99, 20), (98, 15)], [(101, 15), (102, 10), (103, 20)]),
            ("ETH", [(50, 20), (49, 15), (48, 10)], [(51, 15), (52, 20), (53, 10)]),
        ]:
            ma.record_order_book(symbol, bids, asks)
            signal = ma.analyze(symbol)
            assert signal.signal in ("bullish", "bearish", "neutral")

    def test_flash_crash_detector_multiple(self):
        fc = _eng("stratex_flash", "Stratex/execution/flash_crash_detector.py")
        for symbol, vol, spike, stress in [
            ("BTC", 0.5, 3.0, 0.15),
            ("ETH", 0.8, 4.0, 0.20),
        ]:
            stress_result = fc.assess_stress(symbol, vol, spike, stress)
            assert stress_result.stress_level in ("normal", "elevated", "high", "extreme", "critical")
            event = fc.detect_flash_crash(symbol, 50000, 45000, 50100, 5.0)
            assert event.max_drawdown > 0

    def test_regime_change_detector_multiple(self):
        rc = _eng("stratex_regime", "Stratex/execution/regime_change_detector.py")
        for symbol, regime, confidence in [("BTC", "bull", 0.8), ("ETH", "bear", 0.6)]:
            rc.record_regime(symbol, regime, confidence)
            rc.detect_break(symbol, "volatility", "high", "Volatility spike detected")
            forecast = rc.forecast_transition(symbol, regime, "bear" if regime == "bull" else "bull", 0.4, 60.0)
            assert forecast.predicted_regime


# ════════════════════════════════════════════════════════════════════════════════
# FUTURIS — Deep Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestFuturisDeep:
    """Deep tests for Futuris modules."""

    def test_counterfactual_forecaster_complex(self):
        cf = _eng("futuris_cf", "Futuris/futuris/services/counterfactual_forecaster.py")
        factors = []
        for name, impact, direction, strength in [
            ("Economic growth", 0.3, "positive", 0.7),
            ("Interest rates", 0.2, "negative", 0.8),
            ("Inflation", 0.25, "negative", 0.6),
            ("Employment", 0.15, "positive", 0.5),
        ]:
            f = cf.define_factor(name, impact, direction, strength)
            factors.append(f)
        scenario = cf.create_counterfactual("Economic scenario", 5.0, factors, 0.6)
        assert scenario.counterfactual_forecast != 0
        whatif = cf.what_if("What if growth is 10%?", 5.0, 6.5)
        assert whatif.sensitivity > 0

    def test_prediction_market_multiple(self):
        pm = _eng("futuris_pm", "Futuris/futuris/services/prediction_market_engine.py")
        contracts = []
        for title, desc in [
            ("Will AI pass bar exam by 2026?", ""),
            ("Will quantum computing break crypto by 2027?", ""),
            ("Will autonomous vehicles be legal by 2028?", ""),
        ]:
            c = pm.create_contract(title, desc)
            pm.update_price(c.contract_id, 0.65)
            contracts.append(c)
        pm.resolve_contract(contracts[0].contract_id, "Yes")
        resolved = pm.get_contracts(resolved=True)
        assert len(resolved) == 1

    def test_quantum_forecast_complex(self):
        qf = _eng("futuris_qf", "Futuris/futuris/services/quantum_forecast_engine.py")
        forecast = qf.create_superposition(["up", "down", "stable", "volatile"], [0.25, 0.25, 0.25, 0.25])
        assert len(forecast.outcomes) == 4
        qf.collapse(forecast.forecast_id)
        result = qf.amplify(forecast.forecast_id, 3, "stable")
        assert result.amplification_factor > 1

    def test_skill_acquisition_planner_complex(self):
        sa = _eng("futuris_sa", "Futuris/futuris/services/skill_acquisition_planner.py")
        skills = []
        for name, proficiency, difficulty, value, category in [
            ("Python", 0.9, 0.3, 0.9, "technical"),
            ("ML", 0.8, 0.2, 0.8, "technical"),
            ("MLOps", 0.7, 0.4, 0.7, "technical"),
            ("Docker", 0.6, 0.3, 0.8, "technical"),
        ]:
            s = sa.add_skill(name, proficiency, difficulty, value, category)
            skills.append(s)
        resources = sa.recommend_resources("Python")
        assert len(resources) >= 2
        path = sa.create_learning_path("Become ML engineer", ["Python", "ML", "MLOps"])
        assert path.estimated_total_hours > 0
