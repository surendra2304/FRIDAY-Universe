"""TASK-VYR-001: the autopilot cycle's total wall-clock budget.

Before this task ``run_viral_autopilot.py`` had no bound at all: a cycle
could audition up to ten candidates (each a download + Whisper +
render) and then drain the publish queue for up to 1800s more, running
past the daemon's 6h interval while the next fire queued behind the
single-instance lock. The budget (settings
``viral_autopilot_cycle_budget_seconds``, default 5400s) is a
``time.monotonic()`` deadline handed from ``run_cycle`` to
``produce_one`` and ``drain_publish_queue``: no new audition or publish
job starts past it, so the cycle terminates.

The fake clock here is the whole point — a 60s budget is the smallest
the setting allows, and the clock lets the test prove the stop without
waiting a minute. A single in-flight audition is a blocking call with
no deadline of its own, so the guarantee is deliberately scoped to
"starts nothing new past the deadline", not "never exceeds the
budget by a second".
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.services.viral_discovery import Candidate
from scripts import run_viral_autopilot as autopilot


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
        "viral_autopilot_cycle_budget_seconds": 60,
        "youtube_cookies_file": cookies,
    }
    values.update(overrides)
    return Settings(**values)


def _candidate(video_id: str) -> Candidate:
    return Candidate(
        video_id=video_id, title=f"Video {video_id}", channel="Chan",
        duration=30.0, view_count=900_000, like_count=1000,
        upload_date="20261101", license="transformative_commentary",
        category="SPORTS", hook="WAIT FOR IT", score=10.0,
    )


def _wire(monkeypatch, settings, db, *, pool, clock, advance, produce_status):
    """Stub everything produce_one touches except the budget logic."""
    calls: list[str] = []
    rejected: list[tuple[str, str]] = []
    monkeypatch.setattr(autopilot, "cookies_file", lambda: Path("/tmp/cookies.txt"))
    monkeypatch.setattr(autopilot, "used_source_video_ids", lambda db: set())
    monkeypatch.setattr(autopilot, "discover_candidates_api", lambda **kw: list(pool))
    monkeypatch.setattr(autopilot, "discover_candidates", lambda **kw: [])
    monkeypatch.setattr(autopilot, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        autopilot, "_record_rejection",
        lambda video_id, reason: rejected.append((video_id, reason)),
    )

    def fake_produce(candidate, db, *, publish=True, hold_for_review=False):
        calls.append(candidate.video_id)
        clock["now"] += advance
        if produce_status == "QUEUED_FOR_PUBLISH":
            return {
                "status": "QUEUED_FOR_PUBLISH",
                "publish_job_id": 1,
                "edit_mode": "commentary",
            }
        return {"status": "REJECTED", "reason": "quality_gate"}

    monkeypatch.setattr(autopilot, "produce_viral_short", fake_produce)
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    return calls, rejected


def _args(**overrides):
    values = {"max_candidates": 10, "timeout": 1800, "cycle_budget": 0}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_budget_stops_auditions_mid_pool(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"vid{i}") for i in range(5)]
    clock = {"now": 0.0}
    calls, rejected = _wire(
        monkeypatch, settings, db, pool=pool, clock=clock,
        advance=40.0, produce_status="REJECTED",
    )
    result = autopilot.produce_one(settings, max_candidates=10, deadline=60.0)
    # t=0 audition 1 (t=40), t=40 audition 2 (t=80), t=80 past the
    # deadline: the third audition never starts.
    assert result["status"] == "CYCLE_BUDGET_EXCEEDED"
    assert calls == ["vid0", "vid1"]
    assert len(result["attempts"]) == 2
    assert rejected == [("vid0", "quality_gate"), ("vid1", "quality_gate")]


def test_budget_already_exceeded_attempts_nothing(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"vid{i}") for i in range(5)]
    clock = {"now": 100.0}
    calls, _ = _wire(
        monkeypatch, settings, db, pool=pool, clock=clock,
        advance=40.0, produce_status="REJECTED",
    )
    result = autopilot.produce_one(settings, max_candidates=10, deadline=60.0)
    assert result == {"status": "CYCLE_BUDGET_EXCEEDED", "attempts": []}
    assert calls == []


def test_no_deadline_preserves_unbounded_behaviour(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"vid{i}") for i in range(5)]
    clock = {"now": 0.0}
    calls, _ = _wire(
        monkeypatch, settings, db, pool=pool, clock=clock,
        advance=40.0, produce_status="REJECTED",
    )
    result = autopilot.produce_one(settings, max_candidates=10)
    assert result["status"] == "ALL_CANDIDATES_REJECTED"
    assert calls == [f"vid{i}" for i in range(5)]


def test_drain_capped_by_remaining_budget(tmp_path, db, monkeypatch):
    import app.worker as worker

    clock = {"now": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(time, "sleep", lambda s: None)
    worked = []
    monkeypatch.setattr(worker, "run_once", lambda: worked.append(1) or False)
    # Deadline already passed: the drain must not start a job at all.
    result = autopilot.drain_publish_queue(timeout_seconds=1800, deadline=-1.0)
    assert result["jobs_processed"] == 0
    assert worked == []
    assert result["seconds"] < 1.0
    # 0.05s of budget left: the drain still runs, but it stops on the
    # remaining budget, not on its 1800s timeout.
    result = autopilot.drain_publish_queue(timeout_seconds=1800, deadline=0.05)
    assert result["jobs_processed"] == 0
    assert result["seconds"] < 1.0
    # With the full budget left the drain still runs until the queue
    # stays idle (run_once False three times, sleeps stubbed out).
    worked.clear()
    result = autopilot.drain_publish_queue(timeout_seconds=1800, deadline=60.0)
    assert result["jobs_processed"] == 0
    assert len(worked) == 3


def test_run_cycle_wires_deadline_and_reports_elapsed(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"vid{i}") for i in range(5)]
    clock = {"now": 0.0}
    calls, _ = _wire(
        monkeypatch, settings, db, pool=pool, clock=clock,
        advance=30.0, produce_status="QUEUED_FOR_PUBLISH",
    )
    monkeypatch.setattr(autopilot, "_snapshot_ypp", lambda settings: None)
    drains: list[dict] = []
    monkeypatch.setattr(
        autopilot, "drain_publish_queue",
        lambda *, timeout_seconds, deadline: drains.append(
            {"timeout_seconds": timeout_seconds, "deadline": deadline}
        ) or {"jobs_processed": 1, "seconds": 0.0},
    )
    result = autopilot.run_cycle(settings, _args())
    assert result["status"] == "PRODUCED"
    assert result["budget_seconds"] == 60
    assert result["seconds"] == 30.0
    assert calls == ["vid0"]
    # The drain inherits the same deadline (t=60), not a fresh 1800s.
    assert drains == [{"timeout_seconds": 1800, "deadline": 60.0}]


def test_run_cycle_budget_exceeded_skips_drain(tmp_path, db, monkeypatch):
    settings = _settings(tmp_path)
    pool = [_candidate(f"vid{i}") for i in range(5)]
    clock = {"now": 0.0}
    _wire(
        monkeypatch, settings, db, pool=pool, clock=clock,
        advance=40.0, produce_status="REJECTED",
    )
    monkeypatch.setattr(autopilot, "_snapshot_ypp", lambda settings: None)
    drains: list[dict] = []
    monkeypatch.setattr(
        autopilot, "drain_publish_queue",
        lambda **kw: drains.append(kw) or {"jobs_processed": 0, "seconds": 0.0},
    )
    result = autopilot.run_cycle(settings, _args())
    assert result["status"] == "CYCLE_BUDGET_EXCEEDED"
    assert result["budget_seconds"] == 60
    assert result["seconds"] == 80.0
    assert drains == []
