"""TASK-IG3-VYR-09: the single production-rules folder
(cluster B131, IG sources DeyusrQMOmi + DdlIP2YAqsq).

Behaviour pinned here:

* the folder exists as ONE data artifact holding the five
  source rules, each with statement, source and an
  enforcement pointer — not scattered code;
* the checker measures a plan against every rule and
  reports the measured numbers per rule;
* a compliant plan passes all five; breaking any single
  rule fails exactly that rule's verdict;
* the frame-review verdict is honest about its basis: it
  checks the plan's declaration, it does not witness a
  render;
* the router answers through the app pattern and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: neither the folder nor the
module exists.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import production_rules as pr

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

_RULE_IDS = ["hook_first_second", "visuals_timed_to_voice",
             "pictures_land_on_words", "motion_until_last_frame",
             "frame_review_60fps"]


def _plan(**overrides):
    plan = {
        "duration_s": 12.0,
        "hook": {"text": "Thirty-five million views in twenty "
                         "days — here is the folder behind it",
                 "at": 0.0},
        "timed_words": [
            {"word": "thirty-five", "start": 0.12, "end": 0.6},
            {"word": "million", "start": 0.69, "end": 1.1},
            {"word": "views", "start": 1.3, "end": 1.7},
        ],
        "visuals": [
            {"visual_id": "v1", "at": 0.75, "end": 4.0,
             "word": "million"},
            {"visual_id": "v2", "at": 1.35, "end": 12.0,
             "word": "views"},
        ],
        "frame_review": {"fps": 60, "completed": True},
    }
    plan.update(overrides)
    return plan


def test_folder_holds_the_five_source_rules_as_one_artifact():
    folder = pr.load_rules()
    assert [r["id"] for r in folder["rules"]] == _RULE_IDS
    for rule in folder["rules"]:
        assert rule["statement"]
        assert rule["source"]
        assert "production_rules" in rule["enforcement"] or \
            "format_clone" in rule["enforcement"]
    landing = next(r for r in folder["rules"]
                   if r["id"] == "pictures_land_on_words")
    assert landing["threshold"]["max_landing_error_s"] == 0.25
    assert "DdlIP2YAqsq" in landing["source"]


def test_a_compliant_plan_passes_every_rule():
    result = pr.check_plan(_plan())
    assert result["passed"] is True
    assert [v["rule_id"] for v in result["verdicts"]] == _RULE_IDS
    assert all(v["passed"] for v in result["verdicts"])
    assert result["status"] == "pending_review"
    assert result["publish"] is False


def test_each_rule_fails_on_its_own_evidence():
    def verdict(plan, rule_id):
        return next(v for v in pr.check_plan(plan)["verdicts"]
                    if v["rule_id"] == rule_id)

    late_hook = _plan(hook={"text": "a hook", "at": 2.5})
    v = verdict(late_hook, "hook_first_second")
    assert v["passed"] is False
    assert v["measured"]["hook_at_s"] == 2.5

    unanchored = _plan(visuals=[{"visual_id": "v1", "end": 12.0,
                                 "word": "views"}])
    v = verdict(unanchored, "visuals_timed_to_voice")
    assert v["passed"] is False
    assert v["measured"]["unanchored"] == ["v1"]

    off_word = _plan(visuals=[
        {"visual_id": "v1", "at": 3.0, "end": 12.0,
         "word": "million"}])
    v = verdict(off_word, "pictures_land_on_words")
    assert v["passed"] is False
    assert v["measured"]["landings"][0]["error_s"] == 2.31

    dead_tail = _plan(visuals=[
        {"visual_id": "v1", "at": 0.75, "end": 5.0,
         "word": "million"}])
    v = verdict(dead_tail, "motion_until_last_frame")
    assert v["passed"] is False
    assert v["measured"]["tail_gap_s"] == 7.0

    no_review = _plan(frame_review={"fps": 30,
                                    "completed": True})
    v = verdict(no_review, "frame_review_60fps")
    assert v["passed"] is False
    assert "does not witness" in v["basis"]


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(pr.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/production-rules/policy")
    assert res.status_code == 200
    assert res.json()["rule_count"] == 5
    assert res.json()["publish"] is False

    res = client.get("/api/v1/production-rules")
    assert res.status_code == 200
    assert [r["id"] for r in res.json()["rules"]] == _RULE_IDS

    res = client.post("/api/v1/production-rules/check",
                      json={"plan": _plan()})
    assert res.status_code == 200
    assert res.json()["passed"] is True

    res = client.post("/api/v1/production-rules/check",
                      json={"plan": {"duration_s": 0}})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.production_rules import router as " \
        "production_rules_router" in main_src
    assert "app.include_router(production_rules_router" in main_src
