"""TASK-VYR-080: the AgentTube operator workflow wired into VyralX.

Pins:

* a channel mandate validates (objective, audience, pillars, cadence);
* a run checkpoints stage by stage, in order, and resumes where it
  stopped instead of starting over;
* production readiness is fail-closed: no gate input, no narration or
  unlinked facts each fail it, and the measured compliance gate must
  pass — unmeasured sync never passes;
* approval is required before publish, and publishing never uploads:
  an approved run waits unlisted and pending review;
* one scene can be repaired without restarting the run;
* an approved long video repurposes into up to three 9:16 Short drafts
  (local mode only, missing BGM falls back to the ambient pad, doubled
  captions are deduped and counted);
* comment mining turns repeated requests into ideas, never one-offs;
* the learning loop only proposes — the owner approves, and approval is
  not application;
* a title experiment adopts a winner only at the 95% evidence
  threshold with at least 100 impressions; the original is restored;
* guardrail: none of the other four VYR-080 repos (OpenCut, SANA-WM,
  WanGP, ComfyUI) — nor the heavyweight runtimes they need — is
  imported anywhere in VyralX's production path.
On clean main this fails: app.services.agenttube does not exist.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services import agenttube as at
from app.services import content_ab_tester
from app.services import film_pipeline
from app.services import shorts_live_path as lp

MANDATE = at.ChannelMandate(
    objective="Grow the space-science Shorts channel",
    audience="curious adults",
    pillars=["space_science", "history"],
    cadence_per_week=3,
)

TEXT = ("nobody tells you the hidden truth about this crater and wow "
        "you will be stunned because suddenly the floor drops then "
        "finally the whole valley changes forever in this amazing moment")


def _timed(text, wps=2.5):
    out, t = [], 0.0
    for w in text.split():
        out.append({"word": w, "start": round(t, 2), "end": round(t + 1 / wps, 2)})
        t += 1 / wps
    return out


TRANSCRIPT = {"duration_seconds": 72.0, "timed_words": _timed(TEXT * 6),
              "source": "long.mp4"}

SCRIPT = "Apollo 11 launched in July 1969. Armstrong stepped out on July 20."

GATE_INPUT = {
    "provenance": {
        "record_id": "VYR080-TEST-1",
        "source_page_url": "https://images.nasa.gov/details/1",
        "author": "NASA",
        "license_name": "Public Domain",
        "retrieved_at": "2026-11-25T00:00:00+00:00",
        "media_url": "https://images.nasa.gov/1.mp4",
        "license_class": "public_domain",
        "allowed": True,
        "decision_reason": "public domain",
    },
    "lane": "history",
    "format_name": "shorts_factory",
    "category": "",
    "script": SCRIPT,
    "source_has_speech": False,
    "attribution_included": True,
    "language": "en",
    "sync": {
        "beat_deviations_seconds": [0.1, 0.2],
        "caption_match_rate": 0.9,
        "caption_offset_max_abs_seconds": 0.2,
        "narration_seconds": 40.0,
        "render_seconds": 50.0,
    },
}


def _ready_run():
    run = at.new_run(MANDATE, "Apollo 11", lane="history")
    at.set_script(run, SCRIPT)
    at.production_readiness(run, gate_input=GATE_INPUT,
                            narration_present=True, facts_linked=["NASA Apollo 11"])
    return run


def _approved_run():
    run = _ready_run()
    at.approve_run(run)
    return run


# --- mandate / run lifecycle -------------------------------------------------

def test_mandate_validation():
    with pytest.raises(at.AgentTubeError):
        at.ChannelMandate(objective="", audience="x", pillars=["history"])
    with pytest.raises(at.AgentTubeError):
        at.ChannelMandate(objective="x", audience="y", pillars=[])
    with pytest.raises(at.AgentTubeError):
        at.ChannelMandate(objective="x", audience="y", pillars=["history"],
                          cadence_per_week=9)


def test_new_run_starts_at_research_all_stages_pending():
    run = at.new_run(MANDATE, "Apollo 11")
    assert run["stage"] == "research"
    assert run["status"] == "in_progress"
    assert run["approved"] is False
    assert all(s["status"] == "pending" for s in run["stages"].values())


def test_advance_in_order_and_resume_after_interruption():
    run = at.new_run(MANDATE, "Apollo 11")
    at.advance_run(run, "research", output="topics found")
    at.advance_run(run, "script", output="script written")
    assert run["stage"] == "production"
    # A crash after script: resume returns production, not research.
    assert at.resume_run(run) == "production"
    with pytest.raises(at.AgentTubeError):
        at.advance_run(run, "review")  # cannot skip production
    with pytest.raises(at.AgentTubeError):
        at.advance_run(run, "research")  # cannot re-run a done stage


def test_publish_stage_needs_approval():
    run = _ready_run()
    for stage in ("research", "script", "production", "review"):
        at.advance_run(run, stage)
    with pytest.raises(at.AgentTubeError):
        at.advance_run(run, "publish")
    at.approve_run(run)
    at.advance_run(run, "publish")
    assert run["stages"]["publish"]["status"] == "completed"


# --- readiness / approval / publish ------------------------------------------

def test_readiness_is_fail_closed():
    run = at.new_run(MANDATE, "Apollo 11")
    at.set_script(run, SCRIPT)
    readiness = at.production_readiness(run)  # nothing measured
    assert readiness["passed"] is False
    failed = {c["check"] for c in readiness["checks"] if c["status"] != "pass"}
    assert {"narration_present", "facts_linked", "compliance_gate"} <= failed


def test_readiness_passes_with_measured_gate():
    run = _ready_run()
    assert run["readiness"]["passed"] is True
    assert all(c["status"] == "pass" for c in run["readiness"]["checks"])


def test_approve_requires_readiness_and_publish_never_uploads():
    run = at.new_run(MANDATE, "Apollo 11")
    with pytest.raises(at.AgentTubeError):
        at.approve_run(run)
    with pytest.raises(at.AgentTubeError):
        at.publish_decision(run)
    run = _approved_run()
    assert run["status"] == "approved"
    decision = at.publish_decision(run)
    assert decision["publish"] is False
    assert decision["privacy_if_published"] == "unlisted"
    assert decision["review"] == "pending_review"


def test_rejected_run_never_advances_or_publishes():
    run = _ready_run()
    at.reject_run(run, reason="facts do not check out")
    assert run["status"] == "rejected"
    with pytest.raises(at.AgentTubeError):
        at.advance_run(run, "research")
    with pytest.raises(at.AgentTubeError):
        at.approve_run(run)


# --- scene repair --------------------------------------------------------------

def test_repair_scene_fixes_one_scene_without_restarting():
    run = _ready_run()
    film = film_pipeline.build_film(
        title="Apollo 11", lane="history",
        shots=[{"shot_id": "s1", "duration": 10.0, "text": "Launch."},
               {"shot_id": "s2", "duration": 12.0, "text": "Moonwalk."}])
    repaired = at.repair_scene(
        run, film, {"op": "trim", "shot_id": "s1", "duration": 8.0})
    assert repaired["shots"][0]["duration"] == 8.0
    assert repaired["duration"] == 20.0
    assert repaired["status"] == "pending_review"
    assert run["repairs"] == [{"op": "trim", "shot_id": "s1"}]
    # The run itself is untouched: research is still the next stage.
    assert run["stage"] == "research"
    with pytest.raises(ValueError):
        at.repair_scene(run, film, {"op": "explode", "shot_id": "s1"})


# --- Shorts repurposing ----------------------------------------------------------

def test_repurpose_shorts_from_approved_long_video():
    run = _approved_run()
    plans = at.repurpose_shorts(
        run, TRANSCRIPT, source_path="long.mp4", output_dir="/tmp/vyr080",
        music_dir="/tmp/vyr080/no-such-music-dir")
    assert 1 <= len(plans) <= 3
    for plan in plans:
        assert plan["preset"] == "shorts"
        assert (plan["width"], plan["height"]) == (1080, 1920)
        assert plan["publish"] is False
        assert plan["privacy_if_published"] == "unlisted"
        assert plan["review"] == "pending_review"
        # Missing BGM is a named fallback, never a silent render.
        assert plan["bgm_fallback"] == "ambient_pad"
        assert plan["bgm_path"] is None
    assert run["shorts"] == [p["destination"] for p in plans]


def test_repurpose_requires_approval_and_transcript():
    run = _ready_run()  # ready but not approved
    with pytest.raises(at.AgentTubeError):
        at.repurpose_shorts(run, TRANSCRIPT, source_path="long.mp4",
                            output_dir="/tmp/vyr080")
    run = _approved_run()
    with pytest.raises(at.AgentTubeError):
        at.repurpose_shorts(run, {"duration_seconds": 0, "timed_words": []},
                            source_path="long.mp4", output_dir="/tmp/vyr080")


def test_doubled_captions_are_deduped_and_counted():
    cues = [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello world"},
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "hello world"},
        {"start_seconds": 1.0, "end_seconds": 2.0, "text": "next line"},
    ]
    cleaned, removed = lp.dedupe_cues(cues)
    assert removed == 1
    assert len(cleaned) == 2


# --- comment mining / learning loop ----------------------------------------------

def test_mine_comment_ideas_only_from_repeated_requests():
    comments = [
        {"text": "please make a video on black holes!"},
        {"text": "Video on black holes please"},
        {"text": "can you cover black holes?"},
        {"text": "great video, loved it"},
        {"text": "make a video on neutron stars"},
    ]
    ideas = at.mine_comment_ideas(comments)
    assert len(ideas) == 1
    assert ideas[0]["idea"] == "black holes"
    assert ideas[0]["mentions"] == 3


def test_learning_loop_only_proposes_never_applies():
    run = _approved_run()
    lesson = at.propose_lesson(run, kpi="views", value_24h=120, value_7d=800,
                               baseline=1000)
    assert lesson["direction"] == "below"
    assert lesson["status"] == "proposed"
    assert lesson["approved"] is False
    assert lesson["applied"] is False
    approved = at.approve_lesson(run, lesson["lesson_id"])
    assert approved["approved"] is True
    assert approved["status"] == "approved"
    # Approval is not application: the loop never applies it itself.
    assert approved["applied"] is False
    with pytest.raises(at.AgentTubeError):
        at.propose_lesson(run, value_24h=None, value_7d=800, baseline=1000)


# --- controlled experiments ----------------------------------------------------------

def test_title_experiment_adopts_winner_only_at_95_percent():
    tester = content_ab_tester.ContentABTester()
    variants = [{"name": "A", "title": "The hidden truth about craters"},
                {"name": "B", "title": "Craters explained"}]
    strong = at.run_title_experiment(
        tester, video_id="vid1", name="title test", hypothesis="hook wins",
        variants=variants,
        results=[("A", 100, 60), ("B", 100, 20)])
    assert strong["adopted"] is True
    assert strong["winner"] == "A"
    assert strong["significance"] >= 0.95
    assert strong["original_restored"] is True

    weak = at.run_title_experiment(
        tester, video_id="vid1", name="title test 2", hypothesis="hook wins",
        variants=variants,
        results=[("A", 10, 6), ("B", 10, 2)])
    assert weak["adopted"] is False
    assert weak["winner"] is None
    assert weak["original_restored"] is True


# --- guardrail: the other four repos stay out of the production path ----------

def test_no_banned_imports_in_production_path():
    app_root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in sorted(app_root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]] if node.module else []
            else:
                continue
            for name in names:
                if name in at.BANNED_IMPORTS:
                    offenders.append(f"{path.relative_to(app_root)}: {name}")
    assert not offenders, (
        "banned import in the production path (VYR-080 guardrail): "
        + "; ".join(offenders))


def test_no_banned_heavyweight_runtime_in_dependencies():
    vyralx_root = Path(__file__).resolve().parents[1]
    pyproject = (vyralx_root / "pyproject.toml").read_text()
    for banned in ("torch", "diffusers", "gradio", "playwright"):
        assert banned not in pyproject, f"{banned} must not be a VyralX dependency"
