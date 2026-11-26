"""TASK-FRD-045 — WOOP goal-setting template for the goal loop.

WOOP (Wish, Outcome, Obstacle, Plan — Oettingen's mental contrasting
with implementation intentions) structures an owner goal created by
voice/chat before the goal loop (TASK-IG-FRD-001) works it:

- Wish: the goal in plain words — what the owner wants.
- Outcome: the best outcome — what success looks like. Becomes the
  loop's success criterion (a ``judge`` criterion on the outcome text,
  unless the caller supplies explicit criteria instead).
- Obstacle: the inner obstacle most likely to block it. The loop gets
  an explicit obstacle-watch step, so the obstacle is checked, not
  assumed away.
- Plan: if-then plans ("If <situation>, then I will <response>") —
  each becomes a work step the loop executes.

This module is pure data (stdlib only): normalise a raw WOOP record,
derive criteria and plan steps from it. ``goal_loop`` wires it into
``GoalLoopStore.create`` and ``start_goal_loop``; nothing here touches
the store, the brain, or the network.
"""

from __future__ import annotations

from typing import Any

WOOP_FIELDS = ("wish", "outcome", "obstacle", "plan")


def _non_empty_str(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"WOOP {field!r} must not be empty")
    return text


def normalise_plan_entry(raw: Any, index: int) -> dict[str, str]:
    """One if-then plan entry.

    Accepts a dict {"if": ..., "then": ...} or a plain string (becomes
    {"if": "", "then": that string} — a response with no trigger yet).
    The ``then`` (the response) is always required; ``if`` may be empty.
    """
    if isinstance(raw, str):
        return {"if": "", "then": _non_empty_str(raw, f"plan[{index}].then")}
    if not isinstance(raw, dict):
        raise ValueError(
            f"WOOP plan[{index}] must be a string or an object with 'if'/'then'"
        )
    then = _non_empty_str(raw.get("then"), f"plan[{index}].then")
    when = str(raw.get("if") or "").strip()
    return {"if": when, "then": then}


def normalise_woop(raw: Any) -> dict[str, Any]:
    """Validate + normalise a raw WOOP record.

    Returns {"wish", "outcome", "obstacle", "plan": [{"if", "then"}, ...]}.
    ``plan`` accepts a list of entries or a single string/dict.
    Raises ValueError on anything missing or malformed — a half-formed
    WOOP must never silently become a loop.
    """
    if not isinstance(raw, dict):
        raise ValueError("WOOP record must be an object")
    wish = _non_empty_str(raw.get("wish"), "wish")
    outcome = _non_empty_str(raw.get("outcome"), "outcome")
    obstacle = _non_empty_str(raw.get("obstacle"), "obstacle")
    plan_raw = raw.get("plan")
    if isinstance(plan_raw, (str, dict)):
        plan_raw = [plan_raw]
    if not isinstance(plan_raw, list) or not plan_raw:
        raise ValueError("WOOP 'plan' must be a non-empty list of if-then entries")
    plan = [normalise_plan_entry(entry, i) for i, entry in enumerate(plan_raw)]
    return {"wish": wish, "outcome": outcome, "obstacle": obstacle, "plan": plan}


def woop_to_criteria(woop: dict[str, Any]) -> list[dict[str, Any]]:
    """Success criteria derived from the WOOP Outcome.

    One ``judge`` criterion on the best-outcome text: the loop is done
    when the outcome is realised, judged against the evidence it
    produced. Callers that need finer criteria pass explicit criteria
    alongside the WOOP record instead.
    """
    return [
        {
            "description": f"Best outcome realised: {woop['outcome']}",
            "check": "judge",
            "needle": "",
        }
    ]


def _step(step_id: str, instruction: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "instruction": instruction,
        "status": "pending",
        "attempts": 0,
        "result": "",
    }


def woop_plan(woop: dict[str, Any], criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Plan steps for a WOOP-structured loop.

    Order: work the wish toward the outcome; one step per if-then plan
    entry; an obstacle-watch step; then one evidence step per success
    criterion (same wording as the goal loop's default per-criterion
    steps, so criteria are judged against produced evidence).
    """
    wish = woop["wish"]
    outcome = woop["outcome"]
    obstacle = woop["obstacle"]
    steps = [
        _step(
            "s1",
            f"Work on this goal and report concrete progress: {wish} "
            f"(best outcome: {outcome}).",
        )
    ]
    n = 1
    for entry in woop["plan"]:
        n += 1
        if entry["if"]:
            instruction = (
                f"WOOP plan — if {entry['if']}, then {entry['then']} "
                f"(goal: {wish}). Carry out the response and report what happened."
            )
        else:
            instruction = (
                f"WOOP plan — {entry['then']} (goal: {wish}). "
                "Carry it out and report what happened."
            )
        steps.append(_step(f"s{n}", instruction))
    n += 1
    steps.append(
        _step(
            f"s{n}",
            f"Check whether the obstacle has appeared: {obstacle} "
            f"(goal: {wish}). If it has, apply the if-then plan response "
            "and report what happened; if it has not appeared, say so plainly.",
        )
    )
    for i, crit in enumerate(criteria):
        n += 1
        steps.append(
            _step(
                f"s{n}",
                "For the goal "
                f"'{wish}', produce evidence for this success criterion: "
                f"{crit['description']}. Report exactly what exists now, "
                "with specifics — do not claim anything you cannot show.",
            )
        )
    return steps


def format_woop_summary(woop: dict[str, Any]) -> str:
    """One-line WOOP record for loop summaries and reports."""
    plans = "; ".join(
        (f"if {p['if']}, then {p['then']}" if p["if"] else p["then"])
        for p in woop["plan"]
    )
    return (
        f"WOOP — Wish: {woop['wish']} | Outcome: {woop['outcome']} | "
        f"Obstacle: {woop['obstacle']} | Plan: {plans}"
    )
