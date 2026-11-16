"""Tools for TASK-IG-FRD-001 goal-loop autonomy.

``start_goal_loop`` registers a goal + success criteria and (by default)
runs the loop to its terminal state through the real chat brain, returning
the completion report. ``goal_loop_status`` reads loop state back. The
engine lives in ``friday.autonomous.goal_loop``; these tools are the thin
agent-facing surface.
"""

from __future__ import annotations

import json
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


def _store():
    from friday.autonomous.goal_loop import GoalLoopStore

    return GoalLoopStore()


class StartGoalLoopTool(BaseTool):
    """Register a goal with success criteria and work it autonomously."""

    name = "start_goal_loop"
    description = (
        "Start a goal loop: give FRIDAY a goal plus explicit success criteria; "
        "FRIDAY works it autonomously in cycles and returns a completion report "
        "showing which criteria are met and which are not, with evidence."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "The goal to work, in plain words."},
            "criteria": {
                "type": "array",
                "description": (
                    "Success criteria, one object per criterion: "
                    "{description, check, needle}. description is the "
                    "criterion text; check is one of contains / "
                    "not_contains / judge / manual (default judge); "
                    "needle is the text to look for (required when "
                    "check is contains or not_contains). A plain string "
                    "is also accepted and means {description: that string}."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "The criterion text.",
                        },
                        "check": {
                            "type": "string",
                            "enum": ["contains", "not_contains", "judge", "manual"],
                            "description": (
                                "How the criterion is evaluated "
                                "(default judge)."
                            ),
                        },
                        "needle": {
                            "type": "string",
                            "description": (
                                "Text to look for in the evidence; "
                                "required when check is contains or "
                                "not_contains."
                            ),
                        },
                        "id": {
                            "type": "string",
                            "description": "Optional criterion id.",
                        },
                    },
                    "required": ["description"],
                },
            },
            "max_cycles": {
                "type": "integer",
                "description": "Cycle budget (default 5, ceiling 50).",
            },
            "run_now": {
                "type": "boolean",
                "description": "Run cycles immediately (default true); false only registers the loop.",
            },
        },
        "required": ["goal", "criteria"],
    }

    def execute(
        self,
        goal: str = "",
        criteria: Any = None,
        max_cycles: int = 5,
        run_now: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            store = _store()
            loop = store.create(
                goal or "",
                list(criteria or []),
                max_cycles=int(max_cycles or 5),
                source="tool:start_goal_loop",
            )
            if run_now:
                loop = store.run_until_terminal(loop["id"])
            report = loop.get("report") or ""
            from friday.autonomous.goal_loop import format_loop_summary

            content = format_loop_summary(loop)
            if report:
                content = f"{content}\n\n{report}"
            return ToolResult(
                name=self.name,
                content=content,
                is_error=False,
                metadata={"loop_id": loop["id"], "status": loop["status"]},
            )
        except (ValueError, KeyError) as exc:
            return ToolResult(
                name=self.name,
                content=f"Could not start the goal loop: {exc}",
                is_error=True,
            )


class GoalLoopStatusTool(BaseTool):
    """Read back goal-loop state: one loop by id, or all loops."""

    name = "goal_loop_status"
    description = (
        "Check goal loops: pass a loop id for its full report, or no id to "
        "list every loop with its status and criteria progress."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "loop_id": {"type": "string", "description": "Optional goal loop id."},
        },
        "required": [],
    }

    def execute(self, loop_id: str = "", **kwargs: Any) -> ToolResult:
        from friday.autonomous.goal_loop import format_loop_summary

        store = _store()
        if loop_id:
            loop = store.get(loop_id)
            if loop is None:
                return ToolResult(
                    name=self.name,
                    content=f"No goal loop with id {loop_id!r}.",
                    is_error=True,
                )
            content = format_loop_summary(loop)
            if loop.get("report"):
                content = f"{content}\n\n{loop['report']}"
            return ToolResult(name=self.name, content=content)
        loops = store.list()
        if not loops:
            return ToolResult(name=self.name, content="No goal loops exist yet.")
        lines = [format_loop_summary(l) for l in loops]
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"count": len(loops), "loops": [l["id"] for l in loops]},
        )


__all__ = ["StartGoalLoopTool", "GoalLoopStatusTool"]
