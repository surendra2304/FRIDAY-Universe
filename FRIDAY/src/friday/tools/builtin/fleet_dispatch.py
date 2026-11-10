"""TASK-ORCH-006 (checklist C6/C14): generic fleet delegation through FRIDAY chat.

"Assign a quick task to IntelX" / "send this to Sentinel" / "have VyralX write
a script" must become a REAL dispatch to the named agent — not an invented
<execute_agent> XML tag emitted as text (live 2026-11-11 IST: the model,
given no delegation tool, fabricated one on screen). This tool gives the
brain the missing surface: normalize the agent name, build a typed
TaskEnvelope, dispatch through the shared FleetClient (circuit breaker, real
HTTP, per-agent contract endpoints), and hand back the agent's REAL result
with a task-id receipt the owner can reference later.

Truthfulness rules:
- the result content comes from the target agent's response only;
- BLOCKED/FAILED/PENDING statuses are reported as-is with their reason —
  never rewritten into a success;
- an unknown agent name is an honest error listing the nine fleet agents;
- no result is ever synthesized.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)

# The nine specialist agents of FRIDAY Universe (FRIDAY itself is the
# dispatcher and is deliberately not a dispatch target).
FLEET_AGENTS: dict[str, str] = {
    "inference": "Cloud AI Gateway (multi-model consensus)",
    "memora": "Persistent Memory",
    "stratex": "Markets & Portfolio",
    "intelx": "Macro Research & Evidence",
    "futuris": "Predictive Forecasting",
    "cortex": "Web Operations",
    "forge": "Software Engineering",
    "sentinel": "Cybersecurity Shield",
    "vyralx": "Video Production",
}

# Common misspellings / variants the owner may type.
_AGENT_ALIASES: dict[str, str] = {
    "intelix": "intelx", "intel x": "intelx", "research": "intelx",
    "memoria": "memora", "memory agent": "memora",
    "stratexs": "stratex", "markets": "stratex", "trading": "stratex",
    "future": "futuris", "forecast": "futuris", "futuristic": "futuris",
    "cortexx": "cortex", "web": "cortex",
    "sentinal": "sentinel", "security": "sentinel", "cyber": "sentinel",
    "viralx": "vyralx", "vyral": "vyralx", "video": "vyralx",
    "inferance": "inference", "gateway": "inference",
    "forgex": "forge", "engineering": "forge", "code agent": "forge",
}


# Display names with canonical capitalization for owner-facing lines.
DISPLAY_NAMES: dict[str, str] = {
    "inference": "Inference", "memora": "Memora", "stratex": "Stratex",
    "intelx": "IntelX", "futuris": "Futuris", "cortex": "Cortex",
    "forge": "Forge", "sentinel": "Sentinel", "vyralx": "VyralX",
}


def normalize_agent(raw: str) -> str | None:
    """Map free-form agent mentions onto the canonical fleet IDs."""
    name = (raw or "").lower().strip().removesuffix("agent").removesuffix("bot").strip()
    name = name.removeprefix("the ").strip()
    if not name or name in {"friday", "you", "yourself"}:
        return None
    if name in FLEET_AGENTS:
        return name
    if name in _AGENT_ALIASES:
        return _AGENT_ALIASES[name]
    # substring pass: "the IntelX agent", "FRIDAY's intelx", typos with spaces
    for canonical in FLEET_AGENTS:
        if canonical in name or name in canonical:
            return canonical
    for alias, canonical in _AGENT_ALIASES.items():
        if alias in name:
            return canonical
    return None


def _format_result(agent: str, role: str, task: str, data: Any) -> str:
    """Render the target agent's real response for the owner."""
    display = DISPLAY_NAMES.get(agent, agent.title())
    lines = [f"{display} ({role}) — result for: {task}"]
    text = ""
    if isinstance(data, dict):
        if any(isinstance(v, (str, int, float, list, dict)) and v for v in data.values()):
            for key in ("text_response", "response", "summary", "output", "message", "result", "answer"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
            if not text:
                # compact JSON so nothing is hidden, truncated for chat
                text = json.dumps(data, default=str, ensure_ascii=False)
                if len(text) > 2000:
                    text = text[:2000] + "…[truncated]"
    elif data is not None and str(data).strip():
        text = str(data)
    lines.append(text if text else f"{display} returned an empty response — that is its real answer, not a failure I will paper over.")
    return "\n".join(lines)


class FleetDispatchTool(BaseTool):
    """Assign a task to a named specialist agent and return its real result."""

    name = "fleet_dispatch"
    description = (
        "Assign a task to one of the nine specialist agents of the FRIDAY fleet "
        "and return the agent's REAL result with a task-id receipt. Agents: "
        "IntelX (research), Stratex (markets/portfolio), Forge (software "
        "engineering), Sentinel (security scans), Cortex (web operations), "
        "Futuris (forecasting), VyralX (video production), Memora (memory "
        "operations), Inference (AI gateway tasks). Use this whenever the owner "
        "asks to assign, delegate, send, or give a task to a named agent — "
        "e.g. 'assign a quick task to IntelX', 'send this scan to Sentinel', "
        "'have VyralX write a video script'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 60.0
    parameters = {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Agent to assign the task to (IntelX, Stratex, Forge, Sentinel, Cortex, Futuris, VyralX, Memora, or Inference).",
            },
            "task": {
                "type": "string",
                "description": "The task to assign, in plain words.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "Task priority (default: normal).",
            },
        },
        "required": ["agent", "task"],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def _dispatch(self, agent: str, task: str, priority: str) -> Any:
        from friday.core.task_envelope import TaskEnvelope, TaskPriority

        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT,
        }
        envelope = TaskEnvelope(
            capability=f"{agent}.task",
            objective=task,
            action="execute",
            target_agent=agent,
            payload={"task": task, "prompt": task},
            priority=priority_map.get(priority, TaskPriority.NORMAL),
        )
        return asyncio.run(self._client().dispatch_task(envelope))

    def execute(self, agent: str = "", task: str = "", priority: str = "normal", **kwargs: Any) -> ToolResult:
        task = (task or "").strip()
        if not task:
            return ToolResult(
                name=self.name,
                content="I need the task itself — what should the agent do?",
                is_error=True,
                safety_level=self.safety_level,
            )
        canonical = normalize_agent(agent)
        if canonical is None:
            roster = ", ".join(FLEET_AGENTS)
            return ToolResult(
                name=self.name,
                content=(
                    f"'{agent}' is not one of my nine agents. The fleet is: {roster}. "
                    "Tell me the agent by name and I'll assign it right away."
                ),
                is_error=True,
                safety_level=self.safety_level,
            )
        role = FLEET_AGENTS[canonical]
        display = DISPLAY_NAMES.get(canonical, canonical.title())
        try:
            result = self._dispatch(canonical, task, (priority or "normal").strip().lower())
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach {display} to assign that task "
                    f"({type(exc).__name__}: {exc}). That is the real outcome — I won't pretend it was dispatched."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}", "agent": canonical},
            )

        status = str(getattr(result, "status", "")).lower()
        task_id = str(getattr(result, "task_id", "") or "")
        execution_time_ms = getattr(result, "execution_time_ms", 0)
        receipt = f"[Task receipt: {task_id}]" if task_id else ""

        if status not in {"success", "completed"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            content = (
                f"{display} could not complete that assignment: {error}. {receipt} "
                "That is the real outcome — nothing was fabricated."
            )
            return ToolResult(
                name=self.name,
                content=content,
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "error": error, "agent": canonical, "task_id": task_id},
            )

        data = getattr(result, "result", None)
        if not isinstance(data, dict):
            data = {"response": str(data)} if data is not None else {}
        body = _format_result(canonical, role, task, data)
        return ToolResult(
            name=self.name,
            content=(f"{body}\n{receipt}").strip(),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "fleet_dispatch": {
                    "agent": canonical,
                    "task_id": task_id,
                    "execution_time_ms": execution_time_ms,
                    "status": status,
                },
                "raw": json.dumps(data, default=str)[:4000],
            },
        )
