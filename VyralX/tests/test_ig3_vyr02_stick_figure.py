"""TASK-IG3-VYR-02: the stick-figure explainer style (cluster B112).

Behaviour pinned here:

* the format registry now carries ``stick_figure_explainer`` and it
  validates like every other template (in-lane, shares sum to 1.0,
  gate-screened) — the registry's own test (IG-VYR-09) has its
  expected set extended in the same PR;
* poses are real drawing data: every joint sits on the canvas and
  the primitive set is torso + 2 arms + 2 legs + head;
* scene plans are deterministic, beat-aligned to the template, and
  honest about missing captions (recorded, never padded);
* the SVG layer is self-contained and XML-well-formed, with
  captions escaped (script text is never markup);
* the module's router answers through the app pattern, and
  app.main mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the template and module do not
exist.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.services import format_templates as ft
from app.services import stick_figure as sf

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")


def test_template_registered_and_valid():
    template = ft.get_template("stick_figure_explainer")
    assert ft.validate_template(template) == []
    assert template["ig_sources"] == ["DemH26soPPx"]
    assert {b["beat"] for b in template["structure"]} == {
        "hook_pose", "setup", "build_up", "aha_pose", "recap_line"}


def test_every_pose_draws_a_full_figure_on_canvas():
    for pose in sf.POSES:
        prim = sf.figure_primitives(pose)
        cx, cy, r = prim["head"]
        assert 0 <= cx - r and cx + r <= sf.CANVAS[0]
        assert len(prim["segments"]) == 9  # torso + 2x(arm) + 2x(leg)
        for x1, y1, x2, y2 in prim["segments"]:
            for x in (x1, x2):
                assert 0 <= x <= sf.CANVAS[0]
            for y in (y1, y2):
                assert 0 <= y <= sf.CANVAS[1]
    with pytest.raises(ValueError):
        sf.figure_primitives("cartwheel")


def test_svg_is_wellformed_deterministic_and_escapes_captions():
    svg = sf.render_svg("point", 'Why <b>now</b>?')
    ET.fromstring(svg)  # raises if not well-formed
    assert "&lt;b&gt;" in svg and "<b>" not in svg
    assert svg == sf.render_svg("point", 'Why <b>now</b>?')
    assert sf.render_svg("point") != svg  # caption changes output


def test_build_scenes_aligns_beats_poses_and_timings():
    plan = sf.build_scenes(["Why?", "Setup.", "Build.", "Aha!",
                            "Recap."], target_seconds=50.0)
    assert plan["status"] == "pending_review"
    assert plan["publish"] is False
    assert plan["missing_captions"] == []
    scenes = plan["scenes"]
    assert [s["pose"] for s in scenes] == [
        "point", "stand", "present", "celebrate", "think"]
    assert scenes[0]["start"] == 0.0 and scenes[-1]["end"] == 50.0
    for a, b in zip(scenes, scenes[1:]):
        assert a["end"] == b["start"]
    for s in scenes:
        ET.fromstring(s["svg"])


def test_missing_captions_recorded_never_padded():
    plan = sf.build_scenes(["Only the hook."], target_seconds=40.0)
    assert plan["missing_captions"] == [
        "setup", "build_up", "aha_pose", "recap_line"]
    assert plan["scenes"][1]["caption"] == ""
    with pytest.raises(ValueError):
        sf.build_scenes(["a"] * 6, target_seconds=40.0)
    with pytest.raises(ValueError):
        sf.build_scenes(["a"], target_seconds=40.0, lane="sports_news")


def test_enqueue_writes_one_review_record(tmp_path):
    plan = sf.build_scenes(["Why?", "S.", "B.", "A!", "R."],
                           target_seconds=45.0)
    queue = tmp_path / "queue.jsonl"
    assert sf.enqueue_scene_plan(plan, queue) == 1
    import json
    rows = [json.loads(l) for l in
            queue.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "stick_figure_scene_plan"
    assert rows[0]["status"] == "pending_review"
    assert rows[0]["publish"] is False


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(sf.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/stick-figure/poses")
    assert res.status_code == 200
    assert "celebrate" in res.json()["poses"]

    res = client.post("/api/v1/stick-figure/scenes",
                      json={"captions": ["Why?", "S.", "B.", "A!", "R."],
                            "target_seconds": 45.0, "lane": "tech_ai"})
    assert res.status_code == 200
    assert len(res.json()["scenes"]) == 5

    res = client.post("/api/v1/stick-figure/scenes",
                      json={"captions": ["a"] * 6})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.stick_figure import router as " \
        "stick_figure_router" in main_src
    assert "app.include_router(stick_figure_router" in main_src
