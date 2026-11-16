"""
Structured user-model profile in Memora (TASK-IG2-MEM-03, Hermes pattern).

Hermes Agent's second transferable asset (card hermes-agent.md) is
that *it builds a model of the user*. Memora stores facts and episodes
about the owner, but until now there was no single maintained,
inspectable answer to "what do we know about how Surendra wants things
done" — every agent re-inferred it per session, or didn't. This
service is that model:

- ONE profile record per (agent, subject): a PREFERENCE record whose
  provenance carries the structured profile — fields grouped by kind
  (``preference`` / ``habit`` / ``standing_rule`` / ``fact``), each with
  value, confidence, source reference, update count and a capped
  change history. The record's content is the human-readable rendering
  of the same structure, so the profile is findable by ordinary hybrid
  recall as well as by direct lookup.
- ``update_field`` is the only write path: it writes a NEW profile
  version through the write pipeline and supersedes the previous one,
  so the full evolution of the model stays in the record chain —
  nothing is silently overwritten. An owner correction lands with
  confidence 1.0 and kind ``standing_rule`` by default: corrections
  outrank inferences.
- ``consult`` is the read agents use before acting ("what has the
  owner said about X?") — one field, current value, or None. Absence
  is reported as absence: the service never fills a field by guessing.
- ``render_profile`` produces the injection block (standing rules
  first) for session-start context packs, e.g. alongside
  TASK-IG2-MEM-01's capture/inject pack.

Field names are free-form (the model grows with the owner), but every
field must declare its kind — an unclassified claim about the owner
does not enter the model. All methods return dicts and never raise
into the caller.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.memory.pipeline.write_service import MemoryWriteService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

logger = logging.getLogger(__name__)

PROFILE_SOURCE = "user_model_profile"
PATTERN_TAG = "hermes-user-model"

FIELD_KINDS = {"preference", "habit", "standing_rule", "fact"}
_KIND_ORDER = {"standing_rule": 0, "preference": 1, "habit": 2, "fact": 3}
_MAX_HISTORY_PER_FIELD = 10

#: Fields the model is seeded to expect (documentation value only —
#: updates are not restricted to this list).
KNOWN_FIELDS = {
    "preferred_name": "preference",
    "timezone": "fact",
    "briefing_time": "preference",
    "primary_channel": "preference",
    "voice_priority": "standing_rule",
    "spend_policy": "standing_rule",
    "report_cadence": "preference",
    "trading_posture": "standing_rule",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render(fields: Dict[str, Dict[str, Any]], subject: str) -> str:
    """Human-readable rendering stored as the record's content."""
    lines = [f"User model — {subject} ({len(fields)} field(s)):"]
    for name in sorted(fields, key=lambda n: (_KIND_ORDER.get(fields[n].get("kind", "fact"), 3), n)):
        entry = fields[name]
        lines.append(f"- [{entry.get('kind')}] {name}: {entry.get('value')}")
    return "\n".join(lines)


class UserModelService:
    """Maintained, inspectable structured profile of the owner."""

    # ------------------------------------------------------------------
    # storage helpers
    # ------------------------------------------------------------------
    @classmethod
    def _current_record(
        cls, db: Session, *, actor_name: str, subject: str, tenant_id: Optional[str]
    ) -> Optional[MemoryRecord]:
        query = db.query(MemoryRecord).filter(
            MemoryRecord.source == PROFILE_SOURCE,
            MemoryRecord.lifecycle_state.in_(
                [LifecycleState.ACTIVE, LifecycleState.VERIFIED, LifecycleState.CANDIDATE]
            ),
        )
        if tenant_id:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        candidates = [
            r for r in query.all()
            if (r.agent_id == actor_name or r.owner_agent == actor_name)
            and (r.provenance or {}).get("subject") == subject
        ]
        if not candidates:
            return None
        # Newest version wins (highest version, then latest creation).
        return max(
            candidates,
            key=lambda r: (
                int((r.provenance or {}).get("profile_version") or 0),
                r.created_at.timestamp() if r.created_at else 0.0,
                r.id,
            ),
        )

    @classmethod
    def get_profile(
        cls, db: Session, *, actor_name: str, subject: str = "owner", tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """The full structured profile (empty fields when none exists —
        reported as such, never invented)."""
        record = cls._current_record(db, actor_name=actor_name, subject=subject, tenant_id=tenant_id)
        if record is None:
            return {"exists": False, "subject": subject, "fields": {}, "version": 0, "record_id": None}
        prov = record.provenance or {}
        return {
            "exists": True,
            "subject": subject,
            "fields": prov.get("fields") or {},
            "version": int(prov.get("profile_version") or 0),
            "record_id": record.id,
        }

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    @classmethod
    def update_field(
        cls,
        db: Session,
        *,
        actor_name: str,
        field: str,
        value: Any,
        kind: str,
        subject: str = "owner",
        source_ref: Optional[str] = None,
        confidence: float = 0.8,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set one profile field, versioning the profile record.

        Returns the new value, the previous value (or None), and whether
        this was a change — callers can see exactly what the model
        learned and what it replaced.
        """
        kind = (kind or "").strip().lower()
        if kind not in FIELD_KINDS:
            return {"updated": False, "reason": f"unknown_kind:{kind}", "field": field}
        if not field or not field.strip():
            return {"updated": False, "reason": "empty_field", "field": field}
        if value is None or (isinstance(value, str) and not value.strip()):
            return {"updated": False, "reason": "empty_value", "field": field}

        current = cls.get_profile(db, actor_name=actor_name, subject=subject, tenant_id=tenant_id)
        fields: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in (current["fields"] or {}).items()}
        previous = fields.get(field, {}).get("value")
        entry = fields.get(field) or {"history": []}
        history = list(entry.get("history") or [])
        if previous is not None and previous != value:
            history.append({"value": previous, "replaced_at": _now_iso(), "source_ref": entry.get("source_ref")})
        entry.update(
            {
                "value": value,
                "kind": kind,
                "confidence": confidence,
                "source_ref": source_ref,
                "updated_at": _now_iso(),
                "update_count": int(entry.get("update_count") or 0) + 1,
                "history": history[-_MAX_HISTORY_PER_FIELD:],
            }
        )
        fields[field] = entry
        new_version = int(current["version"] or 0) + 1
        try:
            result = MemoryWriteService.execute_pipeline(
                db,
                content_text=_render(fields, subject),
                caller_name=actor_name,
                tenant_id=tenant_id,
                memory_type=MemoryType.PREFERENCE,
                source=PROFILE_SOURCE,
                provenance={
                    "pattern": PATTERN_TAG,
                    "subject": subject,
                    "profile_version": new_version,
                    "fields": fields,
                },
                importance=0.85,
                confidence=0.95,
                allow_duplicates=True,
            )
        except Exception as exc:
            logger.warning("[USER-MODEL] profile write refused for %s: %s", actor_name, exc)
            return {"updated": False, "reason": f"pipeline_refused: {type(exc).__name__}", "field": field}
        superseded = False
        if current.get("record_id"):
            try:
                from core.memory.service import MemoryService

                MemoryService.supersede_memory(
                    db, current["record_id"], result.record.id, actor_name=actor_name,
                    reason=f"user-model profile v{new_version}",
                )
                superseded = True
            except Exception as exc:
                logger.info("[USER-MODEL] previous profile not superseded (newest version still wins): %s", exc)
        return {
            "updated": True,
            "field": field,
            "value": value,
            "previous_value": previous,
            "changed": previous != value,
            "version": new_version,
            "record_id": result.record.id,
            "superseded_previous": superseded,
        }

    @classmethod
    def learn_from_correction(
        cls,
        db: Session,
        *,
        actor_name: str,
        field: str,
        value: Any,
        subject: str = "owner",
        source_ref: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """An owner correction is a standing rule at full confidence —
        the strongest signal the model can hold."""
        return cls.update_field(
            db,
            actor_name=actor_name,
            field=field,
            value=value,
            kind="standing_rule",
            subject=subject,
            source_ref=source_ref,
            confidence=1.0,
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------
    # reads agents use
    # ------------------------------------------------------------------
    @classmethod
    def consult(
        cls, db: Session, *, actor_name: str, field: str, subject: str = "owner", tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """One field's current entry, or an explicit absence."""
        profile = cls.get_profile(db, actor_name=actor_name, subject=subject, tenant_id=tenant_id)
        entry = (profile["fields"] or {}).get(field)
        if entry is None:
            return {"found": False, "field": field, "value": None}
        return {
            "found": True,
            "field": field,
            "value": entry.get("value"),
            "kind": entry.get("kind"),
            "confidence": entry.get("confidence"),
            "updated_at": entry.get("updated_at"),
            "source_ref": entry.get("source_ref"),
        }

    @classmethod
    def render_profile(
        cls, db: Session, *, actor_name: str, subject: str = "owner", tenant_id: Optional[str] = None
    ) -> str:
        """Injection block for session-start context (standing rules first)."""
        profile = cls.get_profile(db, actor_name=actor_name, subject=subject, tenant_id=tenant_id)
        if not profile["exists"] or not profile["fields"]:
            return f"User model — {subject}: (no fields recorded yet — nothing assumed)"
        return _render(profile["fields"], subject)
