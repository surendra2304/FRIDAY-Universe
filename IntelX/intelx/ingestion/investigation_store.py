"""INTELX — Saved Robin investigations: follow-ups + pivots (TASK-INT-051).

Extends the Robin-pattern investigation pipeline (TASK-IG2-INT-04,
``ingestion/untrusted_ingest.py``) with the two upstream Robin features
the first adaptation left out:

  * **Saved investigations** — a run investigation is kept under a
    short id so it can be re-read later instead of re-run;
  * **Grounded follow-ups** — a follow-up question runs a fresh
    investigation whose key terms are grounded in the saved run: the
    result reports which saved evidence items share terms with the
    follow-up, so the investigator sees what the new run builds on;
  * **One-click pivots** — the saved run's pivot queries (already
    derived by ``refine_query``) are retrievable on their own, ready
    to be run as the next investigation.

The store is in-memory: an investigation result is small, and this is
a watch aid for the research flow, not the canonical store (persisting
investigations to the canonical store is a future leg; the live
end-to-end run itself is owed after Muse clearance). Every evidence
item stays delimiter-wrapped exactly as ``run_investigation`` produced
it — this module never unwraps or re-emits scraped text bare.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from intelx.ingestion.untrusted_ingest import (
    EvidenceItem,
    InvestigationResult,
    refine_query,
    relevance_score,
    run_investigation,
)

logger = logging.getLogger("intelx.ingestion.investigation_store")


@dataclass
class FollowUpResult:
    """A follow-up run plus what it grounds in on the saved run."""

    saved_id: str
    question: str
    result: InvestigationResult
    grounded_in: list[EvidenceItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "saved_id": self.saved_id,
            "question": self.question,
            "grounded_in": [e.to_dict() for e in self.grounded_in],
            "result": self.result.to_dict(),
        }


class InvestigationStore:
    """In-memory store of investigation results, keyed by short id."""

    def __init__(self) -> None:
        self._results: dict[str, InvestigationResult] = {}

    def save(self, result: InvestigationResult) -> str:
        """Store a result; returns its id (``inv-`` + 12 hex chars)."""
        investigation_id = f"inv-{uuid.uuid4().hex[:12]}"
        self._results[investigation_id] = result
        return investigation_id

    def get(self, investigation_id: str) -> InvestigationResult | None:
        """Stored result, or None for an unknown id."""
        return self._results.get(investigation_id)

    def pivots(self, investigation_id: str) -> list[str]:
        """The saved run's one-click pivot queries.

        Raises :class:`KeyError` for an unknown id.
        """
        result = self._results.get(investigation_id)
        if result is None:
            raise KeyError(f"unknown investigation {investigation_id!r}")
        return list(result.query.pivots)

    async def follow_up(
        self,
        investigation_id: str,
        question: str,
        *,
        search,
        fetch,
        max_results: int = 5,
        min_relevance: float = 0.2,
    ) -> FollowUpResult:
        """Run a follow-up question grounded in a saved investigation.

        The fresh run goes through the same ``run_investigation``
        pipeline (search -> fetch -> relevance gate -> sanitise ->
        delimiter-wrap). ``grounded_in`` lists the saved evidence items
        that share at least one key term with the follow-up question —
        the saved material the new run builds on. Raises
        :class:`KeyError` for an unknown id and :class:`ValueError`
        for an empty question.
        """
        saved = self._results.get(investigation_id)
        if saved is None:
            raise KeyError(f"unknown investigation {investigation_id!r}")
        cleaned = " ".join((question or "").split())
        if not cleaned:
            raise ValueError("follow-up question must not be empty")
        result = await run_investigation(
            cleaned,
            search=search,
            fetch=fetch,
            max_results=max_results,
            min_relevance=min_relevance,
        )
        follow_terms = refine_query(cleaned).key_terms
        grounded = [
            item
            for item in saved.evidence
            if relevance_score(item.wrapped_text, follow_terms) > 0
        ]
        return FollowUpResult(
            saved_id=investigation_id,
            question=cleaned,
            result=result,
            grounded_in=grounded,
        )


_STORE: InvestigationStore | None = None


def get_store() -> InvestigationStore:
    """Process-wide investigation store used by the research routes."""
    global _STORE
    if _STORE is None:
        _STORE = InvestigationStore()
    return _STORE


__all__ = [
    "FollowUpResult",
    "InvestigationStore",
    "get_store",
]
