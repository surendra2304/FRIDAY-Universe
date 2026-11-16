"""
Capture → compress → inject session memory for Memora (TASK-IG2-MEM-01).

Pattern adapted from agentmemory (Apache-2.0, rohitg00/agentmemory):
its native hooks CAPTURE what an agent does in a session (tool calls,
decisions, corrections), COMPRESS the session into searchable memory,
and INJECT the relevant slice back at the start of the next session.
agentmemory itself is a Node/TypeScript server for coding-agent CLIs —
it cannot run on the ~180 MB Python fleet — so the pattern lands here
as a Memora service over Memora's own write pipeline and hybrid search:

- ``capture_event`` — one session event → one EPISODIC record through
  ``MemoryWriteService`` (identity, namespace, dedupe and policy all
  stay the pipeline's job). Content is secret-SCRUBBED first using the
  write pipeline's own scanner patterns: agentmemory scrubs secrets
  before storage, and a captured tool call is exactly where a leaked
  credential would otherwise be memorised forever. If scrubbing cannot
  make the content clean, the event is NOT stored and the caller is
  told why — a dropped event beats a memorised secret.
- ``compress_session`` — the session's events → one digest record
  (deterministic extractive compression: per-kind first lines,
  duplicates collapsed, length-capped; no LLM, no invented content),
  linked to its sources in provenance, then promoted to SEMANTIC via
  Memora's evidence-checked promotion workflow when policy grants it
  (direct SEMANTIC writes are service-identity-only by design).
  Idempotent per event set.
- ``build_session_context`` / ``handoff`` — INJECT: hybrid recall
  (BM25 + semantic + graph) formatted as a session-start briefing, and
  a handoff pack (compressed summary + fresh context) for the next
  session — agentmemory's session-handoff, Memora-native.

Everything returns plain dicts and never raises into the caller: a
capture failure is reported in the result, not hidden and not fatal.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.memory.pipeline.secret_scanner import SecretScanner
from core.memory.pipeline.write_service import MemoryWriteService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

logger = logging.getLogger(__name__)

CAPTURE_SOURCE = "session_capture"
COMPRESSION_SOURCE = "session_compression"
PATTERN_TAG = "agentmemory-capture-compress-inject"

#: Event kinds the capture hooks emit. Free-form kinds are normalised to
#: "observation" rather than rejected — capture must never lose an event
#: over a label.
KNOWN_KINDS = {"tool_call", "decision", "correction", "observation", "file_edit", "note"}

_MAX_DIGEST_CHARS = 2000
_MAX_EVENTS_PER_SESSION = 500


def scrub_secrets(content: str) -> tuple[str, List[str]]:
    """Replace every scanner-matching secret span with ``[REDACTED]``.

    Returns (cleaned_content, matched_pattern_names). Uses the write
    pipeline's own pattern set so capture and storage agree on what a
    secret is.
    """
    cleaned = content
    matched: List[str] = []
    for name, pattern in SecretScanner.SECRET_PATTERNS:
        if pattern.search(cleaned):
            matched.append(name)
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned, matched


class SessionCaptureService:
    """Capture-compress-inject over Memora's pipeline + hybrid search."""

    # ------------------------------------------------------------------
    # CAPTURE
    # ------------------------------------------------------------------
    @classmethod
    def capture_event(
        cls,
        db: Session,
        *,
        actor_name: str,
        session_id: str,
        kind: str,
        content: str,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store one session event as an EPISODIC memory (secret-scrubbed)."""
        kind = (kind or "observation").strip().lower()
        if kind not in KNOWN_KINDS:
            kind = "observation"
        if not content or not content.strip():
            return {"stored": False, "reason": "empty_content"}
        cleaned, matched = scrub_secrets(content)
        residual = SecretScanner.scan_content(cleaned)
        if residual:
            # Scrubbing could not make this safe (e.g. a pattern that
            # detects but does not localise). Drop the event, say so.
            logger.warning(
                "[CAPTURE] dropped session event for %s: unscrubbable secret types %s",
                actor_name, residual,
            )
            return {"stored": False, "reason": "unscrubbable_secret", "secret_types": residual}
        try:
            result = MemoryWriteService.execute_pipeline(
                db,
                content_text=cleaned,
                caller_name=actor_name,
                tenant_id=tenant_id,
                task_id=task_id,
                memory_type=MemoryType.EPISODIC,
                source=CAPTURE_SOURCE,
                provenance={
                    "pattern": PATTERN_TAG,
                    "session_id": session_id,
                    "event_kind": kind,
                    "scrubbed_secret_types": matched,
                },
                importance=0.5,
                confidence=0.9,
            )
        except Exception as exc:  # pipeline refusal (policy/dedupe gates) — reported, not hidden
            logger.warning("[CAPTURE] write pipeline refused event for %s: %s", actor_name, exc)
            return {"stored": False, "reason": f"pipeline_refused: {type(exc).__name__}"}
        return {
            "stored": True,
            "id": result.record.id,
            "duplicate": bool(result.is_duplicate),
            "scrubbed_secret_types": matched,
            "kind": kind,
            "session_id": session_id,
        }

    # ------------------------------------------------------------------
    # COMPRESS
    # ------------------------------------------------------------------
    @classmethod
    def _session_events(
        cls, db: Session, *, actor_name: str, session_id: str, tenant_id: Optional[str]
    ) -> List[MemoryRecord]:
        query = db.query(MemoryRecord).filter(
            MemoryRecord.source == CAPTURE_SOURCE,
            MemoryRecord.lifecycle_state.in_(
                [LifecycleState.ACTIVE, LifecycleState.VERIFIED, LifecycleState.CANDIDATE]
            ),
        )
        if tenant_id:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        records = (
            query.order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
            .limit(_MAX_EVENTS_PER_SESSION * 4)
            .all()
        )
        events = [
            r for r in records
            if (r.provenance or {}).get("session_id") == session_id
            and (r.agent_id == actor_name or r.owner_agent == actor_name)
        ]
        return events[:_MAX_EVENTS_PER_SESSION]

    @classmethod
    def _existing_compression(
        cls, db: Session, *, session_id: str, event_ids: List[str], tenant_id: Optional[str]
    ) -> Optional[MemoryRecord]:
        query = db.query(MemoryRecord).filter(MemoryRecord.source == COMPRESSION_SOURCE)
        if tenant_id:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        for record in query.all():
            prov = record.provenance or {}
            if prov.get("session_id") == session_id and set(prov.get("compressed_from") or []) == set(event_ids):
                return record
        return None

    @staticmethod
    def _digest(events: List[MemoryRecord], session_id: str) -> str:
        """Deterministic extractive digest: a header, then the first line
        of each event grouped by kind, duplicates collapsed. Nothing is
        paraphrased — lines are the events' own words."""
        lines = [f"Session {session_id}: {len(events)} captured event(s)."]
        seen: set[str] = set()
        by_kind: Dict[str, List[str]] = {}
        for event in events:
            kind = str((event.provenance or {}).get("event_kind") or "observation")
            first_line = re.sub(r"\s+", " ", (event.content_text or "")).strip().split(". ")[0][:220]
            if not first_line or first_line in seen:
                continue
            seen.add(first_line)
            by_kind.setdefault(kind, []).append(first_line)
        for kind in sorted(by_kind):
            lines.append(f"{kind}:")
            for line in by_kind[kind]:
                lines.append(f"- {line}")
        return "\n".join(lines)[:_MAX_DIGEST_CHARS]

    @classmethod
    def _attempt_promotion(
        cls,
        db: Session,
        *,
        digest_id: str,
        actor_name: str,
        event_ids: List[str],
    ) -> bool:
        """Best-effort evidence-checked promotion of a session digest.

        A denied or failed promotion is not a failed compression: the
        digest stays EPISODIC (still searchable) and the caller reports
        ``promoted_to_semantic: False``. This helper therefore NEVER
        raises. Two disciplines make that true even when the promotion
        dies mid-flush (the 2026-11-16 compress HTTP 500):

        - ``digest_id`` arrives as a plain string captured before the
          attempt, so the failure path never touches an ORM object;
        - on failure the session is rolled back FIRST. A failed flush
          leaves the transaction poisoned, and any ORM access before a
          rollback raises ``PendingRollbackError`` — which is what
          escaped the old inline handler (it formatted
          ``result.record.id`` in its log line) and became the 500. The
          digest row itself is already committed by the write pipeline,
          so the rollback discards only the failed promotion attempt.
        """
        try:
            from core.memory.service import MemoryService

            MemoryService.promote_to_semantic(
                db,
                digest_id,
                actor_name=actor_name,
                verification_evidence=event_ids[:32],
                target_confidence=0.85,
            )
            return True
        except Exception as exc:
            try:
                db.rollback()
            except Exception:  # pragma: no cover - rollback must never mask the outcome
                logger.warning(
                    "[CAPTURE] rollback after failed promotion of %s failed",
                    digest_id, exc_info=True,
                )
            logger.info(
                "[CAPTURE] digest %s stays EPISODIC (promotion not granted: %s)",
                digest_id, exc,
            )
            return False

    @classmethod
    def compress_session(
        cls,
        db: Session,
        *,
        actor_name: str,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compress one session's captured events into a SEMANTIC digest."""
        events = cls._session_events(db, actor_name=actor_name, session_id=session_id, tenant_id=tenant_id)
        if not events:
            return {"compressed": False, "reason": "no_events", "session_id": session_id}
        event_ids = [e.id for e in events]
        existing = cls._existing_compression(db, session_id=session_id, event_ids=event_ids, tenant_id=tenant_id)
        if existing is not None:
            # Idempotent per event set — but promotion is part of the
            # compress outcome, and a digest whose promotion was denied
            # or crashed on its first compress would otherwise stay
            # EPISODIC forever: repeat calls took this path and never
            # retried (and the response did not even carry the outcome).
            # Retry the promotion for a not-yet-SEMANTIC digest so
            # compress heals itself; the attempt is policy-checked again
            # inside promote_to_semantic and degrades to
            # promoted_to_semantic: False, never to an exception.
            promoted = existing.memory_type == MemoryType.SEMANTIC
            if not promoted:
                promoted = cls._attempt_promotion(
                    db,
                    digest_id=existing.id,
                    actor_name=actor_name,
                    event_ids=event_ids,
                )
            return {
                "compressed": True,
                "id": existing.id,
                "already_existed": True,
                "promoted_to_semantic": promoted,
                "event_count": len(events),
                "session_id": session_id,
            }
        digest = cls._digest(events, session_id)
        try:
            result = MemoryWriteService.execute_pipeline(
                db,
                content_text=digest,
                caller_name=actor_name,
                tenant_id=tenant_id,
                memory_type=MemoryType.EPISODIC,
                source=COMPRESSION_SOURCE,
                provenance={
                    "pattern": PATTERN_TAG,
                    "session_id": session_id,
                    "compressed_from": event_ids,
                    "event_count": len(events),
                },
                importance=0.7,
                confidence=0.85,
                allow_duplicates=True,
            )
        except Exception as exc:
            # A pipeline failure can leave the transaction poisoned;
            # roll back before returning so callers that reuse the
            # session (handoff builds its context pack on it next) are
            # not handed a dead session.
            try:
                db.rollback()
            except Exception:  # pragma: no cover - the refusal result stands either way
                logger.warning("[CAPTURE] rollback after refused compression write failed", exc_info=True)
            logger.warning("[CAPTURE] compression write refused for %s: %s", actor_name, exc)
            return {"compressed": False, "reason": f"pipeline_refused: {type(exc).__name__}", "session_id": session_id}
        # The pipeline deliberately restricts DIRECT semantic writes to
        # the memora service identity; everyone else promotes through
        # the evidence-checked workflow. The digest's evidence is
        # exactly the events it compresses, so promote with those refs.
        # Capture the id as a plain string NOW: after the pipeline's
        # commit the record is expired, and the promotion failure path
        # must never reach for an ORM attribute (see _attempt_promotion).
        digest_id = result.record.id
        promoted = cls._attempt_promotion(
            db,
            digest_id=digest_id,
            actor_name=actor_name,
            event_ids=event_ids,
        )
        return {
            "compressed": True,
            "id": digest_id,
            "already_existed": False,
            "promoted_to_semantic": promoted,
            "event_count": len(events),
            "session_id": session_id,
        }

    # ------------------------------------------------------------------
    # INJECT
    # ------------------------------------------------------------------
    @classmethod
    def build_session_context(
        cls,
        db: Session,
        *,
        actor_name: str,
        query: str,
        limit: int = 5,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Session-start injection pack: hybrid recall for ``query``,
        formatted as a briefing the agent can prepend to its context."""
        from core.memory.search_service import SearchService

        hits = SearchService.hybrid_search(
            db,
            query_text=query,
            actor_name=actor_name,
            tenant_id=tenant_id or "default",
            limit=limit,
        )
        lines = [f"Relevant memory for: {query}"]
        dicts = []
        for hit in hits:
            data = hit.to_dict()
            dicts.append(data)
            text = re.sub(r"\s+", " ", str(data.get("content_text") or "")).strip()[:300]
            lines.append(f"- [{data.get('memory_type')} · score {data.get('final_score')}] {text}")
        if not hits:
            lines.append("(no relevant memory found — nothing was invented to fill this)")
        return {"context": "\n".join(lines), "hits": dicts, "hit_count": len(hits)}

    @classmethod
    def handoff(
        cls,
        db: Session,
        *,
        actor_name: str,
        session_id: str,
        next_query: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Session handoff: compress the ending session, then build the
        next session's injection pack in one call."""
        compression = cls.compress_session(
            db, actor_name=actor_name, session_id=session_id, tenant_id=tenant_id
        )
        context = cls.build_session_context(
            db, actor_name=actor_name, query=next_query, tenant_id=tenant_id
        )
        return {"compression": compression, "context": context}
