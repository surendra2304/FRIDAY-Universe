"""Skill-learning loop router (TASK-IG2-MEM-02 wiring).

``SkillLearningService`` (PR #711) shipped as a tested library that no
production code called: the Hermes learn-from-experience loop existed
only in its own module and its tests. This router is the production
caller, and the app's existing background worker runs the loop's
trigger pass (see ``run_evaluation_pass`` below and the lifespan in
``apps/api/main.py``):

- ``POST /v1/skills/outcomes`` — an agent reports a task outcome
  (success / failure / owner-corrected) for a recurring pattern.
- ``POST /v1/skills/evaluate`` — one evaluation pass for the caller:
  patterns that earned a draft get one (pending_review, always).
- ``GET  /v1/skills/stats``    — per-pattern outcome tallies.
- ``GET  /v1/skills/drafts``   — drafts, optionally filtered by status.
- ``POST /v1/skills/drafts/{draft_id}/review`` — the review gate.
  Restricted to the Memora service identity (``require_admin``): a
  draft becoming an active skill is an administrative act taken on
  the owner's behalf, and drafts NEVER self-activate — the loop can
  propose, only this gate can dispose.
- ``GET  /v1/skills/active``   — approved skills the caller may reuse.

The actor is always the authenticated agent identity. Service results
are returned verbatim: the service never raises into the caller, and a
refusal carries its reason in the payload.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_actor_header, require_admin
from core.memory.skill_learning_service import OUTCOME_SOURCE, SkillLearningService
from storage.relational.models import MemoryRecord
from storage.relational.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/skills", tags=["Skill Learning"])


class OutcomeRequest(BaseModel):
    pattern_key: str = Field(..., min_length=1, max_length=200)
    outcome: str = Field(..., min_length=1, max_length=32)
    detail: str = Field(..., min_length=1, max_length=4000)
    correction: Optional[str] = Field(default=None, max_length=4000)
    task_id: Optional[str] = Field(default=None, max_length=128)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


class EvaluateRequest(BaseModel):
    min_successes: int = Field(default=3, ge=1, le=100)
    min_success_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


class ReviewRequest(BaseModel):
    approve: bool
    tenant_id: Optional[str] = Field(default=None, max_length=128)


@router.post("/outcomes")
def record_outcome(
    body: OutcomeRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Store one task outcome for a recurring pattern."""
    return SkillLearningService.record_outcome(
        db,
        actor_name=actor_name,
        pattern_key=body.pattern_key,
        outcome=body.outcome,
        detail=body.detail,
        correction=body.correction,
        task_id=body.task_id,
        tenant_id=body.tenant_id,
    )


@router.post("/evaluate")
def evaluate_patterns(
    body: EvaluateRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """One learning-loop pass for the caller (drafts stay pending)."""
    return SkillLearningService.evaluate_patterns(
        db,
        actor_name=actor_name,
        tenant_id=body.tenant_id,
        min_successes=body.min_successes,
        min_success_rate=body.min_success_rate,
    )


@router.get("/stats")
def pattern_stats(
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Per-pattern outcome tallies for the caller."""
    return SkillLearningService.pattern_stats(db, actor_name=actor_name, tenant_id=tenant_id)


@router.get("/drafts")
def list_drafts(
    status_filter: Optional[str] = Query(default=None, alias="status", max_length=32),
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Skill drafts for the caller, optionally filtered by review status."""
    return SkillLearningService.list_skill_drafts(
        db, actor_name=actor_name, tenant_id=tenant_id, status=status_filter
    )


@router.post("/drafts/{draft_id}/review")
def review_draft(
    body: ReviewRequest,
    draft_id: str = Path(..., min_length=1, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Approve (→ active skill) or reject a pending draft.

    Admin-gated: activation is the one irreversible step in the loop,
    so it belongs to the service identity acting for the owner — the
    same convention as identity/audit administration.
    """
    require_admin(actor_name)
    return SkillLearningService.review_skill(
        db,
        actor_name=actor_name,
        draft_id=draft_id,
        approve=body.approve,
        tenant_id=body.tenant_id,
    )


@router.get("/active")
def list_active(
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Approved skills only — what the caller may actually reuse."""
    return SkillLearningService.active_skills(db, actor_name=actor_name, tenant_id=tenant_id)


# ----------------------------------------------------------------------
# background trigger pass
# ----------------------------------------------------------------------

def actors_with_outcomes(db: Session) -> List[str]:
    """Distinct agent names that have recorded at least one outcome."""
    rows = (
        db.query(MemoryRecord.agent_id, MemoryRecord.owner_agent)
        .filter(MemoryRecord.source == OUTCOME_SOURCE)
        .distinct()
        .all()
    )
    actors = set()
    for agent_id, owner_agent in rows:
        if agent_id:
            actors.add(agent_id)
        if owner_agent:
            actors.add(owner_agent)
    return sorted(actors)


def run_evaluation_pass(db: Session) -> Dict[str, Any]:
    """One background learning-loop pass over every actor with outcomes.

    Called by the app's background worker (apps/api/main.py lifespan).
    Drafts are created as pending_review only — this pass can propose
    skills, it can never activate one. Fail-soft per actor: one actor's
    refusal is logged and counted, never fatal to the pass.
    """
    summary: Dict[str, Any] = {"actors": 0, "drafted": 0, "errors": 0}
    for actor in actors_with_outcomes(db):
        summary["actors"] += 1
        try:
            result = SkillLearningService.evaluate_patterns(db, actor_name=actor)
            summary["drafted"] += len(result.get("drafted") or [])
        except Exception as exc:
            summary["errors"] += 1
            logger.warning("[SKILL-LEARN] background pass failed for %s: %s", actor, exc)
    return summary
