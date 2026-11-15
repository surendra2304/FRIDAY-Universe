"""
TASK-MEM-006 — Retention & forgetting policy tests.

Everything here runs against the staging store provided by the suite's
``test_db`` fixture (in-memory SQLite). No production data is touched.

The headline test is the erasure proof: a memory is planted in every store
it can live in (relational row, vector embedding, graph edge, cache
entry), forgotten, and then every store is inspected directly — the
memory must be verifiably gone from all of them.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.cache.memory_cache import memory_cache
from core.identity.service import IdentityService
from core.memory.retention import (
    RetentionClass,
    RetentionSweeper,
    classify_retention,
    resolve_create_expires_at,
    retention_expires_at,
    retention_ttl,
)
from core.memory.schemas import MemoryQuery, MemoryRecordCreate
from core.memory.service import (
    MemoryNotFoundError,
    MemoryService,
    PermissionDeniedError,
)
from storage.relational.models import (
    DeletionTombstone,
    LifecycleState,
    MemoryRecord,
    MemoryRelationship,
    MemoryType,
)
from storage.vector.qdrant_adapter import vector_adapter

NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)


def _agent_and_ns(test_db):
    agent = IdentityService.register_agent(test_db, "friday", role="supervisor")
    ns = IdentityService.resolve_namespace(
        test_db, "memora://friday/private", owner_agent_id=agent.id
    )
    return agent, ns


def _plant_record(test_db, agent, ns, memory_id, memory_type, content, **kwargs):
    record = MemoryRecord(
        id=memory_id,
        namespace_id=ns.id,
        owner_id=agent.id,
        memory_type=memory_type,
        content_text=content,
        lifecycle_state=kwargs.pop("lifecycle_state", LifecycleState.ACTIVE),
        **kwargs,
    )
    test_db.add(record)
    test_db.commit()
    return record


def _plant_everywhere(test_db, agent, ns, memory_id, content="Secret fact ZQXW to forget."):
    """Plant one memory in all four stores; return (record, other_record)."""
    record = _plant_record(
        test_db, agent, ns, memory_id, MemoryType.EPISODIC, content
    )
    other = _plant_record(
        test_db, agent, ns, f"{memory_id}-other", MemoryType.EPISODIC,
        "Unrelated memory that must survive.",
    )
    test_db.add(
        MemoryRelationship(
            source_memory_id=memory_id,
            target_memory_id=other.id,
            relationship_type="relates_to",
        )
    )
    test_db.commit()
    vector_adapter.upsert_embedding(memory_id, [0.1, 0.2, 0.3], tenant_id="default")
    memory_cache.set("default", memory_id, {"content_text": content})
    return record, other


# =============================================================================
# 1. RETENTION CLASSIFICATION
# =============================================================================

def test_classification_defaults():
    assert classify_retention(MemoryType.WORKING) is RetentionClass.TRANSIENT
    assert classify_retention(MemoryType.TOOL) is RetentionClass.TRANSIENT
    assert classify_retention(MemoryType.EPISODIC) is RetentionClass.SHORT_TERM
    assert classify_retention(MemoryType.EXPERIENCE) is RetentionClass.SHORT_TERM
    for durable in (
        MemoryType.SEMANTIC, MemoryType.PREFERENCE, MemoryType.PROCEDURAL,
        MemoryType.DECISION, MemoryType.RELATIONSHIP, MemoryType.PROJECT,
        MemoryType.SYSTEM,
    ):
        assert classify_retention(durable) is RetentionClass.DURABLE
        assert retention_ttl(durable) is None
        assert retention_expires_at(durable, now=NOW) is None

    assert retention_ttl(MemoryType.WORKING) == timedelta(days=30)
    assert retention_ttl(MemoryType.TOOL) == timedelta(days=7)
    assert retention_ttl(MemoryType.EPISODIC) == timedelta(days=90)
    assert retention_expires_at(MemoryType.WORKING, now=NOW) == NOW + timedelta(days=30)


def test_classification_overrides():
    # Provenance class hint beats the type default.
    assert classify_retention(
        MemoryType.WORKING, {"retention_class": "durable"}
    ) is RetentionClass.DURABLE
    assert retention_ttl(MemoryType.WORKING, {"retention_class": "durable"}) is None

    # An explicit TTL hint makes even a durable-class record expire.
    assert retention_ttl(
        MemoryType.PREFERENCE, {"retention_ttl_hours": 2}
    ) == timedelta(hours=2)

    # TTL hints are clamped to [1h, 1y].
    assert retention_ttl(
        MemoryType.EPISODIC, {"retention_ttl_hours": 0}
    ) == timedelta(hours=1)
    assert retention_ttl(
        MemoryType.EPISODIC, {"retention_ttl_hours": 10 ** 9}
    ) == timedelta(hours=24 * 365)

    # An unrecognised class hint is ignored, never silently applied.
    assert classify_retention(
        MemoryType.WORKING, {"retention_class": "forever-ish"}
    ) is RetentionClass.TRANSIENT

    # An explicit caller expiry always wins over the policy.
    explicit = NOW + timedelta(minutes=5)
    assert resolve_create_expires_at(
        MemoryType.PREFERENCE, explicit, None, now=NOW
    ) == explicit
    assert resolve_create_expires_at(
        MemoryType.WORKING, None, None, now=NOW
    ) == NOW + timedelta(days=30)
    assert resolve_create_expires_at(MemoryType.PREFERENCE, None, None, now=NOW) is None


def test_env_ttl_override(monkeypatch):
    monkeypatch.setenv("MEMORA_RETENTION_TTL_HOURS_WORKING", "48")
    assert retention_ttl(MemoryType.WORKING) == timedelta(hours=48)
    monkeypatch.setenv("MEMORA_RETENTION_TTL_HOURS_WORKING", "not-a-number")
    assert retention_ttl(MemoryType.WORKING) == timedelta(days=30)


# =============================================================================
# 2. WRITE PATH ASSIGNS POLICY EXPIRY
# =============================================================================

def test_create_assigns_policy_expiry(test_db):
    IdentityService.register_agent(test_db, "friday", role="supervisor")
    before = datetime.now(timezone.utc)

    working = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text="Scratch context for the current task.",
            memory_type=MemoryType.WORKING,
            source="test",
        ),
        actor_name="friday",
    )
    assert working.expires_at is not None
    # SQLite round-trips may drop tzinfo; compare on a naive-UTC basis.
    exp = working.expires_at
    exp = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp
    assert before + timedelta(days=29) < exp <= before + timedelta(days=30, minutes=5)

    durable = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text="The owner prefers concise answers.",
            memory_type=MemoryType.PREFERENCE,
            source="test",
        ),
        actor_name="friday",
    )
    assert durable.expires_at is None

    explicit = datetime.now(timezone.utc) + timedelta(hours=3)
    episodic = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text="An episode with a caller-chosen expiry.",
            memory_type=MemoryType.EPISODIC,
            source="test",
            expires_at=explicit,
        ),
        actor_name="friday",
    )
    exp2 = episodic.expires_at
    exp2 = exp2.replace(tzinfo=timezone.utc) if exp2.tzinfo is None else exp2
    assert abs((exp2 - explicit).total_seconds()) < 2


# =============================================================================
# 3. PLANT -> FORGET -> VERIFY GONE (the erasure proof)
# =============================================================================

def test_plant_forget_verify_gone(test_db):
    agent, ns = _agent_and_ns(test_db)
    record, other = _plant_everywhere(test_db, agent, ns, "mem-forget-001")

    # Sanity: the memory really is present in every store before forgetting.
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == record.id).first() is not None
    assert record.id in vector_adapter._mock_store
    assert memory_cache.get("default", record.id) is not None
    assert test_db.query(MemoryRelationship).filter(
        MemoryRelationship.source_memory_id == record.id
    ).count() == 1
    assert MemoryService.verify_erasure(test_db, record.id)["erased"] is False

    res = MemoryService.forget_memory(test_db, memory_id=record.id, actor_name="friday")

    assert res["status"] == "hard_deleted"
    assert res["deletion_converged"] is True
    assert res["erasure_verified"] is True
    assert res["verification"]["stores"] == {
        "relational": True, "vector": True, "graph": True, "cache": True,
    }

    # Direct store inspection — not just the service's own report.
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == record.id).first() is None
    assert record.id not in vector_adapter._mock_store
    assert memory_cache.get("default", record.id) is None
    assert test_db.query(MemoryRelationship).filter(
        MemoryRelationship.source_memory_id == record.id
    ).count() == 0
    assert test_db.query(MemoryRelationship).filter(
        MemoryRelationship.target_memory_id == record.id
    ).count() == 0

    # The tombstone is the only trace left, and it converged honestly.
    tombstone = test_db.query(DeletionTombstone).filter(
        DeletionTombstone.memory_id == record.id
    ).first()
    assert tombstone is not None
    assert tombstone.status == "CONVERGED"
    assert tombstone.relational_deleted is True
    assert tombstone.vector_deleted is True
    assert tombstone.graph_deleted is True
    assert tombstone.cache_deleted is True

    # The unrelated memory is untouched, and recall no longer finds the fact.
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == other.id).first() is not None
    hits = MemoryService.query_memories(
        test_db, MemoryQuery(query_text="ZQXW"), actor_name="friday"
    )
    assert all(h.id != record.id for h in hits)


def test_forget_is_owner_only(test_db):
    agent, ns = _agent_and_ns(test_db)
    IdentityService.register_agent(test_db, "forge", role="agent")
    record, _ = _plant_everywhere(test_db, agent, ns, "mem-forget-002")

    with pytest.raises((PermissionDeniedError, MemoryNotFoundError)):
        MemoryService.forget_memory(test_db, memory_id=record.id, actor_name="forge")

    # Nothing was erased by the rejected attempt.
    assert test_db.query(MemoryRecord).filter(MemoryRecord.id == record.id).first() is not None
    assert record.id in vector_adapter._mock_store


def test_forget_endpoint_api(test_db, client):
    IdentityService.register_agent(test_db, "friday", role="supervisor")
    create = client.post(
        "/v1/memories",
        json={
            "content_text": "API-planted working note QZAPI.",
            "memory_type": "working",
            "source": "test",
        },
        headers={"X-Agent-Name": "friday"},
    )
    assert create.status_code == 201
    memory_id = create.json()["id"]

    res = client.post(
        f"/v1/memories/{memory_id}/forget", headers={"X-Agent-Name": "friday"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "hard_deleted"
    assert body["erasure_verified"] is True

    gone = client.get(
        f"/v1/memories/{memory_id}", headers={"X-Agent-Name": "friday"}
    )
    assert gone.status_code == 404


# =============================================================================
# 4. EXPIRY SWEEP ERASES ONLY WHAT LAPSED
# =============================================================================

def test_expiry_sweep_erases_only_lapsed(test_db):
    agent, ns = _agent_and_ns(test_db)
    past = NOW - timedelta(hours=1)
    future = NOW + timedelta(days=30)

    lapsed, survivor = _plant_everywhere(test_db, agent, ns, "mem-sweep-lapsed")
    test_db.query(MemoryRecord).filter(MemoryRecord.id == lapsed.id).update(
        {"expires_at": past}
    )
    soft_deleted = _plant_record(
        test_db, agent, ns, "mem-sweep-softdeleted", MemoryType.EPISODIC,
        "Soft-deleted content whose retention also lapsed.",
        lifecycle_state=LifecycleState.DELETED, expires_at=past,
    )
    durable = _plant_record(
        test_db, agent, ns, "mem-sweep-durable", MemoryType.PREFERENCE,
        "A durable fact with no expiry.", expires_at=None,
    )
    unexpired = _plant_record(
        test_db, agent, ns, "mem-sweep-unexpired", MemoryType.EPISODIC,
        "An episode still inside its retention.", expires_at=future,
    )
    test_db.commit()

    result = RetentionSweeper.run_expiry_sweep(test_db, now=NOW)

    assert result["status"] == "completed"
    assert result["expired_found"] == 2
    assert result["erased"] == 2
    assert result["errors"] == []
    assert set(result["erased_ids"]) == {lapsed.id, soft_deleted.id}

    # Lapsed records are gone from every store, not just hidden.
    for gone_id in (lapsed.id, soft_deleted.id):
        assert test_db.query(MemoryRecord).filter(
            MemoryRecord.id == gone_id
        ).first() is None
        tombstone = test_db.query(DeletionTombstone).filter(
            DeletionTombstone.memory_id == gone_id
        ).first()
        assert tombstone is not None and tombstone.status == "CONVERGED"
    assert lapsed.id not in vector_adapter._mock_store
    assert memory_cache.get("default", lapsed.id) is None
    assert test_db.query(MemoryRelationship).filter(
        MemoryRelationship.source_memory_id == lapsed.id
    ).count() == 0

    # Durable and unexpired records persist.
    for kept in (durable, unexpired, survivor):
        assert test_db.query(MemoryRecord).filter(
            MemoryRecord.id == kept.id
        ).first() is not None

    # The sweep is idempotent.
    again = RetentionSweeper.run_expiry_sweep(test_db, now=NOW)
    assert again["expired_found"] == 0
    assert again["erased"] == 0
