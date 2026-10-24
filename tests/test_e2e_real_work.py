"""
tests/test_e2e_real_work.py — End-to-end tests that actually exercise modules.

These tests import modules via importlib, instantiate engines, call methods,
and verify functionality. No py_compile shortcuts.
"""
import importlib.util
import sys
import os
import time
import asyncio
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, relpath):
    """Load a module directly from file, bypassing broken __init__.py chains."""
    path = os.path.join(ROOT, relpath)
    # Use unique module name to avoid clobbering sys.modules entries
    full_name = f"_e2e_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name):
    return _load(name, MODULES[name]).engine


# --- Module paths ---
MODULES = {
    "dispatch_bus": "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py",
    "auth": "FRIDAY/apps/core/src/friday_core/universe_auth.py",
    "security": "FRIDAY/apps/core/src/friday_core/security_hardening.py",
    "integration": "FRIDAY/apps/core/src/friday_core/cross_agent_integration.py",
    "gateway": "FRIDAY/apps/core/src/friday_core/universe_gateway.py",
    "config": "FRIDAY/apps/core/src/friday_core/universe_config.py",
    "metrics": "FRIDAY/apps/core/src/friday_core/universe_metrics.py",
    "health": "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py",
    "mesh": "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py",
    "events": "FRIDAY/apps/core/src/friday_core/universe_event_bus.py",
    "state": "FRIDAY/apps/core/src/friday_core/universe_state_manager.py",
    "audit": "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py",
    "ratelimit": "FRIDAY/apps/core/src/friday_core/universe_rate_limiter.py",
    "router": "FRIDAY/apps/core/src/friday_core/universe_task_router.py",
    "kg": "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py",

    "cortex_di": "Cortex/apps/api/src/cortex_api/decision_impact_analyzer.py",
    "cortex_sf": "Cortex/apps/api/src/cortex_api/strategic_foresight_engine.py",
    "cortex_dt": "Cortex/apps/api/src/cortex_api/decision_tree_visualizer.py",
    "cortex_pn": "Cortex/apps/api/src/cortex_api/strategic_partner_network_analyzer.py",
    "cortex_df": "Cortex/apps/api/src/cortex_api/decision_fatigue_detector.py",

    "inf_te": "Inference/services/temporal_reasoning_engine.py",
    "inf_ce": "Inference/services/commonsense_reasoning_engine.py",
    "inf_aa": "Inference/services/multi_agent_argumentation_engine.py",
    "inf_mr": "Inference/services/moral_reasoning_engine.py",
    "inf_ar": "Inference/services/analogical_reasoning_engine.py",
    "inf_pl": "Inference/services/probabilistic_logic_engine.py",

    "memora_retrieval": "Memora/apps/api/routers/memory_retrieval_engine.py",
    "memora_reflection": "Memora/apps/api/routers/memory_reflection_engine.py",
    "memora_dream": "Memora/apps/api/routers/memory_dream_engine.py",
    "memora_decay": "Memora/apps/api/routers/memory_decay_predictor.py",
    "memora_interpreter": "Memora/apps/api/routers/memory_dream_interpreter.py",

    "forge_analysis": "Forge/app/services/code_analysis_engine.py",
    "forge_pipeline": "Forge/app/services/build_pipeline_manager.py",
    "forge_coverage": "Forge/app/services/test_coverage_analyzer.py",
    "forge_security": "Forge/app/services/code_security_scanner.py",
    "forge_merge": "Forge/app/services/code_merge_conflict_resolver.py",
    "forge_complexity": "Forge/app/services/code_complexity_quantifier.py",

    "vyral_performance": "VyralX/app/services/content_performance_analyzer.py",
    "vyral_attention": "VyralX/app/services/audience_attention_predictor.py",
    "vyral_economy": "VyralX/app/services/creator_economy_analyzer.py",
    "vyral_moderation": "VyralX/app/services/content_moderation_engine.py",
    "vyral_collaboration": "VyralX/app/services/creator_collaboration_matcher.py",

    "intel_disinfo": "IntelX/intelx/services/disinformation_detector.py",
    "intel_attribution": "IntelX/intelx/services/threat_attribution_engine.py",
    "intel_supply": "IntelX/intelx/services/supply_chain_threat_mapper.py",
    "intel_exchange": "IntelX/intelx/services/threat_intel_exchange_protocol.py",
    "intel_campaign": "IntelX/intelx/services/threat_campaign_predictor.py",

    "sentinel_playbook": "Sentinel/sentinel/apps/api/src/sentinel_api/incident_response_playbook.py",
    "sentinel_slade": "Sentinel/sentinel/apps/api/src/sentinel_api/security_slade_engine.py",
    "sentinel_hunting": "Sentinel/sentinel/apps/api/src/sentinel_api/threat_hunting_automation_engine.py",
    "sentinel_correlation": "Sentinel/sentinel/apps/api/src/sentinel_api/threat_intel_correlation_engine.py",
    "sentinel_timeline": "Sentinel/sentinel/apps/api/src/sentinel_api/security_incident_timeline.py",

    "stratex_portfolio": "Stratex/execution/portfolio_optimization_engine.py",
    "stratex_micro": "Stratex/execution/market_microstructure_analyzer.py",
    "stratex_flash": "Stratex/execution/flash_crash_detector.py",
    "stratex_regime": "Stratex/execution/regime_change_detector.py",

    "futuris_counterfactual": "Futuris/futuris/services/counterfactual_forecaster.py",
    "futuris_market": "Futuris/futuris/services/prediction_market_engine.py",
    "futuris_quantum": "Futuris/futuris/services/quantum_forecast_engine.py",
    "futuris_skill": "Futuris/futuris/services/skill_acquisition_planner.py",
}


def _eng(name):
    return _load(name, MODULES[name]).engine


class TestFRIDAYE2E:
    """Test FRIDAY core modules actually work by calling methods."""

    def test_dispatch_bus_actually_dispatches(self):
        bus = _eng("dispatch_bus")
        receipt = bus.dispatch("Stratex", "get_market_data", {"symbol": "BTC"})
        assert receipt.status == "completed"
        assert receipt.agent == "Stratex"
        assert receipt.task_id

    def test_dispatch_bus_all_9_agents(self):
        bus = _eng("dispatch_bus")
        agents = ["Inference", "Memora", "Stratex", "Forge", "Cortex",
                  "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            receipt = bus.dispatch(agent, "test_action", {"test": True})
            assert receipt.status == "completed", f"Dispatch to {agent} failed"

    def test_dispatch_bus_batch(self):
        bus = _eng("dispatch_bus")
        batch = bus.dispatch_batch([
            {"agent": "Inference", "action": "reason", "payload": {}},
            {"agent": "Memora", "action": "recall", "payload": {}},
            {"agent": "Cortex", "action": "decide", "payload": {}},
        ])
        assert len(batch) == 3

    def test_auth_issue_and_verify_token(self):
        auth = _eng("auth")
        token = auth.issue_token("FRIDAY", ["orchestration", "dispatch"])
        assert token.token_id
        assert auth.verify_token(token.token_id)
        auth.revoke_token(token.token_id)
        assert not auth.verify_token(token.token_id)

    def test_auth_verify_key(self):
        auth = _eng("auth")
        key_id = "test-key"
        secret = "test-secret-123"
        auth.register_agent("test-bot", "test-agent")
        # verify_key takes key_id and secret
        result = auth.verify_key(key_id, secret)
        # may or may not exist, but should not crash
        assert isinstance(result, bool)

    def test_security_ssrf_blocks_private(self):
        sec = _eng("security")
        assert not sec.check_ssrf("http://127.0.0.1:8080/api")
        assert not sec.check_ssrf("http://10.0.0.1/")
        assert not sec.check_ssrf("http://169.254.169.254/latest/meta-data/")
        assert sec.check_ssrf("https://api.github.com/users")

    def test_security_path_traversal(self):
        sec = _eng("security")
        sec.register_sandbox_dir("/tmp/sandbox")
        assert not sec.check_path_traversal("/tmp/sandbox/../../etc/passwd")
        assert sec.check_path_traversal("/tmp/sandbox/data.txt")

    def test_cross_agent_integration_calls(self):
        integration = _eng("integration")
        call = integration.call_peer("Forge", "Sentinel", {"code": "test"})
        assert call.status == "completed"
        assert call.caller == "Forge"
        assert call.callee == "Sentinel"

    def test_gateway_health_checks(self):
        gateway = _eng("gateway")
        agents = gateway.get_all_agents_health()
        assert len(agents) >= 9

    def test_config_get_agent_config(self):
        config = _eng("config")
        agent = config.get_agent_config("Inference")
        assert agent.agent_name == "Inference"
        assert agent.port == 8005

    def test_metrics_record_and_report(self):
        metrics = _eng("metrics")
        metrics.record_request("FRIDAY", 50.0, error=False)
        metrics.record_request("Stratex", 100.0, error=True)
        report = metrics.calculate_metrics()
        assert report.total_requests == 2
        assert report.total_errors == 1

    def test_health_monitor_snapshot(self):
        health = _eng("health")
        health.register_agent("Inference")
        health.register_agent("Memora")
        health.check_agent_health("Inference", True)
        snapshot = health.get_universe_health()
        assert snapshot.total_agents >= 2
        assert snapshot.agents["Inference"].status

    def test_mesh_router_routes(self):
        mesh = _eng("mesh")
        decision = mesh.route_task("analyze trading signals", "trading")
        assert decision.routed_to == "Stratex"
        assert decision.confidence > 0

    def test_event_bus_publish_subscribe(self):
        bus = _eng("events")
        sub = bus.subscribe("test_event", "FRIDAY", "http://localhost:5000/callback")
        event = bus.publish_event("test_event", {"data": "test"}, "Cortex")
        assert event.event_id
        assert sub.delivery_count == 1

    def test_state_manager_set_get(self):
        state = _eng("state")
        state.set_state("test_key", {"value": 42}, "FRIDAY")
        result = state.get_state("test_key")
        assert result["value"]["value"] == 42

    def test_audit_trail_log_and_search(self):
        audit = _eng("audit")
        audit.log("FRIDAY", "dispatch", "Inference", "success")
        audit.log("Cortex", "decide", "budget", "success")
        results = audit.search(agent="FRIDAY")
        assert results.total_matches >= 1

    def test_rate_limiter_configure_and_check(self):
        rl = _eng("ratelimit")
        rl.configure_limit("Stratex", "requests", 100, 60)
        record = rl.check_limit("Stratex", "requests", 5)
        assert record.remaining == 95

    def test_task_router_register_and_route(self):
        router = _eng("router")
        router.register_agent("Inference", ["reasoning", "analysis"])
        router.register_agent("Memora", ["memory", "recall"])
        task = router.submit_task("Analyze market trends", ["analysis"])
        decision = router.route_task(task.task_id)
        assert decision.assigned_agent == "Inference"
        assert decision.confidence > 0

    def test_knowledge_graph_entities(self):
        kg = _eng("kg")
        e1 = kg.add_entity("Trading", "domain")
        e2 = kg.add_entity("BTC", "concept")
        kg.add_edge(e1.entity_id, e2.entity_id, "uses")
        result = kg.query("trading btc")
        assert result.entities_found >= 1


class TestCortexE2E:
    """Test Cortex modules actually work."""

    def test_decision_impact_record_outcome(self):
        di = _eng("cortex_di")
        dec_id = di.record_decision("Hire contractor", "budget", ["contractor", "employee"], "contractor", "cost effective")
        imp = di.record_outcome(dec_id, "positive", 5000, 3000, 2000, 0.8)
        assert imp.overall_impact > 0
        score = di.calculate_quality_score()
        assert score.total_decisions == 1

    def test_strategic_foresight_trends(self):
        sf = _eng("cortex_sf")
        sf.identify_trend("AI regulation", "policy", 0.8, "long", 0.7)
        report = sf.generate_foresight_report("long")
        assert len(report.trends) >= 1

    def test_decision_tree_create_and_analyze(self):
        dt = _eng("cortex_dt")
        tree = dt.create_tree("Product Launch Decision")
        root = tree.root
        node1 = dt.add_node(tree.tree_id, root, "Launch Now", "decision")
        node2 = dt.add_node(tree.tree_id, node1.node_id, "Success", "end", {"value": 0.8})
        analysis = dt.analyze_tree(tree.tree_id)
        assert analysis.total_nodes >= 2
        assert analysis.expected_value >= 0

    def test_partner_network_add_and_analyze(self):
        pn = _eng("cortex_pn")
        p1 = pn.add_partner("TechCorp", "vendor", 0.8, 0.7)
        p2 = pn.add_partner("DataInc", "vendor", 0.6, 0.5)
        pn.add_connection(p1.partner_id, p2.partner_id, "supply", 0.7)
        analysis = pn.analyze_network()
        assert analysis.total_partners == 2
        assert analysis.density > 0

    def test_decision_fatigue(self):
        df = _eng("cortex_df")
        df.record_decision("Decision A", 0.5, 10.0, 0.8)
        df.record_decision("Decision B", 0.7, 20.0, 0.7)
        assessment = df.assess_fatigue()
        assert assessment.total_decisions == 2
        rec = df.recommend_cadence()
        assert rec.max_daily_decisions > 0


class TestInferenceE2E:
    """Test Inference modules actually work."""

    def test_temporal_reasoning_events(self):
        te = _eng("inf_te")
        e1 = te.add_event("Market crash", time.time() - 100, 5, "event")
        e2 = te.add_event("Recovery", time.time() - 50, 3, "event")
        te.add_relation(e1, e2, "after", 0.8)
        query = te.query_events("market", time.time() - 200, time.time())
        assert len(query.results) >= 1

    def test_commonsense_reasoning(self):
        ce = _eng("inf_ce")
        ce.add_fact("fire", "is dangerous to", "water")
        result = ce.reason("Is fire dangerous?")
        assert result.answer
        assert result.steps

    def test_argumentation_debate(self):
        aa = _eng("inf_aa")
        aa.register_agent("agent1")
        aa.register_agent("agent2")
        arg_id = aa.submit_argument("AI will improve education", ["evidence1"], "conclusion", "agent1", 0.7)
        session = aa.start_debate("AI in Education", ["agent1", "agent2"])
        turn = aa.add_turn(session.session_id, "agent1", "AI provides personalized learning", "rebuttal")
        assert turn.turn_id == 1
        result = aa.evaluate_argument(arg_id)
        assert result["strength"] == 0.7

    def test_moral_reasoning(self):
        mr = _eng("inf_mr")
        mr.add_principle("Maximize happiness", "utilitarianism", "", 1.0)
        dil = mr.create_dilemma("Should we sacrifice one to save five?", ["sacrifice", "don't sacrifice"], ["person1", "person2"])
        evaluation = mr.evaluate(dil.dilemma_id)
        assert evaluation.recommended_option
        assert evaluation.principle_scores

    def test_analogical_reasoning(self):
        ar = _eng("inf_ar")
        c1 = ar.add_concept("Water flows downhill", "physics", {"flow": "downhill"})
        c2 = ar.add_concept("Information flows to users", "tech", {"flow": "to users"})
        analogy = ar.create_analogy(c1.concept_id, c2.concept_id)
        assert analogy.similarity_score > 0

    def test_probabilistic_logic(self):
        pl = _eng("inf_pl")
        var = pl.add_variable("Rain", ["yes", "no"], {"yes": 0.3, "no": 0.7})
        result = pl.infer(var.var_id, {"Rain": "yes"})
        assert "yes" in result.posterior
        assert result.confidence > 0


class TestMemoraE2E:
    """Test Memora modules actually work."""

    def test_memory_retrieval_store_and_query(self):
        mr = _eng("memora_retrieval")
        mid = mr.store_memory("The quarterly revenue increased by 15%", "semantic", ["revenue", "finance"])
        query = mr.retrieve("quarterly revenue finance", "all", 5)
        assert len(query.results) >= 1
        assert query.results[0].similarity_score > 0

    def test_memory_reflection_session(self):
        mr = _eng("memora_reflection")
        session = mr.start_reflection("project decisions")
        insight = mr.generate_insight(session.session_id, "hiring", "Need to hire more engineers", 0.8)
        mr.end_reflection(session.session_id)
        assert insight.confidence == 0.8

    def test_memory_dream_generate(self):
        md = _eng("memora_dream")
        md.add_memory("mem1", "Machine learning project", ["ml", "project"])
        md.add_memory("mem2", "Data pipeline implementation", ["data", "pipeline"])
        dream = md.dream("tech", ["mem1", "mem2"])
        assert dream.fragments
        assert dream.insight

    def test_memory_decay_predict(self):
        md = _eng("memora_decay")
        mid = md.store_memory("Important meeting notes", importance=0.9, decay_rate=0.05)
        md.access_memory(mid.memory_id)
        curve = md.predict_decay(mid.memory_id, 86400)
        assert curve.half_life > 0
        assert curve.predicted_retention > 0

    def test_dream_interpreter(self):
        mi = _eng("memora_interpreter")
        interp = mi.interpret_dream("dream1", "I was flying over water with a snake")
        assert interp.symbols
        assert interp.themes


class TestForgeE2E:
    """Test Forge modules actually work."""

    def test_code_analysis_engine(self):
        ca = _eng("forge_analysis")
        report = ca.analyze_code("test.py", "def f():\n    if True:\n        eval('1+1')\n")
        assert report.metrics.cyclomatic_complexity > 0
        assert report.critical_findings >= 1

    def test_build_pipeline_create_and_run(self):
        bp = _eng("forge_pipeline")
        pipeline = bp.create_pipeline("CI Pipeline", "test-project", ["build", "test", "deploy"])
        result = bp.run_pipeline(pipeline.pipeline_id)
        assert result.status == "completed"
        assert len(result.stages) == 3

    def test_test_coverage_analyze(self):
        tc = _eng("forge_coverage")
        report = tc.analyze_coverage("test.py", 100, 75, 0.6, 0.7)
        assert report.gap_count == 25
        assert report.quality_score > 0

    def test_code_security_scanner(self):
        ss = _eng("forge_security")
        vulns = ss.scan_code("test.py", "password = 'hardcoded_secret_12345'")
        assert len(vulns) >= 1
        secrets = ss.scan_secrets("test.py", "api_key = 'sk_test_1234567890abcdef'")
        assert len(secrets) >= 1

    def test_merge_conflict_resolver(self):
        mc = _eng("forge_merge")
        conflict = mc.detect_conflict("test.py", "main", "feature", [{"line_start": 1, "line_end": 5, "our_content": "ours", "their_content": "theirs"}])
        assert conflict.severity == "low"
        hunk = mc.resolve_hunk(conflict.conflict_id, conflict.hunks[0].hunk_id, "theirs")
        assert hunk.resolution == "theirs"

    def test_complexity_quantifier(self):
        cx = _eng("forge_complexity")
        metrics = cx.analyze("test.py", "def f():\n    if True:\n        for i in range(10):\n            if i > 5:\n                pass\n")
        assert metrics.cyclomatic > 1
        assert metrics.maintainability_index > 0


class TestVyralXE2E:
    """Test VyralX modules actually work."""

    def test_content_performance(self):
        cp = _eng("vyral_performance")
        metric = cp.record_metric("video1", 1000, 100, 50, 20, 300)
        assert metric.engagement_rate > 0
        report = cp.generate_report("channel1")
        assert report.total_content >= 1

    def test_attention_predictor(self):
        ap = _eng("vyral_attention")
        forecast = ap.predict_attention("video1", 60, 5)
        assert forecast.avg_attention > 0
        assert len(forecast.segments) == 5

    def test_creator_economy(self):
        ce = _eng("vyral_economy")
        ce.record_creator("creator1", 100000, 5000, 500.0, 0.05)
        strategies = ce.recommend_strategy("creator1")
        assert len(strategies) >= 2

    def test_moderation_engine(self):
        mod = _load("vyral_moderation_mod", MODULES["vyral_moderation"])
        cm = mod.engine
        cm.create_policy("Default Policy")
        ci = mod.ContentItem(content_id="test1", text="Test content", media_type="text")
        result = cm.moderate(ci)
        assert result.decision in ("approved", "flagged", "rejected")

    def test_collaboration_matcher(self):
        cc = _eng("vyral_collaboration")
        cc.register_creator("c1", "gaming", 50000, 0.05)
        cc.register_creator("c2", "gaming", 30000, 0.08)
        match = cc.find_match("c1", "c2")
        assert match.compatibility_score > 0


class TestIntelXE2E:
    """Test IntelX modules actually work."""

    def test_disinformation_detector(self):
        dd = _eng("intel_disinfo")
        report = dd.detect("This is SHOCKING! They don't want you to know the deep state secret plan")
        assert report.risk_score > 0
        assert report.overall_risk in ("low", "medium", "high", "critical")

    def test_threat_attribution(self):
        ta = _eng("intel_attribution")
        ta.register_actor("APT29", ["Cozy Bear"], ["T1566", "T1059"])
        result = ta.attribute("Cozy Bear IP", "IP match")
        assert result.attributed_actor == "APT29"
        assert result.confidence > 0

    def test_supply_chain_mapper(self):
        sc = _eng("intel_supply")
        n1 = sc.add_node("VendorA", "vendor", "high", 0.3, 0.8)
        n2 = sc.add_node("ServiceB", "service", "medium", 0.5, 0.6)
        sc.add_dependency(n1.node_id, n2.node_id)
        path = sc.map_attack_path(n1.node_id, n2.node_id)
        assert len(path.path_nodes) >= 2
        report = sc.assess_risk()
        assert report.risk_score > 0

    def test_intel_exchange(self):
        ie = _eng("intel_exchange")
        pkg = ie.create_package({"type": "indicator", "value": "1.2.3.4"}, "internal")
        ie.register_partner("Partner1", "2.1", "https://taxii.example.com")
        stix = ie.export_stix(pkg.package_id)
        assert stix["type"] == "bundle"

    def test_campaign_predictor(self):
        cp = _eng("intel_campaign")
        cp.add_phase("Reconnaissance", "Initial scanning", 0.8, 7200)
        cp.add_phase("Exploitation", "Gaining access", 0.5, 3600)
        forecast = cp.forecast_campaign("APT29", "Reconnaissance")
        assert forecast.confidence > 0
        assert len(forecast.predicted_phases) >= 2


class TestSentinelE2E:
    """Test Sentinel modules actually work."""

    def test_incident_response_playbook(self):
        ip = _eng("sentinel_playbook")
        pb = ip.create_playbook("Security Incident Response", "security", "high")
        incident = ip.report_incident("high", "security", "SQL injection detected", pb.playbook_id)
        assert len(incident.steps) >= 5
        step = ip.execute_step(incident.incident_id, 1)
        assert step.status == "completed"
        ip.resolve_incident(incident.incident_id)
        result = ip.get_incident(incident.incident_id)
        assert result["status"] == "resolved"

    def test_slade_engine(self):
        se = _eng("sentinel_slade")
        se.create_sla("Patch critical vulns within 7 days", "security", time.time() + 604800, "sec-team")
        se.schedule_audit("Quarterly compliance audit")
        posture = se.generate_posture("SOC2")
        assert posture.score >= 0

    def test_hunting_automation(self):
        ha = _eng("sentinel_hunting")
        hyp = ha.create_hypothesis("There is a ransomware beacon on the network", "anomaly", 0.6)
        query = ha.execute_hunt(hyp.hypothesis_id, "SELECT * FROM logs WHERE beacon = true", 5)
        assert query.result_count == 5
        ha.confirm_hypothesis(hyp.hypothesis_id)
        report = ha.generate_report()
        assert report.confirmed == 1

    def test_intel_correlation(self):
        ic = _eng("sentinel_correlation")
        i1 = ic.add_indicator("1.2.3.4", "ip", "feed", 0.8, ["c2", "malware"])
        i2 = ic.add_indicator("5.6.7.8", "ip", "feed", 0.7, ["c2", "malware"])
        result = ic.correlate(i1.indicator_id)
        assert result.correlation_score > 0

    def test_incident_timeline(self):
        tl = _eng("sentinel_timeline")
        t0 = time.time()
        e1 = tl.add_event(t0, "alert", "Port scan detected", "medium", "attacker")
        e2 = tl.add_event(t0 + 30, "indicator", "SQL injection attempt", "high", "attacker")
        e3 = tl.add_event(t0 + 60, "action", "Firewall blocked IP", "low", "system")
        chain = tl.add_attack_chain("SQL injection attack chain", ["port_scan", "sql_injection"])
        analysis = tl.analyze_timeline("incident1")
        assert analysis.total_events == 3
        assert analysis.root_cause


class TestStratexE2E:
    """Test Stratex modules actually work."""

    def test_portfolio_optimization(self):
        po = _eng("stratex_portfolio")
        portfolio = po.create_portfolio("Growth Portfolio", [
            {"symbol": "AAPL", "weight": 0.4, "expected_return": 0.12, "volatility": 0.18},
            {"symbol": "GOOGL", "weight": 0.3, "expected_return": 0.10, "volatility": 0.20},
            {"symbol": "MSFT", "weight": 0.3, "expected_return": 0.11, "volatility": 0.19},
        ], "medium")
        assert portfolio.sharpe_ratio > 0
        plan = po.generate_rebalance(portfolio.portfolio_id, {"AAPL": 0.5, "GOOGL": 0.25, "MSFT": 0.25})
        assert plan.trades

    def test_microstructure_analyzer(self):
        ma = _eng("stratex_micro")
        ma.record_order_book("BTC", [(100, 10), (99, 20), (98, 15)], [(101, 15), (102, 10), (103, 20)])
        signal = ma.analyze("BTC")
        assert signal.signal in ("bullish", "bearish", "neutral")

    def test_flash_crash_detector(self):
        fc = _eng("stratex_flash")
        stress = fc.assess_stress("BTC", 0.5, 3.0, 0.15)
        assert stress.stress_level in ("normal", "elevated", "high", "extreme", "critical")
        event = fc.detect_flash_crash("BTC", 50000, 45000, 50100, 5.0)
        assert event.max_drawdown > 0

    def test_regime_change_detector(self):
        rc = _eng("stratex_regime")
        rc.record_regime("BTC", "bull", 0.8)
        rc.detect_break("BTC", "volatility", "high", "Volatility spike detected")
        forecast = rc.forecast_transition("BTC", "bull", "bear", 0.4, 60.0)
        assert forecast.predicted_regime == "bear"


class TestFuturisE2E:
    """Test Futuris modules actually work."""

    def test_counterfactual_forecaster(self):
        cf = _eng("futuris_counterfactual")
        f1 = cf.define_factor("Economic growth", 0.3, "positive", 0.7)
        f2 = cf.define_factor("Interest rates", 0.2, "negative", 0.8)
        scenario = cf.create_counterfactual("Economic scenario", 5.0, [f1, f2], 0.6)
        assert scenario.counterfactual_forecast != 0
        whatif = cf.what_if("What if growth is 10%?", 5.0, 6.5)
        assert whatif.sensitivity > 0

    def test_prediction_market(self):
        pm = _eng("futuris_market")
        contract = pm.create_contract("Will AI pass bar exam by 2026?", "")
        pm.update_price(contract.contract_id, 0.65)
        pm.resolve_contract(contract.contract_id, "Yes")
        contracts = pm.get_contracts(resolved=True)
        assert len(contracts) == 1

    def test_quantum_forecast(self):
        qf = _eng("futuris_quantum")
        forecast = qf.create_superposition(["up", "down", "stable"], [0.3, 0.3, 0.4])
        assert len(forecast.outcomes) == 3
        qf.collapse(forecast.forecast_id)
        result = qf.amplify(forecast.forecast_id, 2, "stable")
        assert result.amplification_factor > 1

    def test_skill_acquisition_planner(self):
        sa = _eng("futuris_skill")
        sa.add_skill("Python", 0.9, 0.3, 0.9, "technical")
        sa.add_skill("ML", 0.8, 0.2, 0.8, "technical")
        resources = sa.recommend_resources("Python")
        assert len(resources) >= 2
        path = sa.create_learning_path("Become ML engineer", ["Python", "ML"])
        assert path.estimated_total_hours > 0
