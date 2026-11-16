"""TASK-IG2-FRG-08: the Claudex Loop (build/audit role-swap).

The loop's honesty properties are the tests: agreement only on a real
audit PASS, the swap actually alternating builder/auditor, findings
fed forward, UNAVAILABLE stopping the loop cold, and exhaustion never
reported as agreement.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.verification.claudex_loop import (
    LoopStatus,
    build_loop_prompt,
    parse_build_reply,
    run_claudex_loop,
)
from app.verification.review_passes import PassResult, ReviewIssue, ReviewStatus

A, B = "model-alpha", "model-beta"
FILES = {"main.py": "print('hello')\n"}


def _build_recorder(replies):
    """A fake build_fn: records (goal, files, findings) per call and
    returns the next canned reply."""
    calls = []

    async def build(goal, files, findings):
        calls.append({"goal": goal, "files": files, "findings": findings})
        return replies[len(calls) - 1]

    return build, calls


def _audit_sequence(statuses):
    """A fake audit_fn returning the given statuses in order, with one
    issue attached to each FINDINGS result."""
    calls = []

    async def audit(files, author, auditor):
        calls.append({"files": files, "author": author, "auditor": auditor})
        status = statuses[len(calls) - 1]
        issues = []
        if status is ReviewStatus.FINDINGS:
            issues = [
                ReviewIssue(
                    source="cross_model_audit",
                    severity="HIGH",
                    file_path="main.py",
                    description="prints instead of returning a value",
                )
            ]
        return PassResult(
            name="cross_model_audit",
            status=status,
            issues=issues,
            detail=f"fake audit {len(calls)}",
            author_model=author,
            reviewer_model=auditor,
        )

    return audit, calls


def _reply(files=FILES):
    return json.dumps({"files": files})


def test_agreement_on_first_clean_audit():
    build, build_calls = _build_recorder([_reply()])
    audit, audit_calls = _audit_sequence([ReviewStatus.PASS])
    result = asyncio.run(run_claudex_loop("goal", A, B, build, audit_fn=audit))
    assert result.status is LoopStatus.AGREED
    assert len(result.rounds) == 1
    assert result.rounds[0].builder_model == A
    assert result.rounds[0].auditor_model == B
    assert result.files == FILES
    assert audit_calls[0]["author"] == A and audit_calls[0]["auditor"] == B
    assert len(build_calls) == 1


def test_findings_feed_forward_and_roles_swap():
    build, build_calls = _build_recorder([_reply(), _reply({"main.py": "VALUE = 1\n"})])
    audit, audit_calls = _audit_sequence([ReviewStatus.FINDINGS, ReviewStatus.PASS])
    result = asyncio.run(run_claudex_loop("goal", A, B, build, audit_fn=audit))
    assert result.status is LoopStatus.AGREED
    assert len(result.rounds) == 2
    # Round 2 swapped: B builds, A audits.
    assert result.rounds[1].builder_model == B
    assert result.rounds[1].auditor_model == A
    assert audit_calls[1]["author"] == B and audit_calls[1]["auditor"] == A
    # The round-1 findings reached the round-2 builder as data.
    findings = build_calls[1]["findings"]
    assert len(findings) == 1
    assert findings[0]["description"] == "prints instead of returning a value"
    # And the round-2 builder started from the round-1 file set.
    assert build_calls[1]["files"] == FILES
    assert result.files == {"main.py": "VALUE = 1\n"}


def test_exhaustion_is_not_agreement():
    build, _ = _build_recorder([_reply(), _reply()])
    audit, _ = _audit_sequence([ReviewStatus.FINDINGS, ReviewStatus.FINDINGS])
    result = asyncio.run(
        run_claudex_loop("goal", A, B, build, audit_fn=audit, max_rounds=2)
    )
    assert result.status is LoopStatus.EXHAUSTED
    assert len(result.rounds) == 2
    assert "not as agreed" in result.detail


def test_unavailable_audit_stops_the_loop_immediately():
    build, build_calls = _build_recorder([_reply(), _reply(), _reply()])
    audit, _ = _audit_sequence([ReviewStatus.UNAVAILABLE])
    result = asyncio.run(
        run_claudex_loop("goal", A, B, build, audit_fn=audit, max_rounds=3)
    )
    assert result.status is LoopStatus.UNAVAILABLE
    assert len(result.rounds) == 1
    assert len(build_calls) == 1  # no second build past a missing audit


def test_same_model_and_bad_config_are_refused():
    build, _ = _build_recorder([_reply()])
    audit, _ = _audit_sequence([ReviewStatus.PASS])
    with pytest.raises(ValueError):
        asyncio.run(run_claudex_loop("goal", A, A, build, audit_fn=audit))
    with pytest.raises(ValueError):
        asyncio.run(run_claudex_loop("goal", A, B, build, audit_fn=audit, max_rounds=0))
    with pytest.raises(ValueError):
        asyncio.run(run_claudex_loop("goal", "", B, build, audit_fn=audit))


def test_build_failures_are_named_not_passed_over():
    audit, _ = _audit_sequence([ReviewStatus.PASS])

    async def raising_build(goal, files, findings):
        raise RuntimeError("provider down")

    result = asyncio.run(run_claudex_loop("goal", A, B, raising_build, audit_fn=audit))
    assert result.status is LoopStatus.BUILD_FAILED
    assert "provider down" in result.detail

    build, _ = _build_recorder(["I wrote some lovely code, trust me"])
    result = asyncio.run(run_claudex_loop("goal", A, B, build, audit_fn=audit))
    assert result.status is LoopStatus.BUILD_FAILED

    build, _ = _build_recorder([json.dumps({"files": {}})])
    result = asyncio.run(run_claudex_loop("goal", A, B, build, audit_fn=audit))
    assert result.status is LoopStatus.BUILD_FAILED


def test_default_audit_composes_cross_model_audit():
    build, _ = _build_recorder([_reply()])

    async def passing_review(prompt):
        return json.dumps({"verdict": "pass", "issues": []})

    result = asyncio.run(
        run_claudex_loop("goal", A, B, build, review_fn=passing_review)
    )
    assert result.status is LoopStatus.AGREED
    assert result.rounds[0].audit_status == "PASS"

    # No review provider at all: the default audit is UNAVAILABLE and
    # the loop stops — agreement is never manufactured from silence.
    build, build_calls = _build_recorder([_reply(), _reply()])
    result = asyncio.run(run_claudex_loop("goal", A, B, build, review_fn=None))
    assert result.status is LoopStatus.UNAVAILABLE
    assert len(build_calls) == 1


def test_parse_build_reply_strictness():
    assert parse_build_reply(_reply()) == FILES
    assert parse_build_reply(json.dumps(FILES)) == FILES  # bare shape accepted
    assert parse_build_reply("") is None
    assert parse_build_reply("no json here") is None
    assert parse_build_reply(json.dumps({"files": {}})) is None
    assert parse_build_reply(json.dumps({"files": {"a.py": 42}})) is None
    assert parse_build_reply(json.dumps(["not", "a", "dict"])) is None


def test_build_loop_prompt_states_the_swap_and_findings():
    findings = [
        {"severity": "HIGH", "file_path": "main.py", "description": "boom"}
    ]
    prompt = build_loop_prompt("the goal", FILES, findings, A, B)
    assert "the goal" in prompt
    assert A in prompt and B in prompt
    assert "boom" in prompt
    assert "COMPLETE file set" in prompt
