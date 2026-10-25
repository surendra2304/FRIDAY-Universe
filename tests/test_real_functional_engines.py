"""
tests/test_real_functional_engines.py — Real functional tests for working engines.

These tests actually RUN the engines and verify real outputs:
- DecisionEngine: multi-criteria decision making with real scoring
- ReasoningEngine: Bayesian updating, causal inference, debate
- MemoryEngine: TF-IDF semantic search, decay, consolidation
- TradingEngine: backtesting with real price data, signal generation
- CodeEngine: code analysis, generation, test generation
- SecurityEngine: threat detection, vulnerability scanning, posture
- ThreatIntelEngine: indicator correlation, campaign tracking
- ForecastEngine: time series forecasting, calibration, drift
- ContentEngine: performance prediction, recommendation, growth

Priority 1: Real functional verification — not structural checks
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    """Load a module directly from a file path to avoid name collisions."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load all engines
cortex_decision = load_module("Cortex/apps/api/src/cortex_api/real_decision_engine.py", "real_decision_engine")
inference_reasoning = load_module("Inference/app/agents/real_reasoning_engine.py", "real_reasoning_engine")
memora_memory = load_module("Memora/core/memory/real_memory_engine.py", "real_memory_engine")
stratex_trading = load_module("Stratex/real_trading_engine.py", "real_trading_engine")
forge_code = load_module("Forge/app/services/real_code_engine.py", "real_code_engine")
sentinel_security = load_module("Sentinel/app/services/real_security_engine.py", "real_security_engine")
intelx_threat = load_module("IntelX/intelx/services/real_threat_intel_engine.py", "real_threat_intel_engine")
futuris_forecast = load_module("Futuris/futuris/core/real_forecast_engine.py", "real_forecast_engine")
vyralx_content = load_module("VyralX/app/services/real_content_engine.py", "real_content_engine")


@pytest.fixture
def temp_state():
    """Create a temporary directory for state."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Decision Engine ─────────────────────────────────────────────────────────

class TestRealDecisionEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return cortex_decision.DecisionEngine(state_file=os.path.join(temp_state, "decisions.json"))

    def test_make_real_decision(self, engine):
        result = engine.decide(
            question="Which cloud provider should we use?",
            options=[
                {"name": "AWS", "scores": {"cost": 60, "reliability": 90, "features": 95},
                 "risks": ["complex pricing"], "benefits": ["most services"]},
                {"name": "GCP", "scores": {"cost": 75, "reliability": 85, "features": 80},
                 "risks": ["smaller ecosystem"], "benefits": ["better pricing"]},
                {"name": "Azure", "scores": {"cost": 70, "reliability": 88, "features": 85},
                 "risks": ["Microsoft dependency"], "benefits": ["enterprise integration"]},
            ],
            criteria=[
                {"name": "cost", "weight": 0.3},
                {"name": "reliability", "weight": 0.3},
                {"name": "features", "weight": 0.4},
            ]
        )
        assert result.best_option in ("AWS", "GCP", "Azure")
        assert len(result.ranking) == 3
        assert result.ranking[0]["option"] == result.best_option
        assert 0 <= result.confidence <= 1.0
        assert result.risk_level in ("low", "medium", "high", "critical")
        assert len(result.reasoning) > 20

    def test_decision_history_persisted(self, engine):
        engine.decide("Test?", [{"name": "A", "scores": {"x": 80}}], [{"name": "x", "weight": 1.0}])
        history = engine.get_history()
        assert len(history) >= 1
        patterns = engine.get_decision_patterns()
        assert patterns["total_decisions"] >= 1

    def test_risk_level_calculation(self, engine):
        result = engine.decide(
            "Pick one:",
            [{"name": "A", "scores": {"x": 50}}, {"name": "B", "scores": {"x": 52}}],
            [{"name": "x", "weight": 1.0}]
        )
        assert result.risk_level in ("high", "medium", "critical")

    def test_weighted_score_calculation(self, engine):
        result = engine.decide(
            "Pick best:",
            [
                {"name": "HighScore", "scores": {"a": 90, "b": 90}},
                {"name": "LowScore", "scores": {"a": 20, "b": 20}},
            ],
            [
                {"name": "a", "weight": 0.5},
                {"name": "b", "weight": 0.5},
            ]
        )
        assert result.best_option == "HighScore"
        assert result.total_scores["HighScore"] > result.total_scores["LowScore"]


# ── Reasoning Engine ────────────────────────────────────────────────────────

class TestRealReasoningEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return inference_reasoning.ReasoningEngine(state_file=os.path.join(temp_state, "reasoning.json"))

    def test_bayesian_update(self, engine):
        hyp = engine.bayesian_update(
            "Market will go up", prior=0.3,
            evidence="Positive earnings report", likelihood=0.8
        )
        assert hyp.posterior_probability > 0.3
        assert hyp.posterior_probability <= 1.0

    def test_bayesian_update_negative_evidence(self, engine):
        hyp = engine.bayesian_update(
            "Stock is safe", prior=0.7,
            evidence="Fraud investigation announced", likelihood=0.2
        )
        assert hyp.posterior_probability < 0.7

    def test_causal_chain(self, engine):
        engine.add_causal_link("Cloud outage", "Service down", 0.9, 60.0)
        engine.add_causal_link("Service down", "Revenue loss", 0.8, 300.0)
        causes = engine.find_root_causes("Revenue loss")
        assert "Cloud outage" in causes or "Service down" in causes

    def test_argument_strength(self, engine):
        arg = engine.analyze_argument(
            claim="We should invest in AI",
            premises=[
                "AI is transforming industries globally",
                "Our competitors are investing heavily in AI",
                "AI ROI has been proven in multiple case studies",
            ],
            conclusion="Investing in AI is strategically necessary"
        )
        assert 0 < arg.strength <= 1.0
        assert len(arg.premises) == 3

    def test_debate(self, engine):
        result = engine.debate(
            "Should we use microservices?",
            "Microservices improve scalability and fault tolerance",
            "Monoliths are simpler to develop and deploy",
            rounds=3
        )
        assert len(result["rounds"]) == 3
        assert result["winner"] in ("A", "B", "tie")

    def test_belief_revision(self, engine):
        hyp = engine.bayesian_update("Our product is secure", 0.5, "Security audit passed", 0.8)
        belief = engine._beliefs[hyp.hypothesis_id]
        original_conf = belief.confidence
        revised = engine.revise_belief(hyp.hypothesis_id, 0.9, "Updated assessment")
        assert revised.confidence >= original_conf


# ── Memory Engine ───────────────────────────────────────────────────────────

class TestRealMemoryEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return memora_memory.MemoryEngine(store_dir=os.path.join(temp_state, "memora"))

    def test_store_and_search(self, engine):
        engine.store("The deployment uses Docker containers", tags=["deployment"], importance=0.8)
        engine.store("Authentication uses OAuth 2.0", tags=["security"], importance=0.7)
        engine.store("Database is PostgreSQL", tags=["database"], importance=0.6)

        results = engine.search("Docker deployment", limit=5)
        assert len(results) > 0
        assert results[0].score > 0

    def test_tag_filtering(self, engine):
        engine.store("Redis cache layer", tags=["caching"], importance=0.8)
        engine.store("PostgreSQL database", tags=["database"], importance=0.7)
        results = engine.search("database", tags=["database"])
        assert len(results) >= 1

    def test_consolidation(self, engine):
        for i in range(10):
            engine.store(f"Memory item {i}", tags=["test"], importance=0.3)
        result = engine.consolidate(decay_rate=0.01, importance_threshold=0.1)
        assert result.consolidated >= 10

    def test_context_retrieval(self, engine):
        engine.store("Stratex handles quantitative trading", tags=["trading"], importance=0.9)
        engine.store("Sentinel monitors security threats", tags=["security"], importance=0.8)
        engine.store("Memora stores agent memories", tags=["memory"], importance=0.7)
        context = engine.get_context("trading agents", max_tokens=500)
        assert len(context) > 0

    def test_stats(self, engine):
        engine.store("Test memory", tags=["test"])
        engine.store("Another memory", tags=["test2"])
        stats = engine.get_stats()
        assert stats["total_memories"] == 2
        assert stats["active_memories"] == 2


# ── Trading Engine ───────────────────────────────────────────────────────────

class TestRealTradingEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return stratex_trading.TradingEngine(state_dir=os.path.join(temp_state, "stratex"))

    def test_technical_indicators(self, engine):
        prices = [i * 1.0 + (i % 5) * 0.5 for i in range(50)]
        sma = engine.sma(prices, 10)
        assert len(sma) == len(prices)
        assert sma[-1] > 0

        ema = engine.ema(prices, 12)
        assert len(ema) == len(prices)
        assert ema[-1] > 0

        rsi = engine.rsi(prices, 14)
        assert len(rsi) == len(prices)
        assert 0 <= rsi[-1] <= 100

        macd = engine.macd(prices)
        assert len(macd) == len(prices)

    def test_signal_generation(self, engine):
        bars = [
            stratex_trading.PriceBar(timestamp=i, open=p, high=p+1, low=p-1, close=p, volume=1000)
            for i, p in enumerate([i * 0.1 for i in range(50)] + [5.0 + (i % 10) * 0.1 for i in range(50)])
        ]
        signals = engine.generate_signals("TEST", bars, strategy="sma_cross")
        assert isinstance(signals, list)

    def test_backtest(self, engine):
        prices = []
        price = 100.0
        for i in range(200):
            price += (i % 20 - 10) * 0.1
            if i % 50 == 0:
                price += 2.0
            prices.append(price)

        bars = [
            stratex_trading.PriceBar(timestamp=i, open=p, high=p+0.5, low=p-0.5, close=p, volume=10000)
            for i, p in enumerate(prices)
        ]

        result = engine.backtest("TEST", bars, strategy="sma_cross", initial_capital=10000)
        assert result.total_return_pct is not None
        assert result.sharpe_ratio is not None
        assert result.max_drawdown_pct >= 0
        assert result.total_trades >= 0

    def test_portfolio_optimization(self, engine):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, 0.015],
            "B": [0.02, 0.01, 0.015, -0.005, 0.025],
            "C": [-0.01, 0.03, 0.02, 0.01, 0.015],
        }
        result = engine.optimize_portfolio(returns)
        assert "weights" in result
        assert sum(result["weights"].values()) == pytest.approx(1.0, abs=0.01)


# ── Code Engine ──────────────────────────────────────────────────────────────

class TestRealCodeEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return forge_code.CodeEngine(template_dir=os.path.join(temp_state, "templates"))

    def test_code_analysis(self, engine):
        code = '''
class MyClass:
    def method_one(self):
        return 1

    def method_two(self, x):
        if x > 5:
            while x > 0:
                x -= 1
        return x
'''
        analysis = engine.analyze(code, "python")
        assert analysis.lines_of_code > 0
        assert analysis.number_of_classes == 1
        assert analysis.number_of_methods >= 2
        assert analysis.cyclomatic_complexity >= 2
        assert 0 <= analysis.maintainability_index <= 100

    def test_code_generation(self, engine):
        result = engine.generate_function("hello", ["name"], "Say hello", "return f'Hello {name}'")
        assert "def hello" in result.code
        assert "name" in result.code

    def test_class_generation(self, engine):
        result = engine.generate_class(
            "Calculator", "A simple calculator",
            init_args=[], init_body="pass",
            methods=[{"name": "add", "args": ["a", "b"], "doc": "Add numbers", "body": "return a + b"}]
        )
        assert "class Calculator" in result.code
        assert "def add" in result.code

    def test_test_generation(self, engine):
        code = '''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
'''
        result = engine.generate_tests(code)
        assert "def test_add" in result.test_code
        assert "def test_multiply" in result.test_code
        assert result.test_count >= 2

    def test_code_review(self, engine):
        code = 'password = "admin123"\ndef test():\n    if True:\n        return True'
        review = engine.review(code)
        assert "summary" in review
        assert "issues" in review
        assert review["score"] >= 0


# ── Security Engine ─────────────────────────────────────────────────────────

class TestRealSecurityEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return sentinel_security.SecurityEngine(state_dir=os.path.join(temp_state, "sentinel"))

    def test_threat_detection(self, engine):
        threats = engine.detect_threats(
            "SELECT * FROM users WHERE id='1' OR '1'='1' --",
            source="web_request"
        )
        assert len(threats) >= 1
        assert any(t.threat_type == "sql_injection" for t in threats)

    def test_xss_detection(self, engine):
        threats = engine.detect_threats("<script>alert('xss')</script>", source="web_request")
        assert len(threats) >= 1

    def test_vulnerability_scanning(self, engine):
        code = 'password = "supersecret123"\napi_key = "sk-12345"'
        vulns = engine.scan_code(code, "test.py")
        assert len(vulns) >= 1

    def test_security_posture(self, engine):
        engine.detect_threats("union select", source="test")
        posture = engine.assess_posture()
        assert 0 <= posture.score <= 100
        assert posture.level in ("excellent", "good", "fair", "poor", "critical")

    def test_incident_response(self, engine):
        incident = engine.create_incident("SQL Injection Attack", "high", "Detected SQL injection")
        assert incident.status == "open"
        engine.respond_to_incident(incident.incident_id, "Investigating")
        engine.respond_to_incident(incident.incident_id, "Resolve")
        open_incidents = engine.get_open_incidents()
        assert all(i.incident_id != incident.incident_id for i in open_incidents)


# ── Threat Intel Engine ─────────────────────────────────────────────────────

class TestRealThreatIntelEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return intelx_threat.ThreatIntelEngine(state_dir=os.path.join(temp_state, "intelx"))

    def test_indicator_management(self, engine):
        ind1 = engine.add_indicator("192.168.1.1", "ip", confidence=0.8, tags=["malware"])
        ind2 = engine.add_indicator("malicious.com", "domain", confidence=0.7, tags=["malware"])
        ind3 = engine.add_indicator("evil.org", "domain", confidence=0.6, tags=["phishing"])
        results = engine.search_indicators(min_confidence=0.5)
        assert len(results) >= 2

    def test_correlation(self, engine):
        ind1 = engine.add_indicator("10.0.0.1", "ip", confidence=0.8, tags=["c2"])
        ind2 = engine.add_indicator("10.0.0.2", "ip", confidence=0.8, tags=["c2"])
        correlations = engine.correlate_indicators([ind1.indicator_id, ind2.indicator_id])
        assert len(correlations) >= 1

    def test_campaign_tracking(self, engine):
        ind1 = engine.add_indicator("bad.com", "domain", confidence=0.8, tags=["ransomware"])
        campaign = engine.track_campaign(
            "Ransomware Campaign 2024", "LockBit", "Large scale ransomware campaign",
            severity="critical", indicators=[ind1.indicator_id]
        )
        assert campaign.campaign_id
        assert campaign.severity == "critical"

    def test_report_generation(self, engine):
        ind1 = engine.add_indicator("threat.com", "domain", confidence=0.9, tags=["apt"])
        report = engine.generate_report(
            "APT Activity Report", "Active APT campaign detected",
            [ind1.indicator_id], ["osint", "threat_feed"]
        )
        assert report.report_id
        assert report.confidence > 0

    def test_stats(self, engine):
        engine.add_indicator("1.2.3.4", "ip")
        engine.add_indicator("test.com", "domain")
        stats = engine.get_stats()
        assert stats["total_indicators"] == 2


# ── Forecast Engine ─────────────────────────────────────────────────────────

class TestRealForecastEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return futuris_forecast.ForecastEngine(state_dir=os.path.join(temp_state, "futuris"))

    def test_time_series_forecasting(self, engine):
        series = [i * 1.0 + (i % 3) * 0.5 for i in range(30)]
        sma = engine.simple_moving_average(series, 10)
        assert sma > 0
        ses = engine.exponential_smoothing(series, 0.3)
        assert ses > 0
        holt = engine.holt_linear(series, 0.5, 0.3)
        assert holt > 0
        arima = engine.arima_simple(series, 1)
        assert arima > 0

    def test_ensemble_forecast(self, engine):
        series = [100 + i * 0.5 + (i % 5) * 0.1 for i in range(50)]
        forecast = engine.ensemble_forecast("TEST", series)
        assert forecast.prediction > 0
        assert forecast.lower_bound <= forecast.prediction
        assert forecast.upper_bound >= forecast.prediction
        assert 0 < forecast.confidence <= 1.0

    def test_calibration(self, engine):
        series = [100 + i * 0.1 for i in range(30)]
        forecast = engine.ensemble_forecast("CAL", series)
        for i in range(5):
            engine.record_actual("CAL", forecast.prediction + (i * 0.5 - 1.0),
                                 timestamp=forecast.timestamp + (i + 1) * forecast.horizon_sec)
        result = engine.calibrate("CAL")
        assert result.n_samples >= 1

    def test_drift_detection(self, engine):
        for i in range(40):
            engine.record_actual("DRIFT", 100 + (i % 5) * 0.1, timestamp=i * 3600)
        result = engine.detect_drift("DRIFT", window=20)
        assert isinstance(result.drift_detected, bool)

    def test_scenario_analysis(self, engine):
        series = [100 + i * 0.5 for i in range(20)]
        result = engine.analyze_scenario(
            "TEST", series, "Market scenario", "Bullish/Bearish/Flat",
            {"bullish": 0.3, "bearish": 0.2, "flat": 0.5},
            {"bullish": 0.8, "bearish": -0.5, "flat": 0.0}
        )
        assert result.impact_score != 0.0


# ── Content Engine ───────────────────────────────────────────────────────────

class TestRealContentEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return vyralx_content.ContentEngine(state_dir=os.path.join(temp_state, "vyralx"))

    def test_content_prediction(self, engine):
        prediction = engine.predict_performance(
            "How to Build AI Apps in 2024",
            "Tutorial covering the best practices for building AI applications",
            tags=["ai", "tutorial", "programming"]
        )
        assert prediction["engagement_score"] > 0
        assert prediction["predicted_views"] > 0

    def test_content_recommendation(self, engine):
        c1 = engine.add_content("Python Tutorial", "Learn Python", tags=["python", "tutorial"], category="education")
        c2 = engine.add_content("AI Guide", "AI basics", tags=["ai", "tutorial"], category="education")
        c3 = engine.add_content("Cooking 101", "Cooking basics", tags=["cooking"], category="food")
        engine.record_engagement(c1.content_id, views=1000, likes=50, shares=10)
        engine.record_engagement(c2.content_id, views=500, likes=20, shares=5)
        recommendations = engine.recommend([c1.content_id, c2.content_id], limit=3)
        assert len(recommendations) > 0

    def test_ab_test_analysis(self, engine):
        result = engine.analyze_ab_test(
            {"views": 1000, "engagement": 50},
            {"views": 1000, "engagement": 80}
        )
        assert "improvement_pct" in result
        assert "significance" in result
        assert result["winner"] in ("A", "B")

    def test_growth_prediction(self, engine):
        content = engine.add_content("Test", "Test content", tags=["test"])
        engine.record_engagement(content.content_id, views=1000, likes=50, shares=10)
        prediction = engine.predict_growth(
            current_subscribers=1000,
            content_history=[content],
            strategy="organic"
        )
        assert prediction.predicted_subscribers >= 1000
        assert prediction.timeline
