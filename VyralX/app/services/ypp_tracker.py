"""YouTube Partner Program (YPP) eligibility tracker (TASK-VYR-014).

Channel-level monetization progress for the VyralX Agent channel. Until this
module existed, VyralX tracked per-video counters only (youtube_analytics.py)
and had no subscriber count, no channel totals and no YPP progress anywhere.

What this does:
* snapshots the channel's public statistics (subscribers, total views, video
  count) from the YouTube Data API into ``channel_snapshots``;
* computes progress against both YPP tiers from the numbers we can actually
  measure, and says so where a number cannot be measured from here.

Honesty rules (TASK-REL-020 pattern):
* Watch hours are NOT available from the Data API public statistics, and the
  YouTube Analytics API is not integrated, so the watch-hours path is reported
  as ``unknown`` — never estimated, never treated as met or unmet.
* The Shorts-views figure is a tracked floor: lifetime views of PUBLIC videos
  this system uploaded inside the window (their views all happened inside the
  window). Views inside the window on older public videos cannot be separated
  from lifetime counters, so the true figure is >= the tracked one. YouTube
  Studio's "qualified" figure is authoritative; this tracker exists so the
  channel's approach to the thresholds is visible between Studio checks.
* Only public videos count toward YPP. While every upload is unlisted, the
  tracked public figures are zero — that is the publish decision's cost, made
  visible, not a tracking bug.

Thresholds (YouTube Help, checked 2026-11-17):
* Fan-funding tier: 500 subscribers + 3 public uploads in 90 days + 3,000
  watch hours in 12 months OR 3M valid public Shorts views in 90 days.
* Ad-revenue tier: 1,000 subscribers + 4,000 watch hours in 12 months OR 10M
  valid public Shorts views in 90 days.
* From 2027-02-01, NEW ad-tier applicants need 8,000 watch hours OR 20M
  Shorts views in 90 days, and Shorts revenue sharing itself requires 10M
  qualified Shorts views in the last 90 days each month.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChannelSnapshot, PublishJob, VideoMetric, utcnow

log = logging.getLogger("vyralx.ypp_tracker")

CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

FAN_FUNDING = {
    "subscribers": 500,
    "public_uploads_90d": 3,
    "shorts_views_90d": 3_000_000,
    "watch_hours_12m": 3_000,
}
AD_TIER = {
    "subscribers": 1_000,
    "shorts_views_90d": 10_000_000,
    "watch_hours_12m": 4_000,
}
AD_TIER_FROM_2027_02_01 = {
    "subscribers": 1_000,
    "shorts_views_90d": 20_000_000,
    "watch_hours_12m": 8_000,
    "note": (
        "Applies to NEW ad-tier applicants from 2027-02-01. Shorts revenue "
        "sharing additionally requires 10M qualified Shorts views in the "
        "last 90 days in each month, for every channel."
    ),
}


def _requirement(current: int | None, target: int) -> dict[str, Any]:
    if current is None:
        return {"current": None, "target": target, "met": None, "pct": None}
    return {
        "current": int(current),
        "target": int(target),
        "met": int(current) >= int(target),
        "pct": round(min(100.0, 100.0 * int(current) / int(target)), 2) if target else 100.0,
    }


def _path_met(shorts_req: dict, hours_req: dict) -> bool | None:
    """A tier's activity path is met if EITHER route is met; unknown if the
    Shorts route is unmet and the hours route cannot be measured."""
    if shorts_req["met"] or hours_req["met"]:
        return True
    if hours_req["met"] is None:
        return None
    return False


def compute_ypp_progress(
    *,
    subscriber_count: int,
    public_uploads_90d: int,
    shorts_views_90d: int,
    watch_hours_12m: int | None = None,
) -> dict[str, Any]:
    """Pure progress computation against both YPP tiers (unit-testable)."""
    fan = {
        "subscribers": _requirement(subscriber_count, FAN_FUNDING["subscribers"]),
        "public_uploads_90d": _requirement(public_uploads_90d, FAN_FUNDING["public_uploads_90d"]),
        "shorts_views_90d": _requirement(shorts_views_90d, FAN_FUNDING["shorts_views_90d"]),
        "watch_hours_12m": _requirement(watch_hours_12m, FAN_FUNDING["watch_hours_12m"]),
    }
    fan["activity_path_met"] = _path_met(fan["shorts_views_90d"], fan["watch_hours_12m"])
    fan["eligible"] = bool(
        fan["subscribers"]["met"] and fan["public_uploads_90d"]["met"] and fan["activity_path_met"]
    )

    ad = {
        "subscribers": _requirement(subscriber_count, AD_TIER["subscribers"]),
        "shorts_views_90d": _requirement(shorts_views_90d, AD_TIER["shorts_views_90d"]),
        "watch_hours_12m": _requirement(watch_hours_12m, AD_TIER["watch_hours_12m"]),
    }
    ad["activity_path_met"] = _path_met(ad["shorts_views_90d"], ad["watch_hours_12m"])
    ad["eligible"] = bool(ad["subscribers"]["met"] and ad["activity_path_met"])

    return {
        "fan_funding_tier": fan,
        "ad_revenue_tier": ad,
        "ad_tier_from_2027_02_01": dict(AD_TIER_FROM_2027_02_01),
        "notes": [
            "Watch hours are not measurable from the YouTube Data API; the "
            "hours path is reported as unknown, never assumed.",
            "Shorts views are the tracked floor (public uploads inside the "
            "window); YouTube Studio's qualified figure is authoritative.",
            "Only public videos and their views count toward YPP.",
        ],
    }


def fetch_channel_statistics(settings: Any | None = None) -> dict[str, Any]:
    """Fetch the channel's public statistics from the YouTube Data API.

    Resolution order: explicit ``youtube_channel_id`` + Data API key, else the
    OAuth-authorised channel (``mine=true``) via the existing youtube service.
    Raises RuntimeError with a precise reason when neither path is available.
    """
    settings = settings or get_settings()
    channel_id = str(getattr(settings, "youtube_channel_id", "") or "").strip()
    api_key = str(getattr(settings, "youtube_data_api_key", "") or "").strip()

    if channel_id and api_key:
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(
                    CHANNELS_URL,
                    params={"key": api_key, "part": "statistics,snippet", "id": channel_id},
                )
                response.raise_for_status()
                items = response.json().get("items", [])
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"YouTube Data API returned HTTP {exc.response.status_code} for channel lookup"
            ) from None
        except httpx.RequestError as exc:
            raise RuntimeError(f"Channel lookup request failed ({type(exc).__name__})") from None
        except ValueError:
            raise RuntimeError("YouTube Data API returned invalid JSON") from None
        if not items:
            raise RuntimeError(f"No channel found for youtube_channel_id={channel_id}")
        return _parse_channel_item(items[0])

    # Fall back to the OAuth channel (the same session uploads use).
    try:
        from app.services.youtube import youtube_service

        service = youtube_service()
        result = service.channels().list(part="statistics,snippet", mine=True).execute()
        items = result.get("items", [])
    except Exception as exc:
        raise RuntimeError(
            "Channel statistics unavailable: set youtube_channel_id + "
            f"youtube_data_api_key, or restore the YouTube OAuth session ({type(exc).__name__})"
        ) from None
    if not items:
        raise RuntimeError("OAuth channel lookup returned no channel")
    return _parse_channel_item(items[0])


def _parse_channel_item(item: dict) -> dict[str, Any]:
    stats = item.get("statistics", {}) or {}
    snippet = item.get("snippet", {}) or {}
    return {
        "channel_id": str(item.get("id", "")),
        "channel_title": str(snippet.get("title", "")),
        "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
        "subscriber_count_hidden": bool(stats.get("hiddenSubscriberCount", False)),
        "total_view_count": int(stats.get("viewCount", 0) or 0),
        "video_count": int(stats.get("videoCount", 0) or 0),
    }


def tracked_public_figures(db: Session, *, days: int = 90, now: datetime | None = None) -> dict[str, int]:
    """Tracked floor figures from our own publish + metric tables.

    Counts only jobs this system uploaded as PUBLIC inside the window. A
    public video published inside the window earned all of its lifetime views
    inside the window, so summing its latest VideoMetric counter is exact for
    that video; public videos older than the window are excluded entirely,
    which is why the result is a floor, not the channel's true 90-day views.
    """
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=days)

    jobs = db.scalars(
        select(PublishJob).where(
            PublishJob.status == "uploaded",
            PublishJob.privacy_status == "public",
            PublishJob.youtube_video_id != "",
        )
    ).all()

    uploads_90d = 0
    views_90d = 0
    tracked_public_total = 0
    for job in jobs:
        tracked_public_total += 1
        stamp = job.completed_at or job.created_at
        if stamp is None:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp < cutoff:
            continue
        uploads_90d += 1
        metric = db.scalar(
            select(VideoMetric)
            .where(VideoMetric.youtube_video_id == job.youtube_video_id)
            .order_by(VideoMetric.id.desc())
        )
        if metric is not None:
            views_90d += int(metric.view_count or 0)

    return {
        "public_uploads_90d": uploads_90d,
        "shorts_views_90d_tracked": views_90d,
        "tracked_public_uploads_total": tracked_public_total,
    }


def snapshot_channel(db: Session, settings: Any | None = None) -> dict[str, Any]:
    """Fetch channel statistics, persist a snapshot, return YPP status."""
    settings = settings or get_settings()
    stats = fetch_channel_statistics(settings)
    tracked = tracked_public_figures(db)

    snapshot = ChannelSnapshot(
        channel_id=stats["channel_id"],
        channel_title=stats["channel_title"],
        subscriber_count=stats["subscriber_count"],
        total_view_count=stats["total_view_count"],
        video_count=stats["video_count"],
        public_uploads_90d=tracked["public_uploads_90d"],
        shorts_views_90d=tracked["shorts_views_90d_tracked"],
        fetched_at=utcnow(),
    )
    db.add(snapshot)
    db.commit()

    progress = compute_ypp_progress(
        subscriber_count=stats["subscriber_count"],
        public_uploads_90d=tracked["public_uploads_90d"],
        shorts_views_90d=tracked["shorts_views_90d_tracked"],
    )
    log.info(
        "YPP snapshot: subs=%s total_views=%s public_uploads_90d=%s tracked_shorts_views_90d=%s "
        "fan_funding_eligible=%s ad_tier_eligible=%s",
        stats["subscriber_count"], stats["total_view_count"],
        tracked["public_uploads_90d"], tracked["shorts_views_90d_tracked"],
        progress["fan_funding_tier"]["eligible"], progress["ad_revenue_tier"]["eligible"],
    )
    return {
        "data_status": "ok",
        "snapshot": _snapshot_dict(snapshot),
        "progress": progress,
    }


def _snapshot_dict(snapshot: ChannelSnapshot) -> dict[str, Any]:
    return {
        "channel_id": snapshot.channel_id,
        "channel_title": snapshot.channel_title,
        "subscriber_count": int(snapshot.subscriber_count or 0),
        "total_view_count": int(snapshot.total_view_count or 0),
        "video_count": int(snapshot.video_count or 0),
        "public_uploads_90d": int(snapshot.public_uploads_90d or 0),
        "shorts_views_90d_tracked": int(snapshot.shorts_views_90d or 0),
        "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
    }


def latest_ypp_status(db: Session) -> dict[str, Any]:
    """Latest snapshot + progress, or an explicit no-data status."""
    snapshot = db.scalar(select(ChannelSnapshot).order_by(ChannelSnapshot.id.desc()))
    if snapshot is None:
        return {
            "data_status": "no_data",
            "note": (
                "No channel snapshot yet. Snapshots are taken by the viral "
                "autopilot each cycle, or on demand via POST /api/monetization/ypp/sync."
            ),
            "progress": compute_ypp_progress(
                subscriber_count=0, public_uploads_90d=0, shorts_views_90d=0
            ),
        }
    return {
        "data_status": "ok",
        "snapshot": _snapshot_dict(snapshot),
        "progress": compute_ypp_progress(
            subscriber_count=int(snapshot.subscriber_count or 0),
            public_uploads_90d=int(snapshot.public_uploads_90d or 0),
            shorts_views_90d=int(snapshot.shorts_views_90d or 0),
        ),
    }
