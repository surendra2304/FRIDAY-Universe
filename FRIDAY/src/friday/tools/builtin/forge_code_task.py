"""TASK-FOR-002: real code tasks through FRIDAY chat, executed by Forge.

"Friday, write me a script that does X" must reach Forge — the fleet's
software engineering agent — and return the REAL result of its sandboxed
build (plan, files, verification manifest), never a fabricated "done".
Forge's sandbox was security-reviewed under TASK-FOR-001 (approved; see
docs/security/FORGE_SANDBOX_REVIEW_2026-11-10.md).

Truthfulness rules:
- the reply carries Forge's actual result (plan summary, verification
  stages, artifacts) — nothing invented;
- a FAILED/PARTIAL_FAILURE delegation is reported as such;
- a dispatch failure is an honest error, never a fake success;
- the sandboxed execution is Forge's own (allow_network stays off by
  default; git push requires separate authorization inside Forge).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)


def _format_build(data: dict[str, Any], summary: str) -> str:
    """Render Forge's build result for the owner."""
    lines: list[str] = []
    if summary:
        lines.append(summary)
    plan = data.get("plan") or {}
    if isinstance(plan, dict):
        steps = plan.get("steps") or plan.get("subtasks") or []
        if steps:
            lines.append("")
            lines.append("Plan:")
            for i, s in enumerate(steps[:6], 1):
                text = s.get("description", s.get("title", s)) if isinstance(s, dict) else str(s)
                lines.append(f"  {i}. {str(text)[:120]}")
    manifest = data.get("verification_manifest") or {}
    stages = manifest.get("stages") if isinstance(manifest, dict) else None
    if isinstance(stages, list) and stages:
        passed = sum(1 for st in stages if str(st.get("status", "")).lower() in {"passed", "pass", "success"})
        lines.append("")
        lines.append(f"Verification: {passed}/{len(stages)} stages passed.")
    artifacts = data.get("artifacts") or []
    if artifacts:
        names = [str(a.get("name", a.get("path", a))) if isinstance(a, dict) else str(a) for a in artifacts[:6]]
        lines.append(f"Artifacts: {', '.join(names)}")
    if not lines:
        lines.append("Forge completed the task in its sandbox (no further detail was returned).")
    lines.append("")
    lines.append("Executed inside Forge's sandboxed workspace (security-reviewed, TASK-FOR-001).")
    return "\n".join(lines)


class ForgeCodeTool(BaseTool):
    """Delegate a real code task to Forge and return its sandboxed build result."""

    name = "forge_code_task"
    description = (
        "Send a software engineering task to Forge, the fleet's code agent: "
        "write a script/program/function, build a tool, fix a bug, refactor, "
        "or review code. Forge plans and executes the task inside its "
        "security-reviewed sandboxed workspace and returns the real result "
        "(plan, artifacts, verification). Use for requests like 'write me a "
        "script that renames files', 'build a small web page', 'fix this "
        "bug', 'refactor this function'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 240.0
    parameters = {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "The code task, described naturally (e.g. 'write a Python script that converts CSV to JSON').",
            },
            "requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit requirements.",
                "default": [],
            },
        },
        "required": ["goal"],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def _dispatch(self, goal: str, requirements: list[str]) -> Any:
        from friday.core.task_envelope import TaskEnvelope

        envelope = TaskEnvelope(
            capability="forge.build",
            objective=goal,
            action="build",
            target_agent="forge",
            payload={"goal": goal, "requirements": requirements, "execute_now": True},
        )
        return asyncio.run(self._client().dispatch_task(envelope))

    def execute(self, goal: str = "", requirements: list[str] | None = None, **kwargs: Any) -> ToolResult:
        goal = (goal or "").strip()
        requirements = [str(r) for r in (requirements or []) if str(r).strip()]
        if not goal:
            return ToolResult(
                name=self.name,
                content="I need the code task described to send it to Forge.",
                is_error=True,
                safety_level=self.safety_level,
            )
        try:
            result = self._dispatch(goal, requirements)
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Forge for that code task "
                    f"({type(exc).__name__}: {exc}). Nothing was built — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        status = str(getattr(result, "status", "")).upper()
        if status not in {"SUCCESS", "COMPLETED"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            summary = getattr(result, "summary", "") or ""
            return ToolResult(
                name=self.name,
                content=(
                    f"Forge could not complete that code task: {error}."
                    + (f" {summary}" if summary else "")
                    + " That is the real outcome — nothing was fabricated."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "error": error},
            )

        data = getattr(result, "result", None) or {}
        if not isinstance(data, dict):
            data = {"summary": str(data)}
        summary = str(getattr(result, "summary", "") or data.get("summary", ""))
        content = _format_build(data, summary)
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "forge": {
                    "task_id": getattr(result, "task_id", ""),
                    "execution_time_ms": getattr(result, "execution_time_ms", 0),
                    "status": status,
                },
                "raw": json.dumps(data, default=str)[:4000],
            },
        )
