from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from storage.vector.oracle_vector_adapter import OracleVectorAdapter


class _Savepoint:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, Any]]] = []
        self.savepoints: list[_Savepoint] = []
        self.commit_count = 0
        self.rollback_count = 0

    def begin_nested(self) -> _Savepoint:
        savepoint = _Savepoint()
        self.savepoints.append(savepoint)
        return savepoint

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params or {}))
        return object()

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


@pytest.fixture
def sqlite_vector_adapter(tmp_path: Path, monkeypatch):
    adapter_module = importlib.import_module("storage.vector.oracle_vector_adapter")

    db_path = tmp_path / "vector-isolation.db"
    engine = create_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(adapter_module, "SessionLocal", factory)
    monkeypatch.setattr(
        adapter_module,
        "storage_receipt",
        lambda: {"backend": "sqlite", "durable": False, "durability": "process_local"},
    )

    adapter = OracleVectorAdapter(
        table_name="tenant_vector_test",
        dimension=3,
    )
    monkeypatch.setattr(adapter, "is_oracle_backend", lambda: False)
    assert adapter.ensure_schema() is True

    yield adapter, engine, factory

    engine.dispose()


def test_same_vector_id_cannot_be_reassigned_to_another_tenant(sqlite_vector_adapter):
    adapter, _engine, factory = sqlite_vector_adapter
    vector_a = [1.0, 0.0, 0.0]
    vector_b = [0.0, 1.0, 0.0]

    with factory() as session:
        assert adapter.upsert_embedding(
            "shared-id",
            vector_a,
            payload={"owner": "tenant-a"},
            tenant_id="tenant-a",
            db=session,
        ) is True
        session.commit()

    with factory() as session:
        assert adapter.upsert_embedding(
            "shared-id",
            vector_b,
            payload={"owner": "tenant-b"},
            tenant_id="tenant-b",
            db=session,
        ) is False
        session.commit()

    tenant_a_hits = adapter.search_similarity(
        vector_a,
        tenant_id="tenant-a",
        score_threshold=0.99,
    )
    tenant_b_hits = adapter.search_similarity(
        vector_b,
        tenant_id="tenant-b",
        score_threshold=0.99,
    )

    assert len(tenant_a_hits) == 1
    assert tenant_a_hits[0].memory_id == "shared-id"
    assert tenant_a_hits[0].payload == {"owner": "tenant-a"}
    assert tenant_b_hits == []


def test_same_tenant_can_update_its_vector(sqlite_vector_adapter):
    adapter, _engine, factory = sqlite_vector_adapter
    with factory() as session:
        assert adapter.upsert_embedding(
            "same-tenant-id",
            [1.0, 0.0, 0.0],
            payload={"version": 1},
            tenant_id="tenant-a",
            db=session,
        )
        session.commit()

    with factory() as session:
        assert adapter.upsert_embedding(
            "same-tenant-id",
            [0.0, 1.0, 0.0],
            payload={"version": 2},
            tenant_id="tenant-a",
            db=session,
        )
        session.commit()

    old_query = adapter.search_similarity(
        [1.0, 0.0, 0.0],
        tenant_id="tenant-a",
        score_threshold=0.99,
    )
    new_query = adapter.search_similarity(
        [0.0, 1.0, 0.0],
        tenant_id="tenant-a",
        score_threshold=0.99,
    )

    assert old_query == []
    assert len(new_query) == 1
    assert new_query[0].payload == {"version": 2}


def test_caller_owned_upsert_does_not_commit_outer_transaction(sqlite_vector_adapter):
    adapter, engine, factory = sqlite_vector_adapter
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE transaction_marker (id VARCHAR(32) PRIMARY KEY)"))

    session = factory()
    try:
        session.execute(
            text("INSERT INTO transaction_marker (id) VALUES ('pending-parent-write')")
        )
        assert adapter.upsert_embedding(
            "atomic-vector-id",
            [1.0, 0.0, 0.0],
            tenant_id="tenant-a",
            db=session,
        ) is True

        # A second connection must not see either write until the caller commits.
        with factory() as observer:
            marker_count = observer.execute(
                text("SELECT COUNT(*) FROM transaction_marker")
            ).scalar_one()
            vector_count = observer.execute(
                text("SELECT COUNT(*) FROM tenant_vector_test WHERE id = 'atomic-vector-id'")
            ).scalar_one()
        assert marker_count == 0
        assert vector_count == 0

        # The caller can still roll back the entire memory + vector unit of work.
        session.rollback()

        with factory() as observer:
            marker_count = observer.execute(
                text("SELECT COUNT(*) FROM transaction_marker")
            ).scalar_one()
            vector_count = observer.execute(
                text("SELECT COUNT(*) FROM tenant_vector_test WHERE id = 'atomic-vector-id'")
            ).scalar_one()
        assert marker_count == 0
        assert vector_count == 0
    finally:
        session.close()


def test_caller_owned_delete_does_not_commit_outer_transaction(sqlite_vector_adapter):
    adapter, engine, factory = sqlite_vector_adapter
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE transaction_marker (id VARCHAR(32) PRIMARY KEY)"))
    with factory() as session:
        assert adapter.upsert_embedding(
            "delete-atomic-id",
            [1.0, 0.0, 0.0],
            tenant_id="tenant-a",
            db=session,
        )
        session.commit()

    session = factory()
    try:
        session.execute(
            text("INSERT INTO transaction_marker (id) VALUES ('pending-delete-parent-write')")
        )
        assert adapter.delete_embedding(
            "delete-atomic-id",
            tenant_id="tenant-a",
            db=session,
        ) is True

        with factory() as observer:
            marker_count = observer.execute(
                text("SELECT COUNT(*) FROM transaction_marker")
            ).scalar_one()
            vector_count = observer.execute(
                text("SELECT COUNT(*) FROM tenant_vector_test WHERE id = 'delete-atomic-id'")
            ).scalar_one()
        assert marker_count == 0
        assert vector_count == 1
        session.rollback()

        with factory() as observer:
            vector_count = observer.execute(
                text("SELECT COUNT(*) FROM tenant_vector_test WHERE id = 'delete-atomic-id'")
            ).scalar_one()
        assert vector_count == 1
    finally:
        session.close()


def test_oracle_merge_matches_on_memory_id_and_tenant_without_reassigning_owner():
    adapter = OracleVectorAdapter(table_name="oracle_vector_test", dimension=3)
    adapter._schema_initialized = True
    adapter.is_oracle_backend = lambda: True  # type: ignore[method-assign]
    session = _RecordingSession()

    assert adapter.upsert_embedding(
        "memory-123",
        [1.0, 0.0, 0.0],
        payload={"classification": "private"},
        tenant_id="tenant-a",
        db=session,  # type: ignore[arg-type]
    ) is True

    sql, params = session.statements[0]
    normalized = " ".join(sql.split())
    assert "ON (dest.id = src.id AND dest.tenant_id = src.tenant_id)" in normalized
    update_clause = normalized.split("WHEN MATCHED THEN", 1)[1].split("WHEN NOT MATCHED", 1)[0]
    assert "dest.embedding = src.embedding" in update_clause
    assert "dest.payload = src.payload" in update_clause
    assert "dest.tenant_id =" not in update_clause
    assert params["tenant_id"] == "tenant-a"
    assert session.commit_count == 0
    assert session.rollback_count == 0
    assert session.savepoints[0].committed is True


def test_invalid_vector_dimensions_and_non_finite_values_fail_closed(sqlite_vector_adapter):
    adapter, _engine, factory = sqlite_vector_adapter
    with factory() as session:
        assert adapter.upsert_embedding(
            "wrong-dimension",
            [1.0, 0.0],
            tenant_id="tenant-a",
            db=session,
        ) is False
        assert adapter.upsert_embedding(
            "non-finite",
            [1.0, float("nan"), 0.0],
            tenant_id="tenant-a",
            db=session,
        ) is False
        assert adapter.search_similarity(
            [1.0, 0.0],
            tenant_id="tenant-a",
        ) == []
        session.rollback()


def test_readiness_is_false_until_schema_bootstrap(sqlite_vector_adapter):
    adapter, _engine, _factory = sqlite_vector_adapter
    # The fixture bootstraps before yielding; exercise a fresh adapter instance.
    fresh = OracleVectorAdapter(table_name="fresh_vector_test", dimension=3)
    fresh.is_oracle_backend = lambda: False  # type: ignore[method-assign]
    assert fresh.readiness()["available"] is False
    assert fresh.readiness()["status"] == "not_initialized"
    assert fresh.ensure_schema() is True
    assert fresh.readiness()["available"] is True
