"""TASK-MEM-015 — promotion undo: one-call revert of the latest promotion.

Every promotion (owner path A and auto path C) writes a MEMORY_SCOPE_PROMOTED
audit row carrying from_scope/to_scope/shared_with; revert_scope reads that
row, demotes exactly one rung, removes only the allow-list rows that
promotion granted, and writes a MEMORY_SCOPE_DEMOTED row pointing at the
promotion it undoes. These tests pin that behaviour and its refusals.
"""
import pytest

from core.identity.service import IdentityService
from core.memory.promotion import (
    ACTION_DEMOTED,
    ACTION_PROMOTED,
    MemoryPromotionService,
    PromotionError,
    PromotionPermissionError,
)
from storage.relational.access_scope import record_is_visible, shared_membership
from storage.relational.models import (
    AuditLog,
    LifecycleState,
    MemoryRecord,
    MemoryScopeType,
    MemoryType,
    NamespaceType,
)

AGENTS = ("stratex", "forge", "sentinel", "intelx", "futuris", "cortex", "memora")


@pytest.fixture
def mesh(test_db):
    agents = {name: IdentityService.register_agent(test_db, name) for name in AGENTS}
    owner = agents["stratex"]
    namespace = IdentityService.resolve_namespace(
        test_db,
        "memora://stratex/private",
        owner_agent_id=owner.id,
        default_type=NamespaceType.AGENT_PRIVATE,
        tenant_id="default",
    )
    test_db.commit()
    return test_db, agents, namespace


def _private_memory(test_db, namespace, owner, text="sleeve shock stop is 2x weekly ATR", **kw):
    record = MemoryRecord(
        tenant_id="default",
        namespace_id=namespace.id,
        owner_id=owner.id,
        owner_agent=owner.name,
        scope=MemoryScopeType.PRIVATE,
        memory_type=kw.pop("memory_type", MemoryType.EPISODIC),
        content_text=text,
        lifecycle_state=LifecycleState.ACTIVE,
        provenance=kw.pop("provenance", {}),
        **kw,
    )
    test_db.add(record)
    test_db.commit()
    test_db.refresh(record)
    return record


def _needs(test_db, record, plan):
    """plan: {agent_name: count} of recorded needs."""
    for name, count in plan.items():
        for i in range(count):
            MemoryPromotionService.record_need(
                test_db, requester_name=name, memory_id=record.id, reason=f"need {i}"
            )


def _audits(test_db, record, action):
    return (
        test_db.query(AuditLog)
        .filter(AuditLog.memory_id == record.id, AuditLog.action == action)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )


# --------------------------------------------------------------------- revert
def test_owner_reverts_shared_to_private_restores_visibility(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge", "sentinel"],
    )
    db.refresh(record)
    assert record_is_visible(record, "forge") is True

    result = MemoryPromotionService.revert_scope(
        db, actor_name="stratex", memory_id=record.id, reason="shared too early",
    )
    assert result["status"] == "reverted"
    assert result["scope"] == "PRIVATE"
    assert result["from_scope"] == "SHARED"
    assert result["to_scope"] == "PRIVATE"

    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE
    assert shared_membership(db, record.id) == []
    assert record_is_visible(record, "forge") is False
    assert record_is_visible(record, "stratex") is True

    demotions = _audits(db, record, ACTION_DEMOTED)
    assert len(demotions) == 1
    assert demotions[0].details["reverts_audit_id"] == _audits(db, record, ACTION_PROMOTED)[0].id
    assert demotions[0].details["reverted_by"] == "stratex"
    assert demotions[0].details["shared_with_revoked"] == ["forge", "sentinel"]


def test_owner_reverts_universal_to_shared_keeps_earlier_allow_list(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id, target_scope="UNIVERSAL",
    )
    result = MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    assert result["status"] == "reverted"
    assert result["scope"] == "SHARED"
    assert result["from_scope"] == "UNIVERSAL"
    assert result["to_scope"] == "SHARED"

    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED
    # The earlier SHARED promotion's allow-list was never revoked by the
    # UNIVERSAL promotion, so it is intact again after the revert.
    assert shared_membership(db, record.id) == ["forge"]
    assert record_is_visible(record, "forge") is True
    assert record_is_visible(record, "intelx") is False


def test_owner_reverts_auto_promotion(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    _needs(db, record, {"forge": 2, "sentinel": 2})
    assert len(MemoryPromotionService.run_auto_promotion_sweep(db)) == 1
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED

    result = MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    assert result["status"] == "reverted"
    assert result["scope"] == "PRIVATE"
    assert result["path"] == "auto_repeated_need"
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE
    assert shared_membership(db, record.id) == []


def test_non_owner_cannot_revert(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.revert_scope(db, actor_name="forge", memory_id=record.id)
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED
    assert _audits(db, record, ACTION_DEMOTED) == []


def test_service_identity_can_revert(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    result = MemoryPromotionService.revert_scope(db, actor_name="memora", memory_id=record.id)
    assert result["status"] == "reverted"
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE


def test_double_revert_is_idempotent_noop(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    first = MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    assert first["status"] == "reverted"
    again = MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    assert again["status"] == "already_reverted"
    assert again["reverts_audit_id"] == first["reverts_audit_id"]
    assert len(_audits(db, record, ACTION_DEMOTED)) == 1  # no second demotion row
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE


def test_revert_with_no_promotion_is_not_found(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    with pytest.raises(PromotionError):
        MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)


def test_revert_refused_when_scope_moved_on(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    # Out-of-band scope change after the promotion: the revert would have to
    # skip a rung, so it refuses instead of demoting blindly.
    record.scope = MemoryScopeType.UNIVERSAL
    db.commit()
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    db.refresh(record)
    assert record.scope == MemoryScopeType.UNIVERSAL
    assert _audits(db, record, ACTION_DEMOTED) == []


def test_dual_copy_promotion_revert_refused(mesh):
    db, agents, ns = mesh
    record = _private_memory(
        db, ns, agents["stratex"],
        text="sleeve shock with 3% stop failed: PF 0.92 over 400 trades",
        provenance={"failed_experiment": True, "experiment_outcome": "failed"},
    )
    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id, target_scope="UNIVERSAL",
    )
    assert result["status"] == "promoted_dual_copy"
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.revert_scope(db, actor_name="stratex", memory_id=record.id)
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE  # original never moved
    copy = db.query(MemoryRecord).filter(MemoryRecord.id == result["universal_copy_id"]).first()
    assert copy.scope == MemoryScopeType.UNIVERSAL
    assert _audits(db, record, ACTION_DEMOTED) == []


# --------------------------------------------------------------------- API
def test_revert_api_owner_flow_and_gates(client, test_db, mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])

    promoted = client.post(
        "/v1/promotion/promote",
        headers={"X-Agent-Name": "stratex"},
        json={"memory_id": record.id, "target_scope": "SHARED", "shared_with": ["forge"]},
    )
    assert promoted.status_code == 200, promoted.text

    forbidden = client.post(
        "/v1/promotion/revert",
        headers={"X-Agent-Name": "forge"},
        json={"memory_id": record.id},
    )
    assert forbidden.status_code == 403, forbidden.text

    reverted = client.post(
        "/v1/promotion/revert",
        headers={"X-Agent-Name": "stratex"},
        json={"memory_id": record.id, "reason": "shared too early"},
    )
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["status"] == "reverted"
    assert reverted.json()["scope"] == "PRIVATE"

    again = client.post(
        "/v1/promotion/revert",
        headers={"X-Agent-Name": "stratex"},
        json={"memory_id": record.id},
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "already_reverted"

    unknown = client.post(
        "/v1/promotion/revert",
        headers={"X-Agent-Name": "stratex"},
        json={"memory_id": "no-such-memory"},
    )
    assert unknown.status_code == 404, unknown.text
