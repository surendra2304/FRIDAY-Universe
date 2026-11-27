"""VyralX OpenFilm adapter — TASK-VYR-079 checkpoint 2 (adapt leg 1 of 4).

Adapts openfilm/openfilm (MIT, registry fit ``adapt``) into VyralX's
live path. Registry card (``IntelX/intelx/registries/scouted_repos.json``,
``openfilm.md``): an AI video agent writes a film as ONE ``film.html``
whose tracks cut together pages, footage, stills and sound, each shot
drawn by a ``frame(t)`` function, rendered to MP4 via headless
Chromium + FFmpeg; ships Studio, a browser editor with a real timeline.
Install is ``npx skills add openfilm/openfilm``; requires Node 22.2+
and FFmpeg (first run downloads ~100 MB of Chromium).

VyralX-native implementation (stdlib only, no Node/Chromium here):

* :func:`validate_openfilm_film` — the OpenFilm-pattern conformance
  check on a :mod:`film_pipeline` manifest: every shot carries a
  well-formed ``frame(t)`` descriptor from the supported set, every
  footage/stills shot resolves its asset through the caller's
  ``asset_exists`` check (a missing asset FAILS the film — never
  claimed present without a check), every shot has content, shot
  kinds are restricted to the OpenFilm track set, durations sum to
  the manifest total and the Shorts cap is re-checked.
* :func:`adapt_openfilm_film` — the end-to-end adapt leg: build the
  film, render the single ``film.html``, validate, and gate the
  render. A validation failure returns ``status="failed"`` with the
  errors and issues NO render command. Rendering stays off-fleet
  (see :func:`film_pipeline.render_gate`): VyralX orchestrates, it
  does not render here.

No network, no execution. Python 3.10.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from app.services import film_pipeline as fp

OPENFILM_ADAPTER_VERSION = "vyr079-1"
OPENFILM_REPO = "openfilm/openfilm"
OPENFILM_LICENSE = "MIT"

# frame(t) descriptors VyralX emits into film.html. OpenFilm's own
# frame(t) functions are arbitrary JS; VyralX only vouches for this
# closed set — anything else is rejected, never silently passed on.
KNOWN_FRAME_FNS = ("fadeIn", "fadeOut", "slideLeft", "slideRight",
                   "zoomIn", "zoomOut", "hold", "cut")
_FRAME_FN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(t(?:\s*,[^)]*)?\)$")

# Shot kinds the OpenFilm track set covers. ``video`` is accepted as
# an alias of ``footage`` (the pipeline's own default is ``page``).
SHOT_KINDS = ("page", "footage", "video", "stills")
ASSET_KINDS = ("footage", "video", "stills")


def validate_frame_fn(frame_fn: str, *, shot_id: str) -> Optional[str]:
    """Return an error string for a bad ``frame(t)`` descriptor, else None."""
    if not isinstance(frame_fn, str) or not frame_fn.strip():
        return f"shot {shot_id}: missing frame(t) descriptor"
    m = _FRAME_FN_RE.match(frame_fn.strip())
    if m is None:
        return (f"shot {shot_id}: malformed frame(t) descriptor "
                f"{frame_fn!r} (want Name(t[, ...]))")
    if m.group(1) not in KNOWN_FRAME_FNS:
        return (f"shot {shot_id}: unknown frame(t) function "
                f"{m.group(1)!r} (supported: {', '.join(KNOWN_FRAME_FNS)})")
    return None


def validate_openfilm_film(
        film: dict[str, Any], *,
        asset_exists: Optional[Callable[[str], bool]] = None
) -> dict[str, Any]:
    """Check a film manifest against the OpenFilm pattern.

    ``asset_exists`` maps an asset reference to True/False. When it is
    None, asset references are reported ``unchecked`` (a warning, never
    a pass): the adapter never claims footage exists without a check.
    """
    errors, warnings, assets_checked, assets_missing = [], [], [], []
    if film.get("version") != fp.FILM_VERSION:
        errors.append(f"manifest version {film.get('version')!r} != "
                      f"{fp.FILM_VERSION!r}")
    shots = film.get("shots") or []
    if not shots:
        errors.append("film has no shots")
    total = 0.0
    for s in shots:
        sid = s.get("shot_id", "?")
        total += float(s.get("duration", 0) or 0)
        if s.get("kind") not in SHOT_KINDS:
            errors.append(f"shot {sid}: kind {s.get('kind')!r} not in "
                          f"OpenFilm track set {SHOT_KINDS}")
        if not (s.get("html") or s.get("text")):
            errors.append(f"shot {sid}: no content (empty html and text)")
        err = validate_frame_fn(s.get("frame_fn", ""), shot_id=sid)
        if err:
            errors.append(err)
        asset = s.get("asset", "")
        if s.get("kind") in ASSET_KINDS and asset:
            if asset_exists is None:
                warnings.append(f"shot {sid}: asset {asset!r} unchecked "
                                "(no asset_exists resolver given)")
            elif asset_exists(asset):
                assets_checked.append(asset)
            else:
                assets_missing.append(asset)
                errors.append(f"shot {sid}: missing footage asset {asset!r}")
    if shots and abs(total - float(film.get("duration", total) or total)) > 0.01:
        errors.append(f"shot durations sum to {total:.2f}s but manifest "
                      f"duration is {film.get('duration')}s")
    if film.get("kind") == "short" and total > fp.MAX_SHORT_SECONDS:
        errors.append(f"short film is {total:.1f}s > "
                      f"{fp.MAX_SHORT_SECONDS}s cap")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "shots_checked": len(shots), "assets_checked": assets_checked,
            "assets_missing": assets_missing,
            "adapter_version": OPENFILM_ADAPTER_VERSION}


def adapt_openfilm_film(
        *, title: str, lane: str, shots: list[dict[str, Any]],
        kind: str = "short", voice_track: str = "", music_track: str = "",
        asset_exists: Optional[Callable[[str], bool]] = None,
        host_role: str = "fleet_service") -> dict[str, Any]:
    """Run the OpenFilm adapt leg end to end, repo-side.

    Returns evidence: the manifest, the rendered ``film.html``, the
    validation report, and the render gate/command. On any failure
    ``status`` is ``"failed"`` and no render command is issued.
    """
    film = fp.build_film(title=title, lane=lane, shots=shots, kind=kind,
                         voice_track=voice_track, music_track=music_track)
    page = fp.render_film_html(film)
    validation = validate_openfilm_film(film, asset_exists=asset_exists)
    if not validation["ok"]:
        return {"status": "failed", "adapter_version": OPENFILM_ADAPTER_VERSION,
                "openfilm_repo": OPENFILM_REPO, "license": OPENFILM_LICENSE,
                "film": film, "film_html": page, "validation": validation,
                "render": None}
    gate = fp.render_gate(host_role=host_role)
    render = (fp.render_command(film, host_role=host_role)
              if gate["allowed"] else {"available": False, **gate})
    return {"status": "adapted", "adapter_version": OPENFILM_ADAPTER_VERSION,
            "openfilm_repo": OPENFILM_REPO, "license": OPENFILM_LICENSE,
            "film": film, "film_html": page, "validation": validation,
            "render": render}
