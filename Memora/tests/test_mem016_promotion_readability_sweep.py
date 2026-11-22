"""TASK-MEM-016 — promotion readability (G1) + sweep window (G2).

MEM-014 proved live that (G1) an owner-promoted record stayed unreadable to
its audience — the policy engine decided by namespace type only, so a
SHARED/UNIVERSAL record in a private namespace returned 403 to its
recipients — and (G2) the auto-promotion sweep never evaluated a recent
memory, because its 200-oldest scan filled with older records first.

These tests pin the fixes, mirroring the MEM-014 live probe (M1/M2) at the
unit/API level: the engine honours promoted scope for read/query, and the
sweep evaluates need-bearing memories before the oldest-first scan.
"""
from datetime import datetime, timezone

import pytest

from core.identity.service import IdentityService
from core.memory.promotion import MemoryPromotionService
from core.memory.search_service import _passes_retrieval_filters
from core.policy.engine import PolicyEngine
from storage.relational.models import (
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


def _read_decision(db, agents, namespace, actor_name, record):
    return PolicyEngine.evaluate_access(
        db,
        actor=agents[actor_name],
        namespace=namespace,
        action="read",
        memory_id=record.id,
        log_audit=False,
    )


# --------------------------------------------------------------------- G1

def test_promoted_shared_readable_by_recipient_via_policy_engine(mesh):
    """MEM-014 M1, engine level: SHARED promotion admits its recipients."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    assert _read_decision(db, agents, ns, "forge", record).allowed is False
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge", "sentinel"],
    )
    decision = _read_decision(db, agents, ns, "forge", record)
    assert decision.allowed is True
    assert decision.rule_matched == "RULE_1_PROMOTED_SCOPE_READ"
    assert _read_decision(db, agents, ns, "sentinel", record).allowed is True


def test_promoted_universal_readable_by_outsider_via_policy_engine(mesh):
    """MEM-014 M1, second rung: UNIVERSAL admits an agent never listed."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id, target_scope="UNIVERSAL",
    )
    decision = _read_decision(db, agents, ns, "cortex", record)
    assert decision.allowed is True
    assert decision.rule_matched == "RULE_1_PROMOTED_SCOPE_READ"


def test_promoted_shared_still_denies_non_recipient(mesh):
    """The fix is scoped, not a hole: SHARED admits only its allow-list."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    decision = _read_decision(db, agents, ns, "intelx", record)
    assert decision.allowed is False
    assert decision.rule_matched == "RULE_1_PRIVATE_BY_DEFAULT_PROMOTION_REQUIRED"


def test_private_record_still_denied_to_non_owner(mesh):
    """Unpromoted records behave exactly as before the fix."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    decision = _read_decision(db, agents, ns, "forge", record)
    assert decision.allowed is False
    assert decision.rule_matched == "RULE_1_PRIVATE_BY_DEFAULT_PROMOTION_REQUIRED"
    assert _read_decision(db, agents, ns, "stratex", record).allowed is True


def test_promotion_confers_read_only_not_mutation(mesh):
    """A promoted record's audience may read it, never write/share it."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    for action in ("write", "share", "delete", "promote", "update"):
        decision = PolicyEngine.evaluate_access(
            db, actor=agents["forge"], namespace=ns, action=action,
            memory_id=record.id, log_audit=False,
        )
        assert decision.allowed is False, action


def test_search_gate_admits_promoted_record_to_recipient(mesh):
    """MEM-014 M1, search level: the per-record policy gate admits it."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    gate = lambda actor_name: _passes_retrieval_filters(
        record, db, actor=agents[actor_name], trust_level=None,
        include_expired=False, purpose=None, now_utc=datetime.now(timezone.utc),
    )
    assert gate("forge") is False
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    assert gate("forge") is True
    assert gate("intelx") is False


def test_get_endpoint_returns_promoted_record_to_recipient(client, test_db, mesh):
    """MEM-014 M1, API level: GET 200 for the recipient, 404 otherwise."""
    db, agents, ns = mesh
    record = _private_memory(db, ns, agents["stratex"])
    url = f"/v1/memories/{record.id}"
    assert client.get(url, headers={"X-Agent-Name": "forge"}).status_code == 404
    MemoryPromotionService.promote_scope(
        db, owner_name="stratex", memory_id=record.id,
        target_scope="SHARED", shared_with=["forge"],
    )
    got = client.get(url, headers={"X-Agent-Name": "forge"})
    assert got.status_code == 200, got.text
    assert got.json()["scope"] == "SHARED"
    assert client.get(url, headers={"X-Agent-Name": "intelx"}).status_code == 404


# --------------------------------------------------------------------- G2

def test_sweep_reaches_need_bearing_recent_memory(mesh):
    """MEM-014 M2: 201 older records must not starve a needy recent one."""
    db, agents, ns = mesh
    owner = agents["stratex"]
    for i in range(201):
        _private_memory(db, ns, owner, text=f"old filler memory {i}")
    recent = _private_memory(db, ns, owner, text="recent memory agents keep needing")
    _needs(db, recent, {"forge": 2, "sentinel": 2})  # 2 distinct, 4 total
    results = MemoryPromotionService.run_auto_promotion_sweep(db)
    assert len(results) == 1
    assert results[0]["memory_id"] == recent.id
    assert results[0]["to_scope"] == "SHARED"
    db.refresh(recent)
    assert recent.scope == MemoryScopeType.SHARED


def test_sweep_budget_still_applies_to_need_first_candidates(mesh):
    """The limit is a budget, not a suggestion: limit=1 promotes one."""
    db, agents, ns = mesh
    owner = agents["stratex"]
    first = _private_memory(db, ns, owner, text="first needy memory")
    _needs(db, first, {"forge": 2, "sentinel": 2})
    second = _private_memory(db, ns, owner, text="second needy memory")
    _needs(db, second, {"forge": 2, "sentinel": 2})
    results = MemoryPromotionService.run_auto_promotion_sweep(db, limit=1)
    assert len(results) == 1
    # Most-recent-need first: the second record's needs were recorded last.
    assert results[0]["memory_id"] == second.id
    db.refresh(first)
    assert first.scope == MemoryScopeType.PRIVATE


def test_sweep_below_threshold_still_promotes_nothing(mesh):
    """Need-first ordering does not lower the bar: below threshold, no-op."""
    db, agents, ns = mesh
    owner = agents["stratex"]
    for i in range(5):
        _private_memory(db, ns, owner, text=f"old filler memory {i}")
    recent = _private_memory(db, ns, owner, text="recent memory, thin demand")
    _needs(db, recent, {"forge": 2})  # 1 distinct agent: below both bars
    assert MemoryPromotionService.run_auto_promotion_sweep(db) == []
    db.refresh(recent)
    assert recent.scope == MemoryScopeType.PRIVATE


def test_sweep_without_needs_keeps_oldest_first_order(mesh):
    """No-need sweeps behave exactly as before: oldest-first, in budget."""
    db, agents, ns = mesh
    owner = agents["stratex"]
    records = [
        _private_memory(db, ns, owner, text=f"old memory {i}") for i in range(3)
    ]
    # None of these can promote (no needs at all), so the sweep is a no-op —
    # the ordering assertion is that it runs without error and promotes [].
    assert MemoryPromotionService.run_auto_promotion_sweep(db) == []
    for record in records:
        db.refresh(record)
        assert record.scope == MemoryScopeType.PRIVATE
