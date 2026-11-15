"""VyralX previs / storyboarding (TASK-IG-VYR-06).

The IG reference corpus item DfOm-NzEbw0 shows **MGPREVIS**: a
browser-based AI-video previsualisation tool driven by an agent
over MCP — plan the video shot by shot before producing it.
MGPREVIS has no verified public repository (see
``ig-references/repos/INDEX.md``: named in the video, not
verified), so — as with the other corpus patterns — this module
implements the pattern natively in VyralX rather than adopting a
tool that may not exist as described.

The previs contract:

* A script becomes a **storyboard**: one shot per narration beat,
  each with a duration estimate from its word count.
* Every shot names its **visual source strategy** before any
  render is contemplated:
    - ``catalogue`` — matched to a stocked, licence-carrying clip
      from the lane catalogues (TASK-VYR-006/011/012), with the
      clip's catalogue id and licence attached;
    - ``generated_via_intake`` — AI-generated footage, which may
      only enter production through the provenance intake
      (TASK-IG-VYR-07); the storyboard records the intent, never
      the footage;
    - ``owner_upload`` — the owner's own media;
    - ``unresolved`` — no lawful source identified yet.
* A storyboard with unresolved shots is **incomplete** and says so
  on its face. Previs exists precisely to surface that BEFORE a
  render, instead of the pipeline discovering it mid-job — or
  worse, papering over it with unlicensed media (the failure the
  VYR-004 licence gate exists to prevent).

Storyboards enqueue into the VYR-004 review queue as
``pending_review``. Nothing renders from a storyboard in this
module. Pure functions over plain dicts; no network. Python 3.10.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.services import remix_flow, source_catalog, source_catalog_lane2, source_catalog_lane3

PREVIS_VERSION = "ig-vyr06-1"
WORDS_PER_SECOND = 2.6  # ~156 wpm narration, as in the factory

_LANE_CATALOGUES = {
    "space_science": source_catalog,
    "history": source_catalog_lane2,
    "tech_ai": source_catalog_lane3,
}
_STOPWORDS = {"the", "a", "an", "of", "and", "how", "why", "what",
              "story", "true", "did", "you", "know", "this", "that",
              "with", "from", "into", "then", "than"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", str(text or "").casefold())
            if t not in _STOPWORDS}


def split_beats(script: str) -> list[str]:
    """Split a script into narration beats (sentences / lines)."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(script or ""))
    return [p.strip() for p in parts if p.strip()]


def _match_clip(beat: str, pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    want = _tokens(beat)
    best: tuple[int, str, dict[str, Any]] | None = None
    for clip in pool:
        have = _tokens(clip.get("title", "")) | _tokens(
            " ".join(clip.get("topic_tags") or []))
        overlap = len(want & have)
        if overlap and (best is None or overlap > best[0] or
                        (overlap == best[0]
                         and str(clip.get("catalog_id")) < best[1])):
            best = (overlap, str(clip.get("catalog_id") or ""), clip)
    return best[2] if best else None


def build_storyboard(script: str, lane: str,
                     clips: Iterable[dict[str, Any]] | None = None,
                     generated_beats: Iterable[int] = (),
                     owner_beats: Iterable[int] = ()) -> dict[str, Any]:
    """Build a storyboard from a script for one lane.

    ``generated_beats`` / ``owner_beats`` are 1-based beat numbers
    the caller intends to source from AI generation (via the
    provenance intake) or the owner's own media; every other beat
    is matched against the lane catalogue, and a beat with no match
    is ``unresolved`` — visibly, in the output.
    """
    module = _LANE_CATALOGUES.get(lane)
    if module is None:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of "
            f"{sorted(_LANE_CATALOGUES)}")
    beats = split_beats(script)
    if not beats:
        raise ValueError("script must not be empty")
    pool = list(clips) if clips is not None else module.load_clips()
    generated = set(generated_beats)
    owned = set(owner_beats)
    shots: list[dict[str, Any]] = []
    for i, beat in enumerate(beats, start=1):
        words = len(beat.split())
        shot: dict[str, Any] = {
            "shot_no": i,
            "narration": beat,
            "word_count": words,
            "est_seconds": round(words / WORDS_PER_SECOND, 1),
        }
        if i in generated:
            shot["visual"] = {
                "strategy": "generated_via_intake",
                "note": "AI-generated footage; admissible only via "
                        "the provenance intake (TASK-IG-VYR-07)",
            }
        elif i in owned:
            shot["visual"] = {"strategy": "owner_upload",
                              "note": "the channel owner's own media"}
        else:
            clip = _match_clip(beat, pool)
            if clip is not None:
                shot["visual"] = {
                    "strategy": "catalogue",
                    "catalog_id": clip.get("catalog_id"),
                    "source_title": clip.get("title"),
                    "license_name": clip.get("license_name"),
                    "page_url": clip.get("page_url"),
                }
            else:
                shot["visual"] = {
                    "strategy": "unresolved",
                    "note": "no stocked clip matches this beat; "
                            "source one lawfully before render",
                }
        shots.append(shot)
    summary = storyboard_summary(shots)
    return {
        "kind": "previs_storyboard",
        "previs_version": PREVIS_VERSION,
        "lane": lane,
        "shots": shots,
        "summary": summary,
        "complete": summary["unresolved"] == 0,
        "status": "pending_review",
        "requires_approval": True,
        "publish": False,
    }


def storyboard_summary(shots: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts by strategy + total estimated duration + gaps."""
    by_strategy: dict[str, int] = {}
    total = 0.0
    unresolved = []
    for shot in shots:
        strategy = (shot.get("visual") or {}).get("strategy", "unresolved")
        by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
        total += float(shot.get("est_seconds") or 0)
        if strategy == "unresolved":
            unresolved.append(shot.get("shot_no"))
    return {
        "shots": len(shots),
        "by_strategy": by_strategy,
        "est_seconds_total": round(total, 1),
        "unresolved": len(unresolved),
        "unresolved_shots": unresolved,
    }


def contact_sheet_plan(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-shot frame sources for a human-review contact sheet.

    A plan, not an image: catalogue shots point at their stocked
    clip, other strategies carry an explicit placeholder label —
    the sheet must never imply footage exists where it does not.
    """
    plan = []
    for shot in storyboard.get("shots") or []:
        visual = shot.get("visual") or {}
        if visual.get("strategy") == "catalogue":
            frame = {"source": "catalogue_clip",
                     "catalog_id": visual.get("catalog_id"),
                     "page_url": visual.get("page_url")}
        else:
            frame = {"source": "placeholder",
                     "label": f"SHOT {shot['shot_no']} — "
                              f"{visual.get('strategy', 'unresolved')}"}
        plan.append({"shot_no": shot["shot_no"], "frame": frame,
                     "narration": shot["narration"]})
    return plan


def enqueue_storyboard(storyboard: dict[str, Any],
                       queue_path: Any = None) -> Any:
    """Append a storyboard to the VYR-004 review queue (pending_review)."""
    entry = {
        "kind": "previs_storyboard",
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "storyboard": storyboard,
    }
    return remix_flow.enqueue_review(entry, queue_path)
