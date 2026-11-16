"""TASK-SEN-003 fix-3 regression tests — a hard erase must not delete the
record's graph rows itself before deleting the record.

Production evidence (Server 1, 2026-11-16, after fix-2 / PR #654 removed
the ORA-02291 audit-ordering layer): hard DELETE still returned HTTP 500
for every REL047-239d7477- record that participates in
``memory_relationships``, now with ``oracledb.exceptions.DatabaseError
ORA-12860: deadlock detected while waiting for a sibling row lock`` at
the physical ``DELETE FROM memory_records`` (service.py
``_hard_erase_record``, the final flush).

Phase-1 diagnosis (live, controlled, both directions reproduced):
* b2e85620 (7 outgoing edges) retried in a quiet window -> ORA-12860 again.
* A fresh record with ZERO relationships erased 200/converged on the same
  deployed code; so did REL047 record 9512cb2e (0 relationships).
* Two fresh records + ONE relationship: hard DELETE of the source AND of
  the target each failed with ORA-12860.
* A record with a superseded child (the schema's only unindexed FK,
  ``memory_records.superseded_by_id``, ON DELETE SET NULL) but zero
  relationships erased 200 — the unindexed self-FK is not the trigger.
* Local statement capture (real models + real MemoryService) shows the
  emitted SQL is identical with and without relationships; the only
  difference in the failing case is that the erase transaction itself
  deletes the relationship rows first (the bulk DELETE inside the
  SAVEPOINT in ``_hard_erase_record``) and therefore holds
  memory_relationships row locks when the parent DELETE's FK maintenance
  re-engages that table.

The fix removes the pre-emptive graph delete and the ORM delete: the
parent row is removed with a Core DELETE so neither the service nor the
ORM unit-of-work touches memory_relationships (or the other
delete-orphan collections) ahead of the parent statement; the schema's
ON DELETE CASCADE removes the child rows inside the parent DELETE
itself on an enforcing backend, a post-delete cleanup pass mirrors the
schema's FK actions for non-enforcing backends (its locks can never
deadlock a parent statement that has already run), and
``graph_deleted`` is set from an in-transaction count after the delete.
SQLite cannot reproduce Oracle's lock manager, so these tests pin (a)
the structural invariant production indicted — NO delete against
memory_relationships may be issued BEFORE the parent DELETE — which
FAILS on pre-fix main, and (b) full erasure of a relationship-carrying
record under FK enforcement (children gone, partner record untouched,
tombstone converged, fix-2's audit invariants intact).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from storage.relational.base import Base
from storage.relational.models import (
    AuditLog,
    DeletionTombstone,
    MemoryRecord,
    MemoryRelationship,
    MemorySharedAgent,
)
from core.memory.schemas import MemoryRecordCreate
from core.identity.service import IdentityService
from core.memory.service import MemoryService

TENANT = "tenant_sen003fix3"
AGENT = "sen003fix3_agent"


@pytest.fixture()
def fk_db():
    """Real models + real services on SQLite with FK enforcement ON
    (the fix-2 harness pattern: production Oracle always enforces FKs,
    the shared test_db fixture does not)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_memory(db, content):
    agent = IdentityService.register_agent(db, AGENT, tenant_id=TENANT)
    ns = IdentityService.resolve_namespace(
        db, f"memora://{AGENT}/private",
        owner_agent_id=agent.id, tenant_id=TENANT,
    )
    mem = MemoryService.create_memory(
        db,
        MemoryRecordCreate(
            content_text=content,
            owner_id=agent.id,
            namespace_id=ns.id,
            tenant_id=TENANT,
        ),
        actor_name=AGENT,
    )
    return mem.id


def _linked_pair(db):
    """Two records + one relationship row src -> tgt (direct ORM insert,
    the same single row GraphService.create_relationship commits)."""
    src = _make_memory(db, "SEN-003 fix-3 source record.")
    tgt = _make_memory(db, "SEN-003 fix-3 target record.")
    db.add(MemoryRelationship(
        source_memory_id=src, target_memory_id=tgt,
        relationship_type="shares_entity", weight=1.0,
    ))
    db.flush()
    return src, tgt


def _edges_touching(db, memory_id):
    return db.query(MemoryRelationship).filter(
        (MemoryRelationship.source_memory_id == memory_id)
        | (MemoryRelationship.target_memory_id == memory_id)
    ).count()


def _record(db, memory_id):
    return db.query(MemoryRecord).filter(MemoryRecord.id == memory_id).first()


def _tombstone(db, memory_id):
    return (
        db.query(DeletionTombstone)
        .filter(DeletionTombstone.memory_id == memory_id)
        .order_by(DeletionTombstone.created_at.desc())
        .first()
    )


def _hard_deleted_audit_rows(db):
    return [
        row for row in db.query(AuditLog).all()
        if (row.details or {}).get("rule_matched") == "MEMORY_HARD_DELETED"
    ]


def test_erase_issues_no_graph_delete_before_parent_delete(fk_db):
    """The structural invariant production indicted.

    On pre-fix code the erase emits ``DELETE FROM memory_relationships``
    (the bulk graph pre-delete) ahead of ``DELETE FROM memory_records`` —
    the in-transaction child-row deletion whose held locks deadlock the
    parent DELETE on Oracle. This test FAILS on pre-fix main for exactly
    that reason. On the fix-3 branch no statement may delete graph rows
    before the parent DELETE has run (the FK cascade inside the parent
    DELETE removes them on an enforcing backend; the post-delete cleanup
    pass may only run afterwards), while the rows still end up gone.
    """
    src, _tgt = _linked_pair(fk_db)
    fk_db.commit()

    engine = fk_db.get_bind()
    statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()).upper())

    try:
        res = MemoryService.delete_memory(
            fk_db, memory_id=src, actor_name=AGENT,
            hard_delete=True, tenant_id=TENANT,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert res["status"] == "hard_deleted"
    parent_idx = next(
        i for i, s in enumerate(statements)
        if s.startswith("DELETE FROM MEMORY_RECORDS")
    )
    early_graph_deletes = [
        s for i, s in enumerate(statements)
        if s.startswith("DELETE FROM MEMORY_RELATIONSHIPS") and i < parent_idx
    ]
    assert early_graph_deletes == [], (
        "no graph-row delete may precede the parent delete; the "
        "in-transaction pre-delete is the ORA-12860 trigger. "
        f"captured before parent delete: {early_graph_deletes}"
    )
    # ...and the edge still ends up gone (cascade and/or post-cleanup).
    assert _edges_touching(fk_db, src) == 0


def test_hard_delete_source_erases_children_keeps_partner(fk_db):
    """End-to-end under FK enforcement: source record with an outgoing
    edge and a shared-agent row erases fully; the partner record and the
    fix-2 audit invariants survive intact."""
    src, tgt = _linked_pair(fk_db)
    fk_db.add(MemorySharedAgent(
        tenant_id=TENANT, memory_id=src, agent_name="some_reader",
        granted_by=AGENT,
    ))
    fk_db.commit()

    res = MemoryService.delete_memory(
        fk_db, memory_id=src, actor_name=AGENT,
        hard_delete=True, tenant_id=TENANT,
    )

    assert res["status"] == "hard_deleted"
    assert _record(fk_db, src) is None
    assert _edges_touching(fk_db, src) == 0
    assert fk_db.query(MemorySharedAgent).filter(
        MemorySharedAgent.memory_id == src
    ).count() == 0
    # The partner record is untouched.
    assert _record(fk_db, tgt) is not None
    # Tombstone converged on measured flags, graph included.
    stone = _tombstone(fk_db, src)
    assert stone is not None
    assert stone.relational_deleted is True
    assert stone.graph_deleted is True
    assert stone.status == "CONVERGED"
    assert res["deletion_converged"] is True
    # Fix-2 invariants still hold: one audit row, id preserved in
    # details, memory_id column nulled by ON DELETE SET NULL.
    rows = _hard_deleted_audit_rows(fk_db)
    assert len(rows) == 1
    assert (rows[0].details or {}).get("memory_id") == src
    assert rows[0].memory_id is None


def test_hard_delete_target_erases_children_keeps_partner(fk_db):
    """The incoming direction deadlocked identically in production
    (target-only record, 0 outgoing / 1 incoming edge)."""
    src, tgt = _linked_pair(fk_db)
    fk_db.commit()

    res = MemoryService.delete_memory(
        fk_db, memory_id=tgt, actor_name=AGENT,
        hard_delete=True, tenant_id=TENANT,
    )

    assert res["status"] == "hard_deleted"
    assert _record(fk_db, tgt) is None
    assert _edges_touching(fk_db, tgt) == 0
    assert _record(fk_db, src) is not None
    stone = _tombstone(fk_db, tgt)
    assert stone is not None and stone.graph_deleted is True


def test_forget_memory_with_relationships_erases(fk_db):
    """forget_memory delegates to the same hard path."""
    src, _tgt = _linked_pair(fk_db)
    fk_db.commit()

    res = MemoryService.forget_memory(
        fk_db, memory_id=src, actor_name=AGENT, tenant_id=TENANT,
    )

    assert res["memory_id"] == src
    assert _record(fk_db, src) is None
    assert _edges_touching(fk_db, src) == 0


def test_retention_sweep_erases_record_with_relationships(fk_db):
    """The sweep calls _hard_erase_record directly (no audit rows); the
    cascade path must converge there too."""
    from core.memory.retention import RetentionSweeper

    src, _tgt = _linked_pair(fk_db)
    record = _record(fk_db, src)
    record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    fk_db.commit()

    result = RetentionSweeper.run_expiry_sweep(fk_db, tenant_id=TENANT)

    assert result["errors"] == []
    assert src in result["erased_ids"]
    assert _record(fk_db, src) is None
    assert _edges_touching(fk_db, src) == 0
