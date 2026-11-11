"""Checklist C11 (MASTER_COMPLETION_CHECKLIST, batch 3): Memora memory ops as first-class tasks.

The owner asks in plain words ("search Memora for the deployment runbook",
"save this to fleet memory: the demo account was reset") and the operation
runs against Memora's REAL context-database surface — the same endpoints
Memora serves at GET /v1/context/search and POST /v1/context/write.

Honesty rules:
- an empty search is an honest empty, never a padded answer;
- every failure (auth, connection, non-2xx) is returned honestly;
- this is Memora's cloud memory, distinct from FRIDAY's local memory —
  the reply labels the source.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from friday.tools.base import BaseTool
from friday.core.types import SafetyLevel, ToolResult


def _extract_query(text: str) -> str:
    """Clean the memory request into a search query."""
    low = (text or "").strip().rstrip(".!? ")
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
        r"(?:search|query|look up|find|recall|check)\s+"
        r"(?:in\s+)?(?:the\s+)?(?:memora|fleet\s+memory|cloud\s+memory|memory)\s*"
        r"(?:for|about|about the|for the)?\s*",
        "", low, flags=re.IGNORECASE,
    )
    return cleaned.strip() or low


def _extract_content(text: str) -> str:
    """Clean a save request into the content to store."""
    low = (text or "").strip().rstrip(".!? ")
    m = re.search(r"(?:saying|that|content)\s*[:\-]\s*(.+)$", low, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
        r"(?:save|store|remember|write)\s+(?:this\s+)?(?:to|in|into)\s+"
        r"(?:the\s+)?(?:memora|fleet\s+memory|cloud\s+memory|memory)\s*[:\-]?\s*",
        "", low, flags=re.IGNORECASE,
    )
    return cleaned.strip() or low


class MemoraMemoryTool(BaseTool):
    """Run a real memory operation on Memora, the fleet's persistent memory fabric."""

    name = "memora_memory"
    description = (
        "Run a real memory operation on Memora, the fleet's persistent cloud "
        "memory: search/recall ('search Memora for the deployment runbook') "
        "or write/store ('save this to fleet memory: the demo account was "
        "reset'). Honest empty results, honest failures — never invented "
        "memories. This is Memora's cloud memory, distinct from FRIDAY's "
        "local memory."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 30.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The memory request in plain words (e.g. 'search memora for deployment steps').",
            },
            "op": {
                "type": "string",
                "enum": ["search", "write"],
                "description": "Memory operation (default: inferred from the question).",
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

    def execute(self, question: str = "", op: str = "", **kwargs: Any) -> ToolResult:
        question = (question or "").strip()
        low = question.lower()
        if op not in ("search", "write"):
            op = "write" if re.search(r"\b(?:save|store|remember|write)\b.*\b(?:to|into)\b", low) else "search"
        if not question:
            return ToolResult(
                name=self.name,
                content="What should I look for in Memora? Give me a query or a fact to store.",
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": "empty_question"},
            )

        query = _extract_query(question) if op == "search" else ""
        content = _extract_content(question) if op == "write" else ""

        try:
            result = asyncio.run(
                self._client().request_memora_memory_op(op=op, query=query, content=content)
            )
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Memora for that memory operation ({type(exc).__name__}: {exc}). "
                    "I won't invent a result — try again shortly."
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
                    "Memora did not return a readable result. "
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
                "memora": {
                    k: v for k, v in ((result or {}).get("metadata", {}) or {}).items() if k != "agent_id"
                },
                "raw": str(result)[:4000],
            },
        )
