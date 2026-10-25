"""
tests/test_real_deep_engines.py — Functional tests for deep real engines.

Tests real working implementations:
- Cortex: Recommendation personalizer, predictive analytics, strategic foresight
- Inference: (already covered in advanced)
- Memora: (already covered in advanced)
- Stratex: Sentiment analysis, order flow analyzer, pattern recognition
- Forge: Code security scanner, dependency analyzer, refactoring engine
- Sentinel: Vulnerability management, compliance audit, incident playbook
- IntelX: Threat forecast, quality evaluator, disinformation detector, supply chain
- Futuris: Ensemble selector, forecasting engine, stress tester, realtime impact
- VyralX: Audience intelligence, growth strategy, calendar manager, moderation

Priority 1: Real functional verification of deep engines
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


# Load all deep engines
cortex_deep = load_module("Cortex/apps/api/src/cortex_api/real_deep_engines.py", "deep_cortex")
stratex_deep = load_module("Stratex/real_deep_trading.py", "deep_stratex")
forge_deep = load_module("Forge/app/services/real_deep_code.py", "deep_forge")
sentinel_deep = load_module("Sentinel/app/services/real_deep_security.py", "deep_sentinel")
intelx_deep = load_module("IntelX/intelx/services/real_deep_threat_intel.py", "deep_intelx")
futuris_deep = load_module("Futuris/futuris/core/real_deep_forecast.py", "deep_futuris")
vyralx_deep = load_module("VyralX/app/services/real_deep_content.py", "deep_vyralx")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Cortex Deep Engines ────────────────────────────────────────────────────

class TestCortexRecommender:
    def test_collaborative_filtering(self):
        engine = cortex_deep.RecommendationPersonalizer()
        # Create user-item interactions
        for i in range(5):
            engine.record_interaction(f"user{i}", f"item{i}")
            engine.record_interaction(f"user{i}", f"item{i+5}")

        recs = engine.recommend_collaborative("user0", top_k=3)
        assert isinstance(recs, list)

    def test_content_based_filtering(self):
        engine = cortex_deep.RecommendationPersonalizer()
        engine.add_item_features("item1", {"f0": 0.8, "f1": 0.6})
        engine.add_item_features("item2", {"f0": 0.5, "f1": 0.9})
        engine.record_interaction("user1", "item1")

        recs = engine.recommend_content_based("user1", top_k=3)
        assert isinstance(recs, list)


class TestCortexPredictive:
    def test_linear_regression_training(self):
        engine = cortex_deep.PredictiveAnalyticsEngine()
        X = [{"f0": float(i), "f1": float(i * 2)} for i in range(20)]
        y = [float(i * 3 + 5) for i in range(20)]

        coefs = engine.train_linear_regression("model1", X, y)
        assert len(coefs) > 0

        prediction = engine.predict("model1", {"f0": 10.0, "f1": 20.0})
        assert prediction.prediction > 0

    def test_logistic_regression_training(self):
        engine = cortex_deep.PredictiveAnalyticsEngine()
        X = [{"f0": random.random(), "f1": random.random()} for _ in range(50)]
        y = [1 if i < 25 else 0 for i in range(50)]

        coefs = engine.train_logistic_regression("clf1", X, y)
        assert len(coefs) > 0

        prediction = engine.predict_classification("clf1", {"f0": 0.8, "f1": 0.7})
        assert 0 <= prediction.prediction <= 1.0


class TestCortexForesight:
    def test_scenario_generation(self):
        scenarios = cortex_deep.foresight.generate_scenarios(
            "AI Market", ["regulation", "adoption", "competition"]
        )
        assert len(scenarios) == 3
        assert all(s.probabilities for s in scenarios)
        assert len(scenarios[0].preparation_actions) > 0


# ── Stratex Deep Engines ──────────────────────────────────────────────────

class TestStratexSentiment:
    def test_sentiment_analysis(self):
        result = stratex_deep.sentiment_engine.analyze(
            "AAPL", "Apple stock surged to record profits with strong growth"
        )
        assert result.sentiment_score > 0
        assert result.dominant_sentiment == "positive"

    def test_negative_sentiment(self):
        result = stratex_deep.sentiment_engine.analyze(
            "TSLA", "Tesla plunged after disappointing earnings and weak outlook"
        )
        assert result.sentiment_score < 0
        assert result.dominant_sentiment == "negative"

    def test_aggregate_sentiment(self):
        results = [
            stratex_deep.sentiment_engine.analyze("A", "Stock rose sharply"),
            stratex_deep.sentiment_engine.analyze("B", "Stock fell hard"),
        ]
        agg = stratex_deep.sentiment_engine.aggregate_sentiment(results)
        assert "score" in agg


class TestStratexOrderFlow:
    def test_order_flow_analysis(self):
        trades = [
            {"side": "buy", "quantity": 100},
            {"side": "buy", "quantity": 500},
            {"side": "sell", "quantity": 100},
            {"side": "buy", "quantity": 1000},
        ]
        result = stratex_deep.order_flow.analyze("TEST", trades)
        assert result.imbalance > 0
        assert result.signal in ("bullish", "bearish", "neutral")


class TestStratexPatternRecognition:
    def test_trend_detection(self):
        prices = [100 + i * 0.5 for i in range(30)]
        patterns = stratex_deep.pattern_engine.detect_patterns("TEST", prices)
        assert len(patterns) >= 1
        assert any(p.pattern == "uptrend" for p in patterns)


# ── Forge Deep Engines ─────────────────────────────────────────────────────

class TestForgeSecurityScanner:
    def test_security_scan(self):
        code = "password = 'secret123'\neval('1+1')\nh = hashlib.md5('x'.encode())"
        findings = forge_deep.security_scanner.scan(code, "test.py")
        assert len(findings) >= 2

    def test_security_summary(self):
        code = "eval('1+1')\nexec('x=1')\npassword = 'secret'"
        findings = forge_deep.security_scanner.scan(code, "test.py")
        summary = forge_deep.security_scanner.get_summary(findings)
        assert summary["critical"] >= 2
        assert summary["risk_score"] > 0


class TestForgeDependencyAnalyzer:
    def test_dependency_analysis(self):
        reqs = {"django": "==3.2.0", "flask": "==1.1.0", "requests": "==2.20.0", "numpy": "==1.20.0"}
        result = forge_deep.dependency_analyzer.analyze(reqs)
        assert result.total_dependencies == 4
        assert len(result.vulnerable_dependencies) >= 1  # flask < 2.0


class TestForgeRefactoringEngine:
    def test_refactoring_suggestions(self):
        code = """
# TODO: fix this
def long_function():
    pass
print("hello")
"""
        suggestions = forge_deep.refactoring_engine.analyze(code, "test.py")
        assert len(suggestions) >= 1


# ── Sentinel Deep Engines ──────────────────────────────────────────────────

class TestSentinelVulnManagement:
    @pytest.fixture
    def engine(self, temp_state):
        return sentinel_deep.VulnerabilityManagementSystem(state_dir=os.path.join(temp_state, "vuln"))

    def test_add_vulnerability(self, engine):
        vuln = engine.add_vulnerability(
            "CVE-2024-0001", "high", "SQL Injection",
            "SQL injection in login", 7.5, "MyApp"
        )
        assert vuln.status == "open"

    def test_vulnerability_summary(self, engine):
        engine.add_vulnerability("CVE-1", "critical", "RCE", "Remote code execution", 9.8, "App")
        engine.add_vulnerability("CVE-2", "high", "SQLi", "SQL injection", 7.5, "App")
        summary = engine.get_vulnerability_summary()
        assert summary["total"] == 2
        assert summary["risk_score"] > 0

    def test_update_status(self, engine):
        vuln = engine.add_vulnerability("CVE-1", "high", "Test", "Test", 7.0, "App")
        assert engine.update_status(vuln.vuln_id, "resolved", "1.0.1") is True


class TestSentinelCompliance:
    def test_compliance_audit(self):
        checks = sentinel_deep.compliance_audit.audit("CIS")
        assert len(checks) == 4
        assert all(c.status in ("pass", "fail", "warning") for c in checks)

    def test_compliance_score(self):
        checks = sentinel_deep.compliance_audit.audit("SOC2")
        score = sentinel_deep.compliance_audit.compliance_score(checks)
        assert 0 <= score <= 100


class TestSentinelIncidentPlaybook:
    def test_playbook_execution(self):
        steps = sentinel_deep.incident_playbook.execute_playbook("data_breach")
        assert len(steps) == 5
        assert all(s.status == "completed" for s in steps)

    def test_playbook_types(self):
        for pb_type in ("data_breach", "malware_infection", "ddos_attack"):
            steps = sentinel_deep.incident_playbook.get_playbook(pb_type)
            assert len(steps) == 5


# ── IntelX Deep Engines ───────────────────────────────────────────────────

class TestIntelXThreatForecast:
    def test_threat_forecast(self):
        history = [
            {"timestamp": time.time() - i * 86400, "indicators": ["malware"]}
            for i in range(10)
        ]
        result = intelx_deep.threat_forecast.forecast("malware", history)
        assert result.probability > 0
        assert result.trend in ("increasing", "decreasing", "stable")


class TestIntelXQualityEvaluator:
    def test_quality_evaluation(self):
        indicators = [
            {"value": "1.2.3.4", "type": "ip", "confidence": 0.8, "tags": ["malware"], "first_seen": time.time()},
            {"value": "bad.com", "type": "domain", "confidence": 0.7, "tags": ["phishing"], "first_seen": time.time()},
        ]
        result = intelx_deep.quality_evaluator.evaluate("test_source", indicators, [])
        assert result.overall > 0
        assert result.grade in ("A", "B", "C", "D", "F")


class TestIntelXDisinformationDetector:
    def test_disinformation_detection(self):
        result = intelx_deep.disinfo_detector.detect(
            "Shocking! They don't want you to know this secret!"
        )
        assert result.is_disinformation is True
        assert len(result.indicators) > 0

    def test_legitimate_content(self):
        result = intelx_deep.disinfo_detector.detect(
            "According to recent reports, the economy grew by 2% this quarter."
        )
        assert result.is_disinformation is False


class TestIntelXSupplyChain:
    def test_supply_chain_risk(self):
        deps = [
            {"name": "django", "version": "2.0.0", "maintainer": "unknown", "downloads": 500, "known_vulnerabilities": 3},
            {"name": "flask", "version": "2.0.0", "maintainer": "pallets", "downloads": 50000, "known_vulnerabilities": 0},
        ]
        risks = intelx_deep.supply_chain_mapper.analyze(deps)
        assert len(risks) == 2
        assert risks[0].risk_score >= risks[1].risk_score


# ── Futuris Deep Engines ───────────────────────────────────────────────────

class TestFuturisEnsembleSelector:
    def test_model_selection(self):
        ModelPerformance = futuris_deep.ModelPerformance
        models = [
            ModelPerformance("model_a", 10.0, 8.0, 5.0, 0.8, 0.0),
            ModelPerformance("model_b", 5.0, 4.0, 2.0, 0.9, 0.0),
            ModelPerformance("model_c", 15.0, 12.0, 8.0, 0.7, 0.0),
        ]
        weights = futuris_deep.ensemble_selector.select_models(models, top_k=2)
        assert len(weights) == 2
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)


class TestFuturisForecastingEngine:
    def test_forecast(self):
        series = [100 + i * 0.5 + random.uniform(-1, 1) for i in range(30)]
        result = futuris_deep.forecasting_engine.forecast(series, horizon=5)
        assert len(result.forecast_values) == 5
        assert result.method in ("sma", "ses", "holt", "arima")

    def test_auto_method_selection(self):
        # Trend data
        series = [100 + i * 1.0 for i in range(30)]
        result = futuris_deep.forecasting_engine.forecast(series, method="auto", horizon=5)
        assert result.method in ("holt", "arima")


class TestFuturisStressTester:
    def test_standard_scenarios(self):
        results = futuris_deep.stress_tester.standard_scenarios(10000)
        assert len(results) == 5
        assert all(r.impact < 0 for r in results)  # All negative

    def test_custom_scenarios(self):
        results = futuris_deep.stress_tester.run_stress_test(
            10000,
            [{"name": "Custom", "shock_pct": -10}]
        )
        assert len(results) == 1
        assert results[0].stressed == 9000


class TestFuturisRealtimeImpact:
    def test_event_impact(self):
        result = futuris_deep.realtime_impact.assess_event(
            "economic", "Market crash",
            ["stocks", "crypto"], {"stocks": 0.7, "crypto": 0.3}
        )
        assert result.impact_score < 0  # Negative impact


# ── VyralX Deep Engines ───────────────────────────────────────────────────

class TestVyralXAudienceIntelligence:
    def test_audience_segmentation(self):
        viewers = []
        for i in range(100):
            viewers.append({
                "age": random.randint(18, 60),
                "gender": random.choice(["male", "female"]),
                "location": random.choice(["US", "UK", "India"]),
                "interests": random.sample(["gaming", "music", "tech", "food", "travel"], 2),
                "watch_time": random.uniform(60, 600),
                "spending": random.uniform(0, 100),
            })
        segments = vyralx_deep.audience_intel.analyze_audience(viewers)
        assert len(segments) > 0
        assert sum(s.size for s in segments) == 100

    def test_audience_summary(self):
        viewers = [{"age": 25, "gender": "male", "location": "US", "interests": ["gaming"], "watch_time": 300, "spending": 50}]
        segments = vyralx_deep.audience_intel.analyze_audience(viewers)
        summary = vyralx_deep.audience_intel.get_audience_summary(segments)
        assert summary["total_audience"] == 1


class TestVyralXGrowthStrategy:
    def test_strategy_generation(self):
        strategies = vyralx_deep.growth_strategy.generate_strategies({"subscribers": 5000})
        assert len(strategies) == 4
        assert all(s.expected_growth_pct > 0 for s in strategies)

    def test_recommended_strategy(self):
        strategies = vyralx_deep.growth_strategy.generate_strategies({"subscribers": 500})
        recommended = vyralx_deep.growth_strategy.get_recommended_strategy(
            {"subscribers": 500, "engagement_rate": 0.03}, strategies
        )
        assert recommended.name == "Collaboration Outreach"


class TestVyralXCalendar:
    @pytest.fixture
    def engine(self, temp_state):
        return vyralx_deep.ContentCalendarManager(state_dir=os.path.join(temp_state, "calendar"))

    def test_schedule_post(self, engine):
        post = engine.schedule_post("Test Video", time.time() + 86400)
        assert post.status == "scheduled"

    def test_get_schedule(self, engine):
        engine.schedule_post("Video 1", time.time() + 86400)
        engine.schedule_post("Video 2", time.time() + 2 * 86400)
        schedule = engine.get_schedule(days=3)
        assert len(schedule) == 2

    def test_optimal_times(self):
        times = vyralx_deep.calendar_manager.get_optimal_posting_times()
        assert "youtube" in times
        assert len(times["youtube"]) == 3


class TestVyralXModeration:
    def test_approve_content(self):
        result = vyralx_deep.moderation_engine.moderate("c1", "This is a great educational video")
        assert result.action == "approved"

    def test_reject_hate_speech(self):
        result = vyralx_deep.moderation_engine.moderate("c2", "I hate them and want to destroy them")
        assert result.action == "rejected"

    def test_flag_profanity(self):
        result = vyralx_deep.moderation_engine.moderate("c3", "This is shit and that guy is an asshole")
        assert result.action == "flagged"
