"""
TASK-IG2-MEM-02 follow-up — skill drafting vs the REAL write-policy gate.

The original MEM-02 suites only ever evaluate as "friday". That hid a
production refusal: PROCEDURAL is an evidence-required type, and when
the caller is the Memora service identity itself the write pipeline
applies its strict branch — verified/operator-confirmed trust plus at
least one evidence reference, read from the pipeline's evidence_refs
argument. The learning loop passed neither (its evidence sat under a
provenance key the policy never reads), so every draft the service
identity tried to write was refused with PermissionDeniedError and the
loop could never draft for memora-owned outcomes — over the API when
evaluating as memora, and in the background pass for any pattern whose
outcomes memora owns. Production probes (2026-11-16) proved both
triggers refused live.

Locked here, against the unmocked pipeline and policy:
- as the service identity, a qualifying repeated_success pattern drafts
  (evidence_refs = the stored outcome ids, trust "verified" — the
  service verified the stored records meet the declared bar);
- as the service identity, an owner_correction pattern drafts
  (trust "operator_confirmed" — the operator's correction is itself
  part of the evidence);
- drafts land pending_review and never self-activate; the review gate
  still decides;
- the gate itself is unchanged: a direct PROCEDURAL write from the
  service identity with a trust label but NO evidence — or evidence
  but no trusted label — is still refused, and a below-threshold
  pattern drafts nothing. The fix is in the caller, not the policy.
"""
import pytest

from core.identity.service import IdentityService
from core.memory.pipeline.write_service import MemoryWriteService
from core.memory.service import PermissionDeniedError
from core.memory.skill_learning_service import SkillLearningService
from storage.relational.models import MemoryRecord, MemoryType


def _setup(test_db):
    IdentityService.register_agent(test_db, "memora")
    IdentityService.register_agent(test_db, "friday")


def _outcome(test_db, key, outcome, detail="did the thing", correction=None, actor="memora"):
    return SkillLearningService.record_outcome(
        test_db, actor_name=actor, pattern_key=key, outcome=outcome,
        detail=detail, correction=correction,
    )


def test_memora_repeated_success_drafts_against_real_policy_gate(test_db):
    _setup(test_db)
    outcome_ids = []
    for i in range(3):
        stored = _outcome(
            test_db, "fleet-health-brief", "success",
            detail=f"probe run {i} all agents 200",
        )
        assert stored["stored"], stored
        outcome_ids.append(stored["id"])

    result = SkillLearningService.evaluate_patterns(test_db, actor_name="memora")
    assert len(result["drafted"]) == 1, result
    draft = result["drafted"][0]
    assert draft["pattern_key"] == "fleet-health-brief"
    assert draft["trigger"] == "repeated_success"
    assert draft["version"] == 1

    # The draft is a real PROCEDURAL record whose provenance carries the
    # canonical evidence the policy consumed — the qualifying outcome
    # records themselves, stamped by the pipeline, not just the loop's
    # own bookkeeping key.
    record = test_db.query(MemoryRecord).filter(MemoryRecord.id == draft["draft_id"]).one()
    assert record.memory_type == MemoryType.PROCEDURAL
    assert record.provenance["evidence_refs"] == outcome_ids
    assert record.provenance["evidence_ids"] == outcome_ids
    assert record.provenance["trust_level"] == "verified"

    # Pending, never self-activated.
    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="memora")
    assert len(drafts) == 1 and drafts[0]["review_status"] == "pending_review"
    assert SkillLearningService.active_skills(test_db, actor_name="memora") == []

    # The review gate still disposes: approve → active.
    reviewed = SkillLearningService.review_skill(
        test_db, actor_name="memora", draft_id=draft["draft_id"], approve=True
    )
    assert reviewed["reviewed"] is True and reviewed["review_status"] == "active"
    active = SkillLearningService.active_skills(test_db, actor_name="memora")
    assert [s["pattern_key"] for s in active] == ["fleet-health-brief"]


def test_memora_owner_correction_drafts_against_real_policy_gate(test_db):
    _setup(test_db)
    stored = _outcome(
        test_db, "morning-brief", "corrected",
        detail="sent the brief at 09:30",
        correction="Briefs go at 08:50 IST, never 09:30.",
    )
    assert stored["stored"], stored

    result = SkillLearningService.evaluate_patterns(test_db, actor_name="memora")
    assert len(result["drafted"]) == 1, result
    draft = result["drafted"][0]
    assert draft["trigger"] == "owner_correction"

    record = test_db.query(MemoryRecord).filter(MemoryRecord.id == draft["draft_id"]).one()
    assert record.memory_type == MemoryType.PROCEDURAL
    assert record.provenance["evidence_refs"] == [stored["id"]]
    # The operator's own correction is in the evidence, so the trust the
    # service asserts is operator-confirmed.
    assert record.provenance["trust_level"] == "operator_confirmed"

    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="memora")
    assert len(drafts) == 1 and drafts[0]["review_status"] == "pending_review"
    assert "Briefs go at 08:50 IST, never 09:30." in drafts[0]["content"]
    assert SkillLearningService.active_skills(test_db, actor_name="memora") == []


def test_memora_new_evidence_revises_draft_to_version_2(test_db):
    _setup(test_db)
    for _ in range(3):
        assert _outcome(test_db, "deploy-check", "success", detail="checked the deploy")["stored"]
    first = SkillLearningService.evaluate_patterns(test_db, actor_name="memora")
    assert len(first["drafted"]) == 1 and first["drafted"][0]["version"] == 1

    assert _outcome(test_db, "deploy-check", "success", detail="checked the deploy again")["stored"]
    second = SkillLearningService.evaluate_patterns(test_db, actor_name="memora")
    assert len(second["drafted"]) == 1, second
    assert second["drafted"][0]["version"] == 2


def test_background_pass_drafts_for_memora_owned_outcomes(test_db):
    from apps.api.routers.v1_skills import run_evaluation_pass

    _setup(test_db)
    for _ in range(3):
        assert _outcome(test_db, "deploy-check", "success")["stored"]

    summary = run_evaluation_pass(test_db)
    assert summary["drafted"] == 1, summary
    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="memora")
    assert len(drafts) == 1 and drafts[0]["review_status"] == "pending_review"
    assert SkillLearningService.active_skills(test_db, actor_name="memora") == []

    # Idempotent: no new evidence → the pass drafts nothing more.
    summary = run_evaluation_pass(test_db)
    assert summary["drafted"] == 0, summary


def test_gate_still_refuses_evidence_free_procedural_write(test_db):
    """The policy gate is NOT weakened by the caller fix: from the
    service identity, a trust label without evidence — and evidence
    without a trusted label — are both still refused."""
    _setup(test_db)
    with pytest.raises(PermissionDeniedError):
        MemoryWriteService.execute_pipeline(
            test_db,
            content_text="SKILL DRAFT — fabricated pattern with no evidence behind it.",
            caller_name="memora",
            memory_type=MemoryType.PROCEDURAL,
            source="skill_learning_draft",
            trust_level="verified",
            evidence_refs=[],
        )
    with pytest.raises(PermissionDeniedError):
        MemoryWriteService.execute_pipeline(
            test_db,
            content_text="SKILL DRAFT — evidence claimed but trust left candidate.",
            caller_name="memora",
            memory_type=MemoryType.PROCEDURAL,
            source="skill_learning_draft",
            evidence_refs=["some-record-id"],
        )
    # Nothing was persisted by either refused write.
    assert test_db.query(MemoryRecord).filter(
        MemoryRecord.memory_type == MemoryType.PROCEDURAL
    ).count() == 0


def test_below_threshold_pattern_drafts_nothing_as_memora(test_db):
    _setup(test_db)
    _outcome(test_db, "rare-task", "success")
    _outcome(test_db, "rare-task", "success")
    result = SkillLearningService.evaluate_patterns(test_db, actor_name="memora")
    assert result["drafted"] == []
    reasons = {s["pattern_key"]: s["reason"] for s in result["skipped"]}
    assert reasons["rare-task"] == "below_threshold"
