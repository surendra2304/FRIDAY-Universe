"""TASK-FRD-058 — RSVP speed-reading tools.

Lets the agent start an RSVP reading session from pasted text or an
article URL, control it (pause / resume / rate / jump), and report
where the reader is. The reading surface is ``/static/rsvp.html``;
these tools are the voice/chat equivalent — the owner asks FRIDAY to
read something, and she presents it word by word at the chosen rate.
"""

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool
from friday.workflows import rsvp


class RsvpStartTool(BaseTool):
    """Start an RSVP speed-reading session from text or an article URL."""

    name = "rsvp_start"
    description = (
        "Start a speed-reading (RSVP) session: present pasted text or an "
        "article URL word by word at an adjustable words-per-minute rate. "
        "Pass text or url plus an optional wpm (60-1200, default 300). "
        "Returns the session id and word count; use rsvp_control to pause, "
        "resume, change rate, or jump, and rsvp_status to see progress."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to read word by word.",
            },
            "url": {
                "type": "string",
                "description": "Article URL to fetch and read (alternative to text).",
            },
            "wpm": {
                "type": "integer",
                "description": "Reading rate in words per minute, 60-1200; default 300.",
            },
            "title": {
                "type": "string",
                "description": "Title for the session, shown on the reading surface.",
            },
        },
        "required": [],
    }

    def execute(
        self,
        text: str = "",
        url: str = "",
        wpm: int | None = None,
        title: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        if not (text or "").strip() and not (url or "").strip():
            return ToolResult(
                name=self.name,
                content="Nothing to read: pass text to read or an article URL.",
                is_error=True,
                safety_level=self.safety_level,
            )
        result = rsvp.create_session(
            text or None,
            url=(url or "").strip() or None,
            wpm=rsvp.DEFAULT_WPM if wpm is None else wpm,
            title=title or "",
        )
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not start the reading session: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        return ToolResult(
            name=self.name,
            content=(
                f"RSVP session {result['session_id']} started — "
                f"{result['total_words']} words at {result['wpm']} wpm. "
                f"Open /static/rsvp.html to read, or ask me to pause, resume, "
                f"change the rate, or jump."
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "session_id": result["session_id"],
                "total_words": result["total_words"],
                "wpm": result["wpm"],
                "title": result.get("title", ""),
            },
        )


class RsvpControlTool(BaseTool):
    """Pause, resume, change rate, or jump within an RSVP session."""

    name = "rsvp_control"
    description = (
        "Control an RSVP reading session: pause, resume, set the rate "
        "(set_rate + wpm), or jump to a word position (jump + position). "
        "Pass the session id from rsvp_start."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session id returned by rsvp_start.",
            },
            "action": {
                "type": "string",
                "description": "One of: pause, resume, set_rate, jump.",
            },
            "wpm": {
                "type": "integer",
                "description": "New rate for set_rate (60-1200).",
            },
            "position": {
                "type": "integer",
                "description": "Word position to jump to (0-based).",
            },
        },
        "required": ["session_id", "action"],
    }

    def execute(
        self,
        session_id: str = "",
        action: str = "",
        wpm: int | None = None,
        position: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not (session_id or "").strip():
            return ToolResult(
                name=self.name,
                content="No session id provided.",
                is_error=True,
                safety_level=self.safety_level,
            )
        result = rsvp.control_session(
            session_id.strip(), action=action or "", wpm=wpm, position=position
        )
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not control the reading session: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        state = "paused" if result["paused"] else "reading"
        return ToolResult(
            name=self.name,
            content=(
                f"Session {result['session_id']} — {state} at "
                f"{result['wpm']} wpm, word {result['position'] + 1} of "
                f"{result['total_words']} ({result['percent']}%)."
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "session_id": result["session_id"],
                "position": result["position"],
                "total_words": result["total_words"],
                "wpm": result["wpm"],
                "paused": result["paused"],
            },
        )


class RsvpStatusTool(BaseTool):
    """Report where an RSVP session is, and the current word."""

    name = "rsvp_status"
    description = (
        "Report an RSVP reading session's progress: current word, "
        "position, total words, percent read, rate, and paused state. "
        "Pass the session id from rsvp_start."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session id returned by rsvp_start.",
            },
        },
        "required": ["session_id"],
    }

    def execute(self, session_id: str = "", **kwargs: Any) -> ToolResult:
        if not (session_id or "").strip():
            return ToolResult(
                name=self.name,
                content="No session id provided.",
                is_error=True,
                safety_level=self.safety_level,
            )
        progress = rsvp.session_progress(session_id.strip())
        if not progress.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not read the session: {progress.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        word = rsvp.current_word(session_id.strip())
        current = word.get("word", "") if word.get("ok") else "(end of text)"
        state = "paused" if progress["paused"] else "reading"
        return ToolResult(
            name=self.name,
            content=(
                f"Session {progress['session_id']} ({progress.get('title', '')}) — "
                f"{state} at {progress['wpm']} wpm, word "
                f"{progress['position'] + 1} of {progress['total_words']} "
                f"({progress['percent']}%). Current word: {current}"
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "session_id": progress["session_id"],
                "position": progress["position"],
                "total_words": progress["total_words"],
                "wpm": progress["wpm"],
                "paused": progress["paused"],
                "current_word": current,
            },
        )


__all__ = ["RsvpControlTool", "RsvpStartTool", "RsvpStatusTool"]
