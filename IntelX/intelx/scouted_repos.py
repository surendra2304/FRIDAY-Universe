"""Scouted open-source repo registry (TASK-IG-INT-06).

Implements corpus item Dc-zw_Vicxs (a video shortlisting open-source repos
for builders) in its honest fleet-wide form: the registry of the **102
verified spec cards** produced by the corpus repo passes
(``~/workspace/ig-references/repos/`` — wave 1 verified against real
GitHub pages on 2026-11-15, waves 2 + 2b on 2026-11-16; the source
video's own repos were never named in its caption, so the corpus-wide
verified set is the fulfilment).

Each entry carries the card's BINDING fit verdict (adopt / adapt /
reference-only / reject) — the verdicts other lanes build against. The
data file is generated from the cards + INDEX.md by
``IntelX/scripts/generate_scouted_repos.py``, not hand-typed; the
tests pin the counts so any drift between this registry and the cards
is caught.

Note on counts: across all 102 cards the counts are adopt=6, adapt=40,
reference-only=46, reject=10. (For wave 1 alone the cards and
repos/INDEX.md agree on adopt=2, adapt=15, reference-only=13, reject=2;
the wave-1 roll-up summary's "13 adapt / 15 reference-only" transposes
the two middle counts against its own cards — this registry follows
the cards, and the discrepancy is recorded in the TASK-IG-INT-06
completion comment on issue #35.)
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "registries" / "scouted_repos.json"

_cache: dict | None = None


def load_registry() -> dict:
    """Load the full registry document ({count, fit_counts, entries})."""
    global _cache
    if _cache is None:
        _cache = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return _cache


def all_entries() -> list[dict]:
    return list(load_registry()["entries"])


def by_agent(agent: str) -> list[dict]:
    """Entries whose FRIDAY-agent mapping includes ``agent`` (exact match
    against the INDEX agent column, e.g. 'IntelX', 'Stratex', 'Forge')."""
    return [e for e in all_entries() if agent in e["friday_agents"]]


def by_fit(fit: str) -> list[dict]:
    """Entries with the given fit verdict (adopt|adapt|reference-only|reject)."""
    return [e for e in all_entries() if e["fit"] == fit]


def by_repo(repo: str) -> dict | None:
    """One entry by 'owner/name' (case-insensitive), or None."""
    for entry in all_entries():
        if entry["repo"].lower() == repo.lower():
            return entry
    return None


def summary() -> dict:
    registry = load_registry()
    agents: dict[str, int] = {}
    for entry in registry["entries"]:
        for agent in entry["friday_agents"]:
            agents[agent] = agents.get(agent, 0) + 1
    return {
        "count": registry["count"],
        "fit_counts": registry["fit_counts"],
        "agent_counts": agents,
        "generated_from": registry["generated_from"],
    }


__all__ = ["all_entries", "by_agent", "by_fit", "by_repo", "load_registry", "summary"]
