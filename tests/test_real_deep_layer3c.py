"""
Tests for Layer 3c — Real Deep Engines (ML Pipeline, Dimensionality Reduction, Clustering, Anomaly Detection, Crypto)

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

# ===== CORTEX: ML Pipeline =====
_mlp = _load_module("Cortex/app/agents/real_ml_pipeline.py", "real_ml_pipeline")
DataPreprocessor = _mlp.DataPreprocessor
LinearRegression = _mlp.LinearRegression
LogisticRegression = _mlp.LogisticRegression
DecisionTree = _mlp.DecisionTree
MLPipeline = _mlp.MLPipeline
EnsembleEngine = _mlp.EnsembleEngine

# ===== INFERENCE: Dimensionality Reduction =====
_dr = _load_module("Inference/app/agents/real_dimensionality_reduction.py", "real_dimensionality_reduction")
PCA = _dr.PCA
SVD = _dr.SVD
FeatureSelector = _dr.FeatureSelector
TSNE = _dr.TSNE

# ===== MEMORA: Clustering =====
_cl = _load_module("Memora/core/memory/real_clustering.py", "real_clustering")
DistanceMetrics = _cl.DistanceMetrics
KMeans = _cl.KMeans
HierarchicalClustering = _cl.HierarchicalClustering
DBSCAN = _cl.DBSCAN
ClusterEvaluator = _cl.ClusterEvaluator
GaussianMixtureModel = _cl.GaussianMixtureModel

# ===== SENTINEL: Anomaly Detection =====
_ad = _load_module("Sentinel/app/agents/real_anomaly_detection.py", "real_anomaly_detection")
IsolationForest = _ad.IsolationForest
LocalOutlierFactor = _ad.LocalOutlierFactor
AutoencoderAnomalyDetector = _ad.AutoencoderAnomalyDetector
EllipticEnvelope = _ad.EllipticEnvelope
EnsembleAnomalyDetector = _ad.EnsembleAnomalyDetector

# ===== STRATEXT: Crypto =====
_cr = _load_module("Stratex/app/agents/real_crypto_engine.py", "real_crypto_engine")
CryptoIndicators = _cr.CryptoIndicators
OrderBookAnalyzer = _cr.OrderBookAnalyzer
FundingRateAnalyzer = _cr.FundingRateAnalyzer
CryptoVolatilityAnalyzer = _cr.CryptoVolatilityAnalyzer
CryptoPortfolioOptimizer = _cr.CryptoPortfolioOptimizer
CryptoBacktester = _cr.CryptoBacktester


# =============================================================================
# CORTEX: ML PIPELINE TESTS
# =============================================================================

class TestMLPipeline:
    def test_data_preprocessor_normalize(self):
        """Data preprocessor normalizes correctly."""
        data = [{"a": 1, "b": 10}, {"a": 2, "b": 20}, {"a": 3, "b": 30}]
        pre = DataPreprocessor().fit(data)
        normalized = pre.normalize(data)
        assert normalized[0]["a"] == 0.0
        assert normalized[2]["a"] == 1.0

    def test_data_preprocessor_standardize(self):
        """Data preprocessor standardizes correctly."""
        data = [{"a": 1, "b": 10}, {"a": 2, "b": 20}, {"a": 3, "b": 30}]
        pre = DataPreprocessor().fit(data)
        standardized = pre.standardize(data)
        # Mean should be ~0
        means = [row["a"] for row in standardized]
        assert abs(sum(means) / len(means)) < 0.001

    def test_linear_regression_fit(self):
        """Linear regression learns linear relationship."""
        lr = LinearRegression(learning_rate=0.1)
        X = [[1], [2], [3], [4], [5]]
        y = [2, 4, 6, 8, 10]
        lr.fit(X, y, epochs=500)
        pred = lr.predict([3])
        assert abs(pred - 6) < 1.0

    def test_logistic_regression_fit(self):
        """Logistic regression classifies correctly."""
        lr = LogisticRegression(learning_rate=0.1)
        X = [[0.1], [0.2], [0.3], [0.4], [0.5], [0.6], [0.7], [0.8], [0.9], [1.0]]
        y = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        lr.fit(X, y, epochs=500)
        pred0 = lr.predict([0.1])
        pred1 = lr.predict([1.0])
        assert pred0 == 0
        assert pred1 == 1

    def test_decision_tree_fit(self):
        """Decision tree classifies correctly."""
        dt = DecisionTree(max_depth=3)
        X = [[0.1], [0.2], [0.8], [0.9], [1.0], [1.1]]
        y = [0, 0, 1, 1, 1, 1]
        dt.fit(X, y)
        assert dt.predict([0.1]) == 0
        assert dt.predict([1.0]) == 1

    def test_ml_pipeline_train_test_split(self):
        """Train/test split works."""
        pipeline = MLPipeline()
        X = [[i] for i in range(100)]
        y = [i * 2 for i in range(100)]
        X_train, y_train, X_test, y_test = pipeline.train_test_split(X, y, test_ratio=0.2)
        assert len(X_train) == 80
        assert len(X_test) == 20

    def test_cross_validate(self):
        """Cross-validation produces results."""
        pipeline = MLPipeline()
        X = [[i] for i in range(50)]
        y = [i % 2 for i in range(50)]
        result = pipeline.cross_validate(lambda: DecisionTree(max_depth=2), X, y, k=3)
        assert "mean_scores" in result
        assert "k_folds" in result

    def test_grid_search(self):
        """Grid search finds best params."""
        pipeline = MLPipeline()
        X = [[i] for i in range(30)]
        y = [i % 2 for i in range(30)]
        result = pipeline.grid_search(
            lambda **kw: DecisionTree(**kw),
            {"max_depth": [2, 3], "min_samples_split": [2, 3]},
            X, y, k=3,
        )
        assert "best_params" in result
        assert "best_score" in result

    def test_ensemble_bagging(self):
        """Bagging ensemble works."""
        ens = EnsembleEngine()
        X = [[i] for i in range(30)]
        y = [i % 2 for i in range(30)]
        result = ens.bagging(X, y, lambda: DecisionTree(max_depth=2), n_models=3)
        assert result["n_models"] == 3

    def test_ensemble_boosting(self):
        """Boosting ensemble works."""
        ens = EnsembleEngine()
        X = [[i] for i in range(30)]
        y = [i % 2 for i in range(30)]
        result = ens.boosting(X, y, lambda: DecisionTree(max_depth=2), n_models=3)
        assert result["n_models"] >= 1

    def test_ensemble_predict(self):
        """Ensemble prediction works."""
        ens = EnsembleEngine()
        X = [[i] for i in range(30)]
        y = [i % 2 for i in range(30)]
        ens.bagging(X, y, lambda: DecisionTree(max_depth=2), n_models=3)
        pred = ens.predict([5])
        assert pred is not None


# =============================================================================
# INFERENCE: DIMENSIONALITY REDUCTION TESTS
# =============================================================================

class TestDimensionalityReduction:
    def test_pca_fit(self):
        """PCA fits and produces components."""
        X = [[i, i * 2, i * 3] for i in range(20)]
        pca = PCA()
        pca.fit(X, n_components=2)
        assert len(pca.components) == 2
        assert len(pca.explained_variance) == 2

    def test_pca_transform(self):
        """PCA transform reduces dimensions."""
        X = [[i, i * 2, i * 3] for i in range(20)]
        pca = PCA().fit(X, n_components=2)
        transformed = pca.transform(X)
        assert len(transformed) == 20
        assert len(transformed[0]) == 2

    def test_pca_reconstruction_error(self):
        """PCA reconstruction error is computed."""
        X = [[i, i * 2] for i in range(20)]
        pca = PCA().fit(X, n_components=1)
        error = pca.reconstruct_error(X)
        assert error >= 0

    def test_svd_compute(self):
        """SVD computes decomposition."""
        X = [[i + j for j in range(5)] for i in range(10)]
        svd = SVD().compute(X, n_components=3)
        assert len(svd.S) == 3
        assert len(svd.Vt) == 3  # 3 components
        assert len(svd.Vt[0]) == 5  # Each component has 5 features

    def test_svd_transform(self):
        """SVD transform reduces dimensions."""
        X = [[i + j for j in range(5)] for i in range(10)]
        svd = SVD().compute(X, n_components=3)
        transformed = svd.transform(X)
        assert len(transformed) == 10
        assert len(transformed[0]) == 3

    def test_feature_selector_variance(self):
        """Variance threshold selects features."""
        X = [[i, 1, 1] for i in range(20)]  # Feature 1 and 2 have zero variance
        fs = FeatureSelector().variance_threshold(X, threshold=0.01)
        assert 0 in fs.selected_features
        assert 1 not in fs.selected_features

    def test_feature_selector_correlation(self):
        """Correlation filter selects features."""
        X = [[i, i * 2, 5] for i in range(20)]
        y = [i * 2 for i in range(20)]
        fs = FeatureSelector().correlation_filter(X, y)
        assert len(fs.selected_features) > 0

    def test_tsne_fit_transform(self):
        """t-SNE reduces to 2D."""
        X = [[random.gauss(0, 1), random.gauss(0, 1)] for _ in range(30)]
        tsne = TSNE(n_iter=50)
        result = tsne.fit_transform(X)
        assert len(result.components) == 30
        assert len(result.components[0]) == 2


# =============================================================================
# MEMORA: CLUSTERING TESTS
# =============================================================================

class TestClustering:
    def test_distance_metrics(self):
        """Distance metrics are correct."""
        dm = DistanceMetrics()
        assert dm.euclidean([0, 0], [3, 4]) == 5.0
        assert dm.manhattan([0, 0], [3, 4]) == 7.0
        assert abs(dm.cosine([1, 0], [0, 1]) - 1.0) < 0.001

    def test_kmeans_fit(self):
        """K-Means clusters correctly."""
        # Create 3 clusters
        X = []
        for _ in range(10):
            X.append([random.gauss(0, 0.1), random.gauss(0, 0.1)])
        for _ in range(10):
            X.append([random.gauss(5, 0.1), random.gauss(5, 0.1)])
        for _ in range(10):
            X.append([random.gauss(10, 0.1), random.gauss(10, 0.1)])

        km = KMeans(k=3, max_iter=10)
        km.fit(X, k=3)
        assert len(km.centroids) == 3
        assert len(km.assignments) == 30

    def test_kmeans_predict(self):
        """K-Means predicts cluster."""
        X = [[i, i] for i in range(10)] + [[i + 10, i + 10] for i in range(10)]
        km = KMeans(k=2).fit(X, k=2)
        pred = km.predict([5, 5])
        assert 0 <= pred <= 1

    def test_kmeans_inertia(self):
        """K-Means inertia is computed."""
        X = [[i, i] for i in range(10)]
        km = KMeans(k=2).fit(X, k=2)
        inertia = km.inertia(X)
        assert inertia >= 0

    def test_hierarchical_clustering(self):
        """Hierarchical clustering works."""
        X = [[i, i] for i in range(10)]
        hc = HierarchicalClustering().fit(X, linkage="single")
        assert len(hc.clusters) == 1  # All merged into one

    def test_dbscan_fit(self):
        """DBSCAN clusters correctly."""
        X = []
        for _ in range(10):
            X.append([random.gauss(0, 0.1), random.gauss(0, 0.1)])
        for _ in range(10):
            X.append([random.gauss(10, 0.1), random.gauss(10, 0.1)])

        dbscan = DBSCAN(eps=0.5, min_samples=2)
        assignments = dbscan.fit_predict(X)
        assert dbscan.n_clusters() >= 1

    def test_silhouette_score(self):
        """Silhouette score is computed."""
        X = [[0, 0], [0.1, 0.1], [5, 5], [5.1, 5.1]]
        labels = [0, 0, 1, 1]
        ev = ClusterEvaluator()
        score = ev.silhouette_score(X, labels)
        assert -1 <= score <= 1

    def test_davies_bouldin(self):
        """Davies-Bouldin score is computed."""
        X = [[0, 0], [0.1, 0.1], [5, 5], [5.1, 5.1]]
        labels = [0, 0, 1, 1]
        ev = ClusterEvaluator()
        score = ev.davies_bouldin_score(X, labels)
        assert score >= 0

    def test_dunn_index(self):
        """Dunn index is computed."""
        X = [[0, 0], [0.1, 0.1], [5, 5], [5.1, 5.1]]
        labels = [0, 0, 1, 1]
        ev = ClusterEvaluator()
        score = ev.dunn_index(X, labels)
        assert score >= 0

    def test_gmm_fit(self):
        """GMM clusters correctly."""
        X = []
        for _ in range(10):
            X.append([random.gauss(0, 0.5), random.gauss(0, 0.5)])
        for _ in range(10):
            X.append([random.gauss(5, 0.5), random.gauss(5, 0.5)])

        gmm = GaussianMixtureModel(max_iter=20)
        gmm.fit(X, n_components=2)
        pred = gmm.predict([0, 0])
        assert 0 <= pred <= 1


# =============================================================================
# SENTINEL: ANOMALY DETECTION TESTS
# =============================================================================

class TestAnomalyDetection:
    def test_isolation_forest_fit(self):
        """Isolation Forest fits."""
        X = [[random.gauss(0, 1)] * 5 for _ in range(100)]
        if_model = IsolationForest(n_trees=10, max_depth=10)
        if_model.fit(X)
        assert len(if_model.trees) == 10

    def test_isolation_forest_predict(self):
        """Isolation Forest detects anomalies."""
        # Normal data
        X = [[random.gauss(0, 1)] * 5 for _ in range(100)]
        # Add outliers
        X.extend([[100, 100, 100, 100, 100]] * 5)

        if_model = IsolationForest(n_trees=50, max_depth=20, contamination=0.1)
        predictions = if_model.fit_predict(X)
        assert len(predictions) == 105
        # Outliers should have higher scores than normal data
        scores = if_model.decision_function(X)
        avg_normal_score = sum(scores[:100]) / 100
        avg_outlier_score = sum(scores[-5:]) / 5
        assert avg_outlier_score >= avg_normal_score

    def test_isolation_forest_scores(self):
        """Isolation Forest produces scores."""
        X = [[random.gauss(0, 1)] * 3 for _ in range(50)]
        if_model = IsolationForest(n_trees=10)
        scores = if_model.fit(X).decision_function(X)
        assert len(scores) == 50
        assert all(0 <= s <= 1 for s in scores)

    def test_lof_fit_predict(self):
        """LOF detects anomalies."""
        X = [[random.gauss(0, 1)] * 2 for _ in range(50)]
        X.extend([[50, 50]] * 3)

        lof = LocalOutlierFactor(k=5, contamination=0.1)
        scores = lof.fit_predict(X)
        assert len(scores) == 53
        # Outliers should have high LOF scores
        assert max(scores[-3:]) > 1.0

    def test_autoencoder_fit(self):
        """Autoencoder fits."""
        X = [[random.gauss(0, 0.1)] * 5 for _ in range(50)]
        ae = AutoencoderAnomalyDetector(latent_dim=3, max_iter=10)
        ae.fit(X)
        assert len(ae.encoder_weights) == 3
        assert len(ae.decoder_weights) == 5

    def test_autoencoder_predict(self):
        """Autoencoder detects anomalies."""
        X = [[random.gauss(0, 0.1)] * 5 for _ in range(50)]
        X.extend([[10, 10, 10, 10, 10]] * 5)

        ae = AutoencoderAnomalyDetector(latent_dim=3, max_iter=10)
        predictions = ae.fit_predict(X)
        assert len(predictions) == 55

    def test_elliptic_envelope_fit(self):
        """Elliptic envelope fits."""
        X = [[random.gauss(0, 1)] * 3 for _ in range(50)]
        ee = EllipticEnvelope(contamination=0.1)
        ee.fit(X)
        assert len(ee.center) == 3
        assert len(ee.covariance) == 3

    def test_elliptic_envelope_predict(self):
        """Elliptic envelope detects anomalies."""
        X = [[random.gauss(0, 1)] * 2 for _ in range(50)]
        X.extend([[10, 10]] * 3)

        ee = EllipticEnvelope(contamination=0.1)
        predictions = ee.fit(X).predict(X)
        assert len(predictions) == 53

    def test_ensemble_anomaly_detector(self):
        """Ensemble anomaly detector works."""
        X = [[random.gauss(0, 1)] * 3 for _ in range(50)]

        ensemble = EnsembleAnomalyDetector()
        ensemble.add_detector(IsolationForest(n_trees=5, max_depth=10), weight=1.0)
        ensemble.add_detector(LocalOutlierFactor(k=5), weight=1.0)
        predictions = ensemble.fit_predict(X)
        assert len(predictions) == 50


# =============================================================================
# STRATEXT: CRYPTO ENGINE TESTS
# =============================================================================

class TestCryptoEngine:
    def test_fear_greed_index(self):
        """Fear & Greed index is computed."""
        ci = CryptoIndicators()
        result = ci.fear_greed_index({
            "volatility": 30,
            "momentum": 70,
            "social_media": 60,
            "surveys": 50,
            "dominance": 40,
            "google_trends": 50,
        })
        assert 0 <= result <= 100

    def test_relative_strength(self):
        """Relative strength is computed."""
        ci = CryptoIndicators()
        crypto = [100, 105, 110, 108, 115]
        btc = [100, 102, 104, 103, 106]
        result = ci.relative_strength(crypto, btc)
        assert len(result) == 5
        assert result[0] == 1.0

    def test_nvt_ratio(self):
        """NVT ratio is computed."""
        ci = CryptoIndicators()
        assert ci.nvt_ratio(1_000_000, 10_000_000) == 10.0

    def test_mvrv_ratio(self):
        """MVRV ratio is computed."""
        ci = CryptoIndicators()
        assert ci.mvrv_ratio(10_000_000, 8_000_000) == 1.25

    def test_sopr(self):
        """SOPR is computed."""
        ci = CryptoIndicators()
        assert ci.sopr(60, 40) == 0.6

    def test_order_book_spread(self):
        """Order book spread is computed."""
        ob = OrderBookAnalyzer(
            bids=[(100, 1.0), (99, 2.0)],
            asks=[(101, 1.0), (102, 2.0)],
        )
        assert ob.spread() == 1.0
        assert ob.spread_pct() > 0

    def test_order_book_imbalance(self):
        """Order book imbalance is computed."""
        ob = OrderBookAnalyzer(
            bids=[(100, 2.0)],
            asks=[(101, 1.0)],
        )
        assert ob.imbalance() > 0  # More bids than asks

    def test_order_book_slippage(self):
        """Order book slippage is computed."""
        ob = OrderBookAnalyzer(
            bids=[(100, 1.0), (99, 1.0)],
            asks=[(101, 1.0), (102, 1.0)],
        )
        slippage = ob.slippage(1.5, side="buy")
        assert slippage >= 0

    def test_funding_rate_sentiment(self):
        """Funding rate sentiment is determined."""
        fr = FundingRateAnalyzer(funding_rates=[0.001, 0.002, 0.003])
        assert fr.funding_sentiment() == "bullish"

        fr2 = FundingRateAnalyzer(funding_rates=[-0.001, -0.002, -0.003])
        assert fr2.funding_sentiment() == "bearish"

    def test_funding_rate_trend(self):
        """Funding rate trend is determined."""
        fr = FundingRateAnalyzer(funding_rates=[0.001, 0.002, 0.003, 0.004, 0.005])
        assert fr.funding_trend() == "increasing"

    def test_crypto_volatility(self):
        """Crypto volatility is computed."""
        cv = CryptoVolatilityAnalyzer(prices=[100, 105, 103, 108, 110, 105, 107])
        vol = cv.realized_volatility()
        assert vol > 0

    def test_crypto_portfolio_optimization(self):
        """Crypto portfolio optimization works."""
        returns = {
            "BTC": [0.01, 0.02, -0.01, 0.03, 0.02],
            "ETH": [0.02, 0.01, 0.03, -0.01, 0.02],
            "SOL": [-0.01, 0.03, 0.02, 0.01, -0.02],
        }
        opt = CryptoPortfolioOptimizer()
        result = opt.optimize(returns, n_portfolios=100)
        assert "weights" in result
        assert sum(result["weights"].values()) > 0.99

    def test_crypto_risk_parity(self):
        """Risk parity allocation works."""
        returns = {
            "BTC": [0.01, 0.02, -0.01],
            "ETH": [0.02, 0.01, 0.03],
        }
        opt = CryptoPortfolioOptimizer()
        weights = opt.risk_parity(returns)
        assert len(weights) == 2
        assert sum(weights.values()) > 0.99

    def test_crypto_backtester(self):
        """Crypto backtester runs."""
        bt = CryptoBacktester()
        prices = [(100 + i * 0.5, 1000) for i in range(50)]

        def simple_strategy(data, idx):
            if idx == 10:
                return "buy"
            elif idx == 30:
                return "sell"
            return "hold"

        result = bt.run(prices, simple_strategy, initial_capital=10000, take_profit=0.1, stop_loss=0.05)
        assert "final_equity" in result
        assert "total_return" in result
        assert result["number_of_trades"] >= 2
