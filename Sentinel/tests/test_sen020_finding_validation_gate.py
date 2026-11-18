"""Tests for TASK-SEN-020 finding_validation_gate (stdlib-only).

The gate adapts the 7-question false-positive validation gate from the
Claude-BugHunter bundle (IG intake round 2, shortcode DfoioTRhRTr) to
Sentinel's finding contract: a finding earns "verified" only when all
seven questions pass.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.finding_validation_gate import validate_finding  # noqa: E402


def _finding(**over):
    finding = {
        "id": "F-1",
        "task_id": "T-1",
        "title": "Open telnet on build host",
        "description": "Telnet service listening on the build host; banner captured.",
        "target_ref": "host:build-01",
        "severity": "high",
        "confidence": 0.9,
        "exploitability_context": "Unauthenticated remote login service on the LAN.",
        "impact": "Remote shell access to the build host.",
        "evidence_refs": ["evidence/F-1/nmap.txt"],
        "related_cves": [],
        "related_cwes": ["CWE-319"],
        "remediation": "Disable telnet; enforce SSH key-only access.",
        "status": "open",
    }
    finding.update(over)
    return finding


def test_complete_finding_passes_all_seven():
    result = validate_finding(_finding())
    assert result.passed is True
    assert result.recommended_status == "verified"
    assert result.failed == []
    assert len(result.checks) == 7


def test_missing_evidence_fails_question_1():
    result = validate_finding(_finding(evidence_refs=[]))
    assert result.passed is False
    assert result.recommended_status == "review_required"
    assert result.failed == ["evidence_attached"]


def test_missing_target_fails_question_2():
    result = validate_finding(_finding(target_ref=""))
    assert result.failed == ["target_identified"]


def test_high_severity_without_impact_fails_question_3():
    result = validate_finding(_finding(impact=None))
    assert result.failed == ["severity_justified"]


def test_unknown_severity_fails_question_3():
    result = validate_finding(_finding(severity="catastrophic"))
    assert "severity_justified" in result.failed


def test_critical_without_exploitability_fails_question_4():
    result = validate_finding(
        _finding(severity="critical", confidence=0.95, exploitability_context=None)
    )
    assert result.failed == ["exploitability_stated"]


def test_low_severity_needs_no_exploitability_or_impact():
    result = validate_finding(
        _finding(
            severity="low",
            confidence=0.5,
            impact=None,
            exploitability_context=None,
        )
    )
    assert result.passed is True


def test_confidence_below_floor_fails_question_5():
    result = validate_finding(_finding(confidence=0.4))  # high floor is 0.7
    assert result.failed == ["confidence_floor"]


def test_duplicate_open_finding_fails_question_6():
    twin = _finding(id="F-0")
    result = validate_finding(_finding(), existing=[twin])
    assert result.failed == ["not_duplicate"]


def test_duplicate_by_shared_cve_fails_question_6():
    twin = _finding(id="F-0", title="Something else entirely",
                    related_cves=["CVE-2026-0001"])
    result = validate_finding(
        _finding(related_cves=["cve-2026-0001"]), existing=[twin]
    )
    assert result.failed == ["not_duplicate"]


def test_remediated_twin_does_not_block_a_fresh_report():
    twin = _finding(id="F-0", status="remediated")
    result = validate_finding(_finding(), existing=[twin])
    assert result.passed is True


def test_same_title_on_a_different_target_is_not_a_duplicate():
    twin = _finding(id="F-0", target_ref="host:other-99")
    result = validate_finding(_finding(), existing=[twin])
    assert result.passed is True


def test_finding_is_never_its_own_duplicate():
    result = validate_finding(_finding(), existing=[_finding()])
    assert result.passed is True


def test_missing_remediation_fails_question_7():
    result = validate_finding(_finding(remediation=None))
    assert result.failed == ["remediation_stated"]


def test_minimal_info_finding_can_pass():
    result = validate_finding(_finding(
        severity="info",
        confidence=0.0,
        impact=None,
        exploitability_context=None,
    ))
    assert result.passed is True


def test_blank_evidence_refs_fail_question_1():
    result = validate_finding(_finding(evidence_refs=["", "   "]))
    assert result.passed is False
    assert result.failed == ["evidence_attached"]
    # a real ref among blanks still counts
    result = validate_finding(_finding(evidence_refs=["", "evidence/F-1/nmap.txt"]))
    assert result.passed is True


def test_duplicate_with_case_variant_target_fails_question_6():
    twin = _finding(id="F-0", target_ref=" HOST:Build-01 ")
    result = validate_finding(_finding(), existing=[twin])
    assert result.failed == ["not_duplicate"]


def test_mixed_case_false_positive_twin_does_not_block_a_fresh_report():
    twin = _finding(id="F-0", status="False_Positive")
    result = validate_finding(_finding(), existing=[twin])
    assert result.passed is True


def test_non_dict_finding_is_routed_to_review_not_raised():
    for bad in (None, "not a finding", ["not", "a", "finding"], 42):
        result = validate_finding(bad)
        assert result.passed is False
        assert result.recommended_status == "review_required"
        assert "evidence_attached" in result.failed


def test_as_dict_shape():
    result = validate_finding(_finding(evidence_refs=[]))
    payload = result.as_dict()
    assert payload["passed"] is False
    assert payload["recommended_status"] == "review_required"
    assert payload["failed"] == ["evidence_attached"]
    assert [c["name"] for c in payload["checks"]] == [
        "evidence_attached",
        "target_identified",
        "severity_justified",
        "exploitability_stated",
        "confidence_floor",
        "not_duplicate",
        "remediation_stated",
    ]
