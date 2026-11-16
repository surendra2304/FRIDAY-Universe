"""TASK-IG2-VYR-09: the AgentTube-pattern channel automation gates.

Behaviour pinned here:

* jobs advance stage-by-stage with checkpoints; stages cannot be
  skipped and the approval gate blocks upload without a recorded
  owner approval;
* the mandate cannot be weakened (privacy must stay unlisted, the
  approval gate cannot be disabled, lanes are the VyralX lanes);
* readiness fails closed on missing evidence;
* the only upload plan issued is UNLISTED, via the existing adapter;
* scene repair flags one scene without resetting the job;
* learning proposals never self-apply — sign-off marks eligibility
  only, ``applied`` stays False;
* Shorts repurposing requires an approved/uploaded source and
  enforces the <60s cap.

On clean main every test fails: app.services.channel_automation
does not exist.
"""
from __future__ import annotations

import pytest

from app.services import channel_automation as ca


def _job_at(stage: str) -> dict:
    job = ca.new_job("job-1", "Saturn V", lane="space_science")
    artifacts = {
        "research": {"topic": "Saturn V"},
        "script": {"text": "A script.", "finance_advice_hits": []},
        "production": {"scenes": [{"index": 0}]},
        "metadata": {"title": "Saturn V in 40 Seconds",
                     "description": "The tallest rocket ever flown.",
                     "tags": ["space"]},
    }
    while job["stage"] != stage:
        current = job["stage"]
        if current == "approval":
            ca.approve(job)
        ca.advance(job, artifacts.get(current))
    return job


def test_new_job_starts_checkpointed_at_research():
    job = ca.new_job("j1", "T")
    assert job["stage"] == "research"
    assert job["completed_stages"] == []
    assert job["checkpoints"][0]["stage"] == "research"
    assert job["mandate"]["privacy_status"] == "unlisted"


def test_mandate_cannot_be_weakened():
    with pytest.raises(ca.AutomationError):
        ca.new_job("j", "T", mandate={"privacy_status": "public"})
    with pytest.raises(ca.AutomationError):
        ca.new_job("j", "T", mandate={"approval_required_before_upload": False})
    with pytest.raises(ca.AutomationError):
        ca.new_job("j", "T", lane="crypto_tips")


def test_approval_gate_blocks_upload_without_approval():
    job = _job_at("approval")
    job["approval"] = {"approved": False, "by": None}
    with pytest.raises(ca.AutomationError):
        ca.advance(job)


def test_full_flow_issues_unlisted_upload_plan():
    job = _job_at("upload")
    plan = ca.issue_upload_plan(job)
    assert plan["privacy_status"] == "unlisted"
    assert plan["title"] == "Saturn V in 40 Seconds"
    assert plan["approved_by"] == "owner"
    assert plan["upload_via"] == "vyralx_existing_resumable_adapter"


def test_upload_plan_requires_readiness():
    job = _job_at("upload")
    job["artifacts"]["script"] = {"text": "x"}  # screen result gone
    with pytest.raises(ca.AutomationError):
        ca.issue_upload_plan(job)


def test_readiness_fails_closed_on_missing_evidence():
    job = ca.new_job("j", "T")
    report = ca.readiness(job)
    assert report["ready"] is False
    assert "script_present" in report["failed"]
    assert "finance_screen_clean" in report["failed"]


def test_scene_repair_flags_one_scene_without_reset():
    job = _job_at("production")
    repair = ca.request_scene_repair(job, 2, "footage mismatch")
    assert repair == {"scene_index": 2, "reason": "footage mismatch",
                      "status": "requested"}
    assert job["stage"] == "production"
    assert job["completed_stages"] == ["research", "script"]


def test_learning_proposals_never_self_apply():
    job = _job_at("analytics")
    proposal = ca.propose_learning(job, "Post before 18:00 IST",
                                   source="comments")
    assert proposal["status"] == "proposed" and proposal["applied"] is False
    signed = ca.signoff_learning(job, 0)
    assert signed["status"] == "signed_off"
    assert signed["applied"] is False  # sign-off is not application


def test_shorts_repurpose_requires_upload_and_enforces_cap():
    job = _job_at("analytics")
    plans = ca.plan_shorts_repurpose(job, [{"start_s": 10, "duration_s": 45}])
    assert plans[0]["privacy_if_published"] == "unlisted"
    assert plans[0]["publish"] is False
    with pytest.raises(ca.AutomationError):
        ca.plan_shorts_repurpose(job, [{"start_s": 0, "duration_s": 75}])
    early = ca.new_job("j2", "T")
    with pytest.raises(ca.AutomationError):
        ca.plan_shorts_repurpose(early, [{"start_s": 0, "duration_s": 30}])
