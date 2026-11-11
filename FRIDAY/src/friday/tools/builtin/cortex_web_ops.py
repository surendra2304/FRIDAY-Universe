"""Checklist C9 (MASTER_COMPLETION_CHECKLIST, batch 3): Cortex web-ops monitor via chat.

The owner asks in plain words ("how are my websites doing", "check the web
properties", "cortex status") and gets Cortex's REAL operational picture —
the same FRIDAY contract Cortex serves at GET /v1/friday/health_summary and
GET /v1/friday/properties: uptime indicator, 24h incident/error counts,
cognitive-loop activity, and the governed web-properties roster.

Honesty rules:
- read-only monitoring: no lead, outreach or production operation runs;
- every failure (auth, connection, non-2xx) is returned honestly;
- an empty properties roster is reported as an honest empty, never padded.
"""

from __future__ import annotations

import asyncio
from typing import Any

from friday.tools.base import BaseTool
from friday.core.types import SafetyLevel, ToolResult


class CortexWebOpsTool(BaseTool):
    """Monitor the fleet's web properties through Cortex (read-only)."""

    name = "cortex_web_ops"
    description = (
        "Read-only web-operations monitor via Cortex, the fleet's Web "
        "Operations & Growth agent: uptime indicator, 24h incidents and error "
        "counts, cognitive-loop activity, and every website/web app under "
        "Cortex governance. No lead, outreach or production operation is "
        "performed. Use for requests like 'how are my websites doing', "
        "'check my web properties', 'cortex web status', 'site health'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 30.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The monitoring request in plain words (e.g. 'how are my websites doing').",
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

    def execute(self, question: str = "", **kwargs: Any) -> ToolResult:
        try:
            result = asyncio.run(self._client().request_cortex_web_ops())
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Cortex for that monitoring check ({type(exc).__name__}: {exc}). "
                    "I won't invent a status — try again shortly."
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
                    "Cortex did not return a readable monitoring picture. "
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
                "cortex": {
                    k: v for k, v in ((result or {}).get("metadata", {}) or {}).items() if k != "agent_id"
                },
                "raw": str(result)[:4000],
            },
        )
