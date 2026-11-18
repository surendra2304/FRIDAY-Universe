"""
Sentinel/app/services/finding_validation_gate.py — a 7-question
false-positive gate for security findings.

TASK-SEN-020 (IG intake round 2, 2026-11-18; source shortcode
DfoioTRhRTr — a post showcasing the Claude-BugHunter skill bundle,
whose standout mechanism is a "7-QUESTION VALIDATION GATE — kills
false positives before reports"). PATTERN ADOPTION ONLY: no part of
that external red-team bundle is imported, copied or installed; the
gate questions are re-derived here against Sentinel's own finding
contract (Sentinel/contracts/finding.schema.json).

Why this exists
---------------
Sentinel's finding contract already carries the statuses `verified`,
`false_positive` and `review_required`, and demands that findings be
"strictly anchored to raw evidence artifacts" — but nothing decided
WHEN a finding has earned `verified`. This module is that decision:
a deterministic, auditable checklist a finding must pass in full
before it may be marked verified (and so reported onward as fact).
A finding that fails is routed to `review_required` with the failed
questions named — never silently dropped, and never promoted on
confidence alone.

The 7 questions (all must pass)
--------------------------------
1. evidence_attached     — evidence_refs is non-empty (the contract's
                           own anchoring rule).
2. target_identified     — target_ref names a concrete asset.
3. severity_justified    — high/critical findings state their impact;
                           lower severities carry a real description.
4. exploitability_stated — high/critical findings state an
                           exploitability context (not required below
                           high).
5. confidence_floor      — confidence meets the floor for its
                           severity (info 0.0 / low 0.3 / medium 0.5 /
                           high 0.7 / critical 0.8).
6. not_duplicate         — no other live finding (status not in
                           {false_positive, remediated}) on the same
                           target with the same title or a shared CVE.
7. remediation_stated    — a remediation path is written down.

Pure logic: finding dicts in, a GateVerdict out. No I/O, no clock,
no mutable state — the same inputs always give the same verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

#: Minimum confidence a finding must carry for its severity before it
#: may be verified. A scanner's hunch is not a verified finding.
CONFIDENCE_FLOORS: dict[str, float] = {
    "info": 0.0,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "critical": 0.8,
}

_HIGH_SEVERITIES = {"high", "critical"}

#: Statuses whose findings no longer count as duplicates of a new one.
_DEAD_STATUSES = {"false_positive", "remediated"}


@dataclass
class GateCheck:
    """One gate question and its outcome."""

    question: str
    passed: bool
    detail: str


@dataclass
class GateVerdict:
    """The gate's decision for one finding."""

    passed: bool
    recommended_status: str  # "verified" when passed, else "review_required"
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def failed_questions(self) -> list[str]:
        return [c.question for c in self.checks if not c.passed]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "recommended_status": self.recommended_status,
            "failed_questions": self.failed_questions,
            "checks": [
                {"question": c.question, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalised(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def _find_duplicate(finding: dict, existing: Iterable[dict]) -> dict | None:
    """A live finding on the same target with the same title or a shared CVE."""
    target = _normalised(finding.get("target_ref"))
    if not target:
        return None
    title = _normalised(finding.get("title"))
    cves = {_normalised(c) for c in (finding.get("related_cves") or []) if _text(c)}
    own_id = _text(finding.get("id"))
    for other in existing or ():
        if not isinstance(other, dict):
            continue
        if own_id and _text(other.get("id")) == own_id:
            continue  # a finding is never its own duplicate
        if _normalised(other.get("status") or "open") in _DEAD_STATUSES:
            continue
        if _normalised(other.get("target_ref")) != target:
            continue
        if title and _normalised(other.get("title")) == title:
            return other
        other_cves = {
            _normalised(c) for c in (other.get("related_cves") or []) if _text(c)
        }
        if cves and cves & other_cves:
            return other
    return None


def validate_finding(
    finding: dict, existing: Iterable[dict] = ()
) -> GateVerdict:
    """Run the 7-question gate over one finding dict (finding.schema.json shape).

    ``existing`` is the pool of already-known findings used for the
    duplicate question. The verdict recommends `verified` only when
    every question passes; otherwise `review_required` with the failed
    questions named in the verdict.
    """
    if not isinstance(finding, dict):
        finding = {}
    severity = _normalised(finding.get("severity")) or "info"
    checks: list[GateCheck] = []

    # 1 — evidence attached (the contract's anchoring rule).
    refs = [r for r in (finding.get("evidence_refs") or []) if _text(r)]
    checks.append(
        GateCheck(
            "evidence_attached",
            bool(refs),
            f"{len(refs)} evidence ref(s) attached"
            if refs
            else "no evidence_refs — the finding is not anchored to raw evidence",
        )
    )

    # 2 — target identified.
    target = _text(finding.get("target_ref"))
    checks.append(
        GateCheck(
            "target_identified",
            bool(target),
            f"target: {target}" if target else "target_ref is empty",
        )
    )

    # 3 — severity justified.
    if severity in _HIGH_SEVERITIES:
        justified = bool(_text(finding.get("impact")))
        detail = (
            "impact stated"
            if justified
            else f"{severity} severity with no impact statement"
        )
    else:
        justified = bool(_text(finding.get("description")))
        detail = (
            "description present"
            if justified
            else "no description to justify the severity"
        )
    checks.append(GateCheck("severity_justified", justified, detail))

    # 4 — exploitability context (high/critical only).
    if severity in _HIGH_SEVERITIES:
        stated = bool(_text(finding.get("exploitability_context")))
        checks.append(
            GateCheck(
                "exploitability_stated",
                stated,
                "exploitability context stated"
                if stated
                else f"{severity} severity with no exploitability context",
            )
        )
    else:
        checks.append(
            GateCheck(
                "exploitability_stated",
                True,
                "not required below high severity",
            )
        )

    # 5 — confidence floor for the severity.
    try:
        confidence = float(finding.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    floor = CONFIDENCE_FLOORS.get(severity, 0.0)
    checks.append(
        GateCheck(
            "confidence_floor",
            confidence >= floor,
            f"confidence {confidence:.2f} vs floor {floor:.2f} for {severity}",
        )
    )

    # 6 — not a duplicate of a live finding.
    duplicate = _find_duplicate(finding, existing)
    checks.append(
        GateCheck(
            "not_duplicate",
            duplicate is None,
            "no live duplicate"
            if duplicate is None
            else f"duplicates live finding {_text(duplicate.get('id')) or '(no id)'} "
            f"on {_text(duplicate.get('target_ref'))}",
        )
    )

    # 7 — remediation stated.
    remediation = _text(finding.get("remediation"))
    checks.append(
        GateCheck(
            "remediation_stated",
            bool(remediation),
            "remediation stated" if remediation else "no remediation path written",
        )
    )

    passed = all(c.passed for c in checks)
    return GateVerdict(
        passed=passed,
        recommended_status="verified" if passed else "review_required",
        checks=checks,
    )
