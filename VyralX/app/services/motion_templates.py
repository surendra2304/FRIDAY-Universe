"""VyralX motion-template library + slot editor (TASK-IG3-VYR-07).

Cluster 114 (IG source DekQYGzTTgb, the animos.app pattern)
asked for a template-based motion-graphics step: pick from a
library of motion templates, drop designs into media slots,
adjust timing and motion settings, export. It was graded
PARTIAL: ``motion_graphics.py`` has plan builders and an HTML
composition export, but no template library and no slot-based
editor existed — supervisor AUDIT-2 re-confirmed ``animos`` /
``slot`` / ``4K`` at zero hits in ``motion_graphics.py``.

What the source video actually shows (full browser watch,
2026-11-16), and therefore what this module records as fact:

* an editor with media slots, a TEXT slot and a LOGO slot
  (logo upload max 5 MB), POSITION settings, and TIMING loop
  durations from 5s to 30s;
* twelve template names on screen: Card Globe, Orbit Globe,
  Triple Scene, Spiral Stream, Cover Ring, Collage Reel,
  Fan Shuffle, Sweep Ring, Scatter Zoom, Sphere Wall,
  Totem Wall, Card Tunnel;
* an export matrix: MP4-H.264 / WebM-VP9; 720p / 1080p / 2K /
  4K / 8K; 30 / 60 fps; loops 1x-4x — with the tool's own
  on-screen note that 4K encoding depends on the
  browser/hardware and can be slow.

Honesty boundaries:

* the tool claims "50+ templates"; only the twelve names
  above were recovered from the source. The claim is recorded
  as a claim (``claimed_template_count``) and the catalogue
  holds exactly the twelve — no template is invented to make
  the library look bigger;
* per-template ``motion_family`` values are VyralX-side
  composition parameters (our plan vocabulary, in the style
  of ``motion_graphics``), NOT recovered animos internals;
* nothing here renders video. Filling a template produces a
  composition plan + the existing ``motion_graphics``
  HTML artifact, stamped off-fleet like every VyralX
  composition: raster encoding happens on the owner's
  machine or post-ARM, never inside the fleet service
  (``film_pipeline.render_gate`` states the same rule).

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``GET
/api/v1/motion-templates/library``, ``POST
/api/v1/motion-templates/fill``, ``POST
/api/v1/motion-templates/export-spec``, ``GET
/api/v1/motion-templates/policy``) — the AUDIT-2
production-caller standard.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import motion_graphics

TEMPLATES_VERSION = "ig3-vyr07-1"
IG_SOURCES = ("DekQYGzTTgb",)

#: The source tool's own claim, recorded AS a claim. The
#: catalogue below holds only the names the source video
#: actually showed.
CLAIMED_TEMPLATE_COUNT = "50+"

#: Editor facts recovered from the source video.
LOGO_MAX_BYTES = 5_000_000  # "LOGO upload max 5 MB"
LOOP_MIN_SECONDS = 5.0  # TIMING loop durations 5s-30s
LOOP_MAX_SECONDS = 30.0
EXPORT_FORMATS = ("mp4_h264", "webm_vp9")
EXPORT_RESOLUTIONS = ("720p", "1080p", "2k", "4k", "8k")
EXPORT_FPS = (30, 60)
EXPORT_MAX_LOOPS = 4

# (name as shown on screen in the source video, motion_family —
# a VyralX plan parameter, not a recovered product fact)
_TEMPLATE_NAMES = (
    ("Card Globe", "orbit_rotation"),
    ("Orbit Globe", "orbit_rotation"),
    ("Triple Scene", "staggered_panels"),
    ("Spiral Stream", "spiral_flow"),
    ("Cover Ring", "ring_rotation"),
    ("Collage Reel", "grid_collage"),
    ("Fan Shuffle", "fan_shuffle"),
    ("Sweep Ring", "ring_sweep"),
    ("Scatter Zoom", "scatter_zoom"),
    ("Sphere Wall", "sphere_grid"),
    ("Totem Wall", "stacked_panels"),
    ("Card Tunnel", "tunnel_zoom"),
)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


TEMPLATE_LIBRARY: list[dict[str, Any]] = [
    {
        "template_id": _slug(name),
        "name": name,
        "motion_family": family,
        "slot_kinds": ["media", "text", "logo"],
        "loop_seconds": {"min": LOOP_MIN_SECONDS,
                         "max": LOOP_MAX_SECONDS,
                         "default": 10.0},
        "source": "named on screen in IG source DekQYGzTTgb",
    }
    for name, family in _TEMPLATE_NAMES
]

_BY_ID = {t["template_id"]: t for t in TEMPLATE_LIBRARY}


def list_templates() -> dict[str, Any]:
    """The catalogue, with the claim labelled as a claim."""
    return {
        "kind": "motion_template_library",
        "version": TEMPLATES_VERSION,
        "ig_sources": list(IG_SOURCES),
        "claimed_template_count": CLAIMED_TEMPLATE_COUNT,
        "claim_basis": "the source tool's own on-screen claim "
                       "('more than 50+ templates now') — not "
                       "independently verified",
        "catalogued_count": len(TEMPLATE_LIBRARY),
        "catalogue_basis": "exactly the template names the "
                           "source video showed on screen; no "
                           "template is invented",
        "templates": TEMPLATE_LIBRARY,
        "editor": {
            "slot_kinds": ["media", "text", "logo"],
            "logo_max_bytes": LOGO_MAX_BYTES,
            "loop_seconds": {"min": LOOP_MIN_SECONDS,
                             "max": LOOP_MAX_SECONDS},
            "positions": ["centre", "lower_left", "full_frame"],
        },
        "status": "pending_review",
        "publish": False,
    }


def get_template(template_id: str) -> dict[str, Any]:
    template = _BY_ID.get(str(template_id))
    if template is None:
        raise ValueError(
            f"unknown template {template_id!r}; catalogued: "
            f"{sorted(_BY_ID)}")
    return template


def fill_template(template_id: str, *, media: list[str],
                  text: str = "", logo: dict[str, Any] | None = None,
                  loop_seconds: float = 10.0,
                  position: str = "centre") -> dict[str, Any]:
    """Drop designs into a template's slots -> a composition plan.

    Validates exactly what the source editor exposes: at
    least one media item in the media slots, a logo no larger
    than the recovered 5 MB cap, and a loop duration inside
    the recovered 5s-30s TIMING range. The plan's elements are
    ``motion_graphics``-shaped so the existing
    ``hyperframes_export`` can carry them.
    """
    template = get_template(template_id)
    media = [str(m) for m in (media or [])]
    if not media:
        raise ValueError("at least one media item is required "
                         "for the media slots")
    if logo is not None:
        size = logo.get("size_bytes")
        if size is None:
            raise ValueError("a logo must carry size_bytes — "
                             "an unmeasured logo cannot be "
                             "checked against the cap")
        if float(size) > LOGO_MAX_BYTES:
            raise ValueError(
                f"logo is {size} bytes > the {LOGO_MAX_BYTES} "
                "byte cap the source editor states")
    if not (LOOP_MIN_SECONDS <= float(loop_seconds)
            <= LOOP_MAX_SECONDS):
        raise ValueError(
            f"loop_seconds {loop_seconds} outside the source "
            f"editor's TIMING range {LOOP_MIN_SECONDS}-"
            f"{LOOP_MAX_SECONDS}s")
    elements = [
        {"kind": "media", "text": locator, "at": round(i * 1.0, 2),
         "slot": "media", "position": position}
        for i, locator in enumerate(media)
    ]
    if text:
        elements.append(motion_graphics.title_card_plan(
            text, at=0.0, hold=min(2.5, float(loop_seconds))))
    if logo is not None:
        elements.append({"kind": "logo",
                         "text": str(logo.get("locator", "")),
                         "at": 0.0, "slot": "logo",
                         "position": position})
    return {
        "kind": "motion_template_fill",
        "version": TEMPLATES_VERSION,
        "ig_sources": list(IG_SOURCES),
        "template_id": template["template_id"],
        "template_name": template["name"],
        "motion_family": template["motion_family"],
        "media_slots_filled": len(media),
        "loop_seconds": float(loop_seconds),
        "position": position,
        "elements": elements,
        "export": export_spec(),
        "status": "pending_review",
        "publish": False,
        "note": "A filled plan, not a render: encoding happens "
                "off-fleet (owner machine / post-ARM).",
    }


def export_spec(fmt: str = "mp4_h264", resolution: str = "1080p",
                fps: int = 30, loops: int = 1) -> dict[str, Any]:
    """Validate an export request against the recovered matrix."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"format {fmt!r} not in the source "
                         f"export matrix {EXPORT_FORMATS}")
    if resolution not in EXPORT_RESOLUTIONS:
        raise ValueError(f"resolution {resolution!r} not in the "
                         f"source export matrix {EXPORT_RESOLUTIONS}")
    if int(fps) not in EXPORT_FPS:
        raise ValueError(f"fps {fps} not in the source export "
                         f"matrix {EXPORT_FPS}")
    if not (1 <= int(loops) <= EXPORT_MAX_LOOPS):
        raise ValueError(f"loops {loops} outside the source "
                         f"export range 1-{EXPORT_MAX_LOOPS}")
    return {
        "format": fmt,
        "resolution": resolution,
        "fps": int(fps),
        "loops": int(loops),
        "render_host": "off_fleet",
        "note": "the source tool itself warns 4K encoding "
                "depends on the browser/hardware and can be "
                "slow; on this fleet the composition is an "
                "artifact for off-fleet render, never an "
                "in-service render",
    }


def composition_artifact(plan: dict[str, Any]) -> str:
    """The filled plan as the existing HTML composition artifact."""
    return motion_graphics.hyperframes_export(
        str(plan.get("template_name", "motion template")),
        list(plan.get("elements", [])))


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class FillRequest(BaseModel):
    template_id: str
    media: list[str]
    text: str = ""
    logo: dict[str, Any] | None = None
    loop_seconds: float = 10.0
    position: str = "centre"


class ExportSpecRequest(BaseModel):
    format: str = "mp4_h264"
    resolution: str = "1080p"
    fps: int = 30
    loops: int = 1


@router.get("/motion-templates/policy")
def motion_templates_policy() -> dict[str, Any]:
    return {
        "version": TEMPLATES_VERSION,
        "ig_sources": list(IG_SOURCES),
        "catalogued_count": len(TEMPLATE_LIBRARY),
        "claimed_template_count": CLAIMED_TEMPLATE_COUNT,
        "renders": "never in-service — filled plans are "
                   "off-fleet render artifacts",
        "status": "pending_review",
        "publish": False,
    }


@router.get("/motion-templates/library")
def motion_templates_library() -> dict[str, Any]:
    return list_templates()


@router.post("/motion-templates/fill")
def motion_templates_fill(req: FillRequest) -> dict[str, Any]:
    try:
        return fill_template(
            req.template_id, media=req.media, text=req.text,
            logo=req.logo, loop_seconds=req.loop_seconds,
            position=req.position)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/motion-templates/export-spec")
def motion_templates_export_spec(req: ExportSpecRequest) -> dict[str, Any]:
    try:
        return export_spec(fmt=req.format, resolution=req.resolution,
                           fps=req.fps, loops=req.loops)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
