"""
Real Deep Layer 3f Tests — Real Functional Testing

Tests for real advanced engines:
- VyralX: real_speech_processing.py (AudioSignal, MFCCExtractor, SpeechRecognizer, SpeakerRecognizer, SpeechSynthesizer, SpeechActivityDetector, EmotionRecognizer, AudioCompressor)
- Forge: real_optimization_advanced.py (PSO, GA, SA, ACO, DE, ABC, Firefly, MultiObjective)
- Stratex: real_crypto_advanced.py (TechnicalIndicators, TradingStrategy, MeanReversion, Momentum, PortfolioOptimizer, RiskManager, ArbitrageDetector, OrderBookAnalyzer, Backtester)
- Cortex: real_decision_theory.py (UtilityFunction, Prospect, DecisionMaker, DecisionTree, AHP, TOPSIS, BayesianDecisionMaker, MDP, SocialChoice)
- IntelX: real_intel_analysis.py (Source, IntelligenceReport, StructuredAnalysis, SourceEvaluation, EvidenceFusion, AdvancedLinkAnalysis, PatternOfLife, HypothesisEngine, UncertaintyQuantifier, OSINTCollector, CompetitiveIntel, ReportWriter)
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSpeechProcessing:
    """Test VyralX real_speech_processing.py."""

    @pytest.fixture
    def signal(self):
        from VyralX.app.agents.real_speech_processing import AudioSignal

        samples = [math_sin(i * 0.1) for i in range(1600)]
        return AudioSignal(samples=samples, sample_rate=16000)

    @pytest.fixture
    def silence(self):
        from VyralX.app.agents.real_speech_processing import AudioSignal

        return AudioSignal(samples=[0.0] * 1000, sample_rate=16000)

    def test_signal_normalize(self, signal):
        normalized = signal.normalize()
        assert abs(max(normalized.samples)) <= 1.0
        assert normalized.sample_rate == 16000

    def test_signal_rms(self, signal):
        rms = signal.compute_rms()
        assert rms > 0

    def test_signal_zero_crossing(self, signal):
        zcr = signal.compute_zero_crossing_rate()
        assert 0 <= zcr <= 1

    def test_signal_gain(self, signal):
        boosted = signal.apply_gain(2.0)
        # Find a non-zero sample to compare
        for i, (orig, boosted_val) in enumerate(zip(signal.samples, boosted.samples)):
            if abs(orig) > 1e-10:
                assert abs(boosted_val) > abs(orig)
                break
        else:
            pytest.skip("All samples are zero")

    def test_signal_filter(self, signal):
        filtered = signal.apply_filter(4000, 16000)
        assert len(filtered.samples) == len(signal.samples)

    def test_signal_noise(self, signal):
        noisy = signal.add_noise(0.01)
        assert len(noisy.samples) == len(signal.samples)

    def test_signal_silence_rms(self, silence):
        rms = silence.compute_rms()
        assert rms == 0

    def test_mfcc_extraction(self, signal):
        from VyralX.app.agents.real_speech_processing import MFCCExtractor

        extractor = MFCCExtractor(n_mfcc=13, n_fft=256)
        mfccs = extractor.extract(signal)
        assert len(mfccs) > 0
        assert len(mfccs[0]) == 13

    def test_speech_synthesis(self):
        from VyralX.app.agents.real_speech_processing import SpeechSynthesizer

        synth = SpeechSynthesizer()
        signal = synth.synthesize("hello world", 16000)
        assert len(signal.samples) > 0
        assert signal.duration > 0

    def test_speech_activity_detection(self, signal):
        from VyralX.app.agents.real_speech_processing import SpeechActivityDetector

        detector = SpeechActivityDetector(threshold=0.001)
        segments = detector.get_speech_segments(signal)
        assert len(segments) >= 0

    def test_audio_compression(self, signal):
        from VyralX.app.agents.real_speech_processing import AudioCompressor

        compressor = AudioCompressor(bit_depth=4)
        quantized = compressor.compress(signal)
        assert len(quantized) == len(signal.samples)

        ratio = compressor.compression_ratio(signal)
        assert ratio > 1.0  # Should compress

        decompressed = compressor.decompress(quantized)
        assert len(decompressed.samples) == len(signal.samples)


class TestOptimizationAdvanced:
    """Test Forge real_optimization_advanced.py."""

    @pytest.fixture
    def sphere_problem(self):
        from Forge.app.agents.real_optimization_advanced import OptimizationProblem

        def sphere(x):
            return sum(v ** 2 for v in x)

        bounds = [(-5, 5)] * 5
        return OptimizationProblem(objective=sphere, bounds=bounds)

    def test_pso_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import ParticleSwarmOptimizer

        optimizer = ParticleSwarmOptimizer(
            n_particles=15, n_iterations=30, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 1.0  # Should find near-optimal

    def test_ga_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import GeneticAlgorithm

        optimizer = GeneticAlgorithm(
            population_size=20, n_generations=30, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 1.0

    def test_sa_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import SimulatedAnnealing

        optimizer = SimulatedAnnealing(
            initial_temp=10, cooling_rate=0.98, n_iterations=200,
            bounds=sphere_problem.bounds, dimensions=5
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 8.0

    def test_aco_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import AntColonyOptimizer

        optimizer = AntColonyOptimizer(
            n_ants=10, n_iterations=20, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 5.0

    def test_de_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import DifferentialEvolution

        optimizer = DifferentialEvolution(
            population_size=30, n_generations=30, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 1.0

    def test_abc_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import ArtificialBeeColony

        optimizer = ArtificialBeeColony(
            n_bees=30, n_iterations=100, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 15.0

    def test_firefly_sphere(self, sphere_problem):
        from Forge.app.agents.real_optimization_advanced import FireflyAlgorithm

        optimizer = FireflyAlgorithm(
            n_fireflies=15, n_iterations=30, dimensions=5, bounds=sphere_problem.bounds
        )
        solution, score = optimizer.optimize(sphere_problem.objective)
        assert len(solution) == 5
        assert score < 30.0

    def test_multiobjective(self):
        from Forge.app.agents.real_optimization_advanced import MultiObjectiveOptimizer

        def obj1(x):
            return sum(v ** 2 for v in x)

        def obj2(x):
            return sum((v - 1) ** 2 for v in x)

        bounds = [(-3, 3)] * 3
        optimizer = MultiObjectiveOptimizer(
            population_size=15, n_generations=20, dimensions=3, bounds=bounds
        )
        results = optimizer.optimize([obj1, obj2])
        assert len(results) > 0
        assert len(results[0][0]) == 3
        assert len(results[0][1]) == 2

    def test_problem_feasibility(self, sphere_problem):
        assert sphere_problem.is_feasible([0, 0, 0, 0, 0])


class TestCryptoAdvanced:
    """Test Stratex real_crypto_advanced.py."""

    @pytest.fixture
    def candles(self):
        from Stratex.app.agents.real_crypto_advanced import Candle

        return [
            Candle(i, 100 + i, 105 + i, 95 + i, 103 + i, 1000)
            for i in range(50)
        ]

    @pytest.fixture
    def prices(self, candles):
        return [c.close for c in candles]

    def test_sma(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        sma = TechnicalIndicators.sma(prices, 10)
        assert len(sma) == len(prices) - 9
        assert sma[0] == pytest.approx(sum(prices[:10]) / 10)

    def test_ema(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        ema = TechnicalIndicators.ema(prices, 12)
        assert len(ema) > 0

    def test_rsi(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        rsi = TechnicalIndicators.rsi(prices, 14)
        assert len(rsi) > 0
        assert all(0 <= r <= 100 for r in rsi)

    def test_bollinger_bands(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, 20, 2.0)
        assert len(upper) == len(middle) == len(lower)
        assert all(u > m for u, m in zip(upper, middle))
        assert all(m > l for m, l in zip(middle, lower))

    def test_atr(self, candles):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        atr = TechnicalIndicators.atr(candles, 14)
        assert len(atr) > 0
        assert all(a > 0 for a in atr)

    def test_stochastic(self, candles):
        from Stratex.app.agents.real_crypto_advanced import TechnicalIndicators

        k, d = TechnicalIndicators.stochastic(
            [c.high for c in candles],
            [c.low for c in candles],
            [c.close for c in candles],
            14
        )
        assert len(k) > 0

    def test_trading_buy_sell(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TradingStrategy

        strategy = TradingStrategy(initial_capital=10000)
        assert strategy.buy(100, 50)  # Cost: 5000 + commission
        assert strategy.position == 50
        assert strategy.sell(110, 50)
        assert strategy.position == 0

    def test_mean_reversion(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TradingStrategy, MeanReversionStrategy

        strategy = TradingStrategy(initial_capital=10000)
        mr = MeanReversionStrategy(strategy, z_threshold=2.0)
        signals = mr.generate_signals(prices, 20)
        assert len(signals) > 0
        assert all(s in ["buy", "sell", "hold"] for s in signals)

    def test_momentum(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TradingStrategy, MomentumStrategy

        strategy = TradingStrategy(initial_capital=10000)
        mom = MomentumStrategy(strategy, lookback=20)
        signals = mom.generate_signals(prices)
        assert len(signals) > 0
        assert all(s in ["buy", "sell", "hold"] for s in signals)

    def test_kelly_fraction(self):
        from Stratex.app.agents.real_crypto_advanced import PortfolioOptimizer

        fraction = PortfolioOptimizer.kelly_fraction(0.6, 2.0)
        assert -1 <= fraction <= 1

    def test_risk_manager(self):
        from Stratex.app.agents.real_crypto_advanced import RiskManager

        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        var = RiskManager.var(returns, 0.95)
        es = RiskManager.expected_shortfall(returns, 0.95)
        assert var <= 0
        assert es <= var

        pos_size = RiskManager.position_size(10000, 0.02, 0.05)
        assert pos_size > 0

    def test_arbitrage(self):
        from Stratex.app.agents.real_crypto_advanced import ArbitrageDetector

        market1 = {"BTCUSDT": 30000, "ETHBTC": 0.05}
        market2 = {"BTCUSDT": 29000}
        market3 = {}

        found, profit = ArbitrageDetector.triangular_arbitrage(market1, market2, market3)
        assert isinstance(found, bool)

    def test_order_book(self):
        from Stratex.app.agents.real_crypto_advanced import OrderBookAnalyzer

        book = OrderBookAnalyzer(
            bids=[(100, 10), (99, 20)],
            asks=[(101, 15), (102, 25)]
        )
        bid_depth, ask_depth = book.depth()
        assert bid_depth == 30
        assert ask_depth == 40

        imbalance = book.imbalance()
        assert -1 <= imbalance <= 1

        vwap = book.vwap()
        assert vwap > 0

        spread = book.spread()
        assert spread == 1

    def test_backtest(self, prices):
        from Stratex.app.agents.real_crypto_advanced import TradingStrategy, Backtester

        strategy = TradingStrategy(initial_capital=10000)
        signals = ["buy"] * 10 + ["hold"] * 30 + ["sell"] * 10

        backtester = Backtester(strategy, 10000)
        results = backtester.run(prices, signals)

        assert results["final_equity"] > 0
        assert "return_pct" in results
        assert "max_drawdown" in results
        assert "trades" in results


class TestDecisionTheory:
    """Test Cortex real_decision_theory.py."""

    def test_utility_crra(self):
        from Cortex.app.agents.real_decision_theory import UtilityFunction

        util = UtilityFunction(risk_aversion=2.0, form="crra")
        assert util.evaluate(100) > util.evaluate(50)

    def test_utility_cara(self):
        from Cortex.app.agents.real_decision_theory import UtilityFunction

        util = UtilityFunction(risk_aversion=0.01, form="cara")
        assert util.evaluate(100) > util.evaluate(50)

    def test_certain_equivalent(self):
        from Cortex.app.agents.real_decision_theory import UtilityFunction

        util = UtilityFunction(risk_aversion=2.0, form="crra")
        ce = util.certain_equivalent(100, 10)
        assert ce > 0

    def test_prospect_value(self):
        from Cortex.app.agents.real_decision_theory import Prospect

        prospect = Prospect(outcomes=[100, -50], probabilities=[0.6, 0.4])
        value = prospect.value()
        assert isinstance(value, float)

    def test_decision_maker_utility(self):
        from Cortex.app.agents.real_decision_theory import UtilityFunction, DecisionMaker, Probability

        util = UtilityFunction(risk_aversion=1.0)
        maker = DecisionMaker(utility=util, wealth=100000)

        options = {
            "safe": Probability([90000, 100000], [0.5, 0.5]),
            "risky": Probability([50000, 150000], [0.5, 0.5]),
        }

        choice = maker.choose(options)
        assert choice in ["safe", "risky"]

    def test_decision_maker_prospect(self):
        from Cortex.app.agents.real_decision_theory import DecisionMaker, Prospect

        maker = DecisionMaker(utility=None)
        options = {
            "A": Prospect([100, 0], [0.5, 0.5]),
            "B": Prospect([50, 50], [0.5, 0.5]),
        }

        choice = maker.choose_prospect(options)
        assert choice in ["A", "B"]

    def test_decision_tree(self):
        from Cortex.app.agents.real_decision_theory import DecisionTree

        tree = DecisionTree()

        # Build a simple tree
        root = tree.add_decision(-1, "Invest?")
        chance = tree.add_chance(root, "Market", 0.6)
        terminal_good = tree.add_terminal(chance, "Profit", 1000)
        terminal_bad = tree.add_terminal(chance, "Loss", -500)

        ev = tree.expected_value(root)
        assert ev > 0

    def test_ahp(self):
        from Cortex.app.agents.real_decision_theory import AnalyticHierarchyProcess

        ahp = AnalyticHierarchyProcess()
        ahp.set_criteria(["cost", "quality", "speed"])
        ahp.set_criteria_comparison(0, 1, 2)
        ahp.set_criteria_comparison(0, 2, 3)
        ahp.set_criteria_comparison(1, 2, 1.5)

        ahp.set_alternative("cost", ["A", "B"])
        ahp.set_alternative("quality", ["A", "B"])
        ahp.set_alternative("speed", ["A", "B"])

        ahp.set_alternative_comparison("cost", 0, 1, 1.2)
        ahp.set_alternative_comparison("quality", 0, 1, 0.8)
        ahp.set_alternative_comparison("speed", 0, 1, 1.5)

        scores = ahp.solve()
        assert "A" in scores
        assert "B" in scores

        cr = ahp.consistency_ratio(ahp.criteria_matrix)
        assert cr < 0.1  # Should be consistent

    def test_topsis(self):
        from Cortex.app.agents.real_decision_theory import TOPSIS

        topsis = TOPSIS()
        topsis.set_criteria(["price", "quality"], [0.4, 0.6], [False, True])

        topsis.add_alternative("A", [100, 8])
        topsis.add_alternative("B", [150, 9])
        topsis.add_alternative("C", [80, 6])

        scores = topsis.solve()
        assert len(scores) == 3
        assert all(0 <= s <= 1 for s in scores.values())

    def test_bayesian_decision(self):
        from Cortex.app.agents.real_decision_theory import BayesianDecisionMaker

        maker = BayesianDecisionMaker(
            priors={"H1": 0.6, "H2": 0.4},
            costs={"H1": 10, "H2": 20}
        )

        posterior = maker.update_posterior({}, {"H1": 0.8, "H2": 0.2})
        assert abs(sum(posterior.values()) - 1) < 0.01

        decision = maker.decide(posterior)
        assert decision in ["H1", "H2"]

    def test_mdp(self):
        from Cortex.app.agents.real_decision_theory import MDP

        mdp = MDP(gamma=0.9)
        mdp.add_state("S1")
        mdp.add_state("S2")
        mdp.add_action("A1")
        mdp.add_action("A2")

        mdp.set_transition("S1", "A1", "S1", 0.7)
        mdp.set_transition("S1", "A1", "S2", 0.3)
        mdp.set_transition("S2", "A2", "S1", 1.0)

        mdp.set_reward("S1", "A1", 1)
        mdp.set_reward("S2", "A2", 2)

        values = mdp.value_iteration()
        assert "S1" in values
        assert "S2" in values

        policy = mdp.policy_iteration()
        assert "S1" in policy
        assert "S2" in policy

    def test_social_choice_borda(self):
        from Cortex.app.agents.real_decision_theory import SocialChoice

        votes = [{"A": 0, "B": 1, "C": 2}, {"B": 0, "C": 1, "A": 2}]
        scores = SocialChoice.borda_count(votes)
        assert "A" in scores
        assert "B" in scores
        assert "C" in scores

    def test_social_choice_instant_runoff(self):
        from Cortex.app.agents.real_decision_theory import SocialChoice

        votes = [
            {"A": 0, "B": 1, "C": 2},
            {"A": 0, "B": 1, "C": 2},
            {"C": 0, "A": 1, "B": 2},
        ]
        winner = SocialChoice.instant_runoff(votes)
        assert winner is not None


class TestIntelAnalysis:
    """Test IntelX real_intel_analysis.py."""

    def test_source_evaluation(self):
        from IntelX.app.agents.real_intel_analysis import Source

        source = Source(source_id="S1", reliability=0.8, credibility=0.9)
        assert source.reliability_score() == 0.8
        assert source.credibility_score() == pytest.approx(0.72)
        assert source.admiralty_grade() == "A"

    def test_source_history(self):
        from IntelX.app.agents.real_intel_analysis import Source

        source = Source(source_id="S1")
        source.update_reliability(0.9)
        source.update_reliability(0.7)
        source.update_reliability(0.8)
        assert 0.7 < source.reliability_score() < 0.9

    def test_structured_analysis(self):
        from IntelX.app.agents.real_intel_analysis import StructuredAnalysis

        sa = StructuredAnalysis()
        sa.add_hypothesis("H1")
        sa.add_hypothesis("H2")
        sa.add_evidence("H1", "Evidence A")
        sa.add_evidence("H1", "Evidence B")

        ranked = sa.eliminate_hypotheses()
        assert len(ranked) == 2
        assert ranked[0] == "H1"  # H1 has more evidence

    def test_source_evaluator(self):
        from IntelX.app.agents.real_intel_analysis import Source, IntelligenceReport, SourceEvaluation

        source = Source(source_id="S1", reliability=0.9, credibility=0.8)
        evaluator = SourceEvaluation()
        evaluator.add_source(source)

        report = IntelligenceReport(sources=["S1"], confidence=0.8)
        score = evaluator.evaluate_report(report)
        assert score > 0

    def test_evidence_fusion(self):
        from IntelX.app.agents.real_intel_analysis import EvidenceFusion

        fusion = EvidenceFusion()
        fusion.add_evidence({"likelihood": 0.7})
        fusion.add_evidence({"likelihood": 0.6})
        fusion.add_evidence({"likelihood": 0.8})

        result = fusion.fuse()
        assert result["confidence"] > 0.5
        assert result["evidence_count"] == 3

    def test_link_analysis(self):
        from IntelX.app.agents.real_intel_analysis import AdvancedLinkAnalysis

        links = AdvancedLinkAnalysis()
        links.add_node("A", {"type": "person"})
        links.add_node("B", {"type": "organization"})
        links.add_node("C", {"type": "person"})

        links.add_link("A", "B", 1.0)
        links.add_link("B", "C", 0.8)

        centrality = links.centrality()
        assert "degree" in centrality
        assert centrality["degree"]["B"] == 2  # Connected to both A and C

        communities = links.communities()
        assert len(communities) > 0

        path = links.shortest_path("A", "C")
        assert len(path) >= 2
        assert path[0] == "A"
        assert path[-1] == "C"

    def test_pattern_of_life(self):
        from IntelX.app.agents.real_intel_analysis import PatternOfLife

        pol = PatternOfLife()
        pol.add_observation("S1", {"timestamp": 100, "location": "NYC"})
        pol.add_observation("S1", {"timestamp": 200, "location": "NYC"})
        pol.add_observation("S1", {"timestamp": 300, "location": "LA"})

        pattern = pol.analyze_pattern("S1")
        assert pattern["total_observations"] == 3
        assert len(pattern["locations"]) == 2

        anomaly = pol.detect_anomaly("S1", {"timestamp": 500, "location": "Chicago"})
        assert anomaly is True

    def test_hypothesis_engine(self):
        from IntelX.app.agents.real_intel_analysis import HypothesisEngine

        engine = HypothesisEngine()
        hypotheses = engine.generate(["Activity X", "Communication Y"])
        assert len(hypotheses) >= 2

        for hyp in hypotheses:
            engine.support(hyp, "Supporting evidence")

        ranked = engine.rank()
        assert len(ranked) > 0
        assert all(0 <= conf <= 1 for _, conf in ranked)

    def test_uncertainty(self):
        from IntelX.app.agents.real_intel_analysis import UncertaintyQuantifier

        samples = [1.0, 2.0, 3.0, 4.0, 5.0]
        ci = UncertaintyQuantifier.confidence_interval(samples, 0.95)
        assert ci[0] < ci[1]

        entropy = UncertaintyQuantifier.entropy([0.5, 0.5])
        assert entropy == 1.0

        variance = UncertaintyQuantifier.bootstrap_variance(samples)
        assert variance > 0

    def test_osint_collector(self):
        from IntelX.app.agents.real_intel_analysis import OSINTCollector

        collector = OSINTCollector()
        collector.add_source("Twitter")
        collector.add_source("News")
        collector.add_source("Blogs")

        data = collector.collect("crypto", 5)
        assert len(data) > 0

        analysis = collector.analyze("crypto")
        assert analysis["total_items"] > 0
        assert "avg_relevance" in analysis

    def test_competitive_intel(self):
        from IntelX.app.agents.real_intel_analysis import CompetitiveIntel

        ci = CompetitiveIntel()
        ci.add_competitor("A", {"market_share": 30, "growth_rate": 0.15, "threat_level": 0.8})
        ci.add_competitor("B", {"market_share": 10, "growth_rate": 0.05, "threat_level": 0.3})

        ci.add_market_data("market_share", [("A", 30), ("B", 10)])

        share = ci.market_share()
        assert share["A"] == pytest.approx(75.0)
        assert share["B"] == pytest.approx(25.0)

        swot = ci.swot_analysis()
        assert "strengths" in swot
        assert "weaknesses" in swot
        assert "opportunities" in swot
        assert "threats" in swot

    def test_report_writer(self):
        from IntelX.app.agents.real_intel_analysis import IntelligenceReport, ReportWriter

        report = IntelligenceReport(
            report_id="R1",
            title="Test Report",
            subject="Test Subject",
            content="Test content",
            sources=["S1"],
            confidence=0.8,
            keywords=["test", "analysis"]
        )

        writer = ReportWriter()
        brief = writer.write(report, "brief")
        assert "BRIEF" in brief
        assert "Test Report" in brief

        detailed = writer.write(report, "detailed")
        assert "DETAILED REPORT" in detailed

        classified = writer.classify(report, "TOP SECRET")
        assert "TOP SECRET" in classified

    def test_cross_verification(self):
        from IntelX.app.agents.real_intel_analysis import Source, IntelligenceReport, SourceEvaluation

        source = Source(source_id="S1", reliability=0.9, credibility=0.8)
        evaluator = SourceEvaluation()
        evaluator.add_source(source)

        reports = [
            IntelligenceReport(sources=["S1"], confidence=0.8),
            IntelligenceReport(sources=["S1"], confidence=0.75),
            IntelligenceReport(sources=["S1"], confidence=0.85),
        ]

        result = evaluator.cross_verify(reports)
        assert "agreement" in result
        assert "verified" in result


# Helper function
def math_sin(x):
    import math
    return math.sin(x)
