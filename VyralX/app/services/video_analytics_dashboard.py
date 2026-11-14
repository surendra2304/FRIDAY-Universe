"""
VyralX/app/services/video_analytics_dashboard.py — VyralX Video Analytics Dashboard Engine.

Comprehensive video performance analytics: view metrics, engagement tracking,
audience demographics, retention analysis, virality scoring, and competitive
benchmarking with real-time dashboards and alerts.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class VideoMetrics:
    """Metrics for a video."""
    video_id: str
    title: str
    views: int = 0
    likes: int = 0
    dislikes: int = 0
    shares: int = 0
    comments: int = 0
    watch_time_hours: float | None = None
    avg_view_duration: float | None = None  # seconds
    engagement_rate: float = 0.0
    retention_rate: float | None = None
    ctr: float | None = None  # click-through rate
    virality_score: float | None = None
    revenue: float = 0.0
    timestamp: float = 0.0
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class AudienceDemographics:
    """Audience demographics for a video."""
    video_id: str
    age_distribution: dict = field(default_factory=dict)  # {age_range: percentage}
    gender_distribution: dict = field(default_factory=dict)
    location_distribution: dict = field(default_factory=dict)
    device_distribution: dict = field(default_factory=dict)
    traffic_sources: dict = field(default_factory=dict)
    unique_viewers: int | None = None
    returning_viewers_pct: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class RetentionCurve:
    """Viewer retention curve."""
    video_id: str
    segments: list[dict] = field(default_factory=list)  # [{timestamp_pct, retention_pct}]
    avg_retention: float | None = None
    drop_off_points: list[float] = field(default_factory=list)
    peak_retention: float | None = None
    last_segment_retention: float | None = None
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class ViralityAnalysis:
    """Virality analysis for a video."""
    video_id: str
    virality_score: float | None = None
    sharing_rate: float = 0.0
    velocity_score: float | None = None
    compound_score: float | None = None
    predicted_views: int | None = None
    days_to_viral: float | None = None
    factors: list[str] = field(default_factory=list)
    data_status: str = "no_data"
    data_note: str = ""


@dataclass
class CompetitiveBenchmark:
    """Competitive benchmarking."""
    video_id: str
    benchmark_group: str = ""
    avg_views_in_group: int | None = None
    avg_engagement_in_group: float | None = None
    avg_retention_in_group: float | None = None
    percentile_rank: float | None = None
    competitive_score: float | None = None
    data_status: str = "no_data"
    data_note: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class PerformanceAlert:
    """A performance alert."""
    alert_id: str
    video_id: str
    alert_type: str  # views_spike, views_drop, engagement_low, retention_drop, virality_high
    severity: str = "medium"
    message: str = ""
    threshold: float = 0.0
    current_value: float = 0.0
    triggered_at: float = 0.0


@dataclass
class DashboardWidget:
    """A dashboard widget."""
    widget_id: str
    widget_type: str  # metric, chart, table, gauge, alert
    title: str
    data: list = field(default_factory=list)
    refresh_rate: int = 60  # seconds
    last_updated: float = 0.0


class VideoAnalyticsDashboard:
    """Video analytics dashboard engine."""

    def __init__(self):
        self._metrics: dict[str, VideoMetrics] = {}
        self._demographics: dict[str, AudienceDemographics] = {}
        self._retention: dict[str, RetentionCurve] = {}
        self._virality: dict[str, ViralityAnalysis] = {}
        self._benchmarks: dict[str, CompetitiveBenchmark] = {}
        self._alerts: list[PerformanceAlert] = []
        self._widgets: dict[str, DashboardWidget] = {}

    def track_video(
        self,
        video_id: str,
        title: str,
        views: int = 0,
        likes: int = 0,
        shares: int = 0,
        comments: int = 0,
    ) -> VideoMetrics:
        """Track video metrics."""
        # views/likes/shares/comments are caller-supplied counts and
        # engagement_rate is computed from them. Everything that would
        # require platform analytics (average view duration, retention,
        # CTR, watch time) stays None, and virality_score — whose formula
        # depended on the invented retention constant — is not computed.
        # (TASK-REL-020: avg_view_duration=180.0, retention_rate=0.55 and
        # ctr=0.15 were previously hardcoded constants presented as this
        # video's measured metrics.)
        metrics = VideoMetrics(
            video_id=video_id,
            title=title,
            views=views,
            likes=likes,
            shares=shares,
            comments=comments,
            avg_view_duration=None,
            engagement_rate=(likes + shares + comments) / max(1, views) * 100,
            retention_rate=None,
            ctr=None,
            virality_score=None,
            watch_time_hours=None,
            timestamp=time.time(),
            data_status="no_data",
            data_note=(
                "views/likes/shares/comments are caller-supplied and "
                "engagement_rate is computed from them; avg_view_duration, "
                "retention_rate, ctr, watch_time and virality_score "
                "require platform analytics and are unavailable."
            ),
        )

        self._metrics[video_id] = metrics
        return metrics

    def analyze_demographics(self, video_id: str) -> AudienceDemographics:
        """Analyze audience demographics."""
        # No demographics data source exists. (TASK-REL-020: all five
        # distributions were previously hardcoded constants served for
        # every video, unique_viewers was views x 0.85, and
        # returning_viewers_pct was a constant 0.25.)
        demographics = AudienceDemographics(
            video_id=video_id,
            age_distribution={},
            gender_distribution={},
            location_distribution={},
            device_distribution={},
            traffic_sources={},
            unique_viewers=None,
            returning_viewers_pct=None,
            data_status="no_data",
            data_note=(
                "Audience demographics are unavailable: no platform "
                "analytics data is connected for this video."
            ),
        )

        self._demographics[video_id] = demographics
        return demographics

    def generate_retention_curve(self, video_id: str) -> RetentionCurve:
        """Retention curve (honest no-data state).

        No per-segment watch data exists for any video. (TASK-REL-020:
        the curve was previously an invented linear decay with md5-hash
        jitter, presented as the video's measured retention.)
        """
        curve = RetentionCurve(
            video_id=video_id,
            segments=[],
            avg_retention=None,
            drop_off_points=[],
            peak_retention=None,
            last_segment_retention=None,
            data_status="no_data",
            data_note=(
                "Retention is unavailable: no per-segment watch data is "
                "connected for this video."
            ),
        )

        self._retention[video_id] = curve
        return curve

    def analyze_virality(self, video_id: str) -> ViralityAnalysis:
        """Analyze video virality."""
        metrics = self._metrics.get(video_id)
        if not metrics:
            raise HTTPException(404, f"Video {video_id} not found")

        # sharing_rate is computed from the tracked (caller-supplied)
        # counts. Everything derived from virality_score is unavailable
        # because virality_score itself cannot be computed without
        # retention data. (TASK-REL-020)
        sharing_rate = metrics.shares / max(1, metrics.views)

        virality = ViralityAnalysis(
            video_id=video_id,
            virality_score=None,
            sharing_rate=sharing_rate,
            velocity_score=None,
            compound_score=None,
            predicted_views=None,
            days_to_viral=None,
            factors=[
                f"Sharing rate: {sharing_rate:.2%}",
                f"Engagement rate: {metrics.engagement_rate:.1f}%",
                "Retention: unavailable (no platform analytics)",
            ],
            data_status="no_data",
            data_note=(
                "virality_score and its derivatives are unavailable: the "
                "score requires retention data, which is not connected. "
                "sharing_rate is computed from the tracked counts."
            ),
        )

        self._virality[video_id] = virality
        return virality

    def benchmark_competitively(self, video_id: str, benchmark_group: str = "") -> CompetitiveBenchmark:
        """Benchmark video against competitors (honest no-data state).

        No competitor/benchmark-group dataset exists. (TASK-REL-020: the
        group averages were previously hardcoded constants — 100000
        views, 4.0 engagement, 0.50 retention — and the percentile and
        competitive score were arithmetic on those constants, presented
        as benchmarking.)
        """
        metrics = self._metrics.get(video_id)
        if not metrics:
            raise HTTPException(404, f"Video {video_id} not found")

        benchmark = CompetitiveBenchmark(
            video_id=video_id,
            benchmark_group=benchmark_group or "general",
            avg_views_in_group=None,
            avg_engagement_in_group=None,
            avg_retention_in_group=None,
            percentile_rank=None,
            competitive_score=None,
            strengths=[],
            weaknesses=[],
            data_status="no_data",
            data_note=(
                "Benchmarking is unavailable: no competitor or "
                "benchmark-group dataset is connected."
            ),
        )

        self._benchmarks[video_id] = benchmark
        return benchmark

    def check_alerts(self, video_id: str) -> list[PerformanceAlert]:
        """Check for performance alerts."""
        metrics = self._metrics.get(video_id)
        if not metrics:
            return []

        alerts = []

        if metrics.views > 1000000:
            alerts.append(PerformanceAlert(
                alert_id=hashlib.md5(f"alert:views:{video_id}:{time.time()}".encode()).hexdigest()[:12],
                video_id=video_id,
                alert_type="views_spike",
                severity="high",
                message=f"Views exceeded 1M ({metrics.views:,})",
                threshold=1000000,
                current_value=metrics.views,
                triggered_at=time.time(),
            ))

        if metrics.engagement_rate < 2.0:
            alerts.append(PerformanceAlert(
                alert_id=hashlib.md5(f"alert:eng:{video_id}:{time.time()}".encode()).hexdigest()[:12],
                video_id=video_id,
                alert_type="engagement_low",
                severity="medium",
                message=f"Engagement rate is low ({metrics.engagement_rate:.1f}%)",
                threshold=2.0,
                current_value=metrics.engagement_rate,
                triggered_at=time.time(),
            ))

        if metrics.virality_score is not None and metrics.virality_score > 40:
            alerts.append(PerformanceAlert(
                alert_id=hashlib.md5(f"alert:viral:{video_id}:{time.time()}".encode()).hexdigest()[:12],
                video_id=video_id,
                alert_type="virality_high",
                severity="high",
                message=f"High virality score ({metrics.virality_score:.1f})",
                threshold=40,
                current_value=metrics.virality_score,
                triggered_at=time.time(),
            ))

        self._alerts.extend(alerts)
        return alerts

    def create_dashboard(self, title: str) -> dict:
        """Create a dashboard."""
        dashboard_id = hashlib.md5(f"dashboard:{title}:{time.time()}".encode()).hexdigest()[:12]

        widgets = [
            DashboardWidget(
                widget_id=f"{dashboard_id}:views",
                widget_type="metric",
                title="Total Views",
                data=[{"value": sum(m.views for m in self._metrics.values()), "label": "views"}],
                refresh_rate=60,
                last_updated=time.time(),
            ),
            DashboardWidget(
                widget_id=f"{dashboard_id}:engagement",
                widget_type="gauge",
                title="Avg Engagement Rate",
                data=[{"value": sum(m.engagement_rate for m in self._metrics.values()) / max(1, len(self._metrics)), "label": "%"}],
                refresh_rate=30,
                last_updated=time.time(),
            ),
            DashboardWidget(
                widget_id=f"{dashboard_id}:alerts",
                widget_type="alert",
                title="Active Alerts",
                data=[{"count": len(self._alerts), "label": "alerts"}],
                refresh_rate=30,
                last_updated=time.time(),
            ),
        ]

        for widget in widgets:
            self._widgets[widget.widget_id] = widget

        return {
            "dashboard_id": dashboard_id,
            "title": title,
            "widgets": len(widgets),
            "created_at": time.time(),
        }

    def get_report(self) -> dict:
        """Get video analytics dashboard report."""
        return {
            "total_videos_tracked": len(self._metrics),
            "total_demographics_analyses": len(self._demographics),
            "total_retention_curves": len(self._retention),
            "total_virality_analyses": len(self._virality),
            "total_benchmarks": len(self._benchmarks),
            "total_alerts": len(self._alerts),
            "total_widgets": len(self._widgets),
            "total_views": sum(m.views for m in self._metrics.values()),
            "avg_engagement": sum(m.engagement_rate for m in self._metrics.values()) / max(1, len(self._metrics)),
            "avg_retention": (
                sum(r.avg_retention for r in self._retention.values() if r.avg_retention is not None)
                / max(1, sum(1 for r in self._retention.values() if r.avg_retention is not None))
                if any(r.avg_retention is not None for r in self._retention.values()) else None
            ),
            "recent_alerts": [
                {
                    "video": a.video_id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                }
                for a in self._alerts[-5:]
            ],
        }


# Module-level singleton
analytics_dashboard = VideoAnalyticsDashboard()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/vyralx/analytics/track")
async def track_video(payload: dict):
    """Track video metrics."""
    metrics = analytics_dashboard.track_video(
        video_id=payload["video_id"],
        title=payload["title"],
        views=payload.get("views", 0),
        likes=payload.get("likes", 0),
        shares=payload.get("shares", 0),
        comments=payload.get("comments", 0),
    )
    return {
        "video_id": metrics.video_id,
        "views": metrics.views,
        "engagement_rate": metrics.engagement_rate,
        "virality_score": metrics.virality_score,
        "data_status": metrics.data_status,
        "data_note": metrics.data_note,
    }


@router.get("/api/v1/vyralx/analytics/{video_id}/demographics")
async def analyze_demographics(video_id: str):
    """Analyze audience demographics."""
    demographics = analytics_dashboard.analyze_demographics(video_id)
    return {
        "video_id": demographics.video_id,
        "age_distribution": demographics.age_distribution,
        "gender_distribution": demographics.gender_distribution,
        "location_distribution": demographics.location_distribution,
        "device_distribution": demographics.device_distribution,
        "traffic_sources": demographics.traffic_sources,
        "unique_viewers": demographics.unique_viewers,
        "data_status": demographics.data_status,
        "data_note": demographics.data_note,
    }


@router.get("/api/v1/vyralx/analytics/{video_id}/retention")
async def generate_retention_curve(video_id: str):
    """Generate retention curve."""
    curve = analytics_dashboard.generate_retention_curve(video_id)
    return {
        "video_id": curve.video_id,
        "avg_retention": curve.avg_retention,
        "peak_retention": curve.peak_retention,
        "last_segment_retention": curve.last_segment_retention,
        "drop_off_points": curve.drop_off_points,
        "segments": curve.segments,
        "data_status": curve.data_status,
        "data_note": curve.data_note,
    }


@router.get("/api/v1/vyralx/analytics/{video_id}/virality")
async def analyze_virality(video_id: str):
    """Analyze virality."""
    virality = analytics_dashboard.analyze_virality(video_id)
    return {
        "video_id": virality.video_id,
        "virality_score": virality.virality_score,
        "sharing_rate": virality.sharing_rate,
        "velocity_score": virality.velocity_score,
        "compound_score": virality.compound_score,
        "predicted_views": virality.predicted_views,
        "days_to_viral": virality.days_to_viral,
        "factors": virality.factors,
        "data_status": virality.data_status,
        "data_note": virality.data_note,
    }


@router.get("/api/v1/vyralx/analytics/{video_id}/benchmark")
async def benchmark_competitively(video_id: str, benchmark_group: str = ""):
    """Benchmark competitively."""
    benchmark = analytics_dashboard.benchmark_competitively(video_id, benchmark_group)
    return {
        "video_id": benchmark.video_id,
        "percentile_rank": benchmark.percentile_rank,
        "competitive_score": benchmark.competitive_score,
        "strengths": benchmark.strengths,
        "weaknesses": benchmark.weaknesses,
        "data_status": benchmark.data_status,
        "data_note": benchmark.data_note,
    }


@router.get("/api/v1/vyralx/analytics/{video_id}/alerts")
async def check_alerts(video_id: str):
    """Check for performance alerts."""
    alerts = analytics_dashboard.check_alerts(video_id)
    return {
        "video_id": video_id,
        "alerts": [
            {"type": a.alert_type, "severity": a.severity, "message": a.message}
            for a in alerts
        ],
        "total_alerts": len(alerts),
    }


@router.post("/api/v1/vyralx/analytics/dashboard")
async def create_dashboard(payload: dict):
    """Create a dashboard."""
    dashboard = analytics_dashboard.create_dashboard(title=payload["title"])
    return {"dashboard_id": dashboard["dashboard_id"], "widgets": dashboard["widgets"]}


@router.get("/api/v1/vyralx/analytics/report")
async def get_report():
    """Get video analytics dashboard report."""
    return analytics_dashboard.get_report()
