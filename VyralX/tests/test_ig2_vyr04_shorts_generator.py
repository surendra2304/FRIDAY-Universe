"""TASK-IG2-VYR-04: local-only Shorts generator (AI-Youtube-Shorts-Generator pattern).

Pins: paid api mode rejected; ranking names components and is not a
prediction; overlapping highlights deduped; clips <60s, 9:16, unlisted,
pending_review; empty transcript is honestly empty.
On clean main this fails: app.services.shorts_generator does not exist.
"""
from __future__ import annotations

import pytest

from app.services import shorts_generator as sg


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


def test_paid_api_mode_rejected():
    with pytest.raises(sg.PaidModeRejected):
        sg.generate_shorts(TR, mode="api")
    assert sg.ensure_local_mode("local") == "local"


def test_clips_ranked_deduped_short_unlisted_pending():
    res = sg.generate_shorts(TR, max_clips=3)
    assert res["available"] is True and res["publishes_anything"] is False
    clips = res["clips"]
    assert 1 <= len(clips) <= 3
    for c in clips:
        assert c["duration"] <= sg.MAX_CLIP_SECONDS
        assert c["privacy"] == "unlisted" and c["status"] == "pending_review"
        assert c["publish"] is False
        assert c["crop"]["aspect"] == "9:16"
        assert c["is_prediction"] is False
        assert {"viral_score", "hook", "emotion", "quotable", "story_peak"} <= set(c)
    for a, b in zip(clips, clips[1:]):
        assert b["start"] >= a["end"] - a["duration"] * 0.5  # dedupe bound


def test_empty_transcript_honest():
    res = sg.generate_shorts({"timed_words": []})
    assert res["available"] is False and res["clips"] == []


def test_face_centred_crop_shifts_window():
    centre = sg.vertical_crop_plan({"start": 0, "end": 10})
    left = sg.vertical_crop_plan({"start": 0, "end": 10}, face_center_x=0.1)
    assert centre["filter"] != left["filter"] and left["face_tracked"] is True


def test_batch():
    assert len(sg.batch_generate([TR, {"timed_words": []}])) == 2
