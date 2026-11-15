"""
TASK-FRG-011: ONE authoritative verdict for a Forge build.

Why this module exists
----------------------
TASK-FRG-003's acceptance battery proved, with three instances, that
Forge's verdict surfaces disagreed about the same build:

* pre-fix R3: the in-graph tester gate FAILED the task, the final
  verification manifest read ``all_passed=True``, the delegate answered
  FAILED -- three surfaces, two verdicts, no authority.
* post-fix R1: the task-status endpoint read SUCCESS while the delegate
  manifest read PARTIAL_FAILURE.
* post-fix R5: the in-graph tester gate's exit_code=2 verdict latched
  the task FAILED while the final battery passed 11/11 and the delivered
  project reproduced 13/13 green -- a green deliverable branded FAILED.

The surfaces that carried a verdict (file/line evidence in the
TASK-FRG-011 completion comment on issue #35):

1. the in-graph verification gates (TesterRole / SecurityReviewerRole in
   ``app/agents/roles.py``) -- a point-in-time pytest/security run over
   the workspace *as it exists mid-build*;
2. ``OrchestratorCore.step_task`` -- latches the task state FAILED on
   any gate failure, COMPLETED when the DAG drains;
3. the final verification battery (``app/verification/engine.py``) --
   the full checker suite over the *settled* workspace, after repair,
   peer review and syntax rescue; persisted as
   ``verification_report.json`` / ``verification_manifest.json`` and
   overwritten by every later battery run (delegate re-run, CLI, the
   delegate verify action, delivery);
4. ``OrchestratorCore.run_task``'s post-verification gate
   (TASK-FORGE-002 GAP 5) -- demoted COMPLETED -> FAILED on a failing
   final battery, but had no counterpart for a passing one, and the
   lifecycle matrix (``app/memory/task_lifecycle.py``) does not even
   allow FAILED -> COMPLETED;
5. the delegate execute_now response (``app/api/delegate.py``) -- ran
   its *own* second battery and mirrored state/manifest by hand-rolled
   rules, so its verdict could disagree with the store it had just
   settled (COMPLETED in the store, FAILED in the response);
6. the delegate status endpoint -- re-derived a verdict from (stored
   state, saved manifest, snapshot binding) with a third set of rules;
7. the tasks API / CLI / analytics -- report the raw stored state.

The derivation
--------------
Every surface now reads the verdict from this one function (directly,
or via the stamp written at finalization). Inputs are facts, each named:

* ``task_state`` -- the stored lifecycle state;
* the FINAL battery outcome (``battery_all_passed`` /
  ``battery_partial_failure`` / ``battery_failure_reasons``) -- the
  last full battery run over the settled workspace;
* ``hard_failure_reasons`` -- named failures the battery does not
  measure: a failed non-gate DAG node (the build itself broke), the
  fallback-stub marker, module-completeness misses (TASK-FRG-010), a
  Sentinel delivery block. Each must NAME its check/source;
* ``gate_failure_reasons`` -- in-graph gate verdicts. The battery
  re-judges every subject the gates judge (tests, security), later and
  over the settled files, so a gate verdict is *superseded* by a green
  final battery -- recorded in ``superseded``, never silently dropped;
* ``stamped_verdict`` -- the verdict settled at finalization
  (``OrchestratorCore.apply_final_verdict``), read back by surfaces
  that have no fresher battery run;
* ``snapshot_bound`` -- whether the saved manifest still fingerprints
  the current project files (status endpoint only).

Precedence (stricter verdict wins; agreement, not inflation):

0. CANCELLED -> CANCELLED; BLOCKED -> BLOCKED; a non-terminal state
   (PENDING/READY/RUNNING/VERIFYING) has no final verdict -> ``None``.
1. Any hard failure -> FAILED, reasons = the hard failures. A green
   battery can never launder a build that broke or fell back to stubs.
2. A stamped verdict (settled at finalization from these same inputs)
   is authoritative for read surfaces -- except a SUCCESS stamp whose
   evidence is gone or no longer bound to the current files degrades
   to DEGRADED. The stamp lives in two places (task metadata and the
   manifest artifact); a read surface trusts it only when both agree,
   because a later battery re-run (e.g. the delegate verify action)
   regenerates the manifest unstamped and thereby supersedes the
   stamp -- the fresher battery then decides under rule 3.
3. A final battery that ran decides: failing -> PARTIAL_FAILURE when
   only some stages failed, else FAILED, reasons = the battery's named
   failing checks; passing -> SUCCESS, with any gate failures listed
   as superseded. A passing battery whose manifest is not bound to the
   current files -> DEGRADED. One guard on the passing case: a FAILED
   task is reconciled to SUCCESS only when its failure is *positively*
   identified as gate verdicts (or by a trusted stamp, rule 2) -- an
   unexplained failure stays FAILED with its recorded error, because
   absence of a named reason is not evidence of a gate.
4. No battery evidence: COMPLETED -> DEGRADED (a completion claim
   without evidence is never SUCCESS); FAILED -> FAILED with the
   recorded reasons.

Consequences pinned by tests: a battery PARTIAL can never surface as
SUCCESS anywhere; a green final battery + green deliverable can never
surface as FAILED without a named failing check (rule 1) -- the R5
shape resolves to SUCCESS with the gate verdict named as superseded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BuildVerdict(str, Enum):
    """The one verdict vocabulary every Forge surface reports."""

    SUCCESS = "SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class VerdictDecision:
    """A derived verdict plus the named reasons behind it.

    ``reasons`` names every check/fact that produced a non-SUCCESS
    verdict (a FAILED/PARTIAL verdict without a named reason is a bug
    in the caller). ``superseded`` names earlier verdicts the final
    battery overruled, so the reconciliation is auditable, not silent.
    """

    verdict: BuildVerdict
    reasons: tuple[str, ...] = ()
    superseded: tuple[str, ...] = ()


_TERMINAL_STATES = {"COMPLETED", "FAILED"}


def _state_value(state: Any) -> str | None:
    if state is None:
        return None
    return str(getattr(state, "value", state) or "") or None


def derive_build_verdict(
    *,
    task_state: Any,
    battery_all_passed: bool | None = None,
    battery_partial_failure: bool | None = None,
    battery_failure_reasons: tuple[str, ...] | list[str] = (),
    hard_failure_reasons: tuple[str, ...] | list[str] = (),
    gate_failure_reasons: tuple[str, ...] | list[str] = (),
    stamped_verdict: str | None = None,
    stamped_reasons: tuple[str, ...] | list[str] = (),
    stamped_superseded: tuple[str, ...] | list[str] = (),
    recorded_error: str | None = None,
    snapshot_bound: bool | None = None,
    evidence_available: bool = True,
) -> VerdictDecision | None:
    """Derive the one authoritative verdict for a build.

    Returns ``None`` when the task has not reached a final state and no
    battery-only verdict was requested (``task_state=None`` with no
    battery inputs). See the module docstring for the precedence rules.
    """
    state = _state_value(task_state)
    hard = tuple(r for r in hard_failure_reasons if r)
    gate = tuple(r for r in gate_failure_reasons if r)
    battery_reasons = tuple(r for r in battery_failure_reasons if r)

    # Rule 0: states that are verdicts in themselves / not yet final.
    if state == "CANCELLED":
        return VerdictDecision(BuildVerdict.CANCELLED)
    if state == "BLOCKED":
        return VerdictDecision(BuildVerdict.BLOCKED)
    if state is not None and state not in _TERMINAL_STATES:
        return None

    # Rule 1: named failures the battery does not measure outrank it.
    if hard:
        return VerdictDecision(BuildVerdict.FAILED, reasons=hard, superseded=gate)

    # Rule 2: the verdict stamped at finalization is authoritative for
    # read surfaces -- it was derived from these same inputs when the
    # build settled. Only its SUCCESS form can decay (evidence gone or
    # no longer bound to the files on disk).
    if stamped_verdict:
        try:
            stamped = BuildVerdict(str(stamped_verdict))
        except ValueError:
            stamped = None
        if stamped is not None:
            if stamped == BuildVerdict.SUCCESS and (
                not evidence_available or snapshot_bound is False
            ):
                return VerdictDecision(
                    BuildVerdict.DEGRADED,
                    reasons=(
                        "Saved verification is not bound to the current "
                        "project files; re-run verification.",
                    ),
                    superseded=tuple(stamped_superseded),
                )
            return VerdictDecision(
                stamped,
                reasons=tuple(stamped_reasons),
                superseded=tuple(stamped_superseded),
            )

    # Rule 3: the final battery decides everything it measures.
    if battery_all_passed is not None:
        if not battery_all_passed:
            verdict = (
                BuildVerdict.PARTIAL_FAILURE
                if battery_partial_failure
                else BuildVerdict.FAILED
            )
            return VerdictDecision(
                verdict,
                reasons=battery_reasons or ("Verification battery failed.",),
                superseded=gate,
            )
        if snapshot_bound is False:
            return VerdictDecision(
                BuildVerdict.DEGRADED,
                reasons=(
                    "Saved verification is not bound to the current "
                    "project files; re-run verification.",
                ),
                superseded=gate,
            )
        if state == "FAILED" and not gate:
            # The battery passed, but nothing identifies this task's
            # failure as a gate verdict the battery re-judged (no gate
            # reasons, no trusted stamp). An unexplained execution
            # failure is not reconciled by leftover artifacts that
            # happen to verify (TASK-REL-019's invariant).
            return VerdictDecision(
                BuildVerdict.FAILED,
                reasons=(recorded_error or "Task failed.",),
            )
        return VerdictDecision(BuildVerdict.SUCCESS, superseded=gate)

    # Rule 4: no battery evidence at all.
    if state == "COMPLETED":
        return VerdictDecision(
            BuildVerdict.DEGRADED,
            reasons=("Task execution completed but verification evidence is unavailable.",),
        )
    if state == "FAILED":
        return VerdictDecision(
            BuildVerdict.FAILED,
            reasons=gate or ((recorded_error,) if recorded_error else ("Task failed.",)),
        )
    return None


def failure_reasons_from_graph(graph: Any) -> tuple[list[str], list[str]]:
    """Split a task graph's failed nodes into (hard, gate) reasons.

    A failed verification-gate node is a *gate* reason: the final
    battery re-judges its subject, so it can be superseded. Any other
    failed node means the build itself broke -- a *hard* reason no
    battery result can overrule. Shared by the orchestrator's
    finalization and the delegate status endpoint so both compute the
    derivation's inputs the same way.
    """
    hard: list[str] = []
    gate: list[str] = []
    nodes = getattr(graph, "nodes", None) or {}
    for node in nodes.values():
        status = _state_value(getattr(node, "status", None))
        if status != "FAILED":
            continue
        title = getattr(node, "title", None) or getattr(node, "id", "node")
        error = getattr(node, "error", None) or "failed"
        metadata = getattr(node, "metadata", None) or {}
        if metadata.get("node_type") == "verification_gate":
            gate.append(f"Verification gate '{title}': {error}")
        else:
            hard.append(f"Node '{title}': {error}")
    return hard, gate


def stamped_verdict_of(task: Any) -> str | None:
    """The verdict stamped on a task record at finalization, if any."""
    metadata = getattr(task, "metadata", None)
    if isinstance(metadata, dict):
        value = metadata.get("build_verdict")
        if value:
            return str(value)
    return None
