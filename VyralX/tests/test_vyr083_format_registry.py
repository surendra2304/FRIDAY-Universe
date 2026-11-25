"""TASK-VYR-083: format-template registry additions.

Behaviour pinned here:

* the three board-named formats register and validate clean:
  build-in-public Day-1 series (vyralx package V-02, item
  Dag2UFvTD2C), AI 3D cartoon comedy short (watch Df17y3toZBu),
  trail-transition technique (watch DfHutKDSsEM);
* each instantiates to contiguous beats ending exactly at the
  target duration, inside its target range;
* the Day-1 template carries the standing pilot rules (short
  excerpts only, English narration, subtitles always on, BGM,
  unlisted review-first);
* the comedy short mandates original characters only;
* the trail transition never obscures narration or subtitles, and
  its trail is generated in the edit, never copied.

On clean main every test fails: the three templates do not exist.
"""
from __future__ import annotations

from app.services import format_templates as ft

NEW_TEMPLATES = {
    "build_in_public_day1": {
        "ig": "Dag2UFvTD2C",
        "lanes": {"tech_ai"},
        "range": (30, 60),
    },
    "ai_3d_cartoon_comedy_short": {
        "ig": "Df17y3toZBu",
        "lanes": {"tech_ai", "space_science", "history"},
        "range": (30, 60),
    },
    "trail_transition_technique": {
        "ig": "DfHutKDSsEM",
        "lanes": {"space_science", "history", "tech_ai"},
        "range": (5, 15),
    },
}


def test_new_templates_register_and_validate():
    templates = ft.load_templates()
    assert len(templates) == 11
    for tid, spec in NEW_TEMPLATES.items():
        t = ft.get_template(tid)
        assert ft.validate_template(t) == []
        assert set(t["lanes"]) == spec["lanes"]
        assert list(t["target_seconds"]) == list(spec["range"])
        assert spec["ig"] in t.get("ig_sources", [])


def test_new_templates_instantiate_contiguous():
    for tid, spec in NEW_TEMPLATES.items():
        lo, hi = spec["range"]
        mid = (lo + hi) / 2.0
        plan = ft.instantiate(tid, mid)
        beats = plan["beats"]
        assert beats[0]["start"] == 0.0
        assert beats[-1]["end"] == mid
        for a, b in zip(beats, beats[1:]):
            assert a["end"] == b["start"]
        assert plan["within_template_range"] is True
        assert plan["status"] == "pending_review"


def test_day1_carries_standing_pilot_rules():
    t = ft.get_template("build_in_public_day1")
    rules = " ".join(t["hard_rules"]).casefold()
    assert "short excerpts only" in rules
    assert "english narration" in rules
    assert "subtitles always on" in rules
    assert "bgm" in rules
    assert "unlisted review-first" in rules


def test_comedy_short_mandates_original_characters():
    t = ft.get_template("ai_3d_cartoon_comedy_short")
    rules = " ".join(t["hard_rules"]).casefold()
    assert "original" in rules
    assert "third-party characters" in rules


def test_trail_transition_never_obscures_narration():
    t = ft.get_template("trail_transition_technique")
    rules = " ".join(t["hard_rules"]).casefold()
    assert "never obscure narration or subtitles" in rules
    assert "generated in the edit" in rules
