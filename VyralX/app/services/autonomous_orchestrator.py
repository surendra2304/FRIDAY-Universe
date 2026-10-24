"""
app/services/autonomous_orchestrator.py — VyralX Autonomous Channel Orchestrator.

Manages the complete autonomous YouTube channel lifecycle:
1. Content Discovery: Scans trending topics, competitor channels, and viral content
2. Content Planning: Generates weekly content calendars based on trends and performance
3. Script Generation: Creates high-hook scripts using LLM with proven viral patterns
4. Production Pipeline: Coordinates video rendering, captioning, and thumbnail generation
5. Publishing: Manages YouTube upload with resumable checkpoints and quota awareness
6. Analytics: Tracks performance, adapts strategy based on engagement metrics
7. Self-Improvement: Learns from successful videos to improve future content
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.services.discovery import discover_youtube_videos
from app.services.trends import rank_candidates
from app.services.content import generate_content_pack
from app.services.youtube_analytics import fetch_video_metrics
from app.services.youtube import upload_video
from app.services.hooks import generate_viral_hooks
from app.services.drip_scheduler import DripScheduler

logger = logging.getLogger("vyralx.orchestrator")


@dataclass
class ContentIdea:
    """A content idea with topic, angle, and confidence score."""
    topic: str
    angle: str
    confidence: float
    source: str  # "trending", "competitor", "keyword", "analytics"
    estimated_views: int = 0
    estimated_retention: float = 0.5
    competitor_url: str = ""
    keywords: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class ContentPlan:
    """A weekly content plan with scheduled videos."""
    week_start: datetime
    ideas: list[ContentIdea] = field(default_factory=list)
    scheduled_dates: dict[str, datetime] = field(default_factory=dict)
    status: str = "DRAFT"

    def add_idea(self, idea: ContentIdea, publish_date: datetime) -> None:
        self.ideas.append(idea)
        self.scheduled_dates[idea.topic] = publish_date

    def upcoming_videos(self) -> list[tuple[ContentIdea, datetime]]:
        now = datetime.now(timezone.utc)
        upcoming = []
        for idea in self.ideas:
            pub_date = self.scheduled_dates.get(idea.topic)
            if pub_date and pub_date > now:
                upcoming.append((idea, pub_date))
        return sorted(upcoming, key=lambda x: x[1])


@dataclass
class ChannelMetrics:
    """Aggregate channel performance metrics."""
    total_views: int = 0
    total_subscribers: int = 0
    avg_retention: float = 0.0
    avg_ctr: float = 0.0
    top_video_title: str = ""
    top_video_views: int = 0
    engagement_rate: float = 0.0
    upload_frequency: str = ""
    best_publish_time: str = ""
    best_day_of_week: str = ""


class AutonomousChannelOrchestrator:
    """
    Full autonomous YouTube channel management.

    Orchestrates the complete content lifecycle from discovery to publication
    and continuous improvement based on analytics.
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.content_history: list[ContentIdea] = []
        self.performance_history: list[ChannelMetrics] = []
        self.scheduler = DripScheduler()
        self.idea_pool: list[ContentIdea] = []
        self._running = False
        self._stop_event = asyncio.Event()

    async def discover_trends(self, limit: int = 20) -> list[ContentIdea]:
        """Discover trending topics and viral content ideas."""
        logger.info("Discovering trending content ideas...")

        ideas: list[ContentIdea] = []

        # 1. Discover viral videos from configured competitor channels
        try:
            viral_videos = await discover_youtube_videos(
                channels=self.settings.competitor_channels,
                limit=limit * 2,
            )
            for video in viral_videos:
                idea = ContentIdea(
                    topic=video.get("title", "Unknown Topic"),
                    angle=self._extract_angle(video.get("title", "")),
                    confidence=self._estimate_confidence(video),
                    source="competitor",
                    estimated_views=video.get("views", 0),
                    estimated_retention=video.get("retention", 0.5),
                    competitor_url=video.get("url", ""),
                    keywords=self._extract_keywords(video.get("title", "")),
                )
                ideas.append(idea)
        except Exception as e:
            logger.warning(f"Competitor discovery failed: {e}")

        # 2. Rank candidates by viral potential
        try:
            ranked = await rank_candidates(
                keywords=["trending", "viral", "viral content"],
                limit=limit,
            )
            for item in ranked:
                idea = ContentIdea(
                    topic=item.get("title", "Unknown Topic"),
                    angle="Trending angle",
                    confidence=item.get("score", 0.5),
                    source="trending",
                    estimated_views=item.get("estimated_views", 0),
                    keywords=item.get("keywords", []),
                )
                ideas.append(idea)
        except Exception as e:
            logger.warning(f"Trend ranking failed: {e}")

        # 3. Filter and rank ideas
        ideas = self._rank_ideas(ideas)
        self.idea_pool.extend(ideas[:limit])

        logger.info(f"Discovered {len(ideas)} content ideas")
        return ideas[:limit]

    def _extract_angle(self, title: str) -> str:
        """Extract a unique angle from a competitor video title."""
        # Remove common YouTube prefixes
        title = re.sub(r'^(I |We |You |The |A |An |Why |How |What |When |Where |Who |Is |Are |Do |Does |Can |Will |Would |Should) ', '', title)
        title = re.sub(r'(\.|\?|!|:)$', '', title)
        return title[:100] if title else "Unique Angle"

    def _estimate_confidence(self, video: dict) -> float:
        """Estimate confidence based on video performance."""
        views = video.get("views", 0)
        retention = video.get("retention", 0.5)

        # Confidence based on views and retention
        if views > 1000000:
            confidence = 0.95
        elif views > 500000:
            confidence = 0.85
        elif views > 100000:
            confidence = 0.75
        elif views > 50000:
            confidence = 0.65
        else:
            confidence = 0.5

        confidence = confidence * (0.8 + retention * 0.2)
        return min(0.99, max(0.3, confidence))

    def _extract_keywords(self, title: str) -> list[str]:
        """Extract keywords from a title."""
        # Simple keyword extraction
        words = re.findall(r'[a-zA-Z]+', title.lower())
        # Remove common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        return keywords[:10]

    def _rank_ideas(self, ideas: list[ContentIdea]) -> list[ContentIdea]:
        """Rank ideas by confidence and estimated performance."""
        return sorted(
            ideas,
            key=lambda i: (i.confidence, i.estimated_views, i.estimated_retention),
            reverse=True,
        )

    async def generate_weekly_plan(self) -> ContentPlan:
        """Generate a weekly content plan based on discovered ideas."""
        logger.info("Generating weekly content plan...")

        # Discover fresh trends
        ideas = await self.discover_trends(limit=30)

        # Select top ideas for the week
        plan = ContentPlan(week_start=datetime.now(timezone.utc))

        # Schedule 3-5 videos per week
        videos_per_week = 5
        publish_days = [0, 2, 4]  # Monday, Wednesday, Friday (0=Monday)

        for i, idea in enumerate(ideas[:videos_per_week]):
            day_offset = publish_days[i % len(publish_days)]
            publish_date = datetime.now(timezone.utc) + timedelta(days=day_offset + 7)
            plan.add_idea(idea, publish_date)

        plan.status = "PLANNED"
        logger.info(f"Weekly plan generated: {len(plan.ideas)} videos scheduled")
        return plan

    async def produce_video(self, idea: ContentIdea) -> dict[str, Any]:
        """Produce a complete video from a content idea."""
        logger.info(f"Producing video: {idea.topic}")

        # 1. Generate content pack (script, scenes, keywords)
        try:
            content_pack = await generate_content_pack(
                topic=idea.topic,
                angle=idea.angle,
                keywords=idea.keywords,
            )
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            return {"status": "ERROR", "error": str(e)}

        # 2. Generate viral hooks
        try:
            hooks = await generate_viral_hooks(
                topic=idea.topic,
                script=content_pack.get("script", ""),
            )
            content_pack["hooks"] = hooks
        except Exception as e:
            logger.warning(f"Hook generation failed: {e}")

        # 3. Render video
        try:
            rendered_video = await self._render_video(content_pack)
        except Exception as e:
            logger.error(f"Video rendering failed: {e}")
            return {"status": "RENDER_ERROR", "error": str(e)}

        # 4. Upload to YouTube
        try:
            upload_result = await upload_video(
                file_path=rendered_video,
                title=content_pack.get("title", idea.topic),
                description=content_pack.get("description", ""),
                tags=content_pack.get("tags", idea.keywords),
                category_id=content_pack.get("category_id", "24"),
            )
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {"status": "UPLOAD_ERROR", "error": str(e), "video_path": rendered_video}

        # 5. Record performance
        self.content_history.append(idea)

        return {
            "status": "PUBLISHED",
            "video_id": upload_result.get("video_id"),
            "title": content_pack.get("title", idea.topic),
            "url": upload_result.get("url"),
        }

    async def _render_video(self, content_pack: dict) -> Path:
        """Render a video from content pack."""
        # This would use ffmpeg or moviepy to compose the video
        # For now, return a placeholder path
        output_dir = Path(self.settings.output_dir) / "renders"
        output_dir.mkdir(parents=True, exist_ok=True)

        title = content_pack.get("title", "untitled")
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)[:50]
        output_path = output_dir / f"{safe_title}.mp4"

        # In production, this would call ffmpeg with appropriate filters
        # For now, create a placeholder
        logger.info(f"Rendering video: {output_path}")

        return output_path

    async def analyze_performance(self) -> ChannelMetrics:
        """Analyze channel performance and extract insights."""
        logger.info("Analyzing channel performance...")

        metrics = ChannelMetrics()

        try:
            # Fetch recent video metrics
            video_data = await fetch_video_metrics(limit=50)

            if video_data:
                total_views = sum(v.get("views", 0) for v in video_data)
                avg_retention = sum(v.get("retention", 0.5) for v in video_data) / len(video_data)
                avg_ctr = sum(v.get("ctr", 0.05) for v in video_data) / len(video_data)

                # Find top video
                top_video = max(video_data, key=lambda v: v.get("views", 0))

                metrics.total_views = total_views
                metrics.avg_retention = avg_retention
                metrics.avg_ctr = avg_ctr
                metrics.top_video_title = top_video.get("title", "")
                metrics.top_video_views = top_video.get("views", 0)
                metrics.engagement_rate = (
                    (sum(v.get("likes", 0) + v.get("comments", 0) for v in video_data) / total_views)
                    if total_views > 0 else 0
                )

                # Determine best publish time
                publish_times = [v.get("published_at", "") for v in video_data]
                if publish_times:
                    metrics.best_publish_time = self._find_best_publish_time(video_data)

                self.performance_history.append(metrics)
        except Exception as e:
            logger.warning(f"Performance analysis failed: {e}")

        return metrics

    def _find_best_publish_time(self, video_data: list[dict]) -> str:
        """Find the best publish time based on performance."""
        time_performance: dict[str, list[int]] = {}

        for video in video_data:
            published = video.get("published_at", "")
            if published:
                try:
                    dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    hour_key = f"{dt.hour}:00"
                    time_performance.setdefault(hour_key, []).append(video.get("views", 0))
                except Exception:
                    pass

        if time_performance:
            best_hour = max(time_performance, key=lambda h: sum(time_performance[h]) / len(time_performance[h]))
            return best_hour
        return "18:00"

    async def self_improve(self) -> dict[str, Any]:
        """Analyze performance and improve future content strategy."""
        logger.info("Running self-improvement cycle...")

        metrics = await self.analyze_performance()

        insights = {
            "avg_retention": metrics.avg_retention,
            "avg_ctr": metrics.avg_ctr,
            "engagement_rate": metrics.engagement_rate,
            "best_publish_time": metrics.best_publish_time,
            "top_video": metrics.top_video_title,
        }

        # Adjust content strategy based on performance
        if metrics.avg_retention < 0.4:
            insights["action"] = "Shorten videos, improve hooks"
        elif metrics.avg_retention > 0.6:
            insights["action"] = "Maintain current format, test longer videos"

        if metrics.avg_ctr < 0.03:
            insights["action"] = "Improve thumbnails and titles"

        logger.info(f"Self-improvement insights: {insights}")
        return insights

    async def run_autonomous_loop(self) -> None:
        """Run the autonomous channel management loop."""
        self._running = True
        logger.info("Starting autonomous channel orchestrator...")

        while not self._stop_event.is_set():
            try:
                # 1. Generate weekly plan
                plan = await self.generate_weekly_plan()

                # 2. Produce scheduled videos
                for idea, publish_date in plan.upcoming_videos():
                    if publish_date <= datetime.now(timezone.utc):
                        result = await self.produce_video(idea)
                        logger.info(f"Video production result: {result}")

                # 3. Analyze performance
                await self.analyze_performance()

                # 4. Self-improve
                await self.self_improve()

                # 5. Sleep until next cycle (daily)
                await asyncio.sleep(86400)  # 24 hours

            except Exception as e:
                logger.error(f"Autonomous loop error: {e}")
                await asyncio.sleep(300)  # 5 minute retry

    async def stop(self) -> None:
        """Stop the autonomous loop."""
        self._stop_event.set()
        self._running = False
        logger.info("Autonomous channel orchestrator stopped")


# Module-level singleton
autonomous_orchestrator = AutonomousChannelOrchestrator()
