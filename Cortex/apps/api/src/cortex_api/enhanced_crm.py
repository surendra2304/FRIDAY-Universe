"""
cortex_api/enhanced_crm.py — Cortex Enhanced Multi-Tenant CRM.

Extends Cortex's CRM capabilities with:
1. AI-Powered Lead Scoring: composite scoring from behavior, firmographics,
   engagement, and source data — persisted via LeadScoreHistoryModel.
2. Predictive CLV & Churn: predicts customer lifetime value and churn risk.
3. Dynamic Segmentation: assigns leads to segments (Enterprise Hot Lead,
   Qualified, Nurture, Early Stage, Unqualified).
4. Smart Follow-up: actionable next-step suggestions based on score grade.
5. Engagement Scoring: cross-channel engagement (email, web, social).
6. A/B Test Framework: multi-variant test harness with recommendations.
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_api.config import get_db_session
from cortex_api.db_models import LeadModel, LeadScoreHistoryModel
from cortex_api.auth import Role, require_role
from cortex_api.provenance import (
    CALLER_SUPPLIED,
    ROUTE_DEFAULT,
    STORED_STATE,
    build_provenance,
    input_record,
)

logger = logging.getLogger("cortex-enhanced-crm")

router = APIRouter()


# ── Data classes ────────────────────────────────────────────────────────────


@dataclass
class LeadScore:
    """A scored lead with full breakdown."""
    lead_id: str
    tenant_id: str
    total_score: float
    grade: str
    behavior_score: float
    firmographic_score: float
    engagement_score: float
    source_score: float
    factors: dict[str, float]
    predicted_value: float
    churn_risk: float
    segment: str
    # TASK-COR-002: provenance block (inputs used, defaults applied,
    # value/churn basis) — see cortex_api/provenance.py.
    provenance: dict = field(default_factory=dict)


@dataclass
class EngagementMetrics:
    """Cross-channel engagement metrics."""
    email_open_rate: float = 0.0
    email_click_rate: float = 0.0
    web_visits: int = 0
    web_time_avg: float = 0.0
    social_interactions: int = 0
    engagement_score: float = 0.0


@dataclass
class ABTestResult:
    """An A/B test result."""
    test_id: str
    variant_a: str
    variant_b: str
    metric: str
    result: str
    confidence: float
    recommendation: str


# ── Core engine ────────────────────────────────────────────────────────────


class EnhancedCRM:
    """AI-powered CRM with lead scoring, segmentation, and predictive analytics."""

    GRADE_THRESHOLDS = {"A": 80, "B": 60, "C": 40, "D": 20, "F": 0}

    def __init__(self):
        self._lead_scores: dict[str, LeadScore] = {}
        self._ab_tests: dict[str, ABTestResult] = {}
        self._engagement_log: list[dict] = []
        self._segment_cache: dict[str, list[str]] = {}

    # ── Lead Scoring ───────────────────────────────────────────────────────

    def score_lead(
        self,
        lead_id: str,
        tenant_id: str = "",
        *,
        company_size: int = 0,
        industry: str = "",
        website_visits: int = 0,
        email_opens: int = 0,
        email_clicks: int = 0,
        form_submissions: int = 0,
        demo_requests: int = 0,
        engagement_time: float = 0.0,
        source: str = "",
        supplied_fields: set[str] | None = None,
    ) -> LeadScore:
        """Score a lead across four dimensions and assign a grade + segment.

        TASK-COR-002: ``supplied_fields`` names the inputs the caller
        actually provided (the route passes the request payload's keys).
        Every other input is recorded in the score's provenance as a
        route/engine default, because the defaults are material: an
        unlisted industry contributes +5 firmographic points and an
        unmapped source contributes 3 source points whether or not anyone
        supplied them (production probe 2026-11-15: 8 of a lead's 10
        points came from never-supplied inputs).
        """

        # ── Behavior (0–40) ──
        behavior = 0.0
        behavior += min(15, website_visits / 5.0)
        behavior += min(15, (email_opens / 3.0) + (email_clicks / 2.0))
        behavior += min(10, (form_submissions * 5) + (demo_requests * 10))
        behavior = min(40, behavior)

        # ── Firmographic (0–30) ──
        firmo = 0.0
        firmo += min(20, company_size / 10.0)
        high_value_industries = {"finance", "tech", "healthcare", "saas", "enterprise"}
        firmo += 15 if industry.lower() in high_value_industries else 5
        firmo = min(30, firmo)

        # ── Engagement (0–20) ──
        engagement = min(20, engagement_time / 300.0)

        # ── Source (0–10) ──
        source_map = {"referral": 10, "organic": 8, "paid": 6, "social": 5, "direct": 7}
        source_score = source_map.get(source.lower(), 3)

        total = min(100, behavior + firmo + engagement + source_score)

        grade = self._grade(total)
        predicted_value = total * 100  # $ per score point
        base_churn = (100 - total) / 100.0
        engagement_factor = min(1.0, (website_visits + email_opens + form_submissions) / 10.0)
        churn_risk = max(0.0, base_churn * (1.0 - engagement_factor * 0.3))
        segment = self._segment(total, company_size, engagement_factor)

        factors = {
            "behavior": behavior / 40.0,
            "firmographic": firmo / 30.0,
            "engagement": engagement / 20.0,
            "source": source_score / 10.0,
        }

        raw_inputs = {
            "company_size": company_size,
            "industry": industry,
            "website_visits": website_visits,
            "email_opens": email_opens,
            "email_clicks": email_clicks,
            "form_submissions": form_submissions,
            "demo_requests": demo_requests,
            "engagement_time": engagement_time,
            "source": source,
        }
        provenance = build_provenance(
            inputs=[
                input_record(
                    name, value,
                    CALLER_SUPPLIED
                    if supplied_fields is None or name in supplied_fields
                    else ROUTE_DEFAULT,
                )
                for name, value in raw_inputs.items()
            ],
            confidence=None,
            confidence_basis=(
                "total_score is a rule score (behavior <=40 + firmographic <=30 "
                "+ engagement <=20 + source <=10), not a probability. "
                "predicted_value = total_score x $100 (linear heuristic, NOT "
                "measured revenue). churn_risk = (100 - total_score)/100 x "
                "(1 - 0.3 x engagement_factor). Firmographic industry points: "
                "15 if industry in {finance, tech, healthcare, saas, "
                "enterprise}, else 5. Source points: referral 10, organic 8, "
                "direct 7, paid 6, social 5, unmapped 3."
            ),
        )

        score = LeadScore(
            lead_id=lead_id,
            tenant_id=tenant_id,
            total_score=total,
            grade=grade,
            behavior_score=behavior,
            firmographic_score=firmo,
            engagement_score=engagement,
            source_score=source_score,
            factors=factors,
            predicted_value=predicted_value,
            churn_risk=churn_risk,
            segment=segment,
            provenance=provenance,
        )

        self._lead_scores[lead_id] = score
        return score

    def _grade(self, score: float) -> str:
        for g, threshold in sorted(self.GRADE_THRESHOLDS.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return g
        return "F"

    def _segment(self, score: float, company_size: int, engagement: float) -> str:
        if score >= 80 and company_size > 50:
            return "Enterprise Hot Lead"
        elif score >= 60:
            return "Qualified Lead"
        elif score >= 40:
            return "Nurture Lead"
        elif score >= 20:
            return "Early Stage"
        return "Unqualified"

    # ── Predictive CLV ─────────────────────────────────────────────────────

    def predict_clv(
        self,
        lead_score: LeadScore,
        *,
        avg_order_value: float = 1000.0,
        purchase_frequency: float = 2.0,
        customer_lifetime_years: float = 3.0,
    ) -> float:
        """Predict Customer Lifetime Value."""
        churn_adjusted = customer_lifetime_years * (1.0 - lead_score.churn_risk)
        clv = avg_order_value * purchase_frequency * churn_adjusted
        clv *= (lead_score.total_score / 50.0)
        return clv

    # ── Engagement ────────────────────────────────────────────────────────

    def calculate_engagement(
        self,
        *,
        email_open_rate: float,
        email_click_rate: float,
        web_visits: int,
        web_time_avg: float,
        social_interactions: int,
    ) -> EngagementMetrics:
        """Calculate cross-channel engagement score."""
        score = 0.0
        score += min(30, (email_open_rate * 0.3 + email_click_rate * 0.7) * 30)
        score += min(40, (web_visits / 10.0) + (web_time_avg / 60.0))
        score += min(30, social_interactions / 5.0)

        metrics = EngagementMetrics(
            email_open_rate=email_open_rate,
            email_click_rate=email_click_rate,
            web_visits=web_visits,
            web_time_avg=web_time_avg,
            social_interactions=social_interactions,
            engagement_score=min(100, score),
        )

        self._engagement_log.append({"ts": time.time(), **metrics.__dict__})
        return metrics

    # ── Smart Follow-up ───────────────────────────────────────────────────

    def suggest_follow_up(self, lead_score: LeadScore) -> dict[str, Any]:
        """Suggest a follow-up action based on lead grade."""
        s = lead_score.total_score
        if s >= 80:
            return {
                "action": "schedule_demo",
                "priority": "immediate",
                "message": f"High-value lead (score: {s:.0f}). Schedule demo within 24 hours.",
            }
        elif s >= 60:
            return {
                "action": "personal_email",
                "priority": "high",
                "message": f"Qualified lead (score: {s:.0f}). Send personalized email within 48 hours.",
            }
        elif s >= 40:
            return {
                "action": "nurture_campaign",
                "priority": "medium",
                "message": f"Nurture lead (score: {s:.0f}). Add to nurture campaign.",
            }
        return {
            "action": "monitor",
            "priority": "low",
            "message": f"Early stage lead (score: {s:.0f}). Monitor engagement.",
        }

    # ── A/B Testing ────────────────────────────────────────────────────────

    def run_ab_test(
        self,
        test_id: str,
        variant_a: str,
        variant_b: str,
        *,
        metric: str = "conversion_rate",
        variant_a_data: dict | None = None,
        variant_b_data: dict | None = None,
    ) -> ABTestResult:
        """Run an A/B test between two variants."""
        va = variant_a_data or {"conversions": 50, "visitors": 1000}
        vb = variant_b_data or {"conversions": 55, "visitors": 1000}

        conv_a = va["conversions"] / va["visitors"]
        conv_b = vb["conversions"] / vb["visitors"]

        lift = (conv_b - conv_a) / conv_a if conv_a > 0 else 0.0

        # Simple z-test for proportions
        import math
        p_pool = (va["conversions"] + vb["conversions"]) / (va["visitors"] + vb["visitors"])
        se = math.sqrt(
            p_pool * (1 - p_pool) * (1 / va["visitors"] + 1 / vb["visitors"])
        )
        z = (conv_b - conv_a) / se if se > 0 else 0.0
        confidence = math.erf(abs(z) / math.sqrt(2))

        if confidence >= 0.95:
            winner = "B" if conv_b > conv_a else "A"
            recommendation = f"Variant {winner} wins with {confidence:.1%} confidence."
        elif confidence >= 0.80:
            recommendation = "B is trending better but needs more data."
        else:
            recommendation = "Inconclusive. Continue testing."

        result = ABTestResult(
            test_id=test_id,
            variant_a=variant_a,
            variant_b=variant_b,
            metric=metric,
            result=("B" if lift > 0 else "A") if confidence >= 0.95 else "inconclusive",
            confidence=confidence,
            recommendation=recommendation,
        )

        self._ab_tests[test_id] = result
        return result

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_report(self) -> dict[str, Any]:
        """Generate a CRM summary report."""
        if not self._lead_scores:
            return {"status": "NO_DATA", "message": "No leads scored yet"}

        grades: dict[str, int] = {}
        segments: dict[str, int] = {}
        for s in self._lead_scores.values():
            grades[s.grade] = grades.get(s.grade, 0) + 1
            segments[s.segment] = segments.get(s.segment, 0) + 1

        return {
            "total_leads": len(self._lead_scores),
            "grades": grades,
            "segments": segments,
            "average_score": sum(s.total_score for s in self._lead_scores.values()) / len(self._lead_scores),
            "total_predicted_value": sum(s.predicted_value for s in self._lead_scores.values()),
            "ab_tests": {k: v.__dict__ for k, v in self._ab_tests.items()},
        }


# Module-level singleton
enhanced_crm = EnhancedCRM()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/leads/score")
async def score_lead(
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Score a lead with the enhanced model."""
    if payload.get("lead_id") is None:
        raise HTTPException(400, "Missing required field(s): lead_id")
    score = enhanced_crm.score_lead(
        lead_id=payload["lead_id"],
        tenant_id=payload.get("tenant_id", ""),
        company_size=payload.get("company_size", 0),
        industry=payload.get("industry", ""),
        website_visits=payload.get("website_visits", 0),
        email_opens=payload.get("email_opens", 0),
        email_clicks=payload.get("email_clicks", 0),
        form_submissions=payload.get("form_submissions", 0),
        demo_requests=payload.get("demo_requests", 0),
        engagement_time=payload.get("engagement_time", 0.0),
        source=payload.get("source", ""),
        supplied_fields=set(payload.keys()),
    )

    # Persist score history.
    # TASK-COR-002: the model row MUST carry an id — LeadScoreHistoryModel.id
    # has no database-side default, and Oracle rejects the NULL primary key
    # (ORA-01400), which made this route HTTP 500 on every production call
    # while the score silently survived only in process memory
    # (production journal 2026-11-15 13:00:49 IST).
    history = LeadScoreHistoryModel(
        id=uuid.uuid4().hex,
        tenant_id=score.tenant_id or "unknown",
        lead_id=score.lead_id,
        total_score=score.total_score,
        behavior_score=score.behavior_score,
        firmographic_score=score.firmographic_score,
        engagement_score=score.engagement_score,
        source_score=score.source_score,
        score_breakdown=score.factors,
        triggered_by="enhanced_crm",
    )
    db.add(history)
    try:
        await db.commit()
    except IntegrityError:
        # TASK-COR-002: LeadScoreHistoryModel.lead_id references LEADS.id.
        # Scoring a lead that was never captured violates that FK on
        # enforcing databases (Oracle ORA-02291) — a client error, not a
        # server fault, so answer 404 instead of 500.
        await db.rollback()
        raise HTTPException(
            status_code=404,
            detail=f"Lead {score.lead_id} not found; capture the lead before scoring it",
        )

    return {
        "lead_id": score.lead_id,
        "total_score": score.total_score,
        "grade": score.grade,
        "predicted_value": score.predicted_value,
        "churn_risk": score.churn_risk,
        "segment": score.segment,
        "breakdown": {
            "behavior": score.behavior_score,
            "firmographic": score.firmographic_score,
            "engagement": score.engagement_score,
            "source": score.source_score,
        },
        "provenance": score.provenance,
    }


@router.get("/api/v1/leads/{lead_id}/follow-up")
async def suggest_follow_up(
    lead_id: str,
    user: dict = Depends(require_role(Role.CORTEX_VIEWER)),
):
    """Suggest a follow-up action for a lead."""
    if lead_id not in enhanced_crm._lead_scores:
        raise HTTPException(404, "Lead not found")
    score = enhanced_crm._lead_scores[lead_id]
    suggestion = enhanced_crm.suggest_follow_up(score)
    # TASK-COR-002: the suggestion is only as good as the score behind it —
    # carry the score's provenance so a follow-up driven mostly by
    # defaulted inputs is visible as such.
    suggestion["provenance"] = score.provenance
    return suggestion


@router.post("/api/v1/leads/{lead_id}/clv")
async def predict_clv(
    lead_id: str,
    payload: dict | None = None,
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Predict Customer Lifetime Value for a lead."""
    if lead_id not in enhanced_crm._lead_scores:
        raise HTTPException(404, "Lead not found")
    payload = payload or {}
    score = enhanced_crm._lead_scores[lead_id]
    clv = enhanced_crm.predict_clv(
        score,
        avg_order_value=payload.get("avg_order_value", 1000.0),
        purchase_frequency=payload.get("purchase_frequency", 2.0),
        customer_lifetime_years=payload.get("customer_lifetime_years", 3.0),
    )
    # TASK-COR-002: an empty request used to return a bare dollar figure
    # computed entirely from the three route defaults below (production
    # probe 2026-11-15: predicted_clv 444.0 from {}). Disclose them.
    provenance = build_provenance(
        inputs=[
            input_record("avg_order_value", payload.get("avg_order_value", 1000.0),
                         CALLER_SUPPLIED if "avg_order_value" in payload else ROUTE_DEFAULT),
            input_record("purchase_frequency", payload.get("purchase_frequency", 2.0),
                         CALLER_SUPPLIED if "purchase_frequency" in payload else ROUTE_DEFAULT),
            input_record("customer_lifetime_years", payload.get("customer_lifetime_years", 3.0),
                         CALLER_SUPPLIED if "customer_lifetime_years" in payload else ROUTE_DEFAULT),
            input_record("lead_total_score", score.total_score, STORED_STATE),
            input_record("lead_churn_risk", score.churn_risk, STORED_STATE),
        ],
        confidence=None,
        confidence_basis=(
            "predicted_clv = avg_order_value x purchase_frequency x "
            "customer_lifetime_years x (1 - churn_risk) x (total_score / 50). "
            "A deterministic heuristic over the stated inputs, NOT a measured "
            "or modelled revenue forecast."
        ),
    )
    return {"lead_id": lead_id, "predicted_clv": clv, "provenance": provenance}


@router.post("/api/v1/crm/engagement")
async def calculate_engagement(
    payload: dict,
    user: dict = Depends(require_role(Role.CORTEX_OPERATOR)),
):
    """Calculate cross-channel engagement score."""
    metrics = enhanced_crm.calculate_engagement(
        email_open_rate=payload.get("email_open_rate", 0.0),
        email_click_rate=payload.get("email_click_rate", 0.0),
        web_visits=payload.get("web_visits", 0),
        web_time_avg=payload.get("web_time_avg", 0.0),
        social_interactions=payload.get("social_interactions", 0),
    )
    return metrics.__dict__


@router.post("/api/v1/crm/ab-test")
async def run_ab_test(
    payload: dict,
    user: dict = Depends(require_role(Role.CORTEX_ADMIN)),
):
    """Run an A/B test between two variants."""
    result = enhanced_crm.run_ab_test(
        test_id=payload["test_id"],
        variant_a=payload["variant_a"],
        variant_b=payload["variant_b"],
        metric=payload.get("metric", "conversion_rate"),
        variant_a_data=payload.get("variant_a_data"),
        variant_b_data=payload.get("variant_b_data"),
    )
    return result.__dict__


@router.get("/api/v1/crm/report")
async def get_crm_report(
    user: dict = Depends(require_role(Role.CORTEX_VIEWER)),
):
    """Get CRM summary report."""
    return enhanced_crm.get_report()
