"""All-category trending discovery for the autonomous loop (TASK-VYR-019).

The pre-loop discovery only ever looks where the channel has already
been: four seed creators, their recommendation graph, and comedy style
lanes — which is how the gated renders kept meeting the same stale
12-candidate pool. The owner's locked shape (2026-11-18) is the
opposite: find ALL popular videos, in every category, and organise
them by series.

This module sweeps YouTube's ``mostPopular`` chart once per assignable
category through the official Data API (1 quota unit per category
page) and returns ordinary :class:`~app.services.viral_discovery.Candidate`
objects whose ``category`` is the editorial label from
:mod:`app.services.viral_series` — so ranking, production, metadata
and series filing all work unchanged downstream.

Contract mirrors :mod:`app.services.youtube_api_discovery`: discovery
is best-effort and degrades to an empty (or partial) result instead of
raising. Under the ``reuse_licensed`` source policy the chart cannot
prove a Creative Commons licence for any row, so the sweep honestly
returns nothing rather than laundering chart videos into "licensed".
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.services.viral_discovery import Candidate, score_candidate
from app.services.viral_series import YOUTUBE_TRENDING_CATEGORIES

log = logging.getLogger("vyralx.viral_trending")

_DEFAULT_HOOKS = {
    "VIRAL": "WAIT FOR IT",
    "COMEDY": "WAIT FOR IT",
    "SPORTS": "DO NOT TRY THIS",
}


def _candidate_from_chart_item(item: dict[str, Any], label: str) -> Candidate | None:
    from app.services.youtube_api_discovery import _compact_upload_date, _parse_iso_duration

    video_id = str(item.get("id") or "").strip()
    snippet = item.get("snippet") or {}
    details = item.get("contentDetails") or {}
    stats = item.get("statistics") or {}
    if not video_id or not isinstance(snippet, dict):
        return None
    info = {
        "view_count": int(stats.get("viewCount") or 0),
        "like_count": int(stats.get("likeCount") or 0),
        "comment_count": int(stats.get("commentCount") or 0),
        "duration": float(_parse_iso_duration(details.get("duration"))),
        "upload_date": _compact_upload_date(snippet.get("publishedAt")),
        "title": str(snippet.get("title") or ""),
    }
    return Candidate(
        video_id=video_id,
        title=info["title"],
        channel=str(snippet.get("channelTitle") or ""),
        duration=round(info["duration"], 2),
        view_count=info["view_count"],
        like_count=info["like_count"],
        upload_date=info["upload_date"],
        license="transformative_commentary",
        category=label,
        hook=_DEFAULT_HOOKS.get(label, "WAIT FOR IT"),
        score=score_candidate(info, set()),
        tags=[str(tag) for tag in (snippet.get("tags") or [])][:8],
        description=str(snippet.get("description") or "")[:1200],
        webpage_url=f"https://www.youtube.com/watch?v={video_id}",
    )


def trending_candidates(
    *,
    per_category: int = 10,
    exclude_ids: set[str] | None = None,
    min_views: int = 250_000,
    min_seconds: float = 8.0,
    max_seconds: float = 600.0,
    region: str = "",
    service: Any = None,
) -> list[Candidate]:
    """One mostPopular sweep per YouTube category, ranked as one pool."""
    settings = get_settings()
    if str(getattr(settings, "viral_source_policy", "transformative")) == "reuse_licensed":
        log.info(
            "Trending sweep skipped: the chart cannot verify a reuse licence "
            "and the source policy is reuse_licensed"
        )
        return []
    if service is None:
        try:
            from app.services.youtube import youtube_service

            service = youtube_service()
        except Exception as exc:
            log.warning("Trending sweep unavailable (%s)", type(exc).__name__)
            return []
    exclude = {str(value) for value in (exclude_ids or set()) if value}
    found: dict[str, Candidate] = {}
    for category_id, label, _name in YOUTUBE_TRENDING_CATEGORIES:
        try:
            request = service.videos().list(
                part="snippet,contentDetails,statistics",
                chart="mostPopular",
                videoCategoryId=category_id,
                maxResults=max(1, min(int(per_category), 50)),
                **({"regionCode": region} if region else {}),
            )
            payload = request.execute()
        except Exception as exc:
            log.info(
                "Trending category %s unavailable: %s", category_id, type(exc).__name__
            )
            continue
        for item in (payload or {}).get("items") or []:
            candidate = _candidate_from_chart_item(item, label)
            if candidate is None or candidate.video_id in exclude:
                continue
            if not (min_seconds <= candidate.duration <= max_seconds):
                continue
            if candidate.view_count < min_views:
                continue
            existing = found.get(candidate.video_id)
            if existing is None or candidate.score > existing.score:
                found[candidate.video_id] = candidate
    ranked = sorted(found.values(), key=lambda item: item.score, reverse=True)
    log.info(
        "Trending sweep found %d candidates across %d categories",
        len(ranked), len(YOUTUBE_TRENDING_CATEGORIES),
    )
    return ranked
