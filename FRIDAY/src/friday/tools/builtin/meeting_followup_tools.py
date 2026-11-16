"""Tools for TASK-IG2-FRD-04 — post-meeting follow-up automation.

* ``meeting_followup_create`` (SENSITIVE) — build summary + action items
  + follow-up draft from meeting notes/transcript; action items are also
  registered in FRIDAY's existing follow-up registry. The draft lands
  PENDING — nothing is sent.
* ``meeting_followup_list`` (SAFE) — list drafts and their gate status.
* ``meeting_followup_decide`` (SENSITIVE) — the owner's gate: approve
  (releases the draft text for the owner to send himself) or reject.
Engine: ``friday.workflows.meeting_followup``.
"""
from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


def _store():
    from friday.workflows.meeting_followup import default_store
    return default_store()


class MeetingFollowUpCreateTool(BaseTool):
    name = "meeting_followup_create"
    description = (
        "After a meeting, build its follow-up from the notes/transcript: an "
        "extractive summary, structured action items (also registered as "
        "persistent follow-ups), and a follow-up draft. The draft is "
        "PENDING owner approval — nothing is auto-sent, ever."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "meeting_title": {"type": "string", "description": "Meeting title (as on the calendar)."},
            "notes": {"type": "string", "description": "Meeting notes or transcript text."},
            "attendees": {"type": "array", "items": {"type": "string"},
                          "description": "Optional attendee names."},
            "register_actions": {"type": "boolean",
                                 "description": "Also add action items to the follow-up registry (default true)."},
        },
        "required": ["meeting_title", "notes"],
    }

    def execute(self, meeting_title: str = "", notes: str = "",
                attendees: Any = None, register_actions: bool = True,
                **kwargs: Any) -> ToolResult:
        from friday.workflows.meeting_followup import build_followup, register_action_items

        if not (notes or "").strip():
            return ToolResult(name=self.name, content="meeting_followup_create needs the meeting notes/transcript.",
                              is_error=True, refused=True)
        followup = build_followup(meeting_title or "Meeting", notes,
                                  attendees=list(attendees) if attendees else None)
        draft_id = _store().add(followup)
        registered = ""
        if register_actions and followup.action_items:
            try:
                ids = register_action_items(followup)
                registered = f" Action items registered as follow-ups: {', '.join(ids)}."
            except Exception as exc:  # registry unavailable — draft still stands
                registered = f" (follow-up registry unavailable: {exc})"
        return ToolResult(
            name=self.name,
            content=(f"Draft {draft_id} created for '{followup.meeting_title}' "
                     f"({len(followup.action_items)} action item(s)). Status: PENDING — "
                     f"nothing has been sent.{registered}\n\n{followup.draft_text}"),
            metadata={"draft_id": draft_id, "status": followup.status,
                      "action_items": len(followup.action_items)})


class MeetingFollowUpListTool(BaseTool):
    name = "meeting_followup_list"
    description = "List post-meeting follow-up drafts and their approval status."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {"status": {"type": "string", "description": "Optional filter: PENDING/APPROVED/REJECTED."}},
        "required": [],
    }

    def execute(self, status: str = "", **kwargs: Any) -> ToolResult:
        items = _store().list(status=(status or "").upper())
        if not items:
            return ToolResult(name=self.name, content="No meeting follow-up drafts.")
        lines = [f"{draft_id}: [{f.status}] {f.meeting_title} — "
                 f"{len(f.action_items)} action item(s), {f.created_at}"
                 for draft_id, f in items]
        return ToolResult(name=self.name, content="\n".join(lines),
                          metadata={"count": len(items)})


class MeetingFollowUpDecideTool(BaseTool):
    name = "meeting_followup_decide"
    description = (
        "The owner's decision on a meeting follow-up draft: 'approve' "
        "releases the draft text (for the owner to send himself — FRIDAY "
        "does not send it) or 'reject' discards it."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "draft_id": {"type": "string"},
            "decision": {"type": "string", "enum": ["approve", "reject"]},
        },
        "required": ["draft_id", "decision"],
    }

    def execute(self, draft_id: str = "", decision: str = "approve", **kwargs: Any) -> ToolResult:
        store = _store()
        try:
            followup = (store.reject(draft_id) if decision == "reject"
                        else store.approve(draft_id))
        except (KeyError, ValueError) as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        if followup.status == "REJECTED":
            return ToolResult(name=self.name, content=f"Draft {draft_id} rejected and discarded.")
        return ToolResult(
            name=self.name,
            content=(f"Draft {draft_id} approved. Here is the text for you to send "
                     f"(FRIDAY has not sent it):\n\n{store.approved_text(draft_id)}"),
            metadata={"draft_id": draft_id, "status": "APPROVED"})


__all__ = ["MeetingFollowUpCreateTool", "MeetingFollowUpDecideTool",
           "MeetingFollowUpListTool"]
