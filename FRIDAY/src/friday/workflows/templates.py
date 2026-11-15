"""Ready-made automation workflow templates (TASK-IG-FRD-005).

Pattern source: IG corpus item ``DdbljkbH5b2`` ("ready-made AI
workflows" — stop building automations from scratch). Each template
declares its parameters and an ordered list of steps with ``{param}``
placeholders. Instantiating a template:

* validates parameters — a missing *required* parameter is an explicit
  error, never silently defaulted;
* renders the steps into a concrete plan;
* optionally enqueues each step on the existing mission queue
  (``MissionQueue.add``, source ``workflow_template``) and reports the
  mission ids. If the queue cannot be reached, the plan comes back
  with ``enqueued: False`` and the reason — an enqueue is never faked.

Templates compose capabilities that already exist in the fleet (the
job-hunt scan from TASK-IG-FRD-003, the follow-up sweep from
TASK-IG-FRD-002, goal loops from TASK-IG-FRD-001) — the step text names
the tool to use, so the plan is executable by the normal agent loop.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "content_batch",
        "name": "Content batch",
        "category": "content",
        "description": "Research a topic, then draft a batch of content pieces with review checkpoints.",
        "params": [
            {"name": "topic", "required": True},
            {"name": "count", "required": False, "default": 3},
            {"name": "formats", "required": False, "default": "short video scripts"},
        ],
        "steps": [
            {"title": "Research the topic",
             "detail": "Run a deep research pass on '{topic}' and keep the source list with the findings.",
             "tool_hint": "intelx_research"},
            {"title": "Draft {count} pieces",
             "detail": "Draft {count} {formats} on '{topic}' from the research. Drafts only — nothing publishes from this template.",
             "tool_hint": "draft_content"},
            {"title": "Review checkpoint",
             "detail": "Present the drafts to the owner for review; record which are approved, edited, or dropped as follow-ups.",
             "tool_hint": "followup_add"},
        ],
    },
    {
        "id": "social_draft_pack",
        "name": "Social draft pack",
        "category": "social",
        "description": "Turn one idea into platform-ready draft posts. Drafts only — posting stays a human action.",
        "params": [
            {"name": "idea", "required": True},
            {"name": "platforms", "required": False, "default": "instagram, x, linkedin"},
        ],
        "steps": [
            {"title": "Draft the posts",
             "detail": "Write one draft post per platform ({platforms}) for: {idea}. Adapt tone and length per platform.",
             "tool_hint": "draft_content"},
            {"title": "Save drafts for review",
             "detail": "Save every draft to files and list the paths for the owner. Do not post anything.",
             "tool_hint": "file_operations"},
        ],
    },
    {
        "id": "business_morning_ops",
        "name": "Business morning ops",
        "category": "business",
        "description": "The morning operating picture: brief, inbox triage, calendar, and anything overdue.",
        "params": [
            {"name": "focus", "required": False, "default": "all projects"},
        ],
        "steps": [
            {"title": "Morning briefing",
             "detail": "Produce the morning briefing with focus on {focus}: overnight changes, today's calendar, fleet health.",
             "tool_hint": "morning_briefing"},
            {"title": "Follow-up sweep",
             "detail": "List every due or overdue follow-up and surface the oldest first; nothing gets dropped silently.",
             "tool_hint": "followup_list"},
            {"title": "Goal status",
             "detail": "Report the state of any active goal loops (progress, blockers, criteria met so far).",
             "tool_hint": "goal_loop_status"},
        ],
    },
    {
        "id": "research_brief",
        "name": "Research brief",
        "category": "research",
        "description": "A sourced brief on one question, with claims tied to their sources.",
        "params": [
            {"name": "question", "required": True},
            {"name": "depth", "required": False, "default": "standard"},
        ],
        "steps": [
            {"title": "Research",
             "detail": "Research '{question}' at {depth} depth; verify load-bearing claims against primary sources.",
             "tool_hint": "intelx_research"},
            {"title": "Write the brief",
             "detail": "Write the brief with a source card per load-bearing claim (what was claimed, where it came from).",
             "tool_hint": "file_operations"},
        ],
    },
    {
        "id": "job_hunt_daily",
        "name": "Job-hunt daily scan",
        "category": "work",
        "description": "The daily job-hunt pass: scan career pages, rank fits, flag overlooked roles (TASK-IG-FRD-003).",
        "params": [
            {"name": "min_score", "required": False, "default": 0.5},
        ],
        "steps": [
            {"title": "Scan career pages",
             "detail": "Run the job-hunt scan over the profile's career pages and rank every posting by CV fit.",
             "tool_hint": "job_hunt_scan"},
            {"title": "Report the shortlist",
             "detail": "Report postings scoring at least {min_score}, calling out any flagged as overlooked fits, with matched and missing skills.",
             "tool_hint": "job_hunt_shortlist"},
        ],
    },
    {
        "id": "weekly_review",
        "name": "Weekly review",
        "category": "life",
        "description": "Close the week: what moved, what is stuck, what carries over — nothing silently dropped.",
        "params": [
            {"name": "week_of", "required": False, "default": "this week"},
        ],
        "steps": [
            {"title": "Collect the week",
             "detail": "Gather {week_of}'s completed missions, goal-loop outcomes, and notable memories into one list.",
             "tool_hint": "mission_status"},
            {"title": "Surface the stuck",
             "detail": "List follow-ups still open past their due date and goals blocked, oldest first, with the blocker for each.",
             "tool_hint": "followup_list"},
            {"title": "Carry-over plan",
             "detail": "Propose next week's top three priorities from the stuck list and confirm them with the owner before enqueuing anything.",
             "tool_hint": "followup_add"},
        ],
    },
]

_BY_ID = {t["id"]: t for t in TEMPLATES}


class TemplateError(Exception):
    """Unknown template or invalid parameters."""


def list_templates(category: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for t in TEMPLATES:
        if category and t["category"] != category:
            continue
        out.append(
            {
                "id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "description": t["description"],
                "params": t["params"],
                "step_count": len(t["steps"]),
            }
        )
    return out


def get_template(template_id: str) -> Dict[str, Any]:
    template = _BY_ID.get(template_id)
    if template is None:
        raise TemplateError(
            f"Unknown template {template_id!r}. Available: {', '.join(sorted(_BY_ID))}."
        )
    return template


def _resolve_params(template: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    resolved: Dict[str, Any] = {}
    missing = []
    for spec in template["params"]:
        name = spec["name"]
        if name in params and params[name] not in (None, ""):
            resolved[name] = params[name]
        elif "default" in spec:
            resolved[name] = spec["default"]
        elif spec.get("required"):
            missing.append(name)
    if missing:
        raise TemplateError(
            f"Template {template['id']!r} is missing required parameter(s): "
            + ", ".join(missing)
            + ". Required parameters are never silently defaulted."
        )
    return resolved


def instantiate(
    template_id: str,
    params: Optional[Dict[str, Any]] = None,
    enqueue: bool = False,
    queue: Any = None,
) -> Dict[str, Any]:
    """Render a template into a concrete plan; optionally enqueue steps.

    ``queue`` is injectable for tests; the default is the real
    MissionQueue. An enqueue failure is reported on the plan
    (``enqueued: False`` + ``enqueue_error``), never hidden.
    """
    template = get_template(template_id)
    resolved = _resolve_params(template, dict(params or {}))
    steps = []
    for i, raw in enumerate(template["steps"], 1):
        steps.append(
            {
                "n": i,
                "title": raw["title"].format_map(resolved),
                "detail": raw["detail"].format_map(resolved),
                "tool_hint": raw.get("tool_hint"),
            }
        )
    plan: Dict[str, Any] = {
        "template_id": template["id"],
        "name": template["name"],
        "category": template["category"],
        "params": resolved,
        "steps": steps,
        "created_at": time.time(),
        "enqueued": False,
        "mission_ids": [],
    }
    if enqueue:
        try:
            if queue is None:
                from friday.proactive.mission_queue import MissionQueue

                queue = MissionQueue()
            for step in steps:
                mission = queue.add(
                    f"[{template['name']}] {step['title']}: {step['detail']}",
                    source="workflow_template",
                )
                plan["mission_ids"].append(mission.get("id"))
            plan["enqueued"] = True
        except Exception as exc:  # reported, not hidden
            plan["enqueued"] = False
            plan["enqueue_error"] = f"{type(exc).__name__}: {exc}"
    return plan


def render_plan(plan: Dict[str, Any]) -> str:
    lines = [f"{plan['name']} ({plan['template_id']}) — {len(plan['steps'])} steps"]
    for step in plan["steps"]:
        lines.append(f"{step['n']}. {step['title']} — {step['detail']}")
    if plan.get("enqueued"):
        lines.append(f"Enqueued as missions: {', '.join(str(m) for m in plan['mission_ids'])}")
    elif plan.get("enqueue_error"):
        lines.append(f"NOT enqueued: {plan['enqueue_error']}")
    return "\n".join(lines)


__all__ = [
    "TEMPLATES",
    "TemplateError",
    "list_templates",
    "get_template",
    "instantiate",
    "render_plan",
]
