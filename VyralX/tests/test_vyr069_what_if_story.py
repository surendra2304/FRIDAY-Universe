"""TASK-VYR-069: what-if narrated-story template usable for episode series.

Behaviour pinned here:

* the registry now carries ``what_if_narrated_story`` and it validates
  like every other template (in-lane, shares sum to 1.0, gate-screened,
  target range [60, 120]) — the acceptance shape: one counterfactual
  premise, single narrator, chaptered escalation, cliffhanger ending,
  episode series;
* a malformed what-if-shaped template is rejected by
  ``validate_template`` (shares that do not sum to 1.0; a
  gate-excluded token in the name);
* ``what_if.build_episode`` plans one episode against the template:
  the premise + three chapter texts + cliffhanger align with the
  template beats with contiguous timings, the cliffhanger is carried
  as the next episode's hook, and the plan is pending_review and
  publishes nothing; missing chapters are recorded, never padded;
* the acceptance guards are enforced: a second premise, a second
  narrator, a missing cliffhanger, too many chapters, a non-positive
  episode number, or a lane the template does not serve are refused;
* the series automation plans episodes against the template
  (``validate_series`` accepts the id; ``plan_episodes`` carries the
  instantiated format plan at the [60, 120] midpoint, outline follows
  the template beats);
* the module's router answers through the app pattern, and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the template and module do not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import format_templates as ft
from app.services import remix_flow as rf
from app.services import series_automation as sa
from app.services import what_if as wi

TEMPLATE_ID = "what_if_narrated_story"
EXPECTED_BEATS = ["premise", "chapter_one", "chapter_two",
                  "chapter_three", "cliffhanger"]

SERIES = {
    "series_id": "what-if-machine-minds",
    "lane": "tech_ai",
    "format_name": "series_episode",
    "cadence_days": 2,
    "episodes_planned": 3,
    "start_date": "2026-11-25",
    "topic_seeds": ["what if the first computer had been built "
                    "a century earlier",
                    "what if the internet had stayed a lab network",
                    "what if phones had never learned to talk back"],
}

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

PREMISE = "What if the first computer had been built a century earlier?"
CHAPTERS = ["Babbage's engine works, and the telegraph age gets "
            "programmable machines.",
            "Counting houses become compute houses; every ledger "
            "is a program.",
            "The century turns on a different hinge — and the "
            "analytical engine stops answering."]
CLIFFHANGER = "In the engine room, one gear is turning backwards."


def test_template_registered_and_valid():
    template = ft.get_template(TEMPLATE_ID)
    assert ft.validate_template(template) == []
    assert template["name"] == "What-if narrated story"
    assert template["lanes"] == ["space_science", "history", "tech_ai"]
    assert [b["beat"] for b in template["structure"]] == EXPECTED_BEATS
    assert abs(sum(b["share"] for b in template["structure"]) - 1.0) < 0.011
    assert template["target_seconds"] == [60, 120]
    rules = " ".join(template["hard_rules"])
    assert "one counterfactual premise" in rules
    assert "single narrator" in rules
    assert "cliffhanger" in rules
    assert "ORIGINAL" in rules


def test_registry_expected_set_includes_what_if():
    templates = ft.load_templates()
    ids = {t["id"] for t in templates}
    assert TEMPLATE_ID in ids
    # TASK-VYR-083 grew the registry 8 -> 11; the set is pinned exactly
    # (same set as EXPECTED_TEMPLATES in test_ig_vyr09_format_tooling.py)
    # so the next registry addition fails here loudly, not silently.
    assert ids == {
        "cinematic_short",
        "original_character_series",
        "animated_explainer",
        "character_explainer",
        "flyover_segment",
        "ambient_longform",
        "stick_figure_explainer",
        "what_if_narrated_story",
        "build_in_public_day1",
        "ai_3d_cartoon_comedy_short",
        "trail_transition_technique",
    }


def test_malformed_template_rejected():
    template = ft.get_template(TEMPLATE_ID)
    bad_shares = {**template}
    bad_shares["structure"] = [
        {**b, "share": 0.10} for b in template["structure"]]
    problems = ft.validate_template(bad_shares)
    # Registry message (format_templates.validate_template): "structure
    # shares must sum to 1.0 (got 0.5)" — the word "must" is in it.
    assert any("shares must sum to" in p for p in problems)
    bad_gate = {**template, "name": "What-if movie night"}
    problems = ft.validate_template(bad_gate)
    assert any("gate-excluded token" in p for p in problems)


def test_build_episode_happy_path():
    plan = wi.build_episode(PREMISE, CHAPTERS, CLIFFHANGER,
                            episode_no=2, series_id="what-if-machine-minds",
                            narrator="Mara", target_seconds=90.0,
                            lane="tech_ai")
    assert plan["kind"] == "what_if_episode_plan"
    assert plan["version"] == wi.WHAT_IF_VERSION
    assert plan["template_id"] == TEMPLATE_ID
    assert plan["premise"] == PREMISE
    assert plan["narrator"] == "Mara"
    assert plan["episode_no"] == 2
    assert plan["series_id"] == "what-if-machine-minds"
    assert plan["within_template_range"] is True
    assert plan["missing_chapters"] == []
    assert plan["cliffhanger"] == CLIFFHANGER
    assert plan["next_episode_hook"] == (
        "Episode 3 opens by resolving: " + CLIFFHANGER)
    assert plan["status"] == "pending_review"
    assert plan["publish"] is False
    # Timings are contiguous across the whole episode: premise ->
    # chapters -> cliffhanger, spanning exactly the target length.
    assert plan["premise_beat"]["start"] == 0.0
    assert plan["premise_beat"]["end"] == plan["chapters"][0]["start"]
    for a, b in zip(plan["chapters"], plan["chapters"][1:]):
        assert a["end"] == b["start"]
    assert plan["chapters"][-1]["end"] == \
        plan["cliffhanger_beat"]["start"]
    assert plan["cliffhanger_beat"]["end"] == 90.0
    assert [c["beat"] for c in plan["chapters"]] == list(
        wi.CHAPTER_BEATS)
    assert [c["text"] for c in plan["chapters"]] == CHAPTERS


def test_build_episode_records_missing_chapters():
    plan = wi.build_episode(PREMISE, CHAPTERS[:1], CLIFFHANGER,
                            target_seconds=60.0)
    assert plan["missing_chapters"] == ["chapter_two", "chapter_three"]
    assert plan["chapters"][1]["text"] == ""
    assert plan["chapters"][2]["text"] == ""
    assert plan["within_template_range"] is True


def test_build_episode_rejects_bad_input():
    with pytest.raises(ValueError):
        wi.build_episode([PREMISE, "What if the Moon never formed?"],
                         CHAPTERS, CLIFFHANGER)
    with pytest.raises(ValueError):
        wi.build_episode(PREMISE, CHAPTERS, CLIFFHANGER,
                         narrator=["Mara", "Dev"])
    with pytest.raises(ValueError):
        wi.build_episode("   ", CHAPTERS, CLIFFHANGER)
    with pytest.raises(ValueError):
        wi.build_episode(PREMISE, CHAPTERS, "")
    with pytest.raises(ValueError):
        wi.build_episode(PREMISE, CHAPTERS + ["One chapter too many."],
                         CLIFFHANGER)
    with pytest.raises(ValueError):
        wi.build_episode(PREMISE, CHAPTERS, CLIFFHANGER,
                         lane="sports_news")
    with pytest.raises(ValueError):
        wi.build_episode(PREMISE, CHAPTERS, CLIFFHANGER, episode_no=0)


def test_enqueue_writes_one_review_record(tmp_path):
    plan = wi.build_episode(PREMISE, CHAPTERS, CLIFFHANGER,
                            series_id="what-if-machine-minds",
                            target_seconds=90.0)
    queue = tmp_path / "queue.jsonl"
    assert wi.enqueue_episode_plan(plan, queue) == 1
    import json
    rows = [json.loads(line) for line in
            queue.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "what_if_episode_plan"
    assert rows[0]["status"] == "pending_review"
    assert rows[0]["publish"] is False


def test_validate_accepts_what_if_template():
    spec = {**SERIES, "template_id": TEMPLATE_ID}
    out = sa.validate_series(spec)
    assert out["ok"] is True
    assert out["template"]["id"] == TEMPLATE_ID
    assert out["screened_seeds"] == SERIES["topic_seeds"]


def test_validate_rejects_template_lane_mismatch():
    # ambient_longform serves space_science only; this series is tech_ai.
    spec = {**SERIES, "lane": "tech_ai",
            "template_id": "ambient_longform"}
    out = sa.validate_series(spec)
    assert out["ok"] is False
    assert out["template"] is None
    assert any("does not serve lane" in p for p in out["problems"])


def test_plan_briefs_carry_template_plan():
    spec = {k: v for k, v in SERIES.items() if k != "format_name"}
    spec["template_id"] = TEMPLATE_ID
    plan = sa.plan_episodes(spec)
    assert len(plan["briefs"]) == 3
    for brief in plan["briefs"]:
        assert brief["template_id"] == TEMPLATE_ID
        assert brief["format_name"] == "What-if narrated story"
        assert brief["status"] == "pending_review"
        assert brief["publish"] is False
        fmt = brief["format_plan"]
        assert fmt["template_id"] == TEMPLATE_ID
        assert fmt["registry_version"] == ft.REGISTRY_VERSION
        assert fmt["target_seconds"] == 90.0  # midpoint of [60, 120]
        assert fmt["within_template_range"] is True
        assert fmt["status"] == "pending_review"
        beats = fmt["beats"]
        assert [b["beat"] for b in beats] == EXPECTED_BEATS
        assert beats[0]["start"] == 0.0
        assert beats[-1]["end"] == 90.0
        for a, b in zip(beats, beats[1:]):
            assert a["end"] == b["start"]
        assert any("one counterfactual premise" in r
                   for r in fmt["hard_rules"])
        assert [o.split(":")[0] for o in brief["outline"]] == EXPECTED_BEATS


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(wi.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/what-if/beats")
    assert res.status_code == 200
    assert [b["beat"] for b in res.json()["beats"]] == EXPECTED_BEATS

    res = client.post("/api/v1/what-if/episodes",
                      json={"premise": PREMISE, "chapters": CHAPTERS,
                            "cliffhanger": CLIFFHANGER,
                            "episode_no": 1,
                            "series_id": "what-if-machine-minds",
                            "target_seconds": 90.0, "lane": "tech_ai"})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "what_if_episode_plan"
    assert len(body["chapters"]) == 3
    assert body["next_episode_hook"].startswith("Episode 2 opens")

    res = client.post("/api/v1/what-if/episodes",
                      json={"premise": PREMISE, "chapters": CHAPTERS,
                            "cliffhanger": ""})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.what_if import router as " \
        "what_if_router" in main_src
    assert "app.include_router(what_if_router" in main_src
