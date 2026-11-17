from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Identity, Integer, String, Text, TypeDecorator
from sqlalchemy.dialects.oracle import TIMESTAMP as OracleTIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC timestamp that survives Oracle.

    Oracle's generic ``DateTime(timezone=True)`` maps to plain ``TIMESTAMP`` and
    drops the offset, so aware values come back naive and every subtraction
    against ``utcnow()`` raises ``TypeError``. On Oracle this uses
    ``TIMESTAMP WITH TIME ZONE``; on every backend reads are normalised to UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "oracle":
            return dialect.type_descriptor(OracleTIMESTAMP(timezone=True))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(String(2048), default="")
    platform: Mapped[str] = mapped_column(String(40), default="manual")
    creator: Mapped[str] = mapped_column(String(300), default="")
    license_name: Mapped[str] = mapped_column(String(200), default="")
    permission_reference: Mapped[str] = mapped_column(String(2048), default="")
    repeat_use_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    repeat_use_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    repeat_use_review_notes: Mapped[str] = mapped_column(Text, default="n/a")
    rights_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), default="discovered")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    file_path: Mapped[str] = mapped_column(String(2048))
    duration_seconds: Mapped[float] = mapped_column(default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    rights_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RenderJob(Base):
    __tablename__ = "render_jobs"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer)
    preset: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    output_path: Mapped[str] = mapped_column(String(2048), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer)
    render_job_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    thumbnail_path: Mapped[str] = mapped_column(String(2048), default="")
    category_id: Mapped[str] = mapped_column(String(8), default="")
    privacy_status: Mapped[str] = mapped_column(String(20), default="private")
    scheduled_at: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(40), default="pending_approval")
    youtube_video_id: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ContentPack(Base):
    __tablename__ = "content_packs"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    topic: Mapped[str] = mapped_column(String(500))
    video_format: Mapped[str] = mapped_column(String(20), default="shorts")
    status: Mapped[str] = mapped_column(String(40), default="generated")
    pack_json: Mapped[str] = mapped_column(Text)
    provider_model: Mapped[str] = mapped_column(String(200), default="")
    voiceover_path: Mapped[str] = mapped_column(String(2048), default="")
    voiceover_status: Mapped[str] = mapped_column(String(40), default="not_generated")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class VideoMetric(Base):
    __tablename__ = "video_metrics"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    publish_job_id: Mapped[int] = mapped_column(Integer, index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(100), index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChannelSnapshot(Base):
    """TASK-VYR-014: point-in-time channel statistics for YPP tracking.

    Written by app.services.ypp_tracker once per autopilot cycle (and on
    demand). ``shorts_views_90d`` is the tracked floor defined there: views
    of PUBLIC uploads made inside the last 90 days. Watch hours are not
    stored — they are not measurable from the Data API and are never
    estimated (see ypp_tracker.compute_ypp_progress).
    """

    __tablename__ = "channel_snapshots"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    channel_title: Mapped[str] = mapped_column(String(200), default="")
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    total_view_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    public_uploads_90d: Mapped[int] = mapped_column(Integer, default=0)
    shorts_views_90d: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class BrandPitchDraft(Base):
    """A generated brand-collaboration pitch draft (IG General B8-C3).

    Drafts only: rows in this table are never sent by any code path. Sending a
    pitch is a separate, owner-approved step that does not exist yet, so the
    only status a draft can hold is ``draft``.
    """

    __tablename__ = "brand_pitch_drafts"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(200))
    template_name: Mapped[str] = mapped_column(String(80), default="brand_collab_pitch_v1")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text)
    highlights_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    authorization_context_json: Mapped[str] = mapped_column(Text, default="{}")
    correlation_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    trace_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    parent_task_id: Mapped[str] = mapped_column(String(120), default="")
    request_id: Mapped[str] = mapped_column(String(120), default="")
    actor: Mapped[str] = mapped_column(String(120), default="operator")
    capability: Mapped[str] = mapped_column(String(120), default="")
    objective: Mapped[str] = mapped_column(String(500), default="")
    trust_level: Mapped[str] = mapped_column(String(40), default="untrusted")
    deadline: Mapped[str] = mapped_column(String(80), default="")
    requested_mode: Mapped[str] = mapped_column(String(20), default="async")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    source_agent: Mapped[str] = mapped_column(String(120), default="friday")
    target_agent: Mapped[str] = mapped_column(String(120), default="vyralx")
    action: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class VideoProject(Base):
    __tablename__ = "video_projects"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    project_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(500))
    auto_discover_trend: Mapped[bool] = mapped_column(Boolean, default=False)
    trend_query: Mapped[str] = mapped_column(String(200), default="")
    trend_max_results: Mapped[int] = mapped_column(Integer, default=10)
    trend_source_video_id: Mapped[str] = mapped_column(String(100), default="")
    trend_source_url: Mapped[str] = mapped_column(String(2048), default="")
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    video_format: Mapped[str] = mapped_column(String(20), default="shorts")
    target_seconds: Mapped[int] = mapped_column(Integer, default=45)
    audience: Mapped[str] = mapped_column(String(200), default="general audience")
    tone: Mapped[str] = mapped_column(String(200), default="clear, energetic and factual")
    scene_count: Mapped[int] = mapped_column(Integer, default=4)
    confirm_pexels_license: Mapped[bool] = mapped_column(Boolean, default=False)
    confirm_pexels_repeat_use: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    use_voiceover: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    content_pack_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str] = mapped_column(String(2048), default="")
    memora_memory_id: Mapped[str] = mapped_column(String(128), default="")
    memora_memory_status: Mapped[str] = mapped_column(String(32), default="disabled")
    asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# Canonical alias for compatibility
Project = VideoProject
