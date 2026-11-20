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
        viral_loop.vr, "detect_speech",
        lambda path, **_kwargs: speech_by_id[path.stem],
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


# --- TASK-VYR-026: vision pacing, daily budget, clean rate-limit stop -- #
# The loop half of the rate-limit hardening: scene calls are paced,
# the day's estimated vision-token spend is tracked in the persisted
# state, and a cycle stops cleanly (vision_daily_budget /
# vision_rate_limited) instead of burning attempts against a drained
# day. The scene_analysis module is replaced with a scripted fake;
# production is faked to consume one scripted vision outcome per call.


class _FakeVision:
    """Scripted stand-in for app.services.scene_analysis.

    ``script`` holds one outcome per vision call, consumed in order;
    calls past the end of the script succeed. ``call()`` is invoked by
    the fake production functions to simulate the scene call that
    production makes internally.
    """

    def __init__(self, script):
        self.script = list(script)
        self.seq = 0
        self.current = {
            "seq": 0, "status": None, "rate_limit_exhausted": False,
            "attempts": 0, "estimated_tokens": 0, "called_at": None,
        }
        self.pacing_waits: list[float] = []
        self.seeded_with = "unset"

    def vision_call_seq(self):
        return self.seq

    def last_vision_outcome(self):
        return dict(self.current)

    def wait_for_vision_pacing(self, min_interval_seconds):
        self.pacing_waits.append(min_interval_seconds)
        return 0.0

    def seed_vision_clock(self, epoch):
        self.seeded_with = epoch

    def call(self):
        if self.seq < len(self.script):
            outcome = self.script[self.seq]
        else:
            outcome = {"status": 200, "rate_limit_exhausted": False,
                       "estimated_tokens": 5000}
        self.seq += 1
        self.current = {"seq": self.seq, "attempts": 4, "called_at": 1763000000.0, **outcome}
        return self.current


def _exhausted(tokens=5000):
    return {"status": 429, "rate_limit_exhausted": True, "estimated_tokens": tokens}


def _failed_other(tokens=5000):
    return {"status": 500, "rate_limit_exhausted": False, "estimated_tokens": tokens}


def _ok(tokens=5000):
    return {"status": 200, "rate_limit_exhausted": False, "estimated_tokens": tokens}


def _wire_vision_cycle(monkeypatch, settings, *, pool, vision, produce):
    """_wire variant whose production consumes scripted vision outcomes."""
    monkeypatch.setattr(viral_loop, "get_settings", lambda: settings)
    monkeypatch.setattr(viral_loop, "scene_analysis", vision)
    monkeypatch.setattr(viral_loop, "trending_candidates", lambda **kw: list(pool))
    monkeypatch.setattr(viral_loop, "discover_candidates_api", lambda **kw: [])
    monkeypatch.setattr(
        viral_loop.vr, "download_audio_only",
        lambda video_id, folder: Path(f"/tmp/{video_id}.m4a"),
    )
    monkeypatch.setattr(
        viral_loop.vr, "detect_speech",
        lambda path, **_kwargs: _voiced(),
    )

    def _framed(candidate, db, *, publish=True, hold_for_review=False):
        vision.call()
        return produce(candidate)

    monkeypatch.setattr(viral_loop.viral_framing, "produce_framed_short", _framed)
    monkeypatch.setattr(viral_loop.vr, "produce_viral_short", _framed)


def _skip_vision_unavailable(candidate):
    return {"status": "SKIPPED", "reason": "vision_unavailable"}


def test_cycle_stops_after_consecutive_rate_limited_vision(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"v{i}") for i in range(6)]
    vision = _FakeVision([_exhausted()] * 6)
    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision,
        produce=_skip_vision_unavailable,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    # Threshold is 3: the third consecutive exhausted call stops the
    # cycle; the remaining three candidates are never attempted.
    assert summary["stopped"] == "vision_rate_limited"
    assert summary["attempts"] == 3
    assert summary["produced"] == 0
    assert summary["skips"] == {"vision_unavailable": 2, "vision_rate_limited": 1}
    assert summary["vision"]["rate_limit_streak"] == 3
    assert summary["vision"]["estimated_tokens_today"] == 15000
    # Pacing was consulted before every production attempt.
    assert vision.pacing_waits == [65.0, 65.0, 65.0]
    # The spend was persisted for the next process.
    state = json.loads((tmp_path / "data" / "viral_loop_state.json").read_text())
    assert state["vision_budget"]["estimated_tokens"] == 15000


def test_cycle_vision_streak_resets_on_success(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"v{i}") for i in range(8)]
    vision = _FakeVision([
        _exhausted(), _exhausted(), _ok(),
        _exhausted(), _exhausted(), _exhausted(),
    ])

    def produce(candidate):
        outcome = vision.current
        if outcome["rate_limit_exhausted"]:
            return {"status": "SKIPPED", "reason": "vision_unavailable"}
        job = PublishJob(
            asset_id=1, render_job_id=1, title=f"T {candidate.video_id}",
            tags_json="[]", privacy_status="unlisted", status="pending_approval",
        )
        db.add(job)
        db.commit()
        return {
            "status": "QUEUED_FOR_PUBLISH", "publish_job_id": job.id,
            "render_job_id": 1, "render": "/renders/x.mp4",
            "edit_mode": "framed", "title": job.title, "bgm_source": "synth",
        }

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    # Two exhausted, a success (streak resets), then three more
    # exhausted — the stop lands on the sixth attempt, not the fifth.
    assert summary["produced"] == 1
    assert summary["attempts"] == 6
    assert summary["stopped"] == "vision_rate_limited"
    assert summary["skips"] == {"vision_unavailable": 4, "vision_rate_limited": 1}


def test_cycle_vision_daily_budget_stop(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path, viral_loop_vision_daily_token_budget=9000)
    pool = [_candidate(f"v{i}") for i in range(5)]
    # Non-rate-limit failures: tokens are still charged, the streak
    # never builds, so only the budget can stop this cycle.
    vision = _FakeVision([_failed_other()] * 5)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    # 5000 after attempt 1 (< 9000, continue), 10000 after attempt 2;
    # the third candidate trips the pre-production budget check and
    # production is never invoked for it.
    assert summary["stopped"] == "vision_daily_budget"
    assert produce_calls == ["v0", "v1"]
    assert summary["skips"] == {"vision_unavailable": 2}
    assert summary["vision"]["estimated_tokens_today"] == 10000
    state = json.loads((tmp_path / "data" / "viral_loop_state.json").read_text())
    assert state["vision_budget"]["estimated_tokens"] == 10000


def test_cycle_vision_budget_persists_across_cycles(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path, viral_loop_vision_daily_token_budget=9000)
    vision = _FakeVision([_failed_other()] * 10)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    pool = [_candidate("a0")]
    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    first = viral_loop.run_viral_loop_cycle(db)
    assert "stopped" not in first
    assert first["vision"]["estimated_tokens_today"] == 5000

    pool = [_candidate(f"b{i}") for i in range(3)]
    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    second = viral_loop.run_viral_loop_cycle(db)
    # The second cycle inherits the day's 5000: one more call reaches
    # 10000 and the next candidate stops on the budget.
    assert second["stopped"] == "vision_daily_budget"
    assert second["vision"]["estimated_tokens_today"] == 10000
    assert produce_calls == ["a0", "b0"]


def test_cycle_pacing_only_for_candidates_that_produce(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate("voiced1"), _candidate("nocues"), _candidate("voiced2")]
    vision = _FakeVision([_ok(), _ok()])
    calls: list = []
    _wire(
        monkeypatch, settings, pool=pool,
        speech_by_id={
            "voiced1": _voiced(),
            "nocues": _voiced(cues=False),
            "voiced2": _voiced(),
        },
        calls=calls,
    )
    monkeypatch.setattr(viral_loop, "scene_analysis", vision)
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["produced"] == 2
    assert summary["skips"] == {"no_transcript": 1}
    # The no-transcript candidate never reaches production, so it
    # never touches the pacing clock; the two producers do.
    assert vision.pacing_waits == [65.0, 65.0]

# --- TASK-VYR-029: provider-aware vision token budgets ----------------- #
# Cycle 9 proved the VYR-028 fail-over works but produced 0 renders:
# the VYR-026 budget counted estimated tokens per attempt regardless
# of provider and tripped at 195,560 after 10 attempts, 7 of them
# fail-over. The Groq budget now gates Groq tokens only; Gemini
# fail-over tokens gate against their own budget (default 2,500,000
# ≈ 500 requests at the measured 4,889-token analyze_scene
# estimate) with the distinct stop reason vision_daily_budget_gemini.
# The scripted outcomes below carry the per-provider keys the real
# scene_analysis outcome now records; _failed_other/_ok (no keys)
# still exercise the legacy path, which charges the whole total to
# Groq.
def _failover_ok(groq_tokens=5000, gemini_tokens=5000):
    """A fail-over success: 4 Groq attempts + 1 Gemini attempt."""
    return {
        "status": 200, "rate_limit_exhausted": False,
        "estimated_tokens": groq_tokens + gemini_tokens,
        "estimated_tokens_groq": groq_tokens,
        "estimated_tokens_gemini": gemini_tokens,
    }


def _failover_failed_other(groq_tokens=5000, gemini_tokens=5000):
    """A fail-over that returned a non-429 failure (streak stays 0)."""
    return {
        "status": 500, "rate_limit_exhausted": False,
        "estimated_tokens": groq_tokens + gemini_tokens,
        "estimated_tokens_groq": groq_tokens,
        "estimated_tokens_gemini": gemini_tokens,
    }


def _seed_vision_state(tmp_path, *, total, groq=None, gemini=None):
    """Pre-write today's persisted vision budget (migration cases)."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date().isoformat()
    budget = {"date": today, "estimated_tokens": total, "last_call_at": None}
    if groq is not None:
        budget["estimated_tokens_groq"] = groq
    if gemini is not None:
        budget["estimated_tokens_gemini"] = gemini
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "viral_loop_state.json").write_text(
        json.dumps({"cycles_completed": 0, "vision_budget": budget}),
        encoding="utf-8",
    )


def test_cycle_vision_gemini_budget_stop(tmp_path, db, monkeypatch):
    settings = _settings(
        tmp_path, viral_loop_vision_failover_daily_token_budget=10000,
    )
    pool = [_candidate(f"v{i}") for i in range(5)]
    # Fail-over outcomes: 5000 Groq + 5000 Gemini each. Groq stays
    # far below its 180,000 default; only the Gemini budget can stop
    # this cycle.
    vision = _FakeVision([_failover_failed_other()] * 5)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    # 5000 Gemini after attempt 1 (< 10000, continue), 10000 after
    # attempt 2; the third candidate trips the Gemini pre-production
    # check and production is never invoked for it.
    assert summary["stopped"] == "vision_daily_budget_gemini"
    assert produce_calls == ["v0", "v1"]
    assert summary["skips"] == {"vision_unavailable": 2}
    assert summary["vision"]["estimated_tokens_gemini_today"] == 10000
    assert summary["vision"]["estimated_tokens_groq_today"] == 10000
    assert summary["vision"]["estimated_tokens_today"] == 20000
    assert summary["vision"]["failover_daily_budget"] == 10000
    state = json.loads((tmp_path / "data" / "viral_loop_state.json").read_text())
    assert state["vision_budget"]["estimated_tokens_gemini"] == 10000
    assert state["vision_budget"]["estimated_tokens_groq"] == 10000


def test_cycle_vision_groq_budget_ignores_gemini_tokens(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    # Cycle-9-shaped day, pre-seeded: Groq 100,000 + Gemini 90,000
    # already spent (total 190,000 — over the old single budget of
    # 180,000). Three more fail-over attempts spend 5,000 Groq +
    # 15,000 Gemini each.
    _seed_vision_state(tmp_path, total=190000, groq=100000, gemini=90000)
    pool = [_candidate(f"v{i}") for i in range(3)]
    vision = _FakeVision([_failover_failed_other(5000, 15000)] * 3)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    # Groq ends at 115,000 (< 180,000) and Gemini at 135,000
    # (< 2,500,000): no budget stops this cycle — the old code
    # would have stopped it on the 190,000+ total before any attempt.
    assert "stopped" not in summary
    assert summary["attempts"] == 3
    assert produce_calls == ["v0", "v1", "v2"]
    assert summary["vision"]["estimated_tokens_groq_today"] == 115000
    assert summary["vision"]["estimated_tokens_gemini_today"] == 135000
    assert summary["vision"]["estimated_tokens_today"] == 250000


def test_cycle_vision_legacy_outcome_charges_groq(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path, viral_loop_vision_daily_token_budget=9000)
    pool = [_candidate(f"v{i}") for i in range(5)]
    # Legacy outcomes carry no per-provider keys: the whole total
    # attributes to Groq, so the Groq budget still stops the cycle.
    vision = _FakeVision([_failed_other()] * 5)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["stopped"] == "vision_daily_budget"
    assert produce_calls == ["v0", "v1"]
    assert summary["vision"]["estimated_tokens_groq_today"] == 10000
    assert summary["vision"]["estimated_tokens_gemini_today"] == 0
    assert summary["vision"]["estimated_tokens_today"] == 10000


def test_cycle_vision_budget_state_migrates_legacy_total(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path, viral_loop_vision_daily_token_budget=180000)
    # Same-day state written before the provider split: a bare total
    # of 175,000 with no per-provider keys. It must attribute to
    # Groq, so one more 5,000-token Groq-only call reaches the
    # 180,000 cap and the next candidate stops.
    _seed_vision_state(tmp_path, total=175000)
    pool = [_candidate(f"v{i}") for i in range(3)]
    vision = _FakeVision([_failed_other()] * 3)
    produce_calls: list[str] = []

    def produce(candidate):
        produce_calls.append(candidate.video_id)
        return {"status": "SKIPPED", "reason": "vision_unavailable"}

    _wire_vision_cycle(
        monkeypatch, settings, pool=pool, vision=vision, produce=produce,
    )
    summary = viral_loop.run_viral_loop_cycle(db)
    assert summary["stopped"] == "vision_daily_budget"
    assert produce_calls == ["v0"]
    assert summary["vision"]["estimated_tokens_groq_today"] == 180000
    assert summary["vision"]["estimated_tokens_gemini_today"] == 0
    assert summary["vision"]["estimated_tokens_today"] == 180000
