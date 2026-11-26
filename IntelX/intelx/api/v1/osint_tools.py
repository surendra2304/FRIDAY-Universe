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

TASK-INT-051 additions (same consumer pattern, one route per library):

  * ``AgentReachReader`` (Agent Reach no-login channels) -> GET
    /osint/social-link fallback: a GitHub / RSS / V2EX / Bilibili URL
    the social reader cannot read is tried against the reach reader
    before the route answers 422. The reach reader is GET-only and
    refuses login-gated hosts outright.
  * ``helix_lookup`` (TASK-IG2-INT-03, Helix pattern) -> POST
    /osint/username-lookup, with the owner-approved-subject gate read
    from ``INTELX_HELIX_APPROVED_SUBJECTS`` and every run recorded in
    the Helix watch store (``--watch`` change history).
  * ``InvestigationStore`` (Robin saved investigations) -> GET
    /research/investigations/{id} and POST
    /research/investigations/{id}/follow-up; creation now saves the
    run and returns its id.

The footprint audit stays keyless-only: sections that need a paid key
or a dark-web source are reported UNAVAILABLE by the audit itself, and
the breach section's email leg stays fail-closed (no HIBP key exists;
free-only rule) — this route does not work around that.
"""

from __future__ import annotations

import logging
import os

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


async def read_social_link_document(url: str, *, social_reader=None, reach_reader=None):
    """Read a social link, falling back to the Agent Reach channels.

    TASK-INT-051: the social reader owns YouTube / Reddit / Instagram /
    web; a URL it cannot read (login-gated, removed, unsupported) is
    tried against the Agent Reach no-login channels (GitHub / RSS /
    V2EX / Bilibili) before giving up. Raises
    ``SocialLinkUnavailable`` with the combined reason when neither
    reader can read the link. Readers are injectable for hermetic tests.
    """
    from intelx.connectors.agent_reach import AgentReachReader, AgentReachUnavailable
    from intelx.connectors.social_links import SocialLinkReader, SocialLinkUnavailable

    social = social_reader or SocialLinkReader()
    try:
        return await social.read(url)
    except SocialLinkUnavailable as social_exc:
        reach = reach_reader or AgentReachReader()
        try:
            return await reach.read(url)
        except AgentReachUnavailable as reach_exc:
            raise SocialLinkUnavailable(
                url, f"{social_exc.reason}; Agent Reach: {reach_exc.reason}"
            ) from reach_exc


@router.get("/osint/social-link", summary="Read a social link into a verbatim document")
async def social_link(url: str = Query(..., min_length=8, max_length=2048)) -> dict:
    """Extract a YouTube / Reddit / Instagram / web link verbatim.

    GitHub / RSS / V2EX / Bilibili links fall back to the Agent Reach
    no-login channels. Returns 422 with the readers' honest reason
    when the content is blocked, login-gated or removed — never a
    fabricated document.
    """
    from intelx.connectors.social_links import SocialLinkUnavailable

    try:
        doc = await read_social_link_document(url)
    except SocialLinkUnavailable as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc
    return doc.to_dict()


# ---------------------------------------------------------------------------
# helix_lookup consumer (Helix-pattern username lookup + watch history)
# ---------------------------------------------------------------------------


def _approved_subjects() -> list[str]:
    """Owner-named subjects for OSINT lookups (comma-separated env)."""
    raw = os.environ.get("INTELX_HELIX_APPROVED_SUBJECTS", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


class UsernameLookupPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    max_sites: int = Field(default=25, ge=1, le=50)


@router.post(
    "/osint/username-lookup",
    summary="Helix-pattern username lookup (owner-approved subjects only)",
)
async def username_lookup(body: UsernameLookupPayload) -> dict:
    """Check one username across IntelX's curated platforms.

    The approved-subject gate fires before any network traffic: the
    username must be in ``INTELX_HELIX_APPROVED_SUBJECTS`` or the route
    answers 403. Every hit is re-checked against a deterministic
    control-probe username before it is reported, and the run is
    recorded in the Helix watch store so the response can report what
    changed since the last lookup. Refuses MOCK_MODE: a lookup must
    come from live sources, never fixtures.
    """
    approved = _approved_subjects()
    if body.username not in approved:
        raise HTTPException(
            status_code=403,
            detail=(
                "subject is not owner-approved for OSINT lookup; "
                "add the username to INTELX_HELIX_APPROVED_SUBJECTS only "
                "when the owner has named it"
            ),
        )
    if get_settings().MOCK_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Username lookups are unavailable while IntelX is in MOCK_MODE; "
                "OSINT evidence must come from live sources"
            ),
        )
    from intelx.osint.helix_lookup import helix_lookup
    from intelx.osint.helix_watch import get_watch_store

    store = get_watch_store()
    report = await helix_lookup(
        body.username,
        approved_subjects=approved,
        max_sites=body.max_sites,
    )
    changes = store.diff(body.username, report)
    store.record(report)
    payload = report.to_dict()
    payload["changes_since_last"] = changes
    return payload


@router.get(
    "/osint/username-lookup/{username}/history",
    summary="Helix watch history for one approved subject",
)
async def username_lookup_history(username: str) -> dict:
    """Stored lookup snapshots for a subject, oldest first."""
    if username not in _approved_subjects():
        raise HTTPException(
            status_code=403,
            detail="subject is not owner-approved for OSINT lookup",
        )
    from intelx.osint.helix_watch import get_watch_store

    return {"username": username, "snapshots": get_watch_store().history(username)}


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
    The run is saved in the investigation store and its id is returned,
    so it can be re-read and followed up on (TASK-INT-051).
    """
    if get_settings().MOCK_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Investigations are unavailable while IntelX is in MOCK_MODE; "
                "untrusted-ingest evidence must come from live clearnet sources"
            ),
        )
    from intelx.ingestion.investigation_store import get_store
    from intelx.ingestion.untrusted_ingest import run_investigation

    result = await run_investigation(
        body.query,
        search=_investigation_search,
        fetch=_investigation_fetch,
        max_results=body.max_results,
    )
    payload = result.to_dict()
    payload["id"] = get_store().save(result)
    return payload


@router.get(
    "/research/investigations/{investigation_id}",
    summary="Re-read a saved Robin-pattern investigation",
)
async def get_investigation(investigation_id: str) -> dict:
    """Return a saved investigation, including its pivot queries."""
    from intelx.ingestion.investigation_store import get_store

    result = get_store().get(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown investigation {investigation_id!r}")
    payload = result.to_dict()
    payload["id"] = investigation_id
    return payload


class InvestigationFollowUpPayload(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=10)


@router.post(
    "/research/investigations/{investigation_id}/follow-up",
    summary="Grounded follow-up on a saved investigation",
)
async def follow_up_investigation(
    investigation_id: str, body: InvestigationFollowUpPayload
) -> dict:
    """Run a follow-up question grounded in a saved investigation.

    The fresh run goes through the same pipeline (search -> fetch ->
    relevance gate -> sanitise -> delimiter-wrap); the response reports
    which saved evidence items share terms with the follow-up, so the
    investigator sees what the new run builds on. Refuses MOCK_MODE
    like creation, and 404s for an unknown investigation id.
    """
    if get_settings().MOCK_MODE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Investigations are unavailable while IntelX is in MOCK_MODE; "
                "untrusted-ingest evidence must come from live clearnet sources"
            ),
        )
    from intelx.ingestion.investigation_store import get_store

    store = get_store()
    if store.get(investigation_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown investigation {investigation_id!r}")
    try:
        follow_up = await store.follow_up(
            investigation_id,
            body.question,
            search=_investigation_search,
            fetch=_investigation_fetch,
            max_results=body.max_results,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return follow_up.to_dict()


__all__ = ["router"]
