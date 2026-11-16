"""TASK-IG2-VYR-06: measured-style editing recipes (cooked pattern).

Pins: style = medians of 3-6 references (fewer refused); transcript
cleaning drops retakes/false starts/pauses without mutating input;
application is deterministic + free (no paid driver); staged
approvals cut->look->render cannot be skipped.
On clean main this fails: app.services.style_recipe does not exist.
"""
from __future__ import annotations

import pytest

from app.services import style_recipe as sr

REF = {"duration_seconds": 60.0, "cuts": 12, "zooms": 3, "caption_words": 90,
       "caption_seconds": 30.0, "cards": 2, "graphics": 1, "sound_cues": 4}
REFS = [REF, {**REF, "cuts": 14}, {**REF, "cuts": 10}]


def _timed(text, gap_at=None):
    out, t = [], 0.0
    for i, w in enumerate(text.split()):
        out.append({"word": w, "start": round(t, 2), "end": round(t + 0.4, 2)})
        t += 0.4 + (1.5 if gap_at == i else 0.0)
    return out


def test_style_is_median_of_references():
    s = sr.measure_style(REFS, name="creator-x")
    assert s["cuts_per_minute"] == 12.0 and s["measured"] is True
    assert s["caption_coverage"] == 3.0
    with pytest.raises(ValueError):
        sr.measure_style(REFS[:2], name="too-few")


def test_transcript_cleaning():
    words = _timed("the the crater um forms today", gap_at=3)
    snapshot = [dict(w) for w in words]
    cleaned = sr.clean_transcript(words)
    kinds = {c["kind"] for c in cleaned["cuts"]}
    assert {"retake", "false_start", "pause"} <= kinds
    assert [w["word"] for w in cleaned["kept_words"]] == ["the", "crater", "forms", "today"]
    assert words == snapshot  # input untouched


def test_apply_and_staged_approvals():
    s = sr.measure_style(REFS, name="creator-x")
    cleaned = sr.clean_transcript(_timed("hello world today"))
    plan = sr.apply_style(s, cleaned, duration_seconds=60.0)
    assert plan["target_cuts"] == 12 and plan["paid_driver_used"] is False
    assert plan["stage"] == "cut" and plan["status"] == "pending_review"
    plan = sr.advance_stage(plan, approved_by="owner")
    assert plan["stage"] == "look"
    plan = sr.advance_stage(plan, approved_by="owner")
    assert plan["stage"] == "render"
    plan = sr.advance_stage(plan, approved_by="owner")
    assert plan["stage"] == "done" and plan["status"] == "approved_for_render"
    assert plan["publish"] is False and len(plan["approvals"]) == 3
    with pytest.raises(ValueError):
        sr.advance_stage(plan, approved_by="owner")
