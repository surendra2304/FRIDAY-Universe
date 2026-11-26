"""TASK-FRD-045 — WOOP goal-setting template inside the goal loop.

Hermetic: fake executor/judge; the store is tmp_path-backed. Covers
WOOP normalisation, criteria/plan derivation, store wiring (WOOP record
stored on the loop, outcome-derived criteria, if-then steps), the
``start_goal_loop`` tool surface, and backwards compatibility (loops
without WOOP are unchanged).
"""

from __future__ import annotations

import pytest

from friday.autonomous.goal_loop import (
    STATUS_COMPLETED,
    GoalLoopStore,
    build_report,
    format_loop_summary,
)
from friday.autonomous.woop import (
    format_woop_summary,
    normalise_woop,
    woop_plan,
    woop_to_criteria,
)


def _woop(**overrides):
    record = {
        "wish": "Ship the weekly report every Friday by 5pm",
        "outcome": "The report is sent on time with zero follow-up questions",
        "obstacle": "I get pulled into meetings and lose the afternoon",
        "plan": [
            {"if": "a meeting lands on Friday afternoon", "then": "I draft the report Thursday evening"},
            {"if": "I feel stuck on the numbers", "then": "I ask FRIDAY for a draft from the data"},
        ],
    }
    record.update(overrides)
    return record


def _ok_executor(instruction: str):
    return True, (
        "Done. The report is sent on time with zero follow-up questions. "
        f"Instruction was: {instruction[:40]}"
    )


@pytest.fixture()
def store(tmp_path):
    return GoalLoopStore(store_path=str(tmp_path / "loops.json"))


# -- normalisation ------------------------------------------------------


def test_normalise_woop_accepts_full_record():
    woop = normalise_woop(_woop())
    assert woop["wish"].startswith("Ship the weekly")
    assert woop["outcome"].startswith("The report is sent")
    assert woop["obstacle"].startswith("I get pulled")
    assert woop["plan"][0] == {
        "if": "a meeting lands on Friday afternoon",
        "then": "I draft the report Thursday evening",
    }


def test_normalise_woop_rejects_missing_fields():
    for missing in ("wish", "outcome", "obstacle", "plan"):
        record = _woop()
        del record[missing]
        with pytest.raises(ValueError):
            normalise_woop(record)
    with pytest.raises(ValueError):
        normalise_woop(_woop(wish="   "))
    with pytest.raises(ValueError):
        normalise_woop(_woop(plan=[]))
    with pytest.raises(ValueError):
        normalise_woop("just a wish")


def test_normalise_woop_accepts_plain_string_plan_entries():
    woop = normalise_woop(_woop(plan=["Draft the report Thursday evening"]))
    assert woop["plan"] == [{"if": "", "then": "Draft the report Thursday evening"}]
    woop = normalise_woop(_woop(plan="Draft it Thursday"))
    assert len(woop["plan"]) == 1
    with pytest.raises(ValueError):
        normalise_woop(_woop(plan=[{"if": "something"}]))  # no 'then'


# -- derivation -----------------------------------------------------------


def test_outcome_becomes_judge_criterion():
    criteria = woop_to_criteria(normalise_woop(_woop()))
    assert len(criteria) == 1
    assert criteria[0]["check"] == "judge"
    assert "The report is sent on time" in criteria[0]["description"]


def test_plan_steps_cover_wish_plan_obstacle_and_criteria():
    woop = normalise_woop(_woop())
    steps = woop_plan(woop, woop_to_criteria(woop))
    text = "\n".join(s["instruction"] for s in steps)
    assert "Ship the weekly report" in text  # opener works the wish
    assert "if a meeting lands on Friday afternoon, then I draft the report Thursday evening" in text
    assert "if I feel stuck on the numbers, then I ask FRIDAY for a draft" in text
    assert "I get pulled into meetings" in text  # obstacle-watch step
    assert "Best outcome realised" in text  # per-criterion evidence step
    assert len(steps) == 1 + 2 + 1 + 1  # opener + plans + obstacle + criterion
    assert [s["id"] for s in steps] == ["s1", "s2", "s3", "s4", "s5"]


# -- store wiring ---------------------------------------------------------


def test_create_with_woop_derives_criteria_and_stores_record(store):
    loop = store.create(_woop()["wish"], [], woop=_woop())
    assert loop["woop"]["wish"] == _woop()["wish"]
    assert loop["woop"]["plan"][0]["then"] == "I draft the report Thursday evening"
    assert len(loop["criteria"]) == 1
    assert loop["criteria"][0]["description"].startswith("Best outcome realised:")
    assert len(loop["steps"]) == 5
    assert loop["status"] == "active"


def test_create_with_woop_and_explicit_criteria_keeps_both(store):
    explicit = [{"description": "Report sent", "check": "contains", "needle": "report"}]
    loop = store.create(_woop()["wish"], explicit, woop=_woop())
    assert loop["criteria"][0]["description"] == "Report sent"
    assert loop["woop"]["obstacle"].startswith("I get pulled")
    assert any("obstacle has appeared" in s["instruction"] for s in loop["steps"])


def test_create_with_bad_woop_raises_and_creates_nothing(store):
    with pytest.raises(ValueError):
        store.create("A wish", [], woop={"wish": "x"})
    assert store.list() == []


def test_woop_loop_completes_when_outcome_evidence_arrives(store):
    def judge(criterion, evidence):
        return ("sent on time" in evidence.lower()), "judged against evidence"

    loop = store.create(_woop()["wish"], [], woop=_woop(), max_cycles=2)
    done = store.run_until_terminal(loop["id"], executor=_ok_executor, judge=judge)
    assert done["status"] == STATUS_COMPLETED
    assert done["woop"]["wish"] == _woop()["wish"]
    assert "WOOP" in done["report"]
    assert "Obstacle: I get pulled into meetings" in done["report"]


def test_summary_and_report_carry_the_woop_record(store):
    loop = store.create(_woop()["wish"], [], woop=_woop())
    summary = format_loop_summary(loop)
    assert "WOOP" in summary
    assert "Ship the weekly report" in summary
    report = build_report(loop, [])
    assert "Wish: Ship the weekly report" in report


def test_format_woop_summary_plain_string_plan():
    woop = normalise_woop(_woop(plan=["Draft it Thursday"]))
    assert format_woop_summary(woop) == (
        "WOOP — Wish: Ship the weekly report every Friday by 5pm | "
        "Outcome: The report is sent on time with zero follow-up questions | "
        "Obstacle: I get pulled into meetings and lose the afternoon | "
        "Plan: Draft it Thursday"
    )


# -- tool surface -----------------------------------------------------------


def test_tool_round_trip_with_woop_only(tmp_path, monkeypatch):
    import friday.autonomous.goal_loop as gl
    from friday.tools.builtin.goal_loop_tools import GoalLoopStatusTool, StartGoalLoopTool

    monkeypatch.setattr(
        gl, "_default_store_path", lambda: str(tmp_path / "tool-loops.json")
    )
    start = StartGoalLoopTool().execute(
        goal=_woop()["wish"],
        woop=_woop(),
        run_now=False,
    )
    assert not start.is_error
    assert start.metadata["status"] == "active"
    status = GoalLoopStatusTool().execute(loop_id=start.metadata["loop_id"])
    assert not status.is_error
    assert "Ship the weekly report" in status.content
    assert "WOOP" in status.content


def test_tool_rejects_bad_woop(tmp_path, monkeypatch):
    import friday.autonomous.goal_loop as gl
    from friday.tools.builtin.goal_loop_tools import StartGoalLoopTool

    monkeypatch.setattr(
        gl, "_default_store_path", lambda: str(tmp_path / "tool-loops.json")
    )
    bad = StartGoalLoopTool().execute(goal="A wish", woop={"wish": "x"}, run_now=False)
    assert bad.is_error
    # No criteria and no WOOP is still an error, as before.
    bare = StartGoalLoopTool().execute(goal="A wish", criteria=[], run_now=False)
    assert bare.is_error


# -- backwards compatibility --------------------------------------------------


def test_loop_without_woop_is_unchanged(store):
    loop = store.create(
        "Draft the weekly report",
        [{"description": "A report exists", "check": "contains", "needle": "report"}],
    )
    assert "woop" not in loop
    assert len(loop["steps"]) == 2  # opener + one per-criterion step
    done = store.run_until_terminal(loop["id"], executor=_ok_executor)
    assert done["status"] == STATUS_COMPLETED
