"""TASK-FRD-060 — Daily Signal Brief tool.

Generate FRIDAY's on-demand Daily Signal Brief from live IntelX
standing-watch data. Read-only: it reads IntelX's watch outbox files
and saves the brief locally. It never sends anything, never enables a
watch, and there is no routine schedule behind it — the brief is
produced only when asked.
"""

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool
from friday.workflows import signal_brief as brief_workflow


class GenerateSignalBriefTool(BaseTool):
    """Generate the Daily Signal Brief on demand from live IntelX data."""

    name = "generate_signal_brief"
    description = (
        "Generate FRIDAY's Daily Signal Brief on demand from live IntelX "
        "standing-watch data: the top signals of the last 24 hours with "
        "their watch, significance score and source, plus watch coverage. "
        "Use this when the owner asks for the signal brief, the daily brief, "
        "or what IntelX is flagging. On-demand only — no routine schedule."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "description": "Coverage window in hours (default 24).",
            },
        },
        "required": [],
    }

    def execute(self, hours: int | None = None, **kwargs: Any) -> ToolResult:
        window = hours if isinstance(hours, int) and hours > 0 else brief_workflow.DEFAULT_WINDOW_HOURS
        result = brief_workflow.generate_brief(hours=window)
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not generate the signal brief: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        return ToolResult(
            name=self.name,
            content=result["markdown"],
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "signal_count": result["signal_count"],
                "watch_count": result["watch_count"],
                "date": result["date"],
                "window_hours": result["window_hours"],
                "saved_to": result.get("saved_to"),
            },
        )


__all__ = ["GenerateSignalBriefTool"]
