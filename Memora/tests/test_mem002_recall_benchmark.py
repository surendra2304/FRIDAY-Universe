"""
TASK-MEM-002 offline recall benchmark: the deterministic twin of the live
probe set in Memora/benchmarks/recall_probe_set.json.

The live benchmark (benchmarks/recall_benchmark.py) measures production; this
suite pins the same guarantees in CI with real relational records and a
stubbed vector boundary (the TASK-REL-024 pattern), so a ranking regression
is caught without a production run.

Cases:
  1. Keyword candidate-scan starvation — the lexical leg scans a bounded
     candidate window ordered by importance/confidence BEFORE it scores
     token overlap. With more high-importance records matching a common
     query token than the window holds (500 at FRIDAY's limit=5), a fresh
     fact that matches MORE of the query is never scored at all.
  2. Equal-relevance recency — two versions of one fact with identical
     keyword overlap: the lexical rank tie-break is the record id, so the
     version FRIDAY recalls first is arbitrary (an accident of uuid
     ordering) instead of the newer one.
  3. Guards: superseded/archived records never surface even as semantic
     rank 1 (REL-013/005 semantics); a fresh semantic hit still lands in
     the limit-5 window (REL-013/024).
"""
import importlib
from datetime import datetime, timedelta, timezone

import pytest

from core.identity.service import IdentityService
from core.memory.search_service import SearchService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType
from storage.vector.qdrant_adapter import VectorSearchResult

# storage/vector/__init__.py re-exports the adapter singleton under the same
# name as the submodule, so import the module itself explicitly.
oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")

BASE_TS = datetime(2026, 11, 15, 6, 0, 0, tzinfo=timezone.utc)


class StubOracleAdapter:
    """Oracle-adapter stand-in returning a fixed hit set (REL-013 pattern)."""

    def __init__(self, hits):
        self._hits = hits

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return list(self._hits)


def _record(test_db, ns, owner_id, content, **kwargs):
    record = MemoryRecord(
        namespace_id=ns.id,
        owner_id=owner_id,
        memory_type=kwargs.pop("memory_type", MemoryType.EPISODIC),
        content_text=content,
        confidence=kwargs.pop("confidence", 0.9),
        importance=kwargs.pop("importance", 0.8),
        lifecycle_state=kwargs.pop("lifecycle_state", LifecycleState.ACTIVE),
        **kwargs,
    )
    test_db.add(record)
    test_db.commit()
    return record


def _actor_ns(test_db):
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    return actor, ns


def test_keyword_candidate_scan_cannot_starve_fresh_fact(test_db, monkeypatch):
    """600 high-importance records match the query's common token; the fresh
    fact matches far more of the query but has default importance. At
    FRIDAY's production recall limit (5) the candidate scan holds only 500
    records, so an importance-ordered scan fills it with decoys and the
    target is never even scored by the keyword leg."""
    actor, ns = _actor_ns(test_db)

    decoys = []
    for i in range(600):
        decoys.append(
            MemoryRecord(
                namespace_id=ns.id,
                owner_id=actor.id,
                memory_type=MemoryType.EPISODIC,
                content_text=f"Routine note {i}: the weekly planning checklist and the office rota.",
                confidence=0.95,
                importance=0.95,
                lifecycle_state=LifecycleState.ACTIVE,
                created_at=BASE_TS + timedelta(seconds=i),
            )
        )
    test_db.add_all(decoys)
    test_db.commit()

    target = _record(
        test_db, ns, actor.id,
        "The vault combination for the storage locker is kept with the caretaker.",
        importance=0.5, confidence=0.9,
        created_at=BASE_TS + timedelta(days=1),
    )

    # Isolate the keyword leg: the semantic boundary returns nothing.
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", StubOracleAdapter([]))

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="what is the vault combination for the storage locker",
        actor_name="friday",
        limit=5,
    )
    ids = [r.record.id for r in results]
    assert target.id in ids, (
        "fresh fact starved out of the keyword candidate scan: "
        f"got {[r.record.content_text[:40] for r in results]}"
    )
    by_id = {r.record.id: r for r in results}
    assert by_id[target.id].keyword_score > 0


def test_equal_relevance_newer_fact_ranks_first(test_db, monkeypatch):
    """Two versions of one fact, identical keyword overlap, identical
    confidence/importance. The older record's id sorts first, so the
    id-based lexical tie-break hands it the better keyword rank and the
    stale value wins recall. The newer fact must rank first."""
    actor, ns = _actor_ns(test_db)

    older = _record(
        test_db, ns, actor.id,
        "The workshop door code is 1111.",
        id="aaaaaaaa-0000-4000-8000-000000000001",
        created_at=BASE_TS,
    )
    newer = _record(
        test_db, ns, actor.id,
        "The workshop door code is 2222.",
        id="zzzzzzzz-0000-4000-8000-000000000002",
        created_at=BASE_TS + timedelta(minutes=5),
    )

    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", StubOracleAdapter([]))

    results = SearchService.hybrid_search(
        db=test_db, query_text="workshop door code", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert newer.id in ids and older.id in ids
    assert ids.index(newer.id) < ids.index(older.id), (
        "stale version outranks the newer one on an id-ordering accident"
    )


def test_superseded_and_archived_never_surface(test_db, monkeypatch):
    """Guard (REL-005/013 semantics): even as the semantic rank-1 hit, a
    superseded or archived record must not enter default search results."""
    actor, ns = _actor_ns(test_db)

    superseded = _record(
        test_db, ns, actor.id, "The retreat city is Kodaikanal.",
        lifecycle_state=LifecycleState.SUPERSEDED,
    )
    archived = _record(
        test_db, ns, actor.id, "The retreat city is Ooty.",
        lifecycle_state=LifecycleState.ARCHIVED,
    )
    live = _record(test_db, ns, actor.id, "The retreat city is Coorg.")

    stub = StubOracleAdapter(
        [
            VectorSearchResult(memory_id=superseded.id, score=0.95, payload={}),
            VectorSearchResult(memory_id=archived.id, score=0.93, payload={}),
            VectorSearchResult(memory_id=live.id, score=0.90, payload={}),
        ]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db, query_text="retreat city", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert live.id in ids
    assert superseded.id not in ids
    assert archived.id not in ids


def test_fresh_semantic_hit_inside_limit5_window(test_db, monkeypatch):
    """Guard (REL-013/024): a fresh fact that is the semantic rank 1 with no
    keyword overlap lands inside FRIDAY's normal recall window."""
    actor, ns = _actor_ns(test_db)

    for i in range(8):
        _record(
            test_db, ns, actor.id,
            f"Chatter about the harbour roster and the winter watch rotation {i}.",
        )
    fact = _record(
        test_db, ns, actor.id,
        "The owner's favourite snack is roasted makhana sprinkled with sea salt.",
    )
    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=fact.id, score=0.81, payload={})]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="what does the boss enjoy munching",
        actor_name="friday",
        limit=5,
    )
    ids = [r.record.id for r in results]
    assert fact.id in ids
    assert {r.record.id: r for r in results}[fact.id].semantic_score == pytest.approx(0.81)
