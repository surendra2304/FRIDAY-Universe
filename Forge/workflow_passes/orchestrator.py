"""Forge workflow pass: Agents Orchestrator (Chief of Staff).

Adopted from The Agency's AgentsOrchestrator role
(msitarzewski/agency-agents, specialized/agents-orchestrator.md, MIT):
the conductor who runs the entire dev pipeline from spec to ship.

Rules carried over, implemented as deterministic coordination
(no LLM, no network):

- Pipeline phases, in order, each a quality gate: the AI Code Auditor
  (security) runs first; only if it passes does the Reality Checker
  (final integration gate, Phase 4 in the Agency pipeline) run. No phase
  advancement without meeting quality standards.
- Evidence required: every decision rests on the passes' actual outputs.
- Retry limits: maximum 3 attempts per task before escalation. A blocked
  ship says "revise and resubmit (attempt n/3)"; past the limit the
  verdict is ESCALATED with a detailed failure report.
- Fail-closed: inconclusive evidence defaults to BLOCKED, never to ship.
- The Reality Checker blocks the ship until it is proven to work; the
  auditor blocks on critical/high findings (a leaked secret or an open
  injection hole is never a warning).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ai_code_auditor import AICodeAuditor, AuditReport
from .reality_checker import RealityChecker, RealityReport, ShipCandidate

__all__ = ["AgentsOrchestrator", "ShipVerdict"]

#: Attempts before the orchestrator escalates instead of retrying.
MAX_ATTEMPTS = 3


@dataclass
class ShipVerdict:
    """Outcome of one orchestrated ship attempt."""

    candidate: str
    status: str  # "READY_TO_SHIP" | "BLOCKED" | "ESCALATED"
    phase: str  # "audit" | "reality" | "complete"
    attempt: int
    max_attempts: int
    audit: AuditReport | None = None
    reality: RealityReport | None = None
    next_action: str = ""
    blockers: list[str] = field(default_factory=list)

    @property
    def ship_blocked(self) -> bool:
        """True unless the orchestrator certified the ship."""
        return self.status != "READY_TO_SHIP"

    def status_report(self) -> str:
        """Pipeline progress report (Agency status-report template)."""
        lines = [
            "# WorkflowOrchestrator Status Report",
            "",
            f"**Candidate**: {self.candidate}",
            f"**Current Phase**: {self.phase}",
            f"**Attempt**: {self.attempt}/{self.max_attempts}",
            f"**Status**: {self.status}",
            "",
        ]
        if self.audit is not None:
            counts = self.audit.counts
            lines.append(
                "## Audit Pass (AI Code Auditor)\n"
                f"Files scanned: {self.audit.files_scanned} — "
                f"{len(self.audit.findings)} findings "
                f"({counts['critical']} critical, {counts['high']} high, "
                f"{counts['medium']} medium, {counts['low']} low)"
            )
            for finding in self.audit.findings:
                lines.append(f"- {finding.render().splitlines()[0]}")
            lines.append("")
        if self.reality is not None:
            lines.append(
                "## Reality Pass (Reality Checker)\n"
                f"Verdict: {self.reality.verdict} — rating {self.reality.rating} "
                f"(overwhelming proof: {self.reality.overwhelming_proof})"
            )
            for issue in self.reality.issues:
                lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}")
            lines.append("")
        if self.blockers:
            lines.append("## Blockers")
            for blocker in self.blockers:
                lines.append(f"- {blocker}")
            lines.append("")
        lines.append(f"## Next Action\n{self.next_action}")
        return "\n".join(lines)


class AgentsOrchestrator:
    """Coordinate the two workflow passes over a ship candidate.

    Phase 1 — audit (AI Code Auditor): any critical/high finding blocks
    the ship; the reality pass does not run.
    Phase 2 — reality (Reality Checker): NEEDS_WORK blocks the ship.
    Phase 3 — ship: READY_TO_SHIP only when both passes are clean.
    """

    def __init__(self, max_attempts: int = MAX_ATTEMPTS):
        self.max_attempts = max_attempts
        self.auditor = AICodeAuditor()
        self.reality_checker = RealityChecker()

    def run(
        self,
        candidate: ShipCandidate,
        files: dict[str, str],
        client_reachable: frozenset[str] | set[str] = frozenset(),
        attempt: int = 1,
    ) -> ShipVerdict:
        """Run the pipeline over one ship candidate. Fail-closed."""
        audit = self.auditor.audit(files, client_reachable)
        if audit.blocking:
            return self._blocked(
                candidate, "audit", attempt, audit, None,
                [f.render() for f in audit.blocking],
            )

        reality = self.reality_checker.check(candidate)
        if reality.verdict != "READY":
            return self._blocked(
                candidate, "reality", attempt, audit, reality,
                list(reality.required_fixes),
            )

        return ShipVerdict(
            candidate=candidate.name,
            status="READY_TO_SHIP",
            phase="complete",
            attempt=attempt,
            max_attempts=self.max_attempts,
            audit=audit,
            reality=reality,
            next_action="Ship it. Both passes are clean; the Reality Checker certified READY.",
        )

    def _blocked(
        self,
        candidate: ShipCandidate,
        phase: str,
        attempt: int,
        audit: AuditReport | None,
        reality: RealityReport | None,
        blockers: list[str],
    ) -> ShipVerdict:
        if attempt >= self.max_attempts:
            return ShipVerdict(
                candidate=candidate.name,
                status="ESCALATED",
                phase=phase,
                attempt=attempt,
                max_attempts=self.max_attempts,
                audit=audit,
                reality=reality,
                next_action=(
                    f"Escalate with a detailed failure report: {phase} gate failed "
                    f"on attempt {attempt}/{self.max_attempts}. Do not retry without "
                    "new evidence or a changed approach."
                ),
                blockers=blockers,
            )
        return ShipVerdict(
            candidate=candidate.name,
            status="BLOCKED",
            phase=phase,
            attempt=attempt,
            max_attempts=self.max_attempts,
            audit=audit,
            reality=reality,
            next_action=(
                f"Revise and resubmit (attempt {attempt}/{self.max_attempts}): "
                f"fix the {phase}-gate blockers and re-run with evidence."
            ),
            blockers=blockers,
        )
