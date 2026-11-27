"""TASK-VYR-079 checkpoint 3: Nextwork cooked adapt leg (2 of 4).

Pins: a measured style from 3–6 same-format references averages into
a reusable profile; a transcript cut drops retakes/false starts/
pauses and re-cuts kept speech to the style's mean shot length; the
cut → look → render stages approve in order only; rendering stays
gated off-fleet until every stage is approved AND the host is the
owner machine; the Claude-account constraint is recorded and no paid
path is used. On clean main this fails:
app.services.nextwork_style does not exist.
"""
from __future__ import annotations

import pytest

from app.services import nextwork_style as ns

REFS = [
    {"format": "vertical talking-head", "duration_s": 45.0,
     "measurements": {"cuts_per_minute": 12.0, "mean_shot_seconds": 3.0,
                      "zooms_per_minute": 4.0, "caption_style": "burned_in",
                      "cards_per_minute": 1.0, "graphics_density": 0.4,
                      "sound_bed": "lofi"}},
    {"format": "vertical talking-head", "duration_s": 52.0,
     "measurements": {"cuts_per_minute": 15.0, "mean_shot_seconds": 4.0,
                      "zooms_per_minute": 6.0, "caption_style": "burned_in",
                      "cards_per_minute": 2.0, "graphics_density": 0.6,
                      "sound_bed": "lofi"}},
    {"format": "vertical talking-head", "duration_s": 38.0,
     "measurements": {"cuts_per_minute": 9.0, "mean_shot_seconds": 5.0,
                      "zooms_per_minute": 2.0, "caption_style": "burned_in",
                      "cards_per_minute": 0.0, "graphics_density": 0.2,
                      "sound_bed": "lofi"}},
]

TRANSCRIPT = [
    {"text": "welcome back to the channel", "start_s": 0.0,
     "duration_s": 6.0, "kind": "speech"},
    {"text": "welcome back uh welcome", "start_s": 6.0,
     "duration_s": 2.0, "kind": "false_start"},
    {"text": "today we build a film pipeline", "start_s": 8.0,
     "duration_s": 8.0, "kind": "speech"},
    {"text": "um", "start_s": 16.0, "duration_s": 3.0, "kind": "pause"},
    {"text": "let me redo that intro", "start_s": 19.0,
     "duration_s": 2.0, "kind": "retake"},
    {"text": "three shots and a render gate", "start_s": 21.0,
     "duration_s": 4.0, "kind": "speech"},
]

EXISTING = {"raw/clip.mp4"}


def _adapt(refs=None, transcript=None, **kw):
    kw.setdefault("asset_exists", EXISTING.__contains__)
    return ns.adapt_nextwork_cut(
        style_name="talking-head-burned",
        references=refs if refs is not None else REFS,
        raw_clip="raw/clip.mp4",
        transcript=transcript if transcript is not None else TRANSCRIPT,
        **kw)


def test_nextwork_leg_stages_end_to_end():
    r = _adapt()
    assert r["status"] == "staged"
    assert r["nextwork_repo"] == "nextwork-projects/ai-video-editor-cooked"
    assert r["license"] == "MIT"
    style = r["style"]
    assert style["reference_count"] == 3
    assert style["format"] == "vertical talking-head"
    m = style["measurements"]
    assert m["cuts_per_minute"] == 12.0
    assert m["mean_shot_seconds"] == 4.0
    assert m["caption_style"] == "burned_in"
    assert m["graphics_density"] == 0.4
    assert m["sound_bed"] == "lofi"
    # No paid path: the Claude constraint is recorded, nothing paid used.
    assert style["paid_services_used"] is False
    assert style["claude_code"]["required_upstream"] is True
    assert style["claude_code"]["used_here"] is False
    plan = r["plan"]
    assert plan["status"] == "awaiting_cut_approval"
    assert [s["stage"] for s in plan["stages"]] == ["cut", "look", "render"]
    assert all(s["approved"] is False for s in plan["stages"])
    assert r["render"] is None
    cut = plan["cut"]
    # 3 dropped (false start, pause, retake), 3 kept (18s of speech).
    assert [d["kind"] for d in cut["dropped_segments"]] == [
        "false_start", "pause", "retake"]
    assert cut["dropped_seconds"] == 7.0
    assert cut["kept_seconds"] == 18.0
    # Kept speech re-cut at the 4s mean shot length: 6+8+4 -> 2+2+1 shots.
    assert len(cut["shots"]) == 5
    assert all(s["duration_s"] <= 4.0 for s in cut["shots"])
    assert sum(s["duration_s"] for s in cut["shots"]) == 18.0
    assert cut["shots"][0]["narration"].startswith("welcome back")


def test_reference_bounds_fail():
    with pytest.raises(ns.StyleError, match="at least 3"):
        ns.measure_style("x", REFS[:2])
    with pytest.raises(ns.StyleError, match="at most 6"):
        ns.measure_style("x", REFS * 3)
    mixed = [dict(REFS[0]), dict(REFS[1], format="landscape explainer"),
             dict(REFS[2])]
    with pytest.raises(ns.StyleError, match="share one editing format"):
        ns.measure_style("x", mixed)
    bad_caption = [dict(REFS[0]),
                   dict(REFS[1], measurements=dict(
                       REFS[1]["measurements"],
                       caption_style="karaoke")),
                   dict(REFS[2])]
    with pytest.raises(ns.StyleError, match="caption_style"):
        ns.measure_style("x", bad_caption)
    zero_cuts = [dict(REFS[0]),
                 dict(REFS[1], measurements=dict(
                     REFS[1]["measurements"], cuts_per_minute=0)),
                 dict(REFS[2])]
    with pytest.raises(ns.StyleError, match="above 0"):
        ns.measure_style("x", zero_cuts)


def test_missing_raw_clip_fails_and_unchecked_warns():
    r = _adapt(asset_exists=lambda p: False)
    assert r["status"] == "failed" and r["render"] is None
    assert any("raw/clip.mp4" in e for e in r["errors"])
    r2 = ns.adapt_nextwork_cut(style_name="talking-head-burned",
                               references=REFS, raw_clip="raw/clip.mp4",
                               transcript=TRANSCRIPT)
    assert r2["status"] == "staged"
    assert any("unchecked" in w for w in r2["plan"]["warnings"])


def test_all_dropped_transcript_fails():
    only_junk = [dict(s) for s in TRANSCRIPT if s["kind"] != "speech"]
    r = _adapt(transcript=only_junk)
    assert r["status"] == "failed"
    assert any("kept no speech" in e for e in r["errors"])
    with pytest.raises(ns.StyleError, match="unknown kind"):
        ns.cut_transcript(
            [{"text": "x", "start_s": 0.0, "duration_s": 1.0,
              "kind": "bloopers"}], ns.measure_style("s", REFS))


def test_stages_approve_in_order_only():
    plan = _adapt()["plan"]
    with pytest.raises(ns.StyleError, match="before 'cut'"):
        ns.approve_stage(plan, "look")
    ns.approve_stage(plan, "cut")
    assert plan["status"] == "awaiting_look_approval"
    with pytest.raises(ns.StyleError, match="already approved"):
        ns.approve_stage(plan, "cut")
    ns.approve_stage(plan, "look")
    assert plan["status"] == "awaiting_render_approval"
    ns.approve_stage(plan, "render")
    assert plan["status"] == "ready_to_render"


def test_render_gated_until_approved_and_off_fleet():
    plan = _adapt()["plan"]
    # Unapproved plan: no render command on any host.
    assert ns.render_command(plan, host_role="owner_machine")["available"] is False
    for stage in ("cut", "look", "render"):
        ns.approve_stage(plan, stage)
    # Approved but on the fleet: still refused.
    fleet = ns.render_command(plan, host_role="fleet_service")
    assert fleet["available"] is False
    assert fleet["renders_in_service"] is False
    # Approved on the owner machine: command issued, executes nothing.
    cmd = ns.render_command(plan, host_role="owner_machine")
    assert cmd["available"] is True
    assert cmd["argv"][1:3] == ["remotion", "render"]
    assert cmd["argv"][-1] == "out.mp4"
