"""Tools for TASK-IG-FRD-002 persistent follow-up tracking.

``followup_add`` captures a follow-up the owner delegates ("remind me to
chase X", "follow up on Y") into the persistent registry (mirrored to
Memora episodically); ``followup_list`` reads open/due follow-ups back;
``followup_complete`` closes one — explicitly, never automatically.
Engine: ``friday.proactive.followup_registry``.
"""

from __future__ import annotations

import time
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


def _registry():
    from friday.proactive.followup_registry import default_registry

    return default_registry()


class FollowUpAddTool(BaseTool):
    """Record a follow-up FRIDAY must not drop."""

    name = "followup_add"
    description = (
        "Record a persistent follow-up (something to chase or check later) so it "
        "survives restarts and surfaces when due. Use when the owner delegates "
        "anything with a future check-back: 'follow up on…', 'chase…', 'remind me to…'."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short title of the follow-up."},
            "detail": {"type": "string", "description": "Optional context."},
            "due_in_hours": {
                "type": "number",
                "description": "Optional: hours from now when it comes due.",
            },
        },
        "required": ["title"],
    }

    def execute(
        self,
        title: str = "",
        detail: str = "",
        due_in_hours: float | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            due_at = None
            if due_in_hours is not None:
                due_at = time.time() + float(due_in_hours) * 3600.0
            record = _registry().add(
                title or "", detail or "", due_at=due_at, source="tool:followup_add"
            )
        except ValueError as exc:
            return ToolResult(name=self.name, content=f"Could not record the follow-up: {exc}", is_error=True)
        mirror = (record.get("memora_mirror") or {}).get("status", "unknown")
        return ToolResult(
            name=self.name,
            content=(
                f"Follow-up recorded (id {record['id']}): {record['title']}. "
                f"Memora mirror: {mirror}. It will surface when due and stays "
                "open until you close it."
            ),
            metadata={"followup_id": record["id"], "memora_mirror": mirror},
        )


class FollowUpListTool(BaseTool):
    """List open follow-ups, or only the ones that are due."""

    name = "followup_list"
    description = (
        "List the owner's open follow-ups. With due_only=true, only the ones "
        "that are due or overdue right now — what FRIDAY should be chasing."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "due_only": {"type": "boolean", "description": "Only due/overdue items."},
        },
        "required": [],
    }

    def execute(self, due_only: bool = False, **kwargs: Any) -> ToolResult:
        from friday.proactive.followup_registry import format_followup

        registry = _registry()
        items = registry.due_followups() if due_only else registry.list(status="open")
        if not items:
            return ToolResult(
                name=self.name,
                content="No follow-ups are due right now." if due_only else "No open follow-ups.",
            )
        lines = [format_followup(i) for i in items]
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"count": len(items), "ids": [i["id"] for i in items]},
        )


class FollowUpCompleteTool(BaseTool):
    """Close a follow-up — the only way one leaves the open list."""

    name = "followup_complete"
    description = (
        "Mark a follow-up done (or dropped, with dropped=true) by its id. "
        "Follow-ups never close automatically; this is the explicit close."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "followup_id": {"type": "string", "description": "The follow-up id (from followup_list)."},
            "dropped": {"type": "boolean", "description": "True to drop instead of complete."},
            "note": {"type": "string", "description": "Optional closing note."},
        },
        "required": ["followup_id"],
    }

    def execute(
        self,
        followup_id: str = "",
        dropped: bool = False,
        note: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        registry = _registry()
        try:
            record = (
                registry.drop(followup_id or "", note or "")
                if dropped
                else registry.complete(followup_id or "", note or "")
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(name=self.name, content=f"Could not close the follow-up: {exc}", is_error=True)
        return ToolResult(
            name=self.name,
            content=f"Follow-up {record['id']} marked {record['status']}: {record['title']}",
            metadata={"followup_id": record["id"], "status": record["status"]},
        )


__all__ = ["FollowUpAddTool", "FollowUpListTool", "FollowUpCompleteTool"]
