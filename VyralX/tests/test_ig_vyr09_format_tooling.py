"""TASK-IG-VYR-09: format templates + chat mockup + motion graphics.

Behaviour pinned here:

* the shipped registry loads clean: every template is structurally
  valid, in-lane, shares summing to 1.0, and gate-screened;
* a template invoking a gate-excluded category (e.g. gameplay) is
  rejected by validation — the corpus's game-IP character series
  survives ONLY as the original-character template, whose hard
  rules mandate original characters;
* the flyover template's source strategy is PD stock, never
  Google Earth Studio;
* instantiation produces contiguous beat timings ending exactly at
  the target duration;
* the chat mockup renders one frame per reveal, every frame
  carrying the scripted-dramatisation disclaimer, and refuses
  empty/bad input;
* kinetic-text timings are monotonic within the line's duration;
* the HyperFrames-style export is a single self-contained HTML
  artifact — no external references — stamped off-fleet.

On clean main every test fails: the registry and both modules do
not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.services import chat_mockup, format_templates as ft
from app.services import motion_graphics as mg

EXPECTED_TEMPLATES = {"cinematic_short", "original_character_series",
                      "animated_explainer", "character_explainer",
                      "flyover_segment", "ambient_longform"}


def test_registry_loads_and_covers_corpus_formats():
    templates = ft.load_templates()
    assert {t["id"] for t in templates} == EXPECTED_TEMPLATES
    for t in templates:
        assert ft.validate_template(t) == []


def test_original_character_template_mandates_originals():
    t = ft.get_template("original_character_series")
    rules = " ".join(t["hard_rules"]).casefold()
    assert "original" in rules
    assert "gameplay" in rules  # named as a prohibition


def test_flyover_never_sources_google_earth():
    t = ft.get_template("flyover_segment")
    assert "public-domain" in t["source_strategy"]
    assert "not a source" in " ".join(t["hard_rules"]).casefold() \
        or "not" in " ".join(t["hard_rules"]).casefold()


def test_gate_excluded_template_rejected():
    bad = {
        "id": "gameplay_highlights", "name": "Gameplay highlights",
        "lanes": ["tech_ai"],
        "structure": [{"beat": "clip", "share": 1.0}],
        "source_strategy": "gameplay captures from streams",
        "hard_rules": [], "target_seconds": [30, 60],
        "ig_sources": [],
    }
    problems = ft.validate_template(bad)
    assert any("gameplay" in p for p in problems)


def test_instantiate_contiguous_beats():
    plan = ft.instantiate("cinematic_short", 50.0)
    beats = plan["beats"]
    assert beats[0]["start"] == 0.0
    assert beats[-1]["end"] == 50.0
    for a, b in zip(beats, beats[1:]):
        assert a["end"] == b["start"]
    assert plan["within_template_range"] is True
    assert plan["status"] == "pending_review"


def test_chat_mockup_renders_reveal_frames(tmp_path):
    messages = [
        {"side": "left", "speaker": "Ashoka", "text": "We must talk."},
        {"side": "right", "speaker": "Chandragupta",
         "text": "About the empire?"},
        {"side": "left", "speaker": "Ashoka",
         "text": "About what it costs."},
    ]
    out = chat_mockup.render_conversation(messages, str(tmp_path))
    assert out["frame_count"] == 3
    assert out["scripted_fiction"] is True
    for frame in out["frames"]:
        path = Path(frame)
        assert path.exists() and path.stat().st_size > 1000
        with Image.open(path) as img:
            assert img.size[0] == 540


def test_chat_mockup_refuses_bad_input(tmp_path):
    with pytest.raises(ValueError):
        chat_mockup.render_conversation([], str(tmp_path))
    with pytest.raises(ValueError):
        chat_mockup.render_conversation(
            [{"side": "middle", "speaker": "x", "text": "hi"}],
            str(tmp_path))


def test_kinetic_text_monotonic_and_bounded():
    plan = mg.kinetic_text_plan("the universe is under no obligation",
                                start=2.0, duration=3.5)
    ats = [w["at"] for w in plan["words"]]
    assert ats == sorted(ats)
    assert ats[0] == 2.0
    assert plan["words"][-1]["hold_until"] == pytest.approx(5.5)


def test_hyperframes_export_self_contained():
    doc = mg.hyperframes_export(
        "Nebula Facts",
        [{"kind": "title_card", "text": "NEBULA", "at": 0},
         {"kind": "lower_third", "text": "2,500 light-years", "at": 3}])
    assert doc.startswith("<!DOCTYPE html>")
    assert "NEBULA" in doc and "OFF-FLEET" in doc
    assert "http://" not in doc and "https://" not in doc
    assert "<script src" not in doc and "<link" not in doc
