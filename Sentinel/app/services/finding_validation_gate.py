"""
Sentinel/app/services/finding_validation_gate.py — a 7-question
false-positive validation gate for security findings.

TASK-SEN-020 (IG intake round 2, 2026-11-18; source shortcode DfoioTRhRTr —
the Claude-BugHunter bundle post, @githubprojects). PATTERN ADOPTION ONLY:
the external red-team skill bundle itself is NOT imported into the fleet;
the one mechanism adopted is its 7-question validation gate — in the
bundle's own words, a gate that "kills false positives before reports" —
re-expressed over Sentinel's own finding contract
(Sentinel/contracts/finding.schema.json).

Why this exists
---------------
Sentinel's finding contract already carries the lifecycle statuses
open / verified / false_positive / remediated / accepted /
review_required, and demands findings be "strictly anchored to raw
evidence artifacts" — but nothing decided WHEN a finding has earned
"verified". This module is that decision: seven deterministic questions,
all of which must pass before a finding may be marked verified (and so
reported upward as fact). Anything less is routed to review_required
with the failed questions named — never silently dropped, never
silently believed.

The seven questions (adapted from the source bundle's gate):
1. evidence_attached    — is raw evidence attached? (evidence_refs;
                          blank refs do not count)
2. target_identified    — is the affected target identified? (target_ref)
3. severity_justified   — is the severity backed by a stated impact?
                          (impact required for high/critical; a real
                          description otherwise)
4. exploitability_stated — for high/critical, is the exploitability
                          context stated rather than implied?
5. confidence_floor     — does the reporter's confidence clear the
                          floor for the claimed severity?
6. not_duplicate        — is this the same finding already open?
                          (same target + same title, or same target +
                          a shared CVE, against non-closed findings;
                          target and status compared case- and
                          whitespace-insensitively)
7. remediation_stated   — is a remediation path stated?

Deterministic, stdlib-only, no I/O: the caller hands in finding dicts in
the contract's shape and gets back a GateResult. The gate never mutates
the finding; applying the recommended status is the caller's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

#: Minimum reporter confidence a finding must carry for its claimed
#: severity to be believable without re-verification (question 5).
CONFIDENCE_FLOORS: dict[str, float] = {
    "info": 0.0,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "critical": 0.8,
}

#: Severities whose claims need impact + exploitability spelled out
#: (questions 3 and 4).
_HIGH_SEVERITIES = ("high", "critical")

#: Statuses that close a finding out of the duplicate check (question 6):
#: a remediated or false-positive twin must not block a fresh report.
_CLOSED_STATUSES = {"false_positive", "remediated"}


@dataclass
class CheckResult:
    """One gate question and its outcome."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class GateResult:
    """The gate's verdict for one finding."""

    passed: bool
    recommended_status: str  # "verified" when passed, else "review_required"
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> list[str]:
        """Names of the questions the finding did not answer."""
        return [c.name for c in self.checks if not c.passed]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "recommended_status": self.recommended_status,
            "failed": self.failed,
            "checks": [c.as_dict() for c in self.checks],
        }


def _text(finding: dict[str, Any], key: str) -> str:
    value = finding.get(key)
    return value.strip() if isinstance(value, str) else ""


def _norm_title(title: str) -> str:
    return " ".join(title.lower().split())


def _norm_key(value: str) -> str:
    """Case/whitespace-insensitive comparison key (duplicate question)."""
    return _norm_title(value)


def _is_duplicate(
    finding: dict[str, Any], existing: Iterable[dict[str, Any]]
) -> str:
    """Return the twin finding's id when `finding` duplicates an open one."""
    target = _norm_key(_text(finding, "target_ref"))
    if not target:
        return ""
    title = _norm_title(_text(finding, "title"))
    cves = {str(c).upper() for c in finding.get("related_cves") or []}
    for other in existing:
        if other.get("id") == finding.get("id"):
            continue  # never its own duplicate
        if _norm_key(str(other.get("status") or "open")) in _CLOSED_STATUSES:
            continue
        if _norm_key(_text(other, "target_ref")) != target:
            continue
        if title and _norm_title(_text(other, "title")) == title:
            return str(other.get("id") or "?")
        other_cves = {str(c).upper() for c in other.get("related_cves") or []}
        if cves and cves & other_cves:
            return str(other.get("id") or "?")
    return ""


def validate_finding(
    finding: dict[str, Any],
    existing: Iterable[dict[str, Any]] = (),
) -> GateResult:
    """Run the 7-question gate over one finding dict (contract shape).

    `existing` is the caller's current finding set for the duplicate
    question. The finding is never mutated; the caller applies
    `recommended_status` if it adopts the verdict. A non-dict
    `finding` never raises: it is treated as an empty finding and
    routed to review_required.
    """
    if not isinstance(finding, dict):
        finding = {}
    severity_raw = _text(finding, "severity").lower()
    severity = severity_raw if severity_raw in CONFIDENCE_FLOORS else "info"
    checks: list[CheckResult] = []

    # 1 — evidence attached (only non-blank string refs count: a blank
    # ref anchors the finding to nothing)
    evidence = [
        ref
        for ref in (finding.get("evidence_refs") or [])
        if isinstance(ref, str) and ref.strip()
    ]
    checks.append(CheckResult(
        "evidence_attached",
        bool(evidence),
        f"{len(evidence)} evidence ref(s) attached"
        if evidence else "no evidence_refs — a finding without raw evidence is a rumour",
    ))

    # 2 — target identified
    target = _text(finding, "target_ref")
    checks.append(CheckResult(
        "target_identified",
        bool(target),
        f"target_ref: {target}" if target else "target_ref is empty",
    ))

    # 3 — severity justified by stated impact
    impact = _text(finding, "impact")
    description = _text(finding, "description")
    if severity in _HIGH_SEVERITIES:
        justified = bool(impact)
        detail = "impact stated" if justified else (
            f"severity {severity} claimed with no impact statement"
        )
    else:
        justified = bool(description)
        detail = "description substantiates the claim" if justified else (
            "no description substantiating the claim"
        )
    if severity_raw not in CONFIDENCE_FLOORS:
        justified = False
        detail = f"unknown severity {severity_raw!r} — not in the finding contract"
    checks.append(CheckResult("severity_justified", justified, detail))

    # 4 — exploitability stated (high/critical only)
    exploitability = _text(finding, "exploitability_context")
    if severity in _HIGH_SEVERITIES:
        checks.append(CheckResult(
            "exploitability_stated",
            bool(exploitability),
            "exploitability context stated" if exploitability else (
                f"severity {severity} claimed with no exploitability_context"
            ),
        ))
    else:
        checks.append(CheckResult(
            "exploitability_stated", True,
            f"not required at severity {severity}",
        ))

    # 5 — confidence floor for the claimed severity
    try:
        confidence = float(finding.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    floor = CONFIDENCE_FLOORS[severity]
    checks.append(CheckResult(
        "confidence_floor",
        confidence >= floor,
        f"confidence {confidence:.2f} vs floor {floor:.2f} for {severity}",
    ))

    # 6 — not a duplicate of an open finding
    twin = _is_duplicate(finding, existing)
    checks.append(CheckResult(
        "not_duplicate",
        not twin,
        f"duplicates open finding {twin}" if twin else "no open twin found",
    ))

    # 7 — remediation stated
    remediation = _text(finding, "remediation")
    checks.append(CheckResult(
        "remediation_stated",
        bool(remediation),
        "remediation stated" if remediation else "no remediation path stated",
    ))

    passed = all(c.passed for c in checks)
    return GateResult(
        passed=passed,
        recommended_status="verified" if passed else "review_required",
        checks=checks,
    )
