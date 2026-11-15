"""
Memora Retention & Forgetting Policy (TASK-MEM-006).

Before this module, ``MemoryRecord.expires_at`` was caller-supplied only:
nothing classified a write as transient or durable, nothing assigned an
expiry by policy, and a record whose expiry had passed was merely *hidden*
from query/search results while its row, embedding, and graph edges were
kept forever. "Expiry" was cosmetic and "forget" depended on the caller
remembering to pass ``hard=true``.

This module is the policy layer that makes both real:

* **Retention classes.** Every memory type maps to a class with a default
  time-to-live (see ``DEFAULT_POLICY``). TRANSIENT and SHORT_TERM records
  receive an ``expires_at`` at write time; DURABLE records never expire.
* **Expiry is erasure.** :class:`RetentionSweeper` hard-erases records whose
  ``expires_at`` has passed, through the same multi-store convergence path
  as an explicit hard delete (relational row, vector embedding, graph
  edges, cache), leaving a ``DeletionTombstone`` per record.
* **Forget is erasure, verified.** ``MemoryService.forget_memory`` always
  hard-erases and then verifies absence store by store
  (``MemoryService.verify_erasure``). Soft delete remains an internal
  lifecycle transition; it is never presented as forgetting.

Composition with the zero-work-lost HorizonSweeper: condensation horizons
(working 30 days, episodic 90 days in ``memora_upgrade.consolidation``)
are age-based and run *before* these TTLs lapse, so milestone summaries
(SEMANTIC, hence DURABLE here) are promoted first and the raw records are
erased at expiry. Callers that need a shorter-lived record pass an
explicit ``expires_at`` or a provenance ``retention_ttl_hours`` hint;
callers that need a record kept forever pass ``retention_class=durable``.

The full spec lives in ``Memora/docs/RETENTION_AND_FORGETTING_POLICY.md``.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from storage.relational.models import MemoryType

logger = logging.getLogger(__name__)


class RetentionClass(str, Enum):
    """How long a memory is kept before the expiry sweep erases it."""

    TRANSIENT = "transient"    # Working context: expires, then erased.
    SHORT_TERM = "short_term"  # Episodic history: kept longer, then erased.
    DURABLE = "durable"        # Facts: no expiry; erased only on request.


#: Default (class, TTL) per memory type. TTLs are never shorter than the
#: HorizonSweeper condensation horizons for the types it condenses
#: (working 30d, episodic 90d) so zero-work-lost promotion runs first.
DEFAULT_POLICY: Dict[MemoryType, tuple[RetentionClass, Optional[timedelta]]] = {
    MemoryType.WORKING: (RetentionClass.TRANSIENT, timedelta(days=30)),
    MemoryType.TOOL: (RetentionClass.TRANSIENT, timedelta(days=7)),
    MemoryType.EPISODIC: (RetentionClass.SHORT_TERM, timedelta(days=90)),
    MemoryType.EXPERIENCE: (RetentionClass.SHORT_TERM, timedelta(days=90)),
    MemoryType.SEMANTIC: (RetentionClass.DURABLE, None),
    MemoryType.PREFERENCE: (RetentionClass.DURABLE, None),
    MemoryType.PROCEDURAL: (RetentionClass.DURABLE, None),
    MemoryType.DECISION: (RetentionClass.DURABLE, None),
    MemoryType.RELATIONSHIP: (RetentionClass.DURABLE, None),
    MemoryType.PROJECT: (RetentionClass.DURABLE, None),
    MemoryType.SYSTEM: (RetentionClass.DURABLE, None),
}

_MIN_TTL_HOURS = 1.0
_MAX_TTL_HOURS = 24.0 * 365  # one year; longer retention means "durable"


def _provenance_hints(provenance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return provenance if isinstance(provenance, dict) else {}


def classify_retention(
    memory_type: MemoryType,
    provenance: Optional[Dict[str, Any]] = None,
) -> RetentionClass:
    """Return the retention class for a write.

    A provenance ``retention_class`` hint (``transient`` / ``short_term`` /
    ``durable``) wins over the per-type default; an unrecognised hint is
    ignored so a malformed write can never silently change retention.
    """
    hints = _provenance_hints(provenance)
    raw = hints.get("retention_class")
    if isinstance(raw, str):
        try:
            return RetentionClass(raw.strip().lower())
        except ValueError:
            logger.warning(
                "Ignoring unrecognised retention_class hint %r for %s",
                raw, memory_type,
            )
    return DEFAULT_POLICY[memory_type][0]


def _env_ttl_hours(memory_type: MemoryType) -> Optional[float]:
    """Operator override: MEMORA_RETENTION_TTL_HOURS_<TYPE>=<hours>."""
    raw = os.getenv(f"MEMORA_RETENTION_TTL_HOURS_{memory_type.value.upper()}")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("Ignoring non-numeric retention TTL env override %r", raw)
        return None


def retention_ttl(
    memory_type: MemoryType,
    provenance: Optional[Dict[str, Any]] = None,
) -> Optional[timedelta]:
    """Return the time-to-live for a write, or None for durable records.

    Precedence: provenance ``retention_ttl_hours`` > environment override >
    per-type default. A ``durable`` classification always yields None unless
    an explicit TTL hint/override is present (an explicit TTL is the caller
    asking for expiry, and that request is honoured).
    """
    hints = _provenance_hints(provenance)
    ttl_hours: Optional[float] = None

    raw_hint = hints.get("retention_ttl_hours")
    if isinstance(raw_hint, (int, float)) and not isinstance(raw_hint, bool):
        ttl_hours = float(raw_hint)
    if ttl_hours is None:
        ttl_hours = _env_ttl_hours(memory_type)
    if ttl_hours is None:
        if classify_retention(memory_type, provenance) is RetentionClass.DURABLE:
            return None
        default_ttl = DEFAULT_POLICY[memory_type][1]
        return default_ttl

    clamped = min(max(ttl_hours, _MIN_TTL_HOURS), _MAX_TTL_HOURS)
    if clamped != ttl_hours:
        logger.warning(
            "Retention TTL %sh for %s clamped to %sh", ttl_hours, memory_type, clamped
        )
    return timedelta(hours=clamped)


def retention_expires_at(
    memory_type: MemoryType,
    provenance: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """Compute the policy ``expires_at`` for a new record (None = durable)."""
    ttl = retention_ttl(memory_type, provenance)
    if ttl is None:
        return None
    return (now or datetime.now(timezone.utc)) + ttl


def resolve_create_expires_at(
    memory_type: MemoryType,
    explicit_expires_at: Optional[datetime],
    provenance: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """Write-path rule: an explicit caller expiry always wins; otherwise the
    retention policy assigns one (or None for durable records)."""
    if explicit_expires_at is not None:
        return explicit_expires_at
    return retention_expires_at(memory_type, provenance, now=now)


class RetentionSweeper:
    """Hard-erases records whose retention has lapsed.

    Each expired record goes through ``MemoryService._hard_erase_record``
    (the same convergence path as an explicit hard delete) and is committed
    individually, so one failing record cannot roll back the rest; a record
    whose erasure does not converge keeps a PENDING_RETRY tombstone for the
    existing self-healing worker. The sweep never touches records without
    an ``expires_at`` — durable facts persist until explicitly forgotten.
    """

    @staticmethod
    def run_expiry_sweep(
        db,
        tenant_id: Optional[str] = None,
        now: Optional[datetime] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        from sqlalchemy import or_  # local import: keep module import light

        from core.memory.service import MemoryService
        from storage.relational.models import MemoryRecord

        now = now or datetime.now(timezone.utc)
        query = db.query(MemoryRecord).filter(
            MemoryRecord.expires_at.isnot(None),
            or_(MemoryRecord.expires_at <= now),
        )
        if tenant_id:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        expired = (
            query.order_by(MemoryRecord.expires_at.asc()).limit(limit).all()
        )

        erased_ids: list[str] = []
        pending_ids: list[str] = []
        errors: list[Dict[str, str]] = []
        for record in expired:
            memory_id = record.id
            try:
                tombstone = MemoryService._hard_erase_record(db, record)
                db.commit()
                erased_ids.append(memory_id)
                if not tombstone.is_converged():
                    pending_ids.append(memory_id)
            except Exception as exc:  # one bad record must not stop the sweep
                db.rollback()
                logger.error(
                    "Retention sweep failed to erase %s: %s", memory_id, exc
                )
                errors.append({"memory_id": memory_id, "error": str(exc)})

        return {
            "status": "completed",
            "swept_at": now.isoformat(),
            "tenant_id": tenant_id,
            "expired_found": len(expired),
            "erased": len(erased_ids),
            "erased_ids": erased_ids,
            "pending_retry": pending_ids,
            "errors": errors,
        }
