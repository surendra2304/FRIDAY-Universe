"""TASK-VYR-036: the autonomous loop's wall-clock budget.

Before this task ``scripts/autonomous_loop.py`` had no bound at all: a
cycle could render up to ``batch_size`` candidates (each a voiceover +
render + upload) and run unbounded past the daemon's 180-minute
interval while the next fire queued behind it. The budget
(``DEFAULT_CYCLE_BUDGET_SECONDS``, 5400s — the same default as the
autopilot's ``viral_autopilot_cycle_budget_seconds``, TASK-VYR-001) is
a ``time.monotonic()`` deadline: no new render starts past it, so the
cycle terminates.

The fake clock here is the whole point — a 5400s budget is far too
long to wait out, and the clock lets the test prove the stop without
waiting. A single in-flight render is a blocking call with no deadline
of its own, so the guarantee is deliberately scoped to "starts nothing
new past the deadline", not "never exceeds the budget by a second" —
the same scope as the native lane's
test_vyr001_autopilot_cycle_budget.py and TASK-VYR-035's
test_vyr035_mpt_cycle_deadline.py.
"""
from __future__ import annotations

import time
from pathlib import Path

from scripts import autonomous_loop as al


def _catalog(count: int = 5) -> dict[str, dict]:
    return {
        f"vid{i}": {"title": f"Video {i}", "topic": f"topic {i}"}
        for i in range(count)
    }


def _fake_learner():
    """Deterministic stand-in: hands out candidates in catalog order."""

    class FakeLearner:
        def refresh_and_learn(self, manifest):
            return {
                "total_cycles": 1,
                "total_drafts_created": 0,
                "active_topic_weights": {},
            }

        def select_weighted_candidate(self, candidates, processed_ids):
            for entry in candidates:
                if entry["id"] not in processed_ids:
                    return entry, 1.0
            return None, 1.0

    return FakeLearner()


def _wire(monkeypatch, tmp_path, *, clock, advance, count=5):
    """Stub everything run_autonomous_cycle touches except the budget logic."""
    for i in range(count):
        source = tmp_path / "media" / "viral_sources" / f"vid{i}.mp4"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "MASTER_CATALOG", _catalog(count))
    monkeypatch.setattr(al, "AudienceReachLearner", lambda: _fake_learner())
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

    calls: list[str] = []

    def fake_render(vid, conf):
        calls.append(vid)
        clock["now"] += advance
        return {"watch_url": f"https://www.youtube.com/shorts/{vid}", "video_id": vid}

    monkeypatch.setattr(al, "render_and_draft_video", fake_render)
    return calls


def test_deadline_stops_renders_mid_batch(tmp_path, monkeypatch):
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, tmp_path, clock=clock, advance=3000.0)
    results = al.run_autonomous_cycle(batch_size=5, deadline=5400.0)
    # t=0 render vid0 (t=3000), t=3000 render vid1 (t=6000), t=6000 past
    # the deadline: vid2 never starts.
    assert calls == ["vid0", "vid1"]
    assert [r["video_id"] for r in results] == ["vid0", "vid1"]


def test_deadline_already_exceeded_renders_nothing(tmp_path, monkeypatch):
    clock = {"now": 6000.0}
    calls = _wire(monkeypatch, tmp_path, clock=clock, advance=3000.0)
    results = al.run_autonomous_cycle(batch_size=5, deadline=5400.0)
    assert results == []
    assert calls == []


def test_no_deadline_uses_default_budget(tmp_path, monkeypatch):
    # The live driver calls run_autonomous_cycle with no deadline, so the
    # default budget must bound the cycle on its own.
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, tmp_path, clock=clock, advance=3000.0)
    results = al.run_autonomous_cycle(batch_size=5)
    assert calls == ["vid0", "vid1"]
    assert [r["video_id"] for r in results] == ["vid0", "vid1"]


def test_within_budget_renders_full_batch(tmp_path, monkeypatch):
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, tmp_path, clock=clock, advance=500.0)
    results = al.run_autonomous_cycle(batch_size=5, deadline=5400.0)
    assert calls == [f"vid{i}" for i in range(5)]
    assert len(results) == 5
