"""TASK-ORCH-008 (checklist C13): real task-record lookups through FRIDAY chat.

C14 gave every delegation a receipt the owner can reference
("[Task receipt: task_71f66986709e]"). C13 closes the loop: when the owner
asks "what happened to that IntelX task?", "status of task_71f66986709e?",
or "did the Stratex assignment finish?", FRIDAY answers from the REAL
unified TaskRecordStore — the same store the router and dispatch bus write
into (TASK-ORCH-002) — never from memory or invention.

Truthfulness rules:
- every reported status/description/result/error comes from the store only;
- an unknown task id or agent is answered honestly with what IS known
  (the report counts), never fabricated into a plausible-sounding answer;
- an empty store is stated plainly ("I have no task records yet") with the
  pointer to how records are created (fleet_dispatch receipts);
- timestamps are rendered in IST (Asia/Kolkata), the project clock (D-026).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Task ids look like task_<hex> (router) or disp_<hex> (dispatch bus).
_TASK_ID_RE = re.compile(r"\b(?:task|disp)_[0-9a-f]{6,}\b", re.IGNORECASE)

_IST = timezone(timedelta(hours=5, minutes=30))


def _fmt_ts(ts: float | None) -> str:
    """Render a unix timestamp as a human IST string ('—' when absent)."""
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts, tz=_IST).strftime("%d %b %Y, %I:%M:%S %p IST")
    except (ValueError, OverflowError, OSError):
        return "—"


def _fmt_result(result: Any) -> str:
    """Compact one-line rendering of a record's result payload."""
    if result is None:
        return "—"
    if isinstance(result, dict):
        for key in ("result", "response", "summary", "message", "output", "text_response"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                return text if len(text) <= 220 else text[:217] + "…"
        try:
            import json

            text = json.dumps(result, default=str, ensure_ascii=False)
        except Exception:
            text = str(result)
    else:
        text = str(result)
    return text if len(text) <= 220 else text[:217] + "…"


def _render_record(record: Any, include_history: bool = True) -> str:
    """Render one TaskRecord as the owner-facing status block."""
    lines = [
        f"📋 {record.task_id} — {record.owner_agent or 'unassigned'} — {record.status.upper()}",
    ]
    if record.description:
        desc = record.description.strip()
        lines.append(f"   Task: {desc if len(desc) <= 200 else desc[:197] + '…'}")
    if record.status == "completed":
        lines.append(f"   Result: {_fmt_result(record.result)}")
    if record.error:
        err = record.error.strip()
        lines.append(f"   Error: {err if len(err) <= 200 else err[:197] + '…'}")
    if record.rationale:
        lines.append(f"   Routing: {record.rationale.strip()[:160]}")
    lines.append(
        f"   Created {_fmt_ts(record.created_at)} · Updated {_fmt_ts(record.updated_at)}"
    )
    if include_history:
        trail = " → ".join(to for _, _, to in record.history)
        lines.append(f"   Trail: {trail}")
    return "\n".join(lines)


class TaskStatusQueryTool(BaseTool):
    """Answer 'what happened to that task?' from the real task records."""

    name = "task_status"
    description = (
        "Look up the REAL status of a task the owner delegated to a fleet agent — "
        "by task-id receipt (e.g. task_71f66986709e) or by agent name ('the IntelX "
        "task', 'my Stratex assignment'). Reports the task's real lifecycle "
        "status, result or error, and timing from the unified task records that "
        "the router and dispatch bus write to. Use this whenever the owner asks "
        "what happened to a task, whether a dispatch finished, or for the status "
        "of any receipt like [Task receipt: task_xxx] — never answer from memory "
        "or guess."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 10.0
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The owner's question, phrased as they asked it "
                "(may contain a task_xxx/disp_xxx receipt id and/or an agent name).",
            },
            "agent": {
                "type": "string",
                "description": "Optional agent name to filter by (IntelX, Stratex, "
                "Forge, Sentinel, Cortex, Futuris, VyralX, Memora, Inference).",
            },
            "limit": {
                "type": "integer",
                "description": "Max records to show for agent-scoped queries (default 3).",
            },
        },
        "required": ["query"],
    }

    def __init__(self, store: Any | None = None) -> None:
        super().__init__()
        self._store = store

    def _records(self) -> Any:
        """The live shared store by default; an injected store in tests."""
        if self._store is not None:
            return self._store
        from friday_core.task_records import get_shared_task_records

        return get_shared_task_records()

    # ------------------------------------------------------------------
    def execute(self, query: str = "", agent: str = "", limit: int = 3, **kwargs: Any) -> ToolResult:
        query = (query or kwargs.get("task_id") or "").strip()
        if not query:
            return ToolResult(
                name=self.name,
                content="Which task, Boss? Give me the receipt id (task_…) or tell me the agent — e.g. 'what happened to the IntelX task?'.",
                is_error=True,
                safety_level=self.safety_level,
            )

        try:
            store = self._records()
            records = self._lookup(store, query, agent)
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not read the task records ({type(exc).__name__}: {exc}). "
                    "That is the real outcome — I won't invent a status."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        if not records:
            return self._honest_empty(store, query, agent)

        blocks = [_render_record(r) for r in records[: max(1, int(limit or 3))]]
        body = "\n\n".join(blocks)
        if len(records) > max(1, int(limit or 3)):
            body += f"\n\n(+{len(records) - max(1, int(limit or 3))} more — ask me by receipt id for any specific one)"
        return ToolResult(
            name=self.name,
            content=f"Here's the real record from my task ledger, straight from the dispatch trail:\n\n{body}",
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "task_status_query": {
                    "matched": [r.task_id for r in records],
                    "count": len(records),
                },
            },
        )

    # ------------------------------------------------------------------
    def _lookup(self, store: Any, query: str, agent: str) -> list[Any]:
        """Match explicit receipt ids first, then the named agent's records."""
        ids = _TASK_ID_RE.findall(query)
        found: list[Any] = []
        seen: set[str] = set()
        for task_id in ids:
            record = store.get(task_id)
            if record is not None and record.task_id not in seen:
                seen.add(record.task_id)
                found.append(record)
        if found:
            return found

        # agent: explicit param, or an agent name mentioned in the query
        target = (agent or "").strip().lower()
        if not target:
            from friday.tools.builtin.fleet_dispatch import normalize_agent

            for token in re.findall(r"[a-z]+", query.lower()):
                target = normalize_agent(token) or ""
                if target:
                    break
        if not target:
            return []
        # Most recent records for the agent (the store lists in insertion order).
        return [r for r in store.list(agent=target) if r.owner_agent == target][::-1]

    # ------------------------------------------------------------------
    def _honest_empty(self, store: Any, query: str, agent: str) -> ToolResult:
        """Say what IS known when nothing matches — never fabricate a status."""
        try:
            report = store.report()
            total = int(report.get("total", 0))
            by_agent = report.get("by_agent", {}) or {}
            by_status = report.get("by_status", {}) or {}
        except Exception:
            total, by_agent, by_status = 0, {}, {}
        parts = ["I checked my real task ledger and found no matching record."]
        if total == 0:
            parts.append(
                "The ledger is empty right now — records are created when you assign "
                "work to an agent ('assign a quick task to IntelX …'), and every "
                "dispatch hands back a receipt like [Task receipt: task_xxx] you can ask me about."
            )
        else:
            active = sum(v for k, v in by_status.items() if k in {"submitted", "assigned", "dispatched"})
            done = by_status.get("completed", 0)
            failed = by_status.get("failed", 0) + by_status.get("routing_failed", 0)
            summary = f"I do have {total} task record(s): {done} completed, {active} still moving, {failed} failed."
            if by_agent:
                names = ", ".join(f"{a} ({c})" for a, c in sorted(by_agent.items()))
                summary += f" By agent: {names}."
            parts.append(summary)
            parts.append("Give me the exact receipt id (task_…/disp_…) and I'll pull that one up.")
        ids_in_query = _TASK_ID_RE.findall(query)
        if ids_in_query:
            parts.append(f"The id {ids_in_query[0]} isn't in the ledger — records live only for real dispatches since the service started.")
        return ToolResult(
            name=self.name,
            content=" ".join(parts),
            is_error=False,
            safety_level=self.safety_level,
            metadata={"task_status_query": {"matched": [], "count": 0, "known_total": total}},
        )
