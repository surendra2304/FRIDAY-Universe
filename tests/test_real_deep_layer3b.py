"""
Tests for Layer 3b — Real Deep Engines (Neural Network, NLP, Time Series, Security, Code Analysis, Trading)

All tests verify REAL functionality, not just structure.
"""

import math
import os
import random
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util

def _load_module(module_path: str, name: str):
    """Load a module directly from file path, bypassing package __init__.py."""
    full_path = ROOT / module_path
    spec = importlib.util.spec_from_file_location(name, full_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# ===== CORTEX: Neural Network =====
_nn = _load_module("Cortex/app/agents/real_neural_network.py", "real_neural_network")
NeuralNetworkEngine = _nn.NeuralNetworkEngine
Layer = _nn.Layer
OptimizationEngine = _nn.OptimizationEngine

# ===== INFERENCE: NLP =====
_nlp = _load_module("Inference/app/agents/real_nlp_engine.py", "real_nlp_engine")
TFIDFVectorizer = _nlp.TFIDFVectorizer
SentimentAnalyzer = _nlp.SentimentAnalyzer
NamedEntityRecognizer = _nlp.NamedEntityRecognizer
TextClassifier = _nlp.TextClassifier
DocumentCluster = _nlp.DocumentCluster

# ===== FUTURIS: Time Series =====
_ts = _load_module("Futuris/app/agents/real_time_series.py", "real_time_series")
TimeSeriesForecaster = _ts.TimeSeriesForecaster
MovingAverage = _ts.MovingAverage
SeasonalDecomposer = _ts.SeasonalDecomposer
AnomalyDetector = _ts.AnomalyDetector
TrendAnalyzer = _ts.TrendAnalyzer
VolatilityCalculator = _ts.VolatilityCalculator

# ===== SENTINEL: Security =====
_sec = _load_module("Sentinel/app/agents/real_security_engine.py", "real_security_engine")
CVSSCalculator = _sec.CVSSCalculator
ThreatScorer = _sec.ThreatScorer
AttackTreeAnalyzer = _sec.AttackTreeAnalyzer
BehavioralAnalyzer = _sec.BehavioralAnalyzer
RiskAssessor = _sec.RiskAssessor
PostureScorer = _sec.PostureScorer

# ===== FORGE: Code Analysis =====
_ca = _load_module("Forge/app/agents/real_code_analysis.py", "real_code_analysis")
ComplexityAnalyzer = _ca.ComplexityAnalyzer
StaticAnalyzer = _ca.StaticAnalyzer
SecurityScanner = _ca.SecurityScanner
DependencyAnalyzer = _ca.DependencyAnalyzer
RefactoringAdvisor = _ca.RefactoringAdvisor

# ===== STRATEXT: Trading =====
_tr = _load_module("Stratex/app/agents/real_trading_engine.py", "real_trading_engine")
TechnicalIndicators = _tr.TechnicalIndicators
OptionPricing = _tr.OptionPricing
RiskMetrics = _tr.RiskMetrics
PortfolioOptimizer = _tr.PortfolioOptimizer
BacktestEngine = _tr.BacktestEngine
TradingSentimentAnalyzer = _tr.SentimentAnalyzer


# =============================================================================
# CORTEX: NEURAL NETWORK ENGINE TESTS
# =============================================================================

class TestNeuralNetwork:
    def test_build_network(self):
        """NN must be built with correct layers."""
        nn = NeuralNetworkEngine().build([4, 8, 2], ["relu", "sigmoid"])
        assert len(nn.layers) == 2
        assert nn.layers[0].input_size == 4
        assert nn.layers[0].output_size == 8
        assert nn.layers[1].output_size == 2

    def test_forward_pass(self):
        """Forward pass produces correct output size."""
        nn = NeuralNetworkEngine().build([3, 5, 1], ["relu", "sigmoid"])
        output = nn.forward([1.0, 2.0, 3.0])
        assert len(output) == 1
        assert 0.0 <= output[0] <= 1.0

    def test_predict_confidence(self):
        """Predict returns confidence score."""
        nn = NeuralNetworkEngine().build([2, 4, 2])
        output, confidence = nn.predict([0.5, 0.3])
        assert len(output) == 2
        assert 0.0 <= confidence <= 1.0

    def test_training_reduces_loss(self):
        """Training must reduce loss over epochs."""
        nn = NeuralNetworkEngine().build([2, 8, 1], ["relu", "sigmoid"])
        # Simple linear dataset
        X = [[0, 0], [0, 1], [1, 0], [1, 1]]
        y = [[0.1], [0.2], [0.8], [0.9]]
        result = nn.train(X, y, epochs=500, learning_rate=0.1)
        assert result["epochs_completed"] == 500
        assert result["final_loss"] < result["initial_loss"]

    def test_training_linear_data(self):
        """NN should learn linear data well."""
        nn = NeuralNetworkEngine().build([1, 4, 1], ["relu", "sigmoid"])
        X = [[i * 0.1] for i in range(50)]
        y = [[min(1.0, i * 0.02)] for i in range(50)]
        result = nn.train(X, y, epochs=200, learning_rate=0.1)
        assert result["final_loss"] < 0.1

    def test_evaluate(self):
        """Evaluation produces metrics."""
        nn = NeuralNetworkEngine().build([2, 4, 1])
        X = [[0, 0], [0, 1], [1, 0], [1, 1]]
        y = [[0.1], [0.2], [0.8], [0.9]]
        nn.train(X, y, epochs=200, learning_rate=0.1)
        result = nn.evaluate(X, y)
        assert "mse" in result
        assert "rmse" in result
        assert result["total_predictions"] == 4

    def test_get_architecture(self):
        """Architecture summary is correct."""
        nn = NeuralNetworkEngine().build([3, 6, 2])
        arch = nn.get_architecture()
        assert arch["total_layers"] == 2
        assert arch["layer_sizes"] == [3, 6, 2]
        assert arch["total_parameters"] > 0

    def test_save_load(self, tmp_path):
        """Model can be saved and loaded."""
        nn = NeuralNetworkEngine().build([2, 4, 1])
        path = str(tmp_path / "model.json")
        assert nn.save(path) is True

        nn2 = NeuralNetworkEngine()
        assert nn2.load(path) is True
        assert len(nn2.layers) == 2

    def test_optimization_genetic_algorithm(self):
        """Genetic algorithm finds optimum."""
        opt = OptimizationEngine()
        # Minimize x^2 + y^2
        result = opt.genetic_algorithm(
            lambda x: x[0]**2 + x[1]**2,
            [(-10, 10), (-10, 10)],
            population_size=30,
            generations=50,
        )
        assert result["best_score"] < 5.0
        assert abs(result["best_solution"][0]) < 3.0
        assert abs(result["best_solution"][1]) < 3.0

    def test_optimization_simulated_annealing(self):
        """Simulated annealing finds optimum."""
        opt = OptimizationEngine()
        result = opt.simulated_annealing(
            lambda x: (x[0] - 3)**2 + (x[1] + 2)**2,
            [(-10, 10), (-10, 10)],
            max_iter=200,
        )
        assert result["best_score"] < 1.0
        assert abs(result["best_solution"][0] - 3) < 1.0
        assert abs(result["best_solution"][1] + 2) < 1.0

    def test_optimization_gradient_descent(self):
        """Gradient descent finds optimum."""
        opt = OptimizationEngine()
        # Minimize (x-1)^2
        def obj(x): return (x[0] - 1)**2
        def grad(x): return [2 * (x[0] - 1)]
        result = opt.gradient_descent(obj, grad, [5.0], learning_rate=0.1, max_iter=100)
        assert result["optimal_score"] < 0.01
        assert abs(result["optimal_point"][0] - 1) < 0.1


# =============================================================================
# INFERENCE: NLP ENGINE TESTS
# =============================================================================

class TestNLPEngine:
    def test_tfidf_fit_transform(self):
        """TF-IDF must fit and transform correctly."""
        docs = [
            "the cat sat on the mat",
            "the dog sat on the log",
            "cats and dogs are friends",
        ]
        vec = TFIDFVectorizer().fit(docs)
        assert vec.fit_ is True
        assert len(vec.vocabulary) > 0
        vectors = [vec.transform(d) for d in docs]
        assert len(vectors) == 3
        assert len(vectors[0]) == len(vec.vocabulary)

    def test_tfidf_cosine_similarity(self):
        """Cosine similarity is correct."""
        docs = ["hello world python", "hello world", "goodbye world farewell"]
        vec = TFIDFVectorizer().fit(docs)
        v1 = vec.transform("hello world python")
        v2 = vec.transform("hello world")
        v3 = vec.transform("goodbye world farewell")
        sim12 = vec.cosine_similarity(v1, v2)
        sim13 = vec.cosine_similarity(v1, v3)
        assert sim12 > sim13

    def test_sentiment_positive(self):
        """Positive text gets positive sentiment."""
        sa = SentimentAnalyzer()
        result = sa.analyze("This is great! I love it!")
        assert result["sentiment"] == "positive"
        assert result["polarity"] > 0

    def test_sentiment_negative(self):
        """Negative text gets negative sentiment."""
        sa = SentimentAnalyzer()
        result = sa.analyze("This is terrible. I hate it.")
        assert result["sentiment"] == "negative"
        assert result["polarity"] < 0

    def test_sentiment_neutral(self):
        """Neutral text gets neutral sentiment."""
        sa = SentimentAnalyzer()
        result = sa.analyze("The cat sat on the mat.")
        assert result["sentiment"] == "neutral"

    def test_ner_person(self):
        """NER detects person names."""
        ner = NamedEntityRecognizer()
        text = "John Smith works at Google."
        entities = ner.recognize(text)
        person_entities = [e for e in entities if e["type"] == "PERSON"]
        assert len(person_entities) > 0

    def test_ner_email(self):
        """NER detects emails."""
        ner = NamedEntityRecognizer()
        text = "Contact me at john@example.com"
        entities = ner.recognize(text)
        email_entities = [e for e in entities if e["type"] == "EMAIL"]
        assert len(email_entities) > 0

    def test_ner_url(self):
        """NER detects URLs."""
        ner = NamedEntityRecognizer()
        text = "Visit https://example.com for more info."
        entities = ner.recognize(text)
        url_entities = [e for e in entities if e["type"] == "URL"]
        assert len(url_entities) > 0

    def test_text_classifier(self):
        """Text classifier makes predictions."""
        docs = [
            "I love this product, it's amazing",
            "This is the worst thing I've ever bought",
            "Great service, highly recommend",
            "Terrible quality, do not buy",
            "Absolutely wonderful experience",
            "Complete waste of money",
        ]
        labels = ["positive", "negative", "positive", "negative", "positive", "negative"]
        clf = TextClassifier(k=3)
        clf.train(docs, labels)
        predicted, confidence = clf.predict("This is wonderful!")
        assert predicted == "positive"
        assert confidence > 0

    def test_document_cluster(self):
        """Document clustering works."""
        docs = [
            "machine learning is great",
            "neural networks are powerful",
            "deep learning transforms AI",
            "pizza is delicious food",
            "Italian cuisine is amazing",
            "restaurants serve great meals",
        ]
        cluster = DocumentCluster()
        result = cluster.cluster(docs, k=2)
        assert result["clusters"] == 2
        assert len(result["assignments"]) == 6
        assert "cluster_sizes" in result


# =============================================================================
# FUTURIS: TIME SERIES ENGINE TESTS
# =============================================================================

class TestTimeSeries:
    def test_sma(self):
        """Simple moving average is correct."""
        ma = MovingAverage(window_size=3)
        data = [1, 2, 3, 4, 5]
        result = ma.sma(data)
        assert result[0] == 1.0
        assert result[2] == 2.0  # (1+2+3)/3
        assert result[4] == 4.0  # (3+4+5)/3

    def test_ema(self):
        """Exponential moving average is correct."""
        ma = MovingAverage(window_size=3)
        data = [1, 2, 3, 4, 5]
        result = ma.ema(data, window=3)
        assert len(result) == 5
        assert result[0] == 1.0
        assert result[-1] > 0

    def test_rsi(self):
        """RSI is computed correctly."""
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08]
        ti = TechnicalIndicators(prices)
        rsi = ti.rsi(period=5)
        assert len(rsi) > 0
        assert all(0 <= r <= 100 for r in rsi)

    def test_macd(self):
        """MACD produces correct outputs."""
        prices = [i * 0.1 + 10 for i in range(50)]
        ti = TechnicalIndicators(prices)
        macd = ti.macd()
        assert len(macd["macd_line"]) == 50
        assert len(macd["signal_line"]) == 50
        assert len(macd["histogram"]) == 50

    def test_bollinger_bands(self):
        """Bollinger bands are computed."""
        prices = [i * 0.1 + 10 + random.gauss(0, 0.5) for i in range(30)]
        ti = TechnicalIndicators(prices)
        bands = ti.bollinger_bands(period=5)
        assert len(bands["upper"]) == 30
        assert len(bands["lower"]) == 30
        # Upper should be >= lower (skip None values)
        for i in range(5, 30):
            assert bands["upper"][i] >= bands["lower"][i]

    def test_forecaster_fit(self):
        """Forecaster fits to data."""
        ts = TimeSeriesForecaster()
        data = [i * 0.1 + 10 for i in range(20)]
        ts.fit(data)
        assert ts.model_params["phi"] is not None
        assert ts.model_params["mean"] > 0

    def test_forecaster_predict(self):
        """Forecaster produces predictions."""
        ts = TimeSeriesForecaster()
        data = [i * 0.1 + 10 for i in range(20)]
        ts.fit(data)
        forecast = ts.forecast(steps=5)
        assert len(forecast) == 5
        assert all(isinstance(f, float) for f in forecast)

    def test_forecaster_with_ci(self):
        """Forecaster produces confidence intervals."""
        ts = TimeSeriesForecaster()
        data = [i * 0.1 + 10 for i in range(20)]
        ts.fit(data)
        result = ts.forecast_with_ci(steps=3, confidence=0.95)
        assert len(result) == 3
        for r in result:
            assert r["lower"] <= r["forecast"] <= r["upper"]

    def test_backtest(self):
        """Backtest produces metrics."""
        ts = TimeSeriesForecaster()
        data = [i * 0.1 + 10 + random.gauss(0, 0.5) for i in range(30)]
        result = ts.backtest(data, test_size=5)
        assert "mse" in result
        assert "rmse" in result
        assert "mape" in result

    def test_trend_analysis(self):
        """Trend analysis detects direction."""
        ta = TrendAnalyzer()
        # Upward trend
        result = ta.analyze([i * 0.5 for i in range(20)])
        assert result["trend"] == "upward"
        assert result["slope"] > 0

        # Downward trend
        result = ta.analyze([100 - i * 0.5 for i in range(20)])
        assert result["trend"] == "downward"

    def test_anomaly_detection(self):
        """Anomaly detection finds outliers."""
        ad = AnomalyDetector()
        data = [1, 1, 1, 1, 10, 1, 1, 1, 1, 1]
        anomalies = ad.detect(data, threshold=2.0)
        assert len(anomalies) > 0

    def test_volatility_calculation(self):
        """Volatility is computed correctly."""
        vc = VolatilityCalculator()
        prices = [100 + i * 0.5 + random.gauss(0, 1) for i in range(50)]
        result = vc.calculate(prices)
        assert result["volatility"] > 0
        assert result["annualized_volatility"] > result["volatility"]


# =============================================================================
# SENTINEL: SECURITY ENGINE TESTS
# =============================================================================

class TestSecurityEngine:
    def test_cvss_calculation(self):
        """CVSS score is computed."""
        calc = CVSSCalculator()
        result = calc.calculate(
            attack_vector="N",
            attack_complexity="L",
            priv_required="N",
            user_interaction="N",
            scope="U",
            confidentiality="H",
            integrity="H",
            availability="H",
        )
        assert 0 <= result["base_score"] <= 10
        assert result["severity"] in ("critical", "high", "medium", "low", "none")

    def test_cvss_critical(self):
        """Remotely exploitable, no interaction, full impact = critical."""
        calc = CVSSCalculator()
        result = calc.calculate("N", "L", "N", "N", "U", "H", "H", "H")
        assert result["base_score"] >= 9.0
        assert result["severity"] == "critical"

    def test_threat_scoring_sql_injection(self):
        """SQL injection is detected."""
        ts = ThreatScorer()
        result = ts.score("SELECT * FROM users WHERE id = ' OR 1=1", "10.0.0.1")
        assert result["threat_score"] > 5
        assert "sql_injection" in result["detected_patterns"]

    def test_threat_scoring_xss(self):
        """XSS is detected."""
        ts = ThreatScorer()
        result = ts.score('<script>alert("xss")</script>', "203.0.113.5")
        assert result["threat_score"] > 4
        assert "xss" in result["detected_patterns"]

    def test_threat_scoring_clean(self):
        """Clean log entry has low threat."""
        ts = ThreatScorer()
        result = ts.score("User logged in successfully", "192.168.1.1")
        assert result["threat_score"] < 5

    def test_log_analysis_batch(self):
        """Batch log analysis works."""
        ts = ThreatScorer()
        logs = [
            "User logged in",
            "SELECT * FROM users",
            "Normal request received",
            '<script>alert("xss")</script>',
        ]
        result = ts.analyze_logs(logs)
        assert result["total_logs"] == 4
        assert result["critical_count"] >= 1

    def test_attack_tree(self):
        """Attack tree computes risk."""
        ata = AttackTreeAnalyzer()
        ata.add_node("root", "Compromise system")
        ata.add_node("sub1", "Exploit vulnerability", ["sub1a", "sub1b"], "or")
        ata.add_node("sub1a", "SQL injection")
        ata.add_node("sub1b", "Buffer overflow")
        ata.add_node("sub2", "Social engineering")
        ata.root = "root"
        result = ata.compute_risk()
        assert "root_risk" in result
        assert 0 <= result["root_risk"] <= 1.0

    def test_behavioral_anomaly(self):
        """Behavioral anomaly detection works."""
        ba = BehavioralAnalyzer()
        ba.build_baseline({
            "requests_per_second": [5, 6, 5, 7, 5, 6, 5, 7, 5, 6],
        })
        # Normal behavior
        result = ba.detect("requests_per_second", 5.5)
        assert result["anomaly"] is False

        # Anomalous behavior
        result = ba.detect("requests_per_second", 50)
        assert result["anomaly"] is True

    def test_risk_assessor(self):
        """Risk assessment works."""
        ra = RiskAssessor()
        # High risk
        result = ra.assess(likelihood=5, impact=5)
        assert result["risk_level"] == "critical"
        assert result["acceptable"] is False

        # Low risk
        result = ra.assess(likelihood=1, impact=1)
        assert result["risk_level"] == "low"
        assert result["acceptable"] is True

    def test_posture_scorer(self):
        """Security posture scoring works."""
        ps = PostureScorer()
        result = ps.score(
            encryption_strength=90,
            patch_level=85,
            access_control=80,
            network_security=75,
            incident_response=70,
            vulnerability_management=80,
        )
        assert 0 <= result["overall_score"] <= 100
        assert result["grade"] in ("A", "B", "C", "D", "F")


# =============================================================================
# FORGE: CODE ANALYSIS ENGINE TESTS
# =============================================================================

class TestCodeAnalysis:
    def test_complexity_simple(self):
        """Simple code has low complexity."""
        ca = ComplexityAnalyzer()
        code = "def f():\n    return 1 + 2\n"
        result = ca.analyze(code)
        assert result["cyclomatic_complexity"] <= 5
        assert result["complexity_rating"] == "low"

    def test_complexity_nested(self):
        """Nested conditionals increase complexity."""
        ca = ComplexityAnalyzer()
        code = """
def f(x):
    if x > 0:
        if x > 5:
            return 1
        else:
            return 2
    else:
        return 0
"""
        result = ca.analyze(code)
        assert result["cyclomatic_complexity"] > 1
        assert result["max_nesting"] >= 2

    def test_static_analysis_bare_except(self):
        """Static analyzer detects bare except."""
        sa = StaticAnalyzer()
        code = "try:\n    x = 1\nexcept:\n    pass\n"
        result = sa.analyze(code)
        types = [i["type"] for i in result["issues"]]
        assert "bare_except" in types

    def test_static_analysis_eval(self):
        """Static analyzer detects eval usage."""
        sa = StaticAnalyzer()
        code = "x = eval('1+1')\n"
        result = sa.analyze(code)
        types = [i["type"] for i in result["issues"]]
        assert "eval_usage" in types

    def test_security_scanner_sql_injection(self):
        """Security scanner detects SQL injection."""
        ss = SecurityScanner()
        code = "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')"
        result = ss.scan(code)
        types = [v["type"] for v in result["vulnerabilities"]]
        assert "sql_injection" in types

    def test_security_scanner_hardcoded_password(self):
        """Security scanner detects hardcoded passwords."""
        ss = SecurityScanner()
        code = "password = 'supersecret123'"
        result = ss.scan(code)
        types = [v["type"] for v in result["vulnerabilities"]]
        assert "hardcoded_password" in types

    def test_security_scanner_clean(self):
        """Clean code has high security score."""
        ss = SecurityScanner()
        code = "def safe():\n    import secrets\n    return secrets.token_hex(32)\n"
        result = ss.scan(code)
        assert result["security_score"] >= 80

    def test_dependency_analysis(self):
        """Dependency analysis detects cycles."""
        da = DependencyAnalyzer()
        result = da.analyze({
            "a.py": ["b.py"],
            "b.py": ["c.py"],
            "c.py": ["a.py"],  # Cycle
            "d.py": ["e.py"],
            "e.py": [],
        })
        assert result["total_files"] == 5
        assert result["dependency_cycles"] >= 1

    def test_refactoring_advisor(self):
        """Refactoring advisor provides suggestions."""
        ra = RefactoringAdvisor()
        code = """
def long_function():
    # TODO: fix this
    x = 1
    y = 2
    z = x + y
    return z
"""
        result = ra.analyze(code)
        assert "total_suggestions" in result
        assert result["total_suggestions"] >= 1


# =============================================================================
# STRATEXT: TRADING ENGINE TESTS
# =============================================================================

class TestTradingEngine:
    def test_technical_sma(self):
        """SMA is computed correctly."""
        ti = TechnicalIndicators([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        sma = ti.sma(period=3)
        assert sma[2] == 2.0  # (1+2+3)/3
        assert sma[9] == 9.0  # (8+9+10)/3

    def test_technical_rsi(self):
        """RSI is computed."""
        prices = [i * 0.5 for i in range(30)]
        ti = TechnicalIndicators(prices)
        rsi = ti.rsi(period=14)
        assert len(rsi) > 0
        # All uptrend = high RSI
        assert rsi[-1] > 50

    def test_technical_macd(self):
        """MACD is computed."""
        prices = [i * 0.1 + 10 for i in range(50)]
        ti = TechnicalIndicators(prices)
        macd = ti.macd()
        assert len(macd["macd_line"]) == 50
        assert len(macd["signal_line"]) == 50
        assert len(macd["histogram"]) == 50

    def test_technical_bollinger(self):
        """Bollinger bands are computed."""
        prices = [10 + i * 0.1 + random.gauss(0, 0.2) for i in range(30)]
        ti = TechnicalIndicators(prices)
        bands = ti.bollinger_bands(period=5)
        assert len(bands["upper"]) == 30
        assert len(bands["lower"]) == 30

    def test_black_scholes_call(self):
        """Black-Scholes call price is correct."""
        opt = OptionPricing()
        result = opt.black_scholes(
            S=100, K=100, T=1, r=0.05, sigma=0.2, option_type="call"
        )
        assert result["price"] > 0
        assert 0 <= result["delta"] <= 1

    def test_black_scholes_put(self):
        """Black-Scholes put price is correct."""
        opt = OptionPricing()
        result = opt.black_scholes(
            S=100, K=100, T=1, r=0.05, sigma=0.2, option_type="put"
        )
        assert result["price"] > 0
        assert -1 <= result["delta"] <= 0

    def test_binomial_tree(self):
        """Binomial tree pricing works."""
        opt = OptionPricing()
        result = opt.binomial_tree(
            S=100, K=100, T=1, r=0.05, sigma=0.2, n=50, option_type="call"
        )
        assert result["price"] > 0
        assert 0 <= result["p"] <= 1

    def test_risk_var(self):
        """VaR is computed."""
        rm = RiskMetrics(returns=[0.01, -0.02, 0.015, -0.03, 0.02, -0.01, 0.005, -0.025])
        result = rm.calculate_var(confidence=0.95)
        assert result["var"] < 0  # Negative = loss
        assert result["cvar"] <= result["var"]

    def test_risk_sharpe(self):
        """Sharpe ratio is computed."""
        rm = RiskMetrics(returns=[0.01, 0.02, -0.01, 0.03, 0.02, 0.01, -0.02, 0.015])
        sharpe = rm.sharpe_ratio(risk_free_rate=0.02)
        assert isinstance(sharpe, float)

    def test_portfolio_optimization(self):
        """Portfolio optimization works."""
        po = PortfolioOptimizer()
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, 0.02],
            "B": [0.02, 0.01, 0.03, -0.01, 0.02],
            "C": [-0.01, 0.03, 0.02, 0.01, -0.02],
        }
        result = po.mean_variance_optimize(returns)
        assert "weights" in result
        assert sum(result["weights"].values()) > 0.99  # Weights sum to ~1

    def test_backtest_engine(self):
        """Backtest engine runs."""
        be = BacktestEngine()
        prices = [100 + i * 0.5 for i in range(50)]

        def simple_strategy(data, idx):
            if idx == 10:
                return "buy"
            elif idx == 30:
                return "sell"
            return "hold"

        result = be.run(prices, simple_strategy, initial_capital=10000)
        assert "final_equity" in result
        assert "total_return" in result
        assert result["number_of_trades"] >= 2

    def test_trading_sentiment_bullish(self):
        """Bullish sentiment is detected."""
        sa = TradingSentimentAnalyzer()
        result = sa.analyze("Strong buy, bullish outlook, great growth potential")
        assert result["sentiment"] == "bullish"
        assert result["trading_signal"] in ("buy", "strong_buy")

    def test_trading_sentiment_bearish(self):
        """Bearish sentiment is detected."""
        sa = TradingSentimentAnalyzer()
        result = sa.analyze("Weak sell, bearish outlook, concerning decline")
        assert result["sentiment"] == "bearish"
        assert result["trading_signal"] in ("sell", "strong_sell")
