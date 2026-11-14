import json

import pytest

from apps.api.routers import health
from storage.vector.qdrant_adapter import QdrantVectorAdapter


class DatabaseProbe:
    def execute(self, _statement):
        return 1


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ("production", {"status": "unavailable", "available": False, "backend": "qdrant"}),
        ("development", {"status": "in_memory", "available": True, "backend": "process_local"}),
    ],
)
def test_vector_readiness_distinguishes_production_from_local_fallback(
    monkeypatch, environment, expected
):
    adapter = QdrantVectorAdapter(url="http://localhost:6333")
    monkeypatch.setattr(adapter, "is_production", lambda: environment == "production")

    assert adapter.readiness() == expected


def test_render_environment_forces_production_vector_readiness(monkeypatch):
    adapter = QdrantVectorAdapter(url="http://localhost:6333")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr("storage.vector.qdrant_adapter.settings.MEMORA_ENV", "development")

    assert adapter.is_production() is True
    assert adapter.readiness() == {
        "status": "unavailable",
        "available": False,
        "backend": "qdrant",
    }


def test_render_environment_prevents_ephemeral_vector_writes(monkeypatch):
    from storage.vector.qdrant_adapter import VectorUnavailableError

    adapter = QdrantVectorAdapter(url="http://localhost:6333")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr("storage.vector.qdrant_adapter.settings.MEMORA_ENV", "development")

    with pytest.raises(VectorUnavailableError, match="offline in production"):
        adapter.upsert_embedding("memory-1", [1.0, 0.0], tenant_id="tenant-1")


@pytest.mark.parametrize(
    ("vector_status", "expected_status", "expected_http"),
    [
        ({"status": "available", "available": True, "backend": "oracle_23ai_native_vector"}, "healthy", 200),
        ({"status": "not_initialized", "available": False, "backend": "oracle_23ai_native_vector"}, "degraded", 503),
    ],
)
def test_health_reflects_vector_store_availability(
    monkeypatch, vector_status, expected_status, expected_http
):
    # TASK-REL-013 repair: this test previously patched health.production_mode
    # — a name that has never existed in the health module — so it errored on
    # main before reaching its assertions, and it left the storage receipt at
    # the test harness's sqlite default, whose event-store leg forces a 503
    # regardless of vector state. Patch the receipt to the production (Oracle)
    # shape and the ACTIVE vector adapter's readiness: on the Oracle backend
    # /health reports the Oracle adapter's readiness, not the Qdrant mock's.
    monkeypatch.setattr(
        health,
        "storage_receipt",
        lambda: {"backend": "oracle", "durable": True, "durability": "shared_durable"},
    )
    monkeypatch.setattr(health.oracle_vector_adapter, "readiness", lambda: vector_status)

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == expected_http
    assert body["status"] == expected_status
    assert body["vector_store"] == vector_status

