"""
tests/test_real_advanced_engines.py — Functional tests for advanced real engines.

Tests real working implementations:
- Cortex: A/B testing, customer segmentation, competitive intelligence, risk assessment
- Inference: Causal inference, multi-agent argumentation, probabilistic logic, analogy
- Memora: Knowledge graph, consolidation, spaced repetition
- Stratex: Options pricing, risk analytics, live execution, regime detection
- Forge: Autonomous code repair, deployment pipeline, architecture analysis, coverage
- Sentinel: SIEM integration, behavioral anomaly, zero-trust, threat hunting
- IntelX: Dark web monitor, predictive threat, adversary emulation, intel sharing
- Futuris: Quantum forecast, prediction market, counterfactual, explainability, maintenance
- VyralX: Autonomous daemon, full pipeline, performance analysis, creator economy, translation

Priority 1: Real functional verification of advanced engines
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load all advanced engines
cortex_adv = load_module("Cortex/apps/api/src/cortex_api/real_advanced_engines.py", "adv_cortex")
inference_adv = load_module("Inference/app/agents/real_advanced_reasoning.py", "adv_inference")
memora_adv = load_module("Memora/core/memory/real_advanced_memory.py", "adv_memora")
stratex_adv = load_module("Stratex/real_advanced_trading.py", "adv_stratex")
forge_adv = load_module("Forge/app/services/real_advanced_code.py", "adv_forge")
sentinel_adv = load_module("Sentinel/app/services/real_advanced_security.py", "adv_sentinel")
intelx_adv = load_module("IntelX/intelx/services/real_advanced_threat_intel.py", "adv_intelx")
futuris_adv = load_module("Futuris/futuris/core/real_advanced_forecast.py", "adv_futuris")
vyralx_adv = load_module("VyralX/app/services/real_advanced_content.py", "adv_vyralx")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Cortex Advanced Engines ────────────────────────────────────────────────

class TestCortexABTesting:
    def test_ab_test_analysis(self):
        result = cortex_adv.ab_framework.analyze(
            {"visitors": 1000, "conversions": 50},
            {"visitors": 1000, "conversions": 80},
            test_name="Landing page test"
        )
        assert result.winner in ("A", "B")
        assert result.improvement_pct != 0.0
        assert result.significance in ("significant", "highly_significant", "not_significant")

    def test_ab_test_large_sample(self):
        result = cortex_adv.ab_framework.analyze(
            {"visitors": 10000, "conversions": 100},
            {"visitors": 10000, "conversions": 150}
        )
        assert result.conversion_rate_a < result.conversion_rate_b
        assert result.p_value > 0.0


class TestCortexSegmentation:
    def test_customer_segmentation(self):
        # Generate synthetic customer data
        customers = []
        for i in range(100):
            customers.append({
                "spending": random.uniform(0, 1) if (i < 25) else random.uniform(0.3, 0.6),
                "frequency": random.uniform(0, 1) if (i < 25) else random.uniform(0.3, 0.6),
                "loyalty": random.uniform(0, 1),
            })
        segments = cortex_adv.segmentation_engine.segment_customers(customers, k=4)
        assert len(segments) >= 1
        assert all(s.size > 0 for s in segments)


class TestCortexCompetitiveIntel:
    def test_swot_analysis(self):
        result = cortex_adv.competitive_intel.analyze_competitor(
            "CompetitorX",
            {"market_share": 0.25, "brand_recognition": 0.8,
             "innovation_score": 0.7, "customer_satisfaction": 0.85,
             "debt_ratio": 0.3, "customer_churn": 0.05,
             "market_growth": 0.08, "unmet_needs": 0.4,
             "technology_shift": 0.6, "competition_intensity": 0.6,
             "regulatory_risk": 0.3, "market_decline": 0.02}
        )
        assert len(result.strengths) > 0
        assert len(result.opportunities) > 0


class TestCortexRiskAssessment:
    def test_risk_assessment(self):
        risk = cortex_adv.risk_framework.assess_risk(
            "Financial", "Market downturn", 0.3, 0.8
        )
        assert risk.risk_score > 0
        assert risk.severity in ("critical", "high", "medium", "low")

    def test_risk_matrix(self):
        risks = [
            cortex_adv.risk_framework.assess_risk("A", "Risk 1", 0.8, 0.9),
            cortex_adv.risk_framework.assess_risk("A", "Risk 2", 0.3, 0.3),
        ]
        matrix = cortex_adv.risk_framework.risk_matrix(risks)
        assert len(matrix) >= 1


# ── Inference Advanced Engines ─────────────────────────────────────────────

class TestInferenceCausalInference:
    @pytest.fixture
    def engine(self, temp_state):
        e = inference_adv.CausalInferenceEngine(state_file=os.path.join(temp_state, "causal.json"))
        return e

    def test_adjustment(self, engine):
        data = []
        for _ in range(100):
            data.append({"treatment": random.randint(0, 1), "outcome": random.uniform(0, 1), "confounder": random.randint(0, 1)})
        query = engine.adjust(data, "treatment", "outcome", ["confounder"])
        assert query.estimate is not None
        assert "ci_lower" in dir(query)


class TestInferenceArgumentation:
    def test_multi_agent_debate(self):
        result = inference_adv.argumentation_engine.run_debate(
            "Should we invest in AI?",
            {"Agent1": "AI will transform our business", "Agent2": "AI requires too much investment"},
            rounds=3
        )
        assert result["winner"] in ("Agent1", "Agent2")
        assert len(result["rounds"]) > 0


class TestInferenceProbabilisticLogic:
    def test_belief_propagation(self):
        engine = inference_adv.ProbabilisticLogicEngine()
        engine.add_fact("Fact A", 0.8)
        engine.add_fact("Fact B", 0.6, depends_on=[list(engine._facts.keys())[0]])
        prob = engine.propagate_beliefs(list(engine._facts.keys())[1])
        assert 0 <= prob <= 1.0


class TestInferenceAnalogy:
    def test_case_based_reasoning(self):
        engine = inference_adv.AnalogicalReasoningEngine()
        engine.add_case("Market crash 2020", "Buy dips", "success", features={"market": 0.8})
        result = engine.solve_by_analogy("Market crash 2024", features={"market": 0.8})
        assert result["confidence"] > 0


class TestInferenceConflictResolution:
    def test_resolve_conflicts(self):
        sources = {
            "source_a": {"claim1": 0.8, "claim2": 0.6},
            "source_b": {"claim1": 0.7, "claim2": 0.5},
        }
        result = inference_adv.conflict_resolver.resolve(sources)
        assert "claim1" in result
        assert result["claim1"]["sources"] == 2


# ── Memora Advanced Engines ───────────────────────────────────────────────

class TestMemoraKnowledgeGraph:
    @pytest.fixture
    def engine(self, temp_state):
        return memora_adv.KnowledgeGraphMemory(store_dir=os.path.join(temp_state, "kg"))

    def test_entity_extraction(self, engine):
        entities = engine.extract_entities("Apple released new iPhone. Google announced Pixel.")
        assert len(entities) > 0
        assert any(e.name == "Apple" for e in entities)

    def test_relationship_query(self, engine):
        engine.extract_entities("FRIDAY Universe uses Cortex and Memora")
        entities = list(engine._entities.values())
        if len(entities) >= 2:
            rel = engine.add_relationship(entities[0].name, entities[1].name, "uses")
            assert rel is not None


class TestMemoraConsolidation:
    def test_consolidate_memories(self):
        memories = [
            {"content": "Redis is a cache", "tags": ["tech"]},
            {"content": "Redis stores key-value pairs", "tags": ["tech"]},
            {"content": "PostgreSQL is a database", "tags": ["tech"]},
        ]
        result = memora_adv.consolidation_engine.consolidate(memories)
        assert result.original_count == 3
        assert len(result.key_points) > 0


class TestMemoraReinforcement:
    def test_spaced_repetition(self):
        engine = memora_adv.MemoryReinforcementEngine()
        item = engine.add_item("Learn about Docker")
        assert item.interval == 1.0
        reviewed = engine.review(item.item_id, quality=5)
        assert reviewed.interval > 1.0  # Should increase after good review

    def test_due_items(self):
        engine = memora_adv.MemoryReinforcementEngine()
        item = engine.add_item("Test")
        item.next_review = time.time() - 1  # Make it due
        due = engine.get_due_items()
        assert len(due) == 1


# ── Stratex Advanced Engines ────────────────────────────────────────────────

class TestStratexOptionsPricing:
    def test_black_scholes(self):
        result = stratex_adv.options_engine.price_option(
            "AAPL", "call", 150, 155, 30 * 24 * 3600, 0.05, 0.25
        )
        assert result.price > 0
        assert 0 <= result.delta <= 1.0
        assert result.gamma > 0

    def test_put_pricing(self):
        result = stratex_adv.options_engine.price_option(
            "AAPL", "put", 150, 145, 30 * 24 * 3600, 0.05, 0.25
        )
        assert result.price > 0
        assert -1 <= result.delta <= 0  # Put delta is negative


class TestStratexRiskAnalytics:
    def test_var_calculation(self):
        returns = [random.uniform(-0.05, 0.05) for _ in range(100)]
        var_95, var_99 = stratex_adv.risk_engine.calculate_var(returns, 10000)
        assert var_95 > 0
        assert var_99 >= var_95

    def test_max_drawdown(self):
        curve = [100, 110, 105, 120, 90, 80, 130]
        dd = stratex_adv.risk_engine.calculate_max_drawdown(curve)
        assert dd > 0

    def test_full_risk_report(self):
        returns = [random.uniform(-0.03, 0.03) for _ in range(50)]
        curve = [10000 * (1 + sum(returns[:i])) for i in range(51)]
        report = stratex_adv.risk_engine.full_risk_report(
            returns, 10000, curve, {"AAPL": 5000, "MSFT": 5000}
        )
        assert report.var_95 > 0
        assert report.stress_loss < 0


class TestStratexExecution:
    def test_market_order(self):
        engine = stratex_adv.LiveExecutionEngine()
        order = engine.place_market_order("AAPL", "buy", 100, 150.0)
        assert order.status == "filled"
        assert engine.get_position("AAPL") == 100

    def test_limit_order(self):
        engine = stratex_adv.LiveExecutionEngine()
        order = engine.place_limit_order("AAPL", "buy", 100, 145.0, 150.0)
        assert order.status == "pending"  # Limit below current price


class TestStratexRegimeDetection:
    def test_regime_detection(self):
        # Bullish trend
        prices = [100 + i * 0.5 for i in range(60)]
        result = stratex_adv.regime_detector.detect_regime("TEST", prices)
        assert result.current_regime in ("bull", "bear", "sideways", "volatile")
        assert result.confidence > 0


# ── Forge Advanced Engines ─────────────────────────────────────────────────

class TestForgeCodeRepair:
    def test_bug_detection(self):
        code = '''
try:
    x = eval("1 + 1")
except:
    pass
'''
        bugs = forge_adv.code_repair.detect_bugs(code, "test.py")
        assert len(bugs) >= 2  # eval + bare except

    def test_apply_fix(self):
        code = "x = eval('1+1')"
        bugs = forge_adv.code_repair.detect_bugs(code, "test.py")
        if bugs:
            fixed = forge_adv.code_repair.apply_fix(code, bugs[0])
            assert "eval" not in fixed or "ast.literal_eval" in fixed


class TestForgePipeline:
    def test_pipeline_creation(self):
        engine = forge_adv.pipeline_manager
        pid = engine.create_pipeline("test", ["lint", "test", "build", "deploy"])
        result = engine.run_pipeline(pid)
        assert result["status"] == "success"
        assert len(result["stages"]) == 4


class TestForgeArchitecture:
    def test_architecture_analysis(self):
        source_files = {
            "api.py": "class API: pass\nimport os",
            "service.py": "class Service: pass\nimport json",
            "model.py": "class Model: pass",
        }
        report = forge_adv.architecture_analyzer.analyze(source_files)
        assert report.total_classes == 3
        assert len(report.layers) > 0


class TestForgeCoverage:
    def test_coverage_analysis(self):
        source = "def add(a, b):\n    return a + b\n"
        test = "def test_add():\n    assert add(1, 2) == 3\n"
        report = forge_adv.coverage_analyzer.analyze_coverage(source, test, "add.py")
        assert report.coverage_pct > 0
        assert len(report.recommendation) > 0


# ── Sentinel Advanced Engines ─────────────────────────────────────────────

class TestSentinelSIEM:
    @pytest.fixture
    def engine(self, temp_state):
        return sentinel_adv.SIEMIntegrationBridge(state_dir=os.path.join(temp_state, "siem"))

    def test_log_ingestion(self, engine):
        entry = engine.ingest_log("auth_server", "warning", "Login failed", "auth")
        assert entry.source == "auth_server"

    def test_correlation(self, engine):
        for i in range(5):
            engine.ingest_log("auth", "warning", f"Login failed attempt {i}", "auth")
        events = engine.correlate_logs(time_window_sec=600)
        assert len(events) >= 1


class TestSentinelBehavior:
    def test_anomaly_detection(self):
        engine = sentinel_adv.behavior_detector
        engine.create_profile("user1", [9, 10, 11, 14, 15], 1800.0, {"api": 50})
        result = engine.detect_anomaly("user1", 3, 3600.0, 200)
        assert result["anomaly_detected"] is True


class TestSentinelZeroTrust:
    def test_access_control(self):
        engine = sentinel_adv.zero_trust
        engine.set_user_role("alice", "developer")
        engine.grant_access("repo1", "developer")
        decision = engine.check_access("alice", "repo1")
        assert decision.allowed is True

        decision2 = engine.check_access("bob", "repo1")
        assert decision2.allowed is False


class TestSentinelThreatHunting:
    def test_threat_hunt(self):
        result = sentinel_adv.threat_hunter.hunt(
            "There is a ransomware attack",
            ["encrypted_files", "bitcoin_payment", "ransom note"],
            {"known_threats": ["encrypted_files", "bitcoin_payment", "ransom note"]}
        )
        assert result.result in ("confirmed", "inconclusive")
        assert result.confidence > 0.3


# ── IntelX Advanced Engines ───────────────────────────────────────────────

class TestIntelXDarkWeb:
    @pytest.fixture
    def engine(self, temp_state):
        return intelx_adv.DarkWebMonitor(state_dir=os.path.join(temp_state, "darkweb"))

    def test_scan_credentials(self, engine):
        findings = engine.scan({
            "source": "leak_site", "has_credentials": True,
            "count": 1000, "confidence": 0.8,
        })
        assert len(findings) >= 1
        assert findings[0].severity == "critical"


class TestIntelXPredictiveThreat:
    def test_threat_prediction(self):
        history = [
            {"timestamp": time.time() - 10 * 86400, "indicators": ["malware.com"]},
            {"timestamp": time.time() - 5 * 86400, "indicators": ["malware.com"]},
            {"timestamp": time.time() - 1 * 86400, "indicators": ["malware.com"]},
        ]
        result = intelx_adv.predictive_threat.predict("malware", history)
        assert result.probability > 0
        assert len(result.recommendations) > 0


class TestIntelXAdversaryEmulation:
    def test_adversary_profile(self):
        engine = intelx_adv.adversary_emulation
        profile = engine.create_profile(
            "APT29 Emulation", "Initial Access", "Emulate APT29 techniques",
            ["T1078", "T1059", "T1003"]
        )
        assert len(profile.techniques) == 3

    def test_coverage_assessment(self):
        engine = intelx_adv.adversary_emulation
        profile = engine.create_profile("Test", "Execution", "Test", ["T1059", "T1078"])
        coverage = engine.assess_coverage(profile, ["Command and Scripting Interpreter"])
        assert coverage["coverage_pct"] > 0


class TestIntelXIntelSharing:
    def test_package_creation(self):
        engine = intelx_adv.intel_sharing
        pkg = engine.create_package("Threat Report", ["bad.com"], 0.8, tlp="amber")
        assert pkg.package_id

    def test_tlp_restrictions(self):
        engine = intelx_adv.intel_sharing
        pkg = engine.create_package("Secret", ["x.com"], 0.9, tlp="red")
        assert engine.share_package(pkg.package_id, "public") is False
        assert engine.share_package(pkg.package_id, "tier1") is True


# ── Futuris Advanced Engines ───────────────────────────────────────────────

class TestFuturisQuantumForecast:
    def test_quantum_forecast(self):
        series = [100 + i * 0.5 + random.uniform(-1, 1) for i in range(30)]
        result = futuris_adv.quantum_forecast.forecast("TEST", series)
        assert result.prediction > 0
        assert len(result.superposition_probs) >= 1
        assert result.quantum_advantage >= 0


class TestFuturisPredictionMarket:
    def test_market_creation(self):
        engine = futuris_adv.prediction_market
        contract = engine.create_contract("Will AI exceed GDP?", 365 * 86400)
        assert contract.contract_id

    def test_trade_and_price(self):
        engine = futuris_adv.prediction_market
        contract = engine.create_contract("Test question?", 365 * 86400)
        engine.place_trade(contract.contract_id, "yes", 100, 0.7)
        prob = engine.get_market_implied_probability(contract.contract_id)
        assert prob["yes_probability"] > 0


class TestFuturisCounterfactual:
    def test_what_if_analysis(self):
        result = futuris_adv.counterfactual.analyze(
            100.0, "If interest rates rise",
            {"interest_rate": 0.5, "inflation": -0.2},
            {"interest_rate": 2.0, "inflation": 0.5}
        )
        assert result.difference != 0.0
        assert len(result.key_factors) > 0


class TestFuturisExplainability:
    def test_feature_contributions(self):
        contributions = futuris_adv.explainability.explain(
            100.0, {"feature1": 2.0, "feature2": 3.0},
            {"feature1": 1.0, "feature2": 1.0},
            {"feature1": 10.0, "feature2": 5.0}
        )
        assert len(contributions) == 2
        assert contributions[0].contribution != 0.0


class TestFuturisPredictiveMaintenance:
    def test_equipment_health(self):
        result = futuris_adv.predictive_maintenance.predict(
            "engine1",
            {"temperature": 120, "vibration": 8.0, "pressure": 50},
            {"temperature": 100, "vibration": 5.0, "pressure": 40}
        )
        assert 0 <= result.health_score <= 1.0
        assert result.urgency in ("critical", "high", "medium", "low")


# ── VyralX Advanced Engines ───────────────────────────────────────────────

class TestVyralXDaemon:
    @pytest.fixture
    def engine(self, temp_state):
        return vyralx_adv.AutonomousContentDaemon(state_dir=os.path.join(temp_state, "daemon"))

    def test_task_scheduling(self, engine):
        task = engine.schedule_task("analyze", "Analyze performance")
        assert task.status == "pending"

    def test_run_daily_cycle(self, engine):
        results = engine.run_daily_cycle()
        assert "analyze" in results
        assert "schedule" in results
        assert "report" in results


class TestVyralXPipeline:
    def test_full_pipeline(self):
        engine = vyralx_adv.pipeline_engine
        steps = engine.create_pipeline("AI Tutorial")
        result = engine.run_pipeline(0)
        assert result["pipeline_complete"] is True
        assert result["steps_completed"] == 7


class TestVyralXPerformance:
    def test_performance_analysis(self):
        metrics = vyralx_adv.performance_analyzer.analyze(
            "c1", "Test Video", 10000, 50000.0, 500, 100, 50, 600.0
        )
        assert metrics.engagement_rate > 0
        assert metrics.projected_earnings > 0

    def test_compare_content(self):
        m1 = vyralx_adv.performance_analyzer.analyze("c1", "A", 1000, 1000, 50, 10, 5, 100.0)
        m2 = vyralx_adv.performance_analyzer.analyze("c2", "B", 2000, 3000, 100, 30, 20, 100.0)
        comparison = vyralx_adv.performance_analyzer.compare_content([m1, m2])
        assert comparison["total_content"] == 2
        assert "best_performer" in comparison


class TestVyralXTranslation:
    def test_translation(self):
        result = vyralx_adv.translator.translate("hello world", "en", "es")
        assert "hola" in result.translated_text
        assert result.confidence > 0
