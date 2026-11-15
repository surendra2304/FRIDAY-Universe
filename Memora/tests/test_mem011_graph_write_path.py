"""
TASK-MEM-011 — graph companion edges on the Memora write path.

Origin: TASK-MEM-002's live recall benchmark reported the
graph_companion_guard case failing with graph_boost 0.0 and attributed it
to "the production write path did not apply the companion edge". The
MEM-011 live investigation (production, 2026-11-15) proved that attribution
wrong, with evidence:

- Explicit edges persist: POST /v1/memories/{id}/relationships rows were
  read back via GET /v1/memories/{id}/graph (both directions, weight 0.95).
- Auto-link fires on write: two probe records sharing the canonical entity
  "redis" were linked by a shares_entity edge (weight 0.8) with no explicit
  relationship call.
- The graph leg is alive in production search: instrumenting the deployed
  hybrid_search showed get_graph_neighbors returning boosts for six
  records in one traced query.
- The benchmark's companions showed 0.0 because graph expansion is
  seed-local by design: only non-seed neighbours of the top-5 vector /
  top-5 keyword hits are boosted, and the benchmark web's hub ranked 77th
  lexically for the guard query (33 legacy records matched 3/7 query tokens
  vs the hub's 2/7), so no seed ever touched the web. The 0.0 in MEM-002's
  report was the *snack* record's graph_boost — a record with no edges,
  correctly 0.0.
- Blast radius: of 419 active production records, 131 share a canonical
  entity with another record and 129 of those are linked to a partner;
  only 2 lack an edge. No systemic missing-edge problem.

What WAS defective on the write path: when GraphService.auto_link_entity_memories
raises, the pipeline swallowed the exception at logger.debug and the step
trace recorded graph_links_created: 0 — indistinguishable from "nothing to
link". A silent skip is exactly how a healthy write path came to look
broken. The fix keeps the fail-soft contract (a graph failure must not
fail the write) but surfaces the failure: a WARNING log plus a
graph_link_error entry in step_9_persistence.

Tests:
- test_auto_link_failure_is_surfaced_not_silent — FAILS on clean main
  (no graph_link_error key, no WARNING), passes with the fix.
- test_auto_link_success_records_no_error — FAILS on clean main
  (graph_link_error key absent), passes with the fix.
- The remaining tests pin the proven behaviour (they pass on main too):
  auto-link creates the companion edge, explicit edges persist and are
  traversable, companions of a direct hit receive the bounded boost, and
  the benchmark's guard shape holds offline (companions never outrank the
  direct semantic hit).
"""
import importlib
import logging

import pytest

from core.identity.service import IdentityService
from core.memory.graph_service import GraphService
from core.memory.pipeline.write_service import MemoryWriteService
from core.memory.search_service import SearchService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryRelationship, MemoryType
from storage.vector.qdrant_adapter import VectorSearchResult

oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


def _write(test_db, content, **kwargs):
    return MemoryWriteService.execute_pipeline(
        db=test_db, caller_name="friday", content_text=content, **kwargs
    )


# ---------------------------------------------------------------------------
# Write path: auto-link creates the companion edge (behaviour pin)
# ---------------------------------------------------------------------------

def test_write_auto_links_shared_entity_companion(test_db):
    IdentityService.register_agent(test_db, "friday")
    first = _write(test_db, "drill note one: the staging cache runs on redis for this exercise")
    second = _write(test_db, "drill note two: redis persistence was checked during the exercise")

    rels = test_db.query(MemoryRelationship).filter(
        MemoryRelationship.relationship_type == "shares_entity"
    ).all()
    pairs = {(r.source_memory_id, r.target_memory_id) for r in rels}
    assert (second.record.id, first.record.id) in pairs
    step9 = second.step_outputs["step_9_persistence"]
    assert step9["graph_links_created"] >= 1


def test_auto_link_success_records_no_error(test_db):
    """With the fix, step_9 always carries graph_link_error (None on success).

    On clean main the key is absent, so this fails there and passes here.
    """
    IdentityService.register_agent(test_db, "friday")
    _write(test_db, "a plain note about redis caching for the team")
    result = _write(test_db, "another note: redis again, for the record")
    step9 = result.step_outputs["step_9_persistence"]
    assert "graph_link_error" in step9
    assert step9["graph_link_error"] is None


def test_auto_link_failure_is_surfaced_not_silent(test_db, monkeypatch, caplog):
    """An auto-link exception must not fail the write — but must be visible.

    FAILS on clean main: the exception was swallowed at logger.debug and
    step_9 recorded only graph_links_created: 0, indistinguishable from a
    record with nothing to link.
    """
    IdentityService.register_agent(test_db, "friday")
    _write(test_db, "baseline note mentioning redis so a partner exists")

    def _boom(db, record, extraction_data):
        raise RuntimeError("graph store unavailable (test)")

    monkeypatch.setattr(GraphService, "auto_link_entity_memories", _boom)

    with caplog.at_level(logging.WARNING, logger="core.memory.pipeline.write_service"):
        result = _write(test_db, "a second note mentioning redis as well")

    # Fail-soft: the write itself still succeeds and persists.
    assert result.record.id
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == result.record.id).first()

    step9 = result.step_outputs["step_9_persistence"]
    assert step9["graph_links_created"] == 0
    assert step9.get("graph_link_error")
    assert "RuntimeError" in step9["graph_link_error"]
    assert any(
        r.levelno >= logging.WARNING and "auto-linking failed" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Explicit edges: persist, traverse, and feed graph expansion (behaviour pins)
# ---------------------------------------------------------------------------

def test_explicit_relationship_persists_and_traverses(test_db):
    IdentityService.register_agent(test_db, "friday")
    a = _write(test_db, "alpha record about quixotic zephyr jamboree kettle lantern").record
    b = _write(test_db, "beta record about mundane scheduling paperwork filing cabinets").record

    GraphService.create_relationship(
        test_db, source_memory_id=a.id, target_memory_id=b.id,
        relationship_type="relates_to", weight=0.95)
    GraphService.create_relationship(
        test_db, source_memory_id=b.id, target_memory_id=a.id,
        relationship_type="relates_to", weight=0.95)

    graph = GraphService.get_connected_memories(test_db, memory_id=a.id, max_hops=1)
    assert b.id in graph["connected_memory_ids"]

    boosts = GraphService.get_graph_neighbors(test_db, [a.id], tenant_id="default")
    assert boosts[b.id] == pytest.approx(0.285, abs=0.001)


class StubOracleAdapter:
    """REL-024 pattern: fixed semantic hit set so ranks are deterministic."""

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


def _link(test_db, source_id, target_id, weight=0.95):
    return GraphService.create_relationship(
        test_db,
        source_memory_id=source_id,
        target_memory_id=target_id,
        relationship_type="relates_to",
        weight=weight,
    )


def test_companion_receives_bounded_boost_when_hub_is_direct_hit(test_db, monkeypatch):
    """The companion mechanism the guard relies on: a record whose only path
    to the query is its edge to a direct hit is pulled into the results with
    the bounded graph boost (2 edges x 0.95 x 0.15), below the hit itself."""
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")

    query = "quixotic zephyr jamboree kettle lantern vexholm central mem011twin"
    hub = _record(
        test_db, ns, actor.id,
        "mem011twin hub record: quixotic zephyr jamboree kettle lantern vexholm central",
        importance=0.95,
    )
    companions = [
        _record(
            test_db, ns, actor.id,
            f"mem011twin companion note {i}: municipal accounting ledger reconciliation "
            "procedures for fiscal auditors in the district treasury office",
            importance=0.9,
        )
        for i in range(2)
    ]
    fillers = [
        _record(
            test_db, ns, actor.id,
            f"quixotic zephyr filler briefing note {n}",
            id=f"00000000-0000-4000-8000-00000000000{n}",
        )
        for n in range(5)
    ]
    for comp in companions:
        _link(test_db, hub.id, comp.id)
        _link(test_db, comp.id, hub.id)

    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=hub.id, score=0.90, payload={})]
        + [VectorSearchResult(memory_id=f.id, score=0.80 - 0.01 * i, payload={})
           for i, f in enumerate(fillers)]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db, query_text=query, actor_name="friday", limit=25
    )
    by_id = {r.record.id: r for r in results}
    assert hub.id in by_id
    for comp in companions:
        assert comp.id in by_id, "graph companion must be pulled into the results"
        assert by_id[comp.id].graph_boost == pytest.approx(0.285, abs=0.02)
        assert by_id[comp.id].final_score < by_id[hub.id].final_score


def test_graph_companion_guard_offline_twin(test_db, monkeypatch):
    """Offline twin of MEM-002's graph_companion_guard case (same texts,
    same query): a heavily graph-connected hub and its companions never
    outrank the direct semantic hit."""
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    token = "mem011twin"

    snack = _record(
        test_db, ns, actor.id,
        f"Benchmark record {token}: the owner's favourite snack is roasted "
        "makhana sprinkled with sea salt.",
    )
    hub = _record(
        test_db, ns, actor.id,
        f"Benchmark hub {token}: the central planning hub record linking "
        "the benchmark companion notes.",
        importance=0.95,
    )
    companions = [
        _record(
            test_db, ns, actor.id,
            f"Benchmark companion {token}-{i}: a planning note about scheduling "
            "and the weekly review, linked to the hub.",
            importance=0.9,
        )
        for i in range(3)
    ]
    for comp in companions:
        _link(test_db, hub.id, comp.id)
        _link(test_db, comp.id, hub.id)

    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=snack.id, score=0.74, payload={}),
         VectorSearchResult(memory_id=hub.id, score=0.61, payload={})]
        + [VectorSearchResult(memory_id=c.id, score=0.58, payload={}) for c in companions]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)

    results = SearchService.hybrid_search(
        db=test_db,
        query_text=f"what does the boss enjoy munching {token}",
        actor_name="friday",
        limit=100,
    )
    ids = [r.record.id for r in results]
    by_id = {r.record.id: r for r in results}
    assert ids.index(snack.id) == 0
    for comp in companions:
        assert by_id[comp.id].final_score < by_id[snack.id].final_score
