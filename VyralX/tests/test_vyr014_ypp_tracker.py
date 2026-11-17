"""Unit tests for the TASK-VYR-014 YPP eligibility tracker (pure logic)."""
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PublishJob, VideoMetric
from app.services.ypp_tracker import compute_ypp_progress, tracked_public_figures


class TestComputeYppProgress(unittest.TestCase):
    def test_zero_channel_is_nowhere(self):
        progress = compute_ypp_progress(
            subscriber_count=0, public_uploads_90d=0, shorts_views_90d=0
        )
        fan = progress["fan_funding_tier"]
        ad = progress["ad_revenue_tier"]
        self.assertFalse(fan["eligible"])
        self.assertFalse(ad["eligible"])
        self.assertEqual(fan["subscribers"]["target"], 500)
        self.assertEqual(ad["subscribers"]["target"], 1000)
        self.assertEqual(ad["shorts_views_90d"]["target"], 10_000_000)

    def test_watch_hours_path_is_unknown_never_assumed(self):
        progress = compute_ypp_progress(
            subscriber_count=5000, public_uploads_90d=30, shorts_views_90d=10
        )
        fan = progress["fan_funding_tier"]
        # Hours unmeasured: met must be None and the activity path unknown,
        # so eligibility stays False WITHOUT claiming the hours path failed.
        self.assertIsNone(fan["watch_hours_12m"]["met"])
        self.assertIsNone(fan["activity_path_met"])
        self.assertFalse(fan["eligible"])

    def test_fan_funding_via_shorts(self):
        progress = compute_ypp_progress(
            subscriber_count=500, public_uploads_90d=3, shorts_views_90d=3_000_000
        )
        self.assertTrue(progress["fan_funding_tier"]["eligible"])
        self.assertFalse(progress["ad_revenue_tier"]["eligible"])

    def test_ad_tier_via_shorts(self):
        progress = compute_ypp_progress(
            subscriber_count=1000, public_uploads_90d=40, shorts_views_90d=10_000_000
        )
        self.assertTrue(progress["ad_revenue_tier"]["eligible"])

    def test_ad_tier_via_watch_hours_when_measured(self):
        progress = compute_ypp_progress(
            subscriber_count=1000,
            public_uploads_90d=40,
            shorts_views_90d=0,
            watch_hours_12m=4000,
        )
        self.assertTrue(progress["ad_revenue_tier"]["eligible"])

    def test_2027_thresholds_carried(self):
        progress = compute_ypp_progress(
            subscriber_count=0, public_uploads_90d=0, shorts_views_90d=0
        )
        future = progress["ad_tier_from_2027_02_01"]
        self.assertEqual(future["shorts_views_90d"], 20_000_000)
        self.assertEqual(future["watch_hours_12m"], 8_000)


class TestTrackedPublicFigures(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        now = datetime.now(timezone.utc)
        # Public + recent: counts, with views.
        self._job("pub_recent", "public", now - timedelta(days=5), views=1200)
        # Unlisted + recent: excluded entirely (YPP counts public only).
        self._job("unlisted_recent", "unlisted", now - timedelta(days=5), views=9999)
        # Public + old: excluded from the 90d window (floor semantics).
        self._job("pub_old", "public", now - timedelta(days=120), views=5000)

    def tearDown(self):
        self.db.close()

    def _job(self, video_id, privacy, completed_at, *, views):
        job = PublishJob(
            asset_id=1,
            render_job_id=1,
            title=f"t-{video_id}",
            description="",
            tags_json="[]",
            privacy_status=privacy,
            status="uploaded",
            youtube_video_id=video_id,
            completed_at=completed_at,
        )
        self.db.add(job)
        self.db.flush()
        self.db.add(
            VideoMetric(
                publish_job_id=job.id,
                youtube_video_id=video_id,
                view_count=views,
                like_count=0,
                comment_count=0,
            )
        )
        self.db.commit()

    def test_only_public_recent_uploads_count(self):
        figures = tracked_public_figures(self.db, days=90)
        self.assertEqual(figures["public_uploads_90d"], 1)
        self.assertEqual(figures["shorts_views_90d_tracked"], 1200)
        self.assertEqual(figures["tracked_public_uploads_total"], 2)


if __name__ == "__main__":
    unittest.main()
