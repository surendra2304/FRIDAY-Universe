"""OSINT tool routes: tracking, footprint audit, social links, investigations.

IG wiring (package item X-07): four shipped libraries had no API/service
consumer. These routes are their production consumers:

  * ``TrackingService`` (TASK-IG-005)      -> GET  /tracking/snapshot
  * ``FootprintAudit`` (TASK-IG-004/C48)   -> POST /osint/footprint-audit
  * ``SocialLinkReader`` (TASK-IG-INT-02)  -> GET  /osint/social-link
    (the reader is also wired into the retriever's fetch path)
  * ``untrusted_ingest.run_investigation`` (TASK-IG2-INT-04, Robin
    pattern) -> POST /research/investigations, with the production
    clearnet connectors injected exactly as the module's docstring
    prescribes. Like /research/live, investigations refuse MOCK_MODE:
    untrusted-ingest evidence must come from live sources, never from
    search fixtures.

The footprint audit stays keyless-only: sections that need a paid key
or a dark-web source are reported UNAVAILABLE by the audit itself, and
the breach section's email leg stays fail-closed (no HIBP key exists;
free-only rule) — this route does not work around that.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from intelx.core.settings import get_settings

logger = logging.getLogger("intelx.api.osint_tools")

router = APIRouter(tags=["OSINT Tools"])


# ---------------------------------------------------------------------------
# TrackingService consumer
# ---------------------------------------------------------------------------


@router.get("/tracking/snapshot", summary="Live multi-layer tracking snapshot")
async def tracking_snapshot(
    kinds: str | None = Query(
        default=None,
        description="Comma-separated layer kinds to include: flight, satellite, ship, event",
    ),
) -> dict:
    """One normalised snapshot across the flight/satellite/ship/event layers.

    Layers fail independently and report their own errors in the
    snapshot — a layer that cannot be read says so instead of the
    endpoint failing or fabricating objects.
    """
    from intelx.tracking.service import TrackingService

    kind_set = {k.strip() for k in kinds.split(",") if k.strip()} if kinds else None
    snapshot = await TrackingService().snapshot(kinds=kind_set)
    return snapshot.to_dict()


# ---------------------------------------------------------------------------
# FootprintAudit consumer
# ---------------------------------------------------------------------------


class FootprintAuditPayload(BaseModel):
    username: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)


@router.post("/osint/footprint-audit", summary="Personal digital-footprint audit (keyless checks only)")
async def footprint_audit(body: FootprintAuditPayload) -> dict:
    """Run the keyless footprint audit for a username / email / phone.

    The report is explicit about what was NOT checked (dark-web,
    breach and carrier sections need keys/sources IntelX does not
    have) — see the audit module's UNAVAILABLE_SECTIONS.
    """
    from intelx.osint.audit import FootprintAudit

    try:
        return await FootprintAudit().run(
            username=body.username, email=body.email, phone=body.phone
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# SocialLinkReader consumer (also wired into the retriever)
# ---------------------------------------------------------------------------


@router.get("/osint/social-link", summary="Read a social link into a verbatim document")
async def social_link(url: str = Query(..., min_length=8, max_length=2048)) -> dict:
    """Extract a YouTube / Reddit / Instagram / web link verbatim.

    Returns 422 with the reader's honest reason when the content is
    blocked, login-gated or removed — never a fabricated document.
    """
    from intelx.connectors.social_links import SocialLinkReader, SocialLinkUnavailable

    try:
        doc = await SocialLinkReader().read(url)
    except SocialLinkUnavailable as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc
    return doc.to_dict()


# ---------------------------------------------------------------------------
# untrusted_ingest consumer (Robin-pattern investigations)
# ---------------------------------------------------------------------------


async def _investigation_search(query: str) -> list[dict]:
    """Production SearchFn: the hardened WebSearchConnector router."""
    from intelx.connectors.search import WebSearchConnector

    hits = await WebSearchConnector().fetch(query, max_results=10)
    return [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits]


async def _investigation_fetch(url: str) -> str:
    """Production FetchFn: the hardened HttpFetchConnector, text-normalised.

    Mirrors the /scrape endpoint's honesty: a robots refusal is an
    error (the investigation counts the page as dropped), never
    silently bypassed.
    """
    from intelx.connectors.web import HttpFetchConnector
    from intelx.memory.normalize import normalize_text_content

    result = await HttpFetchConnector().fetch(url)
    if getattr(result, "robots_ok", True) is False:
        raise RuntimeError(result.error or "Disallowed by robots.txt")
    if not isinstance(result.content, bytes):
        raise TypeError("fetch returned non-byte content")
    return normalize_text_content(result.content, getattr(result, "content_type", "text/plain"))


class InvestigationPayload(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=10)


@router.post(
    "/research/investigations",
    summary="Robin-pattern investigation over untrusted web content",
)
async def create_investigation(body: InvestigationPayload) -> dict:
    """Search -> fetch -> relevance-gate -> sanitise -> delimiter-wrap.

    Everything fetched is treated as hostile: invisible characters are
    stripped, forged closing delimiters are defused, and the evidence
    is returned wrapped as UNTRUSTED_DATA for safe LLM consumption.
    """
    if get_settings().MOCK_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Investigations are unavailable while IntelX is in MOCK_MODE; "
                "untrusted-ingest evidence must come from live clearnet sources"
            ),
        )
    from intelx.ingestion.untrusted_ingest import run_investigation

    result = await run_investigation(
        body.query,
        search=_investigation_search,
        fetch=_investigation_fetch,
        max_results=body.max_results,
    )
    return result.to_dict()


__all__ = ["router"]
