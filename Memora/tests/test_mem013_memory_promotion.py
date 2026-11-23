"""TASK-MEM-013 — memory scope promotion paths (A) and (C).

Owner rule (2026-11-18): promotion is BOTH (A) the owning agent promoting
PRIVATE -> SHARED -> UNIVERSAL on its own judgement AND (C) Memora
auto-promoting when many agents repeatedly need the same memory.
Failed-experiment lessons stay private AND go universal.

On origin/main before this task, (A) stopped at SHARED (UNIVERSAL authoring
was reserved to the Memora service identity at write time, with no
post-creation owner promotion) and (C) did not exist (no need recording, no
repeated-need detection, no auto-promotion). These tests pin the completed
behaviour of ``core.memory.promotion`` and its ``/v1/promotion`` router.
"""
import hashlib
from datetime import datetime, timezone

import pytest

from core.identity.service import IdentityService
from core.memory.promotion import (
    ACTION_NEED,
    ACTION_PROMOTED,
    MemoryPromotionService,
    PromotionPermissionError,
)
from core.memory.search_service import _passes_retrieval_filters
from core.security.provenance import (
    compute_memory_signature,
    verify_memory_signature,
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


def _promotion_audits(test_db, record):
    return (
        test_db.query(AuditLog)
        .filter(AuditLog.memory_id == record.id, AuditLog.action == ACTION_PROMOTED)
        .all()
    )


# --------------------------------------------------------------------- (A)

def test_owner_promotes_private_to_shared_with_recipients(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])

    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge", "sentinel"], reason="team needs it",
    )

    assert result["status"] == "promoted"
    assert result["from_scope"] == "PRIVATE"
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED
    assert shared_membership(db, record.id) == ["forge", "sentinel"]
    assert record_is_visible(record, "forge") is True
    assert record_is_visible(record, "intelx") is False
    audits = _promotion_audits(db, record)
    assert len(audits) == 1
    assert audits[0].details["path"] == "owner_judgement"
    assert audits[0].details["to_scope"] == "SHARED"


def test_owner_promotes_shared_to_universal_completing_the_ladder(mesh):
    """The rung that did not exist on main: owner-driven UNIVERSAL."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="UNIVERSAL", reason="every agent needs this",
    )
    assert result["status"] == "promoted"
    db.refresh(record)
    assert record.scope == MemoryScopeType.UNIVERSAL
    assert record_is_visible(record, "cortex") is True
    assert len(_promotion_audits(db, record)) == 2


def test_non_owner_cannot_promote(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.promote_scope(
            db, owner_name="forge", memory_id=record.id,
            target_scope="SHARED", shared_with=["forge"],
        )
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE
    assert _promotion_audits(db, record) == []


def test_promotion_is_monotonic_and_idempotent(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    again = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    assert again["status"] == "already_at_scope"
    assert len(_promotion_audits(db, record)) == 1  # no duplicate audit row
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.promote_scope(
            db, owner_name="stratex", memory_id=record.id, target_scope="PRIVATE",
        )


def test_shared_promotion_requires_a_recipient(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    with pytest.raises(PromotionPermissionError):
        MemoryPromotionService.promote_scope(
            db, owner_name="stratex", memory_id=record.id, target_scope="SHARED",
        )


def test_failed_experiment_lesson_stays_private_and_goes_universal(mesh):
    db, agents, ns = mesh
    record = _private_memory(
        db, ns, agents["stratex"],
        text="sleeve shock with 3% stop failed: PF 0.92 over 400 trades",
        provenance={"failed_experiment": True, "experiment_outcome": "failed"},
    )
    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="UNIVERSAL", reason="all agents must learn this",
    )
    assert result["status"] == "promoted_dual_copy"
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE  # original stays private
    copy = db.query(MemoryRecord).filter(MemoryRecord.id == result["universal_copy_id"]).first()
    assert copy is not None
    assert copy.scope == MemoryScopeType.UNIVERSAL
    assert copy.content_text == record.content_text
    assert copy.provenance["promoted_from_memory_id"] == record.id
    assert record_is_visible(copy, "futuris") is True
    # Idempotent at the dual rule: a second promotion creates no second copy.
    again = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id, target_scope="UNIVERSAL",
    )
    assert again["universal_copy_id"] == copy.id
    copies = [
        r for r in db.query(MemoryRecord).filter(
            MemoryRecord.scope == MemoryScopeType.UNIVERSAL).all()
        if (r.provenance or {}).get("promoted_from_memory_id") == record.id
    ]
    assert len(copies) == 1


def _signed_lesson(db, ns, owner):
    """A failed-experiment lesson signed the way the write path signs it."""
    text = "sleeve shock with 3% stop failed: PF 0.92 over 400 trades"
    record = _private_memory(
        db, ns, owner,
        text=text,
        content_hash=hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
        provenance={"failed_experiment": True, "experiment_outcome": "failed"},
    )
    record.provenance = {
        **record.provenance,
        "hmac_signature": compute_memory_signature(record_or_dict={
            "id": record.id,
            "tenant_id": record.tenant_id,
            "owner_id": record.owner_id,
            "content_hash": record.content_hash,
            "memory_type": record.memory_type.value,
        }),
        "signature_version": "v1",
    }
    db.commit()
    assert verify_memory_signature(record) is True
    return record


def test_universal_copy_signature_verifies_and_passes_search_gate(mesh):
    """TASK-MEM-021: the dual copy must verify and pass the search gate.

    Before the fix the copy inherited the original's hmac_signature
    (computed over the original's id), so verification failed and search's
    Safety Invariant 2 leg discarded the copy for every actor — the
    MEM-019 lesson was invisible to search for owner and non-owners
    alike even though direct GET returned it.
    """
    db, agents, ns = mesh
    record = _signed_lesson(db, ns, agents["stratex"])
    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="UNIVERSAL", reason="all agents must learn this",
    )
    copy = db.query(MemoryRecord).filter(MemoryRecord.id == result["universal_copy_id"]).first()
    assert copy is not None
    assert verify_memory_signature(copy) is True
    assert copy.provenance["hmac_signature"] != record.provenance["hmac_signature"]
    gate = lambda actor_name: _passes_retrieval_filters(
        copy, db, actor=agents[actor_name], trust_level=None,
        include_expired=False, purpose=None, now_utc=datetime.now(timezone.utc),
    )
    assert gate("futuris") is True
    assert gate("sentinel") is True


def test_repair_universal_copies_resigns_stale_copy(mesh):
    """TASK-MEM-021 repair leg: a stale inherited signature is re-signed."""
    db, agents, ns = mesh
    record = _signed_lesson(db, ns, agents["stratex"])
    result = MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="UNIVERSAL", reason="all agents must learn this",
    )
    copy = db.query(MemoryRecord).filter(MemoryRecord.id == result["universal_copy_id"]).first()
    # Simulate the pre-fix state: the copy carries the original's signature.
    copy.provenance = {
        **copy.provenance,
        "hmac_signature": record.provenance["hmac_signature"],
    }
    db.commit()
    assert verify_memory_signature(copy) is False
    # Dry-run first: reports, writes nothing.
    dry = MemoryPromotionService.repair_universal_copies(db, dry_run=True)
    assert dry["scanned"] == 1
    assert dry["would_repair"] == 1
    assert dry["repaired"] == 0
    db.refresh(copy)
    assert verify_memory_signature(copy) is False
    # Apply: the copy verifies again and nothing is left unrepaired.
    report = MemoryPromotionService.repair_universal_copies(db, dry_run=False)
    db.commit()
    assert report["repaired"] == 1
    assert report["unverifiable_ids"] == []
    assert report["unsigned_ids"] == []
    db.refresh(copy)
    assert verify_memory_signature(copy) is True


# --------------------------------------------------------------------- (C)

def test_record_need_ignores_owner_and_audits_requester(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    own = MemoryPromotionService.record_need(db, requester_name="stratex", memory_id=record.id)
    assert own["status"] == "owner_need_ignored"
    MemoryPromotionService.record_need(db, requester_name="forge", memory_id=record.id, reason="backtest")
    rows = db.query(AuditLog).filter(
        AuditLog.memory_id == record.id, AuditLog.action == ACTION_NEED).all()
    assert len(rows) == 1
    assert rows[0].details["requester"] == "forge"


def test_auto_promotion_below_threshold_does_nothing(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    _needs(db, record, {"forge": 2})  # 1 distinct agent, 2 needs: below both bars
    assert MemoryPromotionService.run_auto_promotion_sweep(db) == []
    db.refresh(record)
    assert record.scope == MemoryScopeType.PRIVATE


def test_auto_promotion_private_to_shared_on_repeated_need(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    _needs(db, record, {"forge": 2, "sentinel": 2})  # 2 distinct, 4 total
    results = MemoryPromotionService.run_auto_promotion_sweep(db)
    assert len(results) == 1
    assert results[0]["to_scope"] == "SHARED"
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED
    assert set(shared_membership(db, record.id)) == {"forge", "sentinel"}
    audits = _promotion_audits(db, record)
    assert len(audits) == 1
    assert audits[0].details["path"] == "auto_repeated_need"
    assert audits[0].details["evidence"]["distinct_agents"] == 2
    assert audits[0].details["evidence"]["total_needs"] == 4
    # Idempotent: the same evidence earns no second rung (needers are now
    # inside the allow-list, so outside-agent evidence is zero).
    assert MemoryPromotionService.run_auto_promotion_sweep(db) == []
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED


def test_auto_promotion_shared_to_universal_needs_outside_demand(mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    _needs(db, record, {"forge": 2, "sentinel": 2})
    MemoryPromotionService.run_auto_promotion_sweep(db)
    # Demand grows beyond the shared team: 2 more distinct agents outside
    # the allow-list, 8 total needs, 4 distinct agents.
    _needs(db, record, {"intelx": 2, "futuris": 2})
    results = MemoryPromotionService.run_auto_promotion_sweep(db)
    assert len(results) == 1
    assert results[0]["to_scope"] == "UNIVERSAL"
    db.refresh(record)
    assert record.scope == MemoryScopeType.UNIVERSAL
    assert record_is_visible(record, "cortex") is True


def test_auto_promotion_of_failed_experiment_uses_dual_copy(mesh):
    db, agents, ns = mesh
    record = _private_memory(
        db, ns, agents["stratex"],
        provenance={"lesson_type": "failed_experiment"},
    )
    record.scope = MemoryScopeType.SHARED
    db.commit()
    _needs(db, record, {"forge": 2, "sentinel": 2, "intelx": 2, "futuris": 2})
    results = MemoryPromotionService.run_auto_promotion_sweep(db)
    assert len(results) == 1
    assert results[0]["status"] == "promoted_dual_copy"
    db.refresh(record)
    assert record.scope == MemoryScopeType.SHARED  # original does not move
    copy = db.query(MemoryRecord).filter(
        MemoryRecord.id == results[0]["universal_copy_id"]).first()
    assert copy.scope == MemoryScopeType.UNIVERSAL


# --------------------------------------------------------------------- API

def test_promotion_api_owner_flow_and_sweep_gate(client, test_db, mesh):
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])

    forbidden = client.post(
        "/v1/promotion/promote",
        headers={"X-Agent-Name": "forge"},
        json={"memory_id": record.id, "target_scope": "UNIVERSAL"},
    )
    assert forbidden.status_code == 403, forbidden.text

    promoted = client.post(
        "/v1/promotion/promote",
        headers={"X-Agent-Name": "stratex"},
        json={"memory_id": record.id, "target_scope": "SHARED", "shared_with": ["forge"]},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["scope"] == "SHARED"

    need = client.post(
        "/v1/promotion/need",
        headers={"X-Agent-Name": "intelx"},
        json={"memory_id": record.id, "reason": "threat intel overlap"},
    )
    assert need.status_code == 200, need.text
    assert need.json()["status"] == "need_recorded"

    sweep_forbidden = client.post(
        "/v1/promotion/sweep", headers={"X-Agent-Name": "stratex"}, json={}
    )
    assert sweep_forbidden.status_code == 403, sweep_forbidden.text

    sweep = client.post(
        "/v1/promotion/sweep", headers={"X-Agent-Name": "memora"}, json={}
    )
    assert sweep.status_code == 200, sweep.text
    assert "promotions" in sweep.json()
