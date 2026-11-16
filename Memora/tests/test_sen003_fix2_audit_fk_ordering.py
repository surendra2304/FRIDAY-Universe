"""TASK-SEN-003 fix-2 regression tests — the MEMORY_HARD_DELETED audit row
must not FK-fail against the very memory it attests to deleting.

Production evidence (post-deploy verification of PR #633, Server 1,
2026-11-16 06:48-06:49 IST): hard DELETE still returned HTTP 500 for all
9 attempted records (8 REL047-239d7477- probes + 1 fresh throwaway) with
``sqlalchemy.exc.PendingRollbackError`` whose original exception was
``oracledb.exceptions.IntegrityError ORA-02291: integrity constraint
(MEMORA.SYS_C0038779) violated - parent key not found``.

Root cause: ``MemoryService.delete_memory`` ran the physical erase first
(``_hard_erase_record`` deletes the memory row inside the transaction)
and only then wrote the policy audit row via
``PolicyEngine.log_audit_decision``. ``audit_logs.memory_id`` is an FK to
``memory_records.id`` (founding migration 8a8f529e1cdb, ondelete SET
NULL; the unnamed constraint is Oracle's SYS_C0038779), so the audit
INSERT references a parent that no longer exists inside the transaction.
``log_audit_decision`` swallows the flush error, but the session is left
poisoned and the caller's ``db.commit()`` raises PendingRollbackError —
the hard delete 500s and the record is never erased.

Why PR #633's tests could not see this: the shared ``test_db`` fixture
runs SQLite WITHOUT ``PRAGMA foreign_keys=ON``, so FK violations are
invisible in the harness, and the #633 tests modelled sub-store flush
failures, not FK ordering. These tests therefore run the real models and
real services on SQLite with FK enforcement ON, where the audit insert
after the physical delete fails with the SQLite equivalent
(``IntegrityError: FOREIGN KEY constraint failed`` at the audit flush,
surfacing as ``PendingRollbackError`` at commit — the production
signature). They FAIL on pre-fix main and PASS on the fix-2 branch.

The fix writes the audit row BEFORE the erase, inside the same
transaction: the insert finds its parent, the erase commits atomically
with the audit row (a failed erase rolls the audit row back too — the
audit never claims a deletion that did not happen), and ON DELETE SET
NULL clears the row's memory_id column as the schema intends, so the
erased id is also preserved in the audit row's ``details``.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from storage.relational.base import Base
from storage.relational.models import AuditLog, LifecycleState, MemoryRecord
from core.memory.schemas import MemoryRecordCreate
from core.identity.service import IdentityService
from core.memory.service import MemoryService

TENANT = "tenant_sen003fix2"
AGENT = "sen003fix2_agent"


@pytest.fixture()
def fk_db():
    """Real models + real services on SQLite with FK enforcement ON.

    Mirrors conftest's test_db construction, plus the one line production
    Oracle has always had: foreign keys are actually enforced.
    """
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


def _make_memory(db, tenant=TENANT):
    agent = IdentityService.register_agent(db, AGENT, tenant_id=tenant)
    ns = IdentityService.resolve_namespace(
        db, f"memora://{AGENT}/private",
        owner_agent_id=agent.id, tenant_id=tenant,
    )
    mem = MemoryService.create_memory(
        db,
        MemoryRecordCreate(
            content_text="SEN-003 fix-2 audit-FK probe.",
            owner_id=agent.id,
            namespace_id=ns.id,
            tenant_id=tenant,
        ),
        actor_name=AGENT,
    )
    return mem.id, agent.id


def _hard_deleted_audit_rows(db):
    return [
        row for row in db.query(AuditLog).all()
        if (row.details or {}).get("rule_matched") == "MEMORY_HARD_DELETED"
    ]


def test_hard_delete_commits_and_keeps_audit_row_under_fk_enforcement(fk_db):
    """The production failure: audit insert ordered after the erase.

    On pre-fix code this raises PendingRollbackError at the commit inside
    delete_memory (the audit flush's FOREIGN KEY failure, swallowed by
    log_audit_decision, poisons the session) and the record survives.
    """
    mem_id, agent_id = _make_memory(fk_db)

    res = MemoryService.delete_memory(
        fk_db, memory_id=mem_id, actor_name=AGENT,
        hard_delete=True, tenant_id=TENANT,
    )

    assert res["status"] == "hard_deleted"
    # The record is physically gone.
    assert fk_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first() is None
    # The audit row was written and NOT lost: exactly one MEMORY_HARD_DELETED
    # row, still naming the erased memory (in details — the memory_id FK
    # column is nulled by ON DELETE SET NULL when the erase lands, which
    # the second assertion pins as the schema's designed behaviour).
    rows = _hard_deleted_audit_rows(fk_db)
    assert len(rows) == 1
    assert rows[0].action == "policy_approved"
    assert rows[0].actor_id == agent_id
    assert rows[0].tenant_id == TENANT
    assert (rows[0].details or {}).get("memory_id") == mem_id
    assert rows[0].memory_id is None


def test_forget_memory_erases_and_keeps_audit_row_under_fk_enforcement(fk_db):
    """forget_memory shares the hard path via delete_memory(hard_delete=True),
    so the same FK ordering hazard — and the same fix — applies to it."""
    mem_id, _agent_id = _make_memory(fk_db)

    res = MemoryService.forget_memory(
        fk_db, memory_id=mem_id, actor_name=AGENT, tenant_id=TENANT,
    )

    assert res["memory_id"] == mem_id
    assert fk_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first() is None
    rows = _hard_deleted_audit_rows(fk_db)
    assert len(rows) == 1
    assert (rows[0].details or {}).get("memory_id") == mem_id


def test_retention_sweep_erases_expired_record_under_fk_enforcement(fk_db):
    """The third _hard_erase_record path: the sweep writes no audit rows,
    so it has no FK hazard — pin that it stays healthy under enforcement."""
    from core.memory.retention import RetentionSweeper

    mem_id, _agent_id = _make_memory(fk_db)
    record = fk_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first()
    record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    fk_db.commit()

    result = RetentionSweeper.run_expiry_sweep(fk_db, tenant_id=TENANT)

    assert result["errors"] == []
    assert mem_id in result["erased_ids"]
    assert fk_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first() is None


def test_soft_delete_unchanged_under_fk_enforcement(fk_db):
    """Guard: soft delete never had the hazard and must not change — the
    record stays, and its audit row keeps the memory_id FK value."""
    mem_id, _agent_id = _make_memory(fk_db)

    res = MemoryService.delete_memory(
        fk_db, memory_id=mem_id, actor_name=AGENT,
        hard_delete=False, tenant_id=TENANT,
    )

    assert res["status"] == "soft_deleted"
    record = fk_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first()
    assert record is not None
    assert record.lifecycle_state == LifecycleState.DELETED
    soft_rows = [
        row for row in fk_db.query(AuditLog).all()
        if (row.details or {}).get("rule_matched") == "MEMORY_SOFT_DELETED"
    ]
    assert len(soft_rows) == 1
    assert soft_rows[0].memory_id == mem_id
