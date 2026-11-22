"""Memory scope promotion — owner judgement (A) and auto-promotion (C).

Owner rule (2026-11-18, locked): memory promotion is BOTH

  (A) the owning agent promotes a memory (PRIVATE -> SHARED -> UNIVERSAL)
      on its own judgement, and
  (C) Memora auto-promotes when many agents repeatedly need the same memory.

Failed-experiment lessons are special: the lesson stays in the owner's
private memory AND goes universal, so a promotion to UNIVERSAL for such a
record creates a UNIVERSAL copy and leaves the original PRIVATE.

What existed before this module (verified on origin/main 2240ebb8):

  * (A) was half-built. An owner could create a memory as SHARED (write-time
    ``shared_with`` in ``core/memory/service.py`` / the write pipeline) and
    could share one memory with one peer via
    ``CollaborationService.contribute`` (``share_record_with``). But there
    was NO post-creation owner promotion to UNIVERSAL: UNIVERSAL authoring
    is reserved to the Memora service identity at write time
    (``MemoryService.create_memory`` refuses it for every other actor), so
    an owner could never complete the PRIVATE -> SHARED -> UNIVERSAL ladder
    for a memory it already owned.
  * (C) did not exist at all: nothing recorded cross-agent need, nothing
    counted repeated need, and nothing promoted on that evidence.

This module completes both paths on the existing primitives:

  * Scope moves use ``MemoryScopeType`` + ``memory_shared_agents`` via
    ``storage.relational.access_scope`` (the single visibility authority),
    so every read path honours a promotion immediately: the policy engine
    consults record scope for read/query since TASK-MEM-016 (MEM-014 G1 —
    before that fix the engine decided by namespace type only and a
    promoted record stayed unreadable to its audience).
  * Need signals and promotions are recorded as ``AuditLog`` rows — the
    existing, tenant-scoped audit trail — so no new table or migration is
    required and every promotion carries its evidence.
  * Promotion is monotonic (never demotes), idempotent (re-promoting to the
    current tier is a no-op that writes no second audit row), and refuses
    archived/deleted records. The one audited exception is
    ``MemoryPromotionService.revert_scope`` (TASK-MEM-015): it demotes a
    memory exactly one rung, back to the ``from_scope`` of its latest
    promotion audit row, and writes a ``MEMORY_SCOPE_DEMOTED`` row pointing
    at the promotion it undoes.

Thresholds for (C) are module constants, deliberately conservative:

  * PRIVATE -> SHARED:    >= 2 distinct non-owner agents, >= 3 needs total.
  * SHARED  -> UNIVERSAL: >= 4 distinct non-owner agents, >= 8 needs total,
    and >= 2 distinct needers who are NOT already on the SHARED allow-list
    (need beyond the current team — the same evidence that earned SHARED
    cannot, by itself, earn UNIVERSAL on the next sweep).

A sweep applies at most one rung per memory per run, so the ladder the
owner described (private -> inter-agent -> universal) is never skipped.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.identity.service import IdentityService
from storage.relational.access_scope import (
    SERVICE_AGENT,
    grant_shared_access,
    shared_membership,
)
from storage.relational.base import generate_uuid
from storage.relational.models import (
    SHARED_WITH_ALL_AGENTS,
    AuditLog,
    LifecycleState,
    MemoryRecord,
    MemoryScopeType,
    MemorySharedAgent,
    normalize_agent_name,
)

logger = logging.getLogger(__name__)

#: AuditLog action names written by this module.
ACTION_NEED = "MEMORY_NEED_RECORDED"
ACTION_PROMOTED = "MEMORY_SCOPE_PROMOTED"
ACTION_DEMOTED = "MEMORY_SCOPE_DEMOTED"

#: Promotion provenance paths recorded in audit details / copy provenance.
PATH_OWNER = "owner_judgement"
PATH_AUTO = "auto_repeated_need"

#: (C) thresholds — see module docstring.
SHARED_MIN_DISTINCT_AGENTS = 2
SHARED_MIN_TOTAL_NEEDS = 3
UNIVERSAL_MIN_DISTINCT_AGENTS = 4
UNIVERSAL_MIN_TOTAL_NEEDS = 8
UNIVERSAL_MIN_OUTSIDE_AGENTS = 2
DEFAULT_WINDOW_DAYS = 30

_SCOPE_ORDER = {
    MemoryScopeType.PRIVATE: 0,
    MemoryScopeType.SHARED: 1,
    MemoryScopeType.UNIVERSAL: 2,
}


class PromotionError(Exception):
    """Base for promotion failures (unknown agent / memory)."""


class PromotionPermissionError(PromotionError):
    """The caller is known but may not perform this promotion."""


def is_failed_experiment_lesson(record: MemoryRecord) -> bool:
    """True when a record is marked as a failed-experiment lesson.

    The marking lives in provenance, where experiment writers already put
    outcome metadata: ``failed_experiment: true``, an
    ``experiment_outcome`` of ``failed``/``failure``, or a ``lesson_type``
    of ``failed_experiment``.
    """
    provenance = record.provenance if isinstance(record.provenance, dict) else {}
    if provenance.get("failed_experiment") is True:
        return True
    outcome = str(provenance.get("experiment_outcome", "")).strip().lower()
    if outcome in {"failed", "failure"}:
        return True
    return str(provenance.get("lesson_type", "")).strip().lower() == "failed_experiment"


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_actor(db: Session, name: str, tenant_id: Optional[str]):
    actor = IdentityService.get_agent_by_name(db, name, tenant_id=tenant_id)
    if not actor:
        raise PromotionError(f"unknown agent '{name}' in tenant '{tenant_id or 'default'}'")
    return actor


def _resolve_record(db: Session, memory_id: str, tenant_id: str) -> MemoryRecord:
    record = (
        db.query(MemoryRecord)
        .filter(MemoryRecord.id == memory_id, MemoryRecord.tenant_id == tenant_id)
        .first()
    )
    if not record:
        raise PromotionError(f"memory '{memory_id}' not found")
    if record.lifecycle_state in (LifecycleState.DELETED, LifecycleState.ARCHIVED):
        raise PromotionPermissionError(
            f"memory '{memory_id}' is {record.lifecycle_state.value} and cannot be promoted"
        )
    return record


def _audit(
    db: Session,
    *,
    actor_id: Optional[str],
    memory_id: str,
    tenant_id: str,
    action: str,
    details: Dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        memory_id=memory_id,
        action=action,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry


class MemoryPromotionService:
    """Owner promotion (A), need recording, and auto-promotion sweep (C)."""

    # ------------------------------------------------------------ (A) owner
    @classmethod
    def promote_scope(
        cls,
        db: Session,
        *,
        owner_name: str,
        memory_id: str,
        target_scope: Any,
        shared_with: Optional[List[str]] = None,
        reason: str = "",
        tenant_id: Optional[str] = "default",
    ) -> Dict[str, Any]:
        """Promote one memory the caller owns to ``target_scope``.

        Only the owning agent (or the Memora service identity) may promote.
        Promotion is monotonic and idempotent. A failed-experiment lesson
        promoted to UNIVERSAL keeps its PRIVATE original and gains a
        UNIVERSAL copy instead of moving.
        """
        try:
            target = MemoryScopeType(str(target_scope).strip().upper())
        except ValueError:
            raise PromotionPermissionError(f"unknown target scope '{target_scope}'")

        actor = _resolve_actor(db, owner_name, tenant_id)
        record = _resolve_record(db, memory_id, actor.tenant_id)
        owner = normalize_agent_name(record.owner_agent)
        caller = normalize_agent_name(actor.name)
        if caller != SERVICE_AGENT and caller != owner:
            raise PromotionPermissionError(
                f"'{actor.name}' does not own memory '{memory_id}'; "
                "only the owning agent may promote its scope"
            )

        current = record.scope or MemoryScopeType.PRIVATE
        if _SCOPE_ORDER[target] < _SCOPE_ORDER[current]:
            raise PromotionPermissionError(
                f"promotion is monotonic: {current.value} cannot be demoted to {target.value}"
            )
        if target == current:
            return cls._result(record, status="already_at_scope", path=PATH_OWNER)

        targets: List[str] = []
        if target == MemoryScopeType.SHARED:
            for raw in shared_with or []:
                name = normalize_agent_name(raw)
                if name and name != owner and name not in targets:
                    targets.append(name)
            if not targets:
                raise PromotionPermissionError(
                    "promoting to SHARED requires at least one recipient in shared_with "
                    "(or '*' for every agent)"
                )

        try:
            result = cls._apply_promotion(
                db,
                record=record,
                target=target,
                shared_targets=targets,
                actor_id=actor.id,
                actor_name=caller,
                path=PATH_OWNER,
                reason=reason,
                evidence={},
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return result

    # ------------------------------------------------------------ undo (D)
    @classmethod
    def revert_scope(
        cls,
        db: Session,
        *,
        actor_name: str,
        memory_id: str,
        reason: str = "",
        tenant_id: Optional[str] = "default",
    ) -> Dict[str, Any]:
        """Revert the latest promotion of one memory by exactly one rung.

        TASK-MEM-015: promotion is monotonic through ``promote_scope`` (a
        demotion target is refused there), but every promotion must be
        reversible by one call. The revert reads the latest
        ``MEMORY_SCOPE_PROMOTED`` audit row — the audit trail is the source
        of truth for what the previous rung was — demotes the record to that
        ``from_scope``, removes only the allow-list rows that promotion
        granted, and writes a ``MEMORY_SCOPE_DEMOTED`` audit row pointing at
        the promotion it undoes. Only the owning agent (or the Memora
        service identity) may revert, the same actors allowed to promote.

        Refusals (all honest, no silent partial undo):
        * no promotion on record -> not found;
        * the latest promotion was already reverted -> ``already_reverted``
          no-op, idempotent;
        * the latest promotion created a UNIVERSAL dual copy of a
          failed-experiment lesson -> refused: the copy is a separate record
          and must be dealt with on its own;
        * the record's scope has moved since that promotion (promoted again
          or changed out of band) -> refused, so a revert never skips a rung.
        """
        actor = _resolve_actor(db, actor_name, tenant_id)
        record = _resolve_record(db, memory_id, actor.tenant_id)
        owner = normalize_agent_name(record.owner_agent)
        caller = normalize_agent_name(actor.name)
        if caller != SERVICE_AGENT and caller != owner:
            raise PromotionPermissionError(
                f"'{actor.name}' does not own memory '{memory_id}'; "
                "only the owning agent may revert its scope"
            )

        promotion = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == record.tenant_id,
                AuditLog.memory_id == record.id,
                AuditLog.action == ACTION_PROMOTED,
            )
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .first()
        )
        if promotion is None:
            raise PromotionError(f"memory '{memory_id}' has no promotion to revert")

        already = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == record.tenant_id,
                AuditLog.memory_id == record.id,
                AuditLog.action == ACTION_DEMOTED,
            )
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .first()
        )
        if already is not None:
            details = already.details if isinstance(already.details, dict) else {}
            if details.get("reverts_audit_id") == promotion.id:
                return {
                    "status": "already_reverted",
                    "memory_id": record.id,
                    "owner_agent": owner,
                    "scope": (record.scope or MemoryScopeType.PRIVATE).value,
                    "path": details.get("path", ""),
                    "reverts_audit_id": promotion.id,
                }

        details = promotion.details if isinstance(promotion.details, dict) else {}
        if details.get("failed_experiment_dual"):
            raise PromotionPermissionError(
                "this promotion created a separate UNIVERSAL copy of a "
                "failed-experiment lesson; revert the copy itself instead of "
                "demoting the original, which never moved"
            )
        try:
            from_scope = MemoryScopeType(str(details.get("from_scope", "")).strip().upper())
            to_scope = MemoryScopeType(str(details.get("to_scope", "")).strip().upper())
        except ValueError:
            raise PromotionError(
                f"promotion audit {promotion.id} carries an unreadable scope; "
                "refusing to revert"
            )
        current = record.scope or MemoryScopeType.PRIVATE
        if current != to_scope:
            raise PromotionPermissionError(
                f"memory '{memory_id}' is {current.value}, not {to_scope.value}; "
                "its scope moved after the promotion, so the revert would skip a rung"
            )

        try:
            granted = [
                normalize_agent_name(name)
                for name in (details.get("shared_with") or [])
            ]
            if granted:
                db.query(MemorySharedAgent).filter(
                    MemorySharedAgent.memory_id == record.id,
                    MemorySharedAgent.agent_name.in_(granted),
                ).delete(synchronize_session=False)
            record.scope = from_scope
            db.flush()
            _audit(
                db,
                actor_id=actor.id,
                memory_id=record.id,
                tenant_id=record.tenant_id,
                action=ACTION_DEMOTED,
                details={
                    "from_scope": to_scope.value,
                    "to_scope": from_scope.value,
                    "reverted_by": caller,
                    "reverts_audit_id": promotion.id,
                    "path": details.get("path", ""),
                    "reason": reason[:512],
                    "shared_with_revoked": granted,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {
            "status": "reverted",
            "memory_id": record.id,
            "owner_agent": owner,
            "scope": from_scope.value,
            "from_scope": to_scope.value,
            "to_scope": from_scope.value,
            "path": details.get("path", ""),
            "reverts_audit_id": promotion.id,
        }

    # ------------------------------------------------------- need recording
    @classmethod
    def record_need(
        cls,
        db: Session,
        *,
        requester_name: str,
        memory_id: str,
        reason: str = "",
        tenant_id: Optional[str] = "default",
    ) -> Dict[str, Any]:
        """Record that ``requester_name`` needs ``memory_id`` (path C input).

        A need is an audit row, not access: recording one grants nothing and
        discloses nothing beyond the memory id the requester already holds.
        The owner's own needs are meaningless (it already has the memory)
        and are reported as a no-op instead of inflating the evidence.
        """
        requester = _resolve_actor(db, requester_name, tenant_id)
        record = _resolve_record(db, memory_id, requester.tenant_id)
        if normalize_agent_name(requester.name) == normalize_agent_name(record.owner_agent):
            return {"status": "owner_need_ignored", "memory_id": memory_id}

        try:
            _audit(
                db,
                actor_id=requester.id,
                memory_id=record.id,
                tenant_id=record.tenant_id,
                action=ACTION_NEED,
                details={
                    "requester": normalize_agent_name(requester.name),
                    "owner_agent": normalize_agent_name(record.owner_agent),
                    "scope_at_need": (record.scope or MemoryScopeType.PRIVATE).value,
                    "reason": reason[:512],
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {"status": "need_recorded", "memory_id": memory_id}

    # ------------------------------------------------------------- (C) sweep
    @classmethod
    def need_evidence(
        cls,
        db: Session,
        record: MemoryRecord,
        *,
        window_days: int = DEFAULT_WINDOW_DAYS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate recorded needs for one memory inside the window."""
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)
        rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == record.tenant_id,
                AuditLog.memory_id == record.id,
                AuditLog.action == ACTION_NEED,
            )
            .all()
        )
        owner = normalize_agent_name(record.owner_agent)
        requesters: List[str] = []
        total = 0
        for row in rows:
            ts = _as_utc(row.timestamp)
            if ts is not None and ts < cutoff:
                continue
            details = row.details if isinstance(row.details, dict) else {}
            requester = normalize_agent_name(details.get("requester"))
            if not requester or requester == owner:
                continue
            total += 1
            if requester not in requesters:
                requesters.append(requester)
        members = set(shared_membership(db, record.id))
        outside = [
            name
            for name in requesters
            if name not in members and SHARED_WITH_ALL_AGENTS not in members
        ]
        return {
            "distinct_agents": len(requesters),
            "requesting_agents": sorted(requesters),
            "total_needs": total,
            "outside_agents": sorted(outside),
            "window_days": window_days,
        }

    @classmethod
    def evaluate_auto_promotion(
        cls, db: Session, record: MemoryRecord, *, window_days: int = DEFAULT_WINDOW_DAYS
    ) -> Optional[MemoryScopeType]:
        """Return the next scope rung the need evidence earns, or None."""
        current = record.scope or MemoryScopeType.PRIVATE
        if current == MemoryScopeType.UNIVERSAL:
            return None
        evidence = cls.need_evidence(db, record, window_days=window_days)
        if current == MemoryScopeType.PRIVATE:
            if (
                evidence["distinct_agents"] >= SHARED_MIN_DISTINCT_AGENTS
                and evidence["total_needs"] >= SHARED_MIN_TOTAL_NEEDS
            ):
                return MemoryScopeType.SHARED
            return None
        # SHARED -> UNIVERSAL needs demand beyond the already-shared team.
        if (
            evidence["distinct_agents"] >= UNIVERSAL_MIN_DISTINCT_AGENTS
            and evidence["total_needs"] >= UNIVERSAL_MIN_TOTAL_NEEDS
            and len(evidence["outside_agents"]) >= UNIVERSAL_MIN_OUTSIDE_AGENTS
        ):
            return MemoryScopeType.UNIVERSAL
        return None

    @classmethod
    def run_auto_promotion_sweep(
        cls,
        db: Session,
        *,
        tenant_id: str = "default",
        window_days: int = DEFAULT_WINDOW_DAYS,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """One (C) pass over a tenant: promote each memory one earned rung.

        Runs as the Memora service identity — the only identity allowed to
        move a memory to UNIVERSAL without its owner — and every promotion
        is audited with the need evidence that earned it. Idempotent: a
        second sweep over unchanged evidence promotes nothing further,
        because SHARED promotion puts the needers on the allow-list, which
        zeroes the outside-agent evidence UNIVERSAL requires.

        Candidate selection is two-phase within the ``limit`` budget
        (TASK-MEM-016 / MEM-014 G2): need-bearing memories are evaluated
        first, most-recent-need first, because the old oldest-first scan
        starved every recent memory — the 200-record window filled with
        older records before it could ever reach one with recorded need.
        The remaining budget then scans oldest-first as before, so a
        no-need sweep behaves exactly as it used to.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)
        # Phase 1 — need-bearing candidates. Need rows are rare, so collect
        # their memory ids (window-filtered in Python, mirroring
        # need_evidence, so no DB timezone arithmetic is involved) and
        # evaluate those first, most-recent-need first.
        need_rows = (
            db.query(AuditLog.memory_id, AuditLog.timestamp)
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action == ACTION_NEED,
                AuditLog.memory_id.isnot(None),
            )
            .all()
        )
        latest_need: Dict[str, datetime] = {}
        for memory_id, ts in need_rows:
            ts_utc = _as_utc(ts)
            if ts_utc is None or ts_utc < cutoff:
                continue
            if memory_id not in latest_need or ts_utc > latest_need[memory_id]:
                latest_need[memory_id] = ts_utc
        need_first_ids = sorted(
            latest_need, key=lambda mid: latest_need[mid], reverse=True
        )[:limit]

        base_filters = [
            MemoryRecord.tenant_id == tenant_id,
            MemoryRecord.scope != MemoryScopeType.UNIVERSAL,
            MemoryRecord.lifecycle_state.in_(
                [LifecycleState.ACTIVE, LifecycleState.VERIFIED, LifecycleState.CANDIDATE]
            ),
        ]
        records: List[MemoryRecord] = []
        if need_first_ids:
            records.extend(
                db.query(MemoryRecord)
                .filter(*base_filters, MemoryRecord.id.in_(need_first_ids))
                .all()
            )
            # Keep the need-first evaluation in most-recent-need order.
            order = {mid: i for i, mid in enumerate(need_first_ids)}
            records.sort(key=lambda r: order.get(r.id, len(order)))
        # Phase 2 — oldest-first scan filling the remaining budget.
        remaining = limit - len(records)
        if remaining > 0:
            oldest_query = db.query(MemoryRecord).filter(*base_filters)
            seen_ids = {r.id for r in records}
            if seen_ids:
                oldest_query = oldest_query.filter(~MemoryRecord.id.in_(seen_ids))
            records.extend(
                oldest_query.order_by(MemoryRecord.created_at.asc())
                .limit(remaining)
                .all()
            )
        results: List[Dict[str, Any]] = []
        for record in records:
            target = cls.evaluate_auto_promotion(db, record, window_days=window_days)
            if target is None:
                continue
            evidence = cls.need_evidence(db, record, window_days=window_days)
            shared_targets = (
                evidence["requesting_agents"] if target == MemoryScopeType.SHARED else []
            )
            try:
                result = cls._apply_promotion(
                    db,
                    record=record,
                    target=target,
                    shared_targets=shared_targets,
                    actor_id=None,
                    actor_name=SERVICE_AGENT,
                    path=PATH_AUTO,
                    reason="repeated cross-agent need",
                    evidence=evidence,
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("auto-promotion failed for memory %s", record.id)
                continue
            results.append(result)
        return results

    # ------------------------------------------------------------ internals
    @classmethod
    def _apply_promotion(
        cls,
        db: Session,
        *,
        record: MemoryRecord,
        target: MemoryScopeType,
        shared_targets: List[str],
        actor_id: Optional[str],
        actor_name: str,
        path: str,
        reason: str,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply one rung (already authorised) + audit. Caller commits."""
        current = record.scope or MemoryScopeType.PRIVATE

        # Failed-experiment dual rule: the original stays PRIVATE and a
        # UNIVERSAL copy carries the lesson to the whole universe.
        if target == MemoryScopeType.UNIVERSAL and is_failed_experiment_lesson(record):
            copy = cls._make_universal_copy(db, record, path=path, actor_name=actor_name)
            _audit(
                db,
                actor_id=actor_id,
                memory_id=record.id,
                tenant_id=record.tenant_id,
                action=ACTION_PROMOTED,
                details={
                    "from_scope": current.value,
                    "to_scope": MemoryScopeType.UNIVERSAL.value,
                    "promoted_by": actor_name,
                    "path": path,
                    "reason": reason[:512],
                    "failed_experiment_dual": True,
                    "universal_copy_id": copy.id,
                    "evidence": evidence,
                },
            )
            result = cls._result(record, status="promoted_dual_copy", path=path)
            result["universal_copy_id"] = copy.id
            result["to_scope"] = MemoryScopeType.UNIVERSAL.value
            return result

        if target == MemoryScopeType.SHARED:
            record.scope = MemoryScopeType.SHARED
            db.flush()
            for name in shared_targets:
                if name == SHARED_WITH_ALL_AGENTS:
                    grant_shared_access(
                        db, record, SHARED_WITH_ALL_AGENTS, granted_by=actor_name
                    )
                else:
                    grant_shared_access(db, record, name, granted_by=actor_name)
        elif target == MemoryScopeType.UNIVERSAL:
            record.scope = MemoryScopeType.UNIVERSAL
            db.flush()

        _audit(
            db,
            actor_id=actor_id,
            memory_id=record.id,
            tenant_id=record.tenant_id,
            action=ACTION_PROMOTED,
            details={
                "from_scope": current.value,
                "to_scope": target.value,
                "promoted_by": actor_name,
                "path": path,
                "reason": reason[:512],
                "shared_with": shared_targets if target == MemoryScopeType.SHARED else [],
                "evidence": evidence,
            },
        )
        result = cls._result(record, status="promoted", path=path)
        result["from_scope"] = current.value
        return result

    @staticmethod
    def _make_universal_copy(
        db: Session, record: MemoryRecord, *, path: str, actor_name: str
    ) -> MemoryRecord:
        """Create the UNIVERSAL twin of a failed-experiment lesson."""
        existing = (
            db.query(MemoryRecord)
            .filter(
                MemoryRecord.tenant_id == record.tenant_id,
                MemoryRecord.scope == MemoryScopeType.UNIVERSAL,
            )
            .all()
        )
        for candidate in existing:
            prov = candidate.provenance if isinstance(candidate.provenance, dict) else {}
            if prov.get("promoted_from_memory_id") == record.id:
                return candidate

        provenance = dict(record.provenance) if isinstance(record.provenance, dict) else {}
        provenance["promoted_from_memory_id"] = record.id
        provenance["promotion_path"] = path
        provenance["promoted_by"] = actor_name
        copy = MemoryRecord(
            id=generate_uuid(),
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            agent_id=record.agent_id,
            workspace_id=record.workspace_id,
            device_id=record.device_id,
            task_id=record.task_id,
            namespace_id=record.namespace_id,
            owner_id=record.owner_id,
            scope=MemoryScopeType.UNIVERSAL,
            owner_agent=record.owner_agent,
            memory_type=record.memory_type,
            content_text=record.content_text,
            content_hash=record.content_hash,
            source=record.source,
            provenance=provenance,
            entities=list(record.entities or []),
            confidence=record.confidence,
            importance=record.importance,
            lifecycle_state=record.lifecycle_state,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            expires_at=record.expires_at,
        )
        db.add(copy)
        db.flush()
        return copy

    @staticmethod
    def _result(record: MemoryRecord, *, status: str, path: str) -> Dict[str, Any]:
        return {
            "status": status,
            "memory_id": record.id,
            "owner_agent": normalize_agent_name(record.owner_agent),
            "scope": (record.scope or MemoryScopeType.PRIVATE).value,
            "to_scope": (record.scope or MemoryScopeType.PRIVATE).value,
            "path": path,
        }


__all__ = [
    "ACTION_NEED",
    "ACTION_DEMOTED",
    "ACTION_PROMOTED",
    "DEFAULT_WINDOW_DAYS",
    "MemoryPromotionService",
    "PromotionError",
    "PromotionPermissionError",
    "is_failed_experiment_lesson",
]
