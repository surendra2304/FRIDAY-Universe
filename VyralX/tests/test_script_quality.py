"""Tests for the VyralX script-quality system (TASK-VYR-007).

Covers the rubric/hook library's integrity, the rotation that keeps
consecutive scripts from sharing a template, the brief the scriptwriter
receives, the scorer's verdicts on the sample scripts (good ones pass,
flawed ones are rejected with the right gates), and the content.py
integration (default-off: no lane, no change).
"""
import json
from types import SimpleNamespace

import pytest

from app.services.script_quality import (
    build_script_brief,
    choose_rotation,
    hook_formulas,
    list_formats,
    list_lanes,
    load_library,
    score_content_pack,
    score_script,
)
from script_quality_samples import SAMPLES


def _sample(sample_id):
    return next(s for s in SAMPLES if s["id"] == sample_id)


def _score(sample, recent=None):
    return score_script(
        sample,
        lane=sample["lane"],
        fmt=sample["format"],
        hook_formula=sample["hook_formula"],
        recent=recent,
    )


# --- library integrity -----------------------------------------------------

def test_library_has_exactly_the_three_confirmed_lanes():
    assert list_lanes() == ["history_facts", "space_science", "tech_ai"]
    lib = load_library()
    for lane in lib["lanes"].values():
        assert lane["signal_words"] and lane["banned_terms"] and lane["source_types"]


def test_every_hook_formula_has_an_example_per_lane():
    lib = load_library()
    assert len(lib["hook_formulas"]) >= 8
    for formula in lib["hook_formulas"]:
        assert set(formula["examples"]) == set(lib["lanes"])
        assert formula["cues"] and formula["formats"]


def test_rubric_weights_sum_to_100():
    weights = load_library()["rubric"]["weights"]
    assert sum(weights.values()) == 100
    assert set(weights) == {"hook", "escalation", "payoff", "format_fit", "lane_fit", "originality"}


def test_formats_are_the_three_rotating_structures():
    assert list_formats() == ["one_fact", "story", "top5"]
    for fmt in list_formats():
        assert hook_formulas(fmt=fmt), f"no hook formula serves {fmt}"


# --- rotation ---------------------------------------------------------------

def test_rotation_cycles_formats_before_repeating():
    recent = []
    seen = []
    for _ in range(3):
        pick = choose_rotation("space_science", recent)
        seen.append(pick["format"])
        recent.insert(0, pick)
    assert len(set(seen)) == 3, f"formats repeated too early: {seen}"


def test_rotation_never_repeats_the_previous_formula_for_same_format():
    recent = []
    for _ in range(6):
        pick = choose_rotation("history_facts", recent)
        if recent:
            prev = recent[0]
            assert not (
                pick["format"] == prev["format"]
                and pick["hook_formula"] == prev["hook_formula"]
            ), f"rotation repeated {pick} back-to-back"
        recent.insert(0, pick)


def test_rotation_rejects_unknown_lane():
    with pytest.raises(ValueError):
        choose_rotation("finance_tips")


# --- brief -------------------------------------------------------------------

def test_brief_carries_rubric_hook_and_budgets():
    brief = build_script_brief("space_science")
    text = brief["brief_text"]
    assert brief["lane"] == "space_science"
    assert brief["format"] in list_formats()
    assert brief["hook_formula"] in {f["id"] for f in hook_formulas()}
    assert "SCRIPT QUALITY BRIEF" in text
    assert "3 seconds" in text
    assert "35-60 seconds of speech" in text
    assert "don't want you to know" in text  # the never-deception rule is in the brief


def test_brief_respects_requested_format():
    brief = build_script_brief("tech_ai", fmt="top5")
    assert brief["format"] == "top5"
    formula = next(f for f in hook_formulas() if f["id"] == brief["hook_formula"])
    assert "top5" in formula["formats"]


# --- scorer on samples --------------------------------------------------------

@pytest.mark.parametrize("sample_id", [
    "good_space_one_fact", "good_space_top5", "good_history_story", "good_tech_one_fact",
])
def test_good_samples_pass(sample_id):
    result = _score(_sample(sample_id))
    assert result["verdict"] == "PASS", f"{sample_id}: {result}"
    assert result["gates_failed"] == []
    assert result["score"] >= 75


def test_flawed_top5_is_rejected_with_actionable_notes():
    result = _score(_sample("flawed_tech_top5"))
    assert result["verdict"] == "REJECT"
    all_notes = " ".join(
        note for dim in result["dimensions"].values() for note in dim["notes"]
    )
    assert "throat-clearing" in all_notes
    assert "countdown incomplete" in all_notes
    assert result["dimensions"]["hook"]["score"] < 10


def test_template_repeat_trips_the_gate():
    good = _score(_sample("good_history_story"))
    history_entry = {**good, "script": "\n".join(_sample("good_history_story")["beats"])}
    result = _score(_sample("flawed_history_repeat"), recent=[history_entry])
    assert result["verdict"] == "REJECT"
    assert any(g.startswith("template_repeat") for g in result["gates_failed"])


def test_banned_content_trips_the_gate():
    result = _score(_sample("flawed_space_banned"))
    assert result["verdict"] == "REJECT"
    assert any(g.startswith("banned_content") for g in result["gates_failed"])


def test_overlong_hook_trips_the_gate():
    result = _score(_sample("flawed_hook_too_long"))
    assert result["verdict"] == "REJECT"
    assert any(g.startswith("hook_too_long") for g in result["gates_failed"])
    assert result["metrics"]["hook_words"] > 12


# --- scorer gates and edges ----------------------------------------------------

def test_empty_script_is_rejected():
    result = score_script("", lane="space_science")
    assert result["verdict"] == "REJECT"
    assert result["gates_failed"] == ["empty_script"]


def test_overlong_script_trips_duration_gate():
    beat = "The star is larger than the sun and older than the galaxy around it."
    script = {"hook": "This star hides a giant secret.", "beats": [beat] * 30}
    result = score_script(script, lane="space_science", fmt="one_fact")
    assert any(g.startswith("duration_too_long") for g in result["gates_failed"])
    assert result["verdict"] == "REJECT"


def test_advice_language_is_banned_in_every_lane():
    script = {
        "hook": "This coin trick prints money daily.",
        "beats": [
            "This coin trick prints money daily.",
            "You should invest in the dip and buy now for guaranteed returns.",
            "It works every single time without any real risk at all.",
            "Which means your money grows while you sleep soundly.",
        ],
    }
    result = score_script(script, lane="tech_ai", fmt="one_fact")
    assert any(g.startswith("banned_content") for g in result["gates_failed"])


def test_score_content_pack_shape():
    pack = {
        "hook": _sample("good_tech_one_fact")["hook"],
        "voiceover": "\n".join(_sample("good_tech_one_fact")["beats"]),
        "script": "unused when voiceover exists",
    }
    result = score_content_pack(pack, lane="tech_ai", fmt="one_fact", hook_formula="question_gap")
    assert result["verdict"] == "PASS"
    assert result["fingerprint"]["beats"] == 6


def test_unknown_lane_and_format_raise():
    with pytest.raises(ValueError):
        score_script("Some hook line here.", lane="astrology")
    with pytest.raises(ValueError):
        score_script("Some hook line here.", lane="space_science", fmt="documentary")


# --- content.py integration -----------------------------------------------------

def _fake_inference(monkeypatch, pack):
    from app.services import content as content_service

    settings = SimpleNamespace(
        inference_url="http://inference:8000",
        inference_api_key="test-key",
        inference_model="",
        inference_generation_path="/v1/task/execute",
        inference_timeout_seconds=3,
        channel_name="", channel_niche="", channel_content_pillars="",
        channel_avoid_topics="", channel_brand_voice="", channel_call_to_action="",
        channel_language="English",
    )
    monkeypatch.setattr(content_service, "get_settings", lambda: settings)
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "SUCCESS",
                    "result": {"response": json.dumps(pack), "model_used": "test-model"}}

    def fake_post(url, **kwargs):
        calls["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(content_service.httpx, "post", fake_post)
    return content_service, calls


def _generated_pack():
    sample = _sample("good_space_one_fact")
    return {
        "hook": sample["hook"],
        "script": "\n".join(sample["beats"]),
        "scene_plan": [{"timecode": "00:00-00:05", "visual": "Star field", "on_screen_text": "Betelgeuse"}],
        "voiceover": "\n".join(sample["beats"]),
        "caption": "Caption",
        "title_options": ["The stadium-sized star"],
        "description": "Description",
        "tags": ["space"],
        "thumbnail_brief": "A marble beside a stadium",
    }


def test_content_pack_with_lane_gets_brief_and_grade(monkeypatch):
    content_service, calls = _fake_inference(monkeypatch, _generated_pack())
    # Production-shaped history (most recent first): every other format and
    # one_fact formula was used more recently, so rotation must assign the
    # one_fact / scale_anchor pairing the generated pack was written to.
    recent = [
        {"lane": "space_science", "format": "story", "hook_formula": "story_cold_open"},
        {"lane": "space_science", "format": "top5", "hook_formula": "countdown_promise"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "number_shock"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "question_gap"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "myth_negation"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "second_person_stakes"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "reveal_delay"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "contrast_pair"},
        {"lane": "space_science", "format": "one_fact", "hook_formula": "timebox_promise"},
    ]
    pack = content_service.generate_content_pack(
        "Betelgeuse size", target_seconds=45, lane="space_science",
        recent_scripts=recent,
    )
    assert pack["script_brief"]["lane"] == "space_science"
    assert pack["script_brief"]["format"] == "one_fact"
    assert pack["script_brief"]["hook_formula"] == "scale_anchor"
    assert pack["script_quality"]["verdict"] == "PASS"
    assert pack["script_quality"]["lane"] == "space_science"
    prompt = calls["kwargs"]["json"]["payload"]["prompt"]
    assert "SCRIPT QUALITY BRIEF" in prompt
    context = calls["kwargs"]["json"]["payload"]["context"]
    assert context["script_quality_brief"]["lane"] == "space_science"


def test_content_pack_without_lane_is_unchanged(monkeypatch):
    content_service, calls = _fake_inference(monkeypatch, _generated_pack())
    pack = content_service.generate_content_pack("Betelgeuse size", target_seconds=45)
    assert "script_quality" not in pack
    assert "script_brief" not in pack
    prompt = calls["kwargs"]["json"]["payload"]["prompt"]
    assert "SCRIPT QUALITY BRIEF" not in prompt
    context = calls["kwargs"]["json"]["payload"]["context"]
    assert "script_quality_brief" not in context


def test_content_pack_unknown_lane_fails_fast(monkeypatch):
    content_service, _ = _fake_inference(monkeypatch, _generated_pack())
    with pytest.raises(ValueError):
        content_service.generate_content_pack("Anything", lane="astrology")
