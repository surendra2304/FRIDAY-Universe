"""TASK-IG-FRG-06: loop-until-done + structured plan-to-ship workflow.

Corpus source: DdeTgRuE4yq (Ralph Loop + GSD Core).
Pinned properties: the loop is bounded and its terminal states are
honest — DONE only when every phase passed, BLOCKED stops at once,
EXHAUSTED is reported as exhaustion (never as success), later phases
never run after a stop, and an unjudgeable plan is refused up front.
"""
from __future__ import annotations

import pytest

from app.planning.plan_to_ship import (
    LoopOutcome,
    PhaseResult,
    ShipPhase,
    ShipPlan,
    default_ship_plan,
    run_plan,
)


def _plan(**kwargs) -> ShipPlan:
    return ShipPlan(
        name="test-plan",
        phases=(
            ShipPhase("one", "g1", ("c1",), max_attempts=3),
            ShipPhase("two", "g2", ("c2",), max_attempts=2),
        ),
        **kwargs,
    )


def test_all_pass_first_try_is_done():
    report = run_plan(_plan(), lambda phase, attempt: PhaseResult(passed=True))
    assert report.outcome is LoopOutcome.DONE
    assert report.total_attempts == 2
    assert [r.outcome for r in report.records] == ["passed", "passed"]


def test_flaky_phase_retries_then_done():
    def step(phase, attempt):
        if phase.name == "one" and attempt < 3:
            return PhaseResult(passed=False, detail="tests red")
        return PhaseResult(passed=True)

    report = run_plan(_plan(), step)
    assert report.outcome is LoopOutcome.DONE
    assert report.records[0].attempts == 3
    assert "tests red" in report.records[0].details[0]


def test_never_passing_phase_is_exhausted_not_done():
    calls = []

    def step(phase, attempt):
        calls.append(phase.name)
        return PhaseResult(passed=False, detail="still red")

    report = run_plan(_plan(), step)
    assert report.outcome is LoopOutcome.EXHAUSTED
    assert report.records[0].attempts == 3  # exactly the cap
    assert report.records[1].attempts == 0  # later phase never attempted
    assert calls == ["one", "one", "one"]
    assert "not as done" in report.stop_reason


def test_blocker_stops_immediately():
    def step(phase, attempt):
        return PhaseResult(passed=False, blocked=True, detail="needs API key")

    report = run_plan(_plan(), step)
    assert report.outcome is LoopOutcome.BLOCKED
    assert report.total_attempts == 1
    assert "needs API key" in report.stop_reason


def test_whole_run_cap_is_honoured():
    plan = _plan(max_total_attempts=2)
    report = run_plan(plan, lambda phase, attempt: PhaseResult(passed=False))
    assert report.outcome is LoopOutcome.EXHAUSTED
    assert report.total_attempts == 2
    assert "whole-run attempt cap" in report.stop_reason


def test_invalid_plans_are_refused():
    with pytest.raises(ValueError):
        run_plan(ShipPlan("x", ()), lambda p, a: PhaseResult(passed=True))
    with pytest.raises(ValueError):  # phase with no criteria cannot be judged
        run_plan(
            ShipPlan("x", (ShipPhase("p", "g", ()),)),
            lambda p, a: PhaseResult(passed=True),
        )
    with pytest.raises(ValueError):  # duplicate phase names
        run_plan(
            ShipPlan(
                "x",
                (ShipPhase("p", "g", ("c",)), ShipPhase("p", "g2", ("c",))),
            ),
            lambda p, a: PhaseResult(passed=True),
        )
    with pytest.raises(ValueError):  # cap below 1
        run_plan(
            ShipPlan("x", (ShipPhase("p", "g", ("c",), max_attempts=0),)),
            lambda p, a: PhaseResult(passed=True),
        )


def test_default_plan_shape():
    plan = default_ship_plan()
    assert plan.validate() == []
    assert [p.name for p in plan.phases] == ["plan", "build", "verify", "ship"]
    for phase in plan.phases:
        assert phase.acceptance, phase.name


def test_report_is_serialisable():
    report = run_plan(_plan(), lambda phase, attempt: PhaseResult(passed=True))
    data = report.to_dict()
    assert data["outcome"] == "DONE"
    assert data["phases"][0]["phase"] == "one"
