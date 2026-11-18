"""Tests for TASK-SEN-020 finding_validation_gate (stdlib-only).

The gate adopts the 7-question validation pattern from the
Claude-BugHunter post (IG intake round 2, DfoioTRhRTr): a finding
must answer every question before it may be marked verified.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finding_validation_gate import validate_finding  # noqa: E402


def _complete_high(**overrides):
    finding = {
        "id": "F-1",
        "title": "Unauthenticated bridge endpoint reachable",
        "description": "The bridge answers run_shell without any credential.",
        "target_ref": "server2:bridge",
        "severity": "high",
        "confidence": 0.9,
        "exploitability_context": "Anyone who can reach the port can call it.",
        "impact": "Full shell on the fleet host.",
        "evidence_refs": ["evidence/probe-2026-11-18.txt"],
        "related_cves": [],
        "remediation": "Enable the merged bridge auth and restart the service.",
        "status": "open",
    }
    finding.update(overrides)
    return finding


def test_complete_high_finding_passes_all_seven():
    verdict = validate_finding(_complete_high())
    assert verdict.passed is True
    assert verdict.recommended_status == "verified"
    assert verdict.failed_questions == []
    assert len(verdict.checks) == 7


def test_missing_evidence_fails_question_1():
    verdict = validate_finding(_complete_high(evidence_refs=[]))
    assert verdict.passed is False
    assert verdict.recommended_status == "review_required"
    assert "evidence_attached" in verdict.failed_questions


def test_missing_target_fails_question_2():
    verdict = validate_finding(_complete_high(target_ref="  "))
    assert "target_identified" in verdict.failed_questions


def test_high_without_impact_fails_question_3_but_medium_does_not():
    high = validate_finding(_complete_high(impact=None))
    assert "severity_justified" in high.failed_questions
    medium = validate_finding(
        _complete_high(severity="medium", impact=None, confidence=0.6)
    )
    assert "severity_justified" not in medium.failed_questions


def test_exploitability_required_only_at_high_and_above():
    high = validate_finding(_complete_high(exploitability_context=None))
    assert "exploitability_stated" in high.failed_questions
    low = validate_finding(
        _complete_high(
            severity="low",
            exploitability_context=None,
            impact=None,
            confidence=0.4,
        )
    )
    assert "exploitability_stated" not in low.failed_questions


def test_confidence_floor_scales_with_severity():
    weak_high = validate_finding(_complete_high(confidence=0.6))
    assert "confidence_floor" in weak_high.failed_questions
    strong_critical = validate_finding(
        _complete_high(severity="critical", confidence=0.85)
    )
    assert "confidence_floor" not in strong_critical.failed_questions
    weak_critical = validate_finding(
        _complete_high(severity="critical", confidence=0.75)
    )
    assert "confidence_floor" in weak_critical.failed_questions


def test_duplicate_live_finding_fails_question_6():
    existing = [_complete_high(id="F-0")]
    verdict = validate_finding(_complete_high(), existing=existing)
    assert "not_duplicate" in verdict.failed_questions


def test_dead_or_distinct_findings_are_not_duplicates():
    dead = [_complete_high(id="F-0", status="false_positive")]
    assert "not_duplicate" not in validate_finding(
        _complete_high(), existing=dead
    ).failed_questions
    distinct = [_complete_high(id="F-0", title="Something else entirely")]
    assert "not_duplicate" not in validate_finding(
        _complete_high(), existing=distinct
    ).failed_questions
    itself = [_complete_high()]  # same id — never its own duplicate
    assert "not_duplicate" not in validate_finding(
        _complete_high(), existing=itself
    ).failed_questions


def test_shared_cve_on_same_target_is_a_duplicate():
    existing = [
        _complete_high(id="F-0", title="Different wording", related_cves=["CVE-2026-1234"])
    ]
    verdict = validate_finding(
        _complete_high(related_cves=["cve-2026-1234"]), existing=existing
    )
    assert "not_duplicate" in verdict.failed_questions


def test_missing_remediation_fails_question_7():
    verdict = validate_finding(_complete_high(remediation=None))
    assert "remediation_stated" in verdict.failed_questions


def test_empty_finding_goes_to_review_with_reasons():
    verdict = validate_finding({})
    assert verdict.passed is False
    assert verdict.recommended_status == "review_required"
    assert "evidence_attached" in verdict.failed_questions
    assert "target_identified" in verdict.failed_questions
    assert "remediation_stated" in verdict.failed_questions
    as_dict = verdict.as_dict()
    assert as_dict["passed"] is False
    assert len(as_dict["checks"]) == 7
