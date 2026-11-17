"""Tests for the B8-C3 brand-deal pitch drafts (app.services.brand_pitch).

The guarantees under test are the packet's honesty contract:
- every figure in a draft comes from the real ``video_metrics`` store;
- a metric with no stored value renders as a visible blank, never a number;
- drafts are persisted with status ``draft`` and nothing else;
- the module contains no send path at all (no mail/DM/network sending code).
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BrandPitchDraft, VideoMetric
from app.services import brand_pitch
from app.services.brand_pitch import (
    BLANK,
    CONTACT_PLACEHOLDER,
    PITCH_TEMPLATE,
    TEMPLATE_SLOTS,
    create_pitch_draft,
    highlights_from_metrics,
    list_pitch_drafts,
    render_pitch,
)

FETCHED = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _metric(video_id: str, views: int, likes: int, comments: int, fetched_at=FETCHED):
    return VideoMetric(
        publish_job_id=0,
        youtube_video_id=video_id,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        fetched_at=fetched_at,
    )


@pytest.fixture()
def stocked_db(db):
    # Fixture figures only: totals 6,000 views / 180 likes / 18 comments.
    db.add_all([
        _metric("fixtureVidA", 1000, 100, 10),
        _metric("fixtureVidB", 2000, 50, 5),
        _metric("fixtureVidC", 3000, 30, 3),
    ])
    db.commit()
    return db


def test_highlights_come_from_the_metrics_store(stocked_db):
    highlights = highlights_from_metrics(stocked_db)
    assert highlights.video_count == 3
    assert highlights.total_views == 6000
    assert highlights.total_likes == 180
    assert highlights.total_comments == 18
    assert highlights.avg_views_per_video == 2000
    # (180 likes + 18 comments) / 6000 views = 3.3%
    assert highlights.engagement_rate_pct == 3.3
    assert highlights.metrics_fetched_at == FETCHED
    # Not held in the metrics store -> absent, not estimated.
    assert highlights.subscriber_count is None
    assert highlights.demographics is None


def test_duplicate_metric_rows_keep_the_freshest_fetch(db):
    older = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    db.add_all([
        _metric("fixtureVidA", 10, 1, 0, fetched_at=older),
        _metric("fixtureVidA", 999, 9, 1, fetched_at=FETCHED),
    ])
    db.commit()
    highlights = highlights_from_metrics(db)
    assert highlights.video_count == 1
    assert highlights.total_views == 999


def test_filled_draft_quotes_only_stored_figures(stocked_db):
    draft = create_pitch_draft(stocked_db, brand_name="Fixture Brand")
    assert "6,000" in draft.body
    assert "2,000" in draft.body
    assert "180" in draft.body
    assert "3.30%" in draft.body
    assert "Videos tracked: 3" in draft.body
    # Subscribers were never supplied and are not in the store: blank.
    assert f"Subscribers: {BLANK}" in draft.body
    assert f"Audience demographics: {BLANK}" in draft.body
    # No invented reach figures from the legacy media-kit generator.
    assert "500,000" not in draft.body
    assert "vyralx.media" not in draft.body


def test_supplied_subscriber_count_and_demographics_render(stocked_db):
    _, body = render_pitch(
        brand_name="Fixture Brand",
        highlights=highlights_from_metrics(
            stocked_db, subscriber_count=123, demographics="fixture demographics"
        ),
        creator_name="VyralX",
    )
    assert "Subscribers: 123" in body
    assert "Audience demographics: fixture demographics" in body


def test_missing_metrics_render_visible_blanks(db):
    highlights = highlights_from_metrics(db)
    assert highlights.video_count == 0
    assert highlights.total_views is None
    subject, body = render_pitch(
        brand_name="Fixture Brand", highlights=highlights, creator_name="VyralX"
    )
    assert subject
    assert "Videos tracked: 0" in body
    assert f"Total views: {BLANK}" in body
    assert f"Average views per video: {BLANK}" in body
    assert f"Total likes: {BLANK}" in body
    assert f"Engagement rate: {BLANK}" in body
    assert f"Subscribers: {BLANK}" in body
    assert "have not been synced yet" in body
    assert CONTACT_PLACEHOLDER in body


def test_measured_zero_is_not_rendered_as_blank(db):
    db.add(_metric("fixtureVidZ", 0, 0, 0))
    db.commit()
    highlights = highlights_from_metrics(db)
    assert highlights.total_views == 0
    assert highlights.avg_views_per_video == 0
    # Engagement is undefined at zero views, so that one slot stays blank.
    assert highlights.engagement_rate_pct is None
    _, body = render_pitch(
        brand_name="Fixture Brand", highlights=highlights, creator_name="VyralX"
    )
    assert "Total views: 0" in body
    assert f"Engagement rate: {BLANK}" in body


def test_draft_is_persisted_with_draft_status_only(stocked_db):
    draft = create_pitch_draft(stocked_db, brand_name="Fixture Brand")
    assert draft.id is not None
    assert draft.status == "draft"
    assert draft.template_name == "brand_collab_pitch_v1"
    stored = stocked_db.get(BrandPitchDraft, draft.id)
    assert stored is not None
    assert stored.body == draft.body
    highlights = json.loads(stored.highlights_json)
    assert highlights["source"] == "video_metrics"
    assert highlights["total_views"] == 6000
    assert list_pitch_drafts(stocked_db)[0].id == draft.id


def test_brand_name_is_required(stocked_db):
    with pytest.raises(ValueError):
        create_pitch_draft(stocked_db, brand_name="  ")


def test_template_slots_match_the_declared_set():
    import string

    fields = {
        field
        for _, field, _, _ in string.Formatter().parse(PITCH_TEMPLATE)
        if field is not None
    }
    assert fields == TEMPLATE_SLOTS


def test_render_leaves_no_unfilled_slots(stocked_db):
    _, body = render_pitch(
        brand_name="Fixture Brand",
        highlights=highlights_from_metrics(stocked_db),
        creator_name="VyralX",
    )
    assert "{" not in body and "}" not in body


def test_module_has_no_send_path():
    source_path = Path(brand_pitch.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    allowed_imports = {
        "__future__",
        "json",
        "logging",
        "dataclasses",
        "datetime",
        "typing",
        "sqlalchemy",
        "sqlalchemy.orm",
        "app.config",
        "app.models",
        "app.services.youtube_analytics",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= allowed_imports, f"unexpected imports: {imported - allowed_imports}"

    defined_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    assert all("send" not in name.lower() for name in defined_names)

    lowered = source.lower()
    for forbidden in ("smtplib", "sendmail", "partnerships@vyralx.media", "vyralx.media"):
        assert forbidden not in lowered
