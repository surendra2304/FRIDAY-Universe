"""Forge workflow pass: Reality Checker.

Adopted from The Agency's TestingRealityChecker role
(msitarzewski/agency-agents, testing/testing-reality-checker.md, MIT):
the senior integration specialist who stops fantasy approvals and
requires overwhelming evidence before production certification.

Rules carried over verbatim in spirit, implemented as deterministic
checks (no LLM, no network):

- Default verdict is NEEDS_WORK unless overwhelming proof says otherwise.
- "Zero issues found" or perfect scores (A+, 98/100) from prior agents
  are a red flag, not a green light — unless overwhelming proof backs them.
- Cross-check every claim against actual files and test results; never
  take a report at face value.
- Automatic-fail triggers: failing tests in the evidence, a claimed file
  that does not exist or is empty, a spec item with no evidence, a claim
  whose test numbers do not match the test evidence.
- First implementations typically need 2-3 revision cycles: a first pass
  (revision_cycles == 0) is flagged and its rating capped, even when the
  verdict is READY.

Ratings follow the role's template: C+ / B- / B / B+ (brutally honest).
There is no A. READY requires overwhelming proof; B+ additionally
requires at least one recorded revision cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "EvidenceItem",
    "RealityChecker",
    "RealityIssue",
    "RealityReport",
    "ShipCandidate",
    "SpecCompliance",
]

# Fantasy-assessment indicators (role: "AUTOMATIC FAIL" triggers).
_FANTASY_PATTERNS = (
    re.compile(r"zero issues found", re.IGNORECASE),
    re.compile(r"\b98/100\b"),
    re.compile(r"\b100/100\b"),
    re.compile(r"\bA\+(?![A-Za-z])"),
    re.compile(r"\bperfect score\b", re.IGNORECASE),
    re.compile(r"\bflawless\b", re.IGNORECASE),
)

# Commands the pass runs, recorded in the report (role Step 1).
REALITY_CHECK_COMMANDS = (
    "ls claimed files (existence + non-empty)",
    "cross-check claimed test numbers against test evidence",
    "cross-check every spec item against evidence",
    "scan claim for fantasy indicators",
)


@dataclass
class EvidenceItem:
    """One piece of evidence offered for the ship candidate."""

    kind: str  # "test_run" | "file" | "command_output" | "revision"
    reference: str  # e.g. "pytest Forge/tests/test_frg022_workflow_passes.py" or a path
    detail: str = ""
    passed: bool | None = None  # test_run: did it pass; None = not a pass/fail item
    tests_passed: int | None = None
    tests_total: int | None = None
    spec_refs: tuple[int, ...] = ()  # indices into ShipCandidate.spec this evidences


@dataclass
class ShipCandidate:
    """What is being asked to ship, and what it claims."""

    name: str
    claim: str  # free-text claim of what is done
    spec: list[str]  # acceptance items, in order
    evidence: list[EvidenceItem] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)  # path -> content
    claimed_files: list[str] = field(default_factory=list)
    claimed_tests_passed: int | None = None
    claimed_tests_total: int | None = None
    revision_cycles: int = 0


@dataclass
class SpecCompliance:
    """One spec item and whether any evidence covers it."""

    item: str
    evidenced: bool
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class RealityIssue:
    """One issue found by the Reality Checker."""

    code: str  # e.g. "failing-tests", "claim-not-in-file"
    severity: str  # "blocker" | "warning"
    message: str


@dataclass
class RealityReport:
    """Verdict of the Reality Checker pass."""

    candidate: str
    verdict: str  # "READY" | "NEEDS_WORK"
    rating: str  # "C+" | "B-" | "B" | "B+"
    issues: list[RealityIssue] = field(default_factory=list)
    spec_compliance: list[SpecCompliance] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    overwhelming_proof: bool = False
    required_fixes: list[str] = field(default_factory=list)

    @property
    def blockers(self) -> list[RealityIssue]:
        """Issues that keep the ship blocked."""
        return [i for i in self.issues if i.severity == "blocker"]


class RealityChecker:
    """Evidence-obsessed certification gate. Default: NEEDS_WORK.

    The checker never certifies READY on a claim alone: every spec item
    needs evidence, every claimed file must exist and be non-empty, every
    claimed test number must match a passing test run in the evidence.
    """

    def check(self, candidate: ShipCandidate) -> RealityReport:
        """Run the reality check over one ship candidate."""
        issues: list[RealityIssue] = []
        compliance: list[SpecCompliance] = []

        # --- Spec vs. implementation: every item needs evidence. ---
        for index, item in enumerate(candidate.spec):
            refs = [
                e.reference
                for e in candidate.evidence
                if index in e.spec_refs
            ]
            compliance.append(
                SpecCompliance(item=item, evidenced=bool(refs), evidence_refs=refs)
            )
            if not refs:
                issues.append(
                    RealityIssue(
                        code="spec-unevidenced",
                        severity="blocker",
                        message=(
                            f"Spec item {index + 1} has no evidence: {item!r}. "
                            "Quote the spec, show the evidence, or do not claim it."
                        ),
                    )
                )

        # --- Evidence must exist at all. ---
        if not candidate.evidence:
            issues.append(
                RealityIssue(
                    code="no-evidence",
                    severity="blocker",
                    message="No evidence offered at all — cannot certify anything.",
                )
            )

        # --- Failing tests are an automatic fail. ---
        for item in candidate.evidence:
            if item.kind == "test_run" and item.passed is False:
                issues.append(
                    RealityIssue(
                        code="failing-tests",
                        severity="blocker",
                        message=(
                            f"Test run failed: {item.reference} — {item.detail or 'no detail'}. "
                            "A ship with failing tests is not production ready."
                        ),
                    )
                )

        # --- Claimed files must exist and be non-empty. ---
        for path in candidate.claimed_files:
            content = candidate.files.get(path)
            if content is None:
                issues.append(
                    RealityIssue(
                        code="claim-not-in-file",
                        severity="blocker",
                        message=(
                            f"Claimed file does not exist in the change set: {path}. "
                            "The claim does not match reality."
                        ),
                    )
                )
            elif not content.strip():
                issues.append(
                    RealityIssue(
                        code="claim-not-in-file",
                        severity="blocker",
                        message=f"Claimed file is empty: {path}.",
                    )
                )

        # --- Claimed test numbers must match a passing test run. ---
        if candidate.claimed_tests_passed is not None or candidate.claimed_tests_total is not None:
            runs = [e for e in candidate.evidence if e.kind == "test_run"]
            matched = False
            for run in runs:
                if (
                    run.passed
                    and run.tests_passed == candidate.claimed_tests_passed
                    and run.tests_total == candidate.claimed_tests_total
                ):
                    matched = True
                    break
            if not matched:
                issues.append(
                    RealityIssue(
                        code="claim-test-mismatch",
                        severity="blocker",
                        message=(
                            f"Claimed test numbers "
                            f"{candidate.claimed_tests_passed}/{candidate.claimed_tests_total} "
                            "match no passing test run in the evidence."
                        ),
                    )
                )

        # --- Fantasy indicators: perfect scores / zero issues without proof. ---
        fantasy_hits = sorted({p.pattern for p in _FANTASY_PATTERNS if p.search(candidate.claim)})
        # Overwhelming proof is decided below; fantasy is a blocker unless
        # the rest of the evidence is overwhelming (all spec evidenced,
        # tests green, claims cross-checked). Compute the provisional state
        # without the fantasy issue itself.
        provisional_blockers = [i for i in issues if i.severity == "blocker"]
        test_runs = [e for e in candidate.evidence if e.kind == "test_run"]
        overwhelming = (
            not provisional_blockers
            and bool(test_runs)
            and all(e.passed for e in test_runs)
            and all(c.evidenced for c in compliance)
            and bool(candidate.evidence)
        )
        if fantasy_hits:
            if overwhelming:
                issues.append(
                    RealityIssue(
                        code="fantasy-claim",
                        severity="warning",
                        message=(
                            "Claim carries fantasy indicators "
                            f"({', '.join(fantasy_hits)}) but the evidence behind it "
                            "is overwhelming — noted, not blocking."
                        ),
                    )
                )
            else:
                issues.append(
                    RealityIssue(
                        code="fantasy-claim",
                        severity="blocker",
                        message=(
                            "Claim carries fantasy indicators "
                            f"({', '.join(fantasy_hits)}) with no overwhelming "
                            "proof behind them. Perfect scores without supporting "
                            "evidence are a red flag, not a green light."
                        ),
                    )
                )

        # --- First pass: typically needs 2-3 revision cycles. ---
        if candidate.revision_cycles == 0:
            issues.append(
                RealityIssue(
                    code="first-pass",
                    severity="warning",
                    message=(
                        "First pass: no revision cycle is evidenced. First "
                        "implementations typically need 2-3 revision cycles; "
                        "the rating is capped even if the verdict is READY."
                    ),
                )
            )

        blockers = [i for i in issues if i.severity == "blocker"]
        # Recompute overwhelming proof with the final blocker set: READY
        # only when nothing blocks and the evidence is complete.
        overwhelming = (
            not blockers
            and bool(test_runs)
            and all(e.passed for e in test_runs)
            and all(c.evidenced for c in compliance)
            and bool(candidate.evidence)
        )
        verdict = "READY" if overwhelming else "NEEDS_WORK"
        if verdict == "READY":
            rating = "B+" if candidate.revision_cycles >= 1 else "B"
        elif blockers:
            rating = "C+"
        else:
            rating = "B-"

        required_fixes = [i.message for i in blockers]
        return RealityReport(
            candidate=candidate.name,
            verdict=verdict,
            rating=rating,
            issues=issues,
            spec_compliance=compliance,
            commands_executed=list(REALITY_CHECK_COMMANDS),
            overwhelming_proof=overwhelming,
            required_fixes=required_fixes,
        )
