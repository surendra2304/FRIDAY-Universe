"""
Self-Improvement API Endpoints for Project FORGE.
Enables review and human approval of self-improvement proposals.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.improvement.models import (
    ImprovementProposal,
    SelfImprovementReport,
)
from app.improvement.self_improve import self_improvement_engine

improvement_router = APIRouter(prefix="/improvement", tags=["Self-Improvement"])


@improvement_router.get(
    "/report", response_model=SelfImprovementReport, summary="Get Self-Improvement Analysis Report"
)
async def get_improvement_report(
    days: int = Query(default=7, ge=1, le=90, description="Rolling analysis window in days"),
) -> SelfImprovementReport:
    """Retrieve failure cluster analysis and pending self-improvement proposals."""
    return await self_improvement_engine.generate_weekly_report(days=days)


@improvement_router.post(
    "/apply/{proposal_id}", response_model=ImprovementProposal, summary="Apply Approved Proposal"
)
async def apply_proposal(
    proposal_id: str,
) -> ImprovementProposal:
    """Approve and apply a self-improvement proposal. Requires explicit invocation."""
    prop = self_improvement_engine.apply_proposal(proposal_id)
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Proposal '{proposal_id}' not found."
        )
    return prop
