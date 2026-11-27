"""Tools for TASK-FRD-062 — the FRIDAY CRM workspace surface.

Contacts and deals live in FRIDAY's Oracle schema (``friday.crm.store``);
follow-ups stay in the existing file-backed registry and link to CRM
records by id. Every tool here is ``SafetyLevel.SAFE`` on purpose: the
Gemini Live voice session only offers SAFE tools, and the board
acceptance requires the whole surface to be operable by voice. The
fail-closed rules (unknown reference, ambiguous name, invalid stage)
live in the store; the tools translate them into spoken errors.

No outreach: these tools never email, message or call anyone — contacts
are owner-managed records only.
"""

from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.crm.store import DEAL_STAGES
from friday.tools.base import BaseTool


def _store():
    from friday.crm.store import default_store

    return default_store()


def _registry():
    from friday.proactive.followup_registry import default_registry

    return default_registry()


def _contact_card(contact: dict[str, Any], deals: list[dict[str, Any]] | None = None) -> str:
    """One speakable contact card."""
    bits = [contact["name"]]
    if contact.get("company"):
        bits.append(f"at {contact['company']}")
    if contact.get("email"):
        bits.append(f"email {contact['email']}")
    if contact.get("phone"):
        bits.append(f"phone {contact['phone']}")
    if contact.get("unreachable"):
        bits.append("(no email or phone on file — unreachable)")
    line = ", ".join(bits) + f" (id {contact['id']})"
    if deals:
        deal_bits = ", ".join(f"{d['title']} [{d['stage']}]" for d in deals)
        line += f". Deals: {deal_bits}"
    return line


class CrmContactAddTool(BaseTool):
    """Add a contact to FRIDAY's CRM."""

    name = "crm_contact_add"
    description = (
        "Add a contact to FRIDAY's CRM (the owner's own contacts, e.g. a "
        "CometWorks client). Use when the owner says 'add a contact' or "
        "gives a name to remember with an email or phone. The contact is "
        "stored in FRIDAY's database and can be used for deals and "
        "follow-ups. Never emails or messages the contact."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Contact's full name."},
            "email": {"type": "string", "description": "Email address, if known."},
            "phone": {"type": "string", "description": "Phone number, if known."},
            "company": {"type": "string", "description": "Company or organisation."},
            "source": {
                "type": "string",
                "description": "How the contact arrived: 'voice', 'chat' or 'lead-import'.",
            },
        },
        "required": ["name"],
    }

    def execute(
        self,
        name: str = "",
        email: str = "",
        phone: str = "",
        company: str = "",
        source: str = "chat",
        **kwargs: Any,
    ) -> ToolResult:
        try:
            contact = _store().add_contact(
                name,
                email=email or None,
                phone=phone or None,
                company=company or None,
                source=source or "chat",
            )
        except ValueError as exc:
            return ToolResult(name=self.name, content=f"Could not add the contact: {exc}", is_error=True)
        return ToolResult(
            name=self.name,
            content=f"Contact added: {_contact_card(contact)}",
            metadata={"contact_id": contact["id"]},
        )


class CrmContactGetTool(BaseTool):
    """Read one contact back, with its deals."""

    name = "crm_contact_get"
    description = (
        "Look up one CRM contact by id or by name (a name fragment works "
        "when it matches exactly one contact). Returns the contact card "
        "with its deals. If the name matches nobody — or more than one "
        "person — it says so instead of guessing."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "contact_ref": {
                "type": "string",
                "description": "Contact id, full name, or a name fragment.",
            },
        },
        "required": ["contact_ref"],
    }

    def execute(self, contact_ref: str = "", **kwargs: Any) -> ToolResult:
        store = _store()
        try:
            contact = store.resolve_contact(contact_ref)
        except (KeyError, ValueError) as exc:
            return ToolResult(name=self.name, content=f"Could not find the contact: {exc}", is_error=True)
        deals = store.list_deals(contact_id=contact["id"])
        return ToolResult(
            name=self.name,
            content=_contact_card(contact, deals),
            metadata={"contact_id": contact["id"], "deal_count": len(deals)},
        )


class CrmContactListTool(BaseTool):
    """List contacts by name fragment or company."""

    name = "crm_contact_list"
    description = (
        "List CRM contacts, optionally filtered by a name fragment or a "
        "company. Use to answer 'who do I have at Acme?' or 'show my "
        "contacts'."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Name fragment to match."},
            "company": {"type": "string", "description": "Company to filter by."},
        },
        "required": [],
    }

    def execute(
        self, query: str = "", company: str = "", **kwargs: Any
    ) -> ToolResult:
        contacts = _store().find_contacts(query or "", company=company or None)
        if not contacts:
            return ToolResult(name=self.name, content="No contacts match.")
        lines = [_contact_card(c) for c in contacts]
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"count": len(contacts), "ids": [c["id"] for c in contacts]},
        )


class CrmDealAddTool(BaseTool):
    """Open a deal for a contact."""

    name = "crm_deal_add"
    description = (
        "Open a deal (opportunity) for a CRM contact: give the contact by "
        "id or name and a deal title. The deal starts at stage 'lead' "
        "unless another valid stage is given. Valid stages: "
        + ", ".join(DEAL_STAGES)
        + "."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "contact_ref": {
                "type": "string",
                "description": "Contact id, full name, or a name fragment.",
            },
            "title": {"type": "string", "description": "Deal title, e.g. 'Website copy package'."},
            "stage": {"type": "string", "description": "Starting stage; default 'lead'."},
            "value_text": {
                "type": "string",
                "description": "Free-text value, e.g. '$500' — no currency math is done.",
            },
        },
        "required": ["contact_ref", "title"],
    }

    def execute(
        self,
        contact_ref: str = "",
        title: str = "",
        stage: str = "lead",
        value_text: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        store = _store()
        try:
            contact = store.resolve_contact(contact_ref)
            deal = store.add_deal(
                contact["id"], title, stage=stage or "lead", value_text=value_text or None
            )
        except (KeyError, ValueError) as exc:
            return ToolResult(name=self.name, content=f"Could not open the deal: {exc}", is_error=True)
        return ToolResult(
            name=self.name,
            content=(
                f"Deal opened for {contact['name']}: {deal['title']} "
                f"[stage {deal['stage']}] (id {deal['id']})"
            ),
            metadata={"deal_id": deal["id"], "contact_id": contact["id"], "stage": deal["stage"]},
        )


class CrmDealStageTool(BaseTool):
    """Move a deal to a new pipeline stage."""

    name = "crm_deal_stage"
    description = (
        "Move a CRM deal to a new stage. Give the deal by id or title and "
        "the new stage. Valid stages: " + ", ".join(DEAL_STAGES) + ". "
        "Confirms the old stage and the new stage; an invalid stage or an "
        "unknown deal is rejected, never guessed."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "deal_ref": {
                "type": "string",
                "description": "Deal id, full title, or a title fragment.",
            },
            "new_stage": {"type": "string", "description": "The stage to move to."},
        },
        "required": ["deal_ref", "new_stage"],
    }

    def execute(
        self, deal_ref: str = "", new_stage: str = "", **kwargs: Any
    ) -> ToolResult:
        store = _store()
        try:
            deal = store.resolve_deal(deal_ref)
            moved = store.set_deal_stage(deal["id"], new_stage)
        except (KeyError, ValueError) as exc:
            return ToolResult(name=self.name, content=f"Could not move the deal: {exc}", is_error=True)
        if moved.get("stage_unchanged"):
            return ToolResult(
                name=self.name,
                content=f"Deal {moved['title']} is already at stage {moved['stage']}.",
                metadata={"deal_id": moved["id"], "stage": moved["stage"]},
            )
        return ToolResult(
            name=self.name,
            content=(
                f"Deal {moved['title']} moved from {moved['previous_stage']} "
                f"to {moved['stage']}."
            ),
            metadata={
                "deal_id": moved["id"],
                "previous_stage": moved["previous_stage"],
                "stage": moved["stage"],
            },
        )


class CrmFollowupsDueTool(BaseTool):
    """Read back due CRM follow-ups (today / one contact)."""

    name = "crm_followups_due"
    description = (
        "Read back the follow-ups that are due — today by default, or for "
        "one contact when contact_ref is given. Each line names the linked "
        "contact and deal when there is one. With all_open=true, lists "
        "every open follow-up instead of only the due ones."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "contact_ref": {
                "type": "string",
                "description": "Optional: contact id or name to restrict to.",
            },
            "all_open": {
                "type": "boolean",
                "description": "True to list all open follow-ups, not only due ones.",
            },
        },
        "required": [],
    }

    def execute(
        self, contact_ref: str = "", all_open: bool = False, **kwargs: Any
    ) -> ToolResult:
        from friday.proactive.followup_registry import format_followup

        store = _store()
        registry = _registry()
        contact_id = None
        contact_name = None
        if (contact_ref or "").strip():
            try:
                contact = store.resolve_contact(contact_ref)
            except (KeyError, ValueError) as exc:
                return ToolResult(
                    name=self.name,
                    content=f"Could not find the contact: {exc}",
                    is_error=True,
                )
            contact_id = contact["id"]
            contact_name = contact["name"]
        if all_open:
            items = registry.list(status="open", contact_id=contact_id)
        else:
            items = registry.due_followups(contact_id=contact_id)
        if not items:
            scope = f" for {contact_name}" if contact_name else ""
            return ToolResult(
                name=self.name,
                content=f"No follow-ups are due{scope}."
                if not all_open
                else f"No open follow-ups{scope}.",
            )
        lines = []
        for item in items:
            line = format_followup(item)
            link = self._link_text(item, store)
            if link:
                line += f" — {link}"
            lines.append(line)
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"count": len(items), "ids": [i["id"] for i in items]},
        )

    @staticmethod
    def _link_text(item: dict[str, Any], store: Any) -> str:
        """Human link for a registry record: 'for <contact>' / 'deal: <title>'."""
        parts = []
        contact_id = item.get("contact_id")
        if contact_id:
            try:
                contact = store.get_contact(contact_id)
            except Exception:
                contact = None
            if contact:
                parts.append(f"for {contact['name']}")
        deal_id = item.get("deal_id")
        if deal_id:
            try:
                deal = store.get_deal(deal_id)
            except Exception:
                deal = None
            if deal:
                parts.append(f"deal: {deal['title']}")
        return "; ".join(parts)


__all__ = [
    "CrmContactAddTool",
    "CrmContactGetTool",
    "CrmContactListTool",
    "CrmDealAddTool",
    "CrmDealStageTool",
    "CrmFollowupsDueTool",
]
