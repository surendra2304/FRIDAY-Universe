"""
Store-wide dedup + contradiction hygiene for Memora (TASK-MEM-004).

The write pipeline (``core.memory.pipeline.deduplication``) guards new writes,
but duplicates and direct contradictions that entered the store through other
paths — bulk imports, older writers, races, adapters — are never reconciled
after the fact. This module is the retroactive pass:

* ``analyze`` inspects live records (candidate / active / verified) inside one
  (tenant, namespace) scope at a time and produces a deterministic plan:
  exact-duplicate groups, near-duplicate pairs (token Jaccard at the write
  pipeline's own 0.85 threshold), and direct contradiction pairs from the
  repo's conservative ``ContradictionDetector``.
* ``apply_actions`` executes a plan one action per transaction. It never
  deletes a row: a loser is transitioned to SUPERSEDED through
  ``MemoryLifecycleEngine`` with ``superseded_by_id`` pointing at the winner,
  its provenance is preserved and annotated (never rewritten), and every
  action writes an ``AuditLog`` row. Re-running the pass is a no-op for
  records it already reconciled, because superseded records are not live.

Winner selection follows the task rule "keep the newest verified value" and
the codebase's own supersession doctrine ("never resolve contradictions using
recency alone; use provenance and confidence first"), in this order:

1. a VERIFIED record beats a non-verified one;
2. higher ``SupersessionEngine`` evidence score wins;
3. most recent ``last_verified_at`` wins;
4. most recent ``created_at`` wins;
5. record id (stable tiebreak).

Safety posture: near-duplicate actions are planned but are only applied when
the caller explicitly opts in (``include_near=True``) — two statements can
share 85% of their tokens and still differ in the one token that matters, so
they stay a review class by default. Exact duplicates and detector-confirmed
contradictions are the auto-appliable classes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from core.lifecycle.state_machine import MemoryLifecycleEngine
from core.lifecycle.supersession import SupersessionEngine
from core.memory.pipeline.contradiction_detector import ContradictionDetector
from storage.relational.models import AuditLog, LifecycleState, MemoryRecord

TASK_ID = "TASK-MEM-004"
LIVE_STATES = (LifecycleState.CANDIDATE, LifecycleState.ACTIVE, LifecycleState.VERIFIED)
NEAR_DUPLICATE_THRESHOLD = 0.85  # the write pipeline's own threshold

KIND_EXACT = "exact_duplicate"
KIND_NEAR = "near_duplicate"
KIND_CONTRADICTION = "contradiction"


def normalize_content(text: Optional[str]) -> str:
    """The write pipeline's duplicate semantics: collapse whitespace, casefold."""
    return " ".join((text or "").strip().split()).casefold()


def _token_set(text: Optional[str]) -> set:
    return set((text or "").lower().split())


def token_jaccard(text1: str, text2: str) -> float:
    """Same computation as ``DeduplicationEngine._token_jaccard``."""
    tokens1 = _token_set(text1)
    tokens2 = _token_set(text2)
    if not tokens1 or not tokens2:
        return 0.0
    union = len(tokens1.union(tokens2))
    return len(tokens1.intersection(tokens2)) / union if union else 0.0


def _as_utc(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def evidence_score(record: MemoryRecord) -> float:
    return SupersessionEngine.calculate_evidence_score(
        record, owner_name=getattr(record, "owner_agent", None)
    )


def winner_key(record: MemoryRecord):
    """Sort key implementing the winner rule; the maximum wins."""
    return (
        1 if record.lifecycle_state == LifecycleState.VERIFIED else 0,
        evidence_score(record),
        _as_utc(record.last_verified_at),
        _as_utc(record.created_at),
        record.id or "",
    )


def pick_winner(records: Sequence[MemoryRecord]) -> MemoryRecord:
    return max(records, key=winner_key)


@dataclass
class HygieneAction:
    kind: str
    winner_id: str
    loser_id: str
    reason: str
    evidence_winner: float
    evidence_loser: float
    similarity: Optional[float] = None
    detector_kind: Optional[str] = None
    detector_score: Optional[float] = None

    def as_dict(self) -> Dict:
        return {
            "kind": self.kind,
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "reason": self.reason,
            "evidence_winner": self.evidence_winner,
            "evidence_loser": self.evidence_loser,
            "similarity": self.similarity,
            "detector_kind": self.detector_kind,
            "detector_score": self.detector_score,
        }


@dataclass
class HygieneReport:
    live_records: int = 0
    exact_groups: int = 0
    exact_excess_records: int = 0
    near_pairs: int = 0
    contradiction_pairs: int = 0
    contradiction_by_kind: Dict[str, int] = field(default_factory=dict)
    actions: List[HygieneAction] = field(default_factory=list)
    plan_conflicts: List[str] = field(default_factory=list)

    def counts(self) -> Dict:
        return {
            "live_records": self.live_records,
            "exact_dup_groups": self.exact_groups,
            "exact_dup_excess_records": self.exact_excess_records,
            "near_dup_pairs": self.near_pairs,
            "contradiction_pairs": self.contradiction_pairs,
            "contradiction_by_kind": dict(self.contradiction_by_kind),
            "planned_actions": len(self.actions),
            "plan_conflicts": list(self.plan_conflicts),
        }


def _scope_key(record: MemoryRecord):
    return (record.tenant_id, record.namespace_id)


def find_exact_duplicate_groups(
    records: Sequence[MemoryRecord],
) -> List[List[MemoryRecord]]:
    groups: Dict = defaultdict(list)
    for record in records:
        groups[(_scope_key(record), normalize_content(record.content_text))].append(record)
    return [g for g in groups.values() if len(g) > 1]


def find_near_duplicate_pairs(
    records: Sequence[MemoryRecord], threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> List:
    """Pairs within one scope with token Jaccard >= threshold, excluding
    exact-normalized pairs (those are duplicate groups, not near pairs)."""
    by_scope: Dict = defaultdict(list)
    for record in records:
        by_scope[_scope_key(record)].append(record)
    pairs = []
    for group in by_scope.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if normalize_content(a.content_text) == normalize_content(b.content_text):
                    continue
                sim = token_jaccard(a.content_text, b.content_text)
                if sim >= threshold:
                    pairs.append((a, b, sim))
    return pairs


def find_contradiction_pairs(records: Sequence[MemoryRecord]) -> List:
    """Direct contradictions per the repo's conservative detector.

    Candidate pairs are bucketed by the detector's own skeletons (polarity
    skeleton / numeric skeleton) so the pairwise check stays cheap; every
    candidate is still confirmed through ``ContradictionDetector.assess``.
    """
    by_scope: Dict = defaultdict(list)
    for record in records:
        by_scope[_scope_key(record)].append(record)

    pairs = []
    for group in by_scope.values():
        buckets: Dict = defaultdict(list)
        for record in group:
            text = " ".join((record.content_text or "").strip().split())
            if not text:
                continue
            toks = ContradictionDetector._tokens(text)
            pol_skeleton = ContradictionDetector._polarity_skeleton(toks)
            if pol_skeleton:
                buckets[("pol", pol_skeleton)].append(record)
            num_skeleton = ContradictionDetector._numeric_skeleton(text)
            if num_skeleton:
                buckets[("num", num_skeleton)].append(record)
        seen = set()
        for bucket in buckets.values():
            if len(bucket) < 2:
                continue
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    a, b = bucket[i], bucket[j]
                    pair_key = tuple(sorted((a.id, b.id)))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    assessment = ContradictionDetector.assess(a.content_text, b.content_text)
                    if assessment.is_contradiction:
                        pairs.append((a, b, assessment))
    return pairs


def analyze(
    records: Sequence[MemoryRecord], near_threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> HygieneReport:
    """Build the reconciliation plan for a set of records (pure; no mutation).

    Only live records are considered. Contradiction actions are planned
    first, then exact duplicates, then near duplicates; a record already
    assigned as a loser keeps its first winner and later competing actions
    are recorded as plan conflicts instead of silently re-pointing it.
    """
    live = [r for r in records if r.lifecycle_state in LIVE_STATES]
    report = HygieneReport(live_records=len(live))
    assigned_loser: Dict[str, str] = {}

    def add_action(kind, winner, loser, reason, **extra):
        if loser.id in assigned_loser and assigned_loser[loser.id] != winner.id:
            report.plan_conflicts.append(
                f"{loser.id}: already superseded by {assigned_loser[loser.id]} "
                f"in this plan; skipped re-pointing to {winner.id} ({kind})"
            )
            return
        assigned_loser[loser.id] = winner.id
        report.actions.append(
            HygieneAction(
                kind=kind,
                winner_id=winner.id,
                loser_id=loser.id,
                reason=reason,
                evidence_winner=evidence_score(winner),
                evidence_loser=evidence_score(loser),
                **extra,
            )
        )

    # 1) Contradictions — the semantically decisive class.
    contra = find_contradiction_pairs(live)
    report.contradiction_pairs = len(contra)
    for a, b, assessment in contra:
        report.contradiction_by_kind[assessment.kind] = (
            report.contradiction_by_kind.get(assessment.kind, 0) + 1
        )
        winner = pick_winner([a, b])
        loser = b if winner.id == a.id else a
        add_action(
            KIND_CONTRADICTION,
            winner,
            loser,
            reason=(
                f"Direct contradiction ({assessment.kind}, detector score "
                f"{assessment.score}): {assessment.reason} Winner kept per "
                "verified-first, evidence, then recency rule."
            ),
            detector_kind=assessment.kind,
            detector_score=assessment.score,
        )

    # 2) Exact duplicates.
    exact_groups = find_exact_duplicate_groups(live)
    report.exact_groups = len(exact_groups)
    report.exact_excess_records = sum(len(g) - 1 for g in exact_groups)
    for group in exact_groups:
        # Prefer a winner that is not itself already planned as a loser
        # (e.g. it lost a contradiction to a stronger record earlier).
        candidates = [m for m in group if m.id not in assigned_loser]
        winner = pick_winner(candidates or group)
        for member in group:
            if member.id == winner.id:
                continue
            add_action(
                KIND_EXACT,
                winner,
                member,
                reason=(
                    "Exact duplicate (normalized content identical within the "
                    "same tenant+namespace). Winner kept per verified-first, "
                    "evidence, then recency rule."
                ),
                similarity=1.0,
            )

    # 3) Near duplicates — planned for review; applied only on explicit opt-in.
    near = find_near_duplicate_pairs(live, threshold=near_threshold)
    report.near_pairs = len(near)
    for a, b, sim in near:
        if a.id in assigned_loser or b.id in assigned_loser:
            continue  # already reconciled by a stronger class
        winner = pick_winner([a, b])
        loser = b if winner.id == a.id else a
        add_action(
            KIND_NEAR,
            winner,
            loser,
            reason=(
                f"Near duplicate (token Jaccard {sim:.3f} >= {near_threshold}) "
                "within the same tenant+namespace. Review class: applied only "
                "with explicit opt-in."
            ),
            similarity=round(sim, 4),
        )

    return report


def load_live_records(
    db: Session,
    tenant_id: Optional[str] = None,
    namespace_id: Optional[str] = None,
) -> List[MemoryRecord]:
    query = db.query(MemoryRecord).filter(MemoryRecord.lifecycle_state.in_(LIVE_STATES))
    if tenant_id is not None:
        query = query.filter(MemoryRecord.tenant_id == tenant_id)
    if namespace_id is not None:
        query = query.filter(MemoryRecord.namespace_id == namespace_id)
    return query.order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc()).all()


def _annotate_provenance(record: MemoryRecord, entry: Dict) -> None:
    """Append a hygiene note without rewriting any existing provenance."""
    provenance = dict(record.provenance or {})
    history = list(provenance.get("hygiene") or [])
    history.append(entry)
    provenance["hygiene"] = history
    record.provenance = provenance  # reassignment flags the JSON column dirty


def apply_actions(
    db: Session,
    actions: Iterable[HygieneAction],
    actor_id: Optional[str] = None,
    task_id: str = TASK_ID,
    include_near: bool = False,
    max_actions: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict:
    """Execute planned actions, one transaction per action.

    Guards are re-checked against fresh state at apply time (both records
    must still be live, same tenant+namespace, distinct); anything that no
    longer qualifies is skipped, never forced. Nothing is deleted: losers
    are superseded with provenance annotated and an audit row written.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    applied, skipped, failed = [], [], []
    attempted = 0
    for action in actions:
        if action.kind == KIND_NEAR and not include_near:
            skipped.append({**action.as_dict(), "why": "near_duplicate requires explicit opt-in"})
            continue
        if max_actions is not None and attempted >= max_actions:
            skipped.append({**action.as_dict(), "why": "max_actions cap reached"})
            continue
        attempted += 1
        try:
            loser = db.get(MemoryRecord, action.loser_id)
            winner = db.get(MemoryRecord, action.winner_id)
            if loser is None or winner is None:
                skipped.append({**action.as_dict(), "why": "record no longer exists"})
                continue
            if loser.id == winner.id:
                skipped.append({**action.as_dict(), "why": "winner == loser"})
                continue
            if loser.tenant_id != winner.tenant_id or loser.namespace_id != winner.namespace_id:
                skipped.append({**action.as_dict(), "why": "scope mismatch at apply time"})
                continue
            if loser.lifecycle_state not in LIVE_STATES:
                skipped.append(
                    {**action.as_dict(), "why": f"loser not live ({loser.lifecycle_state})"}
                )
                continue
            if winner.lifecycle_state not in LIVE_STATES:
                skipped.append(
                    {**action.as_dict(), "why": f"winner not live ({winner.lifecycle_state})"}
                )
                continue
            if loser.superseded_by_id == winner.id and loser.lifecycle_state == LifecycleState.SUPERSEDED:
                skipped.append({**action.as_dict(), "why": "already superseded by this winner"})
                continue

            _annotate_provenance(
                loser,
                {
                    "task": task_id,
                    "action": f"superseded_{action.kind}",
                    "winner_id": winner.id,
                    "reason": action.reason,
                    "evidence_winner": action.evidence_winner,
                    "evidence_loser": action.evidence_loser,
                    "at": stamp,
                },
            )
            _annotate_provenance(
                winner,
                {
                    "task": task_id,
                    "action": f"kept_over_{action.kind}",
                    "loser_id": loser.id,
                    "at": stamp,
                },
            )
            MemoryLifecycleEngine.transition(
                loser, LifecycleState.SUPERSEDED, superseded_by_id=winner.id
            )
            db.add(
                AuditLog(
                    tenant_id=loser.tenant_id,
                    actor_id=actor_id,
                    memory_id=loser.id,
                    action=f"hygiene_{action.kind}",
                    details={
                        "task": task_id,
                        "winner_id": winner.id,
                        "loser_id": loser.id,
                        "reason": action.reason,
                        "evidence_winner": action.evidence_winner,
                        "evidence_loser": action.evidence_loser,
                        "detector_kind": action.detector_kind,
                        "detector_score": action.detector_score,
                        "similarity": action.similarity,
                        "at": stamp,
                    },
                )
            )
            db.commit()
            applied.append(action.as_dict())
        except Exception as exc:  # one bad action must not abort the pass
            db.rollback()
            failed.append({**action.as_dict(), "error": f"{type(exc).__name__}: {exc}"})
    return {"applied": applied, "skipped": skipped, "failed": failed}
