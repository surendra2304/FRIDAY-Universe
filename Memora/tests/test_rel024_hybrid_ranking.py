"""
TASK-REL-024 regression tests: the graph term in hybrid search must be a
bounded secondary signal, not a saturating one.

Production defect (live-verified 2026-11-14, Server 1): in the merged
hybrid result list for a zero-overlap paraphrase query, 36 legacy
graph-connected records saturated final_score at 1.0 via graph boosts
(+0.26..+0.69) while the semantic rank-1 fresh fact (sim 0.76) scored
0.3744 and landed at position 54 (limit=100) — outside FRIDAY's production
recall windows (limit 5 and 25). Mechanism: SearchService.hybrid_search
added the graph term RAW (graph_weight * g_boost) while the semantic and
keyword legs are RRF terms damped by 1/(rrf_k + rank); the sum is scaled by
rrf_k/2 (=30) and capped at 1.0, and GraphService.get_graph_neighbors
accumulates weight * 0.15 per incident edge with no bound. With the shipped
config (dense_vector 0.6, bm25 0.3, graph_walk 0.1, rrf_k 60) a perfect
rank-1 semantic + rank-1 keyword hit scores ~0.44, while g_boost >= ~0.34
alone pins a record at 1.0.

The fix squashes the accumulated graph weight into (0, 1) and damps it like
an RRF leg, so its maximum contribution is proportional to graph_weight
exactly as the other legs are to theirs.

These tests use real relational records and real graph edges; only the
vector boundary is stubbed (declared fixture, as in REL-013's tests) so the
semantic ranks are deterministic.
"""
import importlib

import pytest

from core.identity.service import IdentityService
from core.memory.graph_service import GraphService
from core.memory.search_service import SearchService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType
from storage.vector.qdrant_adapter import VectorSearchResult

# storage/vector/__init__.py re-exports the adapter singleton under the same
# name as the submodule, so import the module itself explicitly.
oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


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
        memory_type=MemoryType.EPISODIC,
        content_text=content,
        confidence=kwargs.pop("confidence", 0.9),
        importance=kwargs.pop("importance", 0.8),
        lifecycle_state=LifecycleState.ACTIVE,
        **kwargs,
    )
    test_db.add(record)
    test_db.commit()
    return record


def _link(test_db, source_id, target_id, weight=0.92):
    return GraphService.create_relationship(
        test_db,
        source_memory_id=source_id,
        target_memory_id=target_id,
        relationship_type="relates_to",
        weight=weight,
    )


PARAPHRASE = "who tends the beacon at the southern tip during rainy season dusk"
LIGHTHOUSE = (
    "The lighthouse keeper at Kanyakumari polishes the brass lantern "
    "every monsoon evening before the fishing boats return."
)


def test_graph_boosts_cannot_saturate_or_bury_semantic_hit(test_db, monkeypatch):
    """Mirror of the live incident: hubs with maximal graph connectivity and
    only function-word keyword overlap must not outrank — or saturate above —
    the strongly semantic fresh fact."""
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")

    # Five chatter records with the highest keyword overlap (function words
    # plus a content token or two). They become the keyword top-5 graph
    # seeds, exactly as popular dialogue records do in production.
    chatter = [
        _record(
            test_db, ns, actor.id,
            f"Who keeps the log at the southern depot during the rainy season shift {n}",
        )
        for n in range(5)
    ]
    # The fresh fact: semantic target, only "the"/"at" keyword overlap.
    fact = _record(test_db, ns, actor.id, LIGHTHOUSE)
    # Four hubs: function-word overlap only (the/at/during = 3/11, the same
    # 0.2727 seen on production's saturating records), each wired to all
    # five seeds with near-maximal edges -> g_boost = 5 * 0.92 * 0.15 = 0.69,
    # production's observed maximum.
    hubs = [
        _record(
            test_db, ns, actor.id,
            f"Notes about the routine at the depot during roster planning {n}",
        )
        for n in range(4)
    ]
    for hub in hubs:
        for seed in chatter:
            _link(test_db, hub.id, seed.id, weight=0.92)

    # Semantic ranks: chatter[0] rank 1, the fresh fact rank 2 (sim 0.76),
    # mirroring the production probe.
    stub = StubOracleAdapter(
        [
            VectorSearchResult(memory_id=chatter[0].id, score=0.90, payload={}),
            VectorSearchResult(memory_id=fact.id, score=0.76, payload={}),
        ]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db, query_text=PARAPHRASE, actor_name="friday", limit=25
    )
    ids = [r.record.id for r in results]
    by_id = {r.record.id: r for r in results}

    # The fresh fact is inside FRIDAY's widest production recall window and
    # near the top — not buried under the hubs.
    assert fact.id in ids
    assert ids.index(fact.id) <= 1
    # No record saturates: the 1.0 cap is no longer reachable from these
    # signals (the strongest possible relevance here scores ~0.44).
    assert all(r.final_score < 0.9 for r in results)
    # Every hub — despite maximal graph connectivity (raw boost 0.69) —
    # scores below the semantic hit, and its graph term stays a small
    # secondary contribution.
    for hub in hubs:
        assert by_id[hub.id].graph_boost == pytest.approx(0.69, abs=0.02)
        assert by_id[hub.id].final_score < by_id[fact.id].final_score
    # And inside FRIDAY's normal recall window (limit=5) the fact survives.
    small = SearchService.hybrid_search(
        db=test_db, query_text=PARAPHRASE, actor_name="friday", limit=5
    )
    assert fact.id in [r.record.id for r in small]


def test_graph_boost_breaks_ties_between_equally_relevant_records(test_db, monkeypatch):
    """Graph stays a working secondary signal: between two records with
    (near-)identical query relevance, the graph-connected one wins — by a
    small, bounded margin."""
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")

    query = "harbour roster winter watch"
    # Five filler records tie at full keyword overlap with ids that sort
    # first, so they take keyword ranks 1-5 (and the graph-seed slots).
    fillers = [
        _record(
            test_db, ns, actor.id,
            "harbour roster winter watch briefing",
            id=f"00000000-0000-4000-8000-00000000000{n}",
        )
        for n in range(5)
    ]
    # Identical content -> identical relevance. B holds the better keyword
    # rank (its id wins the lexical tie-break); A is graph-connected to the
    # semantic seed. A must still win, via the graph term alone.
    twin_b = _record(
        test_db, ns, actor.id,
        "harbour roster winter watch shared note",
        id="aaaaaaaa-0000-4000-8000-00000000000b",
    )
    twin_a = _record(
        test_db, ns, actor.id,
        "harbour roster winter watch shared note",
        id="zzzzzzzz-0000-4000-8000-00000000000a",
    )
    _link(test_db, twin_a.id, fillers[0].id, weight=0.95)

    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=fillers[0].id, score=0.90, payload={})]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db, query_text=query, actor_name="friday", limit=10
    )
    ids = [r.record.id for r in results]
    by_id = {r.record.id: r for r in results}

    assert twin_a.id in ids and twin_b.id in ids
    assert ids.index(twin_a.id) < ids.index(twin_b.id)
    margin = by_id[twin_a.id].final_score - by_id[twin_b.id].final_score
    assert 0.0 < margin < 0.05
    assert by_id[twin_a.id].graph_boost > 0.0
    assert any(
        "Graph connection boost" in reason
        for reason in by_id[twin_a.id].match_reasons
    )


def test_graph_only_companion_still_surfaces_after_direct_matches(test_db, monkeypatch):
    """Graph-shaped expansion is preserved: a record with no lexical or
    semantic match of its own still surfaces via its graph connection —
    after every direct-evidence record."""
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")

    query = "harbour roster winter watch"
    seed = _record(test_db, ns, actor.id, "harbour roster winter watch briefing")
    _record(test_db, ns, actor.id, "harbour roster winter watch shared note")
    companion = _record(
        test_db, ns, actor.id, "Zeppelin hangar tide tables archive"
    )
    _link(test_db, companion.id, seed.id, weight=0.95)

    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=seed.id, score=0.90, payload={})]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db, query_text=query, actor_name="friday", limit=10
    )
    ids = [r.record.id for r in results]

    assert companion.id in ids
    assert ids[-1] == companion.id
    companion_item = results[-1]
    assert companion_item.graph_boost > 0.0
    assert companion_item.keyword_score == companion_item.semantic_score == 0.0
    for item in results[:-1]:
        assert item.keyword_score > 0.0 or item.semantic_score > 0.0
