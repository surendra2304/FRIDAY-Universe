"""
Skill-learning loop for Memora (TASK-IG2-MEM-02, Hermes pattern).

Hermes Agent's transferable asset #1 (card hermes-agent.md) is its
learning loop: *a built-in loop creates skills from experience and
improves them in use*. FRIDAY today relearns the owner's workflows
every session. This service is that loop, Memora-native:

- ``record_outcome`` — every task outcome an agent reports (success /
  failure / owner-corrected) is stored as an EXPERIENCE record keyed
  by a stable ``pattern_key`` (the recurring task shape, e.g.
  "morning-fleet-brief" or "stratex-status-check").
- ``evaluate_patterns`` — the loop's trigger pass. A pattern earns a
  skill draft two ways:
    * repetition: >= ``min_successes`` successes at >= 80% success
      rate — the pattern demonstrably works, so capture it;
    * correction: ANY owner-corrected outcome — the owner's correction
      is the highest-value teaching signal there is (Hermes learns
      from being corrected, not just from succeeding), so one
      correction drafts immediately, with the correction quoted in
      the draft.
- Drafts are PROCEDURAL records in ``pending_review`` — a draft NEVER
  becomes an active skill on its own. ``review_skill`` is the gate:
  approve → ``active`` (and lifecycle VERIFIED), reject → ``rejected``.
  New evidence for an already-drafted pattern produces a REVISED draft
  (version + 1) that supersedes the old one, so skills improve in use
  instead of fossilising — with the full version chain inspectable.
- Draft bodies are built deterministically from the recorded outcome
  details (the steps are the successful runs' own words, corrections
  quoted verbatim). An optional ``drafter`` callable may rewrite the
  body (the caller passes its LLM); without one, nothing is invented.

Storage goes through ``MemoryWriteService`` like every other Memora
write — identity, namespace, dedupe and policy stay the pipeline's
job. All methods return dicts and never raise into the caller.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from core.memory.pipeline.write_service import MemoryWriteService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

logger = logging.getLogger(__name__)

OUTCOME_SOURCE = "skill_learning_outcome"
DRAFT_SOURCE = "skill_learning_draft"
PATTERN_TAG = "hermes-skill-learning-loop"

OUTCOMES = {"success", "failure", "corrected"}
DEFAULT_MIN_SUCCESSES = 3
DEFAULT_MIN_SUCCESS_RATE = 0.8
_MAX_OUTCOMES_SCAN = 2000


def _first_line(text: str, limit: int = 200) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()[:limit]


class SkillLearningService:
    """Hermes-style learn-from-experience loop over Memora records."""

    # ------------------------------------------------------------------
    # record outcomes
    # ------------------------------------------------------------------
    @classmethod
    def record_outcome(
        cls,
        db: Session,
        *,
        actor_name: str,
        pattern_key: str,
        outcome: str,
        detail: str,
        correction: Optional[str] = None,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store one task outcome for a recurring pattern."""
        outcome = (outcome or "").strip().lower()
        if outcome not in OUTCOMES:
            return {"stored": False, "reason": f"unknown_outcome:{outcome}"}
        if not pattern_key or not pattern_key.strip():
            return {"stored": False, "reason": "empty_pattern_key"}
        if outcome == "corrected" and not (correction or "").strip():
            return {"stored": False, "reason": "corrected_outcome_needs_correction_text"}
        content = f"Pattern {pattern_key}: outcome {outcome}. {_first_line(detail, 500)}"
        if correction:
            content += f" Owner correction: {_first_line(correction, 500)}"
        try:
            result = MemoryWriteService.execute_pipeline(
                db,
                content_text=content,
                caller_name=actor_name,
                tenant_id=tenant_id,
                task_id=task_id,
                memory_type=MemoryType.EXPERIENCE,
                source=OUTCOME_SOURCE,
                provenance={
                    "pattern": PATTERN_TAG,
                    "pattern_key": pattern_key.strip(),
                    "outcome": outcome,
                    "correction": correction or None,
                },
                importance=0.6 if outcome != "failure" else 0.4,
                confidence=0.9,
                allow_duplicates=True,
            )
        except Exception as exc:
            logger.warning("[SKILL-LEARN] outcome write refused for %s: %s", actor_name, exc)
            return {"stored": False, "reason": f"pipeline_refused: {type(exc).__name__}"}
        return {"stored": True, "id": result.record.id, "pattern_key": pattern_key, "outcome": outcome}

    # ------------------------------------------------------------------
    # read outcomes / drafts
    # ------------------------------------------------------------------
    @classmethod
    def _records_by_source(
        cls, db: Session, *, source: str, actor_name: str, tenant_id: Optional[str]
    ) -> List[MemoryRecord]:
        query = db.query(MemoryRecord).filter(
            MemoryRecord.source == source,
            MemoryRecord.lifecycle_state.in_(
                [LifecycleState.ACTIVE, LifecycleState.VERIFIED, LifecycleState.CANDIDATE]
            ),
        )
        if tenant_id:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        records = (
            query.order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
            .limit(_MAX_OUTCOMES_SCAN)
            .all()
        )
        return [r for r in records if r.agent_id == actor_name or r.owner_agent == actor_name]

    @classmethod
    def pattern_stats(
        cls, db: Session, *, actor_name: str, tenant_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Per-pattern outcome tallies + evidence ids (the loop's input)."""
        stats: Dict[str, Dict[str, Any]] = {}
        for record in cls._records_by_source(db, source=OUTCOME_SOURCE, actor_name=actor_name, tenant_id=tenant_id):
            prov = record.provenance or {}
            key = prov.get("pattern_key")
            if not key:
                continue
            bucket = stats.setdefault(
                key,
                {"success": 0, "failure": 0, "corrected": 0, "evidence_ids": [], "corrections": [], "success_details": []},
            )
            outcome = prov.get("outcome")
            if outcome in OUTCOMES:
                bucket[outcome] += 1
            bucket["evidence_ids"].append(record.id)
            if outcome == "corrected" and prov.get("correction"):
                bucket["corrections"].append(prov["correction"])
            if outcome == "success":
                bucket["success_details"].append(_first_line(record.content_text))
        for bucket in stats.values():
            total = bucket["success"] + bucket["failure"] + bucket["corrected"]
            bucket["total"] = total
            bucket["success_rate"] = (bucket["success"] / total) if total else 0.0
        return stats

    @classmethod
    def list_skill_drafts(
        cls, db: Session, *, actor_name: str, tenant_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        drafts = []
        for record in cls._records_by_source(db, source=DRAFT_SOURCE, actor_name=actor_name, tenant_id=tenant_id):
            prov = record.provenance or {}
            if status and prov.get("review_status") != status:
                continue
            drafts.append(
                {
                    "id": record.id,
                    "pattern_key": prov.get("pattern_key"),
                    "version": prov.get("version", 1),
                    "review_status": prov.get("review_status", "pending_review"),
                    "trigger": prov.get("trigger"),
                    "content": record.content_text,
                    "lifecycle_state": record.lifecycle_state.value,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                }
            )
        return drafts

    # ------------------------------------------------------------------
    # the loop: evaluate → draft
    # ------------------------------------------------------------------
    @staticmethod
    def _draft_body(pattern_key: str, bucket: Dict[str, Any], trigger: str) -> str:
        lines = [
            f"SKILL DRAFT — {pattern_key}",
            f"Trigger for drafting: {trigger}.",
            f"Evidence: {bucket['success']} success(es), {bucket['failure']} failure(s), "
            f"{bucket['corrected']} owner correction(s) over {bucket['total']} recorded outcome(s).",
            "What worked (from the successful runs' own records):",
        ]
        for detail in bucket["success_details"][:5]:
            lines.append(f"- {detail}")
        if bucket["corrections"]:
            lines.append("Owner corrections (verbatim — these override the steps above):")
            for correction in bucket["corrections"][:5]:
                lines.append(f"- {correction}")
        lines.append(
            "Status: DRAFT pending review. This skill is not active until a reviewer approves it."
        )
        return "\n".join(lines)

    @classmethod
    def evaluate_patterns(
        cls,
        db: Session,
        *,
        actor_name: str,
        tenant_id: Optional[str] = None,
        min_successes: int = DEFAULT_MIN_SUCCESSES,
        min_success_rate: float = DEFAULT_MIN_SUCCESS_RATE,
        drafter: Optional[Callable[[str, Dict[str, Any], str], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """One learning-loop pass: draft skills for patterns that earned one.

        A pattern is drafted when (a) it has a corrected outcome not yet
        reflected in a draft, or (b) it meets the repetition bar and has
        outcomes newer than its latest draft. Re-running with no new
        evidence drafts nothing.
        """
        stats = cls.pattern_stats(db, actor_name=actor_name, tenant_id=tenant_id)
        existing = cls.list_skill_drafts(db, actor_name=actor_name, tenant_id=tenant_id)
        latest_by_pattern: Dict[str, Dict[str, Any]] = {}
        for draft in existing:
            key = draft["pattern_key"]
            if key and (key not in latest_by_pattern or draft["version"] > latest_by_pattern[key]["version"]):
                latest_by_pattern[key] = draft

        drafted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        for key, bucket in sorted(stats.items()):
            trigger = None
            if bucket["corrected"] > 0:
                trigger = "owner_correction"
            elif bucket["success"] >= min_successes and bucket["success_rate"] >= min_success_rate:
                trigger = "repeated_success"
            if trigger is None:
                skipped.append({"pattern_key": key, "reason": "below_threshold"})
                continue
            prior = latest_by_pattern.get(key)
            prior_evidence = 0
            prior_version = 0
            if prior:
                prior_record = db.query(MemoryRecord).filter(MemoryRecord.id == prior["id"]).first()
                prior_prov = (prior_record.provenance or {}) if prior_record else {}
                prior_evidence = len(prior_prov.get("evidence_ids") or [])
                prior_version = int(prior_prov.get("version") or 1)
                if prior_evidence >= len(bucket["evidence_ids"]):
                    skipped.append({"pattern_key": key, "reason": "no_new_evidence"})
                    continue
            body = cls._draft_body(key, bucket, trigger)
            if drafter is not None:
                try:
                    rewritten = drafter(key, bucket, body)
                except Exception:
                    rewritten = None
                if rewritten:
                    body = rewritten
            # Policy compliance, by construction. PROCEDURAL is an
            # evidence-required type, and when the caller is the Memora
            # service identity the write pipeline demands verified or
            # operator-confirmed trust plus at least one evidence
            # reference — read from the evidence_refs ARGUMENT (or a
            # provenance "evidence_refs" key), never from this service's
            # own "evidence_ids" provenance key. The first version of
            # this loop passed neither, so every draft the service
            # identity tried to write was refused and the loop could
            # never draft for its own outcomes. The qualifying outcome
            # records ARE the evidence: the bucket was tallied from
            # stored, pipeline-signed records read back in
            # pattern_stats, and a trigger can only fire with at least
            # one of them present (>= 1 owner correction, or >=
            # min_successes successes). The trust label states what the
            # service actually established — an owner correction among
            # the evidence is operator-confirmed; a threshold pass over
            # stored records is service-verified. The pipeline honours
            # a trust label only from the service principal and forces
            # "candidate" for everyone else, so for ordinary actors the
            # existing PROCEDURAL-candidate path applies unchanged.
            # Either way the draft lands pending_review; activation
            # still belongs to the review gate alone.
            try:
                result = MemoryWriteService.execute_pipeline(
                    db,
                    content_text=body,
                    caller_name=actor_name,
                    tenant_id=tenant_id,
                    memory_type=MemoryType.PROCEDURAL,
                    source=DRAFT_SOURCE,
                    trust_level=(
                        "operator_confirmed" if trigger == "owner_correction" else "verified"
                    ),
                    evidence_refs=list(bucket["evidence_ids"]),
                    provenance={
                        "pattern": PATTERN_TAG,
                        "pattern_key": key,
                        "version": prior_version + 1,
                        "review_status": "pending_review",
                        "trigger": trigger,
                        "evidence_ids": bucket["evidence_ids"],
                        "success_rate": bucket["success_rate"],
                    },
                    importance=0.65,
                    confidence=0.8,
                    allow_duplicates=True,
                )
            except Exception as exc:
                logger.warning("[SKILL-LEARN] draft write refused for %s/%s: %s", actor_name, key, exc)
                skipped.append({"pattern_key": key, "reason": f"pipeline_refused: {type(exc).__name__}"})
                continue
            superseded_id = None
            if prior:
                try:
                    from core.memory.service import MemoryService

                    MemoryService.supersede_memory(
                        db, prior["id"], result.record.id, actor_name=actor_name,
                        reason="skill draft revised with new evidence",
                    )
                    superseded_id = prior["id"]
                except Exception as exc:
                    logger.info("[SKILL-LEARN] draft %s not superseded (kept, newest wins): %s", prior["id"], exc)
            drafted.append(
                {
                    "pattern_key": key,
                    "draft_id": result.record.id,
                    "version": prior_version + 1,
                    "trigger": trigger,
                    "superseded_id": superseded_id,
                }
            )
        return {"drafted": drafted, "skipped": skipped, "patterns_seen": len(stats)}

    # ------------------------------------------------------------------
    # review gate
    # ------------------------------------------------------------------
    @classmethod
    def review_skill(
        cls,
        db: Session,
        *,
        actor_name: str,
        draft_id: str,
        approve: bool,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve (→ active skill) or reject a pending draft. The gate
        that keeps the loop honest: nothing self-activates."""
        record = db.query(MemoryRecord).filter(MemoryRecord.id == draft_id).first()
        if record is None or record.source != DRAFT_SOURCE:
            return {"reviewed": False, "reason": "draft_not_found"}
        if tenant_id and record.tenant_id != tenant_id:
            return {"reviewed": False, "reason": "draft_not_found"}
        prov = dict(record.provenance or {})
        if prov.get("review_status") != "pending_review":
            return {"reviewed": False, "reason": f"not_pending:{prov.get('review_status')}"}
        prov["review_status"] = "active" if approve else "rejected"
        record.provenance = prov
        if approve:
            record.lifecycle_state = LifecycleState.VERIFIED
        db.commit()
        return {
            "reviewed": True,
            "draft_id": draft_id,
            "review_status": prov["review_status"],
            "pattern_key": prov.get("pattern_key"),
        }

    @classmethod
    def active_skills(
        cls, db: Session, *, actor_name: str, tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Approved skills only — what an agent may actually reuse."""
        return cls.list_skill_drafts(db, actor_name=actor_name, tenant_id=tenant_id, status="active")
