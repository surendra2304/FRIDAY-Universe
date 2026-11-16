"""Brain tools for the agentic inbox (TASK-IG2-FRD-01).

Thin BaseTool wrappers over ``friday.proactive.agentic_inbox``:

- ``triage_inbox`` (SAFE): fetch → classify → summarise the owner's
  Gmail and render the triage report. Read-only; creates no drafts on
  its own (drafting needs the brain's LLM, wired by the caller).
- ``inbox_drafts`` (SENSITIVE): list / approve-and-send / reject queued
  reply drafts. Approving is the ONLY path that sends mail, and it is
  an explicit owner action — the agentic-inbox pattern's core rule.
"""

from __future__ import annotations

from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = get_logger("tools.agentic_inbox")


class TriageInboxTool(BaseTool):
    """Classify and summarise the owner's inbox (agentic-inbox pattern)."""

    name = "triage_inbox"
    description = (
        "Triage the owner's Gmail inbox the agentic-inbox way: fetch recent mail, "
        "classify each message (security / finance / action_required / meeting / "
        "newsletter / personal / other) with a priority score and the signals that "
        "produced it, and summarise. Read-only — sends nothing and drafts nothing."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "max_emails": {
                "type": "integer",
                "default": 20,
                "description": "Maximum number of recent emails to triage (default 20, max 50).",
            },
            "only_unread": {
                "type": "boolean",
                "default": False,
                "description": "Triage only unread mail.",
            },
        },
    }

    def execute(self, max_emails: int = 20, only_unread: bool = False, **kwargs: Any) -> ToolResult:
        from friday.proactive.agentic_inbox import triage_inbox

        report = triage_inbox(limit=max_emails, only_unread=only_unread)
        if report.status != "ok":
            return ToolResult(
                name=self.name,
                content=f"No mail was read: {report.status}",
                is_error=True,
                safety_level=self.safety_level,
                metadata={"read": False, "status": report.status},
            )
        return ToolResult(
            name=self.name,
            content=report.render(),
            is_error=False,
            safety_level=self.safety_level,
            metadata={"email_count": len(report.items), "counts": report.counts()},
        )


class InboxDraftsTool(BaseTool):
    """List, approve-and-send, or reject queued inbox reply drafts."""

    name = "inbox_drafts"
    description = (
        "Manage agentic-inbox reply drafts. action=list shows pending drafts; "
        "action=approve sends exactly that one draft (the only way inbox mail "
        "is ever sent — human approval before send); action=reject discards it."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "approve", "reject"],
                "description": "list | approve | reject",
            },
            "draft_id": {
                "type": "string",
                "description": "Draft id (required for approve/reject).",
            },
        },
        "required": ["action"],
    }

    def execute(self, action: str, draft_id: str | None = None, **kwargs: Any) -> ToolResult:
        from friday.proactive.agentic_inbox import DraftQueue, _mailbox_login

        address, _ = _mailbox_login()
        if not address:
            return ToolResult(
                name=self.name,
                content="No mailbox is configured (FRIDAY_EMAIL_ADDRESS unset), so there is no draft queue.",
                is_error=True,
                safety_level=self.safety_level,
                metadata={"configured": False},
            )
        queue = DraftQueue(address)
        action = (action or "list").lower()
        if action == "list":
            pending = queue.list_drafts(status="pending")
            if not pending:
                return ToolResult(
                    name=self.name,
                    content="No pending inbox reply drafts.",
                    is_error=False,
                    safety_level=self.safety_level,
                    metadata={"pending": 0},
                )
            lines = [f"{len(pending)} pending draft(s):"]
            for draft in pending:
                lines.append(
                    f"• [{draft['id']}] To: {draft.get('to')} — {draft.get('subject')}\n"
                    f"  {str(draft.get('body') or '')[:200]}"
                )
            return ToolResult(
                name=self.name,
                content="\n".join(lines),
                is_error=False,
                safety_level=self.safety_level,
                metadata={"pending": len(pending)},
            )
        if not draft_id:
            return ToolResult(
                name=self.name,
                content=f"action={action} needs a draft_id.",
                is_error=True,
                safety_level=self.safety_level,
            )
        if action == "approve":
            result = queue.approve_and_send(draft_id)
            if result.get("sent"):
                return ToolResult(
                    name=self.name,
                    content=f"Draft {draft_id} approved and sent.",
                    is_error=False,
                    safety_level=self.safety_level,
                    metadata=result,
                )
            return ToolResult(
                name=self.name,
                content=f"Draft {draft_id} was NOT sent: {result.get('error')}",
                is_error=True,
                safety_level=self.safety_level,
                metadata=result,
            )
        if action == "reject":
            draft = queue.reject(draft_id)
            if draft is None:
                return ToolResult(
                    name=self.name,
                    content=f"Draft {draft_id} not found or not pending — nothing rejected.",
                    is_error=True,
                    safety_level=self.safety_level,
                )
            return ToolResult(
                name=self.name,
                content=f"Draft {draft_id} rejected; it will not be sent.",
                is_error=False,
                safety_level=self.safety_level,
                metadata={"draft_id": draft_id, "status": "rejected"},
            )
        return ToolResult(
            name=self.name,
            content=f"Unknown action '{action}' — use list, approve or reject.",
            is_error=True,
            safety_level=self.safety_level,
        )
