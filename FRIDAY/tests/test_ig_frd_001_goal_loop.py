"""TASK-IG-FRD-001 — goal-loop autonomy tests (hermetic: fake executor/judge)."""

from __future__ import annotations

import pytest

from friday.autonomous.goal_loop import (
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    GoalLoopStore,
    build_report,
    evaluate_criterion,
    normalise_criterion,
)


@pytest.fixture()
def store(tmp_path):
    return GoalLoopStore(store_path=str(tmp_path / "loops.json"))


def _ok_executor(instruction: str):
    return True, f"Done. Evidence: report drafted and saved. Instruction was: {instruction[:40]}"


def _contains_criteria():
    return [
        {"description": "A report exists", "check": "contains", "needle": "report drafted"},
        {"description": "No fabricated claims", "check": "not_contains", "needle": "guaranteed profit"},
    ]


def test_create_requires_goal_and_criteria(store):
    with pytest.raises(ValueError):
        store.create("", _contains_criteria())
    with pytest.raises(ValueError):
        store.create("A goal", [])


def test_normalise_criterion_rejects_bad_check():
    with pytest.raises(ValueError):
        normalise_criterion({"description": "x", "check": "vibes"}, 0)
    with pytest.raises(ValueError):
        normalise_criterion({"description": "x", "check": "contains"}, 0)  # no needle
    plain = normalise_criterion("just do it well", 0)
    assert plain["check"] == "judge"


def test_loop_completes_when_all_criteria_met(store):
    loop = store.create("Draft the weekly report", _contains_criteria(), max_cycles=3)
    done = store.run_until_terminal(loop["id"], executor=_ok_executor)
    assert done["status"] == STATUS_COMPLETED
    assert done["cycles_run"] == 1
    assert "COMPLETED" in done["report"]
    assert "[MET]" in done["report"]


def test_loop_fails_honestly_when_evidence_never_arrives(store):
    def empty_executor(instruction: str):
        return True, "I looked around but found nothing."

    loop = store.create("Find the thing", _contains_criteria(), max_cycles=2)
    done = store.run_until_terminal(loop["id"], executor=empty_executor)
    assert done["status"] == STATUS_FAILED
    assert done["cycles_run"] == 2
    assert "[UNMET]" in done["report"]


def test_step_failure_blocks_loop_after_attempts(store):
    def broken_executor(instruction: str):
        return False, "brain refused: tool unavailable"

    loop = store.create("Do the thing", _contains_criteria(), max_cycles=5)
    done = store.run_until_terminal(loop["id"], executor=broken_executor)
    assert done["status"] == STATUS_BLOCKED
    assert any(s["status"] == "failed" for s in done["steps"])


def test_manual_criterion_blocks_until_owner_confirms(store):
    criteria = _contains_criteria() + [
        {"description": "Owner is happy with it", "check": "manual"}
    ]
    loop = store.create("Draft + owner sign-off", criteria, max_cycles=3)
    done = store.run_until_terminal(loop["id"], executor=_ok_executor)
    assert done["status"] == STATUS_BLOCKED
    # Owner confirmation is the only way the manual criterion is met.
    store.confirm_criterion(loop["id"], "c3")
    loop2 = store.get(loop["id"])
    evals = [e for e in loop2["evaluations"] if e["criterion_id"] == "c3"]
    assert evals[-1]["met"] is True
    assert "owner" in evals[-1]["why"]


def test_judge_criterion_uses_injected_judge(store):
    def judge(criterion, evidence):
        return ("report" in evidence.lower()), "judged against evidence"

    loop = store.create(
        "Write something report-like",
        ["The output reads like a report"],
        max_cycles=2,
    )
    done = store.run_until_terminal(loop["id"], executor=_ok_executor, judge=judge)
    assert done["status"] == STATUS_COMPLETED


def test_judge_criterion_without_judge_is_unmet_not_faked(store):
    ev = evaluate_criterion(
        {"id": "c1", "description": "quality", "check": "judge", "needle": ""},
        "some evidence",
        judge=None,
    )
    assert ev["met"] is False
    assert "no judge" in ev["why"]


def test_registry_survives_reopen(tmp_path):
    path = str(tmp_path / "loops.json")
    s1 = GoalLoopStore(store_path=path)
    loop = s1.create("Persist me", _contains_criteria())
    s2 = GoalLoopStore(store_path=path)
    assert s2.get(loop["id"])["goal"] == "Persist me"
    assert len(s2.list()) == 1


def test_report_names_unmet_criteria(store):
    loop = store.create("X", _contains_criteria(), max_cycles=1)
    done = store.run_until_terminal(loop["id"], executor=lambda i: (True, "nothing here"))
    report = build_report(done, done["evaluations"][-2:])
    assert "A report exists" in report
    assert "UNMET" in report


def test_tools_round_trip(tmp_path, monkeypatch):
    import friday.autonomous.goal_loop as gl
    from friday.tools.builtin.goal_loop_tools import GoalLoopStatusTool, StartGoalLoopTool

    monkeypatch.setattr(
        gl, "_default_store_path", lambda: str(tmp_path / "tool-loops.json")
    )
    # Register-only (run_now False) so no real brain is invoked.
    start = StartGoalLoopTool().execute(
        goal="Prepare the demo checklist",
        criteria=[{"description": "Checklist exists", "check": "contains", "needle": "checklist"}],
        run_now=False,
    )
    assert not start.is_error
    assert start.metadata["status"] == "active"
    status = GoalLoopStatusTool().execute(loop_id=start.metadata["loop_id"])
    assert not status.is_error
    assert "Prepare the demo checklist" in status.content
    bad = StartGoalLoopTool().execute(goal="", criteria=[])
    assert bad.is_error
