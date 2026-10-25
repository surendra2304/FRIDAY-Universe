"""
Real Deep Layer 3h Tests — Real Functional Testing

Tests for real advanced engines:
- Stratex: real_crypto_advanced2.py (OrderBook2, MarketImpactModel, ExecutionOptimizer, AlphaGenerator, PortfolioConstructor2, MonteCarloSimulator, StressTester, DrawdownCalculator, BetaCalculator, OrderFlowAnalyzer, ExecutionStrategy)
- VyralX: real_speech_advanced.py (SpectralSubtraction, WienerFilter, SpeakerDiarizer, CTCRecognizer, ProsodyPredictor, HMMSynthesizer, AcousticModel, EmotionAwareRecognizer, VoiceConverter)
- Cortex: real_decision_advanced.py (CumulativeProspectTheory, CognitiveBiasDetector, HyperbolicDiscounter, ReferenceDependentPreferences, FairnessTheory, NegotiationEngine, MechanismDesigner, AuctionAnalyzer, VotingAnalyzer, SocialWelfare, ContractDesigner, BehavioralAgent)
- IntelX: real_intel_advanced.py (IntelligenceRequirement, CollectionPlanner, AnalyticalWorkflow, ReportStandards, InfoSharingManager, CounterintelligenceAnalyzer, HUMINTTradecraft, SIGINTTradecraft, GeospatialIntel, MultiSourceFusion, IntelligenceLiaison, IntelligenceTraining)
- Memora: real_memory_advanced.py (MemoryTrace, EpisodicMemory, SemanticMemory, ProceduralMemory, WorkingMemory, CueDependentRecall, MemoryDecayModel, FalseMemoryDetector, MemoryReconsolidation, CognitiveMap, SchemaMemory, MemoryMetacognition)
"""

import pytest
import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCryptoAdvanced2:
    """Test Stratex real_crypto_advanced2.py."""

    def test_order_book_matching(self):
        from Stratex.app.agents.real_crypto_advanced2 import OrderBook2

        book = OrderBook2()
        book.add_order("sell", 100, 5)
        book.add_order("sell", 101, 3)

        fills = book.add_order("buy", 101, 4)
        assert len(fills) > 0
        # Remaining asks should be present
        assert len(book.asks) > 0

        # Partial fill
        book2 = OrderBook2()
        book2.add_order("sell", 100, 5)
        fills2 = book2.add_order("buy", 100, 3)
        assert len(fills2) > 0
        assert len(book2.bids) == 0  # Fully matched, no remaining bid

    def test_order_book_spread(self):
        from Stratex.app.agents.real_crypto_advanced2 import OrderBook2

        book = OrderBook2()
        book.add_order("sell", 101, 1)
        book.add_order("buy", 100, 1)

        spread = book.spread()
        assert spread == 1

    def test_order_book_depth(self):
        from Stratex.app.agents.real_crypto_advanced2 import OrderBook2

        book = OrderBook2()
        book.add_order("sell", 101, 5)
        book.add_order("sell", 102, 3)
        book.add_order("buy", 100, 4)
        book.add_order("buy", 99, 2)

        bid_depth, ask_depth = book.depth(2)
        assert bid_depth == 6
        assert ask_depth == 8

    def test_market_impact(self):
        from Stratex.app.agents.real_crypto_advanced2 import MarketImpactModel

        model = MarketImpactModel()
        impact = model.total_impact(1000, 100000, 50000)
        assert impact > 0

        slippage = model.slippage(1000, 10, 50000)
        assert slippage > 0

    def test_vwap_execution(self):
        from Stratex.app.agents.real_crypto_advanced2 import ExecutionOptimizer

        prices = [100, 101, 102, 103, 104]
        volumes = [100, 150, 200, 150, 100]
        plan = ExecutionOptimizer.vwap_execution(prices, volumes, 100, duration=5)

        assert len(plan) > 0
        assert sum(qty for _, _, qty in plan) > 0

    def test_twap_execution(self):
        from Stratex.app.agents.real_crypto_advanced2 import ExecutionOptimizer

        plan = ExecutionOptimizer.twap_execution(100, duration=5, start_price=100)
        assert len(plan) == 5
        assert all(qty > 0 for _, _, qty in plan)

    def test_pov_execution(self):
        from Stratex.app.agents.real_crypto_advanced2 import ExecutionOptimizer

        prices = [100, 101, 102, 103, 104]
        volumes = [100, 150, 200, 150, 100]
        plan = ExecutionOptimizer.pov_execution(prices, volumes, 100, 0.1, 5)

        assert len(plan) > 0

    def test_momentum_alpha(self):
        from Stratex.app.agents.real_crypto_advanced2 import AlphaGenerator

        prices = [100 + i for i in range(30)]
        alphas = AlphaGenerator.momentum_alpha(prices, lookback=10)
        assert len(alphas) > 0

    def test_mean_reversion_alpha(self):
        from Stratex.app.agents.real_crypto_advanced2 import AlphaGenerator

        prices = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106]
        alphas = AlphaGenerator.mean_reversion_alpha(prices, window=5)
        assert len(alphas) > 0

    def test_volatility_alpha(self):
        from Stratex.app.agents.real_crypto_advanced2 import AlphaGenerator

        prices = [100 + random_noise() for _ in range(30)]
        alphas = AlphaGenerator.volatility_alpha(prices, window=10)
        assert len(alphas) > 0

    def test_stat_arb_alpha(self):
        from Stratex.app.agents.real_crypto_advanced2 import AlphaGenerator

        p1 = [100 + i * 0.1 for i in range(20)]
        p2 = [50 + i * 0.05 for i in range(20)]
        alphas = AlphaGenerator.stat_arb_alpha(p1, p2, window=10)
        assert len(alphas) > 0

    def test_min_variance_portfolio(self):
        from Stratex.app.agents.real_crypto_advanced2 import PortfolioConstructor2

        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, 0.02],
            "B": [0.02, -0.01, 0.01, 0.02, -0.02],
            "C": [0.01, 0.01, 0.01, 0.01, 0.01],
        }
        weights = PortfolioConstructor2.min_variance(returns)
        assert "A" in weights
        assert "B" in weights
        assert sum(weights.values()) > 0

    def test_risk_parity_portfolio(self):
        from Stratex.app.agents.real_crypto_advanced2 import PortfolioConstructor2

        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, 0.02],
            "B": [0.02, -0.01, 0.01, 0.02, -0.02],
        }
        weights = PortfolioConstructor2.risk_parity2(returns)
        assert "A" in weights
        assert "B" in weights

    def test_monte_carlo_var(self):
        from Stratex.app.agents.real_crypto_advanced2 import MonteCarloSimulator

        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        var = MonteCarloSimulator.calculate_var(returns, 10000, 0.95, n_paths=500)
        assert var >= 0

    def test_monte_carlo_cvar(self):
        from Stratex.app.agents.real_crypto_advanced2 import MonteCarloSimulator

        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        cvar = MonteCarloSimulator.calculate_cvar(returns, 10000, 0.95, n_paths=500)
        assert cvar >= 0

    def test_stress_test(self):
        from Stratex.app.agents.real_crypto_advanced2 import StressTester

        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = StressTester.monte_carlo_stress(returns, 10000, {"volatility_multiplier": 2.0}, n_paths=100)
        assert "p5" in result
        assert "p95" in result

    def test_drawdown(self):
        from Stratex.app.agents.real_crypto_advanced2 import DrawdownCalculator

        equity = [100, 110, 105, 115, 120, 95, 100]
        dd = DrawdownCalculator.calculate_drawdown(equity)
        assert len(dd) == len(equity)
        assert max(dd) > 0

        max_dd = DrawdownCalculator.max_drawdown(equity)
        assert max_dd > 0

        duration = DrawdownCalculator.drawdown_duration(equity)
        assert duration > 0

    def test_beta_calculation(self):
        from Stratex.app.agents.real_crypto_advanced2 import BetaCalculator

        stock = [0.05, 0.06, 0.07, 0.05, 0.06]
        market = [0.01, 0.015, 0.02, 0.01, 0.015]
        beta = BetaCalculator.calculate_beta(stock, market)
        assert beta > 0

        sharpe = BetaCalculator.calculate_sharpe(stock, risk_free=0.02)
        assert sharpe > 0

        sortino = BetaCalculator.calculate_sortino(stock, risk_free=0.02)
        assert sortino > 0

    def test_order_flow(self):
        from Stratex.app.agents.real_crypto_advanced2 import OrderFlowAnalyzer

        analyzer = OrderFlowAnalyzer()
        for i in range(20):
            analyzer.add_trade(100 + i, 10, "buy" if i % 2 == 0 else "sell", i)

        imbalance = analyzer.imbalance_ratio(10)
        assert -1 <= imbalance <= 1

        profile = analyzer.volume_profile(10)
        assert len(profile) == 10

        intensity = analyzer.trade_intensity(10)
        assert intensity > 0

    def test_execution_strategy(self):
        from Stratex.app.agents.real_crypto_advanced2 import ExecutionStrategy

        strategy = ExecutionStrategy()
        prices = [100, 101, 102, 103, 104]
        volumes = [100, 150, 200, 150, 100]

        result = strategy.execute(prices, volumes, 100, "vwap")
        assert "avg_price" in result
        assert "total_cost" in result


class TestSpeechAdvanced:
    """Test VyralX real_speech_advanced.py."""

    @pytest.fixture
    def signal(self):
        return [math.sin(i * 0.1) for i in range(1600)]

    def test_spectral_subtraction(self, signal):
        from VyralX.app.agents.real_speech_advanced import SpectralSubtraction

        noise_reducer = SpectralSubtraction()
        noise_reducer.estimate_noise(signal, 256)
        enhanced = noise_reducer.subtract(signal, 256)

        assert len(enhanced) > 0

    def test_wiener_filter(self, signal):
        from VyralX.app.agents.real_speech_advanced import WienerFilter

        wiener = WienerFilter()
        enhanced = wiener.apply(signal, 256)
        assert len(enhanced) > 0

    def test_speaker_diarization(self):
        from VyralX.app.agents.real_speech_advanced import SpeakerDiarizer

        diarizer = SpeakerDiarizer()
        embedding1 = diarizer.extract_embedding([100, -50, 30, 50])
        embedding2 = diarizer.extract_embedding([100, -45, 35, 50])
        embedding3 = diarizer.extract_embedding([50, 20, 10, 100])

        segments = [
            (0, 1.0, embedding1),
            (1.0, 2.0, embedding2),
            (2.0, 3.0, embedding3),
        ]

        result = diarizer.cluster(segments)
        assert len(result) == 3

    def test_ctc_recognizer(self):
        from VyralX.app.agents.real_speech_advanced import CTCRecognizer

        recognizer = CTCRecognizer(vocab_size=5)
        emissions = [[0.1, 0.3, 0.6, 0.0, 0.0], [0.1, 0.2, 0.7, 0.0, 0.0]]
        predictions = recognizer.forward_pass(emissions)
        assert len(predictions) > 0

    def test_prosody_prediction(self):
        from VyralX.app.agents.real_speech_advanced import ProsodyPredictor

        prosody = ProsodyPredictor.generate_prosody("Hello World")
        assert "f0" in prosody
        assert "duration" in prosody
        assert "energy" in prosody
        assert len(prosody["f0"]) == len("Hello World")

    def test_hmm_synthesis(self):
        from VyralX.app.agents.real_speech_advanced import HMMSynthesizer

        synth = HMMSynthesizer()
        signal = synth.synthesize("Hello", 16000)
        assert len(signal) > 0

    def test_acoustic_model(self):
        from VyralX.app.agents.real_speech_advanced import AcousticModel

        model = AcousticModel()
        features = [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]]
        labels = ["a", "b"]
        trained = model.train(features, labels)
        assert "a" in trained

        decoded = model.decode(features, trained)
        assert len(decoded) == 2

    def test_emotion_aware_recognition(self):
        from VyralX.app.agents.real_speech_advanced import EmotionAwareRecognizer

        recognizer = EmotionAwareRecognizer()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]

        emotion, confidence = recognizer.detect_emotion(signal)
        assert emotion in recognizer.emotions
        assert 0 <= confidence <= 1

    def test_voice_conversion(self):
        from VyralX.app.agents.real_speech_advanced import VoiceConverter

        converter = VoiceConverter()
        source = [[100, -50, 30] for _ in range(3)]
        target = [[80, -40, 40] for _ in range(3)]

        converter.train(source, target)
        signal = [math.sin(i * 0.1) for i in range(100)]
        converted = converter.convert(signal)
        assert len(converted) == len(signal)


class TestDecisionAdvanced:
    """Test Cortex real_decision_advanced.py."""

    def test_cpt_value_function(self):
        from Cortex.app.agents.real_decision_advanced import CumulativeProspectTheory

        cpt = CumulativeProspectTheory()
        assert cpt.value_function(100) > 0
        assert cpt.value_function(-100) < 0

    def test_cpt_evaluate(self):
        from Cortex.app.agents.real_decision_advanced import CumulativeProspectTheory

        cpt = CumulativeProspectTheory()
        value = cpt.evaluate([100, -50], [0.6, 0.4])
        assert isinstance(value, float)

    def test_anchoring_bias(self):
        from Cortex.app.agents.real_decision_advanced import CognitiveBiasDetector

        bias = CognitiveBiasDetector.anchoring_bias(100, 20, 150)
        assert bias > 0

    def test_confirmation_bias(self):
        from Cortex.app.agents.real_decision_advanced import CognitiveBiasDetector

        evidence = ["climate change is real", "global warming is happening", "earth is warming"]
        bias = CognitiveBiasDetector.confirmation_bias(evidence, "climate")
        assert bias > 0

    def test_sunk_cost_fallacy(self):
        from Cortex.app.agents.real_decision_advanced import CognitiveBiasDetector

        assert CognitiveBiasDetector.sunk_cost_fallacy(invested=1000, expected_return=-100)
        assert not CognitiveBiasDetector.sunk_cost_fallacy(invested=1000, expected_return=2000)

    def test_hyperbolic_discounting(self):
        from Cortex.app.agents.real_decision_advanced import HyperbolicDiscounter

        discounter = HyperbolicDiscounter()
        pv = discounter.present_value(100, 10)
        assert pv > 0

        choice = discounter.compare_choices((100, 1), (150, 10))
        assert choice in ["A", "B"]

    def test_reference_dependent(self):
        from Cortex.app.agents.real_decision_advanced import ReferenceDependentPreferences

        rdp = ReferenceDependentPreferences(reference_point=100)
        assert rdp.utility(120) > 0
        assert rdp.utility(80) < 0
        assert rdp.utility(80) < rdp.utility(120)

    def test_fairness_equity(self):
        from Cortex.app.agents.real_decision_advanced import FairnessTheory

        equity = FairnessTheory.adams_equity(self_input=10, self_outcome=50, other_input=10, other_outcome=100)
        assert equity < 0  # Underpaid

        efficiency = FairnessTheory.allocative_efficiency([1, 0], [10, 20])
        assert 0 <= efficiency <= 1

    def test_nash_bargaining(self):
        from Cortex.app.agents.real_decision_advanced import NegotiationEngine

        engine = NegotiationEngine()
        a, b = engine.nash_bargaining(100, 80, 100)
        assert abs(a + b - 100) < 0.01
        assert a > 0 and b > 0

    def test_vickrey_auction(self):
        from Cortex.app.agents.real_decision_advanced import MechanismDesigner

        winner, price = MechanismDesigner.vickrey_auction([50, 80, 60])
        assert winner == 1
        assert price == 60

    def test_vcg_mechanism(self):
        from Cortex.app.agents.real_decision_advanced import MechanismDesigner

        winner, payment = MechanismDesigner.vcg_mechanism([30, 25, 35], [40, 30, 50])
        assert winner == 2
        assert payment >= 0

    def test_auction_analysis(self):
        from Cortex.app.agents.real_decision_advanced import AuctionAnalyzer

        welfare = AuctionAnalyzer.welfare_analysis([50, 80, 60], [40, 70, 55])
        assert welfare > 0

        revenue = AuctionAnalyzer.revenue_analysis([50, 80, 60], "first_price")
        assert revenue == 80

    def test_bidding_strategy(self):
        from Cortex.app.agents.real_decision_advanced import AuctionAnalyzer

        bid = AuctionAnalyzer.bidding_strategy(100, 5, noise=0.1)
        assert bid < 100

    def test_approval_voting(self):
        from Cortex.app.agents.real_decision_advanced import VotingAnalyzer

        votes = [{"A", "B"}, {"A", "C"}, {"B", "C"}]
        results = VotingAnalyzer.approval_voting(votes)
        assert "A" in results
        assert "B" in results
        assert "C" in results

    def test_social_welfare(self):
        from Cortex.app.agents.real_decision_advanced import SocialWelfare

        utils = [10, 20, 30]
        utilitarian = SocialWelfare.utilitarian(utils)
        assert utilitarian == 60

        egalitarian = SocialWelfare.egalitarian(utils)
        assert egalitarian == 10

    def test_principal_agent(self):
        from Cortex.app.agents.real_decision_advanced import ContractDesigner

        effort, wage = ContractDesigner.principal_agent(
            effort=0.5,
            revenue=lambda e: 10 * e,
            cost=lambda e: 2 * e ** 2,
        )
        assert effort > 0
        assert wage > 0

    def test_behavioral_agent(self):
        from Cortex.app.agents.real_decision_advanced import BehavioralAgent

        agent = BehavioralAgent(wealth=100000)
        choice = agent.choose({
            "safe": (0, 1.0),
            "risky": (1000, 0.5),
        })
        assert choice in ["safe", "risky"]


class TestIntelAdvanced:
    """Test IntelX real_intel_advanced.py."""

    def test_intelligence_requirement(self):
        from IntelX.app.agents.real_intel_advanced import IntelligenceRequirement

        req = IntelligenceRequirement(requirement_id="R1", category="military", question="Enemy troop movement?")
        assert req.is_priority_high() == False

        req.priority = "critical"
        assert req.is_priority_high()

        req.assign_asset("satellite")
        assert "satellite" in req.collection_assets

    def test_collection_planner(self):
        from IntelX.app.agents.real_intel_advanced import CollectionPlanner, IntelligenceRequirement

        planner = CollectionPlanner()
        req = IntelligenceRequirement(requirement_id="R1", category="military")
        planner.add_requirement(req)
        planner.register_asset("SAT1", ["military", "imagery"])

        assignments = planner.assign_assets()
        assert "R1" in assignments

        assert planner.collection_efficiency() == 0.0

    def test_analytical_workflow(self):
        from IntelX.app.agents.real_intel_advanced import AnalyticalWorkflow

        workflow = AnalyticalWorkflow()
        workflow.add_task("T1", "Analyze enemy capabilities")

        assert workflow.advance_stage("T1")
        status = workflow.get_workflow_status()
        assert "collection" in status

    def test_report_standards(self):
        from IntelX.app.agents.real_intel_advanced import ReportStandards

        report = {
            "id": "R1",
            "classification": "TOP SECRET",
            "date": "2024-01-01",
            "source": "S1",
            "key_judgments": ["Enemy is mobilizing"],
            "analysis": "Analysis text",
            "confidence": "High",
        }

        formatted = ReportStandards.format_report(report)
        assert "TOP SECRET" in formatted

        errors = ReportStandards.validate_report(report)
        assert len(errors) == 0

    def test_info_sharing(self):
        from IntelX.app.agents.real_intel_advanced import InfoSharingManager

        manager = InfoSharingManager()
        manager.add_partner("AgencyA")
        manager.add_partner("AgencyB")

        success = manager.share_item({"data": "test"}, ["AgencyA", "AgencyB"])
        assert success

        network = manager.sharing_network()
        assert len(network) > 0

    def test_counterintelligence(self):
        from IntelX.app.agents.real_intel_advanced import CounterintelligenceAnalyzer

        analyzer = CounterintelligenceAnalyzer()
        analyzer.add_suspect({"id": "S1", "access_level": "top_secret", "recent_travel_hostile": True})

        scored = analyzer.prioritize_suspects()
        assert len(scored) > 0
        assert scored[0][1] > 50

    def test_humint_tradecraft(self):
        from IntelX.app.agents.real_intel_advanced import HUMINTTradecraft

        humint = HUMINTTradecraft()
        agent = {"id": "A1", "motivation": "money", "access_level": "secret", "contacts": ["A2"]}
        assert humint.recruit_agent(agent)

        network = humint.agent_network()
        assert "A1" in network

    def test_sigint_tradecraft(self):
        from IntelX.app.agents.real_intel_advanced import SIGINTTradecraft

        sigint = SIGINTTradecraft()
        texts = ["hello world", "this is a test", "another message"]
        analysis = sigint.cryptographic_analysis(texts)

        assert "frequency_distribution" in analysis
        assert "index_of_coincidence" in analysis

    def test_geospatial_intel(self):
        from IntelX.app.agents.real_intel_advanced import GeospatialIntel

        geint = GeospatialIntel()
        before = [{"x": 1, "y": 1}, {"x": 2, "y": 2}]
        after = [{"x": 1, "y": 1}, {"x": 3, "y": 3}]

        changes = geint.change_detection(before, after)
        assert len(changes) > 0

        terrain = geint.terrain_analysis([100, 150, 200, 250, 300])
        assert "terrain_type" in terrain

    def test_multi_source_fusion(self):
        from IntelX.app.agents.real_intel_advanced import MultiSourceFusion

        fusion = MultiSourceFusion()
        fusion.add_source("S1", "HUMINT")
        fusion.add_source("S2", "SIGINT")

        products = [
            {"topic": "threat", "confidence": 0.7, "source_type": "HUMINT", "source": "S1"},
            {"topic": "threat", "confidence": 0.8, "source_type": "SIGINT", "source": "S2"},
        ]

        result = fusion.fuse(products)
        assert result["total_topics"] > 0

    def test_intelligence_training(self):
        from IntelX.app.agents.real_intel_advanced import IntelligenceTraining

        training = IntelligenceTraining()
        training.add_course({"name": "Counterintelligence", "duration": 40, "requirements": ["basic"]})
        training.enroll_trainee({"id": "T1", "skills": ["basic"]})

        training.update_progress("T1", "Counterintelligence", 100)
        assert training.training_completion_rate() > 0


class TestMemoryAdvanced:
    """Test Memora real_memory_advanced.py."""

    def test_memory_trace(self):
        from Memora.core.memory.real_memory_advanced import MemoryTrace

        trace = MemoryTrace(id="T1", content={"color": "red"})
        assert trace.strength == 1.0

        strength = trace.decay(0.1)
        assert strength < 1.0

        trace.reinforce(0.2)
        assert trace.strength > strength

    def test_episodic_memory(self):
        from Memora.core.memory.real_memory_advanced import EpisodicMemory

        memory = EpisodicMemory()
        id1 = memory.encode({"event": "meeting", "location": "office"}, 1.0)
        id2 = memory.encode({"event": "meeting", "location": "conference"}, 2.0)

        recalled = memory.retrieve({"event": "meeting"}, top_k=2)
        assert len(recalled) >= 1

        removed = memory.consolidate(0.5)
        assert isinstance(removed, list)

    def test_semantic_memory(self):
        from Memora.core.memory.real_memory_advanced import SemanticMemory

        memory = SemanticMemory()
        memory.add_concept("dog", {"legs": 4, "barks": True, "pet": True})
        memory.add_concept("cat", {"legs": 4, "meows": True, "pet": True})
        memory.add_relation("dog", "cat", 0.8)

        sim = memory.similarity("dog", "cat")
        assert sim > 0.3

        activation = memory.spreading_activation("dog", steps=2)
        assert "dog" in activation

    def test_procedural_memory(self):
        from Memora.core.memory.real_memory_advanced import ProceduralMemory

        memory = ProceduralMemory()
        memory.learn_procedure("ride_bike", ["mount", "pedal", "steer"])

        executed = memory.execute_procedure("ride_bike")
        assert len(executed) == 3

        mastery = memory.procedure_mastery("ride_bike")
        assert mastery > 0

    def test_working_memory(self):
        from Memora.core.memory.real_memory_advanced import WorkingMemory

        wm = WorkingMemory(max_slots=4)
        assert wm.store("item1")
        assert wm.store("item2")
        assert wm.retrieve(0) == "item1"

        assert wm.manipulate("reverse")
        assert wm.retrieve(0) == "item2"

        wm.clear()
        assert len(wm.slots) == 0

    def test_cue_dependent_recall(self):
        from Memora.core.memory.real_memory_advanced import CueDependentRecall

        recall = CueDependentRecall()
        recall.encode_memory({"word": "apple", "color": "red"}, "fruit")
        recall.encode_memory({"word": "banana", "color": "yellow"}, "fruit")

        result = recall.recall("fruit")
        assert len(result) == 2

    def test_memory_decay(self):
        from Memora.core.memory.real_memory_advanced import MemoryDecayModel

        model = MemoryDecayModel()
        power = model.power_law_decay(10)
        exp = model.exponential_decay(10)

        assert power < 1.0
        assert exp < 1.0

        from Memora.core.memory.real_memory_advanced import MemoryTrace
        old = MemoryTrace(id="O", content={"a": 1})
        new = MemoryTrace(id="N", content={"a": 1})
        pi = model.proactive_interference(old, new)
        ri = model.retroactive_interference(new, old)

        assert pi > 0
        assert ri > 0

    def test_false_memory(self):
        from Memora.core.memory.real_memory_advanced import FalseMemoryDetector

        words = ["bed", "rest", "awake", "tired", "dream", "sleep"]
        critical = "sleep"

        false_mem = FalseMemoryDetector.deese_roediger_karpicke_effect(words, critical)
        assert isinstance(false_mem, bool)

    def test_reconsolidation(self):
        from Memora.core.memory.real_memory_advanced import MemoryReconsolidation

        recon = MemoryReconsolidation()
        recon.memories = [{"id": 0, "value": "original"}]

        assert recon.reconsolidate(0, {"value": "updated"})
        assert recon.memories[0]["value"] == "updated"

        assert recon.update_after_recall(0, {"context": "test"})
        assert recon.memories[0]["_reconsolidated"]

    def test_cognitive_map(self):
        from Memora.core.memory.real_memory_advanced import CognitiveMap

        map_ = CognitiveMap()
        map_.explore("kitchen", (0, 0))
        map_.explore("bedroom", (10, 0))
        map_.add_path("kitchen", "bedroom", 10)

        path = map_.navigate("kitchen", "bedroom")
        assert len(path) >= 2

        dist = map_.distance_estimate("kitchen", "bedroom")
        assert dist == 10

    def test_schema_memory(self):
        from Memora.core.memory.real_memory_advanced import SchemaMemory

        schema = SchemaMemory()
        schema.create_schema("restaurant", ["food", "price", "location"])

        schema.fill_schema("restaurant", {"food": "pizza", "price": 15})
        instance = schema.instantiate_schema("restaurant")

        assert instance["food"] == "pizza"
        assert instance["price"] == 15

    def test_metacognition(self):
        from Memora.core.memory.real_memory_advanced import MemoryMetacognition

        meta = MemoryMetacognition()
        prediction = meta.predict_recall("M1", 0.8)
        assert prediction["predicted_confidence"] == 0.8

        error = meta.calibration_error("M1", True)
        assert abs(abs(error) - 0.2) < 0.01

        joi = meta.judgment_of_learning(study_time=30, difficulty=0.5, prior_recall=True)
        assert 0 <= joi <= 1


# Helper function
def random_noise():
    return random.uniform(-5, 5)
