"""Growth-wiring tests: thumbnails reach YouTube, tags/category are derived
from the clip, and the analytics summary surfaces top/bottom performers."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import PublishJob, VideoMetric
from app.services import youtube as yt
from app.services.source_analysis import SpeechReport
from app.services.viral_remix import build_metadata
from app.worker import _apply_job_thumbnail
import app.worker as worker


def _candidate(**overrides):
    base = dict(
        title="Goalkeeper forgot how gravity works",
        channel="PitchSide Clips",
        video_id="srcVideo123",
        tags=["goalkeeper fails", "Soccer Highlights", "#epic save"],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_SPEECH = SpeechReport(has_speech=True, speech_seconds=12.0, cues=(), text="crowd noise")


def test_build_metadata_sports_tags_are_content_derived():
    meta = build_metadata(_candidate(), _SPEECH, "wait for it", "SPORTS", editorial={})
    tags = meta["tags"]
    lowered = [t.casefold() for t in tags]
    # The old static list stamped comedy tags on every clip, sports included.
    assert "comedy" not in lowered
    assert "sports" in lowered
    # The source video's own proven tags are carried over (cleaned).
    assert "goalkeeper fails" in lowered
    assert "soccer highlights" in lowered
    assert "epic save" in lowered
    assert len(tags) <= 15
    assert sum(len(t) for t in tags) <= 450


def test_build_metadata_category_mapping():
    assert build_metadata(_candidate(), _SPEECH, "h", "COMEDY", editorial={})["category_id"] == "23"
    assert build_metadata(_candidate(), _SPEECH, "h", "SPORTS", editorial={})["category_id"] == "17"
    assert build_metadata(_candidate(), _SPEECH, "h", "VIRAL", editorial={})["category_id"] == "24"
    comedy_tags = build_metadata(_candidate(), _SPEECH, "h", "COMEDY", editorial={})["tags"]
    assert "comedy" in [t.casefold() for t in comedy_tags]


def test_set_thumbnail_calls_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff" + b"x" * 100)
    service = MagicMock()
    monkeypatch.setattr(yt, "youtube_service", lambda: service)
    assert yt.set_thumbnail("dQw4w9WgXcQ", str(thumb)) is True
    kwargs = service.thumbnails().set.call_args.kwargs
    assert kwargs["videoId"] == "dQw4w9WgXcQ"
    assert kwargs["media_body"] is not None


def test_set_thumbnail_rejects_bad_inputs(tmp_path: Path):
    with pytest.raises(ValueError):
        yt.set_thumbnail("bad id!", str(tmp_path / "nope.jpg"))
    with pytest.raises(FileNotFoundError):
        yt.set_thumbnail("dQw4w9WgXcQ", str(tmp_path / "nope.jpg"))


def test_apply_job_thumbnail_success_and_skip(monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr(worker, "set_thumbnail", lambda vid, path: calls.append((vid, path)) or True)
    job = SimpleNamespace(id=7, thumbnail_path="/renders/x-thumb.jpg")
    assert _apply_job_thumbnail(job, "dQw4w9WgXcQ") is True
    assert calls == [("dQw4w9WgXcQ", "/renders/x-thumb.jpg")]
    # No thumbnail on the job -> no API call, no error.
    assert _apply_job_thumbnail(SimpleNamespace(id=8, thumbnail_path=""), "dQw4w9WgXcQ") is False
    assert len(calls) == 1


def test_apply_job_thumbnail_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch):
    def boom(vid, path):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(worker, "set_thumbnail", boom)
    job = SimpleNamespace(id=9, thumbnail_path="/renders/x-thumb.jpg")
    assert _apply_job_thumbnail(job, "dQw4w9WgXcQ") is False


def test_analytics_summary_surfaces_top_and_bottom():
    settings = get_settings()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.api_key}"}
    with SessionLocal() as db:
        db.add(PublishJob(
            asset_id=0, render_job_id=0, title="Growth Blockbuster",
            youtube_video_id="growthTop001", status="uploaded",
        ))
        db.add(VideoMetric(
            publish_job_id=0, youtube_video_id="growthTop001",
            view_count=10**9, like_count=10**6, comment_count=10**5,
        ))
        db.add(VideoMetric(
            publish_job_id=0, youtube_video_id="growthLow001",
            view_count=3, like_count=0, comment_count=0,
        ))
        db.commit()

    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["top_performers"][0]["youtube_video_id"] == "growthTop001"
    assert data["top_performers"][0]["title"] == "Growth Blockbuster"
    assert data["top_performers"][0]["performance_tier"] == "breakout"
    if data["bottom_performers"]:
        assert data["bottom_performers"][-1]["view_count"] <= data["top_performers"][0]["view_count"]
