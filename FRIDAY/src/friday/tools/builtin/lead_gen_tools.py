"""Tool for TASK-IG2-FRD-03 — delegated lead-generation errand.

``lead_generate`` runs the errand end-to-end and delivers the structured
contact table to the owner. It never contacts anyone: the engine
(``friday.autonomous.lead_generation``) has no outreach surface at all.

TASK-FRD-061 adds the verification pass: every lead carries a
verified/stale/unverifiable status with the check date, and stale leads
are dropped from the final outreach list (flagged in the report, never
silently lost). Unverifiable leads stay, flagged, for the owner to
decide. With ``verify=False`` the tool behaves exactly as before.
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
        "structured contacts, dedupe them, verify each lead's phone/email "
        "against its current public listing, and deliver a verified contact "
        "table (name/phone/email/website/status/checked) to the owner. Stale "
        "leads are dropped from the final outreach list. The table is the "
        "deliverable — nobody is emailed, called or messaged."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "directory_url": {"type": "string", "description": "Public directory listing URL (http/https, ports 80/443)."},
            "category": {"type": "string", "description": "Category label for the table, e.g. 'insurance'."},
            "max_pages": {"type": "integer", "description": "Pagination cap (default 5, hard max 5)."},
            "verify": {"type": "boolean", "description": "Verify each lead's contacts before finalising (default true)."},
            "drop_stale": {"type": "boolean", "description": "Drop stale leads from the final outreach list (default true; false keeps them flagged)."},
        },
        "required": ["directory_url"],
    }

    def execute(self, directory_url: str = "", category: str = "",
                max_pages: int = 5, verify: bool = True, drop_stale: bool = True,
                **kwargs: Any) -> ToolResult:
        from friday.autonomous.lead_generation import LeadGenError, run_lead_generation
        from friday.autonomous.lead_verification import (
            finalize_outreach_list,
            render_verification_table,
        )

        if not (directory_url or "").strip():
            return ToolResult(name=self.name, content="lead_generate needs a directory_url.",
                              is_error=True, refused=True)
        try:
            result = run_lead_generation(directory_url.strip(), category or "",
                                         max_pages=int(max_pages or 5),
                                         verify=bool(verify))
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
        if not verify:
            table = result.table("markdown")
            return ToolResult(
                name=self.name,
                content=(f"{len(result.leads)} leads from {result.pages_fetched} page(s) "
                         f"for category '{category or 'general'}' (no outreach performed, "
                         f"verification skipped):\n\n{table}"),
                metadata={"count": len(result.leads),
                          "pages_fetched": result.pages_fetched,
                          "csv": result.table("csv")})
        final = finalize_outreach_list(result.leads, drop_stale=bool(drop_stale))
        counts = final["counts"]
        table = render_verification_table(final["final"], "markdown")
        lines = [
            f"{final['total']} leads from {result.pages_fetched} page(s) for category "
            f"'{category or 'general'}', verified {counts.get('verified', 0)} verified / "
            f"{counts.get('stale', 0)} stale / {counts.get('unverifiable', 0)} unverifiable "
            f"(no outreach performed).",
            f"Final outreach list: {len(final['final'])} leads"
            + (" (stale dropped)" if drop_stale else " (stale kept, flagged)") + ".",
        ]
        if final["dropped"]:
            dropped_names = ", ".join(lead.name for lead in final["dropped"])
            lines.append(f"Dropped as stale: {dropped_names}.")
        lines.append("")
        lines.append(table)
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"count": len(final["final"]),
                      "total": final["total"],
                      "counts": counts,
                      "pages_fetched": result.pages_fetched,
                      "dropped": [lead.name for lead in final["dropped"]],
                      "csv": render_verification_table(final["final"], "csv")})


__all__ = ["LeadGenerateTool"]
