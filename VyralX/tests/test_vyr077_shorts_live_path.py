"""TASK-VYR-077: the shorts ports wired into VyralX's live render path.

Pins:

* a factory job spec becomes a render plan (shorts preset, 9:16,
  unlisted, pending review, never publishes);
* a generator clip becomes a render plan with its trim window, crop
  filter and subtitles sliced from the transcript;
* doubled captions are deduped and counted, not silently kept;
* missing BGM falls back to the ambient pad, named in the plan;
* an over-long short is rejected, not trimmed;
* executing a plan is not tested here: it needs real media and ffmpeg,
  which the live trial on VyralX-Server proves instead.
On clean main this fails: app.services.shorts_live_path does not exist.
"""
from __future__ import annotations

import pytest

from app.services import shorts_factory as sf
from app.services import shorts_generator as sg
from app.services import shorts_live_path as lp

MATERIALS = [{
    "catalog_id": "L1-001", "title": "Apollo footage",
    "license_name": "Public Domain",
    "page_url": "https://images.nasa.gov/details/1",
}]
FACTS = ["Apollo 11 launched in July 1969.",
         "Armstrong stepped out on July 20."]


def _timed(text, wps=2.5):
    out, t = [], 0.0
    for w in text.split():
        out.append({"word": w, "start": round(t, 2), "end": round(t + 1 / wps, 2)})
        t += 1 / wps
    return out


TEXT = ("nobody tells you the hidden truth about this crater and wow "
        "you will be stunned because suddenly the floor drops then "
        "finally the whole valley changes forever in this amazing moment")
TR = {"duration_seconds": 24.0, "timed_words": _timed(TEXT * 3), "source": "long.mp4"}


def test_factory_job_becomes_render_plan():
    job = sf.build_job("Apollo 11", FACTS, MATERIALS, lane="history")
    plan = lp.build_factory_render_plan(
        job, source_path="story.mp4", output_dir="/tmp/vyr077",
        music_dir="/tmp/vyr077/no-such-music-dir")
    assert plan["status"] == "planned"
    assert plan["preset"] == "shorts"
    assert (plan["width"], plan["height"]) == (1080, 1920)
    assert plan["duration_seconds"] < 60
    assert plan["publish"] is False
    assert plan["privacy_if_published"] == "unlisted"
    assert plan["review"] == "pending_review"
    assert plan["render"] == "renderer.render_video"
    assert plan["subtitle_cues"], "subtitle cues must carry through"
    assert plan["bgm_fallback"] == "ambient_pad"
    assert plan["bgm_path"] is None


def test_clip_becomes_render_plan_with_trim_and_crop():
    res = sg.generate_shorts(TR, max_clips=3)
    clip = res["clips"][0]
    plan = lp.build_clip_render_plan(
        clip, TR["timed_words"], source_path="long.mp4",
        output_dir="/tmp/vyr077", music_dir="/tmp/vyr077/no-such-music-dir")
    assert plan["status"] == "planned"
    assert plan["preset"] == "shorts"
    assert plan["duration_seconds"] <= sg.MAX_CLIP_SECONDS
    assert plan["clip_start"] == clip["start"]
    assert plan["clip_end"] == clip["end"]
    assert plan["crop_filter"], "crop filter must carry through"
    assert plan["face_tracked"] is True
    assert plan["subtitle_cues"], "clip subtitles must come from the transcript"
    assert plan["publish"] is False
    assert plan["privacy_if_published"] == "unlisted"
    assert plan["bgm_fallback"] == "ambient_pad"


def test_doubled_captions_deduped_and_counted():
    cues = [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello world"},
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello world"},
        {"start_seconds": 1.0, "end_seconds": 2.0, "text": "next line"},
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello world"},
    ]
    cleaned, removed = lp.dedupe_cues(cues)
    assert removed == 2
    assert len(cleaned) == 2
    assert cleaned[0]["text"] == "hello world"
    assert cleaned[1]["text"] == "next line"


def test_missing_bgm_is_named_fallback_not_silent():
    resolved = lp.resolve_bgm("ambient_explainer", "/tmp/vyr077/no-such-music-dir")
    assert resolved == {"bgm_path": None, "fallback": "ambient_pad"}


def test_overlong_short_rejected_not_trimmed():
    with pytest.raises(lp.LivePathError):
        lp._base_plan(kind="x", topic="Too long", duration=61.0)


def test_wrong_kind_rejected():
    with pytest.raises(lp.LivePathError):
        lp.build_factory_render_plan(
            {"kind": "something-else"}, source_path="a.mp4", output_dir="/tmp/vyr077")


def test_empty_clip_window_has_no_cues():
    assert lp.clip_subtitles([], 0.0, 10.0) == []
    assert lp.clip_subtitles(_timed("hello world"), 100.0, 110.0) == []
