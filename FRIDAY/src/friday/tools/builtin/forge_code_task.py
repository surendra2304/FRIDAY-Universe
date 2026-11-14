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
from friday.tools.builtin.fleet_dispatch import record_specialist_dispatch

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
    manifest = data.get("verification_manifest") or data.get("manifest") or {}
    stages = manifest.get("stages") if isinstance(manifest, dict) else None
    if isinstance(stages, dict):
        stages = [dict(value, check_name=value.get("check_name", name))
                  if isinstance(value, dict) else value for name, value in stages.items()]
    if isinstance(stages, list) and stages:
        passed = sum(1 for st in stages if isinstance(st, dict) and (st.get("passed") is True or str(st.get("status", "")).lower() in {"passed", "pass", "success"}))
        lines.append("")
        lines.append(f"Verification: {passed}/{len(stages)} stages passed.")
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            name = str(stage.get("check_name", ""))
            if str(stage.get("category", stage.get("stage", ""))).lower() != "test" and "test" not in name.lower():
                continue
            exit_code = stage.get("exit_code")
            rendered_exit = str(exit_code) if type(exit_code) is int else "not recorded"
            lines.append(f"Test exit code: {rendered_exit} ({name or 'test stage'})")
            command = stage.get("command")
            if isinstance(command, str) and command.strip():
                lines.append(f"Test command: {command}")
    artifacts = data.get("artifacts") or []
    if artifacts:
        names = [str(a.get("name", a.get("path", a))) if isinstance(a, dict) else str(a) for a in artifacts[:6]]
        lines.append(f"Artifacts: {', '.join(names)}")
    if not lines:
        lines.append("Forge returned no build details; execution and verification cannot be established from this response.")
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
            record_specialist_dispatch("", "forge", goal, "failed", error=f"{type(exc).__name__}: {exc}")
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Forge for that code task "
                    f"({type(exc).__name__}: {exc}). The outcome is unconfirmed — check Forge task history before retrying."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        status_value = getattr(result, "status", "")
        status = str(getattr(status_value, "value", status_value)).upper()
        if status not in {"SUCCESS", "COMPLETED"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            record_specialist_dispatch(getattr(result, "task_id", "") or "", "forge", goal, status.lower(), error=str(error))
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
                metadata={"status": status, "error": error,
                          "forge": {"task_id": getattr(result, "task_id", ""), "status": status},
                          "verification_manifest": (getattr(result, "result", None) or {}).get("verification_manifest")
                          if isinstance(getattr(result, "result", None), dict) else None},
            )

        data = getattr(result, "result", None) or {}
        if not isinstance(data, dict):
            data = {"summary": str(data)}
        if isinstance(data.get("result"), dict) and "status" in data:
            outer = data
            data = dict(outer["result"])
            if isinstance(outer.get("verification_manifest"), dict):
                data.setdefault("verification_manifest", outer["verification_manifest"])
        manifest = data.get("verification_manifest") or data.get("manifest") or {}
        if isinstance(manifest, dict) and (manifest.get("all_passed") is False or manifest.get("failed_stages", 0)):
            record_specialist_dispatch(getattr(result, "task_id", "") or "", "forge", goal, "failed", error="verification stages failed")
            return ToolResult(name=self.name, content="Forge returned failing verification evidence. The build is not verified.",
                              is_error=True, safety_level=self.safety_level, metadata={"verification_manifest": manifest})
        stages = manifest.get("stages") if isinstance(manifest, dict) else None
        stages = list(stages.values()) if isinstance(stages, dict) else stages
        verified_stages = isinstance(stages, list) and bool(stages) and all(
            isinstance(stage, dict) and (
                stage.get("passed") is True if "passed" in stage else
                str(stage.get("status", "")).lower() in {"passed", "pass", "success"})
            and ("exit_code" not in stage or type(stage["exit_code"]) is int and stage["exit_code"] == 0)
            for stage in stages)
        if not verified_stages:
            record_specialist_dispatch(getattr(result, "task_id", "") or "", "forge", goal, "failed", error="verification stages unverified")
            return ToolResult(name=self.name,
                              content="Forge did not provide nonempty passing verification stages. Execution and test completion are unverified.",
                              is_error=True, safety_level=self.safety_level,
                              metadata={"verification_manifest": manifest, "completion_verified": False})
        summary = str(getattr(result, "summary", "") or data.get("summary", ""))
        record_specialist_dispatch(getattr(result, "task_id", "") or "", "forge", goal, "success")
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
                "verification_manifest": manifest,
                "artifacts": data.get("artifacts") or [],
                "raw": json.dumps(data, default=str)[:4000],
            },
        )
