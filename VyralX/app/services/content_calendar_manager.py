"""
VyralX/app/services/content_calendar_manager.py — VyralX Content Calendar Manager.

Manages content calendars: post scheduling, content pipeline tracking,
cross-platform distribution, calendar optimization, and content performance
forecasting across platforms.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ContentCalendar:
    """A content calendar."""
    calendar_id: str
    name: str
    platforms: list[str] = field(default_factory=lambda: ["youtube", "tiktok", "instagram"])
    timezone: str = "UTC"
    auto_schedule: bool = True
    created_at: float = 0.0


@dataclass
class ScheduledPost:
    """A scheduled post."""
    post_id: str
    calendar_id: str
    title: str
    content_type: str = "video"  # video, short, reel, story, carousel
    platform: str = "youtube"
    scheduled_at: float = 0.0
    status: str = "draft"  # draft, scheduled, published, archived
    description: str = ""
    tags: list[str] = field(default_factory=list)
    target_audience: str = ""
    estimated_reach: int | None = None
    estimated_engagement: float | None = None
    data_status: str = "no_data"
    data_note: str = ""
    created_at: float = 0.0


@dataclass
class ContentPipeline:
    """Content pipeline tracking."""
    pipeline_id: str
    calendar_id: str
    stages: dict = field(default_factory=dict)  # {ideation, scripting, production, editing, review, scheduled, published}
    total_items: int = 0
    in_progress: int = 0
    completed: int = 0
    average_cycle_time_hours: float | None = None
    data_status: str = "measured"
    data_note: str = ""


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""
    platform: str
    optimal_posting_times: list[str] = field(default_factory=lambda: ["09:00", "12:00", "18:00"])
    optimal_frequency: str = "daily"  # hourly, daily, weekly
    content_length_seconds: int = 60
    format_specs: dict = field(default_factory=dict)
    audience_peak: str = "18-25"


@dataclass
class ScheduleOptimization:
    """Schedule optimization result."""
    calendar_id: str
    optimized_schedule: list[dict] = field(default_factory=list)
    estimated_reach_increase: float | None = None
    estimated_engagement_increase: float | None = None
    confidence: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class PerformanceForecast:
    """Performance forecast for a post."""
    post_id: str
    platform: str
    estimated_views: int | None = None
    estimated_likes: int | None = None
    estimated_shares: int | None = None
    estimated_comments: int | None = None
    estimated_watch_time_hours: float | None = None
    forecast_confidence: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class DistributionPlan:
    """Cross-platform distribution plan."""
    plan_id: str
    post_id: str
    target_platforms: list[str] = field(default_factory=list)
    distribution_schedule: list[dict] = field(default_factory=list)
    estimated_total_reach: int | None = None
    estimated_total_engagement: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


class ContentCalendarManager:
    """Content calendar management engine."""

    def __init__(self):
        self._calendars: dict[str, ContentCalendar] = {}
        self._posts: dict[str, ScheduledPost] = {}
        self._pipelines: dict[str, ContentPipeline] = {}
        self._platform_configs: dict[str, PlatformConfig] = {}
        self._optimizations: list[ScheduleOptimization] = []
        self._forecasts: list[PerformanceForecast] = []
        self._distribution_plans: dict[str, DistributionPlan] = {}

        self._register_platforms()

    def _register_platforms(self):
        """Register platform configurations."""
        platforms = {
            "youtube": PlatformConfig(
                platform="youtube",
                optimal_posting_times=["15:00", "18:00", "20:00"],
                optimal_frequency="daily",
                content_length_seconds=600,
                format_specs={"resolution": "1080p", "codec": "h264"},
                audience_peak="25-34",
            ),
            "tiktok": PlatformConfig(
                platform="tiktok",
                optimal_posting_times=["12:00", "18:00", "21:00"],
                optimal_frequency="daily",
                content_length_seconds=30,
                format_specs={"resolution": "1080p", "codec": "h265"},
                audience_peak="18-24",
            ),
            "instagram": PlatformConfig(
                platform="instagram",
                optimal_posting_times=["11:00", "19:00"],
                optimal_frequency="daily",
                content_length_seconds=60,
                format_specs={"resolution": "1080x1080", "format": "square"},
                audience_peak="25-34",
            ),
            "x": PlatformConfig(
                platform="x",
                optimal_posting_times=["09:00", "12:00", "17:00"],
                optimal_frequency="multiple_daily",
                content_length_seconds=45,
                format_specs={"resolution": "1200x675", "format": "image"},
                audience_peak="25-44",
            ),
        }
        self._platform_configs = platforms

    def create_calendar(self, name: str, platforms: list[str] | None = None) -> ContentCalendar:
        """Create a content calendar."""
        calendar = ContentCalendar(
            calendar_id=hashlib.md5(
                f"calendar:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            platforms=platforms or ["youtube", "tiktok", "instagram"],
            created_at=time.time(),
        )
        self._calendars[calendar.calendar_id] = calendar
        return calendar

    def schedule_post(
        self,
        calendar_id: str,
        title: str,
        platform: str = "youtube",
        content_type: str = "video",
        scheduled_at: float | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> ScheduledPost:
        """Schedule a post."""
        calendar = self._calendars.get(calendar_id)
        if not calendar:
            raise HTTPException(404, f"Calendar {calendar_id} not found")

        post = ScheduledPost(
            post_id=hashlib.md5(
                f"post:{calendar_id}:{title[:30]}:{time.time()}".encode()
            ).hexdigest()[:12],
            calendar_id=calendar_id,
            title=title,
            content_type=content_type,
            platform=platform,
            scheduled_at=scheduled_at or (time.time() + 86400),
            status="scheduled",
            description=description,
            tags=tags or [],
            # No audience/reach data source exists for a scheduled post.
            # (TASK-REL-020: previously derived from md5 hashes of the
            # title/platform.)
            estimated_reach=None,
            estimated_engagement=None,
            data_status="no_data",
            data_note=(
                "Reach/engagement cannot be estimated: no channel "
                "analytics data is connected."
            ),
            created_at=time.time(),
        )

        self._posts[post.post_id] = post
        return post

    def create_pipeline(self, calendar_id: str) -> ContentPipeline:
        """Create a content pipeline snapshot from the calendar's posts.

        Stage counts are computed from the posts actually stored for this
        calendar. (TASK-REL-020: stages were previously hardcoded counts
        presented as live pipeline tracking, and average_cycle_time_hours
        was a constant 48.0; no stage-transition timestamps exist, so
        cycle time stays None.)
        """
        posts = [p for p in self._posts.values() if p.calendar_id == calendar_id]
        by_status: dict[str, int] = {}
        for post in posts:
            by_status[post.status] = by_status.get(post.status, 0) + 1

        pipeline = ContentPipeline(
            pipeline_id=hashlib.md5(
                f"pipeline:{calendar_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            calendar_id=calendar_id,
            stages={
                "draft": by_status.get("draft", 0),
                "scheduled": by_status.get("scheduled", 0),
                "published": by_status.get("published", 0),
                "archived": by_status.get("archived", 0),
            },
            total_items=len(posts),
            in_progress=by_status.get("draft", 0) + by_status.get("scheduled", 0),
            completed=by_status.get("published", 0),
            average_cycle_time_hours=None,
            data_status="measured",
            data_note=(
                "Stage counts are the calendar's stored posts grouped by "
                "status; production stages (ideation/scripting/production/"
                "editing/review) are not tracked, and cycle time is "
                "unavailable (no stage-transition timestamps)."
            ),
        )

        self._pipelines[pipeline.pipeline_id] = pipeline
        return pipeline

    def optimize_schedule(self, calendar_id: str) -> ScheduleOptimization:
        """Optimize posting schedule."""
        calendar = self._calendars.get(calendar_id)
        if not calendar:
            raise HTTPException(404, f"Calendar {calendar_id} not found")

        optimized = ScheduleOptimization(calendar_id=calendar_id)

        for platform in calendar.platforms:
            config = self._platform_configs.get(platform)
            if config:
                optimized.optimized_schedule.append({
                    "platform": platform,
                    "optimal_times": config.optimal_posting_times,
                    "frequency": config.optimal_frequency,
                })

        # The optimized times come from the static platform configs, but
        # no performance data exists to quantify their effect.
        # (TASK-REL-020: increases/confidence were previously derived
        # from md5 hashes of the calendar id.)
        optimized.estimated_reach_increase = None
        optimized.estimated_engagement_increase = None
        optimized.confidence = None
        optimized.data_status = "no_data"
        optimized.data_note = (
            "Suggested times come from static platform configuration; "
            "their reach/engagement effect cannot be quantified without "
            "measured posting history."
        )

        self._optimizations.append(optimized)
        return optimized

    def forecast_performance(self, post_id: str) -> PerformanceForecast:
        """Forecast post performance."""
        post = self._posts.get(post_id)
        if not post:
            raise HTTPException(404, f"Post {post_id} not found")

        # No measured performance history exists for this channel, so no
        # honest forecast can be produced. (TASK-REL-020: previously the
        # base view count was derived from an md5 hash of the post title
        # and likes/shares/comments were fixed ratios of it.)
        forecast = PerformanceForecast(
            post_id=post_id,
            platform=post.platform,
            estimated_views=None,
            estimated_likes=None,
            estimated_shares=None,
            estimated_comments=None,
            estimated_watch_time_hours=None,
            forecast_confidence=None,
            data_status="no_data",
            data_note=(
                "Performance cannot be forecast: no measured channel "
                "history is connected for this post."
            ),
        )

        self._forecasts.append(forecast)
        return forecast

    def create_distribution_plan(
        self,
        post_id: str,
        target_platforms: list[str] | None = None,
    ) -> DistributionPlan:
        """Create a cross-platform distribution plan."""
        post = self._posts.get(post_id)
        if not post:
            raise HTTPException(404, f"Post {post_id} not found")

        platforms = target_platforms or ["youtube", "tiktok", "instagram"]

        plan = DistributionPlan(
            plan_id=hashlib.md5(
                f"distribution:{post_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            post_id=post_id,
            target_platforms=platforms,
            distribution_schedule=[
                {
                    "platform": p,
                    "scheduled_at": time.time() + (i + 1) * 3600,
                    "optimal_time": self._platform_configs[p].optimal_posting_times[0] if p in self._platform_configs else "12:00",
                }
                for i, p in enumerate(platforms)
            ],
            # No reach data source exists per platform. (TASK-REL-020:
            # previously summed md5-hash figures per platform, and the
            # engagement figure was a constant formula.)
            estimated_total_reach=None,
            estimated_total_engagement=None,
            data_status="no_data",
            data_note=(
                "Total reach/engagement cannot be estimated: no platform "
                "analytics data is connected."
            ),
        )

        self._distribution_plans[plan.plan_id] = plan
        return plan

    def get_report(self) -> dict:
        """Get content calendar report."""
        return {
            "total_calendars": len(self._calendars),
            "total_posts": len(self._posts),
            "total_pipelines": len(self._pipelines),
            "total_optimizations": len(self._optimizations),
            "total_forecasts": len(self._forecasts),
            "total_distribution_plans": len(self._distribution_plans),
            "published_posts": sum(1 for p in self._posts.values() if p.status == "published"),
            "scheduled_posts": sum(1 for p in self._posts.values() if p.status == "scheduled"),
            "draft_posts": sum(1 for p in self._posts.values() if p.status == "draft"),
            "platforms_supported": list(self._platform_configs.keys()),
            "recent_posts": [
                {
                    "title": p.title[:50],
                    "platform": p.platform,
                    "status": p.status,
                    "estimated_reach": p.estimated_reach,
                    "scheduled_at": p.scheduled_at,
                }
                for p in list(self._posts.values())[-10:]
            ],
            "pipeline_summary": [
                {
                    "calendar": p.calendar_id,
                    "total_items": p.total_items,
                    "in_progress": p.in_progress,
                    "completed": p.completed,
                }
                for p in self._pipelines.values()
            ],
        }


# Module-level singleton
calendar_manager = ContentCalendarManager()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/vyralx/calendar/calendars")
async def create_calendar(payload: dict):
    """Create a content calendar."""
    calendar = calendar_manager.create_calendar(
        name=payload["name"],
        platforms=payload.get("platforms", []),
    )
    return {"calendar_id": calendar.calendar_id, "name": calendar.name}


@router.post("/api/v1/vyralx/calendar/calendars/{calendar_id}/posts")
async def schedule_post(calendar_id: str, payload: dict):
    """Schedule a post."""
    post = calendar_manager.schedule_post(
        calendar_id=calendar_id,
        title=payload["title"],
        platform=payload.get("platform", "youtube"),
        content_type=payload.get("content_type", "video"),
        scheduled_at=payload.get("scheduled_at"),
        description=payload.get("description", ""),
        tags=payload.get("tags", []),
    )
    return {"post_id": post.post_id, "title": post.title, "status": post.status}


@router.post("/api/v1/vyralx/calendar/calendars/{calendar_id}/optimize")
async def optimize_schedule(calendar_id: str):
    """Optimize posting schedule."""
    result = calendar_manager.optimize_schedule(calendar_id)
    return {
        "calendar_id": result.calendar_id,
        "reach_increase": result.estimated_reach_increase,
        "engagement_increase": result.estimated_engagement_increase,
        "confidence": result.confidence,
        "optimized_schedule": result.optimized_schedule,
        "data_status": result.data_status,
        "data_note": result.data_note,
    }


@router.get("/api/v1/vyralx/calendar/posts/{post_id}/forecast")
async def forecast_performance(post_id: str):
    """Forecast post performance."""
    forecast = calendar_manager.forecast_performance(post_id)
    return {
        "estimated_views": forecast.estimated_views,
        "estimated_likes": forecast.estimated_likes,
        "estimated_shares": forecast.estimated_shares,
        "confidence": forecast.forecast_confidence,
        "data_status": forecast.data_status,
        "data_note": forecast.data_note,
    }


@router.post("/api/v1/vyralx/calendar/posts/{post_id}/distribute")
async def create_distribution_plan(post_id: str, payload: dict):
    """Create distribution plan."""
    plan = calendar_manager.create_distribution_plan(
        post_id=post_id,
        target_platforms=payload.get("platforms", []),
    )
    return {
        "plan_id": plan.plan_id,
        "platforms": plan.target_platforms,
        "estimated_reach": plan.estimated_total_reach,
        "data_status": plan.data_status,
        "data_note": plan.data_note,
    }


@router.get("/api/v1/vyralx/calendar/report")
async def get_report():
    """Get content calendar report."""
    return calendar_manager.get_report()
