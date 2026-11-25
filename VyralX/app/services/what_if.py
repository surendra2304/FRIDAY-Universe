"""VyralX what-if narrated-story episodes (TASK-VYR-069).

The format registry carries the ``what_if_narrated_story`` template
(one counterfactual premise, single narrator, chaptered escalation,
cliffhanger ending, episode series) alongside the stick-figure
template (TASK-VYR-062) — but a template alone plans nothing. This
module is the planner for that template, the same layer the
stick-figure module (``stick_figure.py``, TASK-IG3-VYR-02) is for
its template:

* :func:`build_episode` turns one premise + chapter texts + a
  cliffhanger into an episode plan over the template: each beat
  gets its timing from the template shares, the cliffhanger is
  recorded as the hook the *next* episode opens by resolving, and
  the episode carries its series position (``episode_no`` /
  ``series_id``) so a chain of episodes is a series, not a pile
  of one-offs;
* the acceptance shape is enforced, not assumed: exactly one
  counterfactual premise (a list of premises is refused), exactly
  one narrator (a list of narrators is refused), three chapter
  beats (fewer chapters are recorded in ``missing_chapters`` and
  never padded; more are refused), and a cliffhanger is mandatory
  — an episode without one has no series hook and is refused;
* episode planning itself is the deliverable: the plan is
  ``pending_review`` and publishes nothing. Narration and video
  rendering stay off-fleet, exactly like ``film_pipeline``'s
  render gate.

The module carries its own FastAPI router, mounted by ``app.main``
at ``/api/v1`` (``POST /api/v1/what-if/episodes``,
``GET /api/v1/what-if/beats``) — the AUDIT-2 production-caller
standard: a library no production code calls is not delivered.

Pure stdlib + FastAPI router; no network. Python 3.10.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import format_templates

WHAT_IF_VERSION = "vyr069-1"
TEMPLATE_ID = "what_if_narrated_story"

#: The template beats that carry the episode's chapters, in order.
CHAPTER_BEATS = ("chapter_one", "chapter_two", "chapter_three")


def build_episode(premise: Any, chapters: Any, cliffhanger: Any, *,
                  episode_no: int = 1,
                  series_id: str | None = None,
                  narrator: Any = "Narrator",
                  target_seconds: float = 90.0,
                  lane: str = "tech_ai") -> dict[str, Any]:
    """A what-if episode plan from one premise + chapters + cliffhanger.

    ``premise`` is exactly one counterfactual question as a single
    string — a list (two premises) is refused, because the template's
    first hard rule is one premise per episode. ``narrator`` is one
    voice, likewise a single string. ``chapters`` aligns with the
    template's three chapter beats in order; fewer chapters than
    beats is recorded in ``missing_chapters`` (the affected chapters
    plan with empty text) — never silently padded; more chapters
    than beats is refused, because a chapter with no beat is a
    script error, not an episode. ``cliffhanger`` is mandatory: an
    episode that pays off its own ending has no hook for the next
    episode, so a missing or empty cliffhanger is refused.
    """
    template = format_templates.get_template(TEMPLATE_ID)
    if lane not in template["lanes"]:
        raise ValueError(f"lane {lane!r} not in template lanes "
                         f"{template['lanes']}")
    if not isinstance(premise, str) or not premise.strip():
        raise ValueError("exactly one counterfactual premise is "
                         "required, as a single non-empty string")
    if not isinstance(narrator, str) or not narrator.strip():
        raise ValueError("exactly one narrator is required, as a "
                         "single non-empty string")
    if not isinstance(cliffhanger, str) or not cliffhanger.strip():
        raise ValueError("a cliffhanger is required — an episode "
                         "without one has no hook for the next episode")
    if not isinstance(chapters, list) or any(
            not isinstance(c, str) for c in chapters):
        raise ValueError("chapters must be a list of strings, one "
                         "per chapter beat")
    if len(chapters) > len(CHAPTER_BEATS):
        raise ValueError(f"{len(chapters)} chapters for "
                         f"{len(CHAPTER_BEATS)} chapter beats")
    if not isinstance(episode_no, int) or isinstance(episode_no, bool) \
            or episode_no < 1:
        raise ValueError(f"episode_no must be a positive integer, "
                         f"got {episode_no!r}")
    if series_id is not None and (
            not isinstance(series_id, str) or not series_id.strip()):
        raise ValueError("series_id, when given, must be a "
                         "non-empty string")
    plan = format_templates.instantiate(TEMPLATE_ID, target_seconds)
    beats = {b["beat"]: b for b in plan["beats"]}
    chapter_plans, missing = [], []
    for i, beat_name in enumerate(CHAPTER_BEATS):
        beat = beats[beat_name]
        text = chapters[i] if i < len(chapters) else ""
        if not text:
            missing.append(beat_name)
        chapter_plans.append({"beat": beat_name, "note": beat["note"],
                              "start": beat["start"], "end": beat["end"],
                              "text": text})
    premise_beat = beats["premise"]
    cliffhanger_beat = beats["cliffhanger"]
    return {
        "kind": "what_if_episode_plan",
        "version": WHAT_IF_VERSION,
        "template_id": TEMPLATE_ID,
        "lane": lane,
        "target_seconds": target_seconds,
        "within_template_range": plan["within_template_range"],
        "premise": premise.strip(),
        "premise_beat": {"beat": "premise", "note": premise_beat["note"],
                         "start": premise_beat["start"],
                         "end": premise_beat["end"]},
        "narrator": narrator.strip(),
        "episode_no": episode_no,
        "series_id": series_id,
        "chapters": chapter_plans,
        "missing_chapters": missing,
        "cliffhanger": cliffhanger.strip(),
        "cliffhanger_beat": {"beat": "cliffhanger",
                             "note": cliffhanger_beat["note"],
                             "start": cliffhanger_beat["start"],
                             "end": cliffhanger_beat["end"]},
        "next_episode_hook": f"Episode {episode_no + 1} opens by "
                             f"resolving: {cliffhanger.strip()}",
        "hard_rules": template["hard_rules"],
        "status": "pending_review",
        "privacy": "unlisted",
        "publish": False,
        "render": "episode plan only — narration and video rendering "
                  "stay off-fleet (film_pipeline render-gate pattern)",
    }


def enqueue_episode_plan(plan: dict[str, Any],
                         queue_path: Any = None) -> int:
    """Append an episode plan to the VYR-004 review queue. Returns 1.

    The remix_flow import is lazy: the episode builder stays
    importable (and testable) without the queue's dependency chain.
    """
    from app.services import remix_flow

    remix_flow.enqueue_review({
        "kind": plan["kind"], "version": plan["version"],
        "template_id": plan["template_id"], "lane": plan["lane"],
        "target_seconds": plan["target_seconds"],
        "episode_no": plan["episode_no"],
        "series_id": plan["series_id"],
        "missing_chapters": plan["missing_chapters"],
        "status": plan["status"], "publish": False,
    }, queue_path)
    return 1


router = APIRouter()


class EpisodeRequest(BaseModel):
    premise: str
    chapters: list[str]
    cliffhanger: str
    episode_no: int = 1
    series_id: str | None = None
    narrator: str = "Narrator"
    target_seconds: float = 90.0
    lane: str = "tech_ai"
    enqueue: bool = False


@router.get("/what-if/beats")
def what_if_beats() -> dict[str, Any]:
    template = format_templates.get_template(TEMPLATE_ID)
    return {"version": WHAT_IF_VERSION, "template_id": TEMPLATE_ID,
            "beats": template["structure"],
            "target_seconds": template["target_seconds"],
            "lanes": template["lanes"]}


@router.post("/what-if/episodes")
def what_if_episodes(req: EpisodeRequest) -> dict[str, Any]:
    try:
        plan = build_episode(req.premise, req.chapters,
                             req.cliffhanger,
                             episode_no=req.episode_no,
                             series_id=req.series_id,
                             narrator=req.narrator,
                             target_seconds=req.target_seconds,
                             lane=req.lane)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if req.enqueue:
        plan["enqueued"] = enqueue_episode_plan(plan)
    return plan
