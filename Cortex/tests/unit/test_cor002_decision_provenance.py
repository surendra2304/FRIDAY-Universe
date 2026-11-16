"""TASK-COR-002 — Cortex decision provenance.

Production audit 2026-11-15 (deployed code sha256-identical to the audit
base) sampled 13 decision/recommendation outputs: 0 of the 11 delivered
outputs were fully traceable. Proven live defects locked by these tests:

1. decision/recommend computed a ranking + confidence from a matrix in
   which 3 of 4 score cells were never supplied (silent 0.5 defaults) and
   disclosed nothing. COR-002 first required the output to disclose the
   defaults (provenance.defaults_applied, data_status); TASK-REL-047
   (lead-coordinator ruling, 2026-11-16) then abolished the defaults
   themselves — an incomplete matrix is now rejected with HTTP 422 naming
   every missing cell, and the refusal is stored as a decision record
   (outcome "rejected_incomplete"). The disclosure machinery remains on
   every record the engine does produce.
2. The DEFAULT recommendation strategy (hybrid) HTTP 500'd for every user
   with a profile: hybrid_recommend bound top_k*2 to content_filter's
   `all_items` parameter positionally.
3. POST /leads/score HTTP 500'd on every production call: the persisted
   LeadScoreHistoryModel row carried no id and Oracle rejects a NULL
   primary key (ORA-01400). The persisted row must carry a non-null id.
4. Lead CLV from an empty payload returned a bare dollar figure computed
   entirely from route defaults; the defaults must be disclosed.
5. Predictive confidences (demand, trend, behavior buckets, forecast
   "accuracy") stated no basis; each output must now carry one.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

import cortex_api.decision_recommendation_system as drs_module
from cortex_api.decision_recommendation_system import DecisionRecommendationSystem
from cortex_api.enhanced_crm import EnhancedCRM
from cortex_api.predictive_analytics import PredictiveAnalytics
from cortex_api.recommendation_engine import RecommendationEngine

from tests.conftest import auth_headers, friday_headers


# ── 1. Decision recommendation provenance ───────────────────────────────────


def _partial_matrix_system() -> DecisionRecommendationSystem:
    system = DecisionRecommendationSystem()
    cost = system.add_criterion("cost", weight=2.0, direction="minimize")
    system.add_criterion("quality", weight=1.0, direction="maximize")
    alt_a = system.add_alternative("A", risk_score=0.3, return_projection=0.8)
    system.add_alternative("B", risk_score=0.6, return_projection=0.4)
    # Only ONE of the four matrix cells is ever supplied.
    system.score_alternative(alt_a.alternative_id, cost.criterion_id, 0.2)
    return system


def test_recommend_rejects_incomplete_matrix_and_logs_rejection():
    """TASK-REL-047 ruling (2026-11-16) supersedes the COR-002-era
    default-and-disclose behaviour for this path: the 1-of-4-cells matrix
    below used to return a confident recommendation computed from three
    invented 0.5 defaults (disclosed in provenance after the fact). It is
    now refused with HTTP 422 naming every missing cell — and the refusal
    is appended to the decision log as a record with outcome
    "rejected_incomplete" (TASK-COR-003), so the log shows the request
    happened without fabricating a decision."""
    system = _partial_matrix_system()
    with pytest.raises(HTTPException) as excinfo:
        system.recommend("choose vendor")
    assert excinfo.value.status_code == 422
    detail = excinfo.value.detail
    # Every missing cell is named; the one supplied cell is not.
    assert "A / quality" in detail
    assert "B / cost" in detail
    assert "B / quality" in detail
    assert "A / cost" not in detail

    (record,) = system._recommendations
    assert record.outcome["status"] == "rejected_incomplete"
    assert record.outcome["missing_cells"] == [
        "A / quality", "B / cost", "B / quality"]
    assert record.best_alternative == ""
    assert record.alternatives_ranking == []
    assert record.created_at > 0
    # Nothing was defaulted: the refusal applied no invented inputs, and
    # it states no confidence — there is no decision to be confident about.
    prov = record.provenance
    assert prov, "rejection record must carry a provenance block"
    assert prov["defaults_applied"] == []
    assert prov["data_status"] == "incomplete_inputs"
    assert prov["confidence"] is None
    assert prov["generated_at"]
    supplied = {i["name"] for i in prov["inputs_used"] if i["source"] == "caller_supplied"}
    assert supplied == {"score[A][cost]"}


def test_recommend_complete_matrix_is_complete_inputs():
    system = DecisionRecommendationSystem()
    c1 = system.add_criterion("cost", weight=1.0)
    a1 = system.add_alternative("A")
    a2 = system.add_alternative("B")
    system.score_alternative(a1.alternative_id, c1.criterion_id, 0.9)
    system.score_alternative(a2.alternative_id, c1.criterion_id, 0.1)
    rec = system.recommend("full matrix")
    assert rec.provenance["data_status"] == "complete_inputs"
    assert rec.provenance["defaults_applied"] == []


def test_decision_routes_validate_payload_and_return_provenance(api_client, monkeypatch):
    headers = friday_headers(monkeypatch)
    # Isolate the decision router's module-level singleton: the REL-047
    # gate makes leftover partial state from other tests fatal (it used to
    # be silently defaulted), so this test runs against a fresh system.
    monkeypatch.setattr(drs_module, "decision_system", DecisionRecommendationSystem())
    # Missing criterion_id used to be a KeyError 500 (8/8 production requests).
    bad = api_client.post(
        "/api/v1/cortex/decision/alternatives/whatever/score",
        json={"score": 0.5}, headers=headers,
    )
    assert bad.status_code == 400
    assert "criterion_id" in bad.json()["detail"]

    crit = api_client.post(
        "/api/v1/cortex/decision/criteria",
        json={"name": "cor002_cost", "weight": 2.0, "direction": "minimize"},
        headers=headers,
    ).json()
    quality = api_client.post(
        "/api/v1/cortex/decision/criteria",
        json={"name": "cor002_quality", "weight": 1.0, "direction": "maximize"},
        headers=headers,
    ).json()
    alt = api_client.post(
        "/api/v1/cortex/decision/alternatives",
        json={"name": "cor002_A", "risk_score": 0.3, "return_projection": 0.8},
        headers=headers,
    ).json()
    scored = api_client.post(
        f"/api/v1/cortex/decision/alternatives/{alt['alternative_id']}/score",
        json={"criterion_id": crit["criterion_id"], "score": 0.2},
        headers=headers,
    )
    assert scored.status_code == 200
    # TASK-REL-047 ruling: with cor002_quality still unscored the matrix is
    # incomplete, so the route refuses with 422 naming the missing cell.
    # (The COR-002-era behaviour returned 200 with the invented 0.5 default
    # disclosed in provenance.)
    rec = api_client.post(
        "/api/v1/cortex/decision/recommend",
        json={"problem_statement": "cor002 route check"},
        headers=headers,
    )
    assert rec.status_code == 422
    assert "cor002_A / cor002_quality" in rec.json()["detail"]
    # Complete the matrix -> the same call succeeds, with provenance.
    scored = api_client.post(
        f"/api/v1/cortex/decision/alternatives/{alt['alternative_id']}/score",
        json={"criterion_id": quality["criterion_id"], "score": 0.7},
        headers=headers,
    )
    assert scored.status_code == 200
    rec = api_client.post(
        "/api/v1/cortex/decision/recommend",
        json={"problem_statement": "cor002 route check"},
        headers=headers,
    )
    assert rec.status_code == 200
    body = rec.json()
    assert body["provenance"]["data_status"] == "complete_inputs"
    assert body["alternatives_ranking"], "route must return the ranking it decided from"


# ── 2. Recommendation engine: hybrid fix + provenance ───────────────────────


def _seeded_engine() -> RecommendationEngine:
    engine = RecommendationEngine()
    engine.update_user_profile("u1", "item_x", 1.0, "content", {"tech": 0.9, "news": 0.2})
    engine.update_user_profile("u2", "item_x", 1.0, "content", {"tech": 0.9, "news": 0.2})
    engine.update_user_profile("u2", "item_y", 1.0, "content", {"tech": 0.8, "sports": 0.7})
    return engine


def test_hybrid_recommend_does_not_crash():
    """Regression: hybrid (the default strategy) raised AttributeError —
    top_k*2 was bound to content_filter's all_items parameter."""
    result = _seeded_engine().hybrid_recommend("u1", top_k=5)
    assert [r.item_id for r in result.recommendations] == ["item_y"]


def test_recommendation_provenance_states_basis_and_inputs():
    prov = _seeded_engine().recommendation_provenance("u1", "collaborative")
    assert prov["data_status"] == "complete_inputs"
    inputs = {i["name"]: i["value"] for i in prov["inputs_used"]}
    assert inputs["user_history_items"] == 1
    assert inputs["similar_users_contributing"] == 1
    assert "NOT a calibrated probability" in prov["confidence_basis"]


def test_recommendation_provenance_unknown_user_is_no_data():
    prov = RecommendationEngine().recommendation_provenance("ghost", "hybrid")
    assert prov["data_status"] == "no_data"


def test_recommendations_route_returns_provenance(api_client):
    headers = auth_headers(role="cortex_operator")
    api_client.post("/api/v1/recommendations/track", headers=headers, json={
        "user_id": "cor002_u1", "item_id": "cor002_x", "rating": 1.0,
        "item_features": {"tech": 0.9}})
    api_client.post("/api/v1/recommendations/track", headers=headers, json={
        "user_id": "cor002_u2", "item_id": "cor002_x", "rating": 1.0,
        "item_features": {"tech": 0.9}})
    api_client.post("/api/v1/recommendations/track", headers=headers, json={
        "user_id": "cor002_u2", "item_id": "cor002_y", "rating": 1.0,
        "item_features": {"tech": 0.8}})
    resp = api_client.get("/api/v1/recommendations/cor002_u1?strategy=hybrid",
                          headers=auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recommendations"][0]["item_id"] == "cor002_y"
    assert body["provenance"]["data_status"] == "complete_inputs"


# ── 3/4. Lead scoring: persisted id + provenance ─────────────────────────────


def test_lead_score_provenance_marks_unsupplied_inputs():
    crm = EnhancedCRM()
    score = crm.score_lead(
        "lead_min", website_visits=10,
        supplied_fields={"lead_id", "website_visits"},
    )
    prov = score.provenance
    assert prov["data_status"] == "partial_inputs_defaulted"
    assert "industry" in prov["defaults_applied"]
    assert "source" in prov["defaults_applied"]
    assert "website_visits" not in prov["defaults_applied"]
    assert "NOT measured revenue" in prov["confidence_basis"]


def test_lead_score_route_persists_row_with_id(api_client, session_factory):
    resp = api_client.post(
        "/api/v1/leads/score", headers=auth_headers(role="cortex_operator"),
        json={"lead_id": "cor002_lead", "website_visits": 10},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provenance"]["data_status"] == "partial_inputs_defaulted"

    from cortex_api.db_models import LeadScoreHistoryModel
    from sqlalchemy import select

    async def _rows():
        async with session_factory() as session:
            result = await session.execute(
                select(LeadScoreHistoryModel).where(
                    LeadScoreHistoryModel.lead_id == "cor002_lead"))
            return result.scalars().all()

    rows = asyncio.run(_rows())
    assert len(rows) == 1
    # Oracle rejects a NULL primary key (ORA-01400) — the production 500.
    assert rows[0].id


def test_clv_route_discloses_route_defaults(api_client):
    headers = auth_headers(role="cortex_operator")
    api_client.post("/api/v1/leads/score", headers=headers,
                    json={"lead_id": "cor002_clv_lead", "website_visits": 10})
    resp = api_client.post("/api/v1/leads/cor002_clv_lead/clv",
                           headers=headers, json={})
    assert resp.status_code == 200, resp.text
    prov = resp.json()["provenance"]
    assert prov["data_status"] == "partial_inputs_defaulted"
    assert set(prov["defaults_applied"]) == {
        "avg_order_value", "purchase_frequency", "customer_lifetime_years"}


# ── 5. Predictive analytics provenance ───────────────────────────────────────


def test_forecast_provenance_explains_accuracy():
    result = PredictiveAnalytics().forecast("m", [10, 12, 11, 13, 15, 14, 16], steps=3)
    basis = result.provenance["confidence_basis"]
    assert "in-sample" in basis and "NOT" in basis
    assert result.provenance["data_status"] == "estimated_from_inputs"


def test_demand_provenance_discloses_endpoints_only_confidence():
    result = PredictiveAnalytics().forecast_demand(
        "p", [100, 110, 105, 120], supplied_fields={"product_id", "sales_history"})
    assert result.confidence == 0.8
    assert "first and last" in result.provenance["confidence_basis"]
    assert "seasonal_factor" in result.provenance["defaults_applied"]


def test_trend_provenance_states_single_step_basis():
    result = PredictiveAnalytics().analyze_trend("m", [10, 11, 12, 14])
    assert "last-step" in result.provenance["confidence_basis"]


def test_behavior_prediction_provenance_states_bucket_rule():
    history = [{"date": d, "engagement": 0.1 * d, "action": "view"} for d in range(8)]
    out = PredictiveAnalytics().predict_customer_behavior("c1", history)
    assert out["confidence"] == 0.8
    assert "bucket constant" in out["provenance"]["confidence_basis"]
    empty = PredictiveAnalytics().predict_customer_behavior("c2", [])
    assert empty["provenance"]["data_status"] == "no_data"


def test_seasonality_provenance_states_detector_limits():
    out = PredictiveAnalytics().detect_seasonal_pattern([5, 9] * 4, period=2)
    assert "within a period is invisible" in out["provenance"]["confidence_basis"]
