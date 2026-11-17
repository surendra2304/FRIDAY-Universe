"""Brand-deal pitch drafts for VyralX — template asset + real-metrics fill.

Source: Instagram General-section cluster B8-C3 (roll-up R-16) — a
fill-in-the-blanks brand-collaboration pitch letter shared via a creator
funnel. The wording here is written in-house from that template's structure
(creator intro -> channel highlights -> collaboration ask -> media-kit
offer); no text is copied from the shared template.

DRAFTS ONLY. This module generates pitch drafts and stores them in the
``brand_pitch_drafts`` table. It has NO send path: there is no email, DM, or
any other outbound-delivery code in this module, and none may be added
without a separate owner-approved change. A draft leaves this system only
when a human copies it out.

Honesty rule: every figure in a draft comes from the channel's real
``video_metrics`` store (populated by the VYR-882 metrics sync). A metric
with no stored value renders as a visible blank marker — never as an
invented, projected, or "typical" number. This module is the honest
counterpart to ``app.services.media_kit.generate_brand_pitch_email``, whose
projected figures must not be quoted to brands.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BrandPitchDraft, VideoMetric
from app.services.youtube_analytics import calculate_engagement_rate

log = logging.getLogger("vyralx.brand_pitch")

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)

TEMPLATE_NAME = "brand_collab_pitch_v1"

# Rendered wherever a figure has no stored value, so a reader can see at a
# glance that the number is absent rather than estimated.
BLANK = "[not yet measured]"

# The pitch template names no contact address. Until the owner designates a
# real outreach address, the sign-off carries this clearly-marked placeholder
# instead of any invented address.
CONTACT_PLACEHOLDER = "[contact email to be added before any use]"

# Named template asset with explicit slots. Structure follows the B8-C3
# source template; wording is original to this codebase.
PITCH_TEMPLATE = """\
Subject: {subject_line}

Hello {brand_name} team,

I am {creator_name}, the creator behind {channel_handle} on {platform}, where I publish {niche_phrase} for a growing audience.

Channel highlights, from our own tracked channel metrics:
- Videos tracked: {video_count}
- Total views: {total_views}
- Average views per video: {avg_views_per_video}
- Total likes: {total_likes}
- Engagement rate: {engagement_rate}
- Subscribers: {subscriber_count}
- Audience demographics: {demographics}
{metrics_note}

I follow what {brand_name} is building and believe your products would genuinely interest my viewers. I would like to propose a collaboration — {collab_format} — created in the channel's usual style so it feels native to the audience.

If that sounds worth exploring, I am happy to share a media kit and talk through formats and timelines.

Thank you for your time and consideration,
{creator_name}
{channel_handle} on {platform}
{contact_email}
"""

TEMPLATE_SLOTS = frozenset({
    "subject_line",
    "brand_name",
    "creator_name",
    "channel_handle",
    "platform",
    "niche_phrase",
    "video_count",
    "total_views",
    "avg_views_per_video",
    "total_likes",
    "engagement_rate",
    "subscriber_count",
    "demographics",
    "metrics_note",
    "collab_format",
    "contact_email",
})


@dataclass(frozen=True)
class ChannelHighlights:
    """Channel figures for the pitch, sourced from the metrics store.

    ``None`` always means "no stored value" and renders as :data:`BLANK`;
    a stored zero is a real measurement and renders as ``0``.
    """

    video_count: int = 0
    total_views: int | None = None
    total_likes: int | None = None
    total_comments: int | None = None
    avg_views_per_video: int | None = None
    engagement_rate_pct: float | None = None
    subscriber_count: int | None = None
    demographics: str | None = None
    metrics_fetched_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_count": self.video_count,
            "total_views": self.total_views,
            "total_likes": self.total_likes,
            "total_comments": self.total_comments,
            "avg_views_per_video": self.avg_views_per_video,
            "engagement_rate_pct": self.engagement_rate_pct,
            "subscriber_count": self.subscriber_count,
            "demographics": self.demographics,
            "metrics_fetched_at": (
                self.metrics_fetched_at.isoformat() if self.metrics_fetched_at else None
            ),
            "source": "video_metrics",
        }


def highlights_from_metrics(
    db: Session,
    *,
    subscriber_count: int | None = None,
    demographics: str | None = None,
) -> ChannelHighlights:
    """Build channel highlights from the real ``video_metrics`` store.

    The store holds one row per video (the metrics sync upserts in place);
    rows are de-duplicated by video id keeping the freshest fetch, in case a
    duplicate ever lands. Subscriber count and audience demographics are NOT
    held in the metrics store: pass them only when they were read from a
    verified source (e.g. the channel page) at draft time, otherwise leave
    them ``None`` and their slots render blank.
    """
    if subscriber_count is not None and subscriber_count < 0:
        raise ValueError("subscriber_count must be non-negative or None")

    rows = db.scalars(select(VideoMetric)).all()
    freshest: dict[str, VideoMetric] = {}
    for row in rows:
        key = row.youtube_video_id or f"row:{row.id}"
        current = freshest.get(key)
        if current is None or (row.fetched_at or _OLDEST) > (current.fetched_at or _OLDEST):
            freshest[key] = row
    videos = list(freshest.values())
    if not videos:
        return ChannelHighlights(
            video_count=0,
            subscriber_count=subscriber_count,
            demographics=demographics or None,
        )

    total_views = sum(max(0, int(v.view_count)) for v in videos)
    total_likes = sum(max(0, int(v.like_count)) for v in videos)
    total_comments = sum(max(0, int(v.comment_count)) for v in videos)
    fetched = [v.fetched_at for v in videos if v.fetched_at]
    return ChannelHighlights(
        video_count=len(videos),
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        avg_views_per_video=int(round(total_views / len(videos))),
        engagement_rate_pct=(
            calculate_engagement_rate(total_views, total_likes, total_comments)
            if total_views > 0
            else None
        ),
        subscriber_count=subscriber_count,
        demographics=demographics or None,
        metrics_fetched_at=max(fetched) if fetched else None,
    )


def _fmt_count(value: int | None) -> str:
    return BLANK if value is None else f"{value:,}"


def _fmt_engagement(value: float | None) -> str:
    return BLANK if value is None else f"{value:.2f}%"


def render_pitch(
    *,
    brand_name: str,
    highlights: ChannelHighlights,
    creator_name: str,
    platform: str = "YouTube",
    channel_handle: str = "",
    niche: str = "",
    collab_format: str = "a sponsored short-form video featuring your product",
    contact_email: str = "",
) -> tuple[str, str]:
    """Fill the template's slots and return ``(subject, body)``.

    Metric slots with no stored value render as :data:`BLANK`. The contact
    line renders :data:`CONTACT_PLACEHOLDER` unless a real address is given.
    """
    brand = (brand_name or "").strip()
    if not brand:
        raise ValueError("brand_name is required to draft a pitch")
    creator = (creator_name or "").strip()
    if not creator:
        raise ValueError("creator_name is required to draft a pitch")
    handle = (channel_handle or "").strip() or creator
    niche_text = (niche or "").strip()
    niche_phrase = f"short-form videos about {niche_text}" if niche_text else "short-form videos"

    if highlights.video_count:
        note = (
            f"(Figures above are the channel's own synced metrics, last fetched "
            f"{highlights.metrics_fetched_at.date().isoformat()}; blank entries are figures "
            f"we do not track yet, not estimates.)"
            if highlights.metrics_fetched_at
            else "(Blank entries are figures we do not track yet, not estimates.)"
        )
    else:
        note = (
            "(Our channel metrics have not been synced yet, so every figure above is "
            "blank rather than estimated.)"
        )

    subject = f"Collaboration idea for {brand} — from {creator} ({platform})"
    body = PITCH_TEMPLATE.format(
        subject_line=subject,
        brand_name=brand,
        creator_name=creator,
        channel_handle=handle,
        platform=(platform or "YouTube").strip() or "YouTube",
        niche_phrase=niche_phrase,
        video_count=f"{highlights.video_count:,}",
        total_views=_fmt_count(highlights.total_views),
        avg_views_per_video=_fmt_count(highlights.avg_views_per_video),
        total_likes=_fmt_count(highlights.total_likes),
        engagement_rate=_fmt_engagement(highlights.engagement_rate_pct),
        subscriber_count=_fmt_count(highlights.subscriber_count),
        demographics=highlights.demographics or BLANK,
        metrics_note=note,
        collab_format=(collab_format or "").strip()
        or "a sponsored short-form video featuring your product",
        contact_email=(contact_email or "").strip() or CONTACT_PLACEHOLDER,
    )
    return subject, body.strip()


def create_pitch_draft(
    db: Session,
    *,
    brand_name: str,
    platform: str = "YouTube",
    channel_handle: str = "",
    niche: str = "",
    collab_format: str = "a sponsored short-form video featuring your product",
    contact_email: str = "",
    creator_name: str | None = None,
    subscriber_count: int | None = None,
    demographics: str | None = None,
) -> BrandPitchDraft:
    """Generate a pitch draft from the live metrics store and persist it.

    The draft is stored with status ``draft`` — the only status this feature
    produces. Nothing is sent anywhere.
    """
    settings = get_settings()
    creator = (creator_name or settings.channel_name or "VyralX").strip()
    highlights = highlights_from_metrics(
        db, subscriber_count=subscriber_count, demographics=demographics
    )
    subject, body = render_pitch(
        brand_name=brand_name,
        highlights=highlights,
        creator_name=creator,
        platform=platform,
        channel_handle=channel_handle,
        niche=niche or settings.channel_niche,
        collab_format=collab_format,
        contact_email=contact_email,
    )
    draft = BrandPitchDraft(
        brand_name=(brand_name or "").strip(),
        template_name=TEMPLATE_NAME,
        subject=subject,
        body=body,
        highlights_json=json.dumps(highlights.to_dict()),
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    log.info(
        "Brand pitch draft #%s created for %r (videos_tracked=%s, total_views=%s)",
        draft.id,
        draft.brand_name,
        highlights.video_count,
        highlights.total_views,
    )
    return draft


def list_pitch_drafts(db: Session, *, limit: int = 50) -> list[BrandPitchDraft]:
    """Return stored pitch drafts, newest first."""
    return list(
        db.scalars(
            select(BrandPitchDraft).order_by(BrandPitchDraft.id.desc()).limit(max(1, limit))
        ).all()
    )
