"""One end-to-end Forge build run, wiring the four wave-3 adopted
components into Forge's orchestration layer (TASK-FRG-028).

The four components were adopted as libraries in waves 1-2 but nothing
in Forge ever called them: ``coding_principles`` (Karpathy Skill),
``code_graph`` (Graphify) and ``ocr_review`` (Open Code Review) were
imported only by their own tests, and ``ecc_patterns`` (ECC) was only
re-exported by ``app/harness/__init__.py``. This module is the wiring —
one build run through ``ForgeController``'s DAG that executes a real
build task with all four components in their stage:

* plan — Karpathy ``preflight`` (refuses a task with no assumptions or
  no verifiable success criteria) + ``guidance_block`` rendered into
  the run context; ECC ``scan_agent_config`` over the build config —
  a critical/high shield finding blocks the run before any code.
* understand — Graphify ``build_graph`` over the target subfolder and
  ``CodeGraph`` query/path over the produced graph (advisory: an
  unavailable CLI is recorded honestly, never faked).
* implement — the caller-supplied build steps, tracked file by file.
* review — Karpathy ``scope_check`` against the declared scope
  (fail-closed) + OCR delegate pass over the changed files; the OCR
  result is attached with ``supplement_review`` and can never change
  the gate verdict.
* test / verify — the declared test command runs for real; its result
  is recorded as ECC test evidence and the ECC ``stage_gate`` refuses
  to leave ``verify`` without passing evidence.
* remember / deliver — the outcome is observed into an ECC
  ``InstinctStore`` and the run summary is delivered.

The run is stdlib-only, runs no model and touches no fleet service:
the Memora writes inside ``ForgeController`` are already guarded by
try/except there and degrade to a log warning offline. Live-fleet
execution (a real build task for another agent through the deployed
Forge, output used in production) is owed after Muse's clearance and
is NOT claimed here.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.harness.ecc_patterns import (
    HarnessRun,
    InstinctStore,
    scan_agent_config,
    stage_gate,
)

from .coding_principles import guidance_block, preflight, scope_check
from .code_graph import CodeGraph, build_graph
from .models import PlanGraph, PlanNode, TaskPhase
from .ocr_review import run_ocr_review, supplement_review
from .orchestrator import ForgeController

#: Build steps: each receives the run workdir and returns the
#: repo-relative paths it changed.
BuildStep = Callable[[Path], list[str]]

#: DAG node ids, in execution order (also the ECC stage order, with the
#: Graphify understand step and the deliver step folded in).
NODE_IDS = (
    "plan",
    "understand",
    "implement",
    "review",
    "test",
    "verify",
    "remember",
    "deliver",
)

_NODE_PHASES = {
    "plan": TaskPhase.PLAN,
    "understand": TaskPhase.UNDERSTAND,
    "implement": TaskPhase.IMPLEMENT,
    "review": TaskPhase.REVIEW,
    "test": TaskPhase.TEST,
    "verify": TaskPhase.TEST,
    "remember": TaskPhase.COMPLETE,
    "deliver": TaskPhase.DELIVER,
}

#: Which ECC stage the run is in while each DAG node executes.
_NODE_ECC_STAGE = {
    "plan": "plan",
    "understand": "test",
    "implement": "implement",
    "review": "review",
    "test": "verify",
    "verify": "verify",
    "remember": "remember",
    "deliver": "improve",
}


@dataclass(slots=True)
class BuildRunSpec:
    """Everything one build run needs, declared up front."""

    task_id: str
    task: str
    assumptions: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    target_agent: str = "forge"
    target_dir: str | Path = "."
    scope_prefixes: list[str] = field(default_factory=list)
    build_config: dict = field(default_factory=dict)
    steps: list[BuildStep] = field(default_factory=list)
    test_command: list[str] = field(default_factory=list)
    graph_terms: list[str] = field(default_factory=list)
    test_timeout: int = 600
    graph_runner: object = None  # subprocess.run-compatible, or None
    ocr_runner: object = None  # subprocess.run-compatible, or None


@dataclass(slots=True)
class BuildRunReport:
    """Outcome of one build run."""

    task_id: str
    status: str  # "completed" | "blocked" | "failed"
    stage: str  # last ECC stage reached
    completed: bool
    blockers: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    history: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"build run {self.task_id}: {self.status} (stage {self.stage})",
            f"changed files: {len(self.changed_files)}",
        ]
        for key in sorted(self.evidence):
            lines.append(f"- {key}: {self.evidence[key]}")
        for blocker in self.blockers:
            lines.append(f"BLOCKER: {blocker}")
        return "\n".join(lines)


def build_plan_graph(spec: BuildRunSpec) -> PlanGraph:
    """The run's DAG: one node per stage, chained in order.

    Passes ``PlanGuard`` by construction: a TEST node and a REVIEW node
    exist, and the DELIVER node depends on them transitively without
    depending directly on IMPLEMENT.
    """
    nodes: dict[str, PlanNode] = {}
    previous: str | None = None
    for node_id in NODE_IDS:
        nodes[node_id] = PlanNode(
            node_id=node_id,
            title=f"frg028 {node_id}: {spec.task_id}",
            description=f"TASK-FRG-028 build-run stage {node_id}",
            phase=_NODE_PHASES[node_id],
            dependencies=(previous,) if previous else (),
        )
        previous = node_id
    return PlanGraph(graph_id=f"frg028-{spec.task_id}", nodes=nodes)


class ForgeBuildRun:
    """Execute one build task end-to-end through Forge's orchestration."""

    def __init__(
        self,
        spec: BuildRunSpec,
        instincts: InstinctStore | None = None,
    ) -> None:
        self.spec = spec
        self.harness = HarnessRun(task_id=spec.task_id)
        self.instincts = instincts if instincts is not None else InstinctStore()
        self.controller = ForgeController(build_plan_graph(spec))
        self.changed_files: list[str] = []
        self.evidence: dict[str, str] = {}
        self.blockers: list[str] = []
        self._blocked = False

    # -- public ---------------------------------------------------------

    def run(self, workdir: str | Path) -> BuildRunReport:
        """Run the build to completion, blocked, or failed. Never raises
        for a gate or build failure — those are reported, not thrown."""
        workdir = Path(workdir)
        while not self.controller.scheduler.complete() and not self.controller.scheduler.failed():
            wave = self.controller.next_wave()
            if not wave:
                break
            for node in wave:
                ok, blocked, detail = self._execute_node(node.node_id, workdir)
                if ok:
                    self.controller.mark_success(node.node_id)
                else:
                    self._blocked = self._blocked or blocked
                    self.blockers.append(detail)
                    self.controller.mark_failure(node.node_id, detail)
        result = self.controller.finish()
        status = (
            "completed"
            if result.completed
            else ("blocked" if self._blocked else "failed")
        )
        if status == "completed":
            self.instincts.observe(
                f"build:{self.spec.target_agent}", "forge build run",
                confirmed=True,
            )
        elif status == "failed":
            self.instincts.observe(
                f"build:{self.spec.target_agent}", "forge build run",
                confirmed=False,
            )
        return BuildRunReport(
            task_id=self.spec.task_id,
            status=status,
            stage=self.harness.stage,
            completed=result.completed,
            blockers=list(self.blockers),
            evidence=dict(self.evidence),
            changed_files=list(self.changed_files),
            history=list(self.harness.history),
        )

    # -- stages ---------------------------------------------------------

    def _execute_node(
        self, node_id: str, workdir: Path
    ) -> tuple[bool, bool, str]:
        """Run one DAG node. Returns (ok, blocked, detail).

        ``blocked`` means a gate refused the run (preflight, shield,
        scope, verify gate) — the build is not at fault, the run is
        not allowed to proceed. ``ok=False, blocked=False`` is a build
        failure (a step raised, the tests failed).
        """
        handler = {
            "plan": self._node_plan,
            "understand": self._node_understand,
            "implement": self._node_implement,
            "review": self._node_review,
            "test": self._node_test,
            "verify": self._node_verify,
            "remember": self._node_remember,
            "deliver": self._node_deliver,
        }[node_id]
        return handler(workdir)

    def _advance_ecc(self, expect: str) -> tuple[bool, str]:
        """Advance the ECC stage machine once; a veto is a block."""
        if self.harness.stage != expect:
            return False, (
                f"ECC stage mismatch: expected {expect}, "
                f"at {self.harness.stage}"
            )
        ok, reason = self.harness.advance()
        if not ok:
            return False, f"ECC refused to advance from {expect}: {reason}"
        return True, reason

    def _node_plan(self, workdir: Path) -> tuple[bool, bool, str]:
        report = preflight(
            self.spec.task, self.spec.assumptions, self.spec.success_criteria
        )
        if not report.ok:
            self.evidence["preflight"] = report.summary()
            return False, True, "preflight refused: " + report.summary()
        self.evidence["preflight"] = report.summary()
        self.evidence["guidance"] = guidance_block().splitlines()[0]
        findings = scan_agent_config(self.spec.build_config)
        severe = [f for f in findings if f.severity in ("critical", "high")]
        self.evidence["shield"] = (
            f"{len(findings)} shield findings, {len(severe)} severe"
            if findings
            else "shield scan clean"
        )
        if severe:
            worst = severe[0]
            return (
                False,
                True,
                f"shield scan blocked the run: {worst.rule} "
                f"({worst.severity}) at {worst.location}",
            )
        ok, reason = self._advance_ecc("plan")
        if not ok:
            return False, True, reason
        return True, False, "plan passed"

    def _node_understand(self, workdir: Path) -> tuple[bool, bool, str]:
        target = Path(self.spec.target_dir)
        if not target.is_absolute():
            target = workdir / target
        result = build_graph(
            target, runner=self.spec.graph_runner or subprocess.run
        )
        self.evidence["graphify"] = f"{result.status}: {result.detail}"
        if result.status == "built" and result.graph_json:
            graph = CodeGraph.load(result.graph_json)
            terms = self.spec.graph_terms or [self.spec.target_agent]
            hits = {term: len(graph.query(term)) for term in terms}
            self.evidence["graph_query"] = ", ".join(
                f"{term}={count}" for term, count in hits.items()
            )
            if len(terms) >= 2:
                first = graph.query(terms[0])
                second = graph.query(terms[1])
                if first and second:
                    path = graph.path(first[0]["id"], second[0]["id"])
                    self.evidence["graph_path"] = (
                        " -> ".join(path) if path else "no path"
                    )
        ok, reason = self._advance_ecc("test")
        if not ok:
            return False, True, reason
        return True, False, "understand passed"

    def _node_implement(self, workdir: Path) -> tuple[bool, bool, str]:
        if not self.spec.steps:
            return False, True, "no build steps declared — nothing to implement"
        for step in self.spec.steps:
            try:
                changed = step(workdir)
            except Exception as exc:  # noqa: BLE001 — reported, not raised
                return False, False, f"build step failed: {type(exc).__name__}: {exc}"
            self.changed_files.extend(str(p) for p in changed)
        self.evidence["implement"] = (
            f"{len(self.spec.steps)} steps, "
            f"{len(self.changed_files)} files changed"
        )
        ok, reason = self._advance_ecc("implement")
        if not ok:
            return False, True, reason
        return True, False, "implement passed"

    def _node_review(self, workdir: Path) -> tuple[bool, bool, str]:
        if not self.spec.scope_prefixes:
            return False, True, "no scope declared — scope check cannot pass"
        check = scope_check(self.changed_files, self.spec.scope_prefixes)
        self.evidence["scope"] = check.summary()
        if not check.ok:
            return False, True, "scope check refused: " + check.summary()
        ocr = run_ocr_review(
            self.changed_files,
            workdir=workdir,
            runner=self.spec.ocr_runner or subprocess.run,
        )
        self.evidence["ocr"] = f"{ocr.status}: {ocr.detail}"
        combined = supplement_review("PASS", ocr)
        self.evidence["review_verdict"] = (
            f"gate verdict {combined.gate_verdict} "
            f"(ocr changed gate: {combined.gate_changed_by_ocr})"
        )
        ok, reason = self._advance_ecc("review")
        if not ok:
            return False, True, reason
        return True, False, "review passed"

    def _node_test(self, workdir: Path) -> tuple[bool, bool, str]:
        if not self.spec.test_command:
            return False, True, "no test command declared — nothing to verify"
        proc = subprocess.run(
            self.spec.test_command,
            capture_output=True,
            text=True,
            timeout=self.spec.test_timeout,
            cwd=str(workdir),
        )
        passed = proc.returncode == 0
        tail = (proc.stdout or "")[-300:] or (proc.stderr or "")[-300:]
        self.harness.record_test_evidence(
            suite=" ".join(self.spec.test_command),
            passed=passed,
            detail=f"exit {proc.returncode}: {tail.strip()[:200]}",
        )
        self.evidence["tests"] = (
            f"exit {proc.returncode} ({'passed' if passed else 'FAILED'})"
        )
        if not passed:
            return False, False, (
                f"test command failed (exit {proc.returncode}): "
                f"{tail.strip()[:300]}"
            )
        # ECC is in verify by now (the review node advanced it); the
        # evidence is recorded here and the gate is checked by the
        # verify node, so no ECC advance happens in this node.
        return True, False, "tests passed"

    def _node_verify(self, workdir: Path) -> tuple[bool, bool, str]:
        veto = stage_gate(self.harness, "verify", "remember")
        if veto:
            self.evidence["verify_gate"] = f"vetoed: {veto}"
            return False, True, veto
        self.evidence["verify_gate"] = "passed: test evidence recorded and green"
        ok, reason = self._advance_ecc("verify")
        if not ok:
            return False, True, reason
        return True, False, "verify passed"

    def _node_remember(self, workdir: Path) -> tuple[bool, bool, str]:
        trusted = self.instincts.trusted_for(f"build:{self.spec.target_agent}")
        self.evidence["instincts"] = (
            f"{len(trusted)} trusted instincts for build:{self.spec.target_agent}"
        )
        ok, reason = self._advance_ecc("remember")
        if not ok:
            return False, True, reason
        return True, False, "remember passed"

    def _node_deliver(self, workdir: Path) -> tuple[bool, bool, str]:
        # The remember node already advanced the ECC run to its final
        # stage; deliver certifies the run is done, it does not advance
        # again (HarnessRun refuses to advance past "improve").
        if self.harness.stage != "improve":
            return (
                False,
                True,
                f"ECC stage mismatch: expected improve, at {self.harness.stage}",
            )
        if not self.harness.done:
            return False, True, "ECC run not done at deliver"
        return True, False, "deliver passed"
