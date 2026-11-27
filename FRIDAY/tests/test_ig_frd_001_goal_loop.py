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


# --- TASK-IG-FRD-001-FIX-01: brain-route executor + terminal reply ---


def _stub_brain(monkeypatch, fn):
    """Stand in ``friday.api.server._run_brain_sync`` with a fake brain.

    The executor lazy-imports the server module, so stubbing it in
    sys.modules is enough — the real (heavy) server module is never
    imported by these tests.
    """
    import sys
    import types

    stub = types.ModuleType("friday.api.server")
    stub._run_brain_sync = fn
    monkeypatch.setitem(sys.modules, "friday.api.server", stub)


def test_default_executor_routes_through_brain(monkeypatch):
    from friday.autonomous.goal_loop import _default_executor

    seen = []

    def fake_brain(instruction):
        seen.append(instruction)
        return {
            "reply": "Created notes/goal-90e54d3f66.md. note created.",
            "metadata": {"success": True},
        }

    _stub_brain(monkeypatch, fake_brain)
    ok, out = _default_executor("Work on this goal and report concrete progress: X")
    assert ok is True
    assert "note created" in out
    assert seen == ["Work on this goal and report concrete progress: X"]


def test_default_executor_refusal_is_honest_failure(monkeypatch):
    from friday.autonomous.goal_loop import _default_executor

    def refusing_brain(instruction):
        return {"reply": "", "metadata": {"refused": True, "error": "blocked"}}

    _stub_brain(monkeypatch, refusing_brain)
    ok, out = _default_executor("Do the thing")
    assert ok is False
    assert "blocked" in out


def test_default_executor_timeout_is_failure_not_success(monkeypatch):
    # The chat endpoint reports a timed-out turn as metadata.success=False
    # with NO top-level flag — the mission queue's top-level-only check
    # would score that as a success. The executor must not.
    from friday.autonomous.goal_loop import _default_executor

    def timing_out_brain(instruction):
        return {
            "reply": "That request is still running after 300 seconds, Boss.",
            "metadata": {"success": False, "timeout": True, "error": "chat_timeout"},
        }

    _stub_brain(monkeypatch, timing_out_brain)
    ok, out = _default_executor("Do the thing")
    assert ok is False
    # The timeout reply itself is the evidence; the error code is what is
    # returned when the brain has no reply text at all.
    assert "still running" in out

    def silent_timeout_brain(instruction):
        return {"reply": "", "metadata": {"success": False, "timeout": True, "error": "chat_timeout"}}

    _stub_brain(monkeypatch, silent_timeout_brain)
    ok2, out2 = _default_executor("Do the thing")
    assert ok2 is False
    assert "chat_timeout" in out2


def test_default_executor_unavailable_brain_is_failure(monkeypatch):
    import sys
    import types

    from friday.autonomous.goal_loop import _default_executor

    stub = types.ModuleType("friday.api.server")  # no _run_brain_sync attr
    monkeypatch.setitem(sys.modules, "friday.api.server", stub)
    ok, out = _default_executor("Do the thing")
    assert ok is False
    assert "brain executor unavailable" in out


def test_tool_loop_completes_leg1_repro(tmp_path, monkeypatch):
    # FRD-051 leg-1 repro (goal-90e54d3f66 shape): a natural-language goal
    # whose steps the OLD shell executor rejected ("Command 'work'/'for'
    # is not allowed"). Through the brain the same steps complete and the
    # tool returns the terminal report as a terminal reply.
    import friday.autonomous.goal_loop as gl
    from friday.tools.builtin.goal_loop_tools import StartGoalLoopTool

    monkeypatch.setattr(
        gl, "_default_store_path", lambda: str(tmp_path / "tool-loops.json")
    )

    def fake_brain(instruction):
        return {
            "reply": "Created notes/goal-90e54d3f66.md with the requested content. note created.",
            "metadata": {"success": True},
        }

    _stub_brain(monkeypatch, fake_brain)
    result = StartGoalLoopTool().execute(
        goal="Create a note file about the goal loop",
        criteria=[
            {"description": "Note file created", "check": "contains", "needle": "note created"}
        ],
        run_now=True,
    )
    assert not result.is_error
    assert result.metadata["status"] == "completed"
    assert result.metadata["terminal_reply"] is True
    assert "COMPLETED" in result.content


def test_start_goal_loop_tool_timeout_fits_brain_loop():
    from friday.tools.builtin.goal_loop_tools import StartGoalLoopTool

    # Each step is a full chat-brain turn; the 30s default cannot hold a
    # multi-step loop. 240s stays inside the 300s chat-turn budget.
    assert StartGoalLoopTool.timeout == 240


def test_terminal_reply_helper():
    from friday.agent.agent import _terminal_reply
    from friday.core.types import ToolResult

    terminal = ToolResult(
        name="start_goal_loop",
        content="Goal loop goal-x — COMPLETED",
        metadata={"terminal_reply": True},
    )
    assert _terminal_reply(terminal) == "Goal loop goal-x — COMPLETED"
    unmarked = ToolResult(name="x", content="hi", metadata={})
    assert _terminal_reply(unmarked) is None
    errored = ToolResult(
        name="start_goal_loop",
        content="boom",
        is_error=True,
        metadata={"terminal_reply": True},
    )
    assert _terminal_reply(errored) is None
    assert _terminal_reply(None) is None


def test_default_executor_reads_jsonresponse_body(monkeypatch):
    # Live 2026-11-27: a failed nested turn comes back from
    # _run_brain_sync as a JSONResponse (502), not a dict — the first
    # version of this executor called .get() on it and crashed the
    # whole tool call mid-cycle. The response body carries the same
    # dispatch dict; read it.
    import json

    from friday.autonomous.goal_loop import _default_executor

    class _FakeResponse:
        def __init__(self, payload):
            self.body = json.dumps(payload).encode("utf-8")

    def failing_brain(instruction):
        return _FakeResponse(
            {
                "reply": "LLM generation failed.",
                "metadata": {"success": False, "error": "LLMProviderError"},
            }
        )

    _stub_brain(monkeypatch, failing_brain)
    ok, out = _default_executor("Do the thing")
    assert ok is False
    assert "LLMProviderError" in out

    def ok_brain(instruction):
        return _FakeResponse({"reply": "done it", "metadata": {"success": True}})

    _stub_brain(monkeypatch, ok_brain)
    ok2, out2 = _default_executor("Do the thing")
    assert ok2 is True
    assert out2 == "done it"


def test_default_executor_unreadable_result_is_failure(monkeypatch):
    from friday.autonomous.goal_loop import _default_executor

    _stub_brain(monkeypatch, lambda instruction: object())
    ok, out = _default_executor("Do the thing")
    assert ok is False
    assert "brain executor error" in out


def test_raising_executor_fails_step_not_loop(store):
    # Defense in depth: an executor that raises must fail the step
    # (and, after attempts, block the loop) — never abort the run.
    def raising_executor(instruction: str):
        raise RuntimeError("boom")

    loop = store.create("Do the thing", _contains_criteria(), max_cycles=5)
    done = store.run_until_terminal(loop["id"], executor=raising_executor)
    assert done["status"] == STATUS_BLOCKED
    assert any(s["status"] == "failed" for s in done["steps"])
    assert "executor error" in done["steps"][0]["result"]
