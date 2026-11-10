"""TASK-FOR-002: real code tasks through FRIDAY chat, executed by Forge.

"Friday, write me a script that does X" must reach Forge (the sandboxed SWE
agent — security-reviewed under TASK-FOR-001) and return the REAL build
result, never a conversational "sure, here's how you could..." from the LLM
and never a fabricated success.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.routing.capability_router import (
    CapabilityRouter,
    ExecutionCapabilityType,
)
from friday.tools.builtin.forge_code_task import ForgeCodeTool


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None,
                 error: str | None = None, summary: str = ""):
        self.status = status
        self.result = result or {}
        self.error = error
        self.summary = summary
        self.task_id = "task_frg1"
        self.execution_time_ms = 8500


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result
        self.envelopes = []

    async def dispatch_task(self, envelope):
        self.envelopes.append(envelope)
        return self._result


class _BrokenFleetClient:
    async def dispatch_task(self, envelope):
        raise ConnectionError("forge unreachable")


class TestCodeTaskQuestionsRouteToForge:
    @pytest.mark.parametrize(
        "request_text",
        [
            "friday, write me a script that converts csv to json",
            "build me a small web page for my portfolio",
            "write a function that validates emails",
            "fix this bug in the parser",
            "refactor this function to use async",
            "review the code in the auth module",
        ],
    )
    def test_code_tasks_route_to_forge(self, request_text: str) -> None:
        decision = CapabilityRouter().route_request(request_text)
        assert decision.selected_capability != ExecutionCapabilityType.DIRECT_REASONING, (
            f"{request_text!r} routed to DIRECT_REASONING — code tasks need Forge"
        )
        forge = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["forge_code_task"]
        ]
        assert forge, f"{request_text!r} produced no forge_code_task candidate"

    def test_plain_chat_stays_conversational(self) -> None:
        decision = CapabilityRouter().route_request("hello, what can you do for me")
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING


class TestForgeToolReportsTruth:
    def test_successful_build_result(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {
            "plan": {"steps": [{"description": "Scaffold converter script"}, {"description": "Add CSV parser"}]},
            "verification_manifest": {"stages": [{"status": "passed"}, {"status": "passed"}, {"status": "passed"}]},
            "artifacts": [{"name": "csv2json.py"}],
        }, summary="Built csv2json.py with 3/3 verification stages passed."))
        result = ForgeCodeTool(fleet_client=client).execute(goal="write a script that converts csv to json")
        assert not result.is_error
        assert "csv2json.py" in result.content
        assert "3/3 stages passed" in result.content
        assert "Scaffold converter script" in result.content
        assert "TASK-FOR-001" in result.content  # sandbox provenance stated
        env = client.envelopes[0]
        assert env.target_agent == "forge"
        assert env.action == "build"
        assert env.payload["execute_now"] is True

    def test_forge_failure_is_honest(self) -> None:
        result = ForgeCodeTool(fleet_client=_FakeFleetClient(
            _FakeResult("FAILED", error="Verification failed: 1 of 3 stages failed")
        )).execute(goal="build a thing")
        assert result.is_error
        assert "could not complete" in result.content
        assert "1 of 3 stages failed" in result.content
        assert "nothing was fabricated" in result.content

    def test_crash_is_honest(self) -> None:
        result = ForgeCodeTool(fleet_client=_BrokenFleetClient()).execute(goal="build a thing")
        assert result.is_error
        assert "could not reach Forge" in result.content
        assert "Nothing was built" in result.content

    def test_empty_goal_rejected(self) -> None:
        result = ForgeCodeTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", {}))).execute(goal="  ")
        assert result.is_error
        assert "code task" in result.content

    def test_requirements_are_forwarded(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {}, summary="done"))
        ForgeCodeTool(fleet_client=client).execute(
            goal="write a script", requirements=["no external deps", "python 3.12"]
        )
        assert client.envelopes[0].payload["requirements"] == ["no external deps", "python 3.12"]


class TestWindowsTypingDirectiveDoesNotSwallowCodeTasks:
    """The Windows 'type/write' keyboard directive must not eat code tasks."""

    def test_write_me_a_script_is_not_a_typing_request(self) -> None:
        from friday.devices.windows_friday import windows_friday

        handled, reply, meta = windows_friday.handle_directive(
            "friday, write me a script that converts csv to json"
        )
        assert handled is False, (
            f"the Windows typing directive swallowed a code task: {reply!r}"
        )

    def test_plain_typing_still_works(self) -> None:
        from friday.devices.windows_friday import windows_friday

        handled, _, meta = windows_friday.handle_directive("type hello world")
        assert handled is True
        assert meta.get("action") == "type_text"
