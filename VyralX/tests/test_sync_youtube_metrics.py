"""Tests for scripts/sync_youtube_metrics.py (the scheduled metrics read-back).

Regression coverage for the production defect found 2026-11-17: the old
``_uploaded_video_ids`` filtered ``youtube_video_id != ""`` — on Oracle an
empty string IS NULL, so the predicate compared against NULL, selected zero
rows, and the timer job printed SKIPPED forever. Also covers the widened id
source: publish jobs merged with the channel's current uploads (videos with
no publish-job row), deduped.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def _ensure_app_imports() -> None:
    """Use the real app modules when importable (CI / full checkout).

    Falls back to minimal stubs so this file can also run against a partial
    tree containing only the script's import chain.
    """
    try:
        import app.config
        import app.database

        if hasattr(app.config, "get_settings") and hasattr(app.database, "Base"):
            return
    except Exception:
        pass
    from sqlalchemy.orm import DeclarativeBase

    class _Base(DeclarativeBase):
        pass

    config_stub = types.ModuleType("app.config")
    config_stub.get_settings = lambda: SimpleNamespace(youtube_data_api_key="test-key")
    database_stub = types.ModuleType("app.database")
    database_stub.Base = _Base
    database_stub.SessionLocal = None
    sys.modules["app.config"] = config_stub
    sys.modules["app.database"] = database_stub


_ensure_app_imports()

from app.models import PublishJob  # noqa: E402

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "sync_youtube_metrics.py"
_spec = importlib.util.spec_from_file_location("sync_youtube_metrics", _SCRIPT_PATH)
sync_metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_metrics)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://")
    PublishJob.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    yield session, engine
    session.close()
    engine.dispose()


def _job(video_id, status="uploaded"):
    return PublishJob(
        asset_id=1,
        render_job_id=1,
        title="t",
        status=status,
        youtube_video_id=video_id,
    )


def test_uploaded_video_ids_excludes_blank_and_non_uploaded(db_session):
    session, _engine = db_session
    session.add_all(
        [
            _job("dQw4w9WgXcQ"),
            _job(""),
            _job("   "),
            _job("shouldNotAppear1", status="failed"),
            _job("shouldNotAppear2", status="pending_approval"),
        ]
    )
    session.commit()

    assert sync_metrics._uploaded_video_ids(session, 200) == ["dQw4w9WgXcQ"]


def test_uploaded_video_ids_newest_first_deduped_and_limited(db_session):
    session, _engine = db_session
    session.add_all([_job("oldVideo123"), _job("dupeVideo12"), _job("dupeVideo12")])
    session.commit()

    assert sync_metrics._uploaded_video_ids(session, 200) == ["dupeVideo12", "oldVideo123"]
    assert sync_metrics._uploaded_video_ids(session, 1) == ["dupeVideo12"]


def test_uploaded_video_ids_query_uses_is_not_null(db_session):
    """The Oracle regression: the emitted SQL must use IS NOT NULL.

    On sqlite the old ``!= ""`` predicate happens to work, so only the
    query shape proves the fix for Oracle, where '' IS NULL and a
    ``!= ''`` comparison can never be true.
    """
    session, engine = db_session
    session.add(_job("dQw4w9WgXcQ"))
    session.commit()

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        assert sync_metrics._uploaded_video_ids(session, 200) == ["dQw4w9WgXcQ"]
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    select_sql = [s for s in statements if "publish_jobs" in s and "youtube_video_id" in s]
    assert select_sql, "expected the publish_jobs id query to be captured"
    assert any("IS NOT NULL" in s.upper() for s in select_sql)


class _Request:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeYouTubeService:
    """Minimal stand-in for the googleapiclient YouTube resource."""

    def __init__(self, pages, channel_items=None):
        self._pages = pages
        self._channel_items = (
            [{"contentDetails": {"relatedPlaylists": {"uploads": "UUuploads"}}}]
            if channel_items is None
            else channel_items
        )
        self.playlist_calls: list[dict] = []

    def channels(self):
        return SimpleNamespace(
            list=lambda **kwargs: _Request({"items": self._channel_items})
        )

    def playlistItems(self):
        return SimpleNamespace(list=self._list_playlist_items)

    def _list_playlist_items(self, **kwargs):
        self.playlist_calls.append(kwargs)
        return _Request(self._pages[len(self.playlist_calls) - 1])


def _playlist_page(video_ids, next_token=None):
    page = {
        "items": [
            {"snippet": {"resourceId": {"videoId": vid}, "title": f"title {vid}"}}
            for vid in video_ids
        ]
    }
    if next_token:
        page["nextPageToken"] = next_token
    return page


def test_channel_upload_ids_paginates_and_dedupes():
    service = _FakeYouTubeService(
        pages=[
            _playlist_page(["chanVideo01", "chanVideo02"], next_token="page2"),
            _playlist_page(["chanVideo02", "chanVideo03"]),
        ]
    )

    ids = sync_metrics._channel_upload_ids(200, service=service)

    assert ids == ["chanVideo01", "chanVideo02", "chanVideo03"]
    assert len(service.playlist_calls) == 2
    assert service.playlist_calls[0]["playlistId"] == "UUuploads"
    assert service.playlist_calls[1]["pageToken"] == "page2"


def test_channel_upload_ids_no_channel_returns_empty():
    service = _FakeYouTubeService(pages=[], channel_items=[])
    assert sync_metrics._channel_upload_ids(200, service=service) == []


def test_sync_video_ids_merges_channel_uploads(db_session, monkeypatch):
    session, _engine = db_session
    session.add_all([_job("jobVideo001"), _job("jobVideo002")])
    session.commit()
    monkeypatch.setattr(
        sync_metrics,
        "_channel_upload_ids",
        lambda limit, service=None: ["jobVideo002", "chanVideo01"],
    )

    assert sync_metrics._sync_video_ids(session, 200) == [
        "jobVideo002",
        "jobVideo001",
        "chanVideo01",
    ]


def test_sync_video_ids_degrades_when_channel_listing_fails(db_session, monkeypatch, capsys):
    session, _engine = db_session
    session.add(_job("jobVideo001"))
    session.commit()

    def _boom(limit, service=None):
        raise RuntimeError("token expired")

    monkeypatch.setattr(sync_metrics, "_channel_upload_ids", _boom)

    assert sync_metrics._sync_video_ids(session, 200) == ["jobVideo001"]
    assert "channel upload listing failed" in capsys.readouterr().out
