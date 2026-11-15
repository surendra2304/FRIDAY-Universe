"""TASK-IG-FRG-06: loop-until-done + structured plan-to-ship workflow.

Corpus source: DdeTgRuE4yq — an Antigravity plugin carousel whose two
transferable patterns are **Ralph Loop** (an agent iterates on a task
until it is *done*, not until it has tried once) and **GSD Core** (a
structured workflow: plan -> build -> verify -> ship, each stage with
explicit criteria).

The naive version of "loop until done" is dangerous in exactly the
way Forge's honesty discipline exists to prevent: an unbounded loop
that eventually declares success because it stopped, not because the
work passed. This module is the bounded, honest version:

* A :class:`ShipPlan` is a list of phases, each with **named
  acceptance criteria** and a per-phase attempt cap. A plan that
  cannot be judged (a phase with no criteria, a cap below 1,
  duplicate phase names) is rejected up front — fail closed.
* :func:`run_plan` drives an injected ``step_fn(phase, attempt)`` —
  in production that is the build/test machinery; here it is a pure
  seam. A phase advances only when its step reports ``passed``.
* Terminal states are honest and exhaustive:
  ``DONE`` (every phase passed), ``BLOCKED`` (a step reported a
  blocker — the run stops immediately, it does not retry through a
  blocker), ``EXHAUSTED`` (a phase or the whole run hit its attempt
  cap without passing — reported as exhaustion, never as success).
* Every attempt is recorded in the :class:`LoopReport`, so a reader
  can see *how many tries* a phase took and *why* the run ended.

No step is executed by this module itself; it is the workflow's
skeleton and its judge, deliberately separable from the machinery
that does the work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence, Tuple


class LoopOutcome(str, Enum):
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True)
class ShipPhase:
    name: str
    goal: str
    acceptance: Tuple[str, ...]  # named criteria; all must hold to pass
    max_attempts: int = 3


@dataclass(frozen=True)
class ShipPlan:
    name: str
    phases: Tuple[ShipPhase, ...]
    max_total_attempts: Optional[int] = None  # whole-run cap, if set

    def validate(self) -> List[str]:
        problems: List[str] = []
        if not self.name.strip():
            problems.append("plan name is empty")
        if not self.phases:
            problems.append("plan has no phases")
        seen = set()
        for phase in self.phases:
            if not phase.name.strip():
                problems.append("a phase has an empty name")
            if phase.name in seen:
                problems.append(f"duplicate phase name: {phase.name}")
            seen.add(phase.name)
            if not phase.acceptance:
                problems.append(
                    f"phase '{phase.name}' has no acceptance criteria — "
                    "a phase that cannot be judged cannot be looped on"
                )
            if phase.max_attempts < 1:
                problems.append(
                    f"phase '{phase.name}' has max_attempts < 1"
                )
        if self.max_total_attempts is not None and self.max_total_attempts < 1:
            problems.append("max_total_attempts must be >= 1 when set")
        return problems


@dataclass
class PhaseResult:
    """One attempt's verdict, reported by the step function."""

    passed: bool
    blocked: bool = False
    detail: str = ""
    criteria_met: Tuple[str, ...] = ()
    criteria_unmet: Tuple[str, ...] = ()


StepFn = Callable[[ShipPhase, int], PhaseResult]


@dataclass
class PhaseRecord:
    phase: str
    attempts: int = 0
    outcome: str = "not_started"  # passed / blocked / exhausted
    details: List[str] = field(default_factory=list)


@dataclass
class LoopReport:
    plan_name: str
    outcome: LoopOutcome
    records: List[PhaseRecord] = field(default_factory=list)
    total_attempts: int = 0
    stop_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "plan": self.plan_name,
            "outcome": self.outcome.value,
            "total_attempts": self.total_attempts,
            "stop_reason": self.stop_reason,
            "phases": [
                {
                    "phase": r.phase,
                    "attempts": r.attempts,
                    "outcome": r.outcome,
                    "details": r.details,
                }
                for r in self.records
            ],
        }


def run_plan(plan: ShipPlan, step_fn: StepFn) -> LoopReport:
    """Drive a plan to an honest terminal state.

    Raises ValueError for an invalid plan — a plan that cannot be
    judged must not be run at all.
    """
    problems = plan.validate()
    if problems:
        raise ValueError("invalid ship plan: " + "; ".join(problems))
    report = LoopReport(plan_name=plan.name, outcome=LoopOutcome.EXHAUSTED)
    # One record per phase from the start, so phases the run never
    # reached are visible in the report as "not_started" — not absent.
    records = {phase.name: PhaseRecord(phase=phase.name) for phase in plan.phases}
    report.records = [records[phase.name] for phase in plan.phases]
    for phase in plan.phases:
        record = records[phase.name]
        phase_passed = False
        for attempt in range(1, phase.max_attempts + 1):
            if (
                plan.max_total_attempts is not None
                and report.total_attempts >= plan.max_total_attempts
            ):
                record.outcome = "exhausted"
                report.outcome = LoopOutcome.EXHAUSTED
                report.stop_reason = (
                    f"whole-run attempt cap ({plan.max_total_attempts}) "
                    f"reached during phase '{phase.name}'"
                )
                return report
            result = step_fn(phase, attempt)
            report.total_attempts += 1
            record.attempts += 1
            if result.detail:
                record.details.append(f"attempt {attempt}: {result.detail}")
            if result.blocked:
                record.outcome = "blocked"
                report.outcome = LoopOutcome.BLOCKED
                report.stop_reason = (
                    f"phase '{phase.name}' reported a blocker on attempt "
                    f"{attempt}: {result.detail or '(no detail given)'}"
                )
                return report
            if result.passed:
                record.outcome = "passed"
                phase_passed = True
                break
        if not phase_passed:
            record.outcome = "exhausted"
            report.outcome = LoopOutcome.EXHAUSTED
            report.stop_reason = (
                f"phase '{phase.name}' did not pass within "
                f"{phase.max_attempts} attempt(s) — reported as exhausted, "
                "not as done"
            )
            return report
    report.outcome = LoopOutcome.DONE
    report.stop_reason = "every phase passed its acceptance criteria"
    return report


# ---------------------------------------------------------------------------
# The GSD-shaped default plan
# ---------------------------------------------------------------------------


def default_ship_plan(max_attempts_per_phase: int = 3) -> ShipPlan:
    """The structured plan-to-ship workflow: plan -> build -> verify
    -> ship, each phase with the criteria Forge already judges by."""
    return ShipPlan(
        name="plan-to-ship",
        phases=(
            ShipPhase(
                name="plan",
                goal="Turn the goal into an explicit plan and file manifest.",
                acceptance=(
                    "plan names every file the build will produce",
                    "plan names the acceptance tests for the goal",
                ),
                max_attempts=max_attempts_per_phase,
            ),
            ShipPhase(
                name="build",
                goal="Generate the project the plan describes.",
                acceptance=(
                    "every file in the manifest exists and is non-empty",
                    "no fabricated/stub module stands in for a planned file",
                ),
                max_attempts=max_attempts_per_phase,
            ),
            ShipPhase(
                name="verify",
                goal="Run the verification battery over the settled build.",
                acceptance=(
                    "test battery passes",
                    "security review passes with no blocking findings",
                    "verdict surfaces agree (single authoritative verdict)",
                ),
                max_attempts=max_attempts_per_phase,
            ),
            ShipPhase(
                name="ship",
                goal="Deliver the verified build.",
                acceptance=(
                    "delivery target recorded",
                    "post-delivery probe confirms the delivered state",
                ),
                max_attempts=max_attempts_per_phase,
            ),
        ),
    )
