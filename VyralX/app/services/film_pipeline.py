"""VyralX film-as-HTML pipeline — OpenFilm pattern (TASK-IG2-VYR-05).

Pattern adapted from openfilm/openfilm (MIT; spec card ``openfilm.md``,
IG source Dep0wuhvizo): a film is ONE ``film.html`` whose tracks cut
together pages, footage, stills and sound; each shot is drawn by a
``frame(t)`` function; a Studio-style edit layer lets a human trim,
move, restyle or retype anything the agent made before rendering.

VyralX-native implementation (stdlib only, no Node/Chromium here):

* :func:`build_film` — a film manifest from VyralX scenes (lane,
  title, shots with per-shot ``frame_fn`` descriptors, audio/voice
  track, caption track), validated (durations, Shorts <60s when
  ``kind="short"``, lanes restricted to the channel's three).
* :func:`render_film_html` — the single self-contained film.html:
  one ``<section class="shot">`` per shot with its ``frame(t)``
  script, tracks declared as data attributes — the artefact a
  Studio-style editor or the off-fleet renderer consumes.
* :func:`apply_studio_edit` — the hand-edit layer: trim / move /
  restyle / retype operations applied to the manifest, each recorded
  in an edit log; the film stays ``pending_review`` after any edit.
* :func:`render_gate` / :func:`render_command` — rendering is
  headless-Chromium work, too heavy for a ~180MB service on the
  ~956MB fleet (same constraint as HyperFrames): the gate REFUSES
  in-service rendering and names the allowed render hosts (owner
  machine / post-ARM). VyralX orchestrates; it does not render here.

No network, no execution. Python 3.10.
"""
from __future__ import annotations

import html
import json
from typing import Any

FILM_VERSION = "ig2-vyr05-1"
LANES = ("space_science", "history", "tech_ai")
MAX_SHORT_SECONDS = 59.0
TRACK_KINDS = ("video", "stills", "page", "voice", "music", "captions")


def build_film(*, title: str, lane: str, shots: list[dict[str, Any]],
               kind: str = "short", voice_track: str = "",
               music_track: str = "") -> dict[str, Any]:
    """Validate and assemble a film manifest. Raises on bad input."""
    if lane not in LANES:
        raise ValueError(f"lane {lane!r} not in VyralX lanes {LANES}")
    if not shots:
        raise ValueError("a film needs at least one shot")
    norm, t = [], 0.0
    for i, s in enumerate(shots, 1):
        dur = float(s.get("duration", 0))
        if dur <= 0:
            raise ValueError(f"shot {i} has non-positive duration")
        norm.append({"shot_id": s.get("shot_id", f"shot-{i:02d}"),
                     "kind": s.get("kind", "page"),
                     "start": round(t, 2), "duration": dur,
                     "end": round(t + dur, 2),
                     "html": s.get("html", ""),
                     "text": s.get("text", ""),
                     "frame_fn": s.get("frame_fn", "fadeIn(t)"),
                     "asset": s.get("asset", "")})
        t += dur
    if kind == "short" and t > MAX_SHORT_SECONDS:
        raise ValueError(f"short film is {t:.1f}s > {MAX_SHORT_SECONDS}s cap")
    tracks = [{"kind": "video", "shots": [s["shot_id"] for s in norm]},
              {"kind": "captions", "source": "shot text"}]
    if voice_track:
        tracks.append({"kind": "voice", "asset": voice_track})
    if music_track:
        tracks.append({"kind": "music", "asset": music_track})
    return {"version": FILM_VERSION, "title": title, "lane": lane,
            "kind": kind, "duration": round(t, 2), "shots": norm,
            "tracks": tracks, "status": "pending_review",
            "privacy": "unlisted", "publish": False, "edit_log": []}


def render_film_html(film: dict[str, Any]) -> str:
    """The single film.html artefact (OpenFilm's one-file format)."""
    sections = []
    for s in film["shots"]:
        sections.append(
            f'<section class="shot" data-shot="{html.escape(s["shot_id"])}" '
            f'data-start="{s["start"]}" data-duration="{s["duration"]}" '
            f'data-frame="{html.escape(s["frame_fn"])}">'
            f'{s["html"] or html.escape(s["text"])}</section>')
    tracks = ",".join(t["kind"] for t in film["tracks"])
    return ("<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(film['title'])}</title></head>"
            f'<body data-film-version="{FILM_VERSION}" data-tracks="{tracks}">'
            + "\n".join(sections)
            + "<script>function frame(t){document.querySelectorAll('.shot')"
              ".forEach(function(el){var st=parseFloat(el.dataset.start),"
              "du=parseFloat(el.dataset.duration);"
              "el.style.display=(t>=st&&t<st+du)?'block':'none';});}</script>"
              "</body></html>")


def apply_studio_edit(film: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any]:
    """Apply one Studio-style edit (trim/move/restyle/retype).

    Returns a NEW manifest with the edit logged; timing is recomputed
    after trim/move. Unknown ops and unknown shots raise — an edit is
    never silently dropped.
    """
    op = edit.get("op")
    if op not in ("trim", "move", "restyle", "retype"):
        raise ValueError(f"unknown studio edit op {op!r}")
    out = json.loads(json.dumps(film))
    shot = next((s for s in out["shots"] if s["shot_id"] == edit.get("shot_id")), None)
    if shot is None:
        raise ValueError(f"no shot {edit.get('shot_id')!r}")
    if op == "trim":
        shot["duration"] = float(edit["duration"])
        if shot["duration"] <= 0:
            raise ValueError("trim duration must be positive")
    elif op == "move":
        out["shots"].remove(shot)
        out["shots"].insert(int(edit["to_index"]), shot)
    elif op == "restyle":
        shot["html"] = str(edit["html"])
    elif op == "retype":
        shot["text"] = str(edit["text"])
    t = 0.0
    for s in out["shots"]:
        s["start"], s["end"] = round(t, 2), round(t + s["duration"], 2)
        t += s["duration"]
    out["duration"] = round(t, 2)
    if out["kind"] == "short" and t > MAX_SHORT_SECONDS:
        raise ValueError("edit would push the short past the 59s cap")
    out["edit_log"] = out.get("edit_log", []) + [{"op": op, **{k: v for k, v in edit.items() if k != "op"}}]
    out["status"] = "pending_review"
    return out


def render_gate(*, host_role: str = "fleet_service") -> dict[str, Any]:
    """Where may this film render? Never inside the fleet service."""
    allowed = host_role in ("owner_machine", "post_arm")
    return {"allowed": allowed, "host_role": host_role,
            "reason": "headless-Chromium rendering exceeds the ~180MB "
                      "fleet service cap" if not allowed else
                      "render host is off-fleet / post-ARM",
            "renders_in_service": False}


def render_command(film: dict[str, Any], *, host_role: str = "owner_machine") -> dict[str, Any]:
    gate = render_gate(host_role=host_role)
    if not gate["allowed"]:
        return {"available": False, **gate}
    return {"available": True, **gate,
            "argv": ["ffmpeg", "-i", "film.html.render.mp4",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "film.mp4"],
            "note": "render film.html with headless Chromium to "
                    "film.html.render.mp4 on the render host, then encode; "
                    "this plan executes nothing"}
