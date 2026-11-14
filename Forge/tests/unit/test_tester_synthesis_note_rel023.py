"""TASK-REL-023: the verification gate must name its true cause.

Round 3 (2026-11-14) production evidence: task17414112026145722's tester
stage called Inference POST /v1/forge/generate-tests, which answered 200
after ~60s with NO usable tests (the service returns an empty test_code
with generation_status degraded/invalid_output when its routed model
fails). TesterRole swallowed that outcome (``except Exception: pass`` +
an unchecked ``test_code``), ran pytest over an empty project, and the
gate failed with a bare "no test files discovered" that named the wrong
cause. These tests pin the honesty plumbing: the generation outcome is
recorded and prefixed onto the gate result, and the test-file scan is
repeated AFTER synthesis so the runner sees what synthesis wrote.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agents.roles import TesterRole
from app.integrations import ai_universe_client


class _StubProvider:
    async def generate(self, prompt, system_prompt=None, temperature=0.2):
        return SimpleNamespace(
            content="",
            usage=SimpleNamespace(total_tokens=0, estimated_cost_usd=0.0),
        )


class _StubFS:
    def __init__(self):
        self.search_calls = 0

    def search_files(self, task_id, pattern, role):
        self.search_calls += 1
        return []

    def read_file(self, task_id, path, role):
        return "def is_palindrome(s):\n    return s == s[::-1]\n"


@pytest.mark.asyncio
async def test_degraded_generation_is_named_in_gate_result(monkeypatch, tmp_path):
    degraded_client = SimpleNamespace(
        generate_tests=AsyncMock(return_value={
            "test_code": "",
            "generation_status": "degraded",
            "error": "provider unavailable",
        })
    )
    monkeypatch.setattr(
        ai_universe_client, "get_ai_universe_client", lambda: degraded_client
    )

    fs = _StubFS()
    engine = SimpleNamespace(
        fs=fs,
        wm=SimpleNamespace(
            get_workspace_paths=lambda task_id: SimpleNamespace(project=tmp_path)
        ),
        terminal=SimpleNamespace(
            run_command=AsyncMock(return_value=SimpleNamespace(
                exit_code=5, stdout="", stderr="no tests ran", command="pytest"
            ))
        ),
    )

    role = TesterRole(provider=_StubProvider())
    result = await role.execute_step(
        task_id="task_rel023",
        node_title="Automated Test Suite & Verification Gate",
        context={"goal": "write a palindrome checker", "requirements": []},
        engine=engine,
    )

    # TASK-REL-026 semantics update (disclosed): this exact scenario —
    # generation degraded, no tests from any path, nothing executed — is
    # no longer a "failed" verdict on the code. It is the distinct,
    # retryable "blocked" outcome (failure_kind
    # test_generation_unavailable). The REL-023 pins below are unchanged:
    # the outcome still names the generation status, and test files are
    # still re-scanned after synthesis.
    assert result["status"] == "blocked"
    assert result["failure_kind"] == "test_generation_unavailable"
    assert result["retryable"] is True
    assert "generation_status='degraded'" in result["stderr"], (
        "the gate outcome must name the test-generation outcome, not just "
        "pytest's empty-discovery message"
    )
    assert fs.search_calls >= 2, "test files must be re-scanned after synthesis"
