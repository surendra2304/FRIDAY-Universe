"""Session capture → compress → inject router (TASK-IG2-MEM-01 wiring).

``SessionCaptureService`` (PR #709) shipped as a tested library that no
production code called: the capture → compress → inject loop existed only
in its own module and its tests. This router is the production caller —
the fleet's agents reach the loop over the same authenticated HTTP path
as every other Memora surface:

- ``POST /v1/capture/events``   — one session event in (secret-scrubbed
  by the service before storage; unscrubbable events are dropped with
  the reason in the response, never stored).
- ``POST /v1/capture/compress`` — compress one session's events into
  its digest record (idempotent per event set).
- ``GET  /v1/capture/context``  — the session-start injection pack:
  hybrid recall for the query PLUS the caller's rendered user-model
  profile (TASK-IG2-MEM-03), so the inject path consults the user
  model on every session start, as the user-model service's docstring
  intended ("e.g. alongside TASK-IG2-MEM-01's capture/inject pack").
- ``POST /v1/capture/handoff``  — compress the ending session and build
  the next session's pack in one call, user-model block included.

The actor is always the authenticated agent identity — a request body
cannot name a different agent to write as. Service results are returned
verbatim: the services never raise into the caller, and a refusal
(``stored: false`` etc.) carries its reason in the payload.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_actor_header
from core.memory.capture_service import SessionCaptureService
from core.memory.user_model_service import UserModelService
from storage.relational.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/capture", tags=["Session Capture"])


class CaptureEventRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(default="observation", max_length=64)
    content: str = Field(..., min_length=1, max_length=20000)
    task_id: Optional[str] = Field(default=None, max_length=128)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


class CompressRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


class HandoffRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    next_query: str = Field(..., min_length=1, max_length=2000)
    tenant_id: Optional[str] = Field(default=None, max_length=128)


def _user_model_block(db: Session, actor_name: str, tenant_id: Optional[str]) -> str:
    """The rendered owner profile for session-start injection.

    Fail-soft by design: the profile is an addition to the pack, never
    a reason for the pack itself to fail.
    """
    try:
        return UserModelService.render_profile(db, actor_name=actor_name, tenant_id=tenant_id)
    except Exception as exc:  # pragma: no cover - render_profile never raises by contract
        logger.warning("[CAPTURE] user-model render failed for %s: %s", actor_name, exc)
        return ""


@router.post("/events")
def capture_event(
    body: CaptureEventRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Store one session event as an EPISODIC memory (secret-scrubbed)."""
    return SessionCaptureService.capture_event(
        db,
        actor_name=actor_name,
        session_id=body.session_id,
        kind=body.kind,
        content=body.content,
        task_id=body.task_id,
        tenant_id=body.tenant_id,
    )


@router.post("/compress")
def compress_session(
    body: CompressRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compress one session's captured events into its digest record."""
    return SessionCaptureService.compress_session(
        db,
        actor_name=actor_name,
        session_id=body.session_id,
        tenant_id=body.tenant_id,
    )


@router.get("/context")
def session_context(
    q: str = Query(..., min_length=1, max_length=2000),
    limit: int = Query(default=5, ge=1, le=25),
    tenant_id: Optional[str] = Query(default=None, max_length=128),
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Session-start injection pack: hybrid recall + the user model."""
    pack = SessionCaptureService.build_session_context(
        db,
        actor_name=actor_name,
        query=q,
        limit=limit,
        tenant_id=tenant_id,
    )
    pack["user_model_profile"] = _user_model_block(db, actor_name, tenant_id)
    return pack


@router.post("/handoff")
def session_handoff(
    body: HandoffRequest,
    actor_name: str = Depends(get_actor_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compress the ending session; build the next session's pack."""
    result = SessionCaptureService.handoff(
        db,
        actor_name=actor_name,
        session_id=body.session_id,
        next_query=body.next_query,
        tenant_id=body.tenant_id,
    )
    result["user_model_profile"] = _user_model_block(db, actor_name, body.tenant_id)
    return result
