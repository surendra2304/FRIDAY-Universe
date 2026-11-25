"""VyralX channel-strategy data, served to the app (TASK-IG3-VYR-01).

``app/data/channel_strategy.json`` (TASK-IG-VYR-10, extended by
TASK-IG3-VYR-01) holds the corpus-derived channel strategy: the
three lane playbooks, the niche-selection criteria, the Silk Road
series seed, and the named reference lists (teaching-channel
watchlist, browser toolkit, free-generator shortlist, faceless-idea
examples, free-route alternatives, listicle tool patterns, space-movies reference).

Until now that file was read by tests only — no production code
loaded it (the lane-wide wiring gap recorded in the supervisor's
AUDIT-2). This module is the production consumer: a loader with
named accessors, plus the module's own FastAPI router, mounted by
``app.main`` at ``/api/v1``:

* ``GET /api/v1/strategy/lanes`` — the three lane playbooks;
* ``GET /api/v1/strategy/series-seeds`` — planned series seeds;
* ``GET /api/v1/strategy/references`` — every reference section,
  each carrying its recorded status;
* ``GET /api/v1/strategy/references/{name}`` — one section (404
  for an unknown name).

Read-only by design: nothing here writes the strategy file, adopts
a listed tool or niche, or publishes anything. Every reference
section keeps the status it was recorded with
(``reference_only_unverified`` / ``pattern_notes_only``) — serving
a name is not adopting it, and the JSON's honesty note travels with
every response. Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

STRATEGY_VERSION = "ig3-vyr01-1"
_DATA_PATH = (Path(__file__).resolve().parent.parent / "data"
              / "channel_strategy.json")

#: Sections of the strategy file that are reference material (as
#: opposed to the playbooks themselves). Every one carries a
#: recorded status; the API never upgrades that status.
REFERENCE_SECTIONS = (
    "creator_tools_reference",
    "teaching_channel_watchlist",
    "browser_toolkit_reference",
    "free_generator_shortlist",
    "faceless_idea_examples",
    "free_route_alternatives",
    "listicle_tool_patterns",
    "space_movies_reference",
)


def load_strategy(path: Path | None = None) -> dict[str, Any]:
    """Load the strategy JSON exactly as recorded on disk."""
    return json.loads(Path(path or _DATA_PATH).read_text(encoding="utf-8"))


def reference_sections(data: dict[str, Any]) -> dict[str, Any]:
    """The reference sections present in ``data``, keyed by name.

    A section missing from the file is missing from the result —
    absence is reported, never papered over.
    """
    return {name: data[name] for name in REFERENCE_SECTIONS
            if name in data}


def get_reference(data: dict[str, Any], name: str) -> dict[str, Any]:
    """One reference section by name; raises KeyError if absent."""
    sections = reference_sections(data)
    if name not in sections:
        raise KeyError(f"unknown strategy reference section: {name!r}")
    return sections[name]


router = APIRouter()


@router.get("/strategy/lanes")
def strategy_lanes() -> dict[str, Any]:
    data = load_strategy()
    return {"version": STRATEGY_VERSION,
            "playbook_version": data.get("playbook_version"),
            "lanes": data.get("lanes") or [],
            "niche_selection_criteria":
                data.get("niche_selection_criteria") or []}


@router.get("/strategy/series-seeds")
def strategy_series_seeds() -> dict[str, Any]:
    data = load_strategy()
    return {"version": STRATEGY_VERSION,
            "series_seeds": data.get("series_seeds") or [],
            "note": "Planning seeds only — production is VyralX's "
                    "owner-gated operation; nothing here publishes."}


@router.get("/strategy/references")
def strategy_references() -> dict[str, Any]:
    data = load_strategy()
    return {"version": STRATEGY_VERSION,
            "honesty_note": data.get("note"),
            "sections": reference_sections(data)}


@router.get("/strategy/references/{name}")
def strategy_reference(name: str) -> dict[str, Any]:
    data = load_strategy()
    try:
        section = get_reference(data, name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"unknown strategy reference section: {name!r}")
    return {"version": STRATEGY_VERSION, "name": name,
            "section": section}
