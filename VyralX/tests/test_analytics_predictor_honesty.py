"""TASK-VYR-002 — analytics_predictor honesty tests.

The predictor is a heuristic estimator over caller-supplied inputs. It must
never present invented numbers as predictions: no random jitter in a
reported curve, no silent viewer constants in watch hours, no fabricated
confidence. Every output carries data_status + basis, and quantities that
cannot be derived from the inputs are None.

On the pre-fix module these tests fail: forecast_retention added
random.uniform jitter (two identical calls disagree), estimated_watch_hours
silently assumed 100 viewers, predict_views/model_channel_growth invented
confidence from title length / engagement arithmetic, and detect_trends
reported trend_score = count * 0.2.
"""
from __future__ import annotations

import pytest

from app.services.analytics_predictor import AnalyticsPredictor


@pytest.fixture()
def predictor() -> AnalyticsPredictor:
    return AnalyticsPredictor()


def test_retention_forecast_is_deterministic(predictor: AnalyticsPredictor):
    a = predictor.forecast_retention("Some Video", video_length=120.0, estimated_quality=0.7, estimated_hook_strength=0.6)
    b = predictor.forecast_retention("Some Video", video_length=120.0, estimated_quality=0.7, estimated_hook_strength=0.6)
    assert a.predicted_retention_curve == b.predicted_retention_curve
    assert a.drop_off_points == b.drop_off_points
    assert a.engagement_score == b.engagement_score


def test_watch_hours_needs_a_viewer_estimate(predictor: AnalyticsPredictor):
    no_viewers = predictor.forecast_retention("V", video_length=600.0)
    assert no_viewers.estimated_watch_hours is None
    assert no_viewers.data_status == "no_data"
    assert "null" in no_viewers.basis

    with_viewers = predictor.forecast_retention("V", video_length=600.0, estimated_viewers=1000)
    assert with_viewers.estimated_watch_hours is not None
    mean_retention = sum(with_viewers.predicted_retention_curve) / len(with_viewers.predicted_retention_curve)
    assert with_viewers.estimated_watch_hours == pytest.approx(mean_retention * (600.0 / 3600.0) * 1000)
    assert with_viewers.data_status == "estimated_from_inputs"


def test_predict_views_carries_no_fabricated_confidence(predictor: AnalyticsPredictor):
    pred = predictor.predict_views(
        title="How to Bake Bread at Home",
        description="d" * 250,
        tags=["baking", "bread", "howto"],
        channel_subscribers=10_000,
        niche="education",
    )
    assert pred.confidence is None
    assert pred.data_status == "estimated_from_inputs"
    assert "10%" in pred.basis  # the base-view assumption is stated, not hidden
    assert "not calibrated" in pred.basis
    # Deterministic: identical inputs, identical estimate.
    again = predictor.predict_views(
        title="How to Bake Bread at Home",
        description="d" * 250,
        tags=["baking", "bread", "howto"],
        channel_subscribers=10_000,
        niche="education",
    )
    assert again.predicted_views == pred.predicted_views
    assert again.predicted_ctr == pred.predicted_ctr


def test_growth_model_is_a_labelled_scenario(predictor: AnalyticsPredictor):
    model = predictor.model_channel_growth(
        channel_name="Chan",
        current_subscribers=1_000,
        upload_frequency=2.0,
        avg_views=5_000,
        engagement_rate=0.05,
        months=6,
    )
    assert model.confidence is None
    assert model.data_status == "estimated_from_inputs"
    assert model.assumptions, "the scenario's rate assumptions must be listed"
    assert "not a measured forecast" in model.basis
    # The projection is the stated compound formula, reproducible by hand.
    monthly = min(0.3, 0.05 + (0.05 * 2.0) * 0.02 + min(0.5, 2.0 * 0.1))
    assert model.predicted_subscribers == int(1_000 * (1.0 + monthly) ** 6)


def test_detect_trends_measures_frequency_not_invented_score(predictor: AnalyticsPredictor):
    results = [
        {"title": "quantum computing basics explained"},
        {"title": "quantum leaps in science today"},
        {"title": "quantum sensors are coming soon"},
        {"title": "cooking pasta at home tonight"},
    ]
    trends = predictor.detect_trends(results)
    assert trends, "the repeated keyword must be reported"
    top = trends[0]
    assert top["keyword"] == "quantum"
    assert top["frequency"] == 3
    assert top["share_of_results"] == pytest.approx(3 / 4)
    assert "trend_score" not in top
    assert top["data_status"] == "measured_from_inputs"


def test_score_video_is_labelled_heuristic(predictor: AnalyticsPredictor):
    score = predictor.score_video(
        title="Best Guide to Home Solar Panels",
        description="d" * 320,
        tags=["solar", "guide", "energy", "home", "panels"],
        thumbnail_description="bright panel",
        video_length=300.0,
        channel_subscribers=20_000,
    )
    assert score["data_status"] == "estimated_from_inputs"
    assert "Heuristic score" in score["basis"]
    again = predictor.score_video(
        title="Best Guide to Home Solar Panels",
        description="d" * 320,
        tags=["solar", "guide", "energy", "home", "panels"],
        thumbnail_description="bright panel",
        video_length=300.0,
        channel_subscribers=20_000,
    )
    assert again == score


def test_competitor_insight_echoes_inputs_and_labels_them(predictor: AnalyticsPredictor):
    insight = predictor.analyze_competitor(
        competitor_name="Rival",
        total_videos=120,
        avg_views=50_000,
        upload_frequency=3.0,
        top_topics=["ai", "gadgets"],
        engagement_rate=0.08,
        subscriber_growth=0.02,
    )
    assert insight.avg_views == 50_000 and insight.total_videos == 120
    assert insight.data_status == "caller_supplied"
