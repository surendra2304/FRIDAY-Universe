"""
Cortex/apps/api/src/cortex_api/decision_recommendation_system.py — Cortex Decision Recommendation System.

Multi-criteria decision recommendation engine with uncertainty quantification,
risk-return optimization, stakeholder analysis, and recommendation explanations.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

from cortex_api.provenance import (
    CALLER_SUPPLIED,
    ENGINE_DEFAULT,
    STORED_STATE,
    build_provenance,
    input_record,
)

router = APIRouter()


@dataclass
class DecisionCriterion:
    """A decision criterion."""
    criterion_id: str
    name: str
    description: str = ""
    weight: float = 1.0
    direction: str = "maximize"  # maximize, minimize
    unit: str = ""


@dataclass
class Alternative:
    """A decision alternative."""
    alternative_id: str
    name: str
    description: str = ""
    criteria_scores: dict = field(default_factory=dict)  # {criterion_id: score}
    risk_score: float = 0.0
    return_projection: float = 0.0


@dataclass
class DecisionMatrix:
    """A decision analysis matrix."""
    matrix_id: str
    problem_statement: str = ""
    criteria: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    weights: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)


@dataclass
class Recommendation:
    """A decision recommendation."""
    recommendation_id: str
    problem_statement: str
    best_alternative: str = ""
    alternatives_ranking: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    risk_level: str = "medium"
    expected_value: float = 0.0
    sensitivity_analysis: dict = field(default_factory=dict)
    rationale: str = ""
    stakeholder_impact: dict = field(default_factory=dict)
    # TASK-COR-003: provenance of the stored record itself. Before this fix a
    # stored recommendation carried no timestamp, no decider, and no snapshot
    # of the inputs it was computed from — the criteria/alternatives live in
    # mutable engine state, so a past decision could never be reconstructed.
    created_at: float = 0.0
    decider: str = ""
    inputs_snapshot: dict = field(default_factory=dict)
    outcome: dict = field(default_factory=dict)
    # TASK-COR-002: provenance block (inputs used, defaults applied,
    # confidence basis) — see cortex_api/provenance.py.
    provenance: dict = field(default_factory=dict)


@dataclass
class Stakeholder:
    """A decision stakeholder."""
    stakeholder_id: str
    name: str
    role: str = ""
    interest_level: float = 0.5
    influence_level: float = 0.5
    position: str = ""  # support, neutral, oppose


@dataclass
class UncertaintyAnalysis:
    """Uncertainty analysis for a decision."""
    analysis_id: str
    recommendation_id: str
    uncertainty_level: float | None = None
    confidence_interval: tuple[float | None, float | None] = (None, None)
    key_uncertainties: list[str] = field(default_factory=list)
    risk_adjusted_score: float | None = None
    data_status: str = "no_data"
    data_note: str = ""
    worst_case: str = ""
    best_case: str = ""


@dataclass
class DecisionHistory:
    """History of decision recommendations."""
    problem_statement: str
    total_decisions: int = 0
    avg_confidence: float = 0.0
    avg_risk_level: float = 0.0
    success_rate: float = 0.0
    trend: str = "stable"


class DecisionRecommendationSystem:
    """Decision recommendation engine."""

    def __init__(self):
        self._criteria: dict[str, DecisionCriterion] = {}
        self._alternatives: dict[str, Alternative] = {}
        self._recommendations: list[Recommendation] = []
        self._stakeholders: list[Stakeholder] = []
        self._uncertainty: list[UncertaintyAnalysis] = []
        self._history: dict[str, DecisionHistory] = {}

    def add_criterion(self, name: str, weight: float = 1.0, direction: str = "maximize") -> DecisionCriterion:
        """Add a decision criterion."""
        criterion = DecisionCriterion(
            criterion_id=hashlib.md5(
                f"criterion:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            weight=weight,
            direction=direction,
        )
        self._criteria[criterion.criterion_id] = criterion
        return criterion

    def add_alternative(self, name: str, description: str = "", risk_score: float = 0.5, return_projection: float = 0.5) -> Alternative:
        """Add a decision alternative."""
        alt = Alternative(
            alternative_id=hashlib.md5(
                f"alternative:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            description=description,
            risk_score=risk_score,
            return_projection=return_projection,
        )
        self._alternatives[alt.alternative_id] = alt
        return alt

    def score_alternative(self, alternative_id: str, criterion_id: str, score: float) -> Alternative:
        """Score an alternative against a criterion."""
        alt = self._alternatives.get(alternative_id)
        if not alt:
            raise HTTPException(404, f"Alternative {alternative_id} not found")

        alt.criteria_scores[criterion_id] = score
        return alt

    def recommend(self, problem_statement: str, decider: str = "") -> Recommendation:
        """Generate a decision recommendation."""
        if not self._criteria or not self._alternatives:
            raise HTTPException(400, "Need criteria and alternatives")

        # TASK-REL-047 (PR #361) + lead-coordinator ruling 2026-11-16: no
        # silent defaults. A criterion an alternative was never scored on
        # used to contribute an invented 0.5 to the weighted score
        # (TASK-COR-002's controlled probe: a recommendation with confidence
        # 0.5833 computed from a matrix that was 75% invented cells).
        # COR-002 first made the output disclose the defaults; the ruling
        # abolishes them — an incomplete score matrix is rejected outright
        # with HTTP 422 naming every missing cell. The refusal itself is
        # appended to the decision log (TASK-COR-003 completeness): the log
        # records that a recommendation was requested and refused, never a
        # fabricated decision.
        missing = [
            f"{alt.name} / {crit.name}"
            for alt in self._alternatives.values()
            for crit in self._criteria.values()
            if crit.criterion_id not in alt.criteria_scores
        ]
        if missing:
            self._record_rejection(problem_statement, decider, missing)
            raise HTTPException(
                422,
                "Incomplete decision matrix: missing scores for "
                + ", ".join(missing)
                + ". Supply a score for every alternative-by-criterion cell "
                "before requesting a recommendation.",
            )

        # Calculate weighted scores for each alternative. Completeness is
        # validated above, so direct indexing is safe — and any future path
        # that bypasses validation fails loudly instead of inventing a 0.5.
        # Every cell is still recorded in the recommendation's provenance
        # (TASK-COR-002) and snapshot (TASK-COR-003); with the gate, the
        # defaulted-cells list is always empty.
        defaulted_cells: list[str] = []
        scores = {}
        provenance_inputs = []
        for alt_id, alt in self._alternatives.items():
            total_score = 0.0
            for crit_id, crit in self._criteria.items():
                supplied = crit_id in alt.criteria_scores
                score = alt.criteria_scores[crit_id]
                provenance_inputs.append(input_record(
                    f"score[{alt.name}][{crit.name}]",
                    score,
                    CALLER_SUPPLIED if supplied else ENGINE_DEFAULT,
                ))
                # Normalize if direction is minimize
                if crit.direction == "minimize":
                    score = 1.0 - score
                # Weight by criterion weight
                total_score += score * crit.weight

            # Average by total weight
            total_weight = sum(c.weight for c in self._criteria.values())
            scores[alt_id] = total_score / max(1, total_weight)

        for crit in self._criteria.values():
            provenance_inputs.append(input_record(
                f"weight[{crit.name}]", crit.weight, STORED_STATE))
        for alt in self._alternatives.values():
            provenance_inputs.append(input_record(
                f"risk_score[{alt.name}]", alt.risk_score, STORED_STATE))
            provenance_inputs.append(input_record(
                f"return_projection[{alt.name}]", alt.return_projection, STORED_STATE))

        # Rank alternatives
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Best alternative
        best_alt_id, best_score = ranking[0]
        best_alt = self._alternatives.get(best_alt_id)

        # Calculate confidence
        confidence = best_score / max(0.01, sum(scores.values()))

        # Risk level
        risk = best_alt.risk_score if best_alt else 0.5
        risk_level = "high" if risk > 0.7 else "medium" if risk > 0.4 else "low"

        # Sensitivity analysis
        sensitivity = {}
        for crit_id, crit in self._criteria.items():
            # Vary weight by ±20%
            varied_scores = {}
            for alt_id, alt in self._alternatives.items():
                score = alt.criteria_scores[crit_id]
                if crit.direction == "minimize":
                    score = 1.0 - score
                varied_scores[alt_id] = score * crit.weight * 1.2

            # Check if ranking changes
            varied_ranking = sorted(varied_scores.items(), key=lambda x: x[1], reverse=True)
            sensitivity[crit.name] = {
                "ranking_change": varied_ranking[0][0] != best_alt_id,
                "impact": abs(varied_ranking[0][1] - best_score) / max(0.01, best_score),
            }

        recommendation = Recommendation(
            recommendation_id=hashlib.md5(
                f"rec:{problem_statement[:30]}:{time.time()}".encode()
            ).hexdigest()[:12],
            problem_statement=problem_statement,
            best_alternative=best_alt.name if best_alt else "",
            alternatives_ranking=[
                {"name": self._alternatives[alt_id].name, "score": round(score, 4)}
                for alt_id, score in ranking
            ],
            confidence=round(confidence, 4),
            risk_level=risk_level,
            expected_value=best_alt.return_projection if best_alt else 0.0,
            sensitivity_analysis=sensitivity,
            rationale=f"Selected '{best_alt.name if best_alt else 'Unknown'}' with highest weighted score ({best_score:.2f})",
            stakeholder_impact={},
            created_at=time.time(),
            decider=decider,
            inputs_snapshot={
                "criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "name": c.name,
                        "weight": c.weight,
                        "direction": c.direction,
                    }
                    for c in self._criteria.values()
                ],
                "alternatives": [
                    {
                        "alternative_id": a.alternative_id,
                        "name": a.name,
                        "criteria_scores": dict(a.criteria_scores),
                        "risk_score": a.risk_score,
                        "return_projection": a.return_projection,
                    }
                    for a in self._alternatives.values()
                ],
                "defaulted_cells": defaulted_cells,
            },
            outcome={
                "status": "decided",
                "selected": best_alt.name if best_alt else "",
                "observed_result": None,
                "success": None,
                "recorded_at": None,
            },
            provenance=build_provenance(
                inputs=provenance_inputs,
                confidence=round(confidence, 4),
                confidence_basis=(
                    "confidence = best alternative's weighted score / sum of all "
                    "alternatives' weighted scores. It is a share of total score, "
                    "NOT a calibrated probability of a correct decision. "
                    "Every score cell was supplied by the caller — incomplete "
                    "matrices are rejected (HTTP 422), never defaulted "
                    "(TASK-REL-047)."
                ),
            ),
        )

        self._recommendations.append(recommendation)

        # Update history
        history = self._history.get(problem_statement)
        if not history:
            history = DecisionHistory(problem_statement=problem_statement)
            self._history[problem_statement] = history

        history.total_decisions += 1
        history.avg_confidence = (
            history.avg_confidence * 0.9 + confidence * 0.1
        )

        return recommendation

    def _record_rejection(
        self, problem_statement: str, decider: str, missing: list[str]
    ) -> Recommendation:
        """Append a rejected-incomplete record to the decision log.

        TASK-REL-047 ruling (2026-11-16): when recommend() refuses an
        incomplete matrix (HTTP 422), the refusal itself is a decision-log
        event (TASK-COR-003 completeness) — what was asked, by whom, and
        which cells were missing. The record carries NO selection and NO
        confidence: nothing was decided, and the log must not pretend
        otherwise. ``missing`` holds the "alternative / criterion" name
        pairs the 422 detail names.
        """
        missing_ids = [
            f"{alt.alternative_id}:{crit.criterion_id}"
            for alt in self._alternatives.values()
            for crit in self._criteria.values()
            if crit.criterion_id not in alt.criteria_scores
        ]
        provenance_inputs = []
        for alt in self._alternatives.values():
            for crit in self._criteria.values():
                if crit.criterion_id in alt.criteria_scores:
                    provenance_inputs.append(input_record(
                        f"score[{alt.name}][{crit.name}]",
                        alt.criteria_scores[crit.criterion_id],
                        CALLER_SUPPLIED,
                    ))
        for crit in self._criteria.values():
            provenance_inputs.append(input_record(
                f"weight[{crit.name}]", crit.weight, STORED_STATE))
        for alt in self._alternatives.values():
            provenance_inputs.append(input_record(
                f"risk_score[{alt.name}]", alt.risk_score, STORED_STATE))
            provenance_inputs.append(input_record(
                f"return_projection[{alt.name}]", alt.return_projection, STORED_STATE))

        record = Recommendation(
            recommendation_id=hashlib.md5(
                f"rec:{problem_statement[:30]}:{time.time()}".encode()
            ).hexdigest()[:12],
            problem_statement=problem_statement,
            best_alternative="",
            alternatives_ranking=[],
            confidence=0.0,
            risk_level="unknown",
            expected_value=0.0,
            sensitivity_analysis={},
            rationale=(
                "Recommendation refused: incomplete decision matrix — "
                "missing scores for " + ", ".join(missing) + "."
            ),
            stakeholder_impact={},
            created_at=time.time(),
            decider=decider,
            inputs_snapshot={
                "criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "name": c.name,
                        "weight": c.weight,
                        "direction": c.direction,
                    }
                    for c in self._criteria.values()
                ],
                "alternatives": [
                    {
                        "alternative_id": a.alternative_id,
                        "name": a.name,
                        "criteria_scores": dict(a.criteria_scores),
                        "risk_score": a.risk_score,
                        "return_projection": a.return_projection,
                    }
                    for a in self._alternatives.values()
                ],
                "defaulted_cells": [],
                "missing_cells": missing_ids,
            },
            outcome={
                "status": "rejected_incomplete",
                "selected": "",
                "missing_cells": missing,
                "observed_result": None,
                "success": None,
                "recorded_at": None,
            },
            provenance=build_provenance(
                inputs=provenance_inputs,
                confidence=None,
                confidence_basis=(
                    "No confidence is stated: no recommendation was computed. "
                    "The score matrix was incomplete, so the request was "
                    "rejected (HTTP 422) instead of being decided from "
                    "invented default inputs (TASK-REL-047)."
                ),
                data_status="incomplete_inputs",
            ),
        )
        self._recommendations.append(record)
        return record

    def record_outcome(
        self, recommendation_id: str, observed_result: object, success: bool | None = None
    ) -> bool:
        """Attach the observed outcome to a stored recommendation (TASK-COR-003).

        Until this method existed, a stored recommendation could never gain
        an outcome after the fact — the log showed what was picked, never
        what happened. Returns True when the recommendation was found.
        """
        for rec in self._recommendations:
            if rec.recommendation_id == recommendation_id:
                rec.outcome = {
                    "status": "outcome_recorded",
                    "selected": rec.best_alternative,
                    "observed_result": observed_result,
                    "success": success,
                    "recorded_at": time.time(),
                }
                return True
        return False

    def add_stakeholder(self, name: str, role: str, interest: float, influence: float, position: str = "neutral") -> Stakeholder:
        """Add a stakeholder."""
        stakeholder = Stakeholder(
            stakeholder_id=hashlib.md5(
                f"stakeholder:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            role=role,
            interest_level=interest,
            influence_level=influence,
            position=position,
        )
        self._stakeholders.append(stakeholder)
        return stakeholder

    def analyze_uncertainty(self, recommendation_id: str) -> UncertaintyAnalysis:
        """Analyze uncertainty for a recommendation."""
        rec = None
        for r in self._recommendations:
            if r.recommendation_id == recommendation_id:
                rec = r
                break

        if not rec:
            raise HTTPException(404, f"Recommendation {recommendation_id} not found")

        # Uncertainty is computed from the recommendation's own sensitivity
        # analysis: the mean per-criterion impact of a +/-20% weight change,
        # clamped to [0, 1]. (TASK-REL-020: previously derived from an md5
        # hash of the recommendation id.)
        impacts = [
            entry.get("impact", 0.0)
            for entry in rec.sensitivity_analysis.values()
            if isinstance(entry, dict)
        ]
        if impacts:
            uncertainty = round(min(1.0, max(0.0, sum(impacts) / len(impacts))), 4)
            analysis = UncertaintyAnalysis(
                analysis_id=hashlib.md5(
                    f"uncertainty:{recommendation_id}:{time.time()}".encode()
                ).hexdigest()[:12],
                recommendation_id=recommendation_id,
                uncertainty_level=uncertainty,
                confidence_interval=(
                    max(0.0, rec.confidence - uncertainty),
                    min(1.0, rec.confidence + uncertainty),
                ),
                key_uncertainties=[
                    "Market conditions may change",
                    "Stakeholder priorities may shift",
                    "Implementation may differ from plan",
                ],
                risk_adjusted_score=rec.expected_value * (1 - uncertainty),
                worst_case=f"Worst case: {rec.best_alternative} yields minimal return",
                best_case=f"Best case: {rec.best_alternative} yields optimal return",
                data_status="estimated_from_inputs",
                data_note=(
                    "Uncertainty is the mean per-criterion impact from the "
                    "recommendation's sensitivity analysis (weight +/-20%), "
                    "clamped to [0, 1]."
                ),
            )
        else:
            analysis = UncertaintyAnalysis(
                analysis_id=hashlib.md5(
                    f"uncertainty:{recommendation_id}:{time.time()}".encode()
                ).hexdigest()[:12],
                recommendation_id=recommendation_id,
                uncertainty_level=None,
                confidence_interval=(None, None),
                key_uncertainties=[
                    "Market conditions may change",
                    "Stakeholder priorities may shift",
                    "Implementation may differ from plan",
                ],
                risk_adjusted_score=None,
                worst_case=f"Worst case: {rec.best_alternative} yields minimal return",
                best_case=f"Best case: {rec.best_alternative} yields optimal return",
                data_status="no_data",
                data_note=(
                    "No sensitivity analysis is stored for this "
                    "recommendation, so uncertainty cannot be quantified."
                ),
            )

        self._uncertainty.append(analysis)
        return analysis

    def get_report(self) -> dict:
        """Get decision recommendation system report."""
        return {
            "total_criteria": len(self._criteria),
            "total_alternatives": len(self._alternatives),
            "total_recommendations": len(self._recommendations),
            "total_stakeholders": len(self._stakeholders),
            "total_uncertainty_analyses": len(self._uncertainty),
            "avg_recommendation_confidence": sum(r.confidence for r in self._recommendations) / max(1, len(self._recommendations)),
            # Ordinal mean of the stored risk_level (low=0, medium=1,
            # high=2). Previously read a non-existent r.risk_score
            # attribute and crashed once a recommendation existed.
            "avg_risk_level": sum(
                {"low": 0.0, "medium": 1.0, "high": 2.0}.get(r.risk_level, 1.0)
                for r in self._recommendations
            ) / max(1, len(self._recommendations)),
            "high_risk_recommendations": sum(1 for r in self._recommendations if r.risk_level == "high"),
            "recent_recommendations": [
                {
                    "problem": r.problem_statement[:50],
                    "best": r.best_alternative,
                    "confidence": r.confidence,
                    "risk": r.risk_level,
                    # TASK-COR-002: surface how much of each past decision
                    # rested on defaulted (never-supplied) inputs.
                    "data_status": r.provenance.get("data_status", "unknown"),
                    "defaults_applied": r.provenance.get("defaults_applied", []),
                }
                for r in self._recommendations[-10:]
            ],
            "recent_uncertainty": [
                {
                    "recommendation": u.recommendation_id,
                    "uncertainty": u.uncertainty_level,
                    "risk_adjusted": u.risk_adjusted_score,
                }
                for u in self._uncertainty[-5:]
            ],
        }


decision_system = DecisionRecommendationSystem()


def _require_fields(payload: dict, *fields: str) -> None:
    """TASK-COR-002: a missing field is a 400 naming the field.

    These routes used to index payload[...] directly, so a malformed
    request died as a KeyError 500 (production journal 2026-11-14: 8 of 8
    decision/score requests 500'd this way) and the caller learned nothing.
    """
    missing = [f for f in fields if payload.get(f) is None]
    if missing:
        raise HTTPException(400, f"Missing required field(s): {', '.join(missing)}")


@router.post("/api/v1/cortex/decision/criteria")
async def add_criterion(payload: dict):
    """Add a decision criterion."""
    _require_fields(payload, "name")
    crit = decision_system.add_criterion(
        name=payload["name"],
        weight=payload.get("weight", 1.0),
        direction=payload.get("direction", "maximize"),
    )
    return {"criterion_id": crit.criterion_id, "name": crit.name, "weight": crit.weight}


@router.post("/api/v1/cortex/decision/alternatives")
async def add_alternative(payload: dict):
    """Add a decision alternative."""
    _require_fields(payload, "name")
    alt = decision_system.add_alternative(
        name=payload["name"],
        description=payload.get("description", ""),
        risk_score=payload.get("risk_score", 0.5),
        return_projection=payload.get("return_projection", 0.5),
    )
    return {"alternative_id": alt.alternative_id, "name": alt.name}


@router.post("/api/v1/cortex/decision/alternatives/{alt_id}/score")
async def score_alternative(alt_id: str, payload: dict):
    """Score an alternative."""
    _require_fields(payload, "criterion_id", "score")
    alt = decision_system.score_alternative(
        alternative_id=alt_id,
        criterion_id=payload["criterion_id"],
        score=payload["score"],
    )
    return {"alternative_id": alt.alternative_id, "scores": len(alt.criteria_scores)}


@router.post("/api/v1/cortex/decision/recommend")
async def recommend(payload: dict):
    """Generate a decision recommendation."""
    _require_fields(payload, "problem_statement")
    # TASK-COR-003: record who asked for the decision in the stored record
    # (callers may identify themselves via the optional "decider" field).
    # Composition note (TASK-REL-047 finisher, 2026-11-16): the stacked
    # COR-002/COR-003 route edits previously invoked recommend() TWICE per
    # request — two decision-log records per call, the second without the
    # decider. Exactly one call now: one request, one log record, whether
    # the outcome is a decision or a logged 422 rejection.
    rec = decision_system.recommend(
        payload["problem_statement"], decider=str(payload.get("decider") or "api_caller")
    )
    return {
        "recommendation_id": rec.recommendation_id,
        "best_alternative": rec.best_alternative,
        "alternatives_ranking": rec.alternatives_ranking,
        "confidence": rec.confidence,
        "risk_level": rec.risk_level,
        "expected_value": rec.expected_value,
        "sensitivity_analysis": rec.sensitivity_analysis,
        "rationale": rec.rationale,
        # TASK-COR-002: the full decision record — which inputs were
        # supplied, which were engine defaults, and what the confidence
        # number actually is. Previously the route dropped the ranking and
        # sensitivity analysis and returned confidence with no basis.
        "provenance": rec.provenance,
    }


@router.get("/api/v1/cortex/decision/report")
async def get_report():
    """Get decision recommendation system report."""
    return decision_system.get_report()
