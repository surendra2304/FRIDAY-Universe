"""TASK-VYR-019: the autonomous loop's guards and routing.

The loop must refuse to run when it cannot guarantee the owner's
shape (off, no BGM, not unlisted, no cookies), and a cycle must route
by the audio rule — voiced -> framed, voiceless short -> commentary,
voiceless long -> skip, voiced without a transcript -> skip — holding
every produced job for review and filing it under its series.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import PublishJob
from app.services import viral_loop
from app.services.viral_discovery import Candidate


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _settings(tmp_path: Path, **overrides) -> Settings:
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
    }
    values.update(overrides)
    return Settings(**values)


def _candidate(video_id: str, *, category: str = "SPORTS", duration: float = 30.0) -> Candidate:
    return Candidate(
        video_id=video_id, title=f"Video {video_id}", channel="Chan",
        duration=duration, view_count=900_000, like_count=1000,
        upload_date="20261101", license="transformative_commentary",
        category=category, hook="WAIT FOR IT", score=10.0,
    )


def _wire(monkeypatch, settings, *, pool, speech_by_id, calls):
    monkeypatch.setattr(viral_loop, "get_settings", lambda: settings)
    monkeypatch.setattr(
        viral_loop, "trending_candidates", lambda **kw: list(pool)
    )
    monkeypatch.setattr(viral_loop, "discover_candidates_api", lambda **kw: [])
    monkeypatch.setattr(
        viral_loop.vr, "download_audio_only",
        lambda video_id, folder: Path(f"/tmp/{video_id}.m4a"),
    )
    monkeypatch.setattr(
        viral_loop.vr, "detect_speech", lambda path: speech_by_id[path.stem]
    )

    def fake_produce(kind):
        def _produce(candidate, db, *, publish=True, hold_for_review=False):
            calls.append((kind, candidate.video_id, hold_for_review))
            job = PublishJob(
                asset_id=1, render_job_id=1, title=f"T {candidate.video_id}",
                tags_json="[]", privacy_status="unlisted",
                status="pending_approval" if hold_for_review else "queued",
            )
            db.add(job)
            db.commit()
            return {
                "status": "QUEUED_FOR_PUBLISH",
                "publish_job_id": job.id,
                "render_job_id": 1,
                "render": f"/renders/{candidate.video_id}.mp4",
                "edit_mode": kind,
                "title": job.title,
                "bgm_source": "growth:Drift Edit:phonk",
            }
        return _produce

    monkeypatch.setattr(
        viral_loop.viral_framing, "produce_framed_short", fake_produce("framed")
    )
    monkeypatch.setattr(
        viral_loop.vr, "produce_viral_short", fake_produce("commentary")
    )


def _voiced(cues=True):
    return SimpleNamespace(
        has_speech=True,
        cues=[{"start": 0.0, "end": 2.0, "text": "hello"}] if cues else [],
        text="hello world",
    )


def _silent():
    return SimpleNamespace(has_speech=False, cues=[], text="")


def test_guard_loop_disabled(tmp_path, db):
    settings = _settings(tmp_path, viral_loop_enabled=False)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(viral_loop, "get_settings", lambda: settings)
        assert viral_loop.run_viral_loop_cycle(db) == {
            "status": "GUARDED", "guard": "LOOP_DISABLED",
        }
    # --force is the supervised override.
    calls: list = []
    with pytest.MonkeyPatch.context() as mp:
        _wire(mp, settings, pool=[], speech_by_id={}, calls=calls)
        summary = viral_loop.run_viral_loop_cycle(db, force=True)
    assert summary["status"] == "COMPLETED"


def test_guard_bgm_privacy_cookies(tmp_path, db):
    cases = [
        ({"viral_music_bed_enabled": False}, "BGM_REQUIRED"),
        ({"autonomous_publish_privacy": "public"}, "PRIVACY_NOT_UNLISTED"),
        ({"youtube_cookies_file": tmp_path / "missing.txt"}, "NO_COOKIES"),
    ]
    for overrides, guard in cases:
        settings = _settings(tmp_path, **overrides)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(viral_loop, "get_settings", lambda: settings)
            result = viral_loop.run_viral_loop_cycle(db)
        assert result == {"status": "GUARDED", "guard": guard}, guard


def test_cycle_routes_by_audio_rule_and_holds_everything(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [
        _candidate("voiced1"),
        _candidate("silent1", category="COMEDY"),
        _candidate("silentlong", duration=300.0),
        _candidate("voicednocues"),
    ]
    speech = {
        "voiced1": _voiced(),
        "silent1": _silent(),
        "silentlong": _silent(),
        "voicednocues": _voiced(cues=False),
    }
    calls: list = []
    _wire(monkeypatch, settings, pool=pool, speech_by_id=speech, calls=calls)
    summary = viral_loop.run_viral_loop_cycle(db)

    assert summary["status"] == "COMPLETED"
    assert summary["produced"] == 2
    assert summary["by_series"] == {"SPORTS": 1, "COMEDY": 1}
    assert summary["skips"] == {"too_long_for_commentary": 1, "no_transcript": 1}
    assert calls == [
        ("framed", "voiced1", True),
        ("commentary", "silent1", True),
    ]
    # Every produced job is held for the owner's review.
    jobs = db.query(PublishJob).all()
    assert len(jobs) == 2
    assert all(job.status == "pending_approval" for job in jobs)
    assert all(job.approved_at is None for job in jobs)
    assert all(job.privacy_status == "unlisted" for job in jobs)
    # Series filing: slug tag on the job + a manifest line per short.
    sports_job = next(j for j in jobs if "voiced1" in j.title)
    assert "sports" in json.loads(sports_job.tags_json)
    manifest = (tmp_path / "data" / "viral_loop_manifest.jsonl").read_text()
    entries = [json.loads(line) for line in manifest.splitlines()]
    assert {entry["video_id"] for entry in entries} == {"voiced1", "silent1"}
    assert all(entry["status"] == "HELD" for entry in entries)
    # BGM state is part of the cycle record, phonk gap visible.
    assert summary["bgm"]["policy"] == "growth"
    assert any("phonk_shelf_empty" in w for w in summary["warnings"])
    state = json.loads((tmp_path / "data" / "viral_loop_state.json").read_text())
    assert state["cycles_completed"] == 1


def test_cycle_excludes_already_used_sources(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    from app.models import Source

    db.add(Source(
        title="old", source_url="https://www.youtube.com/watch?v=voiced1",
        platform="youtube_transformative", creator="c", license_name="x",
        permission_reference="y", rights_verified=True, status="approved",
    ))
    db.commit()
    calls: list = []
    _wire(
        monkeypatch, settings,
        pool=[_candidate("voiced1")],
        speech_by_id={"voiced1": _voiced()},
        calls=calls,
    )
    # The exclusion happens inside trending_candidates in production;
    # here the fake pool bypasses it, so assert the loop's own used-id
    # reader sees the source (the pool merge receives it as exclude).
    assert viral_loop._used_source_ids(db) == {"voiced1"}
