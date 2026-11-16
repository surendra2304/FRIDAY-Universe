"""VyralX single production-rules folder (TASK-IG3-VYR-09).

Cluster 131 (IG source DeyusrQMOmi) describes a production
system whose "secret" is not the model but a single folder
of rules, set by a senior motion designer, that the
generating agent must follow: hook in the first second,
visuals timed to the voice, pictures landing exactly on
words, motion until the last frame, and every frame
reviewed at 60fps before publishing. It was graded PARTIAL:
the rules existed as deterministic scoring code scattered
across the lane (``format_clone.score_hook``,
``shorts_factory._HOOK_TEMPLATES``, the ``packaging``
lints), but a single rules artefact the generating agent
must follow — with review against it — was not a distinct
artifact on main. Supervisor AUDIT-2 re-confirmed: "rules
remain scattered as code".

This module makes the folder real:

* ``app/data/production_rules.json`` IS the folder — the
  five source rules as data, each with its statement, its
  source, its measured threshold, and a pointer to where it
  is enforced;
* :func:`load_rules` loads and validates the folder (a rule
  without an id, statement or enforcement pointer is a
  broken folder and raises);
* :func:`check_plan` measures one production plan against
  every rule and returns per-rule verdicts with the measured
  numbers — a pass and a fail are equally specific. The hook
  rule additionally reports ``format_clone.score_hook``'s
  verdict on the hook text as quality evidence (timing is
  the rule; the score is evidence, not a second gate).

Honesty boundaries: the checker measures the plan it is
handed — timings, word anchors, the declared frame review.
It cannot see a rendered video, so ``frame_review`` is a
declaration the plan must carry, checked for presence and
fps, not independently witnessed; the verdict says so. A
plan that passes is ``pending_review`` like everything in
this lane; nothing publishes from here.

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``GET
/api/v1/production-rules``, ``POST
/api/v1/production-rules/check``, ``GET
/api/v1/production-rules/policy``) — the AUDIT-2
production-caller standard.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import format_clone

RULES_VERSION = "ig3-vyr09-1"
IG_SOURCES = ("DeyusrQMOmi", "DdlIP2YAqsq")

_DATA_PATH = (Path(__file__).resolve().parent.parent
              / "data" / "production_rules.json")


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Load + validate the rules folder. Raises on a broken folder."""
    data = json.loads(
        Path(path or _DATA_PATH).read_text(encoding="utf-8"))
    rules = data.get("rules") or []
    problems: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        rid = rule.get("id", "?")
        if rid in seen:
            problems.append(f"duplicate rule id: {rid}")
        seen.add(rid)
        for field in ("id", "statement", "source", "enforcement"):
            if not rule.get(field):
                problems.append(f"{rid}: missing {field}")
    if not rules:
        problems.append("the folder holds no rules")
    if problems:
        raise ValueError("production rules folder invalid: "
                         + "; ".join(problems))
    return data


def _rule(folder: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(r for r in folder["rules"] if r["id"] == rule_id)


def check_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Measure one production plan against every rule in the folder.

    Plan shape: ``duration_s``, ``hook`` {text, at},
    ``timed_words`` [{word, start, end}], ``visuals``
    [{visual_id, at, end, word}], ``frame_review``
    {fps, completed}. Every verdict carries its measured
    numbers.
    """
    folder = load_rules()
    if not isinstance(plan, dict):
        raise ValueError("a plan object is required")
    duration = float(plan.get("duration_s") or 0)
    if duration <= 0:
        raise ValueError("plan duration_s must be positive")
    hook = plan.get("hook") or {}
    timed_words = plan.get("timed_words") or []
    visuals = plan.get("visuals") or []
    review = plan.get("frame_review") or {}
    word_starts = {str(w.get("word", "")).casefold(): float(w["start"])
                   for w in timed_words if "start" in w}
    verdicts: list[dict[str, Any]] = []

    # Rule 1 — hook in the first second.
    rule = _rule(folder, "hook_first_second")
    max_at = float(rule["threshold"]["hook_at_max_s"])
    hook_at = hook.get("at")
    hook_score = (format_clone.score_hook(str(hook.get("text", "")))
                  if hook.get("text") else None)
    verdicts.append({
        "rule_id": rule["id"],
        "passed": bool(hook.get("text")) and hook_at is not None
                  and float(hook_at) <= max_at,
        "measured": {"hook_at_s": hook_at,
                     "threshold_s": max_at,
                     "hook_score": hook_score},
    })

    # Rule 2 — visuals timed to the voice.
    rule = _rule(folder, "visuals_timed_to_voice")
    unanchored = [v.get("visual_id", "?") for v in visuals
                  if not isinstance(v.get("at"), (int, float))]
    verdicts.append({
        "rule_id": rule["id"],
        "passed": bool(visuals) and not unanchored,
        "measured": {"visual_count": len(visuals),
                     "unanchored": unanchored},
    })

    # Rule 3 — pictures land exactly on words (<=250ms).
    rule = _rule(folder, "pictures_land_on_words")
    max_err = float(rule["threshold"]["max_landing_error_s"])
    landings = []
    for v in visuals:
        word = str(v.get("word", "")).casefold()
        if word not in word_starts or not isinstance(
                v.get("at"), (int, float)):
            landings.append({"visual_id": v.get("visual_id", "?"),
                             "word": v.get("word"),
                             "error_s": None,
                             "passed": False})
            continue
        error = round(abs(float(v["at"]) - word_starts[word]), 3)
        landings.append({"visual_id": v.get("visual_id", "?"),
                         "word": v.get("word"),
                         "error_s": error,
                         "passed": error <= max_err})
    verdicts.append({
        "rule_id": rule["id"],
        "passed": bool(landings)
                  and all(l["passed"] for l in landings),
        "measured": {"threshold_s": max_err,
                     "landings": landings},
    })

    # Rule 4 — motion until the last frame.
    rule = _rule(folder, "motion_until_last_frame")
    max_gap = float(rule["threshold"]["max_tail_gap_s"])
    last_end = max((float(v["end"]) for v in visuals
                    if isinstance(v.get("end"), (int, float))),
                   default=0.0)
    tail_gap = round(duration - last_end, 3)
    verdicts.append({
        "rule_id": rule["id"],
        "passed": bool(visuals) and tail_gap <= max_gap,
        "measured": {"last_visual_end_s": last_end,
                     "duration_s": duration,
                     "tail_gap_s": tail_gap,
                     "threshold_s": max_gap},
    })

    # Rule 5 — every frame reviewed at 60fps before publishing.
    rule = _rule(folder, "frame_review_60fps")
    want_fps = int(rule["threshold"]["fps"])
    verdicts.append({
        "rule_id": rule["id"],
        "passed": review.get("fps") == want_fps
                  and review.get("completed") is True,
        "measured": {"declared_fps": review.get("fps"),
                     "declared_completed": review.get("completed"),
                     "threshold_fps": want_fps},
        "basis": "the plan's declaration, checked for "
                 "presence and fps — the checker measures "
                 "plans, it does not witness the review",
    })

    return {
        "kind": "production_rules_check",
        "version": RULES_VERSION,
        "ig_sources": list(IG_SOURCES),
        "passed": all(v["passed"] for v in verdicts),
        "verdicts": verdicts,
        "status": "pending_review",
        "publish": False,
    }


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class CheckRequest(BaseModel):
    plan: dict[str, Any]


@router.get("/production-rules/policy")
def production_rules_policy() -> dict[str, Any]:
    folder = load_rules()
    return {
        "version": RULES_VERSION,
        "ig_sources": list(IG_SOURCES),
        "rule_count": len(folder["rules"]),
        "checker": "measures plans against the folder — "
                   "timings, word anchors, declared frame "
                   "review; it does not witness a render",
        "status": "pending_review",
        "publish": False,
    }


@router.get("/production-rules")
def production_rules_folder() -> dict[str, Any]:
    return load_rules()


@router.post("/production-rules/check")
def production_rules_check(req: CheckRequest) -> dict[str, Any]:
    try:
        return check_plan(req.plan)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
