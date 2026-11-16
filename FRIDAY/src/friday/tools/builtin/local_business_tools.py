"""Tool for the IG F-30 / F-35 local-business patterns.

``local_business`` qualifies a prospect against the F-30 criteria and
builds the two prompts (website generation, appointment agent) from
``friday.workflows.local_business``. Generation only: the tool never
contacts a business, fetches a page, or deploys anything — the prompt
text is the deliverable, delivered to the owner.
"""
from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class LocalBusinessTool(BaseTool):
    name = "local_business"
    description = (
        "Local-business pattern tools (IG F-30/F-35). Actions: 'qualify' — "
        "judge a prospect (good reviews but poor/no website) against the "
        "F-30 criteria; 'site_prompt' — build a website-generation prompt "
        "whose requirements block is the F-30 prompt tail recovered "
        "verbatim; 'appointment_prompt' — generate an appointment-booking "
        "agent's system prompt from the business's own services text "
        "(the F-35 method). Generation only — nobody is contacted."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["qualify", "site_prompt", "appointment_prompt"],
                "description": "Which pattern step to run.",
            },
            "business_name": {"type": "string", "description": "The business's name."},
            "category": {"type": "string", "description": "Business category, e.g. 'restaurant' or 'dentist'."},
            "location": {"type": "string", "description": "Business location (optional)."},
            "rating": {"type": "number", "description": "Average review rating (qualify)."},
            "reviews": {"type": "integer", "description": "Review count (qualify)."},
            "website_state": {
                "type": "string",
                "enum": ["none", "poor", "good", "unknown"],
                "description": "State of the business's current website (qualify).",
            },
            "services_text": {
                "type": "string",
                "description": "The business's services text, copied from its own website (appointment_prompt; also used in site_prompt's brief).",
            },
        },
        "required": ["action", "business_name"],
    }

    def execute(self, action: str = "", business_name: str = "", category: str = "",
                location: str = "", rating: float | None = None, reviews: int | None = None,
                website_state: str = "unknown", services_text: str = "",
                **kwargs: Any) -> ToolResult:
        from friday.workflows.local_business import (
            LocalBusinessError,
            Prospect,
            build_appointment_agent_prompt,
            build_site_generation_prompt,
            qualify_prospect,
        )

        act = (action or "").strip().lower()
        try:
            if act == "qualify":
                q = qualify_prospect(Prospect(
                    name=business_name, category=category,
                    rating=rating, reviews=reviews, website_state=website_state or "unknown",
                ))
                return ToolResult(
                    name=self.name,
                    content=(f"{q.name}: {q.verdict} (score {q.score}/100)\n"
                             + "\n".join(f"- {r}" for r in q.reasons)),
                    metadata={"verdict": q.verdict, "score": q.score},
                )
            if act == "site_prompt":
                prompt = build_site_generation_prompt(
                    business_name, category=category,
                    services_text=services_text, location=location,
                )
                return ToolResult(name=self.name, content=prompt,
                                  metadata={"kind": "site_generation_prompt"})
            if act == "appointment_prompt":
                prompt = build_appointment_agent_prompt(
                    business_name, services_text, niche=category,
                )
                return ToolResult(name=self.name, content=prompt,
                                  metadata={"kind": "appointment_agent_prompt"})
        except LocalBusinessError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True, refused=True)
        except Exception as exc:  # reported honestly, never dressed up
            return ToolResult(name=self.name,
                              content=f"local_business failed: {exc}", is_error=True)
        return ToolResult(
            name=self.name,
            content="local_business needs action = qualify | site_prompt | appointment_prompt.",
            is_error=True, refused=True,
        )
