"""TASK-IG-VYR-03: viral-pattern analysis & format cloning (Hypit pattern).

Behaviour pinned here:

* keyframe extraction is honest — a missing file or tool yields
  ``available=False`` with a reason, never invented frames; on a
  real synthetic video it returns real frames (skipped without
  ffmpeg);
* templates are word-anchored and structure-only: they store word
  counts and beat boundaries, never the reference's words or media;
* hook scoring is a stated deterministic heuristic with named
  components — a strong hook outscores a flat opening;
* a clone plan maps the NEW script's own words onto the template's
  beats and stays pending_review.

On clean main every test fails: app.services.format_clone does not
exist.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import format_clone as fc


def _timed(text: str, wps: float = 2.5, pause_after: int | None = None):
    words = []
    t = 0.0
    for i, w in enumerate(text.split()):
        words.append({"word": w, "start": round(t, 2),
                      "end": round(t + 1 / wps, 2)})
        t += 1 / wps
        if pause_after is not None and i == pause_after:
            t += 1.2  # a real pause -> a beat boundary
    return words


REF_TEXT = ("watch this crater appear in three seconds flat "
            "the rim forms first then the floor drops away "
            "and the whole valley changes forever today")
REF = {"duration_seconds": 8.4,
       "timed_words": _timed(REF_TEXT, pause_after=7)}


def test_template_is_word_anchored_and_structure_only():
    tpl = fc.build_format_template(REF)
    assert tpl["structure_only"] is True
    assert tpl["carries_reference_words"] is False
    assert tpl["carries_reference_media"] is False
    assert tpl["words_total"] == len(REF_TEXT.split())
    assert tpl["beats"][0]["role"] == "hook"
    # the pause after word 7 must create a beat boundary at index 8
    bounds = [(b["word_start"], b["word_end"]) for b in tpl["beats"]]
    assert (0, 8) in bounds
    # no reference word text anywhere in the template
    assert REF_TEXT.split()[3] not in str(tpl)


def test_template_requires_timed_words():
    try:
        fc.build_format_template({"duration_seconds": 5, "timed_words": []})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_hook_scoring_discriminates():
    strong = fc.score_hook(
        "Have you ever seen 3 craters form in ten seconds? Watch this.")
    flat = fc.score_hook("This is a video about geology and rocks.")
    assert strong["score"] > flat["score"]
    assert strong["checks"]["question_form"] is True
    assert strong["checks"]["concrete_number"] is True
    assert "not a virality predictor" in strong["basis"]


def test_clone_maps_new_words_onto_beats():
    tpl = fc.build_format_template(REF)
    plan = fc.clone_format(
        tpl, "Did you know the moon hides a dark side? "
             "Its craters record four billion years of impacts "
             "and every one tells a story.", topic="the Moon")
    assert plan["status"] == "pending_review"
    assert plan["publish"] is False
    joined = " ".join(s["text"] for s in plan["segments"])
    assert "moon" in joined and "craters" in joined
    # word accounting is exact: every new word placed exactly once
    placed = sum(s["word_end"] - s["word_start"] for s in plan["segments"])
    assert placed == len(joined.split())
    assert plan["hook_score"]["score"] > 0


def test_variants_one_plan_per_script():
    tpl = fc.build_format_template(REF)
    plans = fc.make_variants(tpl, ["Hook one about Mars and its valleys.",
                                   "Hook two about Europa and its ice."])
    assert len(plans) == 2
    assert all(p["status"] == "pending_review" for p in plans)


def test_keyframes_missing_file_is_honest(tmp_path):
    out = fc.extract_keyframes(tmp_path / "nope.mp4", tmp_path / "out")
    assert out["available"] is False
    assert out["frames"] == []
    assert out["reason"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg not available")
def test_keyframes_from_synthetic_video(tmp_path):
    video = tmp_path / "ref.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-f", "lavfi", "-i", "smptebars=duration=2:size=320x240:rate=10",
         "-filter_complex", "[0][1]concat=n=2:v=1", str(video)],
        check=True, capture_output=True, timeout=60)
    facts = fc.probe_video(video)
    assert facts["available"] is True
    assert facts["duration_seconds"] and facts["duration_seconds"] > 3
    out = fc.extract_keyframes(video, tmp_path / "frames")
    assert out["available"] is True
    assert out["frames"] and Path(out["frames"][0]).exists()
