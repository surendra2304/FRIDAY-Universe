"""Actual relational retrieval; optional vector boundary explicitly disabled."""
from core.identity.service import IdentityService
from core.memory.graph_service import GraphService
from core.memory.search_service import SearchService
from storage.relational.models import MemoryRecord, MemoryType, LifecycleState
from storage.vector.qdrant_adapter import vector_adapter


def test_graph_only_popularity_cannot_bury_direct_owner_observation(test_db, monkeypatch):
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    match = MemoryRecord(namespace_id=ns.id, owner_id=actor.id, memory_type=MemoryType.EPISODIC,
                         content_text="Owner requires actual successful tasks not invented completion percentages",
                         confidence=1.0, importance=0.95, lifecycle_state=LifecycleState.ACTIVE)
    unrelated = MemoryRecord(namespace_id=ns.id, owner_id=actor.id, memory_type=MemoryType.EPISODIC,
                             content_text="Graph-only unrelated database migration notes",
                             confidence=1.0, importance=0.95, lifecycle_state=LifecycleState.ACTIVE)
    test_db.add_all([match, unrelated]);test_db.commit()
    monkeypatch.setattr(vector_adapter, "search_similarity", lambda **_: [])
    # Real symptom: graph-only score0.42 outranks lexical0.14. The external
    # graph boundary is a declared fixture, relational scope/scoring are real.
    monkeypatch.setattr(GraphService, "get_graph_neighbors", lambda *a, **k: {unrelated.id: 0.14})
    kwargs = dict(db=test_db, query_text="actual successful tasks invented completion percentages",
                  actor_name="friday", min_score=0.0)
    results = SearchService.hybrid_search(**kwargs, limit=2)
    assert [r.record.id for r in results] == [match.id, unrelated.id]
    assert results[1].final_score > results[0].final_score
    assert results[0].keyword_score == 1.0
    assert results[1].keyword_score == results[1].semantic_score == 0
    assert SearchService.hybrid_search(**kwargs, limit=1)[0].record.id == match.id
