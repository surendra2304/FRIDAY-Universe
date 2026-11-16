"""Tool for TASK-IG2-FRD-03 — delegated lead-generation errand.

``lead_generate`` runs the errand end-to-end and delivers the structured
contact table to the owner. It never contacts anyone: the engine
(``friday.autonomous.lead_generation``) has no outreach surface at all.
"""
from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class LeadGenerateTool(BaseTool):
    name = "lead_generate"
    description = (
        "Run a delegated lead-generation errand: fetch a business-directory "
        "category listing (e.g. a Yello-style directory page), extract "
        "structured contacts, dedupe them, and deliver a contact table "
        "(name/phone/email/website/category) to the owner. The table is "
        "the deliverable — nobody is emailed, called or messaged."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "directory_url": {"type": "string", "description": "Public directory listing URL (http/https, ports 80/443)."},
            "category": {"type": "string", "description": "Category label for the table, e.g. 'insurance'."},
            "max_pages": {"type": "integer", "description": "Pagination cap (default 5, hard max 5)."},
        },
        "required": ["directory_url"],
    }

    def execute(self, directory_url: str = "", category: str = "",
                max_pages: int = 5, **kwargs: Any) -> ToolResult:
        from friday.autonomous.lead_generation import LeadGenError, run_lead_generation

        if not (directory_url or "").strip():
            return ToolResult(name=self.name, content="lead_generate needs a directory_url.",
                              is_error=True, refused=True)
        try:
            result = run_lead_generation(directory_url.strip(), category or "",
                                         max_pages=int(max_pages or 5))
        except LeadGenError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True, refused=True)
        except Exception as exc:  # fetch/parse failure is reported honestly
            return ToolResult(name=self.name,
                              content=f"Lead generation failed: {exc}", is_error=True)
        if not result.leads:
            return ToolResult(
                name=self.name,
                content=(f"No leads extracted from {directory_url} "
                         f"({result.pages_fetched} page(s) fetched). The directory's "
                         "markup may not expose listing blocks."),
                metadata={"pages_fetched": result.pages_fetched, "count": 0})
        table = result.table("markdown")
        return ToolResult(
            name=self.name,
            content=(f"{len(result.leads)} leads from {result.pages_fetched} page(s) "
                     f"for category '{category or 'general'}' (no outreach performed):\n\n{table}"),
            metadata={"count": len(result.leads),
                      "pages_fetched": result.pages_fetched,
                      "csv": result.table("csv")})


__all__ = ["LeadGenerateTool"]
