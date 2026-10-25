"""
Real Deep Layer 3i Tests — Real Functional Testing

Tests for real advanced engines:
- Stratex: real_crypto_advanced3.py (BlackScholes, BinomialModel, GridTradingBot, MartingaleStrategy, DCAStrategy, PortfolioRebalancer, MarginAnalyzer, FundingRateArbitrage, PerpetualFutures, VolatilitySurface, DeltaHedging, LiquidationEngine, OptionsChainAnalyzer)
- VyralX: real_speech_advanced2.py (AttentionBasedRecognizer, KeywordSpotter, LanguageIdentifier, DialectRecognizer, MultiClassEmotionRecognizer, SpeakerVerifier, IVectorExtractor, EnergyVAD, SpectralVAD, CELPCodec, BandwidthExtension, SpeechSuperResolution)
- Cortex: real_decision_advanced2.py (SocialNetworkAnalyzer, InformationCascades, HerdingBehavior, DiffusionModel, NetworkEffects, CollectiveAction, TeamDecisionMaker, RiskCommunicator, MechanismDesigner2, BehavioralGames)
- IntelX: real_intel_advanced2.py (WatchlistManager, PredictivePolicing, ThreatForecaster, IntelligenceCycleOptimizer, KnowledgeManager, CounterProliferation, CounterTerrorism, CyberThreatIntel, OSINTDeepAnalysis, HUMINTDeepAnalysis, IMINTDeepAnalysis, SIGINTDeepAnalysis, MASINTAnalyzer)
- Memora: real_memory_advanced2.py (SynapticPlasticity, SleepConsolidation, MemoryAllocation, InterferenceBasedForgetting, MotivatedForgetting, RetrievalInducedForgetting, StateDependentMemory, FlashbulbMemory, AutobiographicalMemory, ProspectiveMemory, ExpertiseMemory, MemoryStrategyTrainer, MemoryRehabilitation)
"""

import pytest
import sys
import os
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCryptoAdvanced3:
    """Test Stratex real_crypto_advanced3.py."""

    def test_black_scholes_call(self):
        from Stratex.app.agents.real_crypto_advanced3 import BlackScholes

        price = BlackScholes.call_price(100, 100, 1, 0.05, 0.2)
        assert price > 0

    def test_black_scholes_put(self):
        from Stratex.app.agents.real_crypto_advanced3 import BlackScholes

        price = BlackScholes.put_price(100, 100, 1, 0.05, 0.2)
        assert price > 0

    def test_black_scholes_greeks(self):
        from Stratex.app.agents.real_crypto_advanced3 import BlackScholes

        delta = BlackScholes.delta(100, 100, 1, 0.05, 0.2, "call")
        assert 0 < delta < 1

        gamma = BlackScholes.gamma(100, 100, 1, 0.05, 0.2)
        assert gamma > 0

        theta = BlackScholes.theta(100, 100, 1, 0.05, 0.2, "call")
        assert theta < 0

        vega = BlackScholes.vega(100, 100, 1, 0.05, 0.2)
        assert vega > 0

    def test_implied_volatility(self):
        from Stratex.app.agents.real_crypto_advanced3 import BlackScholes

        # First compute price with known vol
        true_vol = 0.25
        price = BlackScholes.call_price(100, 100, 1, 0.05, true_vol)

        # Then calculate implied vol from price
        implied = BlackScholes.implied_volatility(price, 100, 100, 1, 0.05, "call")
        assert abs(implied - true_vol) < 0.05

    def test_binomial_model(self):
        from Stratex.app.agents.real_crypto_advanced3 import BinomialModel

        price = BinomialModel.price(100, 100, 1, 0.05, 0.2, n_steps=50, option_type="call")
        assert price > 0

        am_put = BinomialModel.american_put(100, 100, 1, 0.05, 0.2, n_steps=50)
        assert am_put > 0

    def test_grid_trading(self):
        from Stratex.app.agents.real_crypto_advanced3 import GridTradingBot

        bot = GridTradingBot(lower_bound=100, upper_bound=200, grid_levels=10)
        grid = bot.generate_grid()
        assert len(grid) == 11

        prices = [100 + i * 5 for i in range(20)]
        profit = bot.calculate_profit(prices)
        assert profit >= 0

    def test_martingale(self):
        from Stratex.app.agents.real_crypto_advanced3 import MartingaleStrategy

        strategy = MartingaleStrategy(initial_bet=100, multiplier=2, max_bets=3)
        sequence = strategy.bet_sequence()
        assert sequence == [100, 200, 400]

        total = strategy.calculate_total_loss()
        assert total == 700

        result = strategy.simulate(win_probability=0.5, n_rounds=20)
        assert "balance" in result

    def test_dca_strategy(self):
        from Stratex.app.agents.real_crypto_advanced3 import DCAStrategy

        strategy = DCAStrategy(total_investment=10000, n_investments=10)
        schedule = strategy.generate_schedule()
        assert len(schedule) == 10
        assert sum(schedule) == 10000

        prices = [100 + i for i in range(15)]
        result = strategy.simulate(prices)
        assert result["total_cost"] == 10000

    def test_portfolio_rebalancer(self):
        from Stratex.app.agents.real_crypto_advanced3 import PortfolioRebalancer

        rebalancer = PortfolioRebalancer(target_weights={"A": 0.5, "B": 0.5})
        drift = rebalancer.calculate_drift({"A": 0.6, "B": 0.4})
        assert abs(drift["A"] - 0.1) < 0.01

        assert rebalancer.needs_rebalance({"A": 0.6, "B": 0.4})

        trades = rebalancer.generate_trades({"A": 0.6, "B": 0.4}, 10000)
        assert len(trades) > 0

    def test_margin_analysis(self):
        from Stratex.app.agents.real_crypto_advanced3 import MarginAnalyzer

        maint = MarginAnalyzer.maintenance_margin(equity=1000, notional=10000)
        assert maint == 250

        liq = MarginAnalyzer.liquidation_price(entry_price=100, position_size=1, leverage=10, side="long")
        assert liq < 100

        ratio = MarginAnalyzer.margin_ratio(equity=1000, notional=10000)
        assert ratio == 0.1

    def test_funding_arbitrage(self):
        from Stratex.app.agents.real_crypto_advanced3 import FundingRateArbitrage

        cost = FundingRateArbitrage.funding_cost(0.01, 10000)
        assert cost > 0

        profit = FundingRateArbitrage.arbitrage_profit(spot_price=100, futures_price=101, funding_rate=0.01)
        assert isinstance(profit, float)

    def test_perpetual_futures(self):
        from Stratex.app.agents.real_crypto_advanced3 import PerpetualFutures

        mark = PerpetualFutures.mark_price(spot_price=100, index_price=100, basis=0.01)
        assert mark > 100

        premium = PerpetualFutures.premium_index(mark_price=101, index_price=100)
        assert premium > 0

        analysis = PerpetualFutures.basis_trade(spot_price=100, futures_price=102, funding_rate=0.01)
        assert "signal" in analysis

    def test_volatility_surface(self):
        from Stratex.app.agents.real_crypto_advanced3 import VolatilitySurface

        smile = VolatilitySurface.smile_function(strike=100, spot=100, vol=0.2)
        assert smile > 0

        variance = VolatilitySurface.total_variance(implied_vol=0.2, time=1, spot=100, strike=100)
        assert variance > 0

    def test_delta_hedging(self):
        from Stratex.app.agents.real_crypto_advanced3 import DeltaHedging

        hedge = DeltaHedging.delta_hedge_position(option_delta=0.5, option_quantity=10, underlying_price=100)
        assert hedge < 0

        freq = DeltaHedging.rebalance_frequency(gamma=0.01, transaction_cost=0.01, volatility=0.2)
        assert freq > 0

    def test_liquidation(self):
        from Stratex.app.agents.real_crypto_advanced3 import LiquidationEngine

        assert LiquidationEngine.check_liquidation(equity=100, notional=10000, maintenance_margin_rate=0.025)

        filled, avg_price = LiquidationEngine.liquidation_auction(
            liquidation_amount=10,
            order_book=[(100, 5), (99, 5)],
        )
        assert filled > 0

    def test_options_chain(self):
        from Stratex.app.agents.real_crypto_advanced3 import OptionsChainAnalyzer

        profile = OptionsChainAnalyzer.open_interest_profile(
            strikes=[90, 95, 100, 105, 110],
            open_interest=[100, 200, 500, 300, 100],
        )
        assert "max_oi_strike" in profile

        pain = OptionsChainAnalyzer.max_pain(
            strikes=[90, 95, 100, 105, 110],
            call_oi=[100, 200, 500, 300, 100],
            put_oi=[100, 200, 500, 300, 100],
            spot_price=100,
        )
        assert pain >= 0


class TestSpeechAdvanced2:
    """Test VyralX real_speech_advanced2.py."""

    @pytest.fixture
    def signal(self):
        return [math.sin(i * 0.1) for i in range(1600)]

    def test_attention_recognizer(self):
        from VyralX.app.agents.real_speech_advanced2 import AttentionBasedRecognizer

        rec = AttentionBasedRecognizer()
        features = [[random.uniform(-1, 1) for _ in range(13)] for _ in range(10)]
        labels = rec.recognize(features)
        assert isinstance(labels, list)

    def test_keyword_spotter(self):
        from VyralX.app.agents.real_speech_advanced2 import KeywordSpotter

        spotter = KeywordSpotter()
        spotter.add_keyword("yes", [0.5, 0.3, 0.2])
        spotter.add_keyword("no", [0.1, 0.4, 0.5])

        result = spotter.spot([0.5, 0.3, 0.2])
        assert result == "yes"

    def test_language_identifier(self):
        from VyralX.app.agents.real_speech_advanced2 import LanguageIdentifier

        identifier = LanguageIdentifier()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        lang, confidence = identifier.identify(signal)
        assert lang in identifier.language_profiles
        assert 0 <= confidence <= 1

    def test_dialect_recognizer(self):
        from VyralX.app.agents.real_speech_advanced2 import DialectRecognizer

        dialect = DialectRecognizer()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        result, confidence = dialect.recognize(signal)
        assert result in dialect.dialect_profiles
        assert 0 <= confidence <= 1

    def test_multiclass_emotion(self):
        from VyralX.app.agents.real_speech_advanced2 import MultiClassEmotionRecognizer

        emotion = MultiClassEmotionRecognizer()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        result, confidence = emotion.recognize(signal)
        assert result in emotion.emotions
        assert 0 <= confidence <= 1

    def test_speaker_verifier(self):
        from VyralX.app.agents.real_speech_advanced2 import SpeakerVerifier

        verifier = SpeakerVerifier()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]

        assert verifier.enroll("user1", signal)
        is_match, confidence = verifier.verify("user1", signal)
        assert is_match
        assert confidence > 0.5

    def test_ivector_extractor(self):
        from VyralX.app.agents.real_speech_advanced2 import IVectorExtractor

        extractor = IVectorExtractor()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        ivector = extractor.extract(signal)
        assert len(ivector) > 0

    def test_energy_vad(self):
        from VyralX.app.agents.real_speech_advanced2 import EnergyVAD

        vadat = EnergyVAD(threshold=0.001)
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        segments = vadat.get_speech_segments(signal)
        assert isinstance(segments, list)

    def test_spectral_vad(self):
        from VyralX.app.agents.real_speech_advanced2 import SpectralVAD

        vadat = SpectralVAD(spectral_threshold=0.05)
        signal = [math.sin(i * 0.1) * 0.5 for i in range(1600)]
        result = vadat.detect(signal)
        assert isinstance(result, list)

    def test_celp_codec(self):
        from VyralX.app.agents.real_speech_advanced2 import CELPCodec

        codec = CELPCodec()
        signal = [math.sin(i * 0.1) * 0.5 for i in range(512)]

        coded = codec.encode(signal)
        assert "indices" in coded

        decoded = codec.decode(coded)
        assert len(decoded) > 0

    def test_bandwidth_extension(self):
        from VyralX.app.agents.real_speech_advanced2 import BandwidthExtension

        signal = [math.sin(i * 0.1) * 0.5 for i in range(256)]
        extended = BandwidthExtension.extend(signal)
        assert len(extended) == len(signal)

    def test_speech_super_resolution(self):
        from VyralX.app.agents.real_speech_advanced2 import SpeechSuperResolution

        signal = [math.sin(i * 0.1) * 0.5 for i in range(100)]
        upsampled = SpeechSuperResolution.upsample(signal, target_rate=32000, source_rate=16000)
        assert len(upsampled) > len(signal)


class TestDecisionAdvanced2:
    """Test Cortex real_decision_advanced2.py."""

    def test_social_network(self):
        from Cortex.app.agents.real_decision_advanced2 import SocialNetworkAnalyzer

        net = SocialNetworkAnalyzer()
        net.add_edge("A", "B")
        net.add_edge("B", "C")
        net.add_edge("C", "A")

        assert net.degree("A") == 2
        centrality = net.centrality()
        assert "A" in centrality

        communities = net.communities()
        assert len(communities) >= 1

    def test_information_cascade(self):
        from Cortex.app.agents.real_decision_advanced2 import InformationCascades

        cascade = InformationCascades()
        history = [("A", "A"), ("A", "A"), ("B", "B")]
        assert cascade.cascade_formed(history) == False  # Not all same

        action = cascade.should_follow("B", history)
        assert action in ["A", "B"]

    def test_herding_behavior(self):
        from Cortex.app.agents.real_decision_advanced2 import HerdingBehavior

        prob = HerdingBehavior.herding_probability("sell", ["buy", "buy", "buy"])
        assert prob > 0

        choice = HerdingBehavior.rational_herding(private_value=150, observed_choices=[120, 130], price=100)
        assert choice == "buy"

    def test_diffusion_model(self):
        from Cortex.app.agents.real_decision_advanced2 import DiffusionModel

        model = DiffusionModel(population=50, adoption_rate=0.2)
        history = model.simulate(["agent_0", "agent_1"], steps=5)
        assert len(history) == 5
        assert history[-1] >= history[0]

        curve = model.adoption_curve(["agent_0"], steps=10)
        assert len(curve) == 10

    def test_network_effects(self):
        from Cortex.app.agents.real_decision_advanced2 import NetworkEffects

        effect = NetworkEffects.direct_network_effect(user_count=100, value_per_connection=0.1)
        assert effect == 10

        critical = NetworkEffects.critical_mass(adoption_cost=100, network_benefit=0.5)
        assert critical == 200

    def test_collective_action(self):
        from Cortex.app.agents.real_decision_advanced2 import CollectiveAction

        result = CollectiveAction.public_goods_game(contributions=[50, 50, 50, 50], multiplier=2.0)
        assert result["total_contribution"] == 200

        tragedy = CollectiveAction.tragedy_of_commons(fishers=[10, 10, 10], total_fish=100)
        assert "remaining_fish" in tragedy

        equilibria = CollectiveAction.coordination_game(
            strategies=["A", "B"],
            payoffs=[[2, 1], [1, 2]],
        )
        assert len(equilibria) >= 1

    def test_team_decision(self):
        from Cortex.app.agents.real_decision_advanced2 import TeamDecisionMaker

        team = TeamDecisionMaker()
        team.add_member({"id": "M1", "expertise": 0.8})
        team.add_member({"id": "M2", "expertise": 0.6})

        decision = team.weighted_decision({"option_a": 0.7, "option_b": 0.3})
        assert decision in ["option_a", "option_b"]

        consensus = team.consensus_decision({"M1": "A", "M2": "A"})
        assert consensus == "A"

        polarized = team.group_polarization([0.6, 0.7, 0.8])
        assert len(polarized) == 3

    def test_risk_communication(self):
        from Cortex.app.agents.real_decision_advanced2 import RiskCommunicator

        perception = RiskCommunicator.risk_perception(probability=0.1, severity=5)
        assert perception == 0.5

        message = RiskCommunicator.risk_message("flood", 0.1, 5)
        assert "risk" in message.lower()

    def test_quadratic_voting(self):
        from Cortex.app.agents.real_decision_advanced2 import MechanismDesigner2

        result = MechanismDesigner2.quadratic_voting(votes={"voter1": 3, "voter2": 2})
        assert "costs" in result

        funding = MechanismDesigner2.quadratic_funding(
            contributions={"proj1": 100, "proj2": 200},
            match_budget=100,
        )
        assert "proj1" in funding

    def test_behavioral_games(self):
        from Cortex.app.agents.real_decision_advanced2 import BehavioralGames

        result = BehavioralGames.ultimatum_game(proposer_share=0.4, responder_threshold=0.3)
        assert result[0] == True

        trust = BehavioralGames.trust_game(investment=100, multiplier=2.0, reciprocity=0.5)
        assert trust["returned"] > 0

        qre = BehavioralGames.quantal_response_equilibrium(payoffs=[2, 1, 0])
        assert len(qre) == 3


class TestIntelAdvanced2:
    """Test IntelX real_intel_advanced2.py."""

    def test_watchlist_manager(self):
        from IntelX.app.agents.real_intel_advanced2 import WatchlistManager

        manager = WatchlistManager()
        manager.create_watchlist("Terrorism", "security")
        assert manager.add_entry("Terrorism", {"id": "E1", "name": "Suspect 1"})

        matches = manager.check_watchlist("E1")
        assert "Terrorism" in matches

        stats = manager.watchlist_stats()
        assert stats["total_entries"] == 1

    def test_predictive_policing(self):
        from IntelX.app.agents.real_intel_advanced2 import PredictivePolicing

        hotspots = PredictivePolicing.hotspot_prediction({(1, 1): 5, (2, 2): 3})
        assert (1, 1) in hotspots

        risk = PredictivePolicing.risk_score({"prior_arrests": 2, "gang_affiliation": 1})
        assert 0 <= risk <= 1

        allocations = PredictivePolicing.resource_allocation([(0.8, (1, 1)), (0.5, (2, 2))], 10)
        assert len(allocations) == 2

    def test_threat_forecaster(self):
        from IntelX.app.agents.real_intel_advanced2 import ThreatForecaster

        forecaster = ThreatForecaster()
        forecaster.add_indicator({"weight": 0.7, "type": "terrorism"})
        forecaster.add_indicator({"weight": 0.8, "type": "cyber"})

        result = forecaster.forecast(time_horizon=7)
        assert result["indicators_count"] == 2

    def test_intelligence_cycle(self):
        from IntelX.app.agents.real_intel_advanced2 import IntelligenceCycleOptimizer

        optimizer = IntelligenceCycleOptimizer()
        optimizer.record_cycle_time("planning", 2.0)
        optimizer.record_cycle_time("collection", 5.0)
        optimizer.record_cycle_time("analysis", 3.0)

        assert optimizer.cycle_efficiency() > 0
        bottleneck = optimizer.bottleneck_analysis()
        assert bottleneck == "collection"

    def test_knowledge_manager(self):
        from IntelX.app.agents.real_intel_advanced2 import KnowledgeManager

        manager = KnowledgeManager()
        id1 = manager.add_knowledge({"content": "Enemy troop movement", "category": "military"})
        id2 = manager.add_knowledge({"content": "Economic sanctions", "category": "economic"})

        results = manager.search("troop", category="military")
        assert len(results) >= 1

        coverage = manager.knowledge_coverage()
        assert coverage["military"] == 1

    def test_counter_proliferation(self):
        from IntelX.app.agents.real_intel_advanced2 import CounterProliferation

        risk = CounterProliferation.proliferation_risk("nuclear", capability=0.8, intent=0.7, supplier_network=["A", "B", "C"])
        assert risk["risk_level"] in ["high", "critical"]

        supply = CounterProliferation.supply_chain_analysis(
            components=["uranium", "centrifuge"],
            suppliers=["A"],
            restricted=["centrifuge"],
        )
        assert supply["risk_level"] == "high"

    def test_counter_terrorism(self):
        from IntelX.app.agents.real_intel_advanced2 import CounterTerrorism

        assessment = CounterTerrorism.threat_assessment([
            {"weight": 0.8, "type": "attack_planning"},
            {"weight": 0.6, "type": "weapon_acquisition"},
        ])
        assert assessment["threat_grade"] in ["elevated", "high", "critical"]

        radicalization = CounterTerrorism.radicalization_risk({
            "social_isolation": 0.7,
            "online_exposure": 0.8,
        })
        assert 0 <= radicalization <= 1

    def test_cyber_threat(self):
        from IntelX.app.agents.real_intel_advanced2 import CyberThreatIntel

        cyber = CyberThreatIntel()
        cyber.add_indicator({"type": "malware", "severity": 0.8, "tags": ["trojan", "ransomware"]})
        cyber.add_indicator({"type": "phishing", "severity": 0.6, "tags": ["email", "spoof"]})

        assert cyber.threat_level() > 0

        recommendations = cyber.mitigation_recommendation("malware")
        assert len(recommendations) > 0

    def test_osint_deep(self):
        from IntelX.app.agents.real_intel_advanced2 import OSINTDeepAnalysis

        metadata = OSINTDeepAnalysis.metadata_extraction({
            "camera_model": "Canon",
            "timestamp": "2024-01-01",
        })
        assert metadata["camera_model"] == "Canon"

        analysis = OSINTDeepAnalysis.social_network_analysis([
            {"id": "A", "friends": ["B", "C"]},
            {"id": "B", "friends": ["A"]},
        ])
        assert analysis["profiles_count"] == 2

    def test_humint_deep(self):
        from IntelX.app.agents.real_intel_advanced2 import HUMINTDeepAnalysis

        reliability = HUMINTDeepAnalysis.source_reliability(accuracy=0.8, consistency=0.7, access=0.9)
        assert reliability > 0.7

        double_agent = HUMINTDeepAnalysis.double_agent_detection(
            reporting=["A", "B", "C"],
            known_truth=["A", "B", "D"],
            operational_behavior=["suspicious", "normal"],
        )
        assert 0 <= double_agent <= 1

    def test_imint_deep(self):
        from IntelX.app.agents.real_intel_advanced2 import IMINTDeepAnalysis

        classification = IMINTDeepAnalysis.object_classification([
            {"has_wheels": True, "has_weapons": True},
        ])
        assert classification == "military_vehicle"

        change = IMINTDeepAnalysis.change_detection_analysis([100, 100, 100], [100, 200, 100])
        assert change["changed"]

    def test_sigint_deep(self):
        from IntelX.app.agents.real_intel_advanced2 import SIGINTDeepAnalysis

        cipher = SIGINTDeepAnalysis.cipher_type_detection("HELLOWORLDHELLOWORLD")
        assert isinstance(cipher, str)

        freq = SIGINTDeepAnalysis.frequency_analysis("HELLO WORLD")
        assert isinstance(freq, dict)

    def test_masint(self):
        from IntelX.app.agents.real_intel_advanced2 import MASINTAnalyzer

        nuclear = MASINTAnalyzer.nuclear_signature([1, 2, 10, 1, 2])
        assert "detected" in nuclear

        chemical = MASINTAnalyzer.chemical_signature([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        assert chemical["match"]


class TestMemoryAdvanced2:
    """Test Memora real_memory_advanced2.py."""

    def test_synaptic_plasticity(self):
        from Memora.core.memory.real_memory_advanced2 import SynapticPlasticity

        syn = SynapticPlasticity()
        weight = syn.long_term_potentiation(calcium_level=0.8)
        assert weight > 0.5

        weight2 = syn.long_term_depression(calcium_level=0.1)
        assert weight2 <= weight

        stdp = syn.spike_timing_dependent_plasticity(pre_spike_time=0, post_spike_time=5)
        assert stdp > 0.5

    def test_sleep_consolidation(self):
        from Memora.core.memory.real_memory_advanced2 import SleepConsolidation

        sleep = SleepConsolidation()
        sleep.add_memory({"content": "meeting"})
        sleep.add_memory({"content": "meeting"})

        score = sleep.slow_wave_sleep_consolidation()
        assert score > 0

        rem_score = sleep.rem_sleep_consolidation()
        assert rem_score >= score

        stats = sleep.consolidation_score()
        assert stats["total"] == 2

    def test_memory_allocation(self):
        from Memora.core.memory.real_memory_advanced2 import MemoryAllocation

        alloc = MemoryAllocation(working_memory_capacity=4)
        assert alloc.allocate_attention(["A", "B"])
        assert alloc.capacity_utilization() > 0

        assert alloc.switch_attention("C", "A")
        assert alloc.cognitive_load_score() > 0

    def test_interference_forgetting(self):
        from Memora.core.memory.real_memory_advanced2 import InterferenceBasedForgetting

        pi = InterferenceBasedForgetting.proactive_interference(
            {"a": 1, "b": 2},
            {"a": 1, "c": 3},
        )
        assert pi > 0

        ri = InterferenceBasedForgetting.retroactive_interference(
            {"a": 1, "c": 3},
            {"a": 1, "b": 2},
        )
        assert ri > 0

    def test_motivated_forgetting(self):
        from Memora.core.memory.real_memory_advanced2 import MotivatedForgetting

        strength = MotivatedForgetting.directed_forgetting({"_strength": 1.0}, True)
        assert strength < 1.0

        suppressed = MotivatedForgetting.thought_suppression(["a", "b"], ["b"])
        assert "b" not in suppressed

    def test_retrieval_induced_forgetting(self):
        from Memora.core.memory.real_memory_advanced2 import RetrievalInducedForgetting

        forgetting = RetrievalInducedForgetting.competition_induced_forgetting(
            practiced={"_strength": 1.0, "a": 1},
            unpracticed={"_strength": 0.8, "a": 1},
        )
        assert forgetting > 0

    def test_state_dependent_memory(self):
        from Memora.core.memory.real_memory_advanced2 import StateDependentMemory

        specificity = StateDependentMemory.encoding_specificity(
            encoding_context={"room": "office", "time": "morning"},
            retrieval_context={"room": "office", "time": "evening"},
        )
        assert specificity == 0.5

        dependency = StateDependentMemory.state_dependency(
            encoding_state={"mood": "happy", "location": "park"},
            retrieval_state={"mood": "happy", "location": "park"},
        )
        assert dependency > 0.6

    def test_flashbulb_memory(self):
        from Memora.core.memory.real_memory_advanced2 import FlashbulbMemory

        intensity = FlashbulbMemory.emotional_intensity(
            event={},
            personal_importance=0.9,
            surprise=0.8,
            concatenated_emotion=0.7,
        )
        assert intensity > 0.7

        vividness = FlashbulbMemory.vividness_score(
            event={},
            rehearsal_count=5,
            emotional_intensity=intensity,
        )
        assert vividness > 0.7

    def test_autobiographical_memory(self):
        from Memora.core.memory.real_memory_advanced2 import AutobiographicalMemory

        auto = AutobiographicalMemory()
        auto.encode_memory({"content": "first day", "life_period": "childhood", "valence": 0.8})
        auto.encode_memory({"content": "college", "life_period": "youth", "valence": 0.5})

        review = auto.life_review("childhood")
        assert review["total_memories"] == 1

        narrative = auto.narrative_identity()
        assert "childhood" in narrative

    def test_prospective_memory(self):
        from Memora.core.memory.real_memory_advanced2 import ProspectiveMemory

        intention = ProspectiveMemory.form_intention("take_medicine", "3pm", {"time": "3pm"})
        assert intention["action"] == "take_medicine"

        triggered = ProspectiveMemory.monitor_environment(intention, {"time": "3pm"})
        assert triggered

        action = ProspectiveMemory.execute_action(intention, triggered)
        assert action == "take_medicine"

    def test_expertise_memory(self):
        from Memora.core.memory.real_memory_advanced2 import ExpertiseMemory

        chunks = ExpertiseMemory.chunk_memory(["A", "B", "C", "D", "E"], chunk_size=2)
        assert len(chunks) == 3

        patterns = ExpertiseMemory.pattern_recognition(
            patterns=[["A", "B"], ["C", "D"]],
            sequence=["A", "B", "C", "D"],
        )
        assert len(patterns) >= 1

    def test_memory_strategy_trainer(self):
        from Memora.core.memory.real_memory_advanced2 import MemoryStrategyTrainer

        mnemonic = MemoryStrategyTrainer.mnemonic_device(["apple", "banana"], ["red fruit", "yellow fruit"])
        assert "apple" in mnemonic

        loci = MemoryStrategyTrainer.method_of_loci(["apple", "banana"], ["door", "window"])
        assert "apple" in loci

        accuracy = MemoryStrategyTrainer.recall_accuracy(["A", "B"], ["A", "B"])
        assert accuracy == 1.0

    def test_memory_rehabilitation(self):
        from Memora.core.memory.real_memory_advanced2 import MemoryRehabilitation

        result = MemoryRehabilitation.spaced_retrieval_training(["A", "B", "C"], [1, 2, 3])
        assert result["items_trained"] == 3

        errorless = MemoryRehabilitation.errorless_learning(["A", "B"], ["A?", "B?"])
        assert errorless["error_count"] == 0

        rehab = MemoryRehabilitation.cognitive_rehabilitation(training_sessions=10, baseline_score=0.3)
        assert rehab["final"] > rehab["baseline"]
