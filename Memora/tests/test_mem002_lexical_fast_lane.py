"""
TASK-MEM-002 follow-up — the Memora lexical fast lane.

Production evidence behind this suite: the MEM-002 AFTER benchmark
(2026-11-16) put a production hybrid draw at p50 ~3.9s, and FRD-005
re-run #6 measured a ~32s draw phase under load — the recall leg that
FRIDAY's voice path waits on. The fast lane serves the one class of
query whose answer the lexical evidence already decides — a record
containing EVERY content token of the query (exact / subject-shaped
full match) — without the embedding call, the vector round-trip or
graph expansion, through the same `SearchService.hybrid_search` the
production `/v1/memories/search` route calls.

Pins:
  1. A question-shaped full match ("What is my favorite color?") is
     served by the lane: the embedding generator and the vector adapter
     are NEVER invoked (the latency claim, made testable).
  2. A subject-shaped query ranks two full-match versions newest-first
     (the MEM-002 recency guarantee, through the lane).
  3. A partial match does NOT fire the lane (hybrid runs).
  4. A zero-overlap paraphrase does NOT fire the lane and the hybrid
     semantic fallback is unchanged (REL-013 guarantee).
  5-8. The lane never widens admissibility: superseded, expired,
     other-tenant and tampered-provenance full matches are never
     served by it.
  9. The retrieval-config kill switch ("lexical_fast_lane": false)
     restores the pure hybrid path.
 10. The FRD-017 forensics named acceptance shapes — the exact client
     draws that missed in FRD-005 re-run #7 ('What is my favorite
     color' and 'my favorite color', limit 10, against a store
     mirroring production's teal/chai/ZQ records) — return both teal
     records on top, from the lane.
 11. Spelling variants canonicalise both directions (FRD-014's map):
     UK-stored fact vs US query, UK query vs US-stored fact.
 12. The lane serves a full match even when the vector boundary is
     broken (the distress shape): it never invokes it.

On clean main (no lane) tests 1, 2, 5, 7, 8, 10, 11 and 12 fail on
the vector-leg-invocation assertions; 3, 4, 6 and 9 describe fallback
behaviour that must hold on both trees.
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
search_service_module = importlib.import_module("core.memory.search_service")

BASE_TS = datetime(2026, 11, 15, 6, 0, 0, tzinfo=timezone.utc)


class StubOracleAdapter:
    """Oracle-adapter stand-in returning a fixed hit set (REL-013 pattern)."""

    def __init__(self, hits):
        self._hits = hits

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return list(self._hits)


class CountingOracleAdapter(StubOracleAdapter):
    def __init__(self, hits):
        super().__init__(hits)
        self.calls = 0

    def search_similarity(self, *args, **kwargs):
        self.calls += 1
        return super().search_similarity(*args, **kwargs)


class FakeEmbeddingGenerator:
    """Counts invocations; hybrid_search must not call it on a lane hit."""

    def __init__(self):
        self.calls = 0

    def generate_embedding(self, text):
        self.calls += 1
        return [0.1] * 8


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


def _instrument(monkeypatch, hits=None):
    """Install the counting vector boundary; returns (embedding, adapter)."""
    embedding = FakeEmbeddingGenerator()
    adapter = CountingOracleAdapter(hits or [])
    monkeypatch.setattr(search_service_module, "EmbeddingGenerator", embedding)
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", adapter)
    return embedding, adapter


def _fast_lane_reasons(result):
    return [r for r in result.match_reasons if "Lexical fast lane" in r]


def test_fast_lane_serves_question_shaped_full_match_without_vector_leg(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    fact = _record(test_db, ns, actor.id, "My favorite color is teal.")
    _record(test_db, ns, actor.id, "The weekly planning checklist and the office rota.")
    _record(test_db, ns, actor.id, "Notes about the canteen menu and parking roster.")
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="What is my favorite color?",
        actor_name="friday",
        limit=5,
    )
    assert results, "fast lane returned nothing for a full match"
    assert results[0].record.id == fact.id
    assert _fast_lane_reasons(results[0]), "top hit was not served by the fast lane"
    assert results[0].keyword_score > 0
    assert embedding.calls == 0, "embedding generator invoked on a fast-lane hit"
    assert adapter.calls == 0, "vector adapter invoked on a fast-lane hit"


def test_fast_lane_subject_shaped_query_prefers_newer_version(test_db, monkeypatch):
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
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db, query_text="workshop door code", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert ids.index(newer.id) < ids.index(older.id), (
        "fast lane ranked the stale version first"
    )
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_not_fired_by_partial_match(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    _record(test_db, ns, actor.id, "The workshop door code is 1111.")
    embedding, adapter = _instrument(monkeypatch)

    SearchService.hybrid_search(
        db=test_db,
        query_text="workshop door code missingword",
        actor_name="friday",
        limit=5,
    )
    assert embedding.calls >= 1, "partial match was served without the hybrid path"
    assert adapter.calls >= 1


def test_fast_lane_not_fired_for_paraphrase_semantic_fallback(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    fact = _record(
        test_db, ns, actor.id,
        "The owner's favourite snack is roasted makhana sprinkled with sea salt.",
    )
    embedding, adapter = _instrument(
        monkeypatch,
        hits=[VectorSearchResult(memory_id=fact.id, score=0.81, payload={})],
    )

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="what does the boss enjoy munching",
        actor_name="friday",
        limit=5,
    )
    by_id = {r.record.id: r for r in results}
    assert fact.id in by_id, "hybrid semantic fallback lost the paraphrase hit"
    assert by_id[fact.id].semantic_score == pytest.approx(0.81)
    assert not _fast_lane_reasons(by_id[fact.id])
    assert embedding.calls >= 1 and adapter.calls >= 1


def test_fast_lane_never_serves_superseded(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    superseded = _record(
        test_db, ns, actor.id,
        "The offsite retreat city is Kodaikanal.",
        lifecycle_state=LifecycleState.SUPERSEDED,
    )
    live = _record(test_db, ns, actor.id, "The offsite retreat city is Coorg.")
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db, query_text="offsite retreat city", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert live.id in ids
    assert superseded.id not in ids
    # The live record full-matches, so the lane (not the hybrid) served it.
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_never_serves_expired(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    expired = _record(
        test_db, ns, actor.id,
        "The vault combination for the storage locker is 41-07-99.",
        created_at=BASE_TS,
        expires_at=BASE_TS - timedelta(days=1),
    )
    _record(test_db, ns, actor.id, "A note about the garden upkeep schedule.")
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="vault combination storage locker",
        actor_name="friday",
        limit=5,
    )
    ids = [r.record.id for r in results]
    assert expired.id not in ids, "expired full match was served"
    # The only full match was inadmissible, so the lane yielded and the
    # hybrid path ran (and also excluded the expired record).
    assert embedding.calls >= 1


def test_fast_lane_never_serves_other_tenant(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    foreign = _record(
        test_db, ns, actor.id,
        "My favorite color is blue.",
        tenant_id="other-tenant",
    )
    own = _record(test_db, ns, actor.id, "My favorite color is teal.")
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db, query_text="my favorite color", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert own.id in ids
    assert foreign.id not in ids
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_never_serves_tampered_provenance(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    tampered = _record(
        test_db, ns, actor.id,
        "My favorite color is green.",
        provenance={"hmac_signature": "bogus"},
        created_at=BASE_TS + timedelta(minutes=10),
    )
    clean = _record(
        test_db, ns, actor.id,
        "My favorite color is teal.",
        created_at=BASE_TS,
    )
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db, query_text="my favorite color", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert clean.id in ids
    assert tampered.id not in ids, "tampered-provenance record served by the fast lane"
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_named_acceptance_shapes_from_frd017_forensics(test_db, monkeypatch):
    """The exact draws that missed in FRD-005 re-run #7, as the client
    sends them (memora_client strips the trailing '?'): 'What is my
    favorite color' and 'my favorite color', limit 10. The store mirrors
    production: the plain teal fact, the fragment-prefixed teal record
    ('for me. My favorite color is teal.' — production record 65645084's
    actual content), plus the chai and ZQ-marker records that were the
    only hits the distressed draws merged. Both teal records must be
    the lane's top results for both shapes."""
    actor, ns = _actor_ns(test_db)
    teal = _record(test_db, ns, actor.id, "my favorite color is teal.")
    teal_prefixed = _record(test_db, ns, actor.id, "for me. My favorite color is teal.")
    _record(test_db, ns, actor.id, "my favorite chai is masala chai and I review the fleet every morning at 9.")
    _record(test_db, ns, actor.id, "My secret favorite number is owner favorite test marker ZQ1794340686.")
    embedding, adapter = _instrument(monkeypatch)

    for query in ("What is my favorite color", "my favorite color"):
        results = SearchService.hybrid_search(
            db=test_db, query_text=query, actor_name="friday", limit=10
        )
        ids = [r.record.id for r in results]
        assert teal.id in ids and teal_prefixed.id in ids, (
            f"shape {query!r}: a stored teal record missing from the lane's results"
        )
        assert set(ids[:2]) == {teal.id, teal_prefixed.id}, (
            f"shape {query!r}: teal records not on top: {ids[:3]}"
        )
        assert all(_fast_lane_reasons(r) for r in results[:2])
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_spelling_variants_match_both_directions(test_db, monkeypatch):
    """FRD-014 canonicalisation inside the lane: a UK-spelled stored fact
    full-matches a US-spelled query, and a UK-spelled query full-matches
    the US-spelled fact."""
    actor, ns = _actor_ns(test_db)
    uk_fact = _record(test_db, ns, actor.id, "My favourite colour is teal.")
    embedding, adapter = _instrument(monkeypatch)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="What is my favorite color",
        actor_name="friday",
        limit=5,
    )
    assert [r.record.id for r in results] == [uk_fact.id]
    assert _fast_lane_reasons(results[0])

    us_fact = _record(test_db, ns, actor.id, "My favorite color is teal.")
    results = SearchService.hybrid_search(
        db=test_db,
        query_text="What is my favourite colour",
        actor_name="friday",
        limit=5,
    )
    ids = [r.record.id for r in results]
    assert us_fact.id in ids and uk_fact.id in ids
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_serves_even_when_vector_leg_would_fail(test_db, monkeypatch):
    """Distress shape: the embedding call is the stall-prone dependency
    (external API + vector store). The lane never invokes it, so a full
    match is served even with the vector boundary broken. The fakes
    raise on any invocation AND count it, so a lane regression that
    reached the vector leg could not hide behind the fail-soft catch."""
    actor, ns = _actor_ns(test_db)
    fact = _record(test_db, ns, actor.id, "my favorite color is teal.")

    class ExplodingEmbedding:
        def __init__(self):
            self.calls = 0

        def generate_embedding(self, text):
            self.calls += 1
            raise RuntimeError("embedding backend unavailable")

    class ExplodingAdapter(StubOracleAdapter):
        def __init__(self):
            super().__init__([])
            self.calls = 0

        def search_similarity(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("vector store unavailable")

    embedding = ExplodingEmbedding()
    adapter = ExplodingAdapter()
    monkeypatch.setattr(search_service_module, "EmbeddingGenerator", embedding)
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", adapter)

    results = SearchService.hybrid_search(
        db=test_db, query_text="my favorite color", actor_name="friday", limit=5
    )
    assert [r.record.id for r in results] == [fact.id]
    assert _fast_lane_reasons(results[0])
    assert embedding.calls == 0 and adapter.calls == 0


def test_fast_lane_disabled_by_config_falls_back_to_hybrid(test_db, monkeypatch):
    actor, ns = _actor_ns(test_db)
    fact = _record(test_db, ns, actor.id, "My favorite color is teal.")
    embedding, adapter = _instrument(monkeypatch)

    def _config_without_lane():
        return {
            "vector_weight": 0.5,
            "keyword_weight": 0.35,
            "graph_weight": 0.15,
            "entity_boost_weight": 0.10,
            "rrf_k": 60,
            "ranking_factors": {},
            "lexical_fast_lane": False,
        }

    monkeypatch.setattr(search_service_module, "get_retrieval_config", _config_without_lane)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="What is my favorite color?",
        actor_name="friday",
        limit=5,
    )
    ids = [r.record.id for r in results]
    assert fact.id in ids, "hybrid path lost the full match with the lane disabled"
    assert embedding.calls >= 1 and adapter.calls >= 1
    assert not any(_fast_lane_reasons(r) for r in results)
