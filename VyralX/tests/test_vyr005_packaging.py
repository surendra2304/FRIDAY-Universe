"""TASK-VYR-005 — packaging system tests.

The packaging module is the remix era's replacement for the autopilot
formula documented in docs/AUTOPSY_29_UNLISTED.md (one interchangeable
sensational title + emoji + "#Shorts" for all 46 videos, no lane, no
hook framework, no gate before upload). These tests pin:

* lane title templates render and pass their own lint;
* the old era's patterns fail (source-framing carry-over, emoji spam,
  over-length, finance-advice language in the money-stories lane);
* hook framework: a hook must fit the first seconds and carry a
  curiosity device;
* the pre-publish checklist composes the TASK-VYR-003 sync gates and
  the TASK-VYR-004 provenance/compliance gates — a candidate packaged
  the old way (blanket "operator policy" licence string, no sync
  measurements, no commentary record) is NOT publishable, and every
  missing measurement fails its gate instead of being skipped.
"""
from __future__ import annotations

from app.services.packaging import (
    build_hook,
    lint_thumbnail_text,
    lint_title,
    prepublish_checklist,
    render_title,
    score_hook,
)

GOOD_SCRIPT = " ".join(["word"] * 60)


def _good_candidate() -> dict:
    return {
        "lane": "space_science",
        "title": render_title("space_science", 0, object="Black Hole",
                              comparison="100 Suns"),
        "thumbnail_text": "BIGGER THAN 100 SUNS",
        "hook_line": build_hook("space_science", "scale_shock",
                                object="the largest black hole",
                                scale_fact="4 million suns in one point"),
        "duration_s": 45,
        "claimed_material_possible": False,
        "sync": {  # TASK-VYR-003 proof-render measurements
            "beat_max_error_s": 0.0,
            "caption_mean_abs_offset_s": 0.025,
            "caption_max_abs_offset_s": 0.413,
            "narration_coverage": 1.0,
        },
        "provenance": {
            "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
            "author": "NASA",
            "license": "Public domain",
            "retrieved_on": "2026-11-15",
        },
        "commentary": {"script": GOOD_SCRIPT, "voiceover_present": True},
    }


def test_lane_title_templates_render_and_pass():
    for lane, idx, slots in [
        ("space_science", 2, {"number": "5", "object": "Io", "seconds": "30"}),
        ("history_dyk", 0, {"event": "Library Fire"}),
        ("tech_ai", 0, {"capability": "Fold a Protein"}),
        ("money_stories", 0, {"amount": "$2 Billion", "duration": "One Week"}),
    ]:
        title = render_title(lane, idx, **slots)
        result = lint_title(title, lane)
        assert result["ok"], (lane, title, result["issues"])


def test_old_era_titles_fail():
    # Source-framing carry-over used by all 46 autopilot projects.
    r = lint_title("Repurposed: How Zach King Gets Away With It", "space_science")
    assert not r["ok"] and any("repurposed" in i for i in r["issues"])
    # Emoji spam + over-length, the old formula's shape.
    r = lint_title("Crazy Creamy Egg Toast Shocked My Taste Buds Forever And Ever 😱🔥🤯😱 #Shorts",
                   "space_science")
    assert not r["ok"]
    # Anchor-free filler title: no number, no question, no named subject.
    r = lint_title("it gets even crazier later", "history_dyk")
    assert not r["ok"] and any("anchor" in i for i in r["issues"])


def test_money_stories_advice_language_is_a_hard_fail():
    r = lint_title("This Coin Will Make You Rich — Buy Now", "money_stories")
    assert not r["ok"]
    assert any("money_stories" in i for i in r["issues"])


def test_thumbnail_text_rules():
    assert lint_thumbnail_text("BIGGER THAN 100 SUNS")["ok"]
    assert not lint_thumbnail_text("THIS IS A VERY LONG SENTENCE INDEED")["ok"]
    assert not lint_thumbnail_text("This Black Hole", "This Black Hole Is Bigger Than 100 Suns")["ok"]


def test_hook_framework():
    hook = build_hook("history_dyk", "buried_fact", fact="the Taj Mahal was almost demolished")
    s = score_hook(hook)
    assert s["ok"], s
    long_hook = " ".join(["filler"] * 20)
    assert not score_hook(long_hook)["ok"]
    flat = score_hook("The video shows a large nebula today")
    assert not flat["ok"] and not flat["devices"]


def test_checklist_good_candidate_is_publishable():
    result = prepublish_checklist(_good_candidate())
    assert result["publishable"], [g for g in result["gates"] if not g["ok"]]


def test_checklist_old_era_candidate_is_not_publishable():
    candidate = _good_candidate()
    # Exactly how the 46 autopilot videos were recorded (probe evidence):
    candidate["provenance"] = {
        "source_url": "https://www.youtube.com/watch?v=example",
        "author": "",
        "license": "Transformative commentary - original creator credited (operator policy)",
        "retrieved_on": "",
    }
    candidate["sync"] = {}          # VIDEO_METRICS was empty: nothing measured
    candidate["commentary"] = {"script": "", "voiceover_present": False}
    result = prepublish_checklist(candidate)
    assert not result["publishable"]
    failed = {g["gate"] for g in result["gates"] if not g["ok"]}
    assert "license_allowed" in failed
    assert "provenance_record_complete" in failed
    assert "sync_beats_retimed" in failed
    assert "original_commentary_present" in failed


def test_checklist_claimed_material_over_60s_blocked():
    candidate = _good_candidate()
    candidate["claimed_material_possible"] = True
    candidate["duration_s"] = 75
    result = prepublish_checklist(candidate)
    assert not result["publishable"]
    assert any(g["gate"] == "duration_under_claim_block" and not g["ok"] for g in result["gates"])


def test_checklist_sync_regression_fails():
    candidate = _good_candidate()
    candidate["sync"]["narration_coverage"] = 0.736  # the broken VYR-003-era value
    result = prepublish_checklist(candidate)
    assert not result["publishable"]
    assert any(g["gate"] == "sync_narration_coverage" and not g["ok"] for g in result["gates"])
