#!/usr/bin/env python3
"""Scheduled YouTube performance read-back for VyralX.

Fetches public view/like/comment counters for every video VyralX has
uploaded (YouTube Data API v3), stores the fresh snapshot in the
``video_metrics`` table via
``app.services.youtube_analytics.sync_video_metrics_batch`` and prints the
channel's current top and bottom performers — the feedback signal the
production loop previously never collected on its own.

    python scripts/sync_youtube_metrics.py             # sync + report
    python scripts/sync_youtube_metrics.py --limit 50  # newest 50 uploads

Requires YOUTUBE_DATA_API_KEY. When the key is not configured the script
exits 0 with a SKIPPED line, so a scheduler never mistakes a missing key
for a crash. Safe to run on a timer next to the autopilot.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PublishJob, VideoMetric  # noqa: E402
from app.services.youtube_analytics import (  # noqa: E402
    calculate_engagement_rate,
    classify_performance_tier,
    sync_video_metrics_batch,
)


def _uploaded_video_ids(db, limit: int) -> list[str]:
    ids = db.scalars(
        select(PublishJob.youtube_video_id)
        .where(PublishJob.status == "uploaded", PublishJob.youtube_video_id != "")
        .order_by(PublishJob.id.desc())
        .limit(limit)
    ).all()
    return list(dict.fromkeys(str(v) for v in ids if v))


def _report(db) -> None:
    metrics = db.scalars(
        select(VideoMetric).order_by(VideoMetric.view_count.desc()).limit(100)
    ).all()
    if not metrics:
        print("REPORT: no video metrics stored yet")
        return
    titles = {
        job.youtube_video_id: job.title
        for job in db.scalars(
            select(PublishJob).where(
                PublishJob.youtube_video_id.in_([m.youtube_video_id for m in metrics])
            )
        ).all()
    }

    def _line(m: VideoMetric) -> str:
        rate = calculate_engagement_rate(m.view_count, m.like_count, m.comment_count)
        tier = classify_performance_tier(m.view_count, m.like_count, m.comment_count)
        title = (titles.get(m.youtube_video_id) or "")[:60]
        return (
            f"  {m.youtube_video_id}  views={m.view_count:,} likes={m.like_count:,} "
            f"comments={m.comment_count:,} engagement={rate}% tier={tier}  {title}"
        )

    print(f"REPORT: {len(metrics)} videos tracked")
    print("TOP PERFORMERS:")
    for m in metrics[:5]:
        print(_line(m))
    print("BOTTOM PERFORMERS:")
    for m in reversed(metrics[5:][-5:]):
        print(_line(m))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200,
                        help="max newest uploaded jobs to sync (default 200)")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.youtube_data_api_key:
        print("SKIPPED: YOUTUBE_DATA_API_KEY is not configured; no metrics fetched")
        return 0

    with SessionLocal() as db:
        video_ids = _uploaded_video_ids(db, max(1, args.limit))
        if not video_ids:
            print("SKIPPED: no uploaded publish jobs with a YouTube video id")
            return 0
        try:
            result = sync_video_metrics_batch(db, video_ids)
        except RuntimeError as exc:
            print(f"FAILED: {exc}")
            return 1
        print(f"SYNCED: {result.get('synced_count', 0)} videos")
        _report(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
