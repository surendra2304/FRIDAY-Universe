"""Checklist C7 (MASTER_COMPLETION_CHECKLIST, batch 3): VyralX video scripts via chat.

The owner asks in plain words ("draft a video script about the new trading
strategies", "write a youtube script on fleet automation") and VyralX's REAL
Hyperframes engine drafts it — the same script pipeline VyralX serves at
POST /api/v1/vyralx/engines/hyperframes/create-script: scene composition,
pacing optimization, and the HTML scene manifest.

Honesty rules:
- script DRAFTING only: nothing is rendered, uploaded or published;
- every failure (connection, non-2xx) is returned honestly;
- empty engine results are reported as-is, never invented.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from friday.tools.base import BaseTool
from friday.core.types import SafetyLevel, ToolResult


def _extract_title(text: str) -> str:
    """Pull a short title out of the request; default to a trimmed request."""
    low = (text or "").strip().rstrip(".!? ")
    m = re.search(r"['\"]([^'\"]{3,90})['\"]", low)
    if m:
        return m.group(1).strip()
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
        r"(?:draft|write|create|generate|make|compose)\s+(?:me\s+)?(?:a\s+|an\s+)?"
        r"(?:youtube\s+|video\s+|short\s+)?(?:script|screenplay|video script)\s*"
        r"(?:about|on|for|covering)?\s*",
        "", low, flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip()
    if 3 <= len(cleaned) <= 90:
        return cleaned
    return (low[:80] + "…") if len(low) > 80 else (low or "Untitled video")


class VyralXScriptTool(BaseTool):
    """Draft a real video script via VyralX, the fleet's content agent."""

    name = "vyralx_script"
    description = (
        "Draft a real video script with VyralX's Hyperframes engine: scene "
        "breakdown, pacing optimization and the HTML scene manifest for a "
        "given title/topic. Returns the scene count, total duration and the "
        "first scenes. This is a DRAFT only — nothing is rendered, uploaded "
        "or published. Use for requests like 'draft a video script about "
        "quantum computing', 'write a youtube script on fleet automation'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 45.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The script request in plain words (e.g. 'draft a video script about AI agents').",
            },
            "title": {
                "type": "string",
                "description": "Optional explicit title; extracted from the question when omitted.",
            },
            "text": {
                "type": "string",
                "description": "Optional body text the script should cover; defaults to the request itself.",
            },
        },
        "required": [],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def execute(
        self,
        question: str = "",
        title: str = "",
        text: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        question = (question or "").strip()
        title = (title or "").strip() or _extract_title(question)
        text = (text or "").strip() or question or title

        try:
            result = asyncio.run(self._client().request_vyralx_script(title=title, text=text))
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach VyralX for that script ({type(exc).__name__}: {exc}). "
                    "I won't invent a script — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        reply = str((result or {}).get("reply", "") or "")
        if not reply:
            return ToolResult(
                name=self.name,
                content=(
                    "VyralX did not return a readable script draft. "
                    "That is the real outcome — nothing was invented."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": "empty_reply"},
            )
        return ToolResult(
            name=self.name,
            content=reply,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "vyralx": {
                    k: v for k, v in ((result or {}).get("metadata", {}) or {}).items() if k != "agent_id"
                },
                "raw": str(result)[:4000],
            },
        )
