"""TASK-VYR-058: Reddit sourcing adapter for the discovery pipeline.

Behaviour pinned here:

* a subreddit listing's link posts to YouTube videos become
  ``Candidate`` objects through the SAME gates as the YouTube paths
  (duration window, minimum views, comedy lane, licence policy,
  dedup) — and carry their Reddit provenance with them;
* self posts, stickied posts, NSFW posts (by default) and links to
  anywhere but YouTube are counted as skipped, never fabricated
  into candidates;
* a listing fetch failure is loud (``RuntimeError`` propagates);
  a video whose metadata cannot be resolved is skipped with reason
  ``metadata_unavailable`` — views/duration/score are never invented;
* ``reuse_licensed`` policy refuses the pool (no licence proof in a
  listing), and an unconfigured pool makes no network call at all;
* the viral loop merges the Reddit pool into the same ranked pool
  as the trending/API lanes, deduplicated by video id.

Fully offline: the listing fetcher and the metadata resolver are
injected fakes. No network, no Reddit account, no YouTube key.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import PublishJob
from app.services import reddit_discovery as rd
from app.services import viral_loop
from app.services.viral_discovery import Candidate


# --------------------------------------------------------------------------- #
# Fixtures / fakes
# --------------------------------------------------------------------------- #
def _post(pid, **kw):
    base = {
        "id": pid, "subreddit": "Unexpected", "author": "someone",
        "title": f"Post {pid}",
        # External link: the adapter reads this, not the permalink.
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "selftext": "", "score": 100, "num_comments": 10,
        "permalink": f"/r/Unexpected/comments/{pid}/x/",
        "created_utc": 1700000000.0, "stickied": False,
        "over_18": False, "is_self": False,
    }
    base.update(kw)
    return base


def _listing(*posts):
    return {"data": {"children": [{"data": p} for p in posts]}}


def _settings(**overrides):
    return SimpleNamespace(
        viral_min_source_views=500_000,
        viral_min_source_seconds=10.0,
        viral_source_policy="transformative",
    )


def _metadata(video_id, **kw):
    info = {
        "id": video_id,
        "title": "funny school moment wait for it",
        "channel": "SomeChannel",
        "view_count": 900_000,
        "like_count": 50_000,
        "comment_count": 2_000,
        "duration": 30.0,
        "upload_date": "20261101",
        "description": "a clip",
        "license": "",
        "tags": [],
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    info.update(kw)
    return info


@pytest.fixture(autouse=True)
def _fake_settings(monkeypatch):
    monkeypatch.setattr(rd, "get_settings", lambda: _settings())


# --------------------------------------------------------------------------- #
# URL extraction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=12s", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?t=5", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://vimeo.com/123456", ""),
    ("https://www.reddit.com/r/Unexpected/comments/a1/x/", ""),
    ("https://www.youtube.com/watch?v=short", ""),
    ("https://www.youtube.com/watch", ""),
    ("https://www.youtube.com/playlist?list=PL123", ""),
    ("", ""),
    ("not a url", ""),
])
def test_youtube_video_id_from_url(url, expected):
    assert rd.youtube_video_id_from_url(url) == expected


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def test_select_video_posts_filters_and_ranks():
    posts = [
        _post("self1", is_self=True, selftext="a story " * 50,
              url="https://www.reddit.com/r/Unexpected/comments/self1/x/"),
        _post("sticky1", stickied=True),
        _post("nsfw1", over_18=True),
        _post("other1", url="https://example.com/clip.mp4"),
        _post("low1", score=3),
        _post("dup-low", url="https://youtu.be/AAAAAAAAAAA", score=10),
        _post("dup-high", url="https://youtu.be/AAAAAAAAAAA", score=90,
              num_comments=5),
        _post("good1", url="https://youtu.be/BBBBBBBBBBB", score=50,
              num_comments=99),
    ]
    from app.services.reddit_trends import parse_listing

    parsed = parse_listing(_listing(*posts))
    selected, skipped = rd.select_video_posts(parsed, min_score=5)
    assert [p["video_id"] for p in selected] == ["AAAAAAAAAAA", "BBBBBBBBBBB"]
    # Higher-scored duplicate wins; the loser is reported, not hidden.
    assert selected[0]["post_id"] == "dup-high"
    reasons = {entry["reason"] for entry in skipped}
    assert reasons == {
        "self_post_no_video", "stickied", "nsfw", "non_youtube_link",
        "below_min_score", "duplicate_video",
    }


def test_select_video_posts_nsfw_opt_in():
    from app.services.reddit_trends import parse_listing

    parsed = parse_listing(_listing(_post("n1", over_18=True)))
    selected, _ = rd.select_video_posts(parsed)
    assert selected == []
    selected, _ = rd.select_video_posts(parsed, include_nsfw=True)
    assert [p["video_id"] for p in selected] == ["dQw4w9WgXcQ"]


# --------------------------------------------------------------------------- #
# Discovery: gates, loud failures, honest skips
# --------------------------------------------------------------------------- #
def _run(posts, resolver, **kwargs):
    def fake_fetcher(url):
        return _listing(*posts)

    kwargs.setdefault("min_views", 500_000)
    kwargs.setdefault("min_seconds", 10.0)
    kwargs.setdefault("max_seconds", 58.0)
    return rd.discover_reddit_candidates_detailed(
        "Unexpected", fetcher=fake_fetcher,
        metadata_resolver=lambda ids: {vid: resolver(vid) for vid in ids if resolver(vid)},
        **kwargs,
    )


def test_happy_path_applies_same_gates_and_carries_provenance():
    posts = [
        _post("good", url="https://youtu.be/GOODVIDEO11", score=500,
              num_comments=42),
        _post("fewviews", url="https://youtu.be/FEWVIEWS111", score=400),
        _post("toolong", url="https://youtu.be/TOOLONG1111", score=300),
        _post("excluded", url="https://youtu.be/EXCLUDED111", score=200),
    ]

    def resolver(video_id):
        if video_id == "GOODVIDEO11":
            return _metadata(video_id)
        if video_id == "FEWVIEWS111":
            return _metadata(video_id, view_count=100)
        if video_id == "TOOLONG1111":
            return _metadata(video_id, duration=120.0)
        if video_id == "EXCLUDED111":
            return _metadata(video_id)
        return None

    result = _run(posts, resolver, exclude_ids={"EXCLUDED111"})
    candidates = result["candidates"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, Candidate)
    assert candidate.video_id == "GOODVIDEO11"
    assert candidate.score > 0
    assert candidate.source_platform == "reddit"
    assert candidate.source_subreddit == "Unexpected"
    assert candidate.source_post_id == "good"
    assert candidate.source_url == "https://www.reddit.com/r/Unexpected/comments/good/x/"
    assert candidate.reddit_score == 500
    assert candidate.reddit_comments == 42
    assert result["report"]["accepted"] == 1
    assert result["report"]["skipped"] == {
        "views_gate": 1, "duration_gate": 1, "excluded": 1,
    }


def test_metadata_unavailable_skips_without_fabrication():
    posts = [_post("good", url="https://youtu.be/GOODVIDEO11", score=500)]
    result = _run(posts, lambda video_id: None)
    assert result["candidates"] == []
    assert result["report"]["skipped"] == {"metadata_unavailable": 1}


def test_listing_fetch_failure_is_loud():
    def boom(url):
        raise RuntimeError("reddit listing fetch failed: HTTP 403")

    with pytest.raises(RuntimeError, match="HTTP 403"):
        rd.discover_reddit_candidates_detailed(
            "Unexpected", fetcher=boom,
            metadata_resolver=lambda ids: {},
        )


def test_bad_subreddit_refused_before_any_fetch():
    seen = []

    def fake_fetcher(url):
        seen.append(url)
        return _listing()

    with pytest.raises(ValueError, match="invalid subreddit name"):
        rd.discover_reddit_candidates_detailed(
            "bad name!", fetcher=fake_fetcher,
            metadata_resolver=lambda ids: {},
        )
    assert seen == []


def test_no_subreddits_configured_makes_no_call():
    def boom(url):
        raise AssertionError("no fetch should happen")

    result = rd.discover_reddit_candidates_detailed(
        "", fetcher=boom, metadata_resolver=lambda ids: {},
    )
    assert result == {
        "candidates": [],
        "report": {
            "version": rd.ADAPTER_VERSION, "subreddits": [],
            "received": 0, "video_posts": 0, "accepted": 0,
            "skipped": {}, "skipped_sample": [],
            "reason": "no_subreddits_configured",
        },
    }


def test_reuse_licensed_policy_refuses_pool(monkeypatch):
    monkeypatch.setattr(
        rd, "get_settings",
        lambda: SimpleNamespace(
            viral_min_source_views=500_000,
            viral_min_source_seconds=10.0,
            viral_source_policy="reuse_licensed",
        ),
    )
    seen = []

    def fake_fetcher(url):
        seen.append(url)
        return _listing(_post("good"))

    result = rd.discover_reddit_candidates_detailed(
        "Unexpected", fetcher=fake_fetcher,
        metadata_resolver=lambda ids: {"GOODVIDEO11": _metadata("GOODVIDEO11")},
    )
    assert result["candidates"] == []
    assert result["report"]["reason"] == "reuse_licensed_unverifiable"
    assert seen == []  # refused before any fetch


def test_subreddit_list_parsing():
    assert rd._parse_subreddits("Unexpected, funny ,Unexpected,,") == [
        "Unexpected", "funny",
    ]
    assert rd._parse_subreddits(["a", "b", "a"]) == ["a", "b"]
    assert rd._parse_subreddits(None) == []
    assert rd._parse_subreddits("") == []


def test_candidates_ranked_by_score():
    posts = [
        _post("low", url="https://youtu.be/LOWVIDEO111", score=100),
        _post("high", url="https://youtu.be/HIGHVIDEO11", score=900),
    ]

    def resolver(video_id):
        views = 2_000_000 if video_id == "HIGHVIDEO11" else 600_000
        return _metadata(video_id, view_count=views)

    result = _run(posts, resolver)
    assert [c.video_id for c in result["candidates"]] == [
        "HIGHVIDEO11", "LOWVIDEO111",
    ]


# --------------------------------------------------------------------------- #
# Loop integration: the Reddit pool merges into the ranked pool
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _loop_settings(tmp_path, **overrides):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# cookies", encoding="utf-8")
    values = {
        "data_dir": tmp_path / "data",
        "media_dir": tmp_path / "media",
        "render_dir": tmp_path / "renders",
        "viral_loop_enabled": True,
        "viral_music_bed_enabled": True,
        "autonomous_publish_privacy": "unlisted",
        "youtube_cookies_file": cookies,
        "viral_reddit_subreddits": "Unexpected",
        "viral_reddit_min_score": 0,
    }
    values.update(overrides)
    return Settings(**values)


def _wire_loop(monkeypatch, settings, *, reddit_pool, calls):
    monkeypatch.setattr(viral_loop, "get_settings", lambda: settings)
    monkeypatch.setattr(viral_loop, "trending_candidates", lambda **kw: [])
    monkeypatch.setattr(viral_loop, "discover_candidates_api", lambda **kw: [])
    monkeypatch.setattr(
        viral_loop, "discover_reddit_candidates", lambda *a, **kw: list(reddit_pool)
    )
    monkeypatch.setattr(
        viral_loop.vr, "download_audio_only",
        lambda video_id, folder: Path(f"/tmp/{video_id}.m4a"),
    )
    monkeypatch.setattr(
        viral_loop.vr, "detect_speech",
        lambda path, **_kwargs: SimpleNamespace(
            has_speech=False, cues=[], text="",
        ),
    )

    def fake_produce(candidate, db, *, publish=True, hold_for_review=False):
        calls.append(candidate.video_id)
        job = PublishJob(
            asset_id=1, render_job_id=1, title=f"T {candidate.video_id}",
            tags_json="[]", privacy_status="unlisted",
            status="pending_approval" if hold_for_review else "queued",
        )
        db.add(job)
        db.commit()
        return {
            "status": "QUEUED_FOR_PUBLISH", "publish_job_id": job.id,
            "render_job_id": 1,
            "render": f"/renders/{candidate.video_id}.mp4",
        }

    monkeypatch.setattr(
        viral_loop.viral_framing, "produce_framed_short", fake_produce
    )
    monkeypatch.setattr(viral_loop.vr, "produce_viral_short", fake_produce)


def _reddit_candidate(video_id):
    return Candidate(
        video_id=video_id, title="funny school moment",
        channel="SomeChannel", duration=30.0, view_count=900_000,
        like_count=1000, upload_date="20261101",
        license="transformative_commentary", category="COMEDY",
        hook="WAIT FOR IT", score=10.0,
        source_platform="reddit", source_subreddit="Unexpected",
        source_post_id="p1", source_url="https://www.reddit.com/r/x/",
        reddit_score=500, reddit_comments=42,
    )


def test_loop_merges_reddit_pool(monkeypatch, tmp_path, db):
    calls: list[str] = []
    settings = _loop_settings(tmp_path)
    _wire_loop(
        monkeypatch, settings,
        reddit_pool=[_reddit_candidate("REDDITVID11")], calls=calls,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["status"] == "COMPLETED"
    assert summary["pool"] == 1
    assert summary["produced"] == 1
    assert calls == ["REDDITVID11"]


def test_loop_reddit_pool_dedupes_against_api_lane(monkeypatch, tmp_path, db):
    calls: list[str] = []
    settings = _loop_settings(tmp_path)
    _wire_loop(
        monkeypatch, settings,
        reddit_pool=[_reddit_candidate("SHAREDVID11")], calls=calls,
    )
    monkeypatch.setattr(
        viral_loop, "discover_candidates_api",
        lambda **kw: [_reddit_candidate("SHAREDVID11")],
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["pool"] == 1  # same video id counted once
    assert summary["produced"] == 1


def test_loop_with_reddit_off_runs_unchanged(monkeypatch, tmp_path, db):
    calls: list[str] = []
    settings = _loop_settings(tmp_path, viral_reddit_subreddits="")
    seen: dict[str, Any] = {}
    _wire_loop(monkeypatch, settings, reddit_pool=[], calls=calls)
    monkeypatch.setattr(
        viral_loop, "discover_reddit_candidates",
        lambda subreddits, **kw: seen.setdefault("subreddits", subreddits) or [],
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["status"] == "COMPLETED"
    assert summary["pool"] == 0
    assert seen["subreddits"] == ""


def test_evidence_doc_exists():
    doc = Path(__file__).resolve().parent.parent.parent / "docs" / "collaboration" \
        / "TASK-VYR-058-REDDIT-SOURCING-ADAPTER.md"
    assert doc.is_file(), "evidence doc must ship in the work PR"
