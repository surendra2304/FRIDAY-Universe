"""
TASK-IG2-MEM-02 wiring — the skill-learning loop over HTTP + background.

The service contracts are locked by test_ig2_mem02_skill_learning.py.
What was missing — and what this suite locks — is the PRODUCTION
CALLER: the mounted /v1/skills router and the background evaluation
pass in the app lifespan. Before this wiring, SkillLearningService was
referenced only by its own module and its tests.

Locked here:
- the full loop runs over HTTP with the authenticated identity as the
  actor: record outcomes → stats → evaluate → pending draft → active
  stays empty until review;
- the review gate is admin-only (the Memora service identity): a
  working agent may propose outcomes and trigger evaluation, but may
  not activate its own drafted skill;
- an owner correction recorded over HTTP drafts immediately;
- the background pass (run_evaluation_pass, called by the lifespan
  worker) drafts pending skills for actors with outcomes and is
  idempotent — and it can never activate a skill;
- the routes are mounted on the real app.
"""
from core.identity.service import IdentityService
from apps.api.routers.v1_skills import run_evaluation_pass
from core.memory.skill_learning_service import SkillLearningService


def _setup(test_db):
    IdentityService.register_agent(test_db, "friday")
    IdentityService.register_agent(test_db, "memora")


def _outcome(client, key, outcome, detail="did the thing", correction=None):
    body = {"pattern_key": key, "outcome": outcome, "detail": detail}
    if correction:
        body["correction"] = correction
    return client.post("/v1/skills/outcomes", json=body)


def test_full_loop_over_http(client, test_db):
    _setup(test_db)
    for i in range(3):
        resp = _outcome(client, "fleet-health-brief", "success", detail=f"probe run {i} all agents 200")
        assert resp.status_code == 200, resp.text
        assert resp.json()["stored"] is True, resp.json()

    resp = client.get("/v1/skills/stats")
    assert resp.status_code == 200, resp.text
    assert resp.json()["fleet-health-brief"]["success"] == 3

    resp = client.post("/v1/skills/evaluate", json={})
    assert resp.status_code == 200, resp.text
    drafted = resp.json()["drafted"]
    assert len(drafted) == 1 and drafted[0]["trigger"] == "repeated_success", drafted

    resp = client.get("/v1/skills/drafts")
    drafts = resp.json()
    assert len(drafts) == 1 and drafts[0]["review_status"] == "pending_review"

    # Nothing is active until the review gate says so.
    assert client.get("/v1/skills/active").json() == []

    draft_id = drafts[0]["id"]
    # The recording agent may NOT activate its own draft.
    resp = client.post(f"/v1/skills/drafts/{draft_id}/review", json={"approve": True})
    assert resp.status_code == 403, resp.text
    assert client.get("/v1/skills/active").json() == []

    # The service identity (admin) can — acting on the owner's behalf.
    resp = client.post(
        f"/v1/skills/drafts/{draft_id}/review",
        json={"approve": True},
        headers={"X-Agent-Name": "memora"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["review_status"] == "active"
    active = client.get("/v1/skills/active").json()
    assert [s["pattern_key"] for s in active] == ["fleet-health-brief"]


def test_correction_over_http_drafts_immediately(client, test_db):
    _setup(test_db)
    resp = _outcome(
        client, "morning-brief", "corrected",
        detail="sent the brief at 09:30",
        correction="Briefs go at 08:50 IST, never 09:30.",
    )
    assert resp.json()["stored"] is True
    resp = client.post("/v1/skills/evaluate", json={})
    drafted = resp.json()["drafted"]
    assert len(drafted) == 1 and drafted[0]["trigger"] == "owner_correction"
    drafts = client.get("/v1/skills/drafts").json()
    assert "Briefs go at 08:50 IST, never 09:30." in drafts[0]["content"]


def test_invalid_outcome_is_refused_with_reason(client, test_db):
    _setup(test_db)
    resp = _outcome(client, "p", "maybe")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stored"] is False
    resp = _outcome(client, "p", "corrected")  # correction without text
    assert resp.json()["stored"] is False
    assert resp.json()["reason"] == "corrected_outcome_needs_correction_text"


def test_background_pass_drafts_but_never_activates(client, test_db):
    _setup(test_db)
    for _ in range(3):
        assert _outcome(client, "deploy-check", "success").json()["stored"]

    summary = run_evaluation_pass(test_db)
    assert summary["actors"] >= 1 and summary["drafted"] == 1, summary
    drafts = SkillLearningService.list_skill_drafts(test_db, actor_name="friday")
    assert len(drafts) == 1 and drafts[0]["review_status"] == "pending_review"
    assert SkillLearningService.active_skills(test_db, actor_name="friday") == []

    # Idempotent: no new evidence → the pass drafts nothing more.
    summary = run_evaluation_pass(test_db)
    assert summary["drafted"] == 0, summary


def test_skills_routes_are_mounted():
    from apps.api.main import app

    paths = set(app.openapi()["paths"])
    assert {
        "/v1/skills/outcomes",
        "/v1/skills/evaluate",
        "/v1/skills/stats",
        "/v1/skills/drafts",
        "/v1/skills/drafts/{draft_id}/review",
        "/v1/skills/active",
    } <= paths
