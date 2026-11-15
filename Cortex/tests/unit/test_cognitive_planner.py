"""Unit tests for the goal-aware cognitive planner (TASK-COR-005).

These tests lock in the behaviours the plan-quality review demanded
after finding that /plan and /decompose returned one fixed template
for every goal:

* different goals produce different, executor-aligned plans;
* high-impact operations carry an approval-gate step, ordered the
  way the governed executor orders it;
* read-only goals get no execution/approval steps;
* unidentifiable goals degrade honestly (plannable=False) instead of
  fabricating an execution graph;
* decompose honours max_subtasks by reported merging, never by
  silent truncation or filler;
* durations are labelled phase budgets, not measurements.
"""

from __future__ import annotations

import pytest
from cortex_api.cognitive_planner import (
    _HIGH_IMPACT_MIRROR,
    build_decomposition,
    build_plan,
)


def _actions(plan):
    return [s["action"] for s in plan["steps"]]


def test_goal_sensitivity_two_goals_differ():
    health = build_plan(
        "Compile a health summary for site_storefront",
        {"property_id": "site_storefront", "operation": "health_summary"},
    )
    billing = build_plan(
        "Change subscription pricing for the storefront",
        {"property_id": "site_storefront", "operation": "pricing_change"},
    )
    assert _actions(health) != _actions(billing)
    assert health["operation"] == "health_summary"
    assert billing["operation"] == "pricing_change"


def test_high_impact_execute_plan_has_approval_before_execution():
    plan = build_plan(
        "Change subscription pricing for the storefront",
        {"operation": "pricing_change"},
    )
    actions = _actions(plan)
    assert plan["is_high_impact"] is True
    assert plan["impact_category"] == "billing"
    assert "await_supervisor_approval" in actions
    assert actions.index("await_supervisor_approval") < actions.index("execute_operation")
    assert "capture_pre_execution_snapshot" in actions
    assert "measure_outcome" in actions


def test_preapproved_high_impact_skips_approval_step():
    plan = build_plan(
        "Publish the new landing page",
        {"operation": "content_publish", "approved": True},
    )
    assert "await_supervisor_approval" not in _actions(plan)
    assert "execute_operation" in _actions(plan)


def test_production_execute_plan_includes_sentinel_gate():
    plan = build_plan(
        "Publish the new landing page",
        {"operation": "content_publish", "environment": "production"},
    )
    assert "sentinel_security_gate" in _actions(plan)


def test_read_only_plan_has_no_execution_or_approval():
    plan = build_plan(
        "Compile a health summary for site_storefront",
        {"operation": "health_summary"},
    )
    actions = _actions(plan)
    assert "execute_operation" not in actions
    assert "await_supervisor_approval" not in actions
    assert actions[-1] == "record_provenance"


def test_recommend_flow_approval_comes_after_recommendation():
    plan = build_plan(
        "Recommend an intervention for falling mobile conversion",
        {"proposed_operation": "banner_injection"},
    )
    actions = _actions(plan)
    assert plan["operation"] == "banner_injection"
    assert actions.index("observe_current_state") < actions.index("recommend_intervention")
    assert actions.index("recommend_intervention") < actions.index("await_supervisor_approval")


def test_telemetry_context_routes_to_recommend_not_pricing_change():
    """A pricing *page* plus bounce-rate telemetry is a recommend
    request; the old keyword trap (bare 'pricing') must not fire."""
    plan = build_plan(
        "Optimize visitor conversion on pricing page",
        {"page": "/pricing", "bounce_rate": 0.45},
    )
    assert plan["operation"] == "banner_injection"
    assert plan["operation_source"] == "telemetry_context_executor_default"
    assert "recommend_intervention" in _actions(plan)


def test_unresolvable_goal_degrades_honestly():
    plan = build_plan("Book a flight to Tokyo and summarise the Stratex demo ledger", {})
    assert plan["plannable"] is False
    assert plan["operation"] is None
    assert plan["unplannable_reason"]
    assert "execute_operation" not in _actions(plan)
    assert _actions(plan)[-1] == "identify_operation"


def test_every_step_has_expected_outcome_and_budget_basis():
    plan = build_plan("Publish the new landing page", {"operation": "content_publish"})
    assert plan["estimate_basis"] == "phase_budget_unmeasured"
    assert plan["planner"]["template_free"] is True
    for step in plan["steps"]:
        assert step["expected_outcome"]
        assert isinstance(step["estimated_duration_sec"], int)
    assert plan["estimated_duration_sec"] == sum(
        s["estimated_duration_sec"] for s in plan["steps"]
    )


def test_dependencies_form_a_linear_chain():
    plan = build_plan("Publish the new landing page", {"operation": "content_publish"})
    for idx, step in enumerate(plan["steps"], start=1):
        assert step["step_id"] == idx
        assert step["dependencies"] == ([idx - 1] if idx > 1 else [])


def test_read_only_constraint_truncates_mutation_and_says_so():
    plan = build_plan(
        "Change subscription pricing",
        {"operation": "pricing_change"},
        constraints=["read_only"],
    )
    actions = _actions(plan)
    assert "execute_operation" not in actions
    assert actions[-2] == "report_findings"


def test_decompose_honours_cap_by_merging_not_dropping():
    decomp = build_decomposition(
        "Deploy proactive cart recovery workflow", {}, max_subtasks=3
    )
    assert decomp["total_subtasks"] == 3
    assert decomp["cap_applied"] is True
    assert decomp["phases_total"] > 3
    all_actions = [a for s in decomp["subtasks"] for a in s["actions"]]
    assert "execute_operation" in all_actions  # merged, not dropped
    assert decomp["subtasks"][0]["required_capability"] == "policy_engine"


def test_decompose_never_invents_filler_above_phase_count():
    decomp = build_decomposition(
        "Change subscription pricing",
        {"operation": "pricing_change"},
        max_subtasks=20,
    )
    assert decomp["total_subtasks"] == decomp["phases_total"]
    assert decomp["cap_applied"] is False


def test_decompose_cap_one_merges_everything():
    decomp = build_decomposition(
        "Book a flight to Tokyo", {}, max_subtasks=1
    )
    assert decomp["total_subtasks"] == 1
    assert decomp["plannable"] is False


def test_high_impact_mirror_matches_source_of_truth():
    """The planner's fallback mirror must match
    cortex_core.governed_operations.HIGH_IMPACT_ACTION_MAP whenever
    the real module is importable (it is inside the API app)."""
    try:
        from cortex_core.governed_operations import HIGH_IMPACT_ACTION_MAP
    except Exception:
        pytest.skip("cortex_core not importable in this environment")
    expected = {
        action: category.value
        for category, actions in HIGH_IMPACT_ACTION_MAP.items()
        for action in actions
    }
    assert _HIGH_IMPACT_MIRROR == expected
