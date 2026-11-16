"""User-model router (TASK-IG2-MEM-03 wiring).

``UserModelService`` (PR #712) shipped as a tested library that no
production code called: the structured, inspectable model of the
owner existed only in its own module and its tests, so every agent
kept re-inferring the owner's preferences per session. This router is
the production caller — the model's own surface:

- ``GET  /v1/user-model/profile``     — the full structured profile
  (absence reported as absence: ``exists: false``, never invented).
- ``GET  /v1/user-model/consult``     — one field's current entry:
  the read an agent makes before acting.
- ``GET  /v1/user-model/render``      — the session-start injection
  block (standing rules first).
- ``PUT  /v1/user-model/field``       — set one field (versioned; the
  response reports the value it replaced).
- ``POST /v1/user-model/corrections`` — an owner correction, stored
  as a standing rule at confidence 1.0: corrections outrank
  inferences by design.

The actor is always the authenticated agent identity. (The rendered
profile is additionally embedded in the session-start inject pack by
the capture router — PR #755 — so the model is consulted even by
agents that never call this router directly.)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_actor_header
from core.memory.user_model_service import UserModelService
from storage.relational.session import get_db

router = APIRouter(prefix="/v1/user-model", tags=["User Model"])


class FieldUpdateRequest(BaseModel):
    field: str = Field(..., min_length=1, max_length=200)
    value: Any
    kind: str = Field(..., min_length=1, max_length=32)
    subject: str = Field(default="owner", min_length=1, max_length=128)
    source_ref: Optional[str] = Field(default=None, max_length=500)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


class CorrectionRequest(BaseModel):
    field: str = Field(..., min_length=1, max_length=200)
    value: Any
    subject: str = Field(default="owner", min_length=1, max_length=128)
    source_ref: Optional[str] = Field(default=None, max_length=500)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


@router.get("/profile")
def get_profile(
    subject: str = Query(default="owner", min_length=1, max_length=128),
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """The full structured profile (empty fields when none exists)."""
    return UserModelService.get_profile(
        db, actor_name=actor_name, subject=subject, tenant_id=tenant_id
    )


@router.get("/consult")
def consult_field(
    field: str = Query(..., min_length=1, max_length=200),
    subject: str = Query(default="owner", min_length=1, max_length=128),
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """One field's current entry, or an explicit absence."""
    return UserModelService.consult(
        db, actor_name=actor_name, field=field, subject=subject, tenant_id=tenant_id
    )


@router.get("/render")
def render_profile(
    subject: str = Query(default="owner", min_length=1, max_length=128),
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """The injection block for session-start context (rules first)."""
    return {
        "subject": subject,
        "profile": UserModelService.render_profile(
            db, actor_name=actor_name, subject=subject, tenant_id=tenant_id
        ),
    }


@router.put("/field")
def update_field(
    body: FieldUpdateRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Set one profile field, versioning the profile record."""
    return UserModelService.update_field(
        db,
        actor_name=actor_name,
        field=body.field,
        value=body.value,
        kind=body.kind,
        subject=body.subject,
        source_ref=body.source_ref,
        confidence=body.confidence,
        tenant_id=body.tenant_id,
    )


@router.post("/corrections")
def learn_from_correction(
    body: CorrectionRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Record an owner correction as a standing rule at confidence 1.0."""
    return UserModelService.learn_from_correction(
        db,
        actor_name=actor_name,
        field=body.field,
        value=body.value,
        subject=body.subject,
        source_ref=body.source_ref,
        tenant_id=body.tenant_id,
    )
