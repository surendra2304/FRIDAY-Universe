"""
TASK-REL-013 regression tests: semantic search must read the vector store
the write pipeline actually upserts into.

Production defect: MemoryWriteService upserts embeddings via the Oracle
adapter when the relational backend is Oracle, but SearchService.hybrid_search
queried only the Qdrant adapter — whose in-memory mock is empty in
production — so the semantic leg never produced a hit and all recall was
lexical. /health also hardcoded vector availability on the Oracle backend
while /health/ready reported the Qdrant mock's state.

These tests pin the backend-coherent branch in SearchService and the
truthful vector reporting in /health and /health/ready.
"""
import importlib
import json

import pytest

from apps.api.routers import health
from core.identity.service import IdentityService
from core.memory import search_service as search_module
from core.memory.search_service import SearchService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType
from storage.vector.embedding import EmbeddingGenerator
from storage.vector.qdrant_adapter import VectorSearchResult, vector_adapter

# storage/vector/__init__.py re-exports the adapter singleton under the same
# name as the submodule, so import the module itself explicitly.
oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


class StubOracleAdapter:
    """Oracle-adapter stand-in returning a fixed hit set."""

    def __init__(self, hits, backend=True):
        self._hits = hits
        self._backend = backend
        self.search_calls = []

    def is_oracle_backend(self):
        return self._backend

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        self.search_calls.append(
            {"limit": limit, "tenant_id": tenant_id, "score_threshold": score_threshold}
        )
        return list(self._hits)


class ExplodingQdrant:
    """Fails the test if the Qdrant adapter is consulted on the Oracle path."""

    def search_similarity(self, **kwargs):  # pragma: no cover - guard rail
        raise AssertionError("Qdrant adapter consulted while Oracle backend is active")


def _seed_record(test_db, agent_name="friday"):
    agent = IdentityService.register_agent(test_db, agent_name)
    ns = IdentityService.get_namespace_by_path(test_db, f"memora://{agent_name}/private")
    record = MemoryRecord(
        namespace_id=ns.id,
        owner_id=agent.id,
        memory_type=MemoryType.SEMANTIC,
        content_text="Turquoise warehouse vehicle transports fragrant cereal sacks weekly",
        confidence=0.9,
        importance=0.8,
        lifecycle_state=LifecycleState.ACTIVE,
    )
    test_db.add(record)
    test_db.commit()
    return record


# The query shares no token with the seeded content, so the lexical leg
# cannot produce the hit; only the vector leg can.
PARAPHRASE_QUERY = "machine shifts aromatic rice bags"


def test_hybrid_search_reads_oracle_vector_store_on_oracle_backend(test_db, monkeypatch):
    record = _seed_record(test_db)
    stub = StubOracleAdapter(
        [VectorSearchResult(memory_id=record.id, score=0.83, payload={})]
    )
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)
    monkeypatch.setattr(search_module, "vector_adapter", ExplodingQdrant())

    results = SearchService.hybrid_search(
        db=test_db,
        query_text=PARAPHRASE_QUERY,
        actor_name="friday",
        limit=5,
    )

    assert [r.record.id for r in results] == [record.id]
    top = results[0]
    assert top.semantic_score == pytest.approx(0.83)
    assert top.keyword_score == 0.0
    assert any("Semantic match" in reason for reason in top.match_reasons)
    assert stub.search_calls, "Oracle vector adapter was not consulted"


def test_hybrid_search_no_oracle_hits_means_no_semantic_recall(test_db, monkeypatch):
    _seed_record(test_db)
    stub = StubOracleAdapter([])
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)
    monkeypatch.setattr(search_module, "vector_adapter", ExplodingQdrant())

    results = SearchService.hybrid_search(
        db=test_db,
        query_text=PARAPHRASE_QUERY,
        actor_name="friday",
        limit=5,
    )

    assert results == []


def test_hybrid_search_uses_qdrant_when_backend_is_not_oracle(test_db, monkeypatch):
    record = _seed_record(test_db)
    stub = StubOracleAdapter([], backend=False)
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", stub)
    vector_adapter.upsert_embedding(
        record.id, EmbeddingGenerator.generate_embedding(record.content_text)
    )

    results = SearchService.hybrid_search(
        db=test_db,
        query_text="turquoise warehouse vehicle",
        actor_name="friday",
        limit=5,
    )

    assert record.id in [r.record.id for r in results]
    assert stub.search_calls == [], "Oracle search ran despite non-Oracle backend"


class DatabaseProbe:
    def execute(self, _statement):
        return 1


def _patch_oracle_health(monkeypatch, readiness):
    monkeypatch.setattr(
        health,
        "storage_receipt",
        lambda: {"backend": "oracle", "durable": True, "durability": "shared_durable"},
    )
    monkeypatch.setattr(health.oracle_vector_adapter, "readiness", lambda: readiness)


def test_health_reports_oracle_vector_not_initialized(monkeypatch):
    _patch_oracle_health(
        monkeypatch,
        {
            "status": "not_initialized",
            "available": False,
            "backend": "oracle_23ai_native_vector",
            "dimension": 384,
            "table": "memora_vector_store",
        },
    )

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["vector_store"]["status"] == "not_initialized"
    assert body["vector_store"]["available"] is False


def test_health_reports_oracle_vector_available(monkeypatch):
    _patch_oracle_health(
        monkeypatch,
        {
            "status": "available",
            "available": True,
            "backend": "oracle_23ai_native_vector",
            "dimension": 384,
            "table": "memora_vector_store",
        },
    )

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "healthy"
    assert body["vector_store"]["backend"] == "oracle_23ai_native_vector"
    assert body["vector_store"]["available"] is True


def test_ready_reports_oracle_vector_status(monkeypatch):
    _patch_oracle_health(
        monkeypatch,
        {
            "status": "not_initialized",
            "available": False,
            "backend": "oracle_23ai_native_vector",
            "dimension": 384,
            "table": "memora_vector_store",
        },
    )

    response = health.readiness_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "unready"
    # The readiness probe must name the ACTIVE backend's state, not the
    # Qdrant mock's "in_memory".
    assert body["vector_store"] == "not_initialized"
