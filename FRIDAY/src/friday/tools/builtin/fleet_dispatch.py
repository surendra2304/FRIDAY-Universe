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
import time
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)


def record_chat_dispatch(task_id: str, agent: str, task: str, status: str,
                         result_summary: Any = None, error: str = "") -> None:
    """Record a chat-path delegation into the unified TaskRecordStore (C13).

    FleetClient posts envelopes straight to the target agent's HTTP endpoint —
    it never flows through the in-process universe dispatch bus, so without
    this hook the C14 receipts the owner sees are never written into the
    shared ledger and "what happened to that IntelX task?" cannot find them
    (live-proven 2026-11-11: dispatch returned task_c132e80e926e; the ledger
    and /api/v1/dispatch/records/report both stayed empty). The full router →
    bus lifecycle is mirrored compactly: create → assigned → dispatched →
    completed | failed. A ledger failure NEVER breaks the dispatch itself.
    """
    try:
        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        if store.get(task_id) is None:
            store.create(task_id, description=task, owner_agent=agent)
            store.record_assignment(task_id, agent, rationale="chat delegation (fleet_dispatch)")
            store.record_dispatch(task_id)
        if status in {"success", "completed"}:
            store.record_completion(task_id, result=result_summary)
        else:
            store.record_failure(task_id, error=error or f"status {status or 'unknown'}")
    except Exception as exc:  # noqa: BLE001 — the ledger must never sink a dispatch
        logger.debug(f"chat dispatch not recorded in task ledger ({type(exc).__name__}: {exc})")


def record_specialist_dispatch(task_id: str, agent: str, task: str, status: str,
                               result_summary: Any = None, error: str = "") -> str:
    """TASK-REL-007C: record a specialist-tool dispatch in the unified ledger.

    Round 1 (2026-11-14) left the console's TASKS DELEGATED counter at 0
    across research/forecast/coding/status asks because ONLY this module's
    FleetDispatchTool wrote to the TaskRecordStore the counter reads — a
    successful Forge build (task14714112026084837) never entered the
    ledger. The specialist tools (IntelX research, Futuris forecast,
    Forge code) now record through here; when the upstream gives no task
    id (Futuris returns a bare reply dict), one is synthesized so the
    delegation is still counted. Returns the id used.
    """
    if not task_id:
        import uuid as _uuid

        task_id = f"task_{_uuid.uuid4().hex[:12]}"
    record_chat_dispatch(task_id, agent, task, status, result_summary, error)
    return task_id


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
    if not name or name in {"friday", "you", "yourself", "me", "us", "him", "her", "them", "it", "myself"}:
        return None
    if name in FLEET_AGENTS:
        return name
    if name in _AGENT_ALIASES:
        return _AGENT_ALIASES[name]
    # Substring pass: "the IntelX agent", "FRIDAY's intelx", typos with
    # spaces. TASK-REL-006A: the reverse direction (name inside canonical)
    # needs a length floor — bare "me" is a substring of "memora", so
    # "tell me a joke" was dispatched to Memora as a task (live-verified
    # 2026-11-14, ledger task_92035ba25301, HTTP 422). Pronouns and other
    # short words must never resolve to an agent by containment.
    for canonical in FLEET_AGENTS:
        if canonical in name:
            return canonical
        if len(name) >= 4 and name in canonical:
            return canonical
    for alias, canonical in _AGENT_ALIASES.items():
        if alias in name:
            return canonical
    return None


# TASK-VYR-002: VyralX tasks are asynchronous (202/queued, worker completes
# them seconds later). The generic dispatch waits — bounded, inside this
# tool's 60s timeout — for VyralX's real finished output instead of handing
# the owner a bare "pending".
_VYRALX_SETTLE_BUDGET_SECONDS = 45.0
_VYRALX_SETTLE_POLL_SECONDS = 2.0


def _format_vyralx_result(task: str, data: dict[str, Any]) -> str | None:
    """Render a finished VyralX task's real output; None -> generic format."""
    pack = data.get("content_pack")
    if isinstance(pack, dict):
        lines = [f"VyralX (Video Production) — result for: {task}"]
        titles = pack.get("title_options") or []
        if isinstance(titles, list) and titles:
            lines.append("Title options: " + " | ".join(str(t) for t in titles[:3]))
        hook = str(pack.get("hook") or "").strip()
        if hook:
            lines.append(f"Hook: {hook}")
        script = str(pack.get("script") or pack.get("voiceover") or "").strip()
        if script:
            lines.append("Script: " + (script if len(script) <= 700 else script[:700] + "…"))
        scenes = pack.get("scene_plan") or []
        if isinstance(scenes, list) and scenes:
            lines.append(f"Scene plan: {len(scenes)} scenes.")
        pack_id = data.get("content_pack_id")
        if pack_id is not None:
            lines.append(
                f"(Content pack #{pack_id}, stored by VyralX. Nothing was rendered or published.)"
            )
        return "\n".join(lines)
    items = data.get("items")
    if isinstance(items, list):
        lines = [f"VyralX (Video Production) — result for: {task}"]
        lines.append(
            f"Discovery query: {data.get('query', '')} — {data.get('count', len(items))} result(s)."
        )
        for item in items[:5]:
            if isinstance(item, dict):
                title = item.get("title") or item.get("name") or "untitled"
                url = item.get("url") or item.get("video_url") or item.get("link") or ""
                lines.append(f"- {title} {url}".strip())
        return "\n".join(lines)
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
        return asyncio.run(self._dispatch_and_settle(agent, envelope))

    async def _dispatch_and_settle(self, agent: str, envelope: Any) -> Any:
        """Dispatch, and for VyralX wait (bounded) for its async task to finish.

        TASK-VYR-002: a VyralX dispatch returns PENDING with a task id while
        its worker runs the task. Poll the task record until it completes or
        fails so the chat answer carries VyralX's real output. If the budget
        ends first, the PENDING result stands untouched — reported as still
        in progress, never upgraded to a success.
        """
        client = self._client()
        result = await client.dispatch_task(envelope)
        if agent != "vyralx":
            return result
        status = str(getattr(result, "status", "") or "").rsplit(".", 1)[-1].strip().lower()
        task_id = str(getattr(result, "task_id", "") or "")
        fetch = getattr(client, "fetch_vyralx_task", None)
        if status != "pending" or not task_id or fetch is None:
            return result
        from friday.core.task_envelope import TaskResult, TaskStatus

        deadline = time.monotonic() + _VYRALX_SETTLE_BUDGET_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(_VYRALX_SETTLE_POLL_SECONDS)
            task_data = await fetch(task_id)
            if not isinstance(task_data, dict):
                continue
            task_status = str(task_data.get("status") or "").strip().lower()
            if task_status == "completed":
                settled = task_data.get("result")
                return TaskResult(
                    task_id=task_id,
                    target_agent="vyralx",
                    status=TaskStatus.SUCCESS,
                    result=settled if isinstance(settled, dict) else {},
                    summary="VyralX completed the task.",
                    execution_time_ms=getattr(result, "execution_time_ms", 0),
                )
            if task_status == "failed":
                return TaskResult(
                    task_id=task_id,
                    target_agent="vyralx",
                    status=TaskStatus.ERROR,
                    error=str(task_data.get("error") or "VyralX reported the task failed."),
                    execution_time_ms=getattr(result, "execution_time_ms", 0),
                )
        return result

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

        # TaskResult.status may arrive as the enum repr ("TaskStatus.SUCCESS"),
        # a plain name ("SUCCESS") or lowercase — normalize to the bare token.
        status = str(getattr(result, "status", "") or "").rsplit(".", 1)[-1].strip().lower()
        task_id = str(getattr(result, "task_id", "") or "")
        execution_time_ms = getattr(result, "execution_time_ms", 0)
        receipt = f"[Task receipt: {task_id}]" if task_id else ""

        if status == "pending":
            # Accepted and still running is neither a success nor a failure;
            # say exactly that (TASK-VYR-002 — VyralX dispatches that outlast
            # the settle window land here, as do other agents' 202 accepts).
            if task_id:
                record_chat_dispatch(task_id, canonical, task, status, None, "still in progress")
            content = (
                f"{display} accepted that assignment and is still working on it — "
                f"it has not finished, so there is no result to show yet. {receipt} "
                "Ask me to check on it shortly."
            ).strip()
            return ToolResult(
                name=self.name,
                content=content,
                is_error=True,
                safety_level=self.safety_level,
                metadata={"status": status, "agent": canonical, "task_id": task_id},
            )

        if status not in {"success", "completed"}:
            error = getattr(result, "error", None) or f"status {status or 'unknown'}"
            if task_id:
                record_chat_dispatch(task_id, canonical, task, status, None, error)
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
        if task_id:
            record_chat_dispatch(task_id, canonical, task, status, data)
        body = _format_vyralx_result(task, data) if canonical == "vyralx" else None
        if body is None:
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
