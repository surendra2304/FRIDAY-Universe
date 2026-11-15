"""VyralX faceless series automation (TASK-IG-VYR-04).

The IG reference corpus's faceless-channel cluster (Dd_sICVjFKq —
an open-source faceless-channel system guide; DeoNBhjE_DA — a
channel where an LLM writes every episode and auto-animation
renders them on a daily cadence; DeRrQa-E2AV — a Claude-scripted
faceless Shorts system; Dd3wk7qmgFx — script-to-video stacks) all
describe the same missing layer. VyralX already has the per-video
machinery (sync-fixed rendering, TASK-VYR-003; the licence-gated
remix flow, TASK-VYR-004; the compliance gate, TASK-VYR-009). What
it has never had is a **series**: a recurring show whose episodes
are planned ahead on a cadence, deduped against what already ran,
and queued for review like everything else.

This module is that planning layer:

* :func:`validate_series` — a series spec must name one of the
  three owner-approved lanes, must not trip the compliance gate's
  excluded categories (anime/gameplay/sports/Bollywood/movie
  compilations, re-uploads), and its topic seeds are screened for
  finance advice. Bad specs fail loudly with every problem listed.
* :func:`plan_episodes` — deterministic episode briefs (title,
  hook, three-beat outline) from the seed topics, skipping seeds
  whose normalised title collides with an existing episode or an
  earlier brief in the same plan. Skips are recorded, not silent.
* :func:`daily_queue` — which briefs fall due on a given date
  under each series' cadence, deterministically.
* :func:`enqueue_briefs` — briefs land in the VYR-004 review queue
  as ``pending_review``.

Nothing here renders, uploads, or publishes; a brief is a plan for
a human-approved pipeline, not a video. Money topics are stories,
never advice — the advice screen is the compliance gate's own
finder. Pure functions over plain dicts; no network. Python 3.10.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Iterable

from app.services import compliance_gate, remix_flow

SERIES_VERSION = "ig-vyr04-1"

OWNER_LANES = ("space_science", "history", "tech_ai")

_TITLE_SHAPES = (
    "{topic} — Part {n}",
    "The Story of {topic} (Episode {n})",
    "{topic}: Chapter {n}",
)


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_series(series: dict[str, Any]) -> dict[str, Any]:
    """Validate a series spec; returns {ok, problems, screened_seeds}.

    ``screened_seeds`` are the topic seeds that survived the
    finance-advice screen — a seed that trips it is a problem AND is
    excluded from planning.
    """
    problems: list[str] = []
    lane = str(series.get("lane") or "")
    if lane not in OWNER_LANES:
        problems.append(
            f"lane {lane!r} is not one of the owner-approved lanes "
            f"{list(OWNER_LANES)}")
    declared = f"{lane} {series.get('format_name') or ''}".casefold()
    if lane in compliance_gate.EXCLUDED_LANES:
        problems.append(f"lane {lane!r} is an excluded category")
    token_hits = [t for t in compliance_gate.EXCLUDED_TOKENS
                  if t in declared]
    if token_hits:
        problems.append(
            f"declared lane/format contains excluded token(s) "
            f"{token_hits} (reused-content policy / Content ID)")
    cadence = series.get("cadence_days")
    if not isinstance(cadence, int) or cadence < 1:
        problems.append("cadence_days must be a positive integer")
    planned = series.get("episodes_planned")
    if not isinstance(planned, int) or planned < 1:
        problems.append("episodes_planned must be a positive integer")
    seeds = [str(s).strip() for s in series.get("topic_seeds") or []]
    if not seeds:
        problems.append("topic_seeds must not be empty")
    screened: list[str] = []
    for seed in seeds:
        if not seed:
            continue
        hits = compliance_gate.find_finance_advice(seed)
        if hits:
            problems.append(
                f"topic seed {seed!r} trips the finance-advice screen "
                f"({len(hits)} hit(s)) — excluded from planning")
        else:
            screened.append(seed)
    if seeds and not screened:
        problems.append("no topic seed survived screening")
    return {"ok": not problems, "problems": problems,
            "screened_seeds": screened}


# --------------------------------------------------------------------------- #
# Episode planning
# --------------------------------------------------------------------------- #
def plan_episodes(series: dict[str, Any],
                  existing_titles: Iterable[str] = ()) -> dict[str, Any]:
    """Plan episode briefs for a series, deduped against history.

    Briefs are deterministic: seed topics cycle until
    ``episodes_planned`` briefs exist or the seeds run out (seeds
    are never silently repeated within a plan — a repeat would be
    a duplicate episode, so planning stops and says so).
    """
    check = validate_series(series)
    if not check["ok"]:
        raise ValueError(
            "invalid series spec: " + "; ".join(check["problems"]))
    seeds = check["screened_seeds"]
    planned_total = int(series["episodes_planned"])
    seen = {_norm_title(t) for t in existing_titles}
    briefs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_seeds: set[str] = set()
    n = 0
    while len(briefs) < planned_total:
        seed = seeds[n % len(seeds)]
        n += 1
        if seed in used_seeds:
            skipped.append({"topic": seed,
                            "reason": "seed already used in this plan"})
            break
        used_seeds.add(seed)
        ep_no = len(briefs) + 1
        title = _TITLE_SHAPES[(ep_no - 1) % len(_TITLE_SHAPES)].format(
            topic=seed, n=ep_no)
        seed_norm = _norm_title(seed)
        # A seed is a duplicate if its generated title matches an
        # existing title OR the seed topic itself already appears
        # inside an existing title (an episode about this topic ran,
        # whatever title shape it used).
        if _norm_title(title) in seen or any(
                seed_norm and seed_norm in t for t in seen):
            skipped.append({"topic": seed,
                            "reason": "topic/title collides with an "
                                      "existing episode"})
            continue
        seen.add(_norm_title(title))
        briefs.append({
            "series_id": series.get("series_id"),
            "episode_no": ep_no,
            "topic": seed,
            "title": title,
            "hook": (f"Episode {ep_no}: the part of {seed} nobody "
                     f"tells you first."),
            "outline": [
                f"Open on the strongest documented moment of {seed}.",
                f"Build the story of {seed} in three documented beats.",
                f"Close with what {seed} changed — and what came next.",
            ],
            "lane": series.get("lane"),
            "format_name": series.get("format_name") or "series_episode",
            "status": "pending_review",
            "requires_approval": True,
            "publish": False,
        })
    return {
        "series_id": series.get("series_id"),
        "briefs": briefs,
        "skipped": skipped,
        "planned_total": planned_total,
        "shortfall": planned_total - len(briefs),
    }


# --------------------------------------------------------------------------- #
# Daily queue
# --------------------------------------------------------------------------- #
def daily_queue(plans: Iterable[dict[str, Any]],
                series_specs: Iterable[dict[str, Any]],
                on: date) -> list[dict[str, Any]]:
    """Briefs due on ``on`` given each series' start date + cadence.

    A series spec carries ``start_date`` (ISO). Episode k (1-based)
    falls due at start + (k-1) * cadence_days. Deterministic; a date
    with nothing due returns an empty list, honestly.
    """
    specs = {s.get("series_id"): s for s in series_specs}
    due: list[dict[str, Any]] = []
    for plan in plans:
        spec = specs.get(plan.get("series_id")) or {}
        try:
            start = date.fromisoformat(str(spec.get("start_date")))
        except (TypeError, ValueError):
            continue
        cadence = spec.get("cadence_days")
        if not isinstance(cadence, int) or cadence < 1:
            continue
        for brief in plan.get("briefs") or []:
            due_date = start + timedelta(
                days=(brief["episode_no"] - 1) * cadence)
            if due_date == on:
                due.append({**brief, "due_date": on.isoformat()})
    return due


def enqueue_briefs(briefs: Iterable[dict[str, Any]],
                   queue_path: Any = None) -> int:
    """Append episode briefs to the VYR-004 review queue. Returns count."""
    count = 0
    for brief in briefs:
        remix_flow.enqueue_review({
            "kind": "series_episode_brief",
            "status": "pending_review",
            "requires_approval": True,
            "publishes_anything": False,
            "brief": brief,
        }, queue_path)
        count += 1
    return count
