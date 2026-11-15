"""Deterministic, goal-aware planner for Cortex's cognitive endpoints.

TASK-COR-005 (plan-quality review). Until this module, ``POST /plan``
and ``POST /decompose`` in ``cortex_api.main`` returned a fixed
three-step template for every goal: only the goal string was
interpolated into the first step's description. The graded review
(``Cortex/docs/PLAN_QUALITY_REVIEW_COR005.md``) found, against the
production journal and the governed executor's code:

* identical steps for a read-only health check, a high-impact billing
  change, and a goal Cortex cannot serve at all;
* no approval-gate step, although the executor hard-blocks
  high-impact operations without one (HTTP 403);
* no measurement/verification step, although the executor always
  measures outcomes against ``expected_outcomes``;
* invented duration constants (2s/3s/5s) presented as estimates;
* ``/decompose`` silently returning 3 subtasks for any
  ``max_subtasks`` and truncating the chain mid-way at small caps.

This planner builds the plan from the goal + context by mirroring the
phases the governed executor actually runs
(``cortex_api.friday_router.process_task_envelope``):

    idempotency/scope validation -> impact classification ->
    approval gate (high-impact) -> Sentinel gate (production) ->
    observe (telemetry staleness bound) -> recommend | execute ->
    measure -> provenance record

with ``TaskState`` names from ``cortex_core.task_manager`` attached to
each step as ``executor_state`` so a produced plan can be graded
against a real execution afterwards. Every step carries an
``expected_outcome`` for the same reason.

Honesty rules enforced here:

* Durations are *phase budgets*, not measurements. No production
  timing baseline exists for these phases (the plan endpoints had
  zero production calls in the journal reviewed on 2026-11-15), so
  responses carry ``estimate_basis="phase_budget_unmeasured"``.
* If no governed operation can be identified from the context or the
  goal, the plan says so (``plannable=False`` with a reason) and
  stops at validate/observe/clarify instead of fabricating an
  execution graph. The executor fails closed (422) on unrouted
  actions; the planner now fails honestly at plan time.
* ``/decompose`` never invents filler subtasks and never silently
  truncates: when the caller's cap binds, trailing phases are merged
  into the final subtask and the merge is reported.
"""

from __future__ import annotations

import re
from typing import Any

PLANNER_NAME = "cortex_api.cognitive_planner"
PLANNER_VERSION = "1.0.0"
ESTIMATE_BASIS = "phase_budget_unmeasured"

# Phase budgets in seconds. Planning budgets only (see module
# docstring); await_supervisor_approval is an external human wait and
# is budgeted 0 so it never inflates the total.
PHASE_BUDGET_SEC: dict[str, int] = {
    "validate_scope": 1,
    "classify_impact": 1,
    "identify_operation": 1,
    "await_supervisor_approval": 0,
    "sentinel_security_gate": 1,
    "observe_current_state": 2,
    "recommend_intervention": 2,
    "capture_pre_execution_snapshot": 1,
    "execute_operation": 5,
    "measure_outcome": 2,
    "report_findings": 1,
    "record_provenance": 1,
}

# Executor action vocabulary (friday_router.process_task_envelope).
READ_ONLY_ACTIONS = {"health_summary", "status"}
RECOMMEND_ACTIONS = {"recommend_intervention", "recommend"}
EXECUTE_ACTIONS = {"execute_operation", "execute", "apply_change"}
DIRECT_ACTIONS = {"cancel", "rollback"}

# Fallback mirror of cortex_core.governed_operations
# HIGH_IMPACT_ACTION_MAP (action -> category). The real classifier is
# imported when cortex_core is importable (it is, inside the API app);
# this mirror exists so the planner stays importable in isolation.
# tests/unit/test_cognitive_planner.py asserts the mirror matches the
# source of truth whenever cortex_core is importable.
_HIGH_IMPACT_MIRROR: dict[str, str] = {
    "payment_initiate": "billing",
    "billing_update": "billing",
    "pricing_change": "billing",
    "subscription_modify": "billing",
    "refund_issue": "billing",
    "stripe_charge": "billing",
    "email_dispatch": "customer_communication",
    "sms_dispatch": "customer_communication",
    "voice_dispatch": "customer_communication",
    "broadcast_message": "customer_communication",
    "marketing_outreach": "customer_communication",
    "crm_sync": "customer_communication",
    "config_update": "production_configuration",
    "deployment_traffic_switch": "production_configuration",
    "route_mutate": "production_configuration",
    "prod_env_update": "production_configuration",
    "feature_flag_toggle": "production_configuration",
    "experiment_mutate": "production_configuration",
    "content_publish": "content_publishing",
    "page_deploy": "content_publishing",
    "theme_publish": "content_publishing",
    "banner_injection": "content_publishing",
    "site_modify": "content_publishing",
    "account_update": "account_permissions",
    "permission_grant": "account_permissions",
    "role_modify": "account_permissions",
    "user_invite_admin": "account_permissions",
    "credential_revoke": "account_permissions",
}

# Goal-text keyword layer (heuristic, used only when the context names
# no operation). Every value is a real governed action/executor action
# name; keys are plain-language goal fragments.
_GOAL_KEYWORDS: list[tuple[str, str]] = [
    ("health summary", "health_summary"),
    ("health check", "health_summary"),
    ("recommend", "recommend_intervention"),
    ("suggest an intervention", "recommend_intervention"),
    ("pricing change", "pricing_change"),
    ("price change", "pricing_change"),
    ("change the price", "pricing_change"),
    ("refund", "refund_issue"),
    ("subscription", "subscription_modify"),
    ("deploy", "page_deploy"),
    ("publish", "content_publish"),
    ("banner", "banner_injection"),
    ("email campaign", "email_dispatch"),
    ("send email", "email_dispatch"),
    ("feature flag", "feature_flag_toggle"),
    ("roll back", "rollback"),
    ("rollback", "rollback"),
    ("cancel", "cancel"),
]

# Context keys that mark the request as telemetry-driven; with no
# named operation the governed engine's own recommend flow (and its
# default proposed operation) is the honest mapping.
_TELEMETRY_CONTEXT_KEYS = {
    "telemetry",
    "bounce_rate",
    "conversion_rate",
    "latency_ms",
    "metrics",
    "drop_off_rate",
}
_EXECUTOR_DEFAULT_OPERATION = "banner_injection"


def _classify_impact(operation: str) -> tuple[str, bool]:
    """(category, is_high_impact) for an operation name.

    Uses cortex_core.governed_operations.classify_action_impact when
    importable; otherwise the mirror above (kept in sync by test).
    """
    try:
        from cortex_core.governed_operations import classify_action_impact

        category, is_high = classify_action_impact(operation)
        return str(getattr(category, "value", category)), bool(is_high)
    except Exception:
        norm = operation.lower().strip()
        for action, category in _HIGH_IMPACT_MIRROR.items():
            if norm == action or action in norm:
                return category, True
        return "low_risk", False


def _resolve_operation(
    goal: str, context: dict[str, Any]
) -> tuple[str | None, str, str | None]:
    """Resolve (operation, flow, operation_source).

    Mirrors the executor's own payload reads first
    (operation/action_type/proposed_operation), then a documented
    keyword layer over the goal, then the telemetry-context mapping.
    flow is one of: read_only | recommend | execute | direct | None.
    """
    def flow_of(op_name: str, source: str) -> tuple[str, str, str]:
        norm = op_name.lower()
        if norm in READ_ONLY_ACTIONS:
            return op_name, "read_only", source
        if norm in RECOMMEND_ACTIONS:
            return op_name, "recommend", source
        if norm in DIRECT_ACTIONS:
            return op_name, "direct", source
        return op_name, "execute", source

    for key in ("operation", "action_type"):
        op = context.get(key)
        if isinstance(op, str) and op.strip():
            return flow_of(op.strip(), f"context.{key}")
    proposed = context.get("proposed_operation")
    if isinstance(proposed, str) and proposed.strip():
        return proposed.strip(), "recommend", "context.proposed_operation"
    action = context.get("action")
    if isinstance(action, str) and action.strip():
        norm = action.strip().lower()
        if norm in EXECUTE_ACTIONS:
            op = context.get("operation")
            if isinstance(op, str) and op.strip():
                return op.strip(), "execute", "context.action+context.operation"
            return _EXECUTOR_DEFAULT_OPERATION, "execute", "context.action"
        return flow_of(norm, "context.action")

    # Telemetry-bearing context outranks goal keywords: a goal that
    # mentions a pricing *page* while carrying bounce-rate telemetry
    # is a recommendation request, not a price change.
    if _TELEMETRY_CONTEXT_KEYS & set(context.keys()):
        return _EXECUTOR_DEFAULT_OPERATION, "recommend", "telemetry_context_executor_default"

    goal_norm = re.sub(r"\s+", " ", goal.lower())
    for keyword, op in _GOAL_KEYWORDS:
        if keyword in goal_norm:
            return flow_of(op, "goal_keyword")

    return None, "", "unresolved"


def _step(
    step_id: int,
    action: str,
    capability: str,
    description: str,
    dependencies: list[int],
    executor_state: str | None,
    expected_outcome: str,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "action": action,
        "capability": capability,
        "description": description,
        "estimated_duration_sec": PHASE_BUDGET_SEC[action],
        "dependencies": dependencies,
        "executor_state": executor_state,
        "expected_outcome": expected_outcome,
    }


def build_plan(
    goal: str,
    context: dict[str, Any] | None = None,
    constraints: list[str] | None = None,
    priority: str = "NORMAL",
) -> dict[str, Any]:
    """Build a goal-aware plan aligned with the governed executor."""
    context = context or {}
    constraints = constraints or []
    property_id = (
        context.get("property_id") or context.get("site_id") or "site_storefront"
    )
    operation, flow, op_source = _resolve_operation(goal, context)
    read_only_constraint = any(
        c.strip().lower() in ("read_only", "no_execution", "no_execute")
        for c in constraints
    )

    steps: list[dict[str, Any]] = []

    def add(action, capability, description, executor_state, expected_outcome):
        deps = [steps[-1]["step_id"]] if steps else []
        steps.append(
            _step(len(steps) + 1, action, capability, description, deps,
                  executor_state, expected_outcome)
        )

    add(
        "validate_scope",
        "policy_engine",
        f"Validate property access and environment for '{property_id}' "
        f"(executor rejects unknown/mismatched properties before any work)",
        "RECEIVED",
        "Property access validated, or the plan aborts with the "
        "executor's 404/400 exactly as /v1/task/execute would",
    )

    if operation is None:
        add(
            "observe_current_state",
            "analytics",
            f"Observe current state relevant to goal: '{goal}'",
            "OBSERVING",
            "A current-state snapshot exists to plan against",
        )
        add(
            "identify_operation",
            "reasoning",
            "Identify the governed operation this goal maps to; no "
            "operation was named in context and no governed action "
            "matched the goal text, and the executor fails closed "
            "(422) on unrouted actions",
            None,
            "A named governed operation (or an explicit decision that "
            "Cortex cannot serve this goal)",
        )
        return _plan_response(
            goal, priority, constraints, steps,
            operation=None, operation_source=op_source,
            impact_category=None, is_high_impact=False,
            plannable=False,
            unplannable_reason=(
                "No governed operation identified from context or goal; "
                "returning an observe-and-clarify plan instead of a "
                "fabricated execution graph."
            ),
        )

    category, is_high = _classify_impact(operation)
    add(
        "classify_impact",
        "governance",
        f"Classify operation '{operation}' with the governed impact "
        f"classifier (result: category={category}, "
        f"high_impact={str(is_high).lower()})",
        "RECEIVED",
        f"Impact category '{category}' recorded; approval gating "
        f"decided from it",
    )

    already_approved = context.get("approved") is True
    needs_approval = is_high and not already_approved

    def add_approval_step(gates: str):
        add(
            "await_supervisor_approval",
            "approval",
            f"Obtain explicit supervisor approval for high-impact "
            f"operation '{operation}' (category {category}); the "
            f"executor blocks {gates} with 403 until approved. "
            f"Recommendation is not authorization.",
            "WAITING_APPROVAL",
            "Approval recorded (approver + reason), or the plan stops "
            "here — it never proceeds unapproved",
        )

    if flow == "execute" and needs_approval:
        # Executor order: classify -> approval gate -> execute.
        add_approval_step("execution")

    if flow == "read_only":
        add(
            "observe_current_state",
            "analytics",
            f"Compile the '{operation}' snapshot for '{property_id}' "
            f"including connector health",
            "OBSERVING",
            "A health snapshot compiled from live connector checks",
        )
        add(
            "report_findings",
            "analytics",
            f"Report the '{operation}' findings for goal: '{goal}'",
            "COMPLETED",
            "Findings reported to the caller with the snapshot attached",
        )
    elif flow == "recommend":
        staleness = context.get("max_staleness_seconds", 60)
        add(
            "observe_current_state",
            "analytics",
            f"Observe telemetry for '{property_id}' with staleness "
            f"bound {staleness}s (stale telemetry blocks the flow)",
            "OBSERVING",
            "Fresh telemetry observation recorded, or the plan blocks "
            "on staleness exactly as the executor does",
        )
        add(
            "recommend_intervention",
            "reasoning",
            f"Generate a governed recommendation for operation "
            f"'{operation}' on '{property_id}' with rationale and "
            f"expected outcomes",
            "RECOMMENDING",
            "A recommendation object exists with category, confidence "
            "and expected outcomes; it is not an authorization",
        )
        if needs_approval:
            # Executor order for the recommend flow: observe ->
            # recommend -> WAITING_APPROVAL (the recommendation is
            # produced first; approval gates any follow-on execution).
            add_approval_step("any follow-on execution of the recommendation")
    elif flow == "direct":
        add(
            "execute_operation",
            "execution",
            f"Run '{operation}' via POST /v1/task/execute against the "
            f"target task on '{property_id}'",
            "EXECUTING",
            f"'{operation}' applied to the target task and its state "
            f"returned",
        )
    else:  # execute
        if str(context.get("environment", "")).lower() == "production":
            add(
                "sentinel_security_gate",
                "governance",
                "Pass the Sentinel security gate for the production "
                "environment (a BLOCKED verdict stops execution, 403)",
                "EXECUTING",
                "Sentinel verdict recorded as not BLOCKED",
            )
        add(
            "capture_pre_execution_snapshot",
            "execution",
            f"Capture a pre-execution snapshot of '{property_id}' so "
            f"the change can be rolled back",
            "EXECUTING",
            "A rollback snapshot exists before any mutation",
        )
        dry_run_note = " in dry-run mode" if context.get("dry_run") else ""
        add(
            "execute_operation",
            "execution",
            f"Execute operation '{operation}' on '{property_id}' via "
            f"POST /v1/task/execute{dry_run_note}",
            "EXECUTING",
            f"Execution record for '{operation}' with a terminal "
            f"status and classification",
        )
        add(
            "measure_outcome",
            "analytics",
            "Measure observed outcomes against the expected outcomes "
            "and record lift metrics",
            "MEASURING",
            "A measurement exists comparing expected vs observed "
            "outcomes for this execution",
        )

    if read_only_constraint and flow == "execute":
        # The caller forbade execution: drop the mutation tail and say so.
        steps = [
            s for s in steps
            if s["action"] not in (
                "await_supervisor_approval",
                "sentinel_security_gate",
                "capture_pre_execution_snapshot",
                "execute_operation",
                "measure_outcome",
            )
        ]
        for idx, s in enumerate(steps, start=1):
            s["step_id"] = idx
            s["dependencies"] = [idx - 1] if idx > 1 else []
        add(
            "report_findings",
            "analytics",
            "Report findings only: constraint "
            f"{constraints} forbids execution, so no mutation steps "
            "are planned",
            "COMPLETED",
            "Findings reported; nothing was executed",
        )

    add(
        "record_provenance",
        "audit",
        "Record the plan and its step outcomes under the plan/task "
        "record so the plan can be graded against what happened",
        "COMPLETED",
        "A durable record links this plan to its execution outcome",
    )

    return _plan_response(
        goal, priority, constraints, steps,
        operation=operation, operation_source=op_source,
        impact_category=category, is_high_impact=is_high,
        plannable=True, unplannable_reason=None,
    )


def _plan_response(
    goal: str,
    priority: str,
    constraints: list[str],
    steps: list[dict[str, Any]],
    *,
    operation: str | None,
    operation_source: str,
    impact_category: str | None,
    is_high_impact: bool,
    plannable: bool,
    unplannable_reason: str | None,
) -> dict[str, Any]:
    capabilities: list[str] = []
    for s in steps:
        if s["capability"] not in capabilities:
            capabilities.append(s["capability"])
    return {
        "goal": goal,
        "priority": priority,
        "constraints": constraints,
        "steps": steps,
        "estimated_duration_sec": sum(
            s["estimated_duration_sec"] for s in steps
        ),
        "required_capabilities": capabilities,
        "operation": operation,
        "operation_source": operation_source,
        "impact_category": impact_category,
        "is_high_impact": is_high_impact,
        "plannable": plannable,
        "unplannable_reason": unplannable_reason,
        "planner": {
            "name": PLANNER_NAME,
            "version": PLANNER_VERSION,
            "mode": "deterministic_rules",
            "template_free": True,
        },
        "estimate_basis": ESTIMATE_BASIS,
    }


def build_decomposition(
    goal: str,
    context: dict[str, Any] | None = None,
    max_subtasks: int = 5,
) -> dict[str, Any]:
    """Decompose a goal into subtasks derived from the plan phases.

    Honours ``max_subtasks`` by merging trailing phases into the
    final subtask (reported via ``cap_applied``/``merged_actions``),
    never by silently dropping them, and never invents filler
    subtasks when the phase list is shorter than the cap.
    """
    plan = build_plan(goal, context=context)
    phases = plan["steps"]
    groups: list[list[dict[str, Any]]] = [[p] for p in phases]
    cap_applied = False
    while len(groups) > max_subtasks:
        merged = groups[-2] + groups[-1]
        groups = groups[:-2] + [merged]
        cap_applied = True

    subtasks: list[dict[str, Any]] = []
    for idx, group in enumerate(groups, start=1):
        first = group[0]
        actions = [p["action"] for p in group]
        if len(group) == 1:
            description = first["description"]
        else:
            description = (
                "Merged phases (caller cap): "
                + "; ".join(p["description"] for p in group)
            )
        subtasks.append(
            {
                "id": f"subtask_{idx}",
                "description": description,
                "required_capability": first["capability"],
                "dependencies": [f"subtask_{idx - 1}"] if idx > 1 else [],
                "status": "pending",
                "actions": actions,
            }
        )

    return {
        "goal": goal,
        "subtasks": subtasks,
        "total_subtasks": len(subtasks),
        "phases_total": len(phases),
        "cap_applied": cap_applied,
        "operation": plan["operation"],
        "plannable": plan["plannable"],
        "planner": plan["planner"],
    }
