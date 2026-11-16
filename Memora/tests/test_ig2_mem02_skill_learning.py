"""
TASK-IG2-MEM-02 — Hermes skill-learning loop.

Contracts locked here:
- outcomes are recorded per pattern; invalid outcomes and a
  correction without correction text are refused with reasons;
- a pattern drafts a skill after >= 3 successes at >= 80% success
  rate, OR immediately on any owner correction (correction quoted
  verbatim in the draft);
- drafts are pending_review and NEVER self-activate: active_skills is
  empty until review_skill approves; rejection is terminal for that
  draft;
- re-evaluating with no new evidence drafts nothing; new evidence
  produces a version+1 draft.
"""
from core.identity.service import IdentityService
from core.memory.skill_learning_service import SkillLearningService
from storage.relational.models import MemoryRecord, MemoryType


def _setup(test_db):
    IdentityService.register_agent(test_db, "friday")


def _outcome(test_db, key, outcome, detail="did the thing", correction=None):
    return SkillLearningService.record_outcome(
        test_db, actor_name="friday", pattern_key=key, outcome=outcome,
        detail=detail, correction=correction,
    )


def test_outcome_validation(test_db):
    _setup(test_db)
    assert _outcome(test_db, "p", "maybe")["stored"] is False
    assert _outcome(test_db, "", "success")["stored"] is False
    no_text = _outcome(test_db, "p", "corrected", correction=None)
    assert no_text["stored"] is False
    assert no_text["reason"] == "corrected_outcome_needs_correction_text"
    assert _outcome(test_db, "p", "success")["stored"] is True


def test_repeated_success_drafts_pending_skill(test_db):
    _setup(test_db)
    for i in range(3):
        assert _outcome(test_db, "fleet-health-brief", "success", detail=f"probe run {i} all agents 200")["stored"]
    result = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert len(result["drafted"]) == 1
    draft = result["drafted"][0]
    assert draft["pattern_key"] == "fleet-health-brief"
    assert draft["trigger"] == "repeated_success"
    assert draft["version"] == 1

    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="friday")
    assert len(drafts) == 1
    assert drafts[0]["review_status"] == "pending_review"
    record = test_db.query(MemoryRecord).filter(MemoryRecord.id == drafts[0]["id"]).one()
    assert record.memory_type == MemoryType.PROCEDURAL
    # Not active until a reviewer says so.
    assert SkillLearningService.active_skills(test_db, actor_name="friday") == []

    # No new evidence → no new draft.
    again = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert again["drafted"] == []
    assert any(s["reason"] == "no_new_evidence" for s in again["skipped"])


def test_below_threshold_and_failure_heavy_patterns_do_not_draft(test_db):
    _setup(test_db)
    _outcome(test_db, "rare-task", "success")
    _outcome(test_db, "rare-task", "success")
    for _ in range(3):
        _outcome(test_db, "flaky-task", "success")
    for _ in range(2):
        _outcome(test_db, "flaky-task", "failure", detail="timed out")
    result = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert result["drafted"] == []
    reasons = {s["pattern_key"]: s["reason"] for s in result["skipped"]}
    assert reasons["rare-task"] == "below_threshold"
    assert reasons["flaky-task"] == "below_threshold"  # 3/5 = 60% < 80%


def test_owner_correction_drafts_immediately_with_verbatim_correction(test_db):
    _setup(test_db)
    _outcome(
        test_db, "morning-brief", "corrected",
        detail="sent the brief at 09:30",
        correction="Briefs go at 08:50 IST, never 09:30.",
    )
    result = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert len(result["drafted"]) == 1
    assert result["drafted"][0]["trigger"] == "owner_correction"
    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="friday")
    assert "Briefs go at 08:50 IST, never 09:30." in drafts[0]["content"]


def test_review_gate_approve_and_reject(test_db):
    _setup(test_db)
    for _ in range(3):
        _outcome(test_db, "skill-a", "success")
        _outcome(test_db, "skill-b", "success")
    # interleave correction so both draft in one pass (skill-b via repetition needs 3 successes: it has them)
    SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    drafts = {d["pattern_key"]: d for d in SkillLearningService.list_skill_drafts(test_db, actor_name="friday")}
    assert set(drafts) == {"skill-a", "skill-b"}

    approved = SkillLearningService.review_skill(
        test_db, actor_name="friday", draft_id=drafts["skill-a"]["id"], approve=True
    )
    assert approved["reviewed"] is True and approved["review_status"] == "active"
    active = SkillLearningService.active_skills(test_db, actor_name="friday")
    assert [s["pattern_key"] for s in active] == ["skill-a"]

    rejected = SkillLearningService.review_skill(
        test_db, actor_name="friday", draft_id=drafts["skill-b"]["id"], approve=False
    )
    assert rejected["review_status"] == "rejected"
    # A decided draft cannot be re-decided.
    again = SkillLearningService.review_skill(
        test_db, actor_name="friday", draft_id=drafts["skill-b"]["id"], approve=True
    )
    assert again["reviewed"] is False


def test_new_evidence_revises_draft_to_version_2(test_db):
    _setup(test_db)
    for _ in range(3):
        _outcome(test_db, "deploy-check", "success", detail="checked the deploy")
    first = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert first["drafted"][0]["version"] == 1
    _outcome(test_db, "deploy-check", "success", detail="checked the deploy again")
    second = SkillLearningService.evaluate_patterns(test_db, actor_name="friday")
    assert len(second["drafted"]) == 1
    assert second["drafted"][0]["version"] == 2
