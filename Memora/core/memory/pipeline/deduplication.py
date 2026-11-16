"""
Duplicate detection and conservative contradiction signaling for the Memora write pipeline.

Duplicates may be safely coalesced after authorization. Contradiction signals are
review-only metadata: this module never picks a winner or mutates memory lifecycle.

Two duplicate notions live here:

- ``DeduplicationEngine`` — the original namespace-scoped scan (exact text plus
  lexical near-duplicates, contradiction signaling). It only ever sees the
  target namespace.
- The tenant-scoped EXACT-duplicate helpers below (``find_exact_duplicate`` and
  friends) — the MEM-004 fix. Production accumulated byte-identical copies of
  the same fact because the namespace scan cannot see across namespaces
  (``/v1/memories`` defaults to ``memora://<actor>/private`` while ``/v1/task``
  defaults to ``memora://<actor>/general``) and because the /v1/task router
  opted out of coalescing blanketly (``allow_duplicates=True``) for what are
  fact stores. The exact check keys on (tenant_id, owner_agent, content_hash,
  provenance subject) — the hygiene pass's grouping rule — and is enforced by
  both write services for fact writes. ``allow_duplicates=True`` keeps its
  deliberate OCCURRENCE meaning for the internal event writers (skill
  outcomes, user-model corrections: the Nth identical write is new evidence);
  occurrence writes skip the check and carry no key. ``dedupe_key`` (a hash of
  the tuple above, stored on fact-write records and protected by a unique
  index) is the race net: two concurrent identical fact writes cannot both
  insert.
"""
import hashlib
import json
from typing import Optional

from sqlalchemy.orm import Session

from core.memory.pipeline.contradiction_detector import ContradictionDetector
from storage.relational.models import LifecycleState, MemoryRecord

#: Lifecycle states that count as "the fact already exists". A duplicate of a
#: superseded/archived/deleted record is a fresh write, not a coalesce — the
#: same state set the namespace engine scans.
_LIVE_STATES = [
    LifecycleState.ACTIVE,
    LifecycleState.VERIFIED,
    LifecycleState.CANDIDATE,
]


def normalize_content(content_text: str) -> str:
    """The write pipeline's canonical content form (Step 4): whitespace-folded.

    Both services hash and compare this form, so a re-write that differs only
    in incidental whitespace is the same fact.
    """
    return " ".join(content_text.strip().split())


def compute_content_hash(content_text: str) -> str:
    """SHA-256 of the normalized content — identical to pipeline Step 4."""
    return hashlib.sha256(normalize_content(content_text).encode("utf-8")).hexdigest()


def extract_subject(provenance: Optional[dict]) -> Optional[str]:
    """The provenance subject that scopes an exact duplicate, if any.

    Callers may place it at ``provenance["subject"]`` or in the nested
    ``provenance["metadata"]["subject"]`` (the two shapes the MEM-004
    enumeration recognised). Absent/blank subjects normalise to ``None``;
    in production almost every record is subject-less, so the dedupe key is
    effectively (tenant, owner, content).
    """
    if not isinstance(provenance, dict):
        return None
    subject = provenance.get("subject")
    if subject is None:
        metadata = provenance.get("metadata")
        if isinstance(metadata, dict):
            subject = metadata.get("subject")
    if subject is None:
        return None
    subject = str(subject).strip()
    return subject or None


def compute_dedupe_key(
    tenant_id: str,
    owner_agent: str,
    content_hash: str,
    subject: Optional[str],
) -> str:
    """Stable key for one (tenant, owner, content, subject) fact.

    Stored on the record and covered by the ``uq_memory_dedupe_key`` unique
    index, so the database — not a check-then-insert race — arbitrates
    concurrent identical writes. JSON encoding keeps the fields unambiguous
    (no separator-collision between values).
    """
    material = json.dumps(
        [tenant_id, owner_agent, content_hash, subject],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def find_exact_duplicate(
    db: Session,
    *,
    tenant_id: str,
    owner_agent: str,
    content_hash: str,
    subject: Optional[str] = None,
) -> Optional[MemoryRecord]:
    """Return the canonical live record for an exact duplicate, or None.

    The canonical record is the earliest write (``created_at``, then ``id`` —
    the MEM-004 keep rule). Candidates are matched by ``dedupe_key`` (rows
    written since the key existed) or by ``content_hash`` (pipeline rows
    written before it); the subject is compared in Python because it lives
    inside the provenance JSON, and the candidate set per (tenant, owner,
    hash) is a handful of rows at most. Records written by the legacy direct
    path before it set ``content_hash`` carry neither value and cannot be
    matched — the hygiene pass already removed those copies from production.
    """
    dedupe_key = compute_dedupe_key(tenant_id, owner_agent, content_hash, subject)
    by_key = (
        db.query(MemoryRecord)
        .filter(
            MemoryRecord.tenant_id == tenant_id,
            MemoryRecord.dedupe_key == dedupe_key,
            MemoryRecord.lifecycle_state.in_(_LIVE_STATES),
        )
        .order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        .first()
    )
    if by_key is not None:
        return by_key

    candidates = (
        db.query(MemoryRecord)
        .filter(
            MemoryRecord.tenant_id == tenant_id,
            MemoryRecord.owner_agent == owner_agent,
            MemoryRecord.content_hash == content_hash,
            MemoryRecord.lifecycle_state.in_(_LIVE_STATES),
        )
        .order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        .all()
    )
    for candidate in candidates:
        if extract_subject(candidate.provenance) == subject:
            return candidate
    return None


class DeduplicationResult:
    def __init__(
        self,
        is_duplicate: bool,
        duplicate_of_id: Optional[str] = None,
        similarity_score: float = 0.0,
        duplicate_warning: Optional[str] = None,
        is_contradiction: bool = False,
        contradiction_of_id: Optional[str] = None,
        contradiction_score: float = 0.0,
        contradiction_kind: Optional[str] = None,
        contradiction_reason: Optional[str] = None,
    ):
        self.is_duplicate = is_duplicate
        self.duplicate_of_id = duplicate_of_id
        self.similarity_score = similarity_score
        self.duplicate_warning = duplicate_warning
        self.is_contradiction = is_contradiction
        self.contradiction_of_id = contradiction_of_id
        self.contradiction_score = contradiction_score
        self.contradiction_kind = contradiction_kind
        self.contradiction_reason = contradiction_reason


class DeduplicationEngine:
    @staticmethod
    def _token_jaccard(text1: str, text2: str) -> float:
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def check_duplicates_and_contradictions(
        cls,
        db: Session,
        namespace_id: str,
        content_text: str,
        similarity_threshold: float = 0.85,
        tenant_id: Optional[str] = None,
    ) -> DeduplicationResult:
        """Detect exact/near duplicates and high-confidence candidate conflicts.

        The namespace and optional tenant constrain the candidate set. Conflicts
        take precedence over duplicate matches, and uncertain statements are
        deliberately ignored by the underlying detector.
        """
        query = db.query(MemoryRecord).filter(
            MemoryRecord.namespace_id == namespace_id,
            MemoryRecord.lifecycle_state.in_([
                LifecycleState.ACTIVE,
                LifecycleState.VERIFIED,
                LifecycleState.CANDIDATE,
            ]),
        )
        if tenant_id is not None:
            query = query.filter(MemoryRecord.tenant_id == tenant_id)
        records = query.order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc()).all()

        cleaned_input = " ".join(content_text.strip().split())
        duplicate_match: Optional[DeduplicationResult] = None

        for record in records:
            cleaned_existing = " ".join(record.content_text.strip().split())

            assessment = ContradictionDetector.assess(cleaned_existing, cleaned_input)
            if assessment.is_contradiction:
                return DeduplicationResult(
                    is_duplicate=False,
                    similarity_score=assessment.score,
                    is_contradiction=True,
                    contradiction_of_id=record.id,
                    contradiction_score=assessment.score,
                    contradiction_kind=assessment.kind,
                    contradiction_reason=assessment.reason,
                )

            # Preserve existing exact-duplicate and lexical-overlap behavior.
            if cleaned_input.casefold() == cleaned_existing.casefold():
                if duplicate_match is None or duplicate_match.similarity_score < 1.0:
                    duplicate_match = DeduplicationResult(
                        is_duplicate=True,
                        duplicate_of_id=record.id,
                        similarity_score=1.0,
                        duplicate_warning="Exact content duplicate detected in target namespace.",
                    )
                continue

            similarity = cls._token_jaccard(cleaned_input, cleaned_existing)
            if similarity >= similarity_threshold and duplicate_match is None:
                duplicate_match = DeduplicationResult(
                    is_duplicate=True,
                    duplicate_of_id=record.id,
                    similarity_score=similarity,
                    duplicate_warning="High semantic/lexical overlap with existing record.",
                )

        if duplicate_match is not None:
            return duplicate_match
        return DeduplicationResult(is_duplicate=False, similarity_score=0.0)
