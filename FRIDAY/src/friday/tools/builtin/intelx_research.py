"""TASK-INT-002: IntelX research briefs through FRIDAY chat.

"Friday, research X and give me the highlights" must reach IntelX — the
fleet's Macro Research & Evidence Engine — and return its REAL brief with
citations, never a synthesized guess. This tool dispatches a research query
to IntelX through the shared FleetClient (circuit breaker, real HTTP) and
formats the evidence-based brief for the owner.

Truthfulness rules:
- the brief content comes from IntelX's response only;
- "no conclusive evidence" from IntelX is reported as-is (it is a finding,
  not a failure);
- a dispatch failure is an honest error with the reason — never a fabricated
  summary.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)


def _format_brief(data: dict[str, Any]) -> str:
    """Render IntelX's research result as the owner's highlights."""
    query = data.get("query", "")
    text = str(data.get("text_response") or data.get("response") or "").strip()
    spoken = str(data.get("spoken_summary") or "").strip()
    citations = data.get("citations_count")
    sources = data.get("sources") or []

    lines = [f"Research brief — {query}" if query else "Research brief"]
    if spoken:
        lines.append(f"Bottom line: {spoken}")
    if text:
        lines.append("")
        lines.append(text)
    if citations is not None:
        lines.append("")
        lines.append(f"Evidence: {citations} citation(s) from IntelX.")
    if sources:
        names = ", ".join(str(s.get("name", s.get("source", s)))[:60] for s in sources[:5])
        lines.append(f"Sources: {names}")
    if not spoken and not text:
        lines.append(
            "IntelX returned an empty brief for this query. That is its real "
            "answer — I won't invent highlights."
        )
    return "\n".join(lines)


class IntelXResearchTool(BaseTool):
    """Dispatch a research query to IntelX and return its evidence-based brief."""

    name = "intelx_research"
    description = (
        "Send a research request to IntelX, the fleet's Macro Research & "
        "Evidence Engine, and get back an evidence-based brief with citations. "
        "Use this when the owner asks to research a topic, get the highlights "
        "on something, or wants sourced findings — e.g. 'research the crypto "
        "market and give me the highlights'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 60.0
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question or topic to investigate.",
            },
            "scope": {
                "type": "string",
                "description": "Optional scope hint for the research (e.g. 'quick check', 'deep dive').",
            },
        },
        "required": ["query"],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def _dispatch(self, query: str, scope: str) -> Any:
        from friday.core.task_envelope import TaskEnvelope

        envelope = TaskEnvelope(
            capability="intelx.research",
            objective=f"Research: {query}",
            action="research",
            target_agent="intelx",
            payload={"topic": query, **({"scope": scope} if scope else {})},
        )
        return asyncio.run(self._client().dispatch_task(envelope))

    def execute(self, query: str = "", scope: str = "", **kwargs: Any) -> ToolResult:
        query = (query or "").strip()
        if not query:
            return ToolResult(
                name=self.name,
                content="I need a research question to send to IntelX.",
                is_error=True,
                safety_level=self.safety_level,
            )
        try:
            result = self._dispatch(query, scope.strip())
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach IntelX for that research "
                    f"({type(exc).__name__}: {exc}). I won't guess — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        status = str(getattr(result, "status", "")).lower()
        if status not in {"success", "completed"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            return ToolResult(
                name=self.name,
                content=(
                    f"IntelX could not complete that research: {error}. "
                    "That is the real outcome — no highlights were fabricated."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "error": error},
            )

        data = getattr(result, "result", None) or {}
        if not isinstance(data, dict):
            data = {"text_response": str(data)}
        brief = _format_brief(data)
        return ToolResult(
            name=self.name,
            content=brief,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "intelx": {
                    "task_id": getattr(result, "task_id", ""),
                    "execution_time_ms": getattr(result, "execution_time_ms", 0),
                    "citations_count": data.get("citations_count"),
                    "query": data.get("query", query),
                },
                "raw": json.dumps(data, default=str)[:4000],
            },
        )
