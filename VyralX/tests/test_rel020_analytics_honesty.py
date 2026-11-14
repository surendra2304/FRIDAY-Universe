"""TASK-REL-020 — VyralX analytics honesty tests.

The analytics engines must never serve numbers derived from md5 hash
seeds (or hardcoded constants) as if they were measurements. Every
formerly fabricated metric is either computed from real stored /
caller-supplied inputs (and labelled), or None with an honest
data_status/data_note in the payload.
"""
from __future__ import annotations

from app.services.audience_growth_predictor import AudienceGrowthPredictor
from app.services.content_calendar_manager import ContentCalendarManager
from app.services.creator_collaboration_manager import CreatorCollaborationManager
from app.services.creator_monetization_engine import CreatorMonetizationEngine
from app.services.full_pipeline_engine import FullPipelineEngine
from app.services.multilingual_content_translator import MultilingualContentTranslator
from app.services.thumbnail_optimizer import ThumbnailOptimizer
from app.services.video_analytics_dashboard import VideoAnalyticsDashboard


def test_calendar_post_estimates_are_no_data():
    cm = ContentCalendarManager()
    cal = cm.create_calendar("C1")
    post = cm.schedule_post(cal.calendar_id, "Hello World")
    assert post.estimated_reach is None and post.estimated_engagement is None
    assert post.data_status == "no_data"
    forecast = cm.forecast_performance(post.post_id)
    assert forecast.estimated_views is None and forecast.forecast_confidence is None
    plan = cm.create_distribution_plan(post.post_id, ["youtube"])
    assert plan.estimated_total_reach is None
    opt = cm.optimize_schedule(cal.calendar_id)
    assert opt.estimated_reach_increase is None and opt.confidence is None


def test_calendar_pipeline_counts_real_posts():
    cm = ContentCalendarManager()
    cal = cm.create_calendar("C1")
    cm.schedule_post(cal.calendar_id, "One")
    cm.schedule_post(cal.calendar_id, "Two")
    pipe = cm.create_pipeline(cal.calendar_id)
    assert pipe.total_items == 2
    assert pipe.stages["scheduled"] == 2
    assert pipe.average_cycle_time_hours is None  # was a constant 48.0


def test_growth_forecast_is_no_data_without_history():
    ag = AudienceGrowthPredictor()
    f = ag.forecast_growth("youtube", 5000)
    assert f.projected_total is None and f.viral_coefficient is None
    assert f.data_status == "no_data"
    churn = ag.predict_churn("youtube")
    assert churn.predicted_churn_rate is None and churn.high_risk_count is None
    rec = ag.generate_recommendation("youtube")
    assert rec.content_type is None and rec.expected_growth_impact is None
    assert "highest engagement" not in rec.rationale  # fabricated claim removed
    strategy = ag.create_strategy("youtube")
    assert strategy.expected_roi is None


def test_churn_from_real_cohort_inputs():
    ag = AudienceGrowthPredictor()
    cohort = ag.create_cohort("jan", 1000, [1.0, 0.5])
    assert cohort.current_size == 500 and cohort.churn_rate == 0.5
    churn = ag.predict_churn("youtube", cohort.cohort_id)
    assert churn.predicted_churn_rate == 0.5
    assert churn.data_status == "estimated_from_inputs"
    empty = ag.create_cohort("feb", 1000)
    assert empty.churn_rate is None and empty.data_status == "no_data"


def test_monetization_stream_growth_is_no_data_forecast_labelled():
    me = CreatorMonetizationEngine()
    stream = me.add_revenue_stream("cr1", "ads", "youtube", 10.0)
    assert stream.earnings_week == 70.0 and stream.earnings_month == 300.0
    assert stream.growth_rate is None
    match = me.match_sponsor("cr1", "Acme", "tech")
    assert match.match_score is None and match.estimated_value is None
    forecast = me.forecast_earnings("cr1", 30)
    # (10/day) * 30 days * 1.1 compounding assumption = 330.0, labelled.
    assert forecast.projected_earnings == 330.0
    assert forecast.growth_projection is None
    assert forecast.data_status == "estimated_from_inputs"
    assert me.get_report()["avg_growth_rate"] is None


def test_pipeline_never_fabricates_a_published_url():
    fp = FullPipelineEngine()
    ideas = fp.discover_topics("tech", 3)
    assert all(i.estimated_views is None and i.viral_potential is None for i in ideas)
    assert fp.select_idea("viral_potential") is ideas[0]  # unranked fallback
    task = fp.create_pipeline("My Topic")
    result = fp.execute_pipeline(task.task_id)
    assert result["published_url"] == ""
    assert result["publication_status"] == "not_published"
    report = fp.get_quality_report(task.video_id)
    assert report.estimated_views is None
    assert report.factors["completeness"] == 1.0


def test_localization_report_is_no_data():
    tr = MultilingualContentTranslator()
    report = tr.generate_localization_report("vid1")
    assert report.overall_score is None and report.translation_accuracy is None
    assert report.issues == [] and report.data_status == "no_data"
    segs = tr.add_subtitles("vid1", "en", [{"start_time_ms": 0, "end_time_ms": 1, "text": "hi"}])
    assert segs[0].confidence is None  # was a constant 0.7


def test_video_analytics_only_real_arithmetic_is_served():
    va = VideoAnalyticsDashboard()
    m = va.track_video("v1", "T", views=1000, likes=50, shares=10, comments=5)
    assert m.engagement_rate == 6.5  # (50+10+5)/1000*100 from supplied counts
    assert m.retention_rate is None and m.ctr is None and m.virality_score is None
    demo = va.analyze_demographics("v1")
    assert demo.age_distribution == {} and demo.unique_viewers is None
    curve = va.generate_retention_curve("v1")
    assert curve.segments == [] and curve.avg_retention is None
    virality = va.analyze_virality("v1")
    assert virality.sharing_rate == 0.01 and virality.predicted_views is None
    bench = va.benchmark_competitively("v1")
    assert bench.percentile_rank is None and bench.avg_views_in_group is None


def test_creator_rating_is_no_data():
    cc = CreatorCollaborationManager()
    creator = cc.register_creator("Bob", "youtube", "tech", 10000)
    assert creator.rating is None and creator.data_status == "no_data"


def test_thumbnail_significance_is_a_real_z_test():
    to = ThumbnailOptimizer()
    v1 = to.create_variant("vid", "a")
    v2 = to.create_variant("vid", "b")
    test_id = to.start_ab_test("vid", [v1, v2])
    empty = to.conclude_test(test_id)
    assert empty.winner_id == "" and empty.significance is None  # was constant 0.95

    v3 = to.create_variant("vid", "c")
    v4 = to.create_variant("vid", "d")
    test2 = to.start_ab_test("vid", [v3, v4])
    for _ in range(100):
        to.record_impression(v3, True)
        to.record_impression(v3, False)
        to.record_impression(v4, False)
    for _ in range(10):
        to.record_impression(v4, True)
    for _ in range(90):
        to.record_impression(v4, False)
    result = to.conclude_test(test2)
    assert result.winner_id == v3
    assert result.significance is not None and result.significance > 0.99
    pred = to.predict_ctr("vid", "Some title")
    assert pred.confidence is None and pred.data_status == "estimated_from_inputs"
