"""Tools for TASK-IG-FRD-003 job-hunt workflow.

``job_hunt_scan`` fetches the career pages named in the owner's job
profile and ranks every extracted posting against it. ``job_hunt_shortlist``
reads the last scan back. ``job_hunt_prep`` builds the 30-day prep plan +
an outreach DRAFT for one shortlisted role and saves both as files.

Nothing here sends anything or applies anywhere — drafts only, the
owner reviews and acts personally (the module has no send path at all).
Engine: ``friday.workflows.job_hunt``.
"""

from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class JobHuntScanTool(BaseTool):
    """Scan the career pages in the owner's profile and rank the fits."""

    name = "job_hunt_scan"
    description = (
        "Run a job-hunt scan: fetch the company career pages listed in the "
        "owner's job profile, extract postings, score each against the "
        "profile, and return the ranked shortlist with matched/missing "
        "skills. Requires the profile (FRIDAY/.data/job_hunt/profile.json) "
        "to carry 'career_pages': [urls]."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional career-page URLs; defaults to the profile's career_pages.",
            },
        },
        "required": [],
    }

    def execute(self, urls: Any = None, **kwargs: Any) -> ToolResult:
        from friday.workflows import job_hunt

        profile = job_hunt.load_profile()
        if profile is None:
            return ToolResult(
                name=self.name,
                content=(
                    "No job profile found at FRIDAY/.data/job_hunt/profile.json — "
                    "the job hunt needs the owner's profile first (skills, target "
                    "titles, locations, career_pages). Nothing was scanned."
                ),
                is_error=True,
            )
        pages = list(urls or profile.get("career_pages") or [])
        if not pages:
            return ToolResult(
                name=self.name,
                content="The job profile lists no career_pages to scan. Add company career-page URLs to the profile first.",
                is_error=True,
            )
        scan = job_hunt.run_scan(profile, pages)
        lines = [
            f"Scanned {len(pages)} page(s): {scan['total_listings']} postings found, "
            f"{len(scan['shortlist'])} after fit scoring."
        ]
        for src in scan["sources"]:
            if src["status"] != "ok":
                lines.append(f"- source {src['url']}: {src['status']}" + (f" ({src['error']})" if src.get("error") else ""))
        for i, item in enumerate(scan["shortlist"][:10], 1):
            m = item["match"]
            flag = " [overlooked fit]" if m.get("overlooked") else ""
            lines.append(
                f"{i}. {item['title']} — {item['company']} ({item['location'] or 'location n/a'}) "
                f"score {m['score']}{flag}; matched: {', '.join(m['matched_skills']) or '—'}; "
                f"gaps: {', '.join(m['missing_skills']) or 'none'}"
            )
        return ToolResult(
            name=self.name,
            content="\n".join(lines),
            metadata={"total": scan["total_listings"], "shortlist": len(scan["shortlist"])},
        )


class JobHuntShortlistTool(BaseTool):
    """Read back the last scan's shortlist without re-fetching."""

    name = "job_hunt_shortlist"
    description = "Show the ranked shortlist from the most recent job_hunt_scan."
    safety_level = SafetyLevel.SAFE
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        from friday.workflows import job_hunt

        scan = job_hunt.load_last_scan()
        if not scan:
            return ToolResult(
                name=self.name,
                content="No job scan has run yet — run job_hunt_scan first.",
                is_error=True,
            )
        shortlist = scan.get("shortlist") or []
        if not shortlist:
            return ToolResult(name=self.name, content="The last scan produced an empty shortlist.")
        lines = []
        for i, item in enumerate(shortlist, 1):
            m = item["match"]
            lines.append(
                f"{i}. {item['title']} — {item['company']} · score {m['score']} · "
                f"{item['url']}"
            )
        return ToolResult(name=self.name, content="\n".join(lines))


class JobHuntPrepTool(BaseTool):
    """Prep plan + outreach draft for one shortlisted role (files only)."""

    name = "job_hunt_prep"
    description = (
        "Build the 30-day prep plan and an outreach DRAFT for the shortlist "
        "entry at the given rank (1-based). Both are saved as files under "
        "FRIDAY/.data/job_hunt/drafts/ for the owner to review. Nothing is "
        "sent and no application is submitted — ever — by this tool."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "rank": {"type": "integer", "description": "1-based rank in the last shortlist."},
        },
        "required": ["rank"],
    }

    def execute(self, rank: int = 1, **kwargs: Any) -> ToolResult:
        from friday.workflows import job_hunt

        profile = job_hunt.load_profile()
        scan = job_hunt.load_last_scan()
        if profile is None or not scan or not (scan.get("shortlist") or []):
            return ToolResult(
                name=self.name,
                content="Need a job profile and a completed scan with a non-empty shortlist first.",
                is_error=True,
            )
        shortlist = scan["shortlist"]
        if rank < 1 or rank > len(shortlist):
            return ToolResult(
                name=self.name,
                content=f"Rank {rank} is outside the shortlist (1..{len(shortlist)}).",
                is_error=True,
            )
        listing = shortlist[rank - 1]
        plan = job_hunt.build_prep_plan(profile, listing)
        draft = job_hunt.draft_outreach(profile, listing)
        plan_path = job_hunt.save_draft("prep", listing, plan)
        draft_path = job_hunt.save_draft("outreach", listing, draft)
        return ToolResult(
            name=self.name,
            content=(
                f"Prep plan saved: {plan_path}\nOutreach draft saved: {draft_path}\n\n"
                f"{plan}\n\n---\n{draft}"
            ),
            metadata={"plan_path": plan_path, "draft_path": draft_path},
        )


__all__ = ["JobHuntScanTool", "JobHuntShortlistTool", "JobHuntPrepTool"]
