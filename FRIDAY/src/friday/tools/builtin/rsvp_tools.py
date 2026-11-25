"""TASK-FRD-058 — RSVP speed-reading aid tools.

Create a reading session from pasted text or an article URL (the
agent returns the reading-surface link), and control a session —
pause/resume, change the rate, jump to a position — so the owner can
drive the reader by voice or chat while the page shows the words.
"""

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool
from friday.workflows import rsvp as rsvp_workflow


class CreateRSVPSessionTool(BaseTool):
    """Start an RSVP reading session from text or an article URL."""

    name = "create_rsvp_session"
    description = (
        "Start a speed-reading (RSVP) session from pasted text or an article URL: "
        "FRIDAY shows the words one at a time at the given words-per-minute rate "
        "on the reading surface (/static/rsvp.html). Returns the session link, "
        "word count and rate."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to read, or an article URL (https://...).",
            },
            "wpm": {
                "type": "integer",
                "description": "Words per minute (50-1000, default 250).",
            },
            "title": {
                "type": "string",
                "description": "Optional title for the session.",
            },
        },
        "required": ["text"],
    }

    def execute(self, text: str = "", wpm: int | None = None, title: str | None = None, **kwargs: Any) -> ToolResult:
        if not (text or "").strip():
            return ToolResult(name=self.name, content="Nothing to read: no text provided.", is_error=True, safety_level=self.safety_level)
        result = rsvp_workflow.create_session(text.strip(), wpm=wpm, title=title)
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not start a reading session: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        return ToolResult(
            name=self.name,
            content=(
                f"Reading session ready: {result['word_count']} words at {result['wpm']} WPM. "
                f"Open the reading surface: {result['url']}"
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "session_id": result["session_id"],
                "word_count": result["word_count"],
                "wpm": result["wpm"],
                "url": result["url"],
            },
        )


class ControlRSVPSessionTool(BaseTool):
    """Pause/resume, change the rate, or jump in an RSVP session."""

    name = "control_rsvp_session"
    description = (
        "Control a running RSVP reading session: pause or resume it, change the "
        "words-per-minute rate, or jump to a word position. Only the fields "
        "given are changed. Use this when the owner says pause, resume, faster, "
        "slower, or names a rate while reading."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The RSVP session id.",
            },
            "wpm": {
                "type": "integer",
                "description": "New words-per-minute rate (50-1000).",
            },
            "paused": {
                "type": "boolean",
                "description": "True to pause, False to resume.",
            },
            "position": {
                "type": "integer",
                "description": "Jump to this word position (0-based).",
            },
        },
        "required": ["session_id"],
    }

    def execute(self, session_id: str = "", wpm: int | None = None, paused: bool | None = None, position: int | None = None, **kwargs: Any) -> ToolResult:
        if not (session_id or "").strip():
            return ToolResult(name=self.name, content="No session id provided.", is_error=True, safety_level=self.safety_level)
        result = rsvp_workflow.control_session(
            session_id.strip(), wpm=wpm, paused=paused, position=position
        )
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not control that reading session: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        state = "paused" if result["paused"] else "reading"
        return ToolResult(
            name=self.name,
            content=(
                f"Session {result['id']}: {state} at {result['wpm']} WPM, "
                f"word {result['position'] + 1} of {result['word_count']} ({result['percent']}%)."
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "session_id": result["id"],
                "wpm": result["wpm"],
                "paused": result["paused"],
                "position": result["position"],
            },
        )


__all__ = ["CreateRSVPSessionTool", "ControlRSVPSessionTool"]
