"""
Memora/core/memory/confidence_reinforcement.py — Confidence that learns from use.

TASK-MEM-031: agentmemory adaptation (rohitg00/agentmemory, Apache-2.0,
~30.6k stars, 2026-11-25).

agentmemory's confidence model (test/confidence.test.ts, src/functions/
relations.ts): a memory — and each relation between memories — carries a
confidence in [0, 1], computed by default from co-occurrence + recency,
explicitly overridable, clamped to [0, 1]; recall sorts by confidence
descending and callers can filter by a minimum confidence. Memora already
stores a ``confidence`` column on every record and already uses it as a
tiebreaker in hybrid ranking (core/memory/search_service.py sorts by
final score, then confidence, then recency) — but nothing ever *moved* a
record's confidence after it was written, and the in-memory SM-2
reinforcement engine (apps/api/routers/memory_reinforcement_engine.py)
never touches the stored record. Confidence was write-once. This module
closes that loop, Memora-native and persisted:

- ``reinforce_on_recall`` — the explicit path: an agent reports which of
  the memories it was served were actually useful, and each served
  record's confidence moves a bounded step (+0.05 useful, -0.02 not
  useful), clamped to [0.05, 0.99]. Actor-scoped (only the actor's own
  records move) and tenant-scoped; provenance is never touched (it may
  carry an HMAC signature — Safety Invariant 2).
- ``reinforce_compressed_events`` — the implicit path: when a session
  digest is promoted to SEMANTIC through the evidence-checked workflow,
  the source events proved useful enough to survive the gate, so each
  gains +0.03. Called from ``SessionCaptureService.compress_session``
  only when promotion was just granted in that call — never on the
  idempotent repeat, so a digest cannot farm confidence by re-compress.
- ``confidence_weighted_score`` / ``confidence_weighted_sort`` — the
  recall side of agentmemory's rule: rank by final score *weighted by*
  confidence (0.5 + 0.5 * confidence), so confidence moves order instead
  of merely breaking ties. Applied in ``SessionCaptureService.
  build_session_context`` — the session-start inject path — leaving the
  hybrid search's own ordering contracts untouched.

Every function here never raises into its caller: a reinforcement failure
is reported in the result dict, never fatal to the capture/inject path
that called it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from storage.relational.models import MemoryRecord

logger = logging.getLogger(__name__)

#: agentmemory clamps confidence to [0, 1]; Memora keeps a margin off the
#: rails so a record can always move again in either direction.
CONFIDENCE_MIN = 0.05
CONFIDENCE_MAX = 0.99

#: Bounded per-report steps. A single report can never swing a record.
USEFUL_STEP = 0.05
NOT_USEFUL_STEP = 0.02
#: Implicit step for events whose digest just passed the promotion gate.
COMPRESS_STEP = 0.03

MAX_REINFORCE_IDS = 50


def clamp_confidence(value: float) -> float:
    """Clamp a confidence value into the reinforcement band."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return CONFIDENCE_MIN
    if number != number:  # NaN guard: NaN comparisons are False, so clamp explicitly
        return CONFIDENCE_MIN
    return max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, number))


def confidence_weighted_score(final_score: float, confidence: float) -> float:
    """Rank weight: relevance * (0.5 + 0.5 * confidence).

    A record at confidence 1.0 keeps its full score; at 0.05 it keeps
    just over half. Confidence moves order; it never invents relevance.
    """
    try:
        score = float(final_score)
    except (TypeError, ValueError):
        score = 0.0
    return score * (0.5 + 0.5 * clamp_confidence(confidence))


def confidence_weighted_sort(hits: List[Any]) -> List[Any]:
    """Re-sort recall hits by confidence-weighted score, descending.

    ``hits`` are ``SearchResultItem`` objects (``.final_score`` and
    ``.record.confidence``); ties fall back to raw score, then record id
    for determinism. Returns a new list; the input order is untouched.
    """
    return sorted(
        hits,
        key=lambda h: (
            -round(confidence_weighted_score(h.final_score, h.record.confidence), 4),
            -round(float(h.final_score), 4),
            h.record.id,
        ),
    )


def _visible_to_actor(record: MemoryRecord, actor_name: str, tenant_id: Optional[str]) -> Optional[str]:
    """Return None when the actor may reinforce this record, else the skip reason."""
    if record.agent_id != actor_name and record.owner_agent != actor_name:
        return "not_owned_by_actor"
    if tenant_id is not None and record.tenant_id != tenant_id:
        return "tenant_mismatch"
    return None


def reinforce_on_recall(
    db: Session,
    *,
    record_ids: List[str],
    useful_ids: List[str],
    actor_name: str,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move stored confidence from an agent's recall-outcome report.

    ``record_ids`` are the memories the agent was served;
    ``useful_ids`` the subset it actually used. Served-but-unused
    records lose a little confidence; useful ones gain a little. Both
    steps are bounded and the result is clamped to [0.05, 0.99].
    """
    seen: List[str] = []
    for record_id in record_ids or []:
        if isinstance(record_id, str) and record_id.strip() and record_id not in seen:
            seen.append(record_id)
    useful = {u for u in (useful_ids or []) if isinstance(u, str)}
    if not seen:
        return {"updated": [], "skipped": [], "actor": actor_name, "reason": "no_records"}
    if len(seen) > MAX_REINFORCE_IDS:
        return {
            "updated": [],
            "skipped": [{"id": rid, "reason": "batch_too_large"} for rid in seen],
            "actor": actor_name,
            "reason": "batch_too_large",
        }
    updated: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    try:
        records = db.query(MemoryRecord).filter(MemoryRecord.id.in_(seen)).all()
        by_id = {r.id: r for r in records}
        for record_id in seen:
            record = by_id.get(record_id)
            if record is None:
                skipped.append({"id": record_id, "reason": "not_found"})
                continue
            blocked = _visible_to_actor(record, actor_name, tenant_id)
            if blocked is not None:
                skipped.append({"id": record_id, "reason": blocked})
                continue
            before = float(record.confidence or 0.0)
            step = USEFUL_STEP if record_id in useful else -NOT_USEFUL_STEP
            after = clamp_confidence(before + step)
            record.confidence = after
            updated.append(
                {"id": record_id, "before": round(before, 4), "after": round(after, 4), "useful": record_id in useful}
            )
        db.commit()
    except Exception as exc:  # reinforcement must never break the caller
        try:
            db.rollback()
        except Exception:  # pragma: no cover - the report stands either way
            logger.warning("[REINFORCE] rollback after failed reinforcement failed", exc_info=True)
        logger.warning("[REINFORCE] reinforcement failed for %s: %s", actor_name, exc)
        return {"updated": [], "skipped": skipped, "actor": actor_name, "error": f"{type(exc).__name__}: {exc}"}
    return {"updated": updated, "skipped": skipped, "actor": actor_name}


def reinforce_compressed_events(
    db: Session,
    *,
    event_ids: List[str],
    actor_name: str,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Implicit reinforcement: a digest just passed the promotion gate,
    so its source events gain a small confidence step.

    Called only when promotion was granted in the same compress call.
    Bounded (+0.03 each), clamped, actor/tenant-scoped, never raises.
    """
    if not event_ids:
        return {"updated": [], "skipped": [], "actor": actor_name, "reason": "no_events"}
    updated: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    try:
        records = db.query(MemoryRecord).filter(MemoryRecord.id.in_(list(dict.fromkeys(event_ids)))).all()
        by_id = {r.id: r for r in records}
        for event_id in dict.fromkeys(event_ids):
            record = by_id.get(event_id)
            if record is None:
                skipped.append({"id": event_id, "reason": "not_found"})
                continue
            blocked = _visible_to_actor(record, actor_name, tenant_id)
            if blocked is not None:
                skipped.append({"id": event_id, "reason": blocked})
                continue
            before = float(record.confidence or 0.0)
            after = clamp_confidence(before + COMPRESS_STEP)
            record.confidence = after
            updated.append({"id": event_id, "before": round(before, 4), "after": round(after, 4)})
        db.commit()
    except Exception as exc:  # reinforcement must never break compression
        try:
            db.rollback()
        except Exception:  # pragma: no cover - the report stands either way
            logger.warning("[REINFORCE] rollback after failed compress reinforcement failed", exc_info=True)
        logger.warning("[REINFORCE] compress reinforcement failed for %s: %s", actor_name, exc)
        return {"updated": [], "skipped": skipped, "actor": actor_name, "error": f"{type(exc).__name__}: {exc}"}
    return {"updated": updated, "skipped": skipped, "actor": actor_name}
