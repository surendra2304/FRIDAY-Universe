"""
Multi-agent coordination: specialists reviewing each other's work and fixing it.

Before this module the agents in a FORGE run never actually interacted. Each
DAG node was dispatched to one specialist in a parallel wave, the results were
written to a shared context, and that was the whole story. There was no review
step, no hand-off, and no path by which one agent could act on another's
findings -- the only thing called "consensus" was an HTTP call to an external
service.

This coordinator makes the collaboration real and, importantly, *objective*:

  * REVIEWERS are the specialist checkers (build, lint, security, tests). They
    are the same code the verification battery uses, so a finding is a fact with
    an exit code and a file, not an opinion.
  * FIXERS are the engineering agents (Debugger, Developer). They read the
    findings, write the repair through the normal workspace tools, and the
    reviewers then re-check their work.

That review -> repair -> re-review loop is what "agents helping each other"
means here, and because the reviewers are objective it works with every model
endpoint unreachable -- the fixer degrades to the deterministic repairer, and
the loop still converges or honestly reports that it did not.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.verification.checkers import (
    BuildChecker,
    LintChecker,
    SecurityChecker,
    TestChecker,
)

logger = get_logger("agents.coordinator")


@dataclass
class ReviewFinding:
    """One actionable defect found by a reviewer agent."""

    reviewer: str
    check_name: str
    severity: str
    detail: str
    target_file: str | None = None

    def as_prompt(self) -> str:
        loc = f" in {self.target_file}" if self.target_file else ""
        return f"[{self.severity}] {self.check_name}{loc}: {self.detail}"


@dataclass
class ReviewOutcome:
    """Result of a review -> repair -> re-review cycle."""

    rounds: int = 0
    findings_before: int = 0
    findings_after: int = 0
    resolved: int = 0
    introduced: int = 0
    repairs: list[str] = field(default_factory=list)
    agents_involved: list[str] = field(default_factory=list)
    clean: bool = False
    duration_ms: float = 0.0

    @property
    def summary(self) -> str:
        return (
            f"rounds={self.rounds} findings {self.findings_before}->{self.findings_after} "
            f"resolved={self.resolved} introduced={self.introduced} "
            f"agents={','.join(self.agents_involved) or 'none'} clean={self.clean}"
        )


# Reviewer agents: name -> checker class. The name is what shows up in the audit
# trail and in the outcome, so it reads as "which specialist looked at this".
REVIEWERS: dict[str, Any] = {
    "build_engineer": BuildChecker,
    "code_reviewer": LintChecker,
    "security_reviewer": SecurityChecker,
    "test_engineer": TestChecker,
}


def _severity_for(check_name: str, exit_code: int) -> str:
    if "Security" in check_name:
        return "critical"
    if "Build" in check_name or "Test" in check_name:
        return "high"
    return "medium"


_FILENAME_RE = re.compile(r"[\w./-]+\.py\b")


def _extract_target_file(detail: str) -> str | None:
    """Pull a plausible filename out of a checker's output, if there is one.

    Checkers emit things like ``[{'file': 'a.py', 'line': 4, ...}]``. Splitting on
    whitespace leaves ``'a.py',`` attached to its quotes and comma, so an
    endswith('.py') test never matched and the deterministic repairer was handed
    a finding with no target file -- which silently disabled that repair route
    for exactly the findings it was written for.
    """
    match = _FILENAME_RE.search(detail or "")
    if not match:
        return None
    name = match.group(0)
    # An absolute path points outside the project workspace, so fall back to the
    # bare filename. A relative path is kept as-is: reducing "src/util.py" to
    # "util.py" sent the fixer looking for a file at the project root, which is
    # not where the reviewer said the defect was, and the repair was silently
    # skipped.
    return name.lstrip("/").split("/")[-1] if name.startswith("/") else name


class AgentCoordinator:
    """Runs reviewer agents over a workspace and delegates repairs to fixers."""

    def __init__(self, engine, max_rounds: int = 2):
        self.engine = engine
        self.max_rounds = max_rounds
        self._reviewers = {name: cls() for name, cls in REVIEWERS.items()}

    # ------------------------------------------------------------------
    # review
    # ------------------------------------------------------------------

    async def review_workspace(self, task_id: str) -> list[ReviewFinding]:
        """Have every reviewer agent inspect the workspace and report findings."""
        findings: list[ReviewFinding] = []
        for name, checker in self._reviewers.items():
            try:
                evidence = await checker.run_check(task_id=task_id, engine=self.engine)
            except Exception as exc:
                logger.warning(f"Reviewer '{name}' failed on task {task_id}: {exc}")
                continue
            if evidence.passed:
                continue
            detail = (evidence.stderr or evidence.stdout or "").strip()
            if not detail and evidence.issues:
                detail = str(evidence.issues[0])[:400]
            findings.append(
                ReviewFinding(
                    reviewer=name,
                    check_name=evidence.check_name,
                    severity=_severity_for(evidence.check_name, evidence.exit_code),
                    detail=detail[:600],
                    target_file=_extract_target_file(detail),
                )
            )
        return findings

    # ------------------------------------------------------------------
    # repair
    # ------------------------------------------------------------------

    async def delegate_repair(
        self, task_id: str, findings: list[ReviewFinding]
    ) -> list[str]:
        """Hand the findings to a fixer agent and report what it changed.

        The Debugger is asked first because root-cause repair is its job; the
        Developer is the fallback for anything the Debugger declines. Both write
        through the normal workspace tools, so a repair is auditable and
        permission-checked exactly like any other agent action.
        """
        if not findings:
            return []

        from app.agents.roles import DebuggerRole, DeveloperRole

        brief = "\n".join(f.as_prompt() for f in findings)
        changed: list[str] = []

        for role_name, role_cls in (("debugger", DebuggerRole), ("developer", DeveloperRole)):
            try:
                agent = role_cls()
                result = await agent.execute_step(
                    task_id=task_id,
                    node_title=f"Peer review remediation ({len(findings)} findings)",
                    context={
                        "error": brief,
                        "terminal_logs": "",
                        "findings": [f.as_prompt() for f in findings],
                        "project_files": [],
                    },
                    engine=self.engine,
                )
            except Exception as exc:
                logger.warning(f"Fixer agent '{role_name}' failed on task {task_id}: {exc}")
                continue

            touched = (result or {}).get("fixed_files") or []
            for path in touched:
                if path not in changed:
                    changed.append(path)
            if touched:
                logger.info(
                    f"[Task {task_id}] Fixer '{role_name}' changed {len(touched)} file(s)"
                )
                break
            logger.info(f"[Task {task_id}] Fixer '{role_name}' made no changes")

        # The deterministic repairer is the last line of defence: it needs no
        # provider and can close the obvious syntax defects on its own.
        if not changed:
            from app.recovery.engine import RecoveryEngine

            recovery = RecoveryEngine(exec_engine=self.engine)
            for finding in findings:
                if not finding.target_file or not finding.target_file.endswith(".py"):
                    continue
                try:
                    self.engine.fs.read_file(
                        task_id, finding.target_file, role="debugger"
                    )
                except Exception:
                    continue
                patch = recovery._deterministic_syntax_repair(
                    task_id,
                    finding.target_file,
                    _synthetic_diagnosis(finding),
                )
                if patch is None:
                    continue
                if recovery.applicator.apply_patch(task_id, patch, role="debugger"):
                    changed.append(finding.target_file)
                    logger.info(
                        f"[Task {task_id}] Deterministic repair applied to "
                        f"{finding.target_file}"
                    )

        return changed

    # ------------------------------------------------------------------
    # the loop
    # ------------------------------------------------------------------

    async def review_and_repair(self, task_id: str) -> ReviewOutcome:
        """Review, delegate repairs, and re-review until clean or out of rounds."""
        started = time.perf_counter()
        outcome = ReviewOutcome()

        findings = await self.review_workspace(task_id)
        outcome.findings_before = len(findings)
        seen = {f.check_name for f in findings}

        if not findings:
            outcome.clean = True
            outcome.duration_ms = (time.perf_counter() - started) * 1000
            return outcome

        for round_index in range(1, self.max_rounds + 1):
            outcome.rounds = round_index
            logger.info(
                f"[Task {task_id}] Peer review round {round_index}: "
                f"{len(findings)} finding(s) from "
                f"{sorted({f.reviewer for f in findings})}"
            )

            changed = await self.delegate_repair(task_id, findings)
            for path in changed:
                if path not in outcome.repairs:
                    outcome.repairs.append(path)
            outcome.agents_involved = sorted(
                set(outcome.agents_involved)
                | {f.reviewer for f in findings}
                | ({"debugger"} if changed else set())
            )

            if not changed:
                logger.info(
                    f"[Task {task_id}] No agent could act on the findings; "
                    "stopping the review loop"
                )
                break

            findings = await self.review_workspace(task_id)
            outcome.findings_after = len(findings)

            resolved = len(seen - {f.check_name for f in findings})
            outcome.resolved += max(0, resolved)
            new_checks = {f.check_name for f in findings} - seen
            outcome.introduced += len(new_checks)
            seen |= {f.check_name for f in findings}

            if not findings:
                outcome.clean = True
                break

        outcome.findings_after = len(findings)
        outcome.duration_ms = (time.perf_counter() - started) * 1000
        logger.info(f"[Task {task_id}] Peer review outcome: {outcome.summary}")
        return outcome


def _synthetic_diagnosis(finding: ReviewFinding):
    """Build a minimal FailureDiagnosis for the deterministic repairer."""
    from app.recovery.classifier import FailureClass, FailureDiagnosis

    return FailureDiagnosis(
        failure_class=FailureClass.SYNTAX_ERROR
        if "Build" in finding.check_name
        else FailureClass.UNKNOWN,
        error_message=finding.detail[:200],
        failing_file=finding.target_file,
        suggested_strategy="deterministic syntax repair",
    )
