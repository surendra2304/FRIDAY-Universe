"""A11 — Long-goal persistence: a goal stated Monday is still tracked Friday.

The owner states a goal once ("my goal this week is to double the demo
account"). FRIDAY stores it as a PINNED memory (category ``goal``,
importance 1.0, ``GOAL (active):`` prefix), recalls it days later on any
goal-shaped query ("what about my goal?" → "Still on it, Boss — …"), marks
it done when the owner says so (auditable supersede, never a hard delete),
and surfaces active goals in the morning brief.

All storage goes through the same auditable Memora lifecycle the memory
commands use; nothing is invented — an unreachable store is reported
honestly and never faked as success.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Protocol

ACTIVE_PREFIX = "GOAL (active): "
DONE_PREFIX = "GOAL (complete): "

_GOAL_STATEMENT_PREFIXES = (
    "my goal this week is", "my goal this month is", "my goal for this week is",
    "my goal is", "my goal:", "this week i want to", "this week i want",
    "i want to finish", "i want to complete", "i'm planning to finish",
    "im planning to finish", "i'm planning to complete", "im planning to complete",
    "my target this week is", "my target is",
)
_GOAL_QUERIES = (
    "what about my goal", "what about the goal", "what's my goal", "whats my goal",
    "what are my goals", "what is my goal", "still working on my goal",
    "still on my goal", "still on it", "are you still on my goal",
    "how is my goal", "how's my goal", "hows my goal", "did you forget my goal",
    "did you lose my goal", "any progress on my goal", "my goal status",
    "what was my goal", "what were my goals", "how are my goals",
)
_GOAL_DONE_PHRASES = (
    "i finished my goal", "i completed my goal", "goal complete", "goal completed",
    "goal done", "i did it", "i finished the goal", "done with my goal",
    "done with the goal", "my goal is complete", "my goal is done",
    "i achieved my goal", "goal achieved",
)


class _GoalClient(Protocol):
    """The subset of MemoraClient the goal lifecycle needs (fakes implement it)."""

    def record_fact(self, agent_name: str, fact_text: str, category: str = "preference", importance: float = 0.95) -> dict[str, Any]: ...

    def recall_memories(self, agent_name: str, query: str, limit: int = 5) -> list[dict[str, Any]]: ...

    def supersede_fact(self, agent_name: str, memory_id: str, winner_id: str = "", reason: str = "") -> dict[str, Any]: ...


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def extract_goal_statement(text: str) -> str | None:
    """Return the goal text when ``text`` states a goal, else None."""

    low = _clean(text).lower().rstrip(".,!")
    for pfx in _GOAL_STATEMENT_PREFIXES:
        if low.startswith(pfx):
            goal = _clean(text)[len(pfx):].strip(" .,:-–")
            # "my goal is TO double…" reads better stored as "double…"
            if goal.lower().startswith("to "):
                goal = goal[3:]
            if len(goal) >= 4:
                return goal
            return None
    return None


def is_goal_query(text: str) -> bool:
    low = _clean(text).lower().rstrip(".,!?")
    return low in _GOAL_QUERIES or any(low == q for q in _GOAL_QUERIES)


def is_goal_done(text: str) -> bool:
    low = _clean(text).lower().rstrip(".,!")
    return low in _GOAL_DONE_PHRASES


def record_goal(client: _GoalClient, goal: str, *, agent_name: str = "friday") -> dict[str, Any]:
    """Store an active goal as a pinned memory. Honest status, never raises."""

    try:
        res = client.record_fact(
            agent_name,
            fact_text=f"{ACTIVE_PREFIX}{goal}",
            category="goal",
            importance=1.0,
        ) or {}
        ok = bool(res) and str(res.get("status", "success")) not in ("error",)
        return {"status": "stored" if ok else "error", "goal": goal}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__, "goal": goal}


def active_goals(client: _GoalClient, *, agent_name: str = "friday", limit: int = 20) -> list[str]:
    """The owner's active goals, most recent first. Empty on failure — never raises."""

    goals: list[str] = []
    try:
        rows = client.recall_memories(agent_name, "GOAL active goal target this week", limit=limit) or []
    except Exception:
        return []
    for row in rows:
        text = _clean(str(row.get("content_text", "")))
        if text.startswith(ACTIVE_PREFIX):
            goal = text[len(ACTIVE_PREFIX):].strip()
            if goal and goal not in goals:
                goals.append(goal)
    return goals


def mark_goal_done(client: _GoalClient, *, agent_name: str = "friday") -> dict[str, Any]:
    """Retire the most recent active goal (supersede — auditable, no hard delete)."""

    try:
        rows = client.recall_memories(agent_name, "GOAL active goal target this week", limit=10) or []
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    for row in rows:
        text = _clean(str(row.get("content_text", "")))
        if not text.startswith(ACTIVE_PREFIX):
            continue
        mem_id = str(row.get("id") or row.get("memory_id") or "")
        goal = text[len(ACTIVE_PREFIX):].strip()
        if not mem_id:
            return {"status": "error", "error": "no_record_id", "goal": goal}
        try:
            res = client.supersede_fact(agent_name, mem_id, reason="goal completed by owner (A11)") or {}
        except Exception as exc:
            return {"status": "error", "error": type(exc).__name__, "goal": goal}
        if str(res.get("status")) == "superseded":
            # keep a done-marker for the audit trail (best effort, non-fatal)
            try:
                client.record_fact(agent_name, f"{DONE_PREFIX}{goal}", category="goal", importance=0.7)
            except Exception:
                pass
            return {"status": "done", "goal": goal}
        return {"status": "error", "error": "supersede_refused", "goal": goal}
    return {"status": "not_found"}


def goal_reply_for_query(client: _GoalClient, *, agent_name: str = "friday") -> dict[str, Any]:
    """Compose the honest 'still on it, Boss' reply for a goal query."""

    goals = active_goals(client, agent_name=agent_name)
    if goals:
        lines = "\n".join(f"• {g}" for g in goals[:3])
        reply = (
            f"Still on it, Boss — I never dropped it. Here's what I'm tracking:\n\n{lines}\n\n"
            "Say 'I finished my goal' when one's done and I'll cross it off."
        )
        return {"reply": reply, "metadata": {"fast_path": True, "conversational": True, "goal_query": True, "active_goals": goals[:3]}}
    return {
        "reply": (
            "I don't have an active goal on file right now, Boss. Tell me one — "
            "'my goal this week is …' — and I'll stay on it until you say it's done."
        ),
        "metadata": {"fast_path": True, "conversational": True, "goal_query": True, "active_goals": []},
    }


def morning_brief_goal_line(client: _GoalClient, *, agent_name: str = "friday") -> str | None:
    """One line for the morning brief: active goals, or None when there are none."""

    goals = active_goals(client, agent_name=agent_name)
    if not goals:
        return None
    first = goals[0]
    extra = f" (+{len(goals) - 1} more)" if len(goals) > 1 else ""
    return f"Goal check: still on it, Boss — {first}{extra}."
