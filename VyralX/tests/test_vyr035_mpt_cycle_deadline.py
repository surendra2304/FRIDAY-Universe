"""TASK-VYR-035: the autopilot cycle deadline in the MPT lane.

VYR-001's audit found the cycle deadline is not checked in the MPT
lane: ``produce_one`` returned from ``produce_from_briefs`` before the
audition loop, so a long MPT run — each brief is an MPT subprocess
render plus the five quality gates — could overrun the cycle budget
unchecked. The fix hands the same ``time.monotonic()`` deadline to the
MPT lane, which checks it before every brief and stops with
``CYCLE_BUDGET_EXCEEDED`` instead of starting another render.

The fake clock here is the whole point — a 60s budget is the smallest
the setting allows, and the clock lets the test prove the stop without
waiting a minute. A single in-flight MPT run is a blocking subprocess
call with no deadline of its own, so the guarantee is deliberately
scoped to "starts nothing new past the deadline", not "never exceeds
the budget by a second" — the same scope as the native lane's
test_vyr001_autopilot_cycle_budget.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import mpt_lane as ml
from scripts import run_viral_autopilot as autopilot


def _settings(tmp_path: Path, **overrides) -> SimpleNamespace:
    base = dict(
        viral_producer_lane="mpt",
        viral_mpt_lane_enabled=True,
        viral_mpt_briefs_path="",
        data_dir=tmp_path / "data",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _briefs_file(tmp_path: Path, settings: SimpleNamespace, count: int = 5) -> Path:
    path = tmp_path / "briefs.json"
    path.write_text(json.dumps([
        {"topic": f"Topic {i}", "script": f"Script {i} " * 8, "title": f"Title {i}"}
        for i in range(count)
    ]), encoding="utf-8")
    settings.viral_mpt_briefs_path = str(path)
    return path


def _wire(monkeypatch, *, clock, advance, produce_status="SKIPPED"):
    """Stub produce_mpt_short: record each attempted brief and advance
    the fake clock as if the render + gates took ``advance`` seconds."""
    calls: list[str] = []

    def fake_produce(brief, settings, runner=None):
        calls.append(brief.topic)
        clock["now"] += advance
        if produce_status == "GATED_PASS":
            return {"status": "GATED_PASS", "lane": "mpt", "task_id": "fake"}
        return {"status": "SKIPPED", "reason": "script_unverifiable", "lane": "mpt"}

    monkeypatch.setattr(ml, "produce_mpt_short", fake_produce)
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    return calls


def test_deadline_stops_briefs_mid_file(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _briefs_file(tmp_path, settings, count=5)
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, clock=clock, advance=40.0)
    result = ml.produce_from_briefs(settings, max_candidates=10, deadline=60.0)
    # t=0 brief 1 (t=40), t=40 brief 2 (t=80), t=80 past the
    # deadline: the third brief never starts.
    assert result["status"] == "CYCLE_BUDGET_EXCEEDED"
    assert calls == ["Topic 0", "Topic 1"]
    assert len(result["attempts"]) == 2
    assert all(a["status"] == "SKIPPED" for a in result["attempts"])


def test_deadline_already_exceeded_attempts_nothing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _briefs_file(tmp_path, settings, count=5)
    clock = {"now": 100.0}
    calls = _wire(monkeypatch, clock=clock, advance=40.0)
    result = ml.produce_from_briefs(settings, max_candidates=10, deadline=60.0)
    assert result == {"status": "CYCLE_BUDGET_EXCEEDED", "attempts": []}
    assert calls == []


def test_no_deadline_preserves_unbounded_behaviour(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _briefs_file(tmp_path, settings, count=5)
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, clock=clock, advance=40.0)
    result = ml.produce_from_briefs(settings, max_candidates=10)
    assert result["status"] == "ALL_BRIEFS_REJECTED"
    assert calls == [f"Topic {i}" for i in range(5)]


def test_gated_pass_before_deadline_still_returns(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _briefs_file(tmp_path, settings, count=5)
    clock = {"now": 0.0}
    calls = _wire(monkeypatch, clock=clock, advance=10.0,
                  produce_status="GATED_PASS")
    result = ml.produce_from_briefs(settings, max_candidates=10, deadline=60.0)
    assert result["status"] == "GATED_PASS"
    assert calls == ["Topic 0"]
    assert len(result["attempts"]) == 1


def test_produce_one_passes_deadline_to_mpt_lane(tmp_path, monkeypatch):
    """The autopilot hands its cycle deadline to the MPT lane instead
    of returning before the deadline is ever consulted."""
    settings = _settings(tmp_path)
    _briefs_file(tmp_path, settings, count=5)
    seen: dict = {}

    def fake_produce_from_briefs(s, *, max_candidates, deadline=None):
        seen["max_candidates"] = max_candidates
        seen["deadline"] = deadline
        return {"status": "GATED_PASS", "result": {"status": "GATED_PASS"},
                "attempts": []}

    monkeypatch.setattr(ml, "produce_from_briefs", fake_produce_from_briefs)
    result = autopilot.produce_one(settings, max_candidates=3, deadline=123.0)
    assert seen == {"max_candidates": 3, "deadline": 123.0}
    assert result["status"] == "GATED_PASS"
