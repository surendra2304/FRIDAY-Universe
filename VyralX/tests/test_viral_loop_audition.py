"""TASK-VYR-020: the loop's routing audition requires two-pass agreement.

The single-call audition this replaces flipped 12/12 candidates in
gated render #2 (PR #957 supervisor review, §5). The dangerous
direction is a voiced clip judged voiceless: the loop would lay her
commentary over source speech. So the commentary route now requires
two differently-tuned detector passes to agree there is no speech,
while a single positive still routes voiced (production re-auditions
and fails closed in that direction).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models import PublishJob
from app.services import viral_loop
from app.services.source_analysis import SpeechReport
from app.services.viral_discovery import Candidate

_CUE = {"start": 0.0, "end": 2.0, "text": "hello world", "speech": True}


def _report(has_speech: bool, *, cues: tuple = (), seconds: float = 0.0) -> SpeechReport:
    return SpeechReport(
        has_speech,
        seconds,
        tuple(cues),
        " ".join(cue["text"] for cue in cues),
    )


def _silent() -> SpeechReport:
    return _report(False)


def _voiced(cues: bool = True) -> SpeechReport:
    return _report(True, cues=(_CUE,) if cues else (), seconds=2.0)


class _ScriptedDetector:
    """detect_speech stand-in: verdicts are consumed in call order."""

    def __init__(self, verdicts):
        self._verdicts = list(verdicts)
        self.calls: list[dict] = []

    def __call__(self, path, **kwargs):
        self.calls.append(kwargs)
        return self._verdicts.pop(0)


def _candidate(video_id: str, *, duration: float = 30.0) -> Candidate:
    return Candidate(
        video_id=video_id, title=f"Video {video_id}", channel="Chan",
        duration=duration, view_count=900_000, like_count=1000,
        upload_date="20261101", license="transformative_commentary",
        category="SPORTS", hook="WAIT FOR IT", score=10.0,
    )


def _audition(monkeypatch, verdicts, candidate, *, cap=58.0):
    detector = _ScriptedDetector(verdicts)
    monkeypatch.setattr(viral_loop.vr, "detect_speech", detector)
    report, audit = viral_loop._routing_audition(
        candidate, Path(f"/tmp/{candidate.video_id}.m4a"), commentary_cap=cap
    )
    return report, audit, detector


def test_agree_no_speech_allows_commentary(monkeypatch):
    report, audit, detector = _audition(
        monkeypatch, [_silent(), _silent()], _candidate("v1")
    )
    assert report.has_speech is False
    assert audit["agreement"] == "agree_no_speech"
    assert audit["disagreement"] is False
    assert audit["pass1"]["has_speech"] is False
    assert audit["pass2"]["has_speech"] is False
    # Pass 1 uses the production settings untouched; the confirmation
    # pass is the differently-tuned one.
    assert detector.calls[0] == {}
    assert detector.calls[1] == {"beam_size": 5, "vad_threshold": 0.25}


def test_disagreement_is_treated_as_voiced_with_its_transcript(monkeypatch):
    second = _voiced()
    report, audit, detector = _audition(
        monkeypatch, [_silent(), second], _candidate("v2")
    )
    # The second pass's report drives routing: voiced, framed on its cues.
    assert report is second
    assert report.has_speech is True
    assert len(report.cues) == 1
    assert audit["agreement"] == "disagreement_treated_voiced"
    assert audit["disagreement"] is True
    assert len(detector.calls) == 2


def test_disagreement_without_transcript_still_voiced(monkeypatch):
    # Includes the detector-failure shape (assume narration, no cues):
    # never commentary — the cycle will skip it as no_transcript.
    report, audit, _detector = _audition(
        monkeypatch, [_silent(), _voiced(cues=False)], _candidate("v3")
    )
    assert report.has_speech is True
    assert report.cues == ()
    assert audit["disagreement"] is True


def test_single_positive_suffices_and_skips_second_pass(monkeypatch):
    first = _voiced()
    report, audit, detector = _audition(monkeypatch, [first], _candidate("v4"))
    assert report is first
    assert audit["agreement"] == "voiced_first_pass"
    assert audit["pass2"] is None
    assert len(detector.calls) == 1


def test_long_candidate_gets_no_second_pass(monkeypatch):
    # Voiceless + long skips either way; confirming it would buy nothing.
    report, audit, detector = _audition(
        monkeypatch, [_silent()], _candidate("v5", duration=300.0)
    )
    assert report.has_speech is False
    assert audit["agreement"] == "no_second_pass_too_long"
    assert audit["pass2"] is None
    assert len(detector.calls) == 1


# --- cycle level: a flipped first verdict can no longer reach commentary ---


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _settings(tmp_path: Path) -> Settings:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# cookies", encoding="utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        media_dir=tmp_path / "media",
        render_dir=tmp_path / "renders",
        viral_loop_enabled=True,
        viral_music_bed_enabled=True,
        autonomous_publish_privacy="unlisted",
        youtube_cookies_file=cookies,
    )


def test_cycle_flip_cannot_reach_commentary(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [
        _candidate("flipvoiced"),
        _candidate("flipnocues"),
        _candidate("truesilent"),
        _candidate("truevoiced"),
    ]
    verdicts = {
        # Pass 1 hears nothing; pass 2 hears speech -> framed, never commentary.
        "flipvoiced": [_silent(), _voiced()],
        # Pass 2 hears speech but has no transcript -> skip, never commentary.
        "flipnocues": [_silent(), _voiced(cues=False)],
        # Both passes agree there is no speech -> commentary, as before.
        "truesilent": [_silent(), _silent()],
        # Voiced on pass 1 -> framed, no second pass spent.
        "truevoiced": [_voiced()],
    }
    detectors: dict[str, _ScriptedDetector] = {}

    def fake_detect(path, **kwargs):
        detector = detectors.setdefault(path.stem, _ScriptedDetector(verdicts[path.stem]))
        return detector(path, **kwargs)

    calls: list = []

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

    monkeypatch.setattr(viral_loop, "get_settings", lambda: settings)
    monkeypatch.setattr(viral_loop, "trending_candidates", lambda **kw: list(pool))
    monkeypatch.setattr(viral_loop, "discover_candidates_api", lambda **kw: [])
    monkeypatch.setattr(
        viral_loop.vr, "download_audio_only",
        lambda video_id, folder: Path(f"/tmp/{video_id}.m4a"),
    )
    monkeypatch.setattr(viral_loop.vr, "detect_speech", fake_detect)
    monkeypatch.setattr(
        viral_loop.viral_framing, "produce_framed_short", fake_produce("framed")
    )
    monkeypatch.setattr(
        viral_loop.vr, "produce_viral_short", fake_produce("commentary")
    )

    summary = viral_loop.run_viral_loop_cycle(db)

    assert summary["status"] == "COMPLETED"
    # The flipped candidate is framed on the second pass's transcript;
    # commentary is reached ONLY by the candidate both passes cleared.
    assert calls == [
        ("framed", "flipvoiced", True),
        ("commentary", "truesilent", True),
        ("framed", "truevoiced", True),
    ]
    assert summary["produced"] == 3
    assert summary["skips"] == {"no_transcript": 1}
    assert summary["audition_disagreements"] == 2
    assert summary["audition_second_passes"] == 3
    assert {vid: len(d.calls) for vid, d in detectors.items()} == {
        "flipvoiced": 2, "flipnocues": 2, "truesilent": 2, "truevoiced": 1,
    }
    # Everything produced is still held for the owner's review.
    jobs = db.query(PublishJob).all()
    assert len(jobs) == 3
    assert all(job.status == "pending_approval" for job in jobs)
    assert all(job.approved_at is None for job in jobs)
    state = json.loads((tmp_path / "data" / "viral_loop_state.json").read_text())
    assert state["last_summary"]["audition_disagreements"] == 2
