"""Tests for the TASK-MEM-004 store-wide hygiene pass (core.memory.hygiene).

Covers: exact-duplicate grouping with the verified-first winner rule,
evidence-before-recency contradiction resolution, near-duplicate review
class (planned, never applied without opt-in), provenance preservation,
audit rows, idempotency, and scope isolation.
"""
from datetime import datetime, timedelta, timezone

from core.identity.service import IdentityService
from core.memory.hygiene import (
    KIND_CONTRADICTION,
    KIND_EXACT,
    KIND_NEAR,
    analyze,
    apply_actions,
)
from storage.relational.models import (
    AuditLog,
    LifecycleState,
    MemoryRecord,
    MemoryType,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _seed(test_db, contents, namespace_path="memora://friday/private"):
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, namespace_path)
    records = []
    for spec in contents:
        record = MemoryRecord(
            namespace_id=ns.id,
            owner_id=actor.id,
            memory_type=MemoryType.SEMANTIC,
            content_text=spec["text"],
            confidence=spec.get("confidence", 0.8),
            lifecycle_state=spec.get("state", LifecycleState.ACTIVE),
            created_at=T0 + timedelta(days=spec.get("day", 0)),
            provenance=spec.get("provenance"),
            source=spec.get("source", "test"),
        )
        test_db.add(record)
        records.append(record)
    test_db.commit()
    for record in records:
        test_db.refresh(record)
    return records


def _live(test_db):
    return (
        test_db.query(MemoryRecord)
        .filter(MemoryRecord.lifecycle_state.in_(
            [LifecycleState.CANDIDATE, LifecycleState.ACTIVE, LifecycleState.VERIFIED]))
        .all()
    )


def test_exact_duplicate_group_prefers_verified_over_newer(test_db):
    records = _seed(test_db, [
        {"text": "The owner prefers concise answers.", "day": 2, "confidence": 0.95},
        {"text": "the owner prefers concise answers.", "day": 0,
         "state": LifecycleState.VERIFIED, "confidence": 0.5},
        {"text": "  The   owner prefers concise answers. ", "day": 3, "confidence": 0.9},
    ])
    report = analyze(records)
    assert report.exact_groups == 1
    assert report.exact_excess_records == 2
    actions = [a for a in report.actions if a.kind == KIND_EXACT]
    assert len(actions) == 2
    verified = records[1]
    assert all(a.winner_id == verified.id for a in actions)
    assert {a.loser_id for a in actions} == {records[0].id, records[2].id}


def test_exact_duplicate_group_newest_wins_when_none_verified(test_db):
    records = _seed(test_db, [
        {"text": "Server region is ap-mumbai-1.", "day": 1},
        {"text": "Server region is ap-mumbai-1.", "day": 5},
    ])
    report = analyze(records)
    assert len(report.actions) == 1
    assert report.actions[0].winner_id == records[1].id
    assert report.actions[0].loser_id == records[0].id


def test_contradiction_evidence_beats_recency(test_db):
    records = _seed(test_db, [
        {"text": "PostgreSQL connection pool maximum is 50 connections.",
         "day": 0, "confidence": 1.0},
        {"text": "PostgreSQL connection pool maximum is 20 connections.",
         "day": 9, "confidence": 0.4},
    ])
    report = analyze(records)
    assert report.contradiction_pairs == 1
    assert report.contradiction_by_kind == {"conflicting_scalar_value": 1}
    action = report.actions[0]
    assert action.kind == KIND_CONTRADICTION
    # Older but far stronger evidence wins; recency alone never decides.
    assert action.winner_id == records[0].id
    assert action.loser_id == records[1].id


def test_contradiction_verified_newcomer_wins(test_db):
    records = _seed(test_db, [
        {"text": "TLS verification is enabled.", "day": 0, "confidence": 1.0},
        {"text": "TLS verification is not enabled.", "day": 4,
         "state": LifecycleState.VERIFIED, "confidence": 0.4},
    ])
    report = analyze(records)
    assert report.contradiction_pairs == 1
    assert report.contradiction_by_kind == {"opposite_polarity": 1}
    action = report.actions[0]
    assert action.winner_id == records[1].id  # the verified value is kept
    assert action.loser_id == records[0].id


def test_cross_namespace_identical_content_is_not_grouped(test_db):
    from storage.relational.models import Namespace, NamespaceType

    actor = IdentityService.register_agent(test_db, "friday")
    ns_a = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    ns_b = Namespace(path="memora://friday/project-x", agent_id=actor.id,
                     type=NamespaceType.PROJECT_PRIVATE, tenant_id="default")
    test_db.add(ns_b)
    test_db.commit()
    text = "The standup happens at 09:30."
    a = MemoryRecord(namespace_id=ns_a.id, owner_id=actor.id,
                     memory_type=MemoryType.SEMANTIC, content_text=text,
                     lifecycle_state=LifecycleState.ACTIVE, created_at=T0)
    b = MemoryRecord(namespace_id=ns_b.id, owner_id=actor.id,
                     memory_type=MemoryType.SEMANTIC, content_text=text,
                     lifecycle_state=LifecycleState.ACTIVE, created_at=T0)
    test_db.add_all([a, b])
    test_db.commit()
    report = analyze([a, b])
    assert report.actions == []


def test_non_live_records_are_ignored(test_db):
    records = _seed(test_db, [
        {"text": "The cache TTL is 300 seconds.", "day": 0},
        {"text": "The cache TTL is 300 seconds.", "day": 1,
         "state": LifecycleState.SUPERSEDED},
    ])
    report = analyze(records)
    assert report.live_records == 1
    assert report.actions == []


def test_near_duplicate_is_review_class_only(test_db):
    records = _seed(test_db, [
        {"text": "The deployment window opens at midnight UTC every single day", "day": 0},
        {"text": "The deployment window opens at midnight UTC every day", "day": 1},
    ])
    report = analyze(records)
    assert report.near_pairs == 1
    assert [a.kind for a in report.actions] == [KIND_NEAR]

    result = apply_actions(test_db, report.actions)
    assert result["applied"] == []
    assert len(result["skipped"]) == 1
    assert "opt-in" in result["skipped"][0]["why"]
    assert all(r.lifecycle_state == LifecycleState.ACTIVE for r in _live(test_db))

    result2 = apply_actions(test_db, report.actions, include_near=True)
    assert len(result2["applied"]) == 1
    states = {r.id: r.lifecycle_state for r in test_db.query(MemoryRecord).all()}
    assert states[records[0].id] == LifecycleState.SUPERSEDED
    assert states[records[1].id] == LifecycleState.ACTIVE


def test_apply_supersedes_preserves_provenance_and_audits(test_db):
    # Both records carry equally rich provenance, so their evidence scores
    # tie and recency decides: the day-2 record is the winner. (With poorer
    # provenance the newer record would lose on evidence — see
    # test_contradiction_evidence_beats_recency.)
    records = _seed(test_db, [
        {"text": "The owner timezone is Asia/Kolkata.", "day": 0,
         "provenance": {"origin": "onboarding", "ticket": "T-1"}},
        {"text": "The owner timezone is Asia/Kolkata.", "day": 2,
         "provenance": {"origin": "chat", "ticket": "T-2"}},
    ])
    report = analyze(records)
    result = apply_actions(test_db, report.actions)
    assert len(result["applied"]) == 1
    assert result["failed"] == []

    loser = test_db.get(MemoryRecord, records[0].id)
    winner = test_db.get(MemoryRecord, records[1].id)
    assert loser is not None  # superseded, never deleted
    assert loser.lifecycle_state == LifecycleState.SUPERSEDED
    assert loser.superseded_by_id == winner.id
    # Original provenance intact, hygiene note appended.
    assert loser.provenance["origin"] == "onboarding"
    assert loser.provenance["ticket"] == "T-1"
    notes = loser.provenance["hygiene"]
    assert notes[-1]["task"] == "TASK-MEM-004"
    assert notes[-1]["winner_id"] == winner.id
    assert winner.provenance["hygiene"][-1]["loser_id"] == loser.id

    audits = test_db.query(AuditLog).filter(AuditLog.memory_id == loser.id).all()
    assert len(audits) == 1
    assert audits[0].action == "hygiene_exact_duplicate"
    assert audits[0].details["winner_id"] == winner.id


def test_apply_is_idempotent(test_db):
    records = _seed(test_db, [
        {"text": "Backups run nightly at 02:00.", "day": 0},
        {"text": "Backups run nightly at 02:00.", "day": 1},
        {"text": "Backups run nightly at 02:00.", "day": 2},
    ])
    report = analyze(records)
    first = apply_actions(test_db, report.actions)
    assert len(first["applied"]) == 2

    second_report = analyze(_live(test_db))
    assert second_report.actions == []

    replay = apply_actions(test_db, report.actions)
    assert replay["applied"] == []
    assert len(replay["skipped"]) == 2  # losers no longer live


def test_analyze_does_not_mutate(test_db):
    records = _seed(test_db, [
        {"text": "The API allows external access.", "day": 0},
        {"text": "The API denies external access.", "day": 1},
        {"text": "The API allows external access.", "day": 2},
    ])
    before = {r.id: (r.lifecycle_state, r.superseded_by_id) for r in records}
    report = analyze(records)
    # "allows" contradicts "denies" for both copies of the allows-statement.
    assert report.contradiction_pairs == 2
    assert report.exact_groups == 1
    after = {r.id: (r.lifecycle_state, r.superseded_by_id)
             for r in test_db.query(MemoryRecord).all()}
    assert before == after
