"""VyralX content factory (TASK-IG-VYR-02).

The IG reference corpus (source DelZub4u74G — "twelve GitHub repos to
build an AI content factory") describes one automated chain:
**research → generate → repurpose long-form into shorts → schedule**.
The roundup's member repos are not named in the corpus data, so there
is nothing to adopt; this module builds the chain from VyralX's own
stocked parts instead:

* research — keyword-matches a topic against the stocked source
  catalogues (TASK-VYR-006 lane 1, VYR-011 lane 2, VYR-012 lane 3).
  Every candidate carries its catalogue licence/provenance fields;
  the factory never invents a source.
* generate — builds a long-form outline (intro, one section per
  research beat, outro) with template narration. The outline is
  screened with the compliance gate's finance-advice finder; a
  tripping outline aborts the run with the hits recorded — money
  content is stories, never advice.
* repurpose — slices the long-form outline into one Short per body
  section, each with its own hook and a VYR-010 title-strength score,
  keeping the section's source clip attached so the VYR-004 licence
  gate still sees per-short provenance.
* schedule — assigns the shorts to weekly IST slots as a *plan*
  (``publish=False``, privacy ``unlisted``).

The chain is a planning layer: it renders nothing, uploads nothing,
publishes nothing. Its manifest enqueues into the VYR-004 review
queue as ``pending_review`` — a human (the owner) is the gate between
a factory run and any render, exactly as for remix jobs.

Pure functions over plain dicts; deterministic; no network.
Python 3.10.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.services import (compliance_gate, publish_priority, remix_flow,
                          source_catalog, source_catalog_lane2,
                          source_catalog_lane3)

FACTORY_VERSION = "ig-vyr02-1"

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_SLOTS: tuple[tuple[int, str], ...] = (
    (0, "18:00"), (2, "18:00"), (4, "18:00"))

_LANE_CATALOGUES = {
    "space_science": source_catalog,
    "history": source_catalog_lane2,
    "tech_ai": source_catalog_lane3,
}

_STOPWORDS = {"the", "a", "an", "of", "and", "how", "why", "what",
              "story", "true", "did", "you", "know"}


def _tokens(text: str) -> set[str]:
    # Split on any non-alphanumeric so hyphenated catalogue tags
    # ("star-formation") match plain topic words ("star formation").
    return {tok for tok in re.findall(r"[a-z0-9]+", str(text or "").casefold())
            if tok not in _STOPWORDS}


# --------------------------------------------------------------------------- #
# Stage 1 — research over the stocked catalogues
# --------------------------------------------------------------------------- #
def research_stage(topic: str, lane: str,
                   clips: Iterable[dict[str, Any]] | None = None,
                   limit: int = 6) -> dict[str, Any]:
    """Match a topic to stocked, licence-carrying catalogue clips.

    Scoring is transparent keyword overlap between the topic and each
    clip's title + topic tags. Clips with zero overlap are not
    candidates — the factory would rather report an empty shelf than
    pad a run with unrelated footage.
    """
    module = _LANE_CATALOGUES.get(lane)
    if module is None:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of "
            f"{sorted(_LANE_CATALOGUES)}")
    pool = list(clips) if clips is not None else module.load_clips()
    want = _tokens(topic)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for clip in pool:
        have = _tokens(clip.get("title", "")) | _tokens(
            " ".join(clip.get("topic_tags") or []))
        overlap = len(want & have)
        if overlap:
            scored.append((overlap, str(clip.get("catalog_id") or ""),
                           clip))
    scored.sort(key=lambda t: (-t[0], t[1]))
    candidates = []
    for overlap, _cid, clip in scored[:limit]:
        candidates.append({
            "catalog_id": clip.get("catalog_id"),
            "title": clip.get("title"),
            "platform": clip.get("platform"),
            "creator": clip.get("creator"),
            "page_url": clip.get("page_url"),
            "license_name": clip.get("license_name"),
            "rights_basis": clip.get("rights_basis"),
            "duration_seconds": clip.get("duration_seconds"),
            "match_score": overlap,
        })
    return {
        "stage": "research",
        "topic": topic,
        "lane": lane,
        "candidates": candidates,
        "shelf_empty": not candidates,
    }


# --------------------------------------------------------------------------- #
# Stage 2 — generate a long-form outline
# --------------------------------------------------------------------------- #
def generate_stage(topic: str, lane: str,
                   research: dict[str, Any]) -> dict[str, Any]:
    """Build the long-form outline from the research beats.

    One body section per candidate clip (up to 4), each narrated from a
    fixed template that names the clip it will show. The whole outline
    is finance-advice screened; hits abort with ``blocked=True``.
    """
    candidates = research.get("candidates") or []
    sections: list[dict[str, Any]] = [{
        "kind": "intro",
        "narration": (
            f"Today we are looking at {topic} — told through real, "
            f"licensed footage, with original commentary throughout."),
        "catalog_id": None,
    }]
    for i, cand in enumerate(candidates[:4]):
        sections.append({
            "kind": "beat",
            "beat": i + 1,
            "narration": (
                f"Beat {i + 1}: {cand.get('title')}. Watch closely — "
                f"this is the moment that matters, and it is exactly "
                f"what the record shows."),
            "catalog_id": cand.get("catalog_id"),
            "source_title": cand.get("title"),
        })
    sections.append({
        "kind": "outro",
        "narration": (
            "That is the story the footage tells. Sources and "
            "licences for everything shown are in the description."),
        "catalog_id": None,
    })
    full_text = "\n".join(s["narration"] for s in sections)
    hits = compliance_gate.find_finance_advice(full_text)
    words = len(full_text.split())
    return {
        "stage": "generate",
        "topic": topic,
        "lane": lane,
        "title": f"{topic} — The Full Story",
        "sections": sections,
        "word_count": words,
        "est_seconds": round(words / 2.6, 1),  # ~156 wpm narration
        "advice_hits": hits,
        "blocked": bool(hits),
    }


# --------------------------------------------------------------------------- #
# Stage 3 — repurpose the long-form into shorts
# --------------------------------------------------------------------------- #
def repurpose_stage(longform: dict[str, Any]) -> dict[str, Any]:
    """Slice one Short per body beat of the long-form outline.

    Each short keeps its beat's source clip (per-short provenance for
    the VYR-004 gate), opens with a hook line, and gets a title scored
    by the VYR-010 heuristic. A blocked long-form repurposes into
    nothing.
    """
    if longform.get("blocked"):
        return {"stage": "repurpose", "shorts": [], "blocked": True}
    shorts = []
    for section in longform.get("sections") or []:
        if section.get("kind") != "beat":
            continue
        title = (f"{longform['topic']} — Part {section['beat']}: "
                 f"The Moment That Matters")
        score, _flags = publish_priority.title_strength(title)
        shorts.append({
            "title": title,
            "hook": ("Watch this moment closely — it changes the "
                     "whole story."),
            "narration": section["narration"],
            "catalog_id": section.get("catalog_id"),
            "source_title": section.get("source_title"),
            "lane": longform["lane"],
            "format_name": "factory_short",
            "title_strength": score,
            "status": "pending_review",
            "requires_approval": True,
            "publish": False,
        })
    return {"stage": "repurpose", "shorts": shorts, "blocked": False}


# --------------------------------------------------------------------------- #
# Stage 4 — schedule the shorts (plan only)
# --------------------------------------------------------------------------- #
def schedule_stage(shorts: Iterable[dict[str, Any]], start: datetime,
                   slots: tuple[tuple[int, str], ...] = DEFAULT_SLOTS
                   ) -> list[dict[str, Any]]:
    """Assign shorts to weekly IST slots. Plan only — publish=False."""
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    start = start.astimezone(IST)
    ordered = sorted(slots)
    pending = list(shorts)
    entries: list[dict[str, Any]] = []
    day = start.date()
    idx = 0
    while pending:
        for weekday, hhmm in ordered:
            if not pending:
                break
            delta = (weekday - day.weekday()) % 7
            when = datetime.combine(
                day + timedelta(days=delta),
                datetime.strptime(hhmm, "%H:%M").time(), tzinfo=IST)
            if when <= start and delta == 0:
                continue
            short = pending.pop(0)
            entries.append({
                "slot": idx,
                "planned_for": when.isoformat(),
                "title": short.get("title"),
                "catalog_id": short.get("catalog_id"),
                "privacy": "unlisted",
                "status": "pending_review",
                "requires_approval": True,
                "publish": False,
            })
            idx += 1
        day = day + timedelta(days=7)
    return entries


# --------------------------------------------------------------------------- #
# The chain
# --------------------------------------------------------------------------- #
def run_factory(topic: str, lane: str, start: datetime,
                clips: Iterable[dict[str, Any]] | None = None
                ) -> dict[str, Any]:
    """Run research → generate → repurpose → schedule for one topic."""
    research = research_stage(topic, lane, clips=clips)
    longform = generate_stage(topic, lane, research)
    repurposed = repurpose_stage(longform)
    schedule = schedule_stage(repurposed["shorts"], start)
    return {
        "kind": "content_factory_run",
        "factory_version": FACTORY_VERSION,
        "topic": topic,
        "lane": lane,
        "stages": {
            "research": research,
            "generate": longform,
            "repurpose": repurposed,
        },
        "schedule": schedule,
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "renders_anything": False,
    }


def enqueue_factory_run(run: dict[str, Any], queue_path: Any = None) -> Any:
    """Append a factory run to the VYR-004 review queue (pending_review)."""
    entry = {
        "kind": "content_factory_run",
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "run": run,
    }
    return remix_flow.enqueue_review(entry, queue_path)
