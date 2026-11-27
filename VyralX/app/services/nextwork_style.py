"""VyralX Nextwork "cooked" style adapter — TASK-VYR-079 checkpoint 3 (adapt leg 2 of 4).

Adapts nextwork-projects/ai-video-editor-cooked (MIT, registry fit
``adapt``) into VyralX's live path. Registry card
(``IntelX/intelx/registries/scouted_repos.json``,
``ai-video-editor-cooked.md``): a Claude Code plugin (also Codex,
Cursor, Gemini CLI, Copilot) that edits a talking-head video in the
style of a creator you like — raw clip + 3–6 reference videos sharing
one editing format; it measures their cut speed, zooms, captions,
cards, graphics and sound into a saved, reusable **style**, cuts the
raw video's retakes/false starts/pauses by transcript, then renders
in that style (Remotion) through staged approvals — cut, look, render.
Also makes Shorts from a long video/podcast link, a product video from
a website URL, and a "creator teardown" that turns a profile into a
style. Runs locally with a browser editor; setup installs Python,
FFmpeg, Node, a local Whisper model and the renderer (~1.5 GB total).

VyralX-native implementation (stdlib only, no Claude Code, no plugin,
no Remotion here):

* :func:`measure_style` — the measured-style workflow: 3–6 reference
  descriptors sharing one format are averaged into a reusable style
  profile (cut speed, mean shot length, zooms, caption style, cards,
  graphics density, sound bed). Fewer than 3 or more than 6 references,
  mismatched formats, or out-of-range measurements FAIL the profile —
  never silently averaged.
* :func:`cut_transcript` — the transcript cut: retakes, false starts
  and pauses are dropped (each named with its reason); kept speech is
  re-cut into shots at the style's mean shot length.
* :func:`build_staged_plan` / :func:`approve_stage` — the staged
  approvals (cut → look → render): a plan starts awaiting cut
  approval and advances one stage at a time; approving out of order
  is an error, never a skip.
* :func:`render_gate` / :func:`render_command` — Remotion rendering
  (~1.5 GB install) stays off-fleet like the OpenFilm leg: the gate
  REFUSES in-service rendering and names the allowed render hosts
  (owner machine / post-ARM). VyralX orchestrates; it does not render
  here.

Paid-path honesty: upstream needs a Claude account with a paid plan
or an API key to drive it, which conflicts with the fleet's free-only
rule for unattended server use. This leg runs NO Claude Code/plugin
step, takes no key, and promises no paid path; the constraint is
recorded on every plan (``claude_code``).

No network, no execution. Python 3.10.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

NEXTWORK_STYLE_VERSION = "vyr079-1"
NEXTWORK_REPO = "nextwork-projects/ai-video-editor-cooked"
NEXTWORK_LICENSE = "MIT"

MIN_REFERENCES = 3
MAX_REFERENCES = 6

# Caption treatments the style profile vouches for. Anything else is
# rejected, never silently passed on as "some captions".
CAPTION_STYLES = ("burned_in", "word_by_word", "static", "none")

# Transcript segment kinds. Only ``speech`` survives the cut.
KEPT_KINDS = ("speech",)
DROPPED_KINDS = ("retake", "false_start", "pause")

CLAUDE_CONSTRAINT = {
    "required_upstream": True,
    "used_here": False,
    "note": ("Upstream needs a Claude account with a paid plan or an "
             "API key to drive it; this adapt leg runs no Claude "
             "Code/plugin step, takes no key, and promises no paid path."),
}

STAGES = ("cut", "look", "render")


class StyleError(ValueError):
    """Raised when a style profile, cut, or staged approval is invalid."""


def _measure_number(measurements: dict[str, Any], field: str,
                    *, minimum: float, ref_label: str) -> float:
    value = measurements.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StyleError(f"{ref_label}: measurement {field!r} must be a "
                         f"number, got {value!r}")
    if float(value) < minimum:
        raise StyleError(f"{ref_label}: measurement {field!r} is "
                         f"{value}, below minimum {minimum}")
    return float(value)


def measure_style(name: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    """Average 3–6 same-format reference measurements into a style profile.

    Each reference is ``{"format": str, "duration_s": number,
    "measurements": {...}}`` with ``cuts_per_minute`` (>0),
    ``mean_shot_seconds`` (>0), ``zooms_per_minute`` (>=0),
    ``caption_style`` (closed set), ``cards_per_minute`` (>=0),
    ``graphics_density`` (0..1) and ``sound_bed`` (str).
    """
    if not str(name or "").strip():
        raise StyleError("style needs a non-empty name")
    if len(references) < MIN_REFERENCES:
        raise StyleError(
            f"need at least {MIN_REFERENCES} reference videos, got "
            f"{len(references)} (Nextwork measures a style from 3–6)")
    if len(references) > MAX_REFERENCES:
        raise StyleError(
            f"at most {MAX_REFERENCES} reference videos, got "
            f"{len(references)}")
    formats = {str(r.get("format", "")).strip() for r in references}
    if len(formats) != 1:
        raise StyleError(
            f"references must share one editing format, got {sorted(formats)}")
    fmt = formats.pop()
    if not fmt:
        raise StyleError("references must name their editing format")

    totals: dict[str, float] = {"cuts_per_minute": 0.0,
                                "mean_shot_seconds": 0.0,
                                "zooms_per_minute": 0.0,
                                "cards_per_minute": 0.0,
                                "graphics_density": 0.0}
    captions: set[str] = set()
    beds: set[str] = set()
    for i, ref in enumerate(references, 1):
        label = f"reference {i}"
        duration = ref.get("duration_s")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) \
                or float(duration) <= 0:
            raise StyleError(f"{label}: duration_s must be a positive "
                             f"number, got {duration!r}")
        m = ref.get("measurements")
        if not isinstance(m, dict):
            raise StyleError(f"{label}: missing measurements dict")
        for field in totals:
            value = _measure_number(m, field, minimum=0.0, ref_label=label)
            if field in ("cuts_per_minute", "mean_shot_seconds") \
                    and value <= 0:
                raise StyleError(f"{label}: measurement {field!r} must be "
                                 f"above 0, got {value}")
            if field == "graphics_density" and value > 1.0:
                raise StyleError(f"{label}: measurement 'graphics_density' "
                                 f"must be at most 1.0, got {value}")
            totals[field] += value
        caption = m.get("caption_style")
        if caption not in CAPTION_STYLES:
            raise StyleError(f"{label}: caption_style {caption!r} not in "
                             f"{CAPTION_STYLES}")
        captions.add(str(caption))
        bed = m.get("sound_bed")
        if not isinstance(bed, str):
            raise StyleError(f"{label}: sound_bed must be a string, got "
                             f"{bed!r}")
        beds.add(bed)
    n = len(references)
    if len(captions) != 1:
        raise StyleError(
            f"references must agree on one caption style, got "
            f"{sorted(captions)}")
    if len(beds) != 1:
        raise StyleError(
            f"references must agree on one sound bed, got {sorted(beds)}")
    return {
        "version": NEXTWORK_STYLE_VERSION,
        "name": name,
        "repo": NEXTWORK_REPO,
        "license": NEXTWORK_LICENSE,
        "format": fmt,
        "reference_count": n,
        "measurements": {
            "cuts_per_minute": round(totals["cuts_per_minute"] / n, 2),
            "mean_shot_seconds": round(totals["mean_shot_seconds"] / n, 2),
            "zooms_per_minute": round(totals["zooms_per_minute"] / n, 2),
            "caption_style": captions.pop(),
            "cards_per_minute": round(totals["cards_per_minute"] / n, 2),
            "graphics_density": round(totals["graphics_density"] / n, 2),
            "sound_bed": beds.pop(),
        },
        "claude_code": dict(CLAUDE_CONSTRAINT),
        "paid_services_used": False,
    }


def cut_transcript(transcript: list[dict[str, Any]],
                   style: dict[str, Any]) -> dict[str, Any]:
    """Cut a transcript to the style: drop retakes/false starts/pauses,
    re-cut kept speech into shots at the style's mean shot length.

    Transcript segments are ``{"text", "start_s", "duration_s",
    "kind"}``. Kept shots split long speech word-proportionally so
    each shot carries its own narration slice.
    """
    mean_shot = float(style["measurements"]["mean_shot_seconds"])
    kept, dropped, shots = [], [], []
    for i, seg in enumerate(transcript):
        kind = seg.get("kind", "speech")
        entry = {"index": i, "kind": kind,
                 "start_s": float(seg.get("start_s", 0) or 0),
                 "duration_s": float(seg.get("duration_s", 0) or 0),
                 "text": str(seg.get("text", ""))}
        if entry["duration_s"] <= 0:
            raise StyleError(f"transcript segment {i}: non-positive duration")
        if kind in DROPPED_KINDS:
            entry["reason"] = {"retake": "retake — re-recorded later",
                               "false_start": "false start — abandoned take",
                               "pause": "pause — dead air"}[kind]
            dropped.append(entry)
        elif kind in KEPT_KINDS:
            kept.append(entry)
        else:
            raise StyleError(f"transcript segment {i}: unknown kind "
                             f"{kind!r} (want speech/retake/false_start/pause)")
    if not kept:
        raise StyleError("transcript cut kept no speech — every segment "
                         "was a retake, false start or pause")
    for seg in kept:
        words = seg["text"].split()
        remaining = seg["duration_s"]
        start = seg["start_s"]
        wps = len(words) / seg["duration_s"] if seg["duration_s"] else 0
        word_idx = 0
        while remaining > 0:
            shot_s = min(mean_shot, remaining)
            take = max(1, round(shot_s * wps)) if words else 0
            take = min(take, len(words) - word_idx)
            shots.append({
                "shot_id": f"shot-{len(shots) + 1:02d}",
                "source_segment": seg["index"],
                "start_s": round(start, 2),
                "duration_s": round(shot_s, 2),
                "narration": " ".join(words[word_idx:word_idx + take]),
            })
            word_idx += take
            start += shot_s
            remaining = round(remaining - shot_s, 2)
    return {"kept_segments": kept, "dropped_segments": dropped,
            "shots": shots,
            "kept_seconds": round(sum(s["duration_s"] for s in kept), 2),
            "dropped_seconds": round(sum(s["duration_s"] for s in dropped), 2)}


def build_staged_plan(style: dict[str, Any], raw_clip: str,
                      transcript: list[dict[str, Any]], *,
                      asset_exists: Optional[Callable[[str], bool]] = None
                      ) -> dict[str, Any]:
    """Build the cut → look → render staged plan for one raw clip.

    Returns ``status="failed"`` with errors (and no stages) when the
    raw clip asset is missing; a missing ``asset_exists`` resolver is
    a warning, never a pass.
    """
    errors, warnings = [], []
    if not str(raw_clip or "").strip():
        errors.append("raw clip asset reference is empty")
    elif asset_exists is None:
        warnings.append(f"raw clip {raw_clip!r} unchecked "
                        "(no asset_exists resolver given)")
    elif not asset_exists(raw_clip):
        errors.append(f"missing raw clip asset {raw_clip!r}")
    if errors:
        return {"status": "failed", "style_version": NEXTWORK_STYLE_VERSION,
                "errors": errors, "warnings": warnings, "stages": [],
                "render": None}
    try:
        cut = cut_transcript(transcript, style)
    except StyleError as exc:
        return {"status": "failed", "style_version": NEXTWORK_STYLE_VERSION,
                "errors": [str(exc)], "warnings": warnings, "stages": [],
                "render": None}
    return {"status": "awaiting_cut_approval",
            "style_version": NEXTWORK_STYLE_VERSION,
            "style": style, "raw_clip": raw_clip,
            "cut": cut,
            "stages": [{"stage": s, "approved": False} for s in STAGES],
            "errors": [], "warnings": warnings, "render": None}


def approve_stage(plan: dict[str, Any], stage: str) -> dict[str, Any]:
    """Approve one stage, in order (cut → look → render).

    Returns the plan with its status advanced; approving out of order
    raises :class:`StyleError`.
    """
    if stage not in STAGES:
        raise StyleError(f"unknown stage {stage!r} (want {STAGES})")
    stages = plan.get("stages") or []
    idx = STAGES.index(stage)
    if any(not s["approved"] for s in stages[:idx]):
        raise StyleError(f"cannot approve {stage!r} before "
                         f"{STAGES[idx - 1]!r} is approved")
    if stages[idx]["approved"]:
        raise StyleError(f"stage {stage!r} is already approved")
    stages[idx]["approved"] = True
    if idx == 0:
        plan["status"] = "awaiting_look_approval"
    elif idx == 1:
        plan["status"] = "awaiting_render_approval"
    else:
        plan["status"] = "ready_to_render"
    return plan


def render_gate(*, host_role: str = "fleet_service") -> dict[str, Any]:
    """Where may this style render? Never inside the fleet service."""
    allowed = host_role in ("owner_machine", "post_arm")
    return {"allowed": allowed, "host_role": host_role,
            "reason": ("Remotion rendering plus the ~1.5 GB Nextwork "
                       "install exceeds the ~180MB fleet service cap"
                       if not allowed else
                       "render host is off-fleet / post-ARM"),
            "renders_in_service": False}


def render_command(plan: dict[str, Any], *,
                   host_role: str = "owner_machine") -> dict[str, Any]:
    """The Remotion render command for a fully-approved plan.

    Only issued when every stage is approved AND the host is allowed.
    This plan executes nothing.
    """
    gate = render_gate(host_role=host_role)
    if plan.get("status") != "ready_to_render":
        return {"available": False, **gate,
                "reason": f"plan is {plan.get('status')!r}, not "
                          "'ready_to_render' — all three stages (cut, look, "
                          "render) must be approved first"}
    if not gate["allowed"]:
        return {"available": False, **gate}
    return {"available": True, **gate,
            "argv": ["npx", "remotion", "render",
                     f"nextwork-style-{plan['style']['name']}",
                     "out.mp4"],
            "note": ("render the approved cut in the measured style on "
                     "the render host; this plan executes nothing")}


def adapt_nextwork_cut(*, style_name: str,
                       references: list[dict[str, Any]], raw_clip: str,
                       transcript: list[dict[str, Any]],
                       asset_exists: Optional[Callable[[str], bool]] = None
                       ) -> dict[str, Any]:
    """Run the Nextwork adapt leg end to end, repo-side.

    Measure the style from references, cut the transcript, and stage
    the cut → look → render plan. Any failure returns
    ``status="failed"`` with the errors and issues no render command.
    """
    try:
        style = measure_style(style_name, references)
    except StyleError as exc:
        return {"status": "failed", "style_version": NEXTWORK_STYLE_VERSION,
                "nextwork_repo": NEXTWORK_REPO,
                "license": NEXTWORK_LICENSE,
                "errors": [str(exc)], "warnings": [], "render": None}
    plan = build_staged_plan(style, raw_clip, transcript,
                             asset_exists=asset_exists)
    if plan["status"] == "failed":
        return {"status": "failed", "style_version": NEXTWORK_STYLE_VERSION,
                "nextwork_repo": NEXTWORK_REPO,
                "license": NEXTWORK_LICENSE, "style": style,
                "errors": plan["errors"], "warnings": plan["warnings"],
                "render": None}
    return {"status": "staged", "style_version": NEXTWORK_STYLE_VERSION,
            "nextwork_repo": NEXTWORK_REPO,
            "license": NEXTWORK_LICENSE, "style": style, "plan": plan,
            "render": None}
