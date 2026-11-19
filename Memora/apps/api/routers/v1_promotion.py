"""
MEMORA v1 Promotion Endpoints (TASK-MEM-013)

The two owner-locked promotion paths (2026-11-18):

  (A) POST /v1/promotion/promote — the owning agent promotes its own
      memory PRIVATE -> SHARED -> UNIVERSAL on its own judgement.
  (C) POST /v1/promotion/need    — an agent records that it needs a memory;
      POST /v1/promotion/sweep   — the Memora service identity runs one
      auto-promotion pass over the recorded need evidence.

The caller acts as itself: the actor identity comes from the authenticated
header, never from the request body. The sweep is restricted to the Memora
service identity, the only identity allowed to author UNIVERSAL scope.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_actor_header
from core.memory.promotion import (
    PromotionError,
    PromotionPermissionError,
    MemoryPromotionService,
)
from storage.relational.access_scope import SERVICE_AGENT
from storage.relational.models import normalize_agent_name
from storage.relational.session import get_db

router = APIRouter(prefix="/v1/promotion", tags=["v1 Promotion"])


class PromoteRequest(BaseModel):
    memory_id: str = Field(..., min_length=1, max_length=64)
    target_scope: str = Field(
        ..., description="SHARED or UNIVERSAL (promotion is monotonic; PRIVATE is a demotion)."
    )
    shared_with: List[str] = Field(
        default_factory=list,
        description="Recipients when target_scope is SHARED ('*' shares with every agent).",
    )
    reason: Optional[str] = Field(default=None, max_length=512)


@router.post("/promote")
def promote_memory(
    req: PromoteRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """(A) Promote one memory you own, on your own judgement."""
    try:
        return MemoryPromotionService.promote_scope(
            db,
            owner_name=actor_name,
            memory_id=req.memory_id,
            target_scope=req.target_scope,
            shared_with=req.shared_with,
            reason=req.reason or "",
            tenant_id="default",
        )
    except PromotionPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


class NeedRequest(BaseModel):
    memory_id: str = Field(..., min_length=1, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=512)


@router.post("/need")
def record_need(
    req: NeedRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record cross-agent need for a memory — the evidence path (C) counts."""
    try:
        return MemoryPromotionService.record_need(
            db,
            requester_name=actor_name,
            memory_id=req.memory_id,
            reason=req.reason or "",
            tenant_id="default",
        )
    except PromotionPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


class SweepRequest(BaseModel):
    window_days: int = Field(default=30, ge=1, le=365)


@router.post("/sweep")
def run_auto_promotion_sweep(
    req: SweepRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """(C) One auto-promotion pass. Memora service identity only."""
    if normalize_agent_name(actor_name) != SERVICE_AGENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-promotion sweeps run only as the Memora service identity.",
        )
    promotions = MemoryPromotionService.run_auto_promotion_sweep(
        db, tenant_id="default", window_days=req.window_days
    )
    return {"promotions": promotions, "count": len(promotions)}
