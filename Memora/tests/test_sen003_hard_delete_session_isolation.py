"""TASK-SEN-003 regression tests — Memora hard delete must survive a
sub-store DatabaseError raised on the caller's shared session.

Production evidence (Server 1, Memora journal, 2026-11-15 14:47 IST):
``DELETE /v1/memories/<id>?hard=true`` returned 500 with
``sqlalchemy.exc.PendingRollbackError`` raised at the ``db.commit()`` in
``MemoryService.delete_memory`` (deployed service.py line 814). An earlier
sub-step — the Oracle vector delete, which by design runs on the caller's
session — raised an ``oracledb`` DatabaseError; the bare
``except Exception`` around it swallowed the Python error but left the
SQLAlchemy transaction poisoned, so the relational delete and the commit
failed and the memory was never deleted (7 failed DELETEs vs 75 succeeded
on 2026-11-15; affected records fail deterministically on every retry).

The tombstone design already intends degradation: a failed sub-store marks
its tombstone flag False and the tombstone stays PENDING_RETRY for the
convergence worker. These tests pin that contract: a DatabaseError inside
either sub-store step must degrade the tombstone, never poison the delete.
"""
from sqlalchemy import text

from storage.relational.models import MemoryRecord, DeletionTombstone
from core.memory.schemas import MemoryRecordCreate
from core.identity.service import IdentityService
from core.memory.service import MemoryService


def _make_memory(test_db, tenant="tenant_sen003"):
    agent = IdentityService.register_agent(test_db, "sen003_agent", tenant_id=tenant)
    ns = IdentityService.resolve_namespace(
        test_db, "memora://sen003_agent/private",
        owner_agent_id=agent.id, tenant_id=tenant,
    )
    mem = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text="SEN-003 hard-delete isolation probe.",
            owner_id=agent.id,
            namespace_id=ns.id,
            tenant_id=tenant,
        ),
        actor_name="sen003_agent",
    )
    return mem.id


def test_hard_delete_survives_vector_db_failure(test_db, monkeypatch):
    """Vector sub-store raises a DatabaseError ON the shared session."""
    mem_id = _make_memory(test_db)

    import importlib

    ova = importlib.import_module("storage.vector.oracle_vector_adapter")

    def poisoned_delete(memory_id, tenant_id=None, db=None):
        # Faithful repro of the production failure mode: the sub-store's
        # write fails DURING FLUSH on the caller's session (here: a
        # duplicate-PK insert). A flush-time DatabaseError is what marks
        # the session inactive in SQLAlchemy — every later statement (and
        # the commit) then raises PendingRollbackError, exactly as in the
        # production traceback. (A bare failed SELECT/execute does NOT
        # poison a session and would not reproduce it.)
        db.add(DeletionTombstone(id="sen003-vector-poison", memory_id="sen003-vector-poison"))
        db.flush()
        db.add(DeletionTombstone(id="sen003-vector-poison", memory_id="sen003-vector-poison"))
        db.flush()
        return True

    monkeypatch.setattr(ova.oracle_vector_adapter, "is_oracle_backend", lambda: True)
    monkeypatch.setattr(ova.oracle_vector_adapter, "delete_embedding", poisoned_delete)

    res = MemoryService.delete_memory(
        test_db, memory_id=mem_id, actor_name="sen003_agent",
        hard_delete=True, tenant_id="tenant_sen003",
    )

    assert res["status"] == "hard_deleted"
    # The record itself is gone — the delete was not rolled back by the
    # sub-store failure.
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first() is None
    # The tombstone honestly records the degraded convergence.
    tombstone = test_db.query(DeletionTombstone).filter(
        DeletionTombstone.memory_id == mem_id
    ).first()
    assert tombstone is not None
    assert tombstone.relational_deleted is True
    assert tombstone.vector_deleted is False
    assert res["deletion_converged"] is False
    assert res["tombstone_status"] == "PENDING_RETRY"


def test_hard_delete_survives_graph_db_failure(test_db, monkeypatch):
    """Graph sub-store fails during flush inside the cleanup step."""
    from sqlalchemy.orm import Query

    from storage.relational.models import MemoryRelationship

    mem_id = _make_memory(test_db)

    real_delete = Query.delete

    def sabotaged_delete(self, synchronize_session=None, **kwargs):
        entity = self.column_descriptions[0].get("entity")
        if entity is MemoryRelationship:
            # Fail during FLUSH inside the graph step, on the shared
            # session — the same poisoning mechanism as the vector test.
            self.session.add(
                DeletionTombstone(id="sen003-graph-poison", memory_id="sen003-graph-poison")
            )
            self.session.flush()
            self.session.add(
                DeletionTombstone(id="sen003-graph-poison", memory_id="sen003-graph-poison")
            )
            self.session.flush()
        return real_delete(self, synchronize_session=synchronize_session, **kwargs)

    monkeypatch.setattr(Query, "delete", sabotaged_delete)

    res = MemoryService.delete_memory(
        test_db, memory_id=mem_id, actor_name="sen003_agent",
        hard_delete=True, tenant_id="tenant_sen003",
    )

    assert res["status"] == "hard_deleted"
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == mem_id).first() is None
    tombstone = test_db.query(DeletionTombstone).filter(
        DeletionTombstone.memory_id == mem_id
    ).first()
    assert tombstone is not None
    assert tombstone.relational_deleted is True
    assert tombstone.graph_deleted is False
    assert res["tombstone_status"] == "PENDING_RETRY"
