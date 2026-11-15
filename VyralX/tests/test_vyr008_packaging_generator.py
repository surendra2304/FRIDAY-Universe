"""TASK-VYR-008 — packaging generator + research scorer tests.

The generator is the companion to TASK-VYR-005's packaging rules: VYR-005
owns the hard gates, this module proposes 3 variants per video and ranks
them by research priors (docs/PACKAGING_RESEARCH.md). These tests pin:

* exactly 3 variants, one per strategy, deterministically ranked;
* the research scoring rewards what the studies reward (short anchored
  titles, 1-2 emoji, <=3-word thumbnail text, in-media-res hooks) and
  penalises the autopilot era's patterns;
* hard gates still bite inside the generator (advice language in the
  money lane, over-length titles, thumbnail repeating the title);
* the generator never invents facts: missing required slots = an honest
  failure, missing optional slots = an ungenerated variant scoring 0.
"""
from __future__ import annotations

from app.services.packaging_generator import (
    classify_hook,
    generate_variants,
    score_hook,
    score_thumbnail_text,
    score_title,
)

SPACE_VIDEO = {
    "lane": "space_science",
    "subject": "Venus",
    "fact_title": "A Day on Venus Is Longer Than Its Year",
    "hook_fact": "On Venus, one day outlasts a whole year.",
    "thumb_shout": "LONGER THAN A YEAR",
    "question": "Why Does Venus Spin Backwards?",
    "gap_hook": "Venus spins the wrong way. Nobody knows why.",
    "thumb_gap": "SPINNING BACKWARDS",
    "story_title": "Venus: The Planet That Broke Every Rule",
    "story_hook": "Every planet spins one way. Venus refused.",
    "thumb_story": "IT REFUSED",
}


def test_three_variants_one_per_strategy_ranked():
    out = generate_variants(SPACE_VIDEO)
    assert out["ok"] is True
    assert len(out["variants"]) == 3
    assert {v["strategy"] for v in out["variants"]} == {
        "fact_first", "curiosity_gap", "scale_or_story"}
    scores = [v["score"] for v in out["variants"]]
    assert scores == sorted(scores, reverse=True)
    assert out["recommended"] == out["variants"][0]["strategy"]
    # Deterministic: same input, same output.
    assert generate_variants(SPACE_VIDEO) == out


def test_good_title_beats_autopilot_formula_title():
    good = score_title("A Day on Venus Is Longer Than Its Year 🤯", "Venus")
    old = score_title("INSANE REACTION!!! You Won't Believe This Repurposed Clip #Shorts")
    assert good["score"] > old["score"]
    assert good["components"]["anchor"] == 8
    assert old["components"].get("caps_abuse") == -4


def test_question_title_flagged_not_banned():
    q = score_title("Why Does Venus Spin Backwards?", "Venus")
    assert q["components"].get("question_form") == -3
    assert "R5_QUESTION_TITLES" in q["rules"]


def test_thumbnail_scoring():
    assert score_thumbnail_text("LONGER THAN A YEAR")["score"] >= 15
    assert score_thumbnail_text("A Day on Venus Is Longer", "A Day on Venus Is Longer Than Its Year")["components"]["not_title_repeat"] == 0
    assert score_thumbnail_text("This Is A Very Long Thumbnail Sentence Indeed")["components"]["words"] == 0


def test_hook_classification_and_scoring():
    assert classify_hook("Venus spins the wrong way. Nobody knows why.") == "problem_statement"
    assert classify_hook("Why does Venus spin backwards?") == "question_gap"
    strong = score_hook("On Venus, one day outlasts a whole year.",
                        "A Day on Venus Is Longer Than Its Year")
    weak = score_hook("Hello and welcome back to another video about space facts today",
                      "A Day on Venus Is Longer Than Its Year")
    assert strong["score"] > weak["score"]
    assert strong["components"]["promise_alignment"] == 8


def test_money_lane_advice_language_fails_gate():
    video = {
        "lane": "money_stories",
        "subject": "the 2008 crash",
        "fact_title": "Invest In This Stock And Double Your Money",
        "hook_fact": "He lost everything in 2008.",
        "thumb_shout": "LOST EVERYTHING",
    }
    out = generate_variants(video)
    fact_first = next(v for v in out["variants"] if v["strategy"] == "fact_first")
    assert fact_first["publishable_packaging"] is False
    assert any("banned term" in i for i in fact_first["gates"]["issues"])


def test_missing_facts_fail_honestly_missing_optional_slots_score_zero():
    out = generate_variants({"lane": "space_science", "subject": "Venus"})
    assert out["ok"] is False and out["variants"] == []
    minimal = {"lane": "history_dyk", "subject": "the Titanic",
               "fact_title": "The Titanic Sank 112 Years Ago Today",
               "hook_fact": "This ship was called unsinkable. It sank.",
               "thumb_shout": "CALLED UNSINKABLE"}
    out = generate_variants(minimal)
    assert out["ok"] is True
    gap = next(v for v in out["variants"] if v["strategy"] == "curiosity_gap")
    assert gap["score"] == 0 and gap["title"] == ""
    assert out["recommended"] == "fact_first"


def test_unknown_lane_rejected():
    out = generate_variants({"lane": "anime", "subject": "x",
                             "fact_title": "y", "hook_fact": "z"})
    assert out["ok"] is False
