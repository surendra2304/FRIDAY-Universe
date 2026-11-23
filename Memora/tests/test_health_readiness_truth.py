import json

import pytest
from fastapi import HTTPException

from apps.api.routers import health
from storage.relational.session import get_db
import storage.relational.session as session_mod
from storage.vector.qdrant_adapter import QdrantVectorAdapter


class DatabaseProbe:
    def execute(self, _statement):
        return 1


class FailingDatabaseProbe:
    def execute(self, _statement):
        raise RuntimeError("connection refused")


class _HealthyCircuits:
    """circuit_registry stub: no breaker open."""

    def healthy(self):
        return True

    def snapshot(self):
        return {}


class _OpenCircuits:
    """circuit_registry stub: the named breakers are open."""

    def __init__(self, names):
        self._names = names

    def healthy(self):
        return False

    def snapshot(self):
        return {n: {"state": "open", "name": n} for n in self._names}


def _oracle_receipt(monkeypatch):
    monkeypatch.setattr(
        health,
        "storage_receipt",
        lambda: {"backend": "oracle", "durable": True, "durability": "shared_durable"},
    )


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
        ({"status": "available", "available": True, "backend": "oracle_23ai_native_vector"}, "ok", 200),
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
    _oracle_receipt(monkeypatch)
    monkeypatch.setattr(health.oracle_vector_adapter, "readiness", lambda: vector_status)
    # The registry is process-global; pin it healthy so this test measures
    # the vector leg only, not breakers registered by other test files.
    monkeypatch.setattr(health, "circuit_registry", _HealthyCircuits())

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == expected_http
    assert body["status"] == expected_status
    assert body["vector_store"] == vector_status


def test_health_returns_capability_report_when_all_probes_pass(monkeypatch):
    # REL-004 §2.2: every required capability and dependency is reported
    # with a closed-vocabulary state, and the top-level status is derived.
    _oracle_receipt(monkeypatch)
    monkeypatch.setattr(
        health.oracle_vector_adapter,
        "readiness",
        lambda: {"status": "available", "available": True, "backend": "oracle_23ai_native_vector"},
    )
    monkeypatch.setattr(health, "circuit_registry", _HealthyCircuits())

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["evidence_class"] == "capability_report"
    assert body["capabilities"]["memory_store"]["state"] == "ok"
    assert body["capabilities"]["event_store"]["state"] == "ok"
    assert body["capabilities"]["vector_search"]["state"] == "ok"
    assert body["dependencies"]["database"]["state"] == "ok"
    assert body["dependencies"]["vector_store"]["state"] == "ok"
    assert body["dependencies"]["circuit_breakers"]["state"] == "ok"
    # No detail code on an ok entry (REL-004 §2.2 rule 5).
    assert "detail" not in body["capabilities"]["memory_store"]
    # Every pre-existing field is kept.
    assert body["service"] == "memora"
    assert body["database"] == "healthy"
    assert body["event_store"] == "oracle_database"
    assert body["version"] == "2.0.0"


def test_health_vector_not_initialized_names_failing_capability(monkeypatch):
    _oracle_receipt(monkeypatch)
    monkeypatch.setattr(
        health.oracle_vector_adapter,
        "readiness",
        lambda: {"status": "not_initialized", "available": False, "backend": "oracle_23ai_native_vector"},
    )
    monkeypatch.setattr(health, "circuit_registry", _HealthyCircuits())

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["capabilities"]["vector_search"]["state"] == "unavailable"
    assert body["capabilities"]["vector_search"]["detail"] == "VECTOR_STORE_NOT_INITIALIZED"
    assert body["dependencies"]["vector_store"]["state"] == "unavailable"
    assert body["dependencies"]["vector_store"]["detail"] == "VECTOR_STORE_NOT_INITIALIZED"
    # The passing legs stay ok and carry no detail.
    assert body["capabilities"]["memory_store"]["state"] == "ok"
    assert body["capabilities"]["event_store"]["state"] == "ok"


def test_health_database_failure_is_unavailable_not_ok(monkeypatch):
    _oracle_receipt(monkeypatch)
    monkeypatch.setattr(
        health.oracle_vector_adapter,
        "readiness",
        lambda: {"status": "available", "available": True, "backend": "oracle_23ai_native_vector"},
    )
    monkeypatch.setattr(health, "circuit_registry", _HealthyCircuits())

    response = health.health_check(db=FailingDatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["capabilities"]["memory_store"]["state"] == "unavailable"
    assert body["capabilities"]["memory_store"]["detail"] == "DATABASE_UNREACHABLE"
    assert body["dependencies"]["database"]["state"] == "unavailable"
    # Only the exception class name is recorded, never the message text
    # (REL-004 §2.2 rule 8: no raw exception text in a health payload).
    assert "connection refused" not in json.dumps(body)
    assert body["capabilities"]["event_store"]["state"] == "ok"


def test_health_open_circuit_breaker_degrades(monkeypatch):
    _oracle_receipt(monkeypatch)
    monkeypatch.setattr(
        health.oracle_vector_adapter,
        "readiness",
        lambda: {"status": "available", "available": True, "backend": "oracle_23ai_native_vector"},
    )
    monkeypatch.setattr(health, "circuit_registry", _OpenCircuits(["qdrant"]))

    response = health.health_check(db=DatabaseProbe())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["dependencies"]["circuit_breakers"]["state"] == "degraded"
    assert body["dependencies"]["circuit_breakers"]["detail"] == "CIRCUIT_BREAKER_OPEN"
    assert "qdrant" in body["dependencies"]["circuit_breakers"]["evidence"]
    assert body["capabilities"]["memory_store"]["state"] == "ok"


def test_get_db_rejects_unready_storage_with_503(monkeypatch):
    # REL-004 §6 Q5, resolved from source (Memora/storage/relational/
    # session.py get_db): when storage is not ready the dependency itself
    # raises HTTPException 503, so FastAPI answers 503 and the /health
    # handler body never runs. The failure mode is an honest 503, not a
    # 500 and not a 200 with a stale body.
    monkeypatch.setattr(session_mod, "storage_ready", lambda: False)

    with pytest.raises(HTTPException) as excinfo:
        next(get_db())

    assert excinfo.value.status_code == 503
    assert "production storage is unavailable" in str(excinfo.value.detail)
