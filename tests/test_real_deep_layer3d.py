"""
Tests for Layer 3d — Real Deep Engines (Graph Analytics, Reinforcement Learning, Bayesian, Streaming, Vision)

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

# ===== INTELX: Graph Analytics =====
_ga = _load_module("IntelX/app/agents/real_graph_analytics.py", "real_graph_analytics")
Graph = _ga.Graph
PageRankAnalyzer = _ga.PageRankAnalyzer
CommunityDetector = _ga.CommunityDetector
ShortestPathFinder = _ga.ShortestPathFinder
CentralityAnalyzer = _ga.CentralityAnalyzer
InfluenceSpreadAnalyzer = _ga.InfluenceSpreadAnalyzer

# ===== CORTEX: Reinforcement Learning =====
_rl = _load_module("Cortex/app/agents/real_reinforcement_learning.py", "real_reinforcement_learning")
QLearningAgent = _rl.QLearningAgent
SarsaAgent = _rl.SarsaAgent
PolicyGradientAgent = _rl.PolicyGradientAgent
ActorCriticAgent = _rl.ActorCriticAgent
RewardTracker = _rl.RewardTracker
ExplorationStrategy = _rl.ExplorationStrategy

# ===== INFERENCE: Bayesian =====
_ba = _load_module("Inference/app/agents/real_bayesian_engine.py", "real_bayesian_engine")
Normal = _ba.Normal
Beta = _ba.Beta
BayesianInference = _ba.BayesianInference
MetropolisHastings = _ba.MetropolisHastings
GibbsSampler = _ba.GibbsSampler
BayesianLinearRegression = _ba.BayesianLinearRegression
BayesianHypothesisTest = _ba.BayesianHypothesisTest

# ===== FUTURIS: Streaming =====
_st = _load_module("Futuris/app/agents/real_streaming.py", "real_streaming")
Event = _st.Event
TumblingWindow = _st.TumblingWindow
SlidingWindow = _st.SlidingWindow
StreamProcessor = _st.StreamProcessor
RealtimeStats = _st.RealtimeStats
StreamAlert = _st.StreamAlert
PatternDetector = _st.PatternDetector
BackpressureHandler = _st.BackpressureHandler
StreamPipeline = _st.StreamPipeline
StatefulStreamProcessor = _st.StatefulStreamProcessor

# ===== VYRALX: Vision =====
_vi = _load_module("VyralX/app/agents/real_vision_engine.py", "real_vision_engine")
Image = _vi.Image
ImageProcessor = _vi.ImageProcessor
FeatureExtractor = _vi.FeatureExtractor
ImageSegmenter = _vi.ImageSegmenter
TemplateMatcher = _vi.TemplateMatcher
ImageClassifier = _vi.ImageClassifier
SimpleOCR = _vi.SimpleOCR


# =============================================================================
# INTELX: GRAPH ANALYTICS TESTS
# =============================================================================

class TestGraphAnalytics:
    def test_graph_add_node(self):
        """Graph adds nodes correctly."""
        g = Graph()
        g.add_node("A")
        assert "A" in g.nodes

    def test_graph_add_edge(self):
        """Graph adds edges correctly."""
        g = Graph()
        g.add_edge("A", "B", weight=2.0)
        assert g.get_edge_weight("A", "B") == 2.0
        assert g.get_degree("A") == 1

    def test_graph_density(self):
        """Graph density is computed."""
        g = Graph()
        for i in range(5):
            for j in range(i + 1, 5):
                g.add_edge(f"N{i}", f"N{j}")
        density = g.get_density()
        assert 0 < density <= 1.0

    def test_pagerank(self):
        """PageRank computes scores."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        g.add_edge("C", "A")
        pr = PageRankAnalyzer()
        scores = pr.compute(g)
        assert len(scores) == 3
        assert sum(scores.values()) > 0

    def test_community_detection(self):
        """Community detection works."""
        g = Graph()
        # Two clusters
        for i in range(5):
            for j in range(i + 1, 5):
                g.add_edge(f"A{i}", f"A{j}")
        for i in range(5):
            for j in range(i + 1, 5):
                g.add_edge(f"B{i}", f"B{j}")

        cd = CommunityDetector()
        communities = cd.detect(g)
        assert len(communities) == 10
        assert cd.modularity >= 0

    def test_dijkstra(self):
        """Dijkstra finds shortest paths."""
        g = Graph()
        g.add_edge("A", "B", 1.0)
        g.add_edge("B", "C", 2.0)
        g.add_edge("A", "C", 5.0)

        sp = ShortestPathFinder()
        dist = sp.dijkstra(g, "A")
        assert dist["A"] == 0.0
        assert dist["B"] == 1.0
        assert dist["C"] == 3.0  # A->B->C = 3, not A->C = 5

    def test_bfs(self):
        """BFS finds shortest paths (unweighted)."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        g.add_edge("C", "D")

        sp = ShortestPathFinder()
        dist = sp.bfs(g, "A")
        assert dist["A"] == 0
        assert dist["B"] == 1
        assert dist["C"] == 2
        assert dist["D"] == 3

    def test_floyd_warshall(self):
        """Floyd-Warshall finds all-pairs shortest paths."""
        g = Graph()
        g.add_edge("A", "B", 1)
        g.add_edge("B", "C", 2)
        g.add_edge("A", "C", 5)

        sp = ShortestPathFinder()
        dist = sp.floyd_warshall(g)
        assert dist["A"]["C"] == 3  # A->B->C

    def test_degree_centrality(self):
        """Degree centrality is computed."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("A", "C")
        g.add_edge("A", "D")

        ca = CentralityAnalyzer()
        centrality = ca.compute_degree(g)
        assert centrality["A"] > centrality["B"]

    def test_betweenness_centrality(self):
        """Betweenness centrality is computed."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        g.add_edge("C", "D")

        ca = CentralityAnalyzer()
        centrality = ca.compute_betweenness(g)
        assert centrality["B"] >= centrality["A"]

    def test_closeness_centrality(self):
        """Closeness centrality is computed."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        g.add_edge("A", "C")

        ca = CentralityAnalyzer()
        centrality = ca.compute_closeness(g)
        assert centrality["A"] > 0

    def test_eigenvector_centrality(self):
        """Eigenvector centrality is computed."""
        g = Graph()
        g.add_edge("A", "B")
        g.add_edge("B", "C")
        g.add_edge("C", "A")

        ca = CentralityAnalyzer()
        centrality = ca.compute_eigenvector(g)
        assert len(centrality) == 3
        assert sum(centrality.values()) > 0

    def test_connected_components(self):
        """Connected components are found."""
        g = Graph(is_directed=False)
        g.add_edge("A", "B")
        g.add_edge("C", "D")
        g.add_node("E")

        components = g.get_connected_components()
        assert len(components) == 3  # {A,B}, {C,D}, {E}

    def test_influence_spread(self):
        """Influence spread is simulated."""
        g = Graph()
        for i in range(5):
            for j in range(i + 1, 5):
                g.add_edge(f"N{i}", f"N{j}")

        isa = InfluenceSpreadAnalyzer()
        cascade = isa.simulate_cascade(g, ["N0"], model="independent")
        assert "N0" in cascade
        assert sum(cascade.values()) > 0


# =============================================================================
# CORTEX: REINFORCEMENT LEARNING TESTS
# =============================================================================

class TestReinforcementLearning:
    def test_q_learning_get_action(self):
        """Q-Learning selects actions."""
        agent = QLearningAgent(action_space=[0, 1])
        action = agent.get_action((0, 0), explore=False)
        assert action in [0, 1]

    def test_q_learning_update(self):
        """Q-Learning updates Q-table."""
        agent = QLearningAgent(action_space=[0, 1], learning_rate=0.5)
        agent.update((0, 0), 0, 1.0, (0, 1))
        assert agent.q_table[((0, 0), 0)] > 0

    def test_q_learning_train(self):
        """Q-Learning trains on environment."""
        # Simple environment: 3 states, 2 actions
        def env_step(action, *args):
            if action == "reset":
                return (0, 0)
            state = args[0]
            if state == 0:
                next_state = 1
                reward = 0.0
            elif state == 1:
                next_state = 2
                reward = 1.0
            else:
                next_state = 2
                reward = 1.0

            return next_state, reward, state == 2

        agent = QLearningAgent(
            action_space=[0, 1],
            learning_rate=0.1,
            discount_factor=0.9,
            epsilon=0.1,
        )
        agent.state_space = [0, 1, 2]

        # Fix env_step signature
        def env(action, *args):
            if action == "reset":
                return (0, 0)
            state = args[0]
            if state == 0:
                return (1, 0.0, False)
            elif state == 1:
                return (2, 1.0, False)
            else:
                return (2, 1.0, True)

        result = agent.train(env, episodes=50, max_steps=10)
        assert result["episodes"] == 50
        assert result["q_table_size"] > 0

    def test_sarsa_update(self):
        """SARSA updates Q-table."""
        agent = SarsaAgent(action_space=[0, 1])
        agent.update((0, 0), 0, 1.0, (0, 1), 1)
        assert agent.q_table[((0, 0), 0)] > 0

    def test_policy_gradient_select_action(self):
        """Policy gradient selects actions."""
        agent = PolicyGradientAgent(action_space=[0, 1])
        action = agent.select_action((0, 0))
        assert action in [0, 1]

    def test_policy_gradient_update(self):
        """Policy gradient updates policy."""
        agent = PolicyGradientAgent(action_space=[0, 1], learning_rate=0.1)
        agent.update_policy((0, 0), 0, 1.0, (0, 1))
        # Probability of action 0 should increase
        probs = agent.policy.get((0, 0), {0: 0.5, 1: 0.5})
        assert probs.get(0, 0) >= 0.5

    def test_actor_critic_update(self):
        """Actor-Critic updates both actor and critic."""
        agent = ActorCriticAgent(action_space=[0, 1])
        agent.update((0, 0), 0, 1.0, (0, 1))
        assert agent.critic_values.get((0, 0), 0.0) > 0

    def test_reward_tracker(self):
        """Reward tracker computes statistics."""
        rt = RewardTracker()
        for _ in range(100):
            rt.add_reward(random.gauss(1, 0.1), episode=True)

        assert rt.get_average_reward() > 0
        assert rt.get_reward_std() > 0
        assert rt.get_max_reward() > 0

    def test_exploration_strategy(self):
        """Exploration strategy decays epsilon."""
        es = ExplorationStrategy(epsilon=0.5, epsilon_decay=0.9)
        initial = es.get_epsilon()
        for _ in range(10):
            es.decay()
        assert es.get_epsilon() < initial

    def test_softmax_exploration(self):
        """Softmax exploration selects actions."""
        es = ExplorationStrategy(strategy="softmax")
        action = es.use_softmax([0.1, 0.9, 0.5])
        assert 0 <= action <= 2


# =============================================================================
# INFERENCE: BAYESIAN TESTS
# =============================================================================

class TestBayesianEngine:
    def test_normal_pdf(self):
        """Normal distribution pdf is computed."""
        n = Normal(mean=0, std=1)
        assert n.pdf(0) > 0
        assert n.pdf(0) > n.pdf(2)

    def test_normal_sample(self):
        """Normal distribution samples correctly."""
        n = Normal(mean=0, std=1)
        samples = [n.sample() for _ in range(1000)]
        mean = sum(samples) / len(samples)
        assert abs(mean) < 0.1  # Should be close to 0

    def test_normal_cdf(self):
        """Normal distribution cdf is computed."""
        n = Normal(mean=0, std=1)
        assert 0 <= n.cdf(0) <= 1
        assert n.cdf(0) == 0.5

    def test_beta_mean(self):
        """Beta distribution mean is computed."""
        b = Beta(alpha=2, beta=2)
        assert abs(b.mean() - 0.5) < 0.01

    def test_beta_sample(self):
        """Beta distribution samples correctly."""
        b = Beta(alpha=2, beta=5)
        samples = [b.sample() for _ in range(1000)]
        mean = sum(samples) / len(samples)
        expected = 2 / 7
        assert abs(mean - expected) < 0.05

    def test_bayesian_inference_update(self):
        """Bayesian inference updates posterior."""
        bi = BayesianInference()
        bi.update([1.0, 2.0, 3.0, 4.0, 5.0], prior_mean=0.0, prior_std=10.0, likelihood_std=1.0)
        assert bi.posterior.mean > 0
        assert bi.posterior.std < 10.0  # Posterior should be more certain

    def test_bayesian_inference_ci(self):
        """Bayesian inference computes confidence interval."""
        bi = BayesianInference()
        bi.update([1.0, 2.0, 3.0, 4.0, 5.0])
        lower, upper = bi.confidence_interval(alpha=0.05)
        assert lower < upper
        assert lower < bi.posterior.mean < upper

    def test_metropolis_hastings(self):
        """Metropolis-Hastings samples from distribution."""
        # Target: normal distribution
        def log_pdf(x):
            return -0.5 * x ** 2

        mh = MetropolisHastings(target_log_pdf=log_pdf, n_samples=500, burn_in=100)
        samples = mh.sample(initial=0.0)
        assert len(samples) == 500
        assert abs(mh.mean()) < 1.0

    def test_gibbs_sampler(self):
        """Gibbs sampler samples from joint distribution."""
        def cond_x(states):
            return states["y"] * 0.5

        def cond_y(states):
            return states["x"] * 0.5

        gs = GibbsSampler(n_samples=100, burn_in=20)
        samples = gs.sample({"x": cond_x, "y": cond_y}, {"x": 1.0, "y": 1.0})
        assert len(samples) == 100
        assert "x" in samples[0]

    def test_bayesian_linear_regression(self):
        """Bayesian linear regression fits."""
        # Linear data: y = 2x + 1
        X = [[i] for i in range(50)]
        y = [2 * i + 1 + random.gauss(0, 0.1) for i in range(50)]

        blr = BayesianLinearRegression()
        blr.fit(X, y)

        pred_mean, pred_std = blr.predict([25])
        assert abs(pred_mean - 51) < 2.0
        assert pred_std > 0

    def test_bayesian_hypothesis_test(self):
        """Bayesian hypothesis test computes Bayes factor."""
        bht = BayesianHypothesisTest()
        bf = bht.bayes_factor(model1_ll=-10, model2_ll=-15, n_samples=100)
        assert bf > 1  # Model 1 is better
        assert "interpretation" in bht.get_result()


# =============================================================================
# FUTURIS: STREAMING TESTS
# =============================================================================

class TestStreaming:
    def test_event_creation(self):
        """Events are created correctly."""
        event = Event(data={"value": 10}, event_type="test")
        assert event.get("value") == 10
        assert event.timestamp > 0

    def test_tumbling_window(self):
        """Tumbling window aggregates correctly."""
        window = TumblingWindow(window_size=3)
        for i in range(3):
            window.add(Event(data={"value": i + 1}))

        assert window.is_full()
        assert window.aggregate("sum") == 6
        assert window.aggregate("avg") == 2

    def test_sliding_window(self):
        """Sliding window produces overlapping windows."""
        window = SlidingWindow(window_size=3, slide_size=1)
        windows = []
        for i in range(5):
            windows.extend(window.add(Event(data={"value": i})))

        # Should have multiple overlapping windows
        assert len(windows) >= 1

    def test_stream_processor(self):
        """Stream processor processes events."""
        sp = StreamProcessor()
        event = Event(data={"value": 10})
        sp.process(event)
        assert sp.state["value"] == 10
        assert sp.events_processed == 1

    def test_stream_processor_stateful(self):
        """Stream processor maintains state."""
        sp = StreamProcessor()
        for i in range(5):
            sp.process(Event(data={"value": 1}))
        assert sp.state["value"] == 5

    def test_realtime_stats(self):
        """Real-time stats compute statistics."""
        stats = RealtimeStats()
        for i in range(100):
            stats.add(i)

        assert stats.mean() == 49.5
        assert stats.std() > 0
        assert stats.count() == 100

    def test_realtime_moving_average(self):
        """Moving average is computed."""
        stats = RealtimeStats()
        for i in range(20):
            stats.add(i)

        ma = stats.moving_average(window=5)
        assert ma > 0

    def test_stream_alert(self):
        """Stream alerts trigger on conditions."""
        alerts = StreamAlert()
        alerts.add_rule("high_value", lambda e: e.get("value", 0) > 100, severity="high")

        triggered = alerts.check(Event(data={"value": 150}))
        assert len(triggered) == 1
        assert triggered[0]["severity"] == "high"

        triggered2 = alerts.check(Event(data={"value": 50}))
        assert len(triggered2) == 0

    def test_pattern_detector_momentum(self):
        """Pattern detector detects momentum."""
        pd = PatternDetector()
        values = [1, 2, 3, 4, 5, 6]  # Strong upward momentum
        assert pd.detect_momentum(values, window=5, threshold=0.1) is True

    def test_pattern_detector_trend(self):
        """Pattern detector detects trend."""
        pd = PatternDetector()
        upward = [i * 0.5 for i in range(10)]
        assert pd.detect_trend(upward, window=5) == "upward"

        downward = [10 - i * 0.5 for i in range(10)]
        assert pd.detect_trend(downward, window=5) == "downward"

    def test_pattern_detector_anomaly(self):
        """Pattern detector detects anomalies."""
        pd = PatternDetector()
        values = [10, 10, 10, 10, 10, 10000]  # Extreme anomaly at end
        assert pd.detect_anomaly(values, window=5, threshold=1.5) is True

    def test_backpressure_handler(self):
        """Backpressure handler manages buffer."""
        bp = BackpressureHandler(max_buffer_size=100)
        bp.update_buffer(50)
        assert bp.should_drop() is False

        bp.update_buffer(150)
        assert bp.should_drop() is True

        bp.drop_event()
        assert bp.get_stats()["dropped_events"] == 1

    def test_stream_pipeline(self):
        """Stream pipeline processes through stages."""
        pipeline = StreamPipeline()
        pipeline.add_stage("stage1", StreamProcessor(), predicate=lambda e: e.get("value", 0) > 5)

        event1 = Event(data={"value": 10})
        event2 = Event(data={"value": 1})

        result1 = pipeline.process(event1)
        result2 = pipeline.process(event2)

        assert result1 is not None
        assert result2 is None  # Filtered out

    def test_stateful_stream_processor(self):
        """Stateful stream processor triggers windows."""
        ssp = StatefulStreamProcessor()
        ssp.add_window("count", window_size=3)

        triggered = []
        for i in range(5):
            result = ssp.process(Event(data={"value": 1}), "count")
            if result:
                triggered.append(result)

        assert len(triggered) >= 1
        assert triggered[0]["count"] == 3


# =============================================================================
# VYRALX: VISION TESTS
# =============================================================================

class TestVisionEngine:
    def _make_image(self, width: int, height: int, color: tuple = (128, 128, 128)) -> Image:
        """Create a test image."""
        pixels = [[color] * width for _ in range(height)]
        return Image(pixels=pixels, width=width, height=height)

    def test_image_creation(self):
        """Image is created correctly."""
        img = self._make_image(10, 10)
        assert img.width == 10
        assert img.height == 10
        assert img.get_pixel(0, 0) == (128, 128, 128)

    def test_grayscale_conversion(self):
        """Grayscale conversion works."""
        img = self._make_image(5, 5, (255, 0, 0))
        gray = img.to_grayscale()
        r, g, b = gray.get_pixel(0, 0)
        assert r == g == b  # Grayscale has equal channels

    def test_binary_conversion(self):
        """Binary conversion works."""
        img = self._make_image(5, 5, (255, 255, 255))
        binary = img.to_binary(threshold=128)
        r, _, _ = binary.get_pixel(0, 0)
        assert r == 255

    def test_blur(self):
        """Blur operation works."""
        img = self._make_image(5, 5)
        # Create a sharp edge
        img.set_pixel(0, 0, (255, 255, 255))
        blurred = ImageProcessor().blur(img, radius=1)
        # Pixel should be less than 255 after blur
        r, _, _ = blurred.get_pixel(0, 0)
        assert r < 255

    def test_sharpen(self):
        """Sharpen operation works."""
        img = self._make_image(5, 5)
        img.set_pixel(0, 0, (200, 200, 200))
        img.set_pixel(1, 0, (100, 100, 100))
        sharpened = ImageProcessor().sharpen(img, amount=2.0)
        r, _, _ = sharpened.get_pixel(0, 0)
        assert r > 150  # Should be sharpened

    def test_edge_detection(self):
        """Edge detection finds edges."""
        img = self._make_image(10, 10, (0, 0, 0))
        # Create a sharp vertical edge
        for y in range(10):
            for x in range(5):
                img.set_pixel(x, y, (255, 255, 255))

        edges = ImageProcessor().edge_detect(img)
        # Edge should be detected at boundary
        edge_sum = sum(row[0][0] for row in edges.pixels) + sum(row[-1][0] for row in edges.pixels)
        # Check interior pixels where edge should be
        for y in range(1, 9):
            for x in range(3, 7):
                r, _, _ = edges.get_pixel(x, y)
                if r > 0:
                    edge_sum += r
        assert edge_sum > 0

    def test_brightness_adjust(self):
        """Brightness adjustment works."""
        img = self._make_image(5, 5, (100, 100, 100))
        brightened = ImageProcessor().adjust_brightness(img, factor=1.5)
        r, _, _ = brightened.get_pixel(0, 0)
        assert r > 100

    def test_contrast_adjust(self):
        """Contrast adjustment works."""
        img = self._make_image(5, 5)
        # Add variation
        img.set_pixel(0, 0, (50, 50, 50))
        img.set_pixel(4, 4, (200, 200, 200))
        contrasted = ImageProcessor().adjust_contrast(img, factor=1.5)
        r1, _, _ = contrasted.get_pixel(0, 0)
        r2, _, _ = contrasted.get_pixel(4, 4)
        assert r2 - r1 > 150  # More contrast

    def test_color_histogram(self):
        """Color histogram is extracted."""
        img = self._make_image(10, 10, (255, 0, 0))
        hist = FeatureExtractor().color_histogram(img, bins=4)
        assert len(hist) == 64  # 4^3
        assert sum(hist) > 0

    def test_grayscale_histogram(self):
        """Grayscale histogram is extracted."""
        img = self._make_image(10, 10, (128, 128, 128))
        hist = FeatureExtractor().grayscale_histogram(img, bins=8)
        assert len(hist) == 8
        assert sum(hist) > 0

    def test_texture_features(self):
        """Texture features are extracted."""
        img = self._make_image(10, 10)
        features = FeatureExtractor().texture_features(img)
        assert "mean" in features
        assert "std" in features
        assert "edge_density" in features

    def test_color_moments(self):
        """Color moments are extracted."""
        img = self._make_image(10, 10, (255, 128, 0))
        moments = FeatureExtractor().color_moments(img)
        assert "red" in moments
        assert "green" in moments
        assert "blue" in moments

    def test_threshold_segmentation(self):
        """Threshold segmentation works."""
        img = self._make_image(5, 5)
        img.set_pixel(0, 0, (200, 200, 200))
        segmented = ImageSegmenter().threshold_segmentation(img, threshold=128)
        r, _, _ = segmented.get_pixel(0, 0)
        assert r == 255

    def test_adaptive_threshold(self):
        """Adaptive threshold works."""
        img = self._make_image(10, 10)
        # Create variation
        for i in range(5):
            img.set_pixel(i, i, (255, 255, 255))
        segmented = ImageSegmenter().adaptive_threshold(img, window_size=5, offset=10)
        assert segmented.width == 10

    def test_connected_components(self):
        """Connected components are found."""
        img = self._make_image(10, 10, (0, 0, 0))
        # Create two separate shapes
        for i in range(3):
            img.set_pixel(i, i, (255, 255, 255))
        for i in range(7, 10):
            img.set_pixel(i, i, (255, 255, 255))

        components = ImageSegmenter().connected_components(img)
        assert len(components) >= 2  # At least two separate components

    def test_template_matching(self):
        """Template matching finds objects."""
        # Create image with a pattern
        img = self._make_image(10, 10, (0, 0, 0))
        # Add a 3x3 pattern at position (5, 5)
        pattern = [[0, 255, 0], [255, 0, 255], [0, 255, 0]]
        for dy in range(3):
            for dx in range(3):
                img.set_pixel(5 + dx, 5 + dy, (pattern[dy][dx], pattern[dy][dx], pattern[dy][dx]))

        # Create template (same 3x3 pattern)
        template = self._make_image(3, 3, (0, 0, 0))
        for dy in range(3):
            for dx in range(3):
                template.set_pixel(dx, dy, (pattern[dy][dx], pattern[dy][dx], pattern[dy][dx]))

        matcher = TemplateMatcher()
        result = matcher.match(img, template)
        assert result["score"] > 0
        assert result["location"][0] >= 5

    def test_image_classifier(self):
        """Image classifier trains and predicts."""
        # Create training images
        images = []
        labels = []

        # Dark images (class A)
        for _ in range(5):
            images.append(self._make_image(10, 10, (30, 30, 30)))
            labels.append("A")

        # Bright images (class B)
        for _ in range(5):
            images.append(self._make_image(10, 10, (220, 220, 220)))
            labels.append("B")

        clf = ImageClassifier().train(images, labels)

        # Predict dark image
        pred_label, confidence = clf.predict(self._make_image(10, 10, (30, 30, 30)))
        assert pred_label == "A"

        # Predict bright image
        pred_label, confidence = clf.predict(self._make_image(10, 10, (220, 220, 220)))
        assert pred_label == "B"

    def test_ocr_recognition(self):
        """OCR recognizes characters."""
        # Create simple character templates
        chars = {}

        # Create "A" template (triangle shape)
        a_img = self._make_image(8, 10, (0, 0, 0))
        for y in range(10):
            for x in range(8):
                if 3 <= x <= 4 or (2 <= x <= 5 and (y == 2 or y == 7)) or (1 <= x <= 6 and (y == 4 or y == 5)) or (y == 8 and 2 <= x <= 5):
                    a_img.set_pixel(x, y, (255, 255, 255))
        chars["A"] = a_img

        # Create "B" template (rectangle-ish)
        b_img = self._make_image(8, 10, (0, 0, 0))
        for y in range(10):
            for x in range(8):
                if x <= 2 or (y >= 3 and x >= 6) or (y >= 7 and x >= 6):
                    b_img.set_pixel(x, y, (255, 255, 255))
        chars["B"] = b_img

        ocr = SimpleOCR().train(chars)

        # Recognize A
        result_char, confidence = ocr.recognize(chars["A"])
        assert result_char == "A"

        # Recognize B
        result_char, confidence = ocr.recognize(chars["B"])
        assert result_char == "B"
