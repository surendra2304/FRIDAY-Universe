"""TASK-IG3-VYR-07: motion-template library + slot editor
(cluster B114, IG source DekQYGzTTgb — the animos.app pattern).

Behaviour pinned here:

* the catalogue holds exactly the twelve template names the
  source video showed on screen — and the tool's "50+" is
  recorded as a labelled claim, never as catalogue fact;
* filling a template validates the recovered editor rules:
  media slots need at least one item, a logo must carry its
  size and stay under the 5 MB cap, loop duration stays in
  the 5s-30s TIMING range;
* the export spec validates against the recovered matrix
  (MP4-H.264 / WebM-VP9; 720p-8K; 30/60 fps; loops 1-4) and
  stamps every render off-fleet;
* the filled plan rides the existing motion_graphics HTML
  artifact, which states its off-fleet nature on its face;
* the router answers through the app pattern and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the module does not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import motion_templates as mt

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

_SOURCE_NAMES = [
    "Card Globe", "Orbit Globe", "Triple Scene", "Spiral Stream",
    "Cover Ring", "Collage Reel", "Fan Shuffle", "Sweep Ring",
    "Scatter Zoom", "Sphere Wall", "Totem Wall", "Card Tunnel",
]


def test_library_catalogues_exactly_the_source_named_templates():
    library = mt.list_templates()
    assert [t["name"] for t in library["templates"]] == _SOURCE_NAMES
    assert library["catalogued_count"] == 12
    # The "50+" is the tool's claim, labelled as one.
    assert library["claimed_template_count"] == "50+"
    assert "not" in library["claim_basis"]
    for template in library["templates"]:
        assert template["slot_kinds"] == ["media", "text", "logo"]
        assert template["loop_seconds"]["min"] == 5.0
        assert template["loop_seconds"]["max"] == 30.0


def test_fill_template_builds_a_plan_from_the_slots():
    plan = mt.fill_template(
        "card_globe", media=["design-a.png", "design-b.png"],
        text="Spring Collection",
        logo={"locator": "logo.png", "size_bytes": 1_200_000},
        loop_seconds=12.0)
    assert plan["template_name"] == "Card Globe"
    assert plan["media_slots_filled"] == 2
    assert plan["loop_seconds"] == 12.0
    kinds = [e["kind"] for e in plan["elements"]]
    assert kinds == ["media", "media", "title_card", "logo"]
    assert plan["export"]["render_host"] == "off_fleet"
    assert plan["status"] == "pending_review"
    assert plan["publish"] is False


def test_fill_template_enforces_the_recovered_editor_rules():
    with pytest.raises(ValueError, match="unknown template"):
        mt.fill_template("not_a_template", media=["a.png"])
    with pytest.raises(ValueError, match="at least one media"):
        mt.fill_template("card_globe", media=[])
    with pytest.raises(ValueError, match="size_bytes"):
        mt.fill_template("card_globe", media=["a.png"],
                         logo={"locator": "logo.png"})
    with pytest.raises(ValueError, match="cap"):
        mt.fill_template("card_globe", media=["a.png"],
                         logo={"locator": "logo.png",
                               "size_bytes": 5_000_001})
    # Exactly at the cap is allowed — the cap is a maximum.
    mt.fill_template("card_globe", media=["a.png"],
                     logo={"locator": "logo.png",
                           "size_bytes": 5_000_000})
    with pytest.raises(ValueError, match="TIMING range"):
        mt.fill_template("card_globe", media=["a.png"],
                         loop_seconds=4.0)
    with pytest.raises(ValueError, match="TIMING range"):
        mt.fill_template("card_globe", media=["a.png"],
                         loop_seconds=31.0)


def test_export_spec_validates_the_recovered_matrix():
    spec = mt.export_spec(fmt="webm_vp9", resolution="4k",
                          fps=60, loops=4)
    assert spec["format"] == "webm_vp9"
    assert spec["resolution"] == "4k"
    assert spec["render_host"] == "off_fleet"
    assert "4K" in spec["note"]
    assert mt.export_spec()["resolution"] == "1080p"
    with pytest.raises(ValueError):
        mt.export_spec(fmt="avi")
    with pytest.raises(ValueError):
        mt.export_spec(resolution="480p")
    with pytest.raises(ValueError):
        mt.export_spec(fps=24)
    with pytest.raises(ValueError):
        mt.export_spec(loops=5)


def test_filled_plan_rides_the_existing_html_artifact():
    plan = mt.fill_template("orbit_globe", media=["shot.png"],
                            text="Orbit")
    artifact = mt.composition_artifact(plan)
    assert "OFF-FLEET RENDER ARTIFACT" in artifact
    assert "Orbit Globe" in artifact


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(mt.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/motion-templates/policy")
    assert res.status_code == 200
    assert res.json()["publish"] is False
    assert res.json()["catalogued_count"] == 12

    res = client.get("/api/v1/motion-templates/library")
    assert res.status_code == 200
    assert res.json()["catalogued_count"] == 12

    res = client.post("/api/v1/motion-templates/fill", json={
        "template_id": "triple_scene",
        "media": ["a.png", "b.png", "c.png"]})
    assert res.status_code == 200
    assert res.json()["media_slots_filled"] == 3

    res = client.post("/api/v1/motion-templates/fill", json={
        "template_id": "triple_scene", "media": ["a.png"],
        "loop_seconds": 45.0})
    assert res.status_code == 422

    res = client.post("/api/v1/motion-templates/export-spec",
                      json={"format": "webm_vp9",
                            "resolution": "8k", "fps": 60,
                            "loops": 2})
    assert res.status_code == 200
    assert res.json()["resolution"] == "8k"

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.motion_templates import router as " \
        "motion_templates_router" in main_src
    assert "app.include_router(motion_templates_router" in main_src
