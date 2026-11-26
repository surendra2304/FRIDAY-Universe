"""TASK-VYR-061: best-take selection + blank-frame
self-verification wired into the pipeline layer.

Behaviour pinned here:

* media_quality black intervals adapt into gate segments
  exactly as measured — nothing invented, nothing dropped;
* a render's blank self-verification verdict comes from
  take_verification.blank_gate over those intervals, and an
  unmeasured render (intervals None) is reported unavailable,
  never as passing;
* best-take selection applies the blank gate FIRST: a
  high-scoring take with a long blank is excluded with its
  gate evidence, and the clean take wins;
* a candidate with no timed words or no duration cannot win;
* when every candidate fails, there is NO winner
  (fail-closed) and each exclusion carries its evidence;
* project_pipeline records the verdict into the QA report of
  the held render (source-level wiring check).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import take_verification as tv


_PIPELINE = (Path(__file__).resolve().parent.parent / "app"
             / "services" / "project_pipeline.py")


def _words(text, *, step=0.3):
    return [{"word": w, "start": round(i * step, 2),
             "end": round(i * step + 0.25, 2)}
            for i, w in enumerate(text.split())]


_CLEAN_INTERVALS = [
    {"start_seconds": 3.0, "end_seconds": 3.4, "duration_seconds": 0.4},
]
_BLANK_INTERVALS = [
    {"start_seconds": 5.0, "end_seconds": 9.0, "duration_seconds": 4.0},
]


def test_adapter_converts_media_quality_intervals_exactly():
    segments = tv.blank_segments_from_intervals(_BLANK_INTERVALS)
    assert segments == [{"start": 5.0, "end": 9.0, "duration": 4.0}]
    assert tv.blank_segments_from_intervals(None) == []
    assert tv.blank_segments_from_intervals(
        [{"not": "a measurement"}, {"duration_seconds": "x"}]) == []


def test_verify_render_signals_passes_clean_and_fails_blank():
    clean = tv.verify_render_signals(_CLEAN_INTERVALS, duration_s=60.0)
    assert clean["kind"] == "render_blank_self_verification"
    assert clean["task"] == "TASK-VYR-061"
    assert clean["status"] == "measured"
    assert clean["passed"] is True
    blank = tv.verify_render_signals(_BLANK_INTERVALS, duration_s=60.0)
    assert blank["passed"] is False
    assert blank["failures"][0]["kind"] == "single_blank_too_long"


def test_verify_render_signals_unmeasured_is_never_a_pass():
    verdict = tv.verify_render_signals(None, duration_s=60.0)
    assert verdict["status"] == "unavailable"
    assert verdict["passed"] is None


def test_blank_high_scorer_is_excluded_and_clean_take_wins():
    strong_but_blank = {
        "take_id": "take-blank",
        "timed_words": _words("the lighthouse keeper watched "
                              "the wide sea every single night"),
        "duration_s": 60.0,
        "black_intervals": _BLANK_INTERVALS,
    }
    clean = {
        "take_id": "take-clean",
        "timed_words": _words("the lighthouse keeper watched the sea"),
        "duration_s": 60.0,
        "black_intervals": _CLEAN_INTERVALS,
    }
    result = tv.select_verified_best_take([strong_but_blank, clean])
    assert result["best_take_id"] == "take-clean"
    assert [e["take_id"] for e in result["excluded"]] == ["take-blank"]
    gate = result["excluded"][0]["blank_gate"]
    assert gate["passed"] is False
    assert gate["longest_blank_s"] == 4.0


def test_all_candidates_failing_selects_no_winner():
    blank_a = {
        "take_id": "take-a", "timed_words": _words("one two three"),
        "duration_s": 30.0, "black_intervals": _BLANK_INTERVALS,
    }
    blank_b = {
        "take_id": "take-b", "timed_words": _words("four five six"),
        "duration_s": 30.0,
        "blackdetect_output": (
            "black_start:1.0 black_end:6.0 black_duration:5.0"),
    }
    result = tv.select_verified_best_take([blank_a, blank_b])
    assert result["best_take_id"] is None
    assert result["ranking"] == []
    assert len(result["excluded"]) == 2
    assert result["publish"] is False


def test_unmeasured_candidates_cannot_win():
    unmeasured = {
        "take_id": "take-silent",
        "duration_s": 60.0,
        "black_intervals": [],
    }
    no_duration = {
        "take_id": "take-nodur",
        "timed_words": _words("hello world"),
        "black_intervals": [],
    }
    result = tv.select_verified_best_take([unmeasured, no_duration])
    assert result["best_take_id"] is None
    reasons = {e["take_id"]: e["reason"] for e in result["excluded"]}
    assert "timed_words" in reasons["take-silent"]
    assert "duration_s" in reasons["take-nodur"]


def test_empty_candidate_list_is_an_error():
    with pytest.raises(ValueError):
        tv.select_verified_best_take([])


def test_project_pipeline_records_the_verdict_on_held_renders():
    source = _PIPELINE.read_text(encoding="utf-8")
    assert "verify_render_signals" in source
    assert 'qa_report["blank_self_verification"]' in source
