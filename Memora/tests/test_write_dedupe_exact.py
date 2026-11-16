"""
Exact-duplicate write dedupe (MEM-004 fix).

Production accumulated byte-identical copies of the same fact (18 surplus
rows removed by the hygiene pass) because the pipeline's dedupe only scanned
the target namespace and several callers opted out of coalescing entirely.
These tests pin the service-layer rule that replaced that: an exact
duplicate — same tenant, same owner, same content hash, same provenance
subject — returns the canonical record instead of inserting a copy, in BOTH
write services and across namespaces. The /v1/task router (FRIDAY's fleet
store path) no longer opts out blanketly; allow_duplicates=True survives
only as the internal event writers' deliberate occurrence semantics, and
these tests pin that carve-out too. The dedupe_key unique index is the race
net: when the pre-insert lookup is bypassed (simulated race), the loser
adopts the winner instead of landing a second row.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.identity.service import IdentityService
from core.memory.pipeline import write_service
from core.memory.pipeline.deduplication import (
    compute_content_hash,
    compute_dedupe_key,
    extract_subject,
    find_exact_duplicate,
)
from core.memory.pipeline.write_service import MemoryWriteService
from core.memory.schemas import MemoryRecordCreate
from core.memory.service import MemoryService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

TEXT = "FRIDAY confirmed the morning briefing pipeline is healthy."


def _all_records(db):
    return (
        db.query(MemoryRecord)
        .order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        .all()
    )


# ----------------------------------------------------------------------
# Helper semantics
# ----------------------------------------------------------------------

def test_extract_subject_shapes():
    assert extract_subject(None) is None
    assert extract_subject({}) is None
    assert extract_subject({"subject": "teal"}) == "teal"
    assert extract_subject({"metadata": {"subject": "teal"}}) == "teal"
    assert extract_subject({"subject": "  "}) is None
    # Top-level wins over the nested shape.
    assert extract_subject({"subject": "a", "metadata": {"subject": "b"}}) == "a"


def test_dedupe_key_dimensions():
    base = compute_dedupe_key("default", "friday", "hash-a", None)
    assert base == compute_dedupe_key("default", "friday", "hash-a", None)
    assert base != compute_dedupe_key("other", "friday", "hash-a", None)
    assert base != compute_dedupe_key("default", "forge", "hash-a", None)
    assert base != compute_dedupe_key("default", "friday", "hash-b", None)
    assert base != compute_dedupe_key("default", "friday", "hash-a", "subject")


def test_find_exact_duplicate_matches_legacy_content_hash_row(test_db):
    """Rows written before dedupe_key existed carry only content_hash; the
    lookup must still find them (that is the whole pre-fix pipeline store)."""
    agent = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    legacy = MemoryRecord(
        tenant_id="default",
        namespace_id=ns.id,
        owner_id=agent.id,
        owner_agent="friday",
        memory_type=MemoryType.EPISODIC,
        content_text=TEXT,
        content_hash=compute_content_hash(TEXT),
        dedupe_key=None,
        lifecycle_state=LifecycleState.ACTIVE,
    )
    test_db.add(legacy)
    test_db.commit()

    found = find_exact_duplicate(
        test_db,
        tenant_id="default",
        owner_agent="friday",
        content_hash=compute_content_hash(TEXT),
        subject=None,
    )
    assert found is not None
    assert found.id == legacy.id


# ----------------------------------------------------------------------
# Pipeline (MemoryWriteService)
# ----------------------------------------------------------------------

def test_pipeline_duplicate_across_namespaces_returns_canonical(test_db):
    """The headline regression: /v1/memories writes memora://friday/private,
    /v1/task writes memora://friday/general — the same fact must coalesce."""
    first = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/private",
    )
    assert first.is_duplicate is False

    second = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/general",
    )
    assert second.is_duplicate is True
    assert second.record.id == first.record.id
    assert second.step_outputs["step_6_deduplication"]["exact_content_hit"] is True
    assert len(_all_records(test_db)) == 1


def test_task_router_duplicate_store_returns_canonical(client, test_db):
    """The production regression, end to end: FRIDAY's fleet path stores via
    POST /v1/task/execute. The same content re-sent under a new task_id /
    trace_id (per-write volatiles) must return the canonical memory_id with
    duplicate=True and store exactly one row."""
    def _store(task_id, trace_id):
        return client.post(
            "/v1/task/execute",
            headers={"X-Agent-Name": "friday"},
            json={
                "task_id": task_id,
                "trace_id": trace_id,
                "source_agent": "friday",
                "target_agent": "memora",
                "action": "store",
                "payload": {"content": TEXT},
            },
        )

    first = _store("task-1", "trace-1")
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["status"] == "SUCCESS", first_body
    assert first_body["result"]["duplicate"] is False

    second = _store("task-2", "trace-2")
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["status"] == "SUCCESS", second_body
    assert second_body["result"]["duplicate"] is True
    assert second_body["result"]["memory_id"] == first_body["result"]["memory_id"]
    assert len(_all_records(test_db)) == 1


def test_pipeline_allow_duplicates_occurrence_writes_stay_separate(test_db):
    """allow_duplicates=True is deliberate OCCURRENCE semantics (skill
    outcomes, user-model corrections): the Nth identical write is a new
    evidence event. Such writes are neither coalesced nor keyed, so the
    unique index never constrains them."""
    first = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/private",
        allow_duplicates=True,
    )
    second = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/private",
        allow_duplicates=True,
    )
    assert second.is_duplicate is False
    assert second.record.id != first.record.id
    records = _all_records(test_db)
    assert len(records) == 2
    assert all(r.dedupe_key is None for r in records)


def test_pipeline_cross_tenant_same_text_stores(test_db):
    first = MemoryWriteService.execute_pipeline(
        db=test_db, content_text=TEXT, caller_name="friday", tenant_id="default",
    )
    second = MemoryWriteService.execute_pipeline(
        db=test_db, content_text=TEXT, caller_name="friday", tenant_id="tenant-b",
    )
    assert second.is_duplicate is False
    assert second.record.id != first.record.id
    assert len(_all_records(test_db)) == 2


def test_pipeline_cross_agent_same_text_stores(test_db):
    first = MemoryWriteService.execute_pipeline(
        db=test_db, content_text=TEXT, caller_name="friday",
    )
    second = MemoryWriteService.execute_pipeline(
        db=test_db, content_text=TEXT, caller_name="forge",
    )
    assert second.is_duplicate is False
    assert second.record.id != first.record.id
    assert len(_all_records(test_db)) == 2


def test_pipeline_subject_differing_same_text_stores(test_db):
    """Distinct namespaces per write isolate the exact-check layer from the
    fuzzy namespace coalescing: only the subject dimension is under test."""
    alpha = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/private",
        provenance={"subject": "alpha"},
    )
    beta = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/general",
        provenance={"subject": "beta"},
    )
    assert beta.is_duplicate is False
    assert beta.record.id != alpha.record.id
    assert len(_all_records(test_db)) == 2

    alpha_again = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/projects",
        provenance={"subject": "alpha"},
    )
    assert alpha_again.is_duplicate is True
    assert alpha_again.record.id == alpha.record.id
    assert len(_all_records(test_db)) == 2


def test_pipeline_concurrent_duplicate_adopts_winner(test_db, monkeypatch):
    """Simulated race: the loser's pre-insert lookup misses the winner
    (patched to None for its first call), so its insert hits the dedupe
    unique index — the pipeline must adopt the winner, not error or dup."""
    winner = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/private",
    )

    real_find = write_service.find_exact_duplicate
    calls = {"n": 0}

    def miss_first(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_find(*args, **kwargs)

    monkeypatch.setattr(write_service, "find_exact_duplicate", miss_first)

    loser = MemoryWriteService.execute_pipeline(
        db=test_db,
        content_text=TEXT,
        caller_name="friday",
        target_namespace_path="memora://friday/general",
    )
    assert loser.is_duplicate is True
    assert loser.record.id == winner.record.id
    assert loser.step_outputs["step_6_deduplication"]["recovered_via"] == "dedupe_key"
    assert len(_all_records(test_db)) == 1


# ----------------------------------------------------------------------
# Direct service (MemoryService.create_memory)
# ----------------------------------------------------------------------

def test_create_memory_duplicate_returns_canonical(test_db):
    first = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(content_text=TEXT, owner_name="friday"),
        actor_name="friday",
    )
    assert first.content_hash == compute_content_hash(TEXT)
    assert first.dedupe_key is not None

    second = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(content_text=TEXT, owner_name="friday"),
        actor_name="friday",
    )
    assert second.id == first.id
    assert len(_all_records(test_db)) == 1


def test_create_memory_subject_differing_stores(test_db):
    first = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text=TEXT, owner_name="friday", provenance={"subject": "alpha"}
        ),
        actor_name="friday",
    )
    second = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(
            content_text=TEXT, owner_name="friday", provenance={"subject": "beta"}
        ),
        actor_name="friday",
    )
    assert second.id != first.id
    assert len(_all_records(test_db)) == 2


def test_create_memory_concurrent_duplicate_adopts_winner(test_db, monkeypatch):
    import core.memory.pipeline.deduplication as dedup_module

    winner = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(content_text=TEXT, owner_name="friday"),
        actor_name="friday",
    )

    real_find = dedup_module.find_exact_duplicate
    calls = {"n": 0}

    def miss_first(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_find(*args, **kwargs)

    monkeypatch.setattr(dedup_module, "find_exact_duplicate", miss_first)

    loser = MemoryService.create_memory(
        test_db,
        MemoryRecordCreate(content_text=TEXT, owner_name="friday"),
        actor_name="friday",
    )
    assert loser.id == winner.id
    assert len(_all_records(test_db)) == 1


# ----------------------------------------------------------------------
# Database-level race net
# ----------------------------------------------------------------------

def test_dedupe_key_unique_index_rejects_second_row(test_db):
    agent = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    key = compute_dedupe_key("default", "friday", compute_content_hash(TEXT), None)

    def _row():
        return MemoryRecord(
            tenant_id="default",
            namespace_id=ns.id,
            owner_id=agent.id,
            owner_agent="friday",
            memory_type=MemoryType.EPISODIC,
            content_text=TEXT,
            content_hash=compute_content_hash(TEXT),
            dedupe_key=key,
            lifecycle_state=LifecycleState.ACTIVE,
        )

    test_db.add(_row())
    test_db.commit()
    test_db.add(_row())
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()
    assert len(_all_records(test_db)) == 1
