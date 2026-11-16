"""VyralX stick-figure explainer scenes (TASK-IG3-VYR-02).

Wave-2 cluster 112 (IG source DemH26soPPx) is the Channel
Farm-style script-to-video pattern: a pasted script becomes an
animated stick-figure explainer. The script-to-video pipelines
existed (``shorts_factory``, ``short_video_assembly``) but the
stick-figure *style* did not: no template in the format registry
and no figure renderer anywhere (supervisor AUDIT-2 re-confirmed:
registry still exactly 6 templates, none stick-figure).

This module closes the style gap at the layer the fleet can
actually run:

* the ``stick_figure_explainer`` template now lives in
  ``app/data/format_templates.json`` (validated by
  ``format_templates`` like every other template);
* :func:`build_scenes` turns per-beat captions into a scene plan
  over that template: each beat gets a pose from a small vector
  pose vocabulary and a deterministic, self-contained **SVG**
  rendering of the figure layer (stdlib only — the same
  self-contained-artifact approach as the diagram service);
* video rendering itself stays off-fleet, exactly like
  ``film_pipeline``'s render gate: the plan is
  ``pending_review`` and publishes nothing.

The module carries its own FastAPI router, mounted by ``app.main``
at ``/api/v1`` (``POST /api/v1/stick-figure/scenes``,
``GET /api/v1/stick-figure/poses``) — the AUDIT-2 production-caller
standard: a library no production code calls is not delivered.

Pure stdlib + FastAPI router; no network. Python 3.10.
"""
from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import format_templates

FIGURE_VERSION = "ig3-vyr02-1"
TEMPLATE_ID = "stick_figure_explainer"

#: Canvas the pose vocabulary is drawn on (SVG user units).
CANVAS = (100, 100)
_HEAD = (50, 20, 9)          # cx, cy, r
_NECK = (50, 29)
_SHOULDER = (50, 33)
_HIP = (50, 54)

#: Joint coordinates per pose: elbow/hand per arm, knee/foot per leg.
POSES: dict[str, dict[str, tuple[int, int]]] = {
    "stand": {"elbow_l": (39, 44), "hand_l": (35, 56),
              "elbow_r": (61, 44), "hand_r": (65, 56),
              "knee_l": (44, 72), "foot_l": (43, 90),
              "knee_r": (56, 72), "foot_r": (57, 90)},
    "point": {"elbow_l": (40, 45), "hand_l": (36, 57),
              "elbow_r": (63, 32), "hand_r": (79, 28),
              "knee_l": (44, 72), "foot_l": (43, 90),
              "knee_r": (56, 72), "foot_r": (57, 90)},
    "shrug": {"elbow_l": (37, 38), "hand_l": (30, 30),
              "elbow_r": (63, 38), "hand_r": (70, 30),
              "knee_l": (44, 72), "foot_l": (43, 90),
              "knee_r": (56, 72), "foot_r": (57, 90)},
    "walk": {"elbow_l": (41, 45), "hand_l": (35, 55),
             "elbow_r": (60, 42), "hand_r": (67, 50),
             "knee_l": (41, 70), "foot_l": (33, 86),
             "knee_r": (61, 68), "foot_r": (71, 84)},
    "jump": {"elbow_l": (38, 24), "hand_l": (31, 13),
             "elbow_r": (62, 24), "hand_r": (69, 13),
             "knee_l": (43, 66), "foot_l": (41, 76),
             "knee_r": (57, 66), "foot_r": (59, 76)},
    "think": {"elbow_l": (40, 45), "hand_l": (36, 57),
              "elbow_r": (61, 42), "hand_r": (53, 28),
              "knee_l": (44, 72), "foot_l": (43, 90),
              "knee_r": (56, 72), "foot_r": (57, 90)},
    "celebrate": {"elbow_l": (37, 23), "hand_l": (29, 11),
                  "elbow_r": (63, 23), "hand_r": (71, 11),
                  "knee_l": (43, 72), "foot_l": (38, 90),
                  "knee_r": (57, 72), "foot_r": (62, 90)},
    "present": {"elbow_l": (37, 33), "hand_l": (23, 33),
                "elbow_r": (63, 33), "hand_r": (77, 33),
                "knee_l": (44, 72), "foot_l": (43, 90),
                "knee_r": (56, 72), "foot_r": (57, 90)},
}

#: Template beat -> pose. Beats outside the map use "stand".
BEAT_POSES = {"hook_pose": "point", "setup": "stand",
              "build_up": "present", "aha_pose": "celebrate",
              "recap_line": "think"}


def pose_for_beat(beat: str) -> str:
    return BEAT_POSES.get(beat, "stand")


def figure_primitives(pose: str) -> dict[str, Any]:
    """The drawing primitives for one pose: a head circle + segments.

    Segments are (x1, y1, x2, y2) tuples: torso, both arms
    (shoulder -> elbow -> hand), both legs (hip -> knee -> foot).
    """
    if pose not in POSES:
        raise ValueError(f"unknown stick-figure pose: {pose!r}")
    j = POSES[pose]
    segments = [
        (_NECK[0], _NECK[1], _HIP[0], _HIP[1]),
        (_SHOULDER[0], _SHOULDER[1], *j["elbow_l"]),
        (*j["elbow_l"], *j["hand_l"]),
        (_SHOULDER[0], _SHOULDER[1], *j["elbow_r"]),
        (*j["elbow_r"], *j["hand_r"]),
        (_HIP[0], _HIP[1], *j["knee_l"]),
        (*j["knee_l"], *j["foot_l"]),
        (_HIP[0], _HIP[1], *j["knee_r"]),
        (*j["knee_r"], *j["foot_r"]),
    ]
    return {"head": _HEAD, "segments": segments}


def render_svg(pose: str, caption: str = "") -> str:
    """One scene's figure layer as a self-contained SVG string.

    Deterministic: same pose + caption always yields the same SVG.
    The caption is XML-escaped — captions are script text, never
    markup.
    """
    prim = figure_primitives(pose)
    cx, cy, r = prim["head"]
    lines = "".join(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
        for x1, y1, x2, y2 in prim["segments"])
    text = (f'<text x="50" y="97" text-anchor="middle" '
            f'font-size="5">{escape(caption)}</text>') if caption else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {CANVAS[0]} {CANVAS[1]}" '
            f'stroke="black" stroke-width="2.5" fill="none" '
            f'stroke-linecap="round">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}"/>{lines}{text}</svg>')


def build_scenes(captions: list[str], *,
                 target_seconds: float = 45.0,
                 lane: str = "tech_ai") -> dict[str, Any]:
    """A stick-figure scene plan from per-beat captions.

    ``captions`` aligns with the template's beats in order. Fewer
    captions than beats is recorded in ``missing_captions`` (the
    affected scenes render without text) — never silently padded;
    more captions than beats is refused, because a caption with no
    beat is a script error, not a scene.
    """
    template = format_templates.get_template(TEMPLATE_ID)
    if lane not in template["lanes"]:
        raise ValueError(f"lane {lane!r} not in template lanes "
                         f"{template['lanes']}")
    plan = format_templates.instantiate(TEMPLATE_ID, target_seconds)
    beats = plan["beats"]
    if len(captions) > len(beats):
        raise ValueError(f"{len(captions)} captions for "
                         f"{len(beats)} template beats")
    scenes, missing = [], []
    for i, beat in enumerate(beats):
        caption = str(captions[i]) if i < len(captions) else ""
        if not caption:
            missing.append(beat["beat"])
        pose = pose_for_beat(beat["beat"])
        scenes.append({"beat": beat["beat"], "note": beat["note"],
                       "start": beat["start"], "end": beat["end"],
                       "pose": pose, "caption": caption,
                       "svg": render_svg(pose, caption)})
    return {
        "kind": "stick_figure_scene_plan",
        "version": FIGURE_VERSION,
        "template_id": TEMPLATE_ID,
        "lane": lane,
        "target_seconds": target_seconds,
        "within_template_range": plan["within_template_range"],
        "scenes": scenes,
        "missing_captions": missing,
        "hard_rules": template["hard_rules"],
        "status": "pending_review",
        "privacy": "unlisted",
        "publish": False,
        "render": "svg scene layer only — video rendering stays "
                  "off-fleet (film_pipeline render-gate pattern)",
    }


def enqueue_scene_plan(plan: dict[str, Any],
                       queue_path: Any = None) -> int:
    """Append a scene plan to the VYR-004 review queue. Returns 1.

    The remix_flow import is lazy: the scene builder stays
    importable (and testable) without the queue's dependency chain.
    """
    from app.services import remix_flow

    remix_flow.enqueue_review({
        "kind": plan["kind"], "version": plan["version"],
        "template_id": plan["template_id"], "lane": plan["lane"],
        "target_seconds": plan["target_seconds"],
        "scene_count": len(plan["scenes"]),
        "missing_captions": plan["missing_captions"],
        "status": plan["status"], "publish": False,
    }, queue_path)
    return 1


router = APIRouter()


class ScenesRequest(BaseModel):
    captions: list[str]
    target_seconds: float = 45.0
    lane: str = "tech_ai"
    enqueue: bool = False


@router.get("/stick-figure/poses")
def stick_figure_poses() -> dict[str, Any]:
    return {"version": FIGURE_VERSION, "poses": sorted(POSES),
            "beat_poses": BEAT_POSES, "canvas": CANVAS}


@router.post("/stick-figure/scenes")
def stick_figure_scenes(req: ScenesRequest) -> dict[str, Any]:
    try:
        plan = build_scenes(req.captions,
                            target_seconds=req.target_seconds,
                            lane=req.lane)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if req.enqueue:
        plan["enqueued"] = enqueue_scene_plan(plan)
    return plan
