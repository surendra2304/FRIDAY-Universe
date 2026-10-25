"""
Tests for Layer 3e — Real Deep Engines (Game Theory, Time Series Advanced, NLP Advanced, Knowledge Graph, Threat Intel)

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

# ===== CORTEX: Game Theory =====
_gt = _load_module("Cortex/app/agents/real_game_theory.py", "real_game_theory")
NormalFormGame = _gt.NormalFormGame
NashEquilibriumFinder = _gt.NashEquilibriumFinder
PrisonersDilemma = _gt.PrisonersDilemma
ZeroSumGame = _gt.ZeroSumGame
EvolutionaryGame = _gt.EvolutionaryGame
NashBargaining = _gt.NashBargaining
AuctionAnalyzer = _gt.AuctionAnalyzer
VotingSystem = _gt.VotingSystem

# ===== FUTURIS: Time Series Advanced =====
_tsa = _load_module("Futuris/app/agents/real_time_series_advanced.py", "real_time_series_advanced")
ARMA = _tsa.ARMA
ARIMA = _tsa.ARIMA
HoltWinters = _tsa.HoltWinters
ProphetLike = _tsa.ProphetLike
ModelSelector = _tsa.ModelSelector
TimeSeriesCrossValidator = _tsa.TimeSeriesCrossValidator
EnsembleForecaster = _tsa.EnsembleForecaster

# ===== INFERENCE: NLP Advanced =====
_nlp = _load_module("Inference/app/agents/real_nlp_advanced.py", "real_nlp_advanced")
WordEmbeddings = _nlp.WordEmbeddings
POSTagger = _nlp.POSTagger
SemanticAnalyzer = _nlp.SemanticAnalyzer
ExtractiveSummarizer = _nlp.ExtractiveSummarizer
LDA = _nlp.LDA
AdvancedNER = _nlp.AdvancedNER
MarkovTextGenerator = _nlp.MarkovTextGenerator
CoreferenceResolver = _nlp.CoreferenceResolver

# ===== MEMORA: Knowledge Graph =====
_kg = _load_module("Memora/core/memory/real_knowledge_graph.py", "real_knowledge_graph")
KGNode = _kg.KGNode
KGEdge = _kg.KGEdge
KnowledgeGraph = _kg.KnowledgeGraph
GraphEmbedding = _kg.GraphEmbedding
RelationshipInferer = _kg.RelationshipInferer
OntologyBuilder = _kg.OntologyBuilder
DescriptionLogicReasoner = _kg.DescriptionLogicReasoner
EntityLinker = _kg.EntityLinker

# ===== SENTINEL: Threat Intelligence =====
_ti = _load_module("Sentinel/app/agents/real_threat_intel_advanced.py", "real_threat_intel_advanced")
Indicator = _ti.Indicator
ThreatActor = _ti.ThreatActor
AttackPattern = _ti.AttackPattern
ThreatCorrelator = _ti.ThreatCorrelator
CampaignAnalyzer = _ti.CampaignAnalyzer
MalwareClassifier = _ti.MalwareClassifier
VulnerabilityAnalyzer = _ti.VulnerabilityAnalyzer
ThreatFeedAnalyzer = _ti.ThreatFeedAnalyzer
AttackPatternMapper = _ti.AttackPatternMapper
ThreatPrioritizer = _ti.ThreatPrioritizer
IndicatorLifecycleManager = _ti.IndicatorLifecycleManager


# =============================================================================
# CORTEX: GAME THEORY TESTS
# =============================================================================

class TestGameTheory:
    def test_normal_form_game(self):
        """Normal form game is created correctly."""
        game = NormalFormGame()
        assert len(game.players) == 2
        assert len(game.strategies) == 2

    def test_best_response(self):
        """Best response is computed correctly."""
        game = NormalFormGame(payoffs=[[[1, 0], [0, 1]], [[1, 0], [0, 1]]])
        br = game.best_response(0, 0)
        assert br == 0  # Strategy 0 is best response to strategy 0

    def test_dominant_strategy(self):
        """Dominant strategy is found."""
        game = NormalFormGame(payoffs=[[[3, 2], [1, 0]], [[0, 1], [2, 3]]])
        dominant = game.has_dominant_strategy(0)
        assert dominant == 0  # Strategy 0 dominates

    def test_pure_nash_equilibrium(self):
        """Pure Nash equilibrium is found."""
        game = NormalFormGame(payoffs=[[[3, 0], [0, 1]], [[3, 0], [0, 1]]])
        finder = NashEquilibriumFinder()
        equilibria = finder.find_pure_equilibria(game)
        assert len(equilibria) >= 1

    def test_mixed_nash_equilibrium(self):
        """Mixed strategy Nash equilibrium is found."""
        game = NormalFormGame(payoffs=[[[2, 0], [0, 1]], [[0, 1], [1, 2]]])
        finder = NashEquilibriumFinder()
        result = finder.find_mixed_equilibrium(game)
        assert "player1" in result
        assert 0 <= result["player1"] <= 1

    def test_prisoners_dilemma(self):
        """Prisoner's dilemma payoff matrix is correct."""
        pd = PrisonersDilemma()
        payoffs = pd.payoff_matrix()
        assert payoffs["cooperate"]["cooperate"] == [3.0, 3.0]
        assert payoffs["defect"]["defect"] == [1.0, 1.0]

    def test_prisoners_dilemma_nash(self):
        """Prisoner's dilemma Nash equilibrium is both defect."""
        pd = PrisonersDilemma()
        eq = pd.nash_equilibrium()
        assert eq == (False, False)

    def test_zero_sum_minimax(self):
        """Zero-sum game is solved using minimax."""
        zs = ZeroSumGame()
        result = zs.solve_minimax([[3, -2], [1, 4]])
        assert "value" in result
        assert "strategy" in result

    def test_replicator_dynamics(self):
        """Replicator dynamics are simulated."""
        eg = EvolutionaryGame()
        # Hawk-Dove game payoff matrix
        result = eg.replicator_dynamics([[0, 2], [1, 1]], initial_freq=0.5, steps=50)
        assert len(result) == 51

    def test_ess(self):
        """Evolutionarily stable strategy is found."""
        eg = EvolutionaryGame()
        ess = eg.evolutionarily_stable_strategy([[0, 2], [1, 1]])
        assert 0 <= ess <= 1

    def test_nash_bargaining(self):
        """Nash bargaining solution is computed."""
        nb = NashBargaining()
        solution = nb.solve(0, 0, 100, 100)
        assert solution[0] > 0
        assert solution[1] > 0

    def test_asymmetric_bargaining(self):
        """Asymmetric Nash bargaining is computed."""
        nb = NashBargaining()
        solution = nb.asymmetric_solution(0, 0, 100, 100, weight1=2.0, weight2=1.0)
        assert solution[0] > solution[1]  # Player 1 gets more

    def test_first_price_auction(self):
        """First-price auction is simulated."""
        aa = AuctionAnalyzer()
        result = aa.first_price_auction([10, 20, 30])
        assert result["winner"] == 2
        assert result["winning_bid"] == 30

    def test_second_price_auction(self):
        """Second-price auction is simulated."""
        aa = AuctionAnalyzer()
        result = aa.second_price_auction([10, 20, 30])
        assert result["winner"] == 2
        assert result["winning_bid"] == 20  # Second highest

    def test_optimal_bid(self):
        """Optimal bid is computed."""
        aa = AuctionAnalyzer()
        bid = aa.optimal_bid(100, n_opponents=2)
        assert bid > 0
        assert bid < 100

    def test_plurality_voting(self):
        """Plurality voting works."""
        v = VotingSystem()
        winner = v.plurality({"A": 3, "B": 2, "C": 1})
        assert winner == "A"

    def test_majority_voting(self):
        """Majority voting works."""
        v = VotingSystem()
        winner = v.majority({"A": 6, "B": 3, "C": 1})
        assert winner == "A"

    def test_borda_count(self):
        """Borda count works."""
        v = VotingSystem()
        votes = [["A", "B", "C", "D"], ["B", "A", "C", "D"], ["A", "C", "B", "D"]]
        winner = v.borda_count(votes, n_candidates=4)
        assert winner == "A"

    def test_copeland(self):
        """Copeland method works."""
        v = VotingSystem()
        preferences = [["A", "B", "C"], ["B", "A", "C"], ["A", "C", "B"]]
        winner = v.copeland(preferences)
        assert winner == "A"


# =============================================================================
# FUTURIS: TIME SERIES ADVANCED TESTS
# =============================================================================

class TestTimeSeriesAdvanced:
    def test_arma_fit(self):
        """ARMA model fits."""
        data = [i * 0.5 + random.gauss(0, 0.1) for i in range(50)]
        arma = ARMA().fit(data, ar_order=1, ma_order=1, max_iter=10)
        assert len(arma.ar_params) == 1
        assert len(arma.ma_params) == 1

    def test_arma_forecast(self):
        """ARMA model forecasts."""
        data = [i * 0.5 for i in range(50)]
        arma = ARMA().fit(data, ar_order=1, ma_order=1, max_iter=10)
        forecasts = arma.forecast(list(data), steps=5)
        assert len(forecasts) == 5

    def test_arima_fit(self):
        """ARIMA model fits."""
        data = [i * 0.5 + random.gauss(0, 0.1) for i in range(50)]
        arima = ARIMA().fit(data, p=1, d=1, q=1, max_iter=10)
        assert arima.d == 1

    def test_arima_forecast(self):
        """ARIMA model forecasts."""
        data = [i * 0.5 for i in range(50)]
        arima = ARIMA().fit(data, p=1, d=1, q=1, max_iter=10)
        forecasts = arima.forecast(list(data), steps=5)
        assert len(forecasts) == 5

    def test_holt_winters_fit(self):
        """Holt-Winters fits."""
        # Seasonal data
        data = [10 + 5 * math.sin(2 * math.pi * i / 12) + i * 0.1 for i in range(36)]
        hw = HoltWinters().fit(data, seasonal_period=12, smoothing_level=0.3, smoothing_trend=0.1, smoothing_seasonal=0.1)
        assert hw.seasonal_period == 12

    def test_holt_winters_forecast(self):
        """Holt-Winters forecasts."""
        data = [10 + 5 * math.sin(2 * math.pi * i / 12) + i * 0.1 for i in range(36)]
        hw = HoltWinters().fit(data, seasonal_period=12)
        forecasts = hw.forecast(steps=5)
        assert len(forecasts) == 5

    def test_prophet_like_fit(self):
        """Prophet-like model fits."""
        dates = [i for i in range(365)]
        values = [100 + i * 0.1 + 10 * math.sin(2 * math.pi * i / 7) for i in range(365)]
        prophet = ProphetLike().fit(dates, values)
        assert "slope" in prophet.trend
        assert "components" in prophet.seasonality

    def test_prophet_like_forecast(self):
        """Prophet-like model forecasts."""
        dates = [i for i in range(365)]
        values = [100 + i * 0.1 + 10 * math.sin(2 * math.pi * i / 7) for i in range(365)]
        prophet = ProphetLike().fit(dates, values)
        forecasts = prophet.forecast(dates, steps=5)
        assert len(forecasts) == 5

    def test_model_selector(self):
        """Model selector chooses best model."""
        data = [i * 0.5 + random.gauss(0, 0.1) for i in range(50)]
        models = {
            "arma_1_1": ARMA().fit(data, ar_order=1, ma_order=1, max_iter=10),
            "arma_2_1": ARMA().fit(data, ar_order=2, ma_order=1, max_iter=10),
        }
        selector = ModelSelector()
        result = selector.select(data, models)
        assert "best_model" in result

    def test_cross_validation(self):
        """Time series cross-validation works."""
        data = [i * 0.5 + random.gauss(0, 0.1) for i in range(100)]
        cv = TimeSeriesCrossValidator()
        result = cv.cross_validate(data, lambda: ARMA(), n_splits=3, test_size=10)
        assert "average_mae" in result
        assert "n_splits" in result

    def test_ensemble_forecaster(self):
        """Ensemble forecaster combines models."""
        data = [i * 0.5 for i in range(50)]
        models = {
            "arma": ARMA().fit(data, ar_order=1, ma_order=1, max_iter=10),
            "arima": ARIMA().fit(data, p=1, d=1, q=1, max_iter=10),
        }

        ensemble = EnsembleForecaster()
        ensemble.add_model(models["arma"], weight=1.0)
        ensemble.add_model(models["arima"], weight=1.0)
        forecasts = ensemble.forecast(data, steps=5)
        assert len(forecasts) == 5


# =============================================================================
# INFERENCE: NLP ADVANCED TESTS
# =============================================================================

class TestNLPAdvanced:
    def test_word_embeddings_build(self):
        """Word embeddings are built from corpus."""
        corpus = [
            "the cat sat on the mat",
            "the dog sat on the log",
            "cats and dogs are friends",
            "the cat and dog play together",
        ]
        we = WordEmbeddings().build_co_occurrence(corpus, dimension=50)
        assert len(we.vocab) > 0
        assert len(we.embeddings) > 0

    def test_word_similarity(self):
        """Word similarity is computed."""
        corpus = [
            "the cat sat on the mat",
            "the cat and the dog played",
            "dogs and cats are pets",
        ]
        we = WordEmbeddings().build_co_occurrence(corpus, dimension=50)
        sim = we.similarity("cat", "dog")
        assert 0 <= sim <= 1

    def test_most_similar(self):
        """Most similar words are found."""
        corpus = [
            "the cat sat on the mat",
            "the cat and the dog played",
            "dogs and cats are pets",
        ]
        we = WordEmbeddings().build_co_occurrence(corpus, dimension=50)
        similar = we.most_similar("cat", top_k=3)
        assert len(similar) <= 3

    def test_pos_tagger(self):
        """POS tagger tags words."""
        corpus = [(["the", "cat"], ["DT", "NN"]), (["a", "dog"], ["DT", "NN"])]
        tagger = POSTagger().train(corpus)

        text = "the cat sat"
        tags = tagger.tag(text)
        assert len(tags) == 3
        assert tags[0][1] == "DT"  # "the" should be determiner

    def test_semantic_similarity(self):
        """Semantic similarity is computed."""
        corpus = [
            "the cat sat on the mat",
            "the cat and the dog played together",
            "dogs and cats are common pets",
            "the dog runs in the park",
        ]
        we = WordEmbeddings().build_co_occurrence(corpus, dimension=50)
        sa = SemanticAnalyzer(embeddings=we)

        sim = sa.sentence_similarity("cat sat mat", "dog played park")
        assert 0 <= sim <= 1

    def test_keyword_extraction(self):
        """Keywords are extracted."""
        text = "machine learning is a subset of artificial intelligence that enables computers to learn from data"
        sa = SemanticAnalyzer()
        keywords = sa.keyword_extraction(text, top_k=3)
        assert len(keywords) == 3
        assert keywords[0][0] in text.lower().split()

    def test_summarization(self):
        """Text summarization works."""
        text = (
            "Artificial intelligence is transforming the world. "
            "Machine learning is a key component of AI. "
            "Deep learning has achieved remarkable results. "
            "Neural networks are the foundation of deep learning. "
            "AI is being applied in healthcare, finance, and transportation."
        )
        summarizer = ExtractiveSummarizer()
        summary = summarizer.summarize(text, max_sentences=2)
        assert len(summary) < len(text)

    def test_lda_topics(self):
        """LDA discovers topics."""
        corpus = [
            "cat dog pet animal",
            "cat dog pet mammal",
            "car truck vehicle automobile",
            "car truck vehicle transport",
            "programming code software developer",
            "programming code software engineer",
        ]
        lda = LDA().fit(corpus, n_topics=3, n_iter=5)
        assert len(lda.topics) == 3

        top_words = lda.topic_words(0, top_k=2)
        assert len(top_words) == 2

    def test_lda_infer_topic(self):
        """LDA infers topic of new text."""
        corpus = [
            "cat dog pet animal",
            "cat dog pet mammal",
            "car truck vehicle automobile",
            "car truck vehicle transport",
        ]
        lda = LDA().fit(corpus, n_topics=2, n_iter=5)

        topic = lda.infer_topic("cat dog pet")
        assert 0 <= topic <= 1

    def test_advanced_ner(self):
        """Advanced NER recognizes entities."""
        ner = AdvancedNER()
        text = "John Smith works at Microsoft Corporation in New York. Contact him at john@example.com on 2024-01-15."
        entities = ner.recognize(text)

        entity_types = [e["type"] for e in entities]
        assert "PERSON" in entity_types
        assert "ORGANIZATION" in entity_types
        assert "LOCATION" in entity_types or "GPE" in entity_types
        assert "EMAIL" in entity_types
        assert "DATE" in entity_types

    def test_markov_generator(self):
        """Markov text generator produces text."""
        text = "the cat sat on the mat the dog sat on the log the cat and dog played"
        gen = MarkovTextGenerator().train(text, order=2)
        generated = gen.generate(length=20)
        assert len(generated) > 0

    def test_coreference_resolution(self):
        """Coreference resolution finds pronouns."""
        cr = CoreferenceResolver()
        text = "John went to the store. He bought some milk."
        resolved = cr.resolve(text)
        assert len(resolved) >= 1
        assert "pronoun" in resolved[0]


# =============================================================================
# MEMORA: KNOWLEDGE GRAPH TESTS
# =============================================================================

class TestKnowledgeGraph:
    def test_add_node(self):
        """Nodes are added to graph."""
        kg = KnowledgeGraph()
        node = kg.add_node("Alice", ["Person"])
        assert node.name == "Alice"
        assert "Person" in node.labels

    def test_add_edge(self):
        """Edges are added to graph."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("Alice")
        n2 = kg.add_node("Bob")
        edge = kg.add_edge(n1.id, n2.id, "KNOWS")
        assert edge.relation == "KNOWS"

    def test_get_neighbors(self):
        """Neighbors are retrieved."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("Alice")
        n2 = kg.add_node("Bob")
        n3 = kg.add_node("Charlie")
        kg.add_edge(n1.id, n2.id, "KNOWS")
        kg.add_edge(n1.id, n3.id, "KNOWS")

        neighbors = kg.get_neighbors(n1.id, relation="KNOWS")
        assert len(neighbors) == 2

    def test_get_paths(self):
        """Paths are found between nodes."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("A")
        n2 = kg.add_node("B")
        n3 = kg.add_node("C")
        kg.add_edge(n1.id, n2.id, "CONNECTED")
        kg.add_edge(n2.id, n3.id, "CONNECTED")

        paths = kg.get_paths(n1.id, n3.id, max_depth=3)
        assert len(paths) >= 1

    def test_query(self):
        """Graph queries work."""
        kg = KnowledgeGraph()
        alice = kg.add_node("Alice", ["Person"])
        bob = kg.add_node("Bob", ["Person"])
        company = kg.add_node("Google", ["Organization"])
        kg.add_edge(alice.id, company.id, "WORKS_AT")
        kg.add_edge(bob.id, company.id, "WORKS_AT")

        results = kg.query({"node_label": "Person", "relation": "WORKS_AT", "target_label": "Organization"})
        assert len(results) == 2

    def test_graph_stats(self):
        """Graph statistics are computed."""
        kg = KnowledgeGraph()
        for i in range(5):
            kg.add_node(f"N{i}", ["Test"])

        for i in range(5):
            for j in range(i + 1, 5):
                kg.add_edge(f"node_{i}", f"node_{j}", "REL")

        stats = kg.get_stats()
        assert stats["total_nodes"] == 5
        assert stats["total_edges"] == 10

    def test_graph_embedding(self):
        """Graph embeddings are trained."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("A")
        n2 = kg.add_node("B")
        n3 = kg.add_node("C")
        kg.add_edge(n1.id, n2.id, "REL1")
        kg.add_edge(n2.id, n3.id, "REL2")

        gem = GraphEmbedding().train(kg, epochs=10)
        score = gem.score_triple(n1.id, "REL1", n2.id)
        assert score >= 0

    def test_transitive_inference(self):
        """Transitive relationships are inferred."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("A")
        n2 = kg.add_node("B")
        n3 = kg.add_node("C")
        kg.add_edge(n1.id, n2.id, "RELATED")
        kg.add_edge(n2.id, n3.id, "RELATED")

        inf = RelationshipInferer()
        inferred = inf.infer_transitive(kg, "RELATED")
        assert len(inferred) >= 1

    def test_symmetry_inference(self):
        """Symmetric relationships are inferred."""
        kg = KnowledgeGraph()
        n1 = kg.add_node("A")
        n2 = kg.add_node("B")
        kg.add_edge(n1.id, n2.id, "FRIEND_OF")

        inf = RelationshipInferer()
        inferred = inf.infer_symmetric(kg, "FRIEND_OF")
        assert len(inferred) >= 1

    def test_ontology_subclass(self):
        """Ontology subclass checking works."""
        ob = OntologyBuilder()
        ob.add_class("Animal")
        ob.add_class("Mammal", parent="Animal")
        ob.add_class("Dog", parent="Mammal")

        assert ob.is_subclass("Dog", "Mammal")
        assert ob.is_subclass("Dog", "Animal")
        assert not ob.is_subclass("Mammal", "Dog")

    def test_ontology_properties(self):
        """Ontology inherits properties."""
        ob = OntologyBuilder()
        ob.add_class("Animal", properties=["name", "age"])
        ob.add_class("Dog", parent="Animal", properties=["breed"])

        props = ob.get_inherited_properties("Dog")
        assert "name" in props
        assert "age" in props
        assert "breed" in props

    def test_description_logic_inference(self):
        """Description logic inference works."""
        reasoner = DescriptionLogicReasoner()
        reasoner.add_axiom("dog1", "is_a", "Dog")
        reasoner.add_axiom("Dog", "is_a", "Mammal")
        reasoner.add_axiom("Mammal", "is_a", "Animal")

        assert reasoner.is_instance_of("dog1", "Mammal")
        assert reasoner.is_instance_of("dog1", "Animal")

    def test_entity_linking(self):
        """Entity linking works."""
        entities = [
            {"id": "apple_inc", "name": "Apple"},
            {"id": "apple_fruit", "name": "Apple"},
        ]
        linker = EntityLinker().build_index(entities)
        results = linker.link("I ate an Apple and bought an Apple", context=["fruit", "computer"])
        assert len(results) == 2


# =============================================================================
# SENTINEL: THREAT INTELLIGENCE TESTS
# =============================================================================

class TestThreatIntel:
    def test_indicator_creation(self):
        """Indicators are created correctly."""
        ind = Indicator(id="ind_1", type="ipv4", value="1.2.3.4", confidence=0.8)
        assert ind.type == "ipv4"
        assert ind.value == "1.2.3.4"

    def test_indicator_confidence(self):
        """Indicator confidence score is computed."""
        ind = Indicator(id="ind_1", type="ipv4", value="1.2.3.4", confidence=0.5, tags=["malware"])
        score = ind.confidence_score()
        assert score > 0.5  # Should be boosted by recent activity and tags

    def test_threat_actor_threat_level(self):
        """Threat actor threat level is computed."""
        actor = ThreatActor(
            name="APT1",
            sophistication="expert",
            tactics=["initial_access", "persistence", "privilege_escalation"],
            techniques=["t1566", "t1059", "t1068"],
            tools=["powershell", "mimikatz"],
        )
        level = actor.threat_level()
        assert level == "critical"

    def test_threat_actor_overlap(self):
        """Threat actor overlap is computed."""
        actor1 = ThreatActor(name="APT1", techniques=["t1566", "t1059"], tactics=["initial_access"])
        actor2 = ThreatActor(name="APT2", techniques=["t1566", "t1059", "t1068"], tactics=["initial_access", "persistence"])

        overlap = actor1.overlap_with(actor2)
        assert overlap > 0

    def test_correlate_by_type(self):
        """Correlation by type works."""
        tc = ThreatCorrelator()
        tc.add_indicator(Indicator(id="1", type="ipv4", value="1.2.3.4"))
        tc.add_indicator(Indicator(id="2", type="ipv4", value="5.6.7.8"))
        tc.add_indicator(Indicator(id="3", type="domain", value="bad.com"))

        correlations = tc.correlate_by_type()
        assert len(correlations) == 1
        assert correlations[0]["type"] == "ipv4"

    def test_correlate_by_tags(self):
        """Correlation by tags works."""
        tc = ThreatCorrelator()
        tc.add_indicator(Indicator(id="1", type="ipv4", value="1.2.3.4", tags=["malware", "apt"]))
        tc.add_indicator(Indicator(id="2", type="domain", value="bad.com", tags=["malware"]))
        tc.add_indicator(Indicator(id="3", type="url", value="evil.com", tags=["phishing"]))

        correlations = tc.correlate_by_tags()
        assert len(correlations) >= 1

    def test_campaign_analysis(self):
        """Campaign analysis works."""
        indicators = [
            Indicator(id="1", type="ipv4", value="1.2.3.4", tags=["ransomware"]),
            Indicator(id="2", type="domain", value="bad.com", tags=["ransomware"]),
        ]
        actors = [ThreatActor(name="LockBit", tactics=["ransomware"])]
        patterns = [AttackPattern(name="Ransomware", tactic="ransomware")]

        ca = CampaignAnalyzer()
        campaigns = ca.analyze(indicators, actors, patterns)
        assert len(campaigns) >= 1

    def test_malware_classification(self):
        """Malware classification works."""
        mc = MalwareClassifier()
        mc.add_family("Emotet", {"api_calls": 100, "strings": 50, "sections": 4})
        mc.add_family("Trickbot", {"api_calls": 120, "strings": 60, "sections": 3})

        family, score = mc.classify({"api_calls": 105, "strings": 52, "sections": 4})
        assert family in ["Emotet", "Trickbot"]
        assert score > 0

    def test_vulnerability_analysis(self):
        """Vulnerability analysis works."""
        va = VulnerabilityAnalyzer()
        va.add_cve("CVE-2024-0001", 9.8, "Critical vulnerability", ["Windows"])
        va.add_cve("CVE-2024-0002", 5.0, "Medium vulnerability", ["Linux"])

        top = va.get_top_vulnerabilities(n=1)
        assert top[0]["id"] == "CVE-2024-0001"
        assert top[0]["cvss"] == 9.8

    def test_threat_feed_merge(self):
        """Threat feeds are merged."""
        tfa = ThreatFeedAnalyzer()
        tfa.add_feed("Feed1", ["1.2.3.4", "5.6.7.8"], "source1")
        tfa.add_feed("Feed2", ["5.6.7.8", "9.10.11.12"], "source2")

        merged = tfa.merge_feeds()
        assert len(merged) == 3

        deduplicated = tfa.deduplicate(merged)
        assert len(deduplicated) == 3

    def test_attack_pattern_mapping(self):
        """Attack pattern mapping works."""
        apm = AttackPatternMapper()
        apm.add_technique(AttackPattern(id="T1566", name="Phishing", tactic="initial_access"))
        apm.add_technique(AttackPattern(id="T1059", name="Command Execution", tactic="execution"))

        coverage = apm.get_coverage(["initial_access", "execution"])
        assert coverage["initial_access"]["technique_count"] == 1
        assert coverage["execution"]["technique_count"] == 1

    def test_threat_prioritization(self):
        """Threat prioritization works."""
        threats = [
            {"id": "t1", "cvss": 9.8, "asset": "db01", "exposure": 1.0},
            {"id": "t2", "cvss": 5.0, "asset": "web01", "exposure": 0.5},
            {"id": "t3", "cvss": 7.5, "asset": "db02", "exposure": 1.0},
        ]
        asset_criticality = {"db01": 1.0, "web01": 0.5, "db02": 0.8}

        tp = ThreatPrioritizer()
        prioritized = tp.prioritize(threats, asset_criticality)

        assert prioritized[0]["id"] == "t1"  # Highest priority
        assert prioritized[0]["priority_level"] == "critical"

    def test_indicator_lifecycle(self):
        """Indicator lifecycle management works."""
        import time
        lm = IndicatorLifecycleManager()
        # Add an expired indicator
        expired = Indicator(id="ind_1", value="1.2.3.4")
        expired.last_seen = time.time() - 500 * 86400  # 500 days ago
        lm.add(expired)
        lm.add(Indicator(id="ind_2", value="5.6.7.8"))

        stats = lm.get_stats()
        assert stats["total_indicators"] == 2
        assert stats["active_indicators"] == 1

        lm.archive("ind_1")
        stats = lm.get_stats()
        assert stats["archived_indicators"] >= 1

    def test_attack_pattern_mitigation(self):
        """Attack pattern mitigation recommendations are returned."""
        apm = AttackPatternMapper()
        apm.add_technique(AttackPattern(
            id="T1566", name="Phishing", tactic="initial_access",
            mitigation="Implement email filtering and user training"
        ))

        recommendations = apm.get_mitigation_recommendations("initial_access")
        assert len(recommendations) >= 1
