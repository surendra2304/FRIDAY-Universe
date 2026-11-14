"""TASK-REL-020 — Cortex analytics honesty tests.

The deep-module analytics engines must never serve numbers derived from
md5 hash seeds (or hardcoded constants) as if they were measurements.
For every formerly fabricated metric: it is either computed from real
stored/caller-supplied inputs (and labelled), or it is None with an
honest data_status/data_note in the payload.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api", "src")))

from cortex_api.competitive_intelligence import CompetitiveIntelligenceEngine
from cortex_api.decision_recommendation_system import DecisionRecommendationSystem
from cortex_api.marketing_platform_integrator import MarketingPlatformIntegrator
from cortex_api.multi_channel_attribution import MultiChannelAttributionModeler
from cortex_api.predictive_demand_forecaster import PredictiveDemandForecaster


def test_email_campaign_metrics_are_no_data_not_md5():
    mi = MarketingPlatformIntegrator()
    c = mi.create_email_campaign("N", "S", "B", "aud")
    sent = mi.send_email_campaign(c.campaign_id)
    assert sent.open_rate is None
    assert sent.click_rate is None
    assert sent.bounce_rate is None
    assert sent.data_status == "no_data"
    assert sent.data_note


def test_social_and_ad_metrics_are_no_data():
    mi = MarketingPlatformIntegrator()
    p = mi.publish_social_post(mi.create_social_post("twitter", "hi").post_id)
    assert p.likes is None and p.reach is None and p.data_status == "no_data"
    a = mi.activate_ad_campaign(mi.create_ad_campaign("google_ads", "Ad", 100, 10).campaign_id)
    assert a.impressions is None and a.roas is None and a.data_status == "no_data"


def test_competitive_intelligence_no_hash_metrics():
    ci = CompetitiveIntelligenceEngine()
    comp = ci.add_competitor("Acme")
    pa = ci.analyze_pricing(comp.competitor_id, "Widget", 120.0, 100.0)
    # Input-derived fields stay real; the hash-derived change is gone.
    assert pa.price_change_pct is None
    assert pa.value_score == 120.0
    assert pa.compared_to_us == 20.0
    ms = ci.estimate_market_share(comp.competitor_id, 1_000_000)
    assert ms.estimated_share is None and ms.confidence is None and ms.trend == "unknown"
    swot = ci.generate_swot(comp.competitor_id)
    assert swot.overall_score is None and swot.data_status == "no_data"


def test_demand_forecast_is_pure_trend_of_supplied_series():
    df = PredictiveDemandForecaster()
    sr = df.add_demand_series("Widget", "tools", [100.0, 110.0, 120.0, 130.0])
    f = df.forecast_demand(sr.series_id)
    # trend = (130-100)/3/130 = 0.076923...; first prediction = 130*(1+trend)
    assert abs(f.predictions[0] - 140.0) < 1e-6
    assert f.rmse is None and f.mape is None
    assert f.model == "naive_trend_extrapolation"
    assert f.data_status == "estimated_from_inputs"
    # Deterministic: same series -> identical predictions (no hash jitter).
    f2 = df.forecast_demand(sr.series_id)
    assert f.predictions == f2.predictions


def test_demand_forecast_empty_series_is_no_data():
    df = PredictiveDemandForecaster()
    sr = df.add_demand_series("Empty", "tools", [])
    f = df.forecast_demand(sr.series_id)
    assert f.predictions == [] and f.data_status == "no_data"


def test_ensemble_forecast_is_honest_no_data():
    df = PredictiveDemandForecaster()
    sr = df.add_demand_series("Widget", "tools", [10.0, 20.0])
    e = df.ensemble_forecast(sr.series_id)
    assert e.predictions == {} and e.models == []
    assert e.consensus is None and e.agreement is None and e.confidence is None
    assert e.data_status == "no_data"


def test_markov_removal_effects_computed_from_journeys():
    m = MultiChannelAttributionModeler()
    m.add_journey("c1", [{"channel": "A"}, {"channel": "B"}], conversion_value=100.0)
    m.add_journey("c2", [{"channel": "A"}, {"channel": "B"}], conversion_value=100.0)
    m.add_journey("c3", [{"channel": "A"}, {"channel": "B"}], conversion_value=50.0)
    m.add_journey("c4", [{"channel": "A"}], conversion_value=0.0)
    m.add_journey("c5", [{"channel": "B"}], conversion_value=10.0)
    g = m.build_markov_graph()
    assert g.conversion_rate == 0.8  # 4 of 5 journeys carry a conversion value
    # Removing B loses every conversion path; removing A keeps c5's path.
    assert g.removal_effects["B"] == 1.0
    assert abs(g.removal_effects["A"] - 0.75) < 1e-9
    result = m.attribute("data_driven")
    total_dd = sum(c.data_driven_credit for c in result.channel_contributions)
    assert abs(total_dd - 260.0) < 1e-6  # sums to total converted value


def test_markov_graph_without_journeys_is_no_data():
    g = MultiChannelAttributionModeler().build_markov_graph()
    assert g.conversion_rate is None and g.removal_effects == {}
    assert g.data_status == "no_data"


def test_uncertainty_computed_from_sensitivity_not_hash():
    ds = DecisionRecommendationSystem()
    crit = ds.add_criterion("cost", 1.0, "minimize")
    a1 = ds.add_alternative("A1", risk_score=0.2, return_projection=0.9)
    a2 = ds.add_alternative("A2", risk_score=0.8, return_projection=0.4)
    ds.score_alternative(a1.alternative_id, crit.criterion_id, 0.9)
    ds.score_alternative(a2.alternative_id, crit.criterion_id, 0.3)
    rec = ds.recommend("Pick one")
    ua = ds.analyze_uncertainty(rec.recommendation_id)
    assert ua.uncertainty_level is not None and 0.0 <= ua.uncertainty_level <= 1.0
    assert ua.data_status == "estimated_from_inputs"
    assert ua.risk_adjusted_score is not None
    # Report must not crash once recommendations exist (avg_risk_level fix).
    report = ds.get_report()
    assert report["total_recommendations"] == 1
    assert report["recent_uncertainty"][0]["uncertainty"] == ua.uncertainty_level
