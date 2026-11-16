"""Standing feed routes: headline watch + AI radar (IG wiring, X-07).

These routes are the API consumers of the two standing feed libraries
shipped by TASK-IG-INT-01 (``HeadlineWatch``) and TASK-IG2-INT-05
(``AiRadar``). They read the process-wide instances from
``intelx.ingestion.feed_service`` — the same instances the lifespan
hooks poll when ENABLE_HEADLINE_WATCH / ENABLE_AI_RADAR are on — so
what Stratex (or any caller) reads here is the standing feed, not a
per-request reconstruction. The ``/poll`` routes let an operator (or a
scheduler on another host) drive a sweep on demand when the in-process
loops are disabled.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from intelx.ingestion.feed_service import get_ai_radar, get_headline_watch

router = APIRouter(tags=["Standing Feeds"])


@router.get("/feeds/headlines", summary="Latest buffered headlines from the standing watch")
async def feed_headlines(
    limit: int = Query(default=20, ge=1, le=200),
    min_score: int = Query(default=0, ge=0, le=100),
    asset: str | None = Query(default=None),
) -> dict:
    """Newest headlines at/above an impact floor — the Stratex-facing feed."""
    watch = get_headline_watch()
    items = watch.latest(limit=limit, min_score=min_score, asset=asset)
    return {"count": len(items), "headlines": [h.to_dict() for h in items]}


@router.get("/feeds/headlines/sources", summary="Headline-watch source registry and poll state")
async def feed_headline_sources() -> dict:
    """Per-source state, including WHY inactive sources are inactive."""
    return {"sources": get_headline_watch().source_report()}


@router.post("/feeds/headlines/poll", summary="Drive one headline-watch sweep now")
async def feed_headlines_poll() -> dict:
    fresh = await get_headline_watch().poll_once()
    return {"new": len(fresh), "headlines": [h.to_dict() for h in fresh]}


@router.get("/feeds/ai-radar", summary="AI-trending radar digest")
async def feed_ai_radar(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    """Trending AI topics + per-source honesty from the shared radar."""
    return get_ai_radar().digest(limit=limit)


@router.post("/feeds/ai-radar/poll", summary="Drive one AI-radar sweep now")
async def feed_ai_radar_poll() -> dict:
    radar = get_ai_radar()
    fresh = await radar.poll_once()
    return {"new_items": len(fresh), "digest": radar.digest()}


__all__ = ["router"]
