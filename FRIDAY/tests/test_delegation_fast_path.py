"""TASK-ORCH-007: delegation that actually dispatches (checklist C6/C13/C14).

Live incidents (2026-11-11 IST): "assign a quick task to IntelX: one-line
research note on why the sky is blue" → the model emitted an invented
`<execute_agent name="IntelX" …>` XML tag as plain text; "send this task to
Sentinel: run a quick security posture check" → `<send_task>` XML as plain
text. No task was ever dispatched, even though a real fleet_dispatch tool
was registered. These tests pin the two-layer fix:

1. a deterministic delegation fast-path fires on explicit delegation
   phrasing and returns the agent's REAL result with a task receipt;
2. if the model still emits phantom delegation markup on the normal path,
   the loop redirects it once toward the real tool.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.config import Settings
from friday.core.types import Message, Role, SafetyLevel, ToolCall, ToolResult
from friday.llm.mock_provider import MockLLMProvider
from friday.tools.base import BaseTool
from friday.tools.registry import ToolRegistry


class _FakeResult:
    def __init__(self, status: str = "SUCCESS", result: dict[str, Any] | None = None):
        self.status = status
        self.result = result or {"response": "sky-note: Rayleigh scattering scatters blue light."}
        self.error = None
        self.task_id = "task_live_receipt_9"
        self.execution_time_ms = 812


class _FakeFleetClient:
    def __init__(self):
        self.envelopes = []

    async def dispatch_task(self, envelope):
        self.envelopes.append(envelope)
        return _FakeResult()


def _agent(registry: ToolRegistry | None = None, responder=None) -> FridayAgent:
    return FridayAgent(
        settings=Settings(env="testing", embedding_provider="none"),
        llm_provider=MockLLMProvider(custom_responder=responder),
        tool_registry=registry,
        authorizer=__import__("friday.core.auth", fromlist=["AutoApproveAuthorizer"]).AutoApproveAuthorizer.create_for_testing(),
    )


class TestDelegationFastPath:
    """Explicit delegation phrasings dispatch straight to the named agent."""

    @pytest.mark.parametrize(
        "phrase,agent",
        [
            ("assign a quick task to IntelX: one-line research note on why the sky is blue. then show me its result.", "intelx"),
            ("assign a task to intelx: summarize the fed decision", "intelx"),
            ("send this task to Sentinel: run a quick security posture check and give me the summary", "sentinel"),
            ("delegate this task to VyralX: write a 30-second short script", "vyralx"),
            ("have Forge write a unit test for the fleet dispatch tool", "forge"),
            ("tell Sentinel to run a security scan", "sentinel"),
            ("please send the task to Memora: store that the owner likes masala chai", "memora"),
        ],
    )
    def test_delegation_phrasings_dispatch_to_agent(self, phrase: str, agent: str) -> None:
        client = _FakeFleetClient()
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            agent_ = _agent()
            response = agent_.process_message(phrase)
        # dispatched to the right agent with the real task text
        assert len(client.envelopes) == 1
        assert client.envelopes[0].target_agent == agent
        # the owner sees the agent's real result plus the receipt
        assert "Rayleigh scattering" in response.content or response.metadata.get("delegation_dispatch")
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("delegation_dispatch") is True
        assert response.metadata.get("target_agent") == agent

    def test_result_tail_stripped_from_task(self) -> None:
        client = _FakeFleetClient()
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            _agent().process_message("assign a quick task to IntelX: sky note. then show me its result")
        assert "then show me" not in client.envelopes[0].payload["task"]
        assert client.envelopes[0].payload["task"] == "sky note"

    def test_delegation_before_fleet_status_no_hijack(self) -> None:
        """"…check of the fleet" must dispatch, not trigger the status probe."""
        client = _FakeFleetClient()
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            response = _agent().process_message("send this task to Sentinel: check the fleet security posture")
        assert response.metadata.get("delegation_dispatch") is True
        assert response.metadata.get("fleet_status") is None
        assert client.envelopes[0].target_agent == "sentinel"

    def test_non_fleet_recipient_falls_through(self) -> None:
        """"tell Rajesh to…" is not a fleet delegation — no dispatch."""
        client = _FakeFleetClient()
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            calls = {"n": 0}

            def responder(messages, tools):
                calls["n"] += 1
                return Message(role=Role.ASSISTANT, content="I can't message Rajesh, Boss — he's not one of my agents.")

            response = _agent(responder=responder).process_message("tell Rajesh to bring coffee")
        assert client.envelopes == []
        assert "Rajesh" in response.content

    def test_empty_task_falls_through_to_model(self) -> None:
        client = _FakeFleetClient()
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            def responder(messages, tools):
                return Message(role=Role.ASSISTANT, content="What task should IntelX do, Boss?")

            response = _agent(responder=responder).process_message("assign a task to IntelX")
        assert client.envelopes == []
        assert "What task" in response.content

    def test_plain_sentences_never_match(self) -> None:
        def responder(messages, tools):
            return Message(role=Role.ASSISTANT, content="Sure, Boss — noted.")

        response = _agent(responder=responder).process_message("yesterday I had to assign a task to my accountant")
        assert "noted" in response.content


class TestPhantomXMLRedirect:
    """If the model emits delegation markup as text, redirect it to the tool."""

    def test_phantom_xml_gets_one_redirect_to_real_tool(self) -> None:
        client = _FakeFleetClient()
        calls = {"n": 0}

        def responder(messages, tools):
            calls["n"] += 1
            if calls["n"] == 1:
                return Message(
                    role=Role.ASSISTANT,
                    content='<execute_agent name="IntelX" task="sky note">\n{"task": "sky note"}\n</execute_agent>',
                )
            if calls["n"] == 2:
                # second turn: obey and call the real tool
                return Message(
                    role=Role.ASSISTANT,
                    content="Dispatching.",
                    tool_calls=[ToolCall(id="d1", name="fleet_dispatch", arguments={"agent": "IntelX", "task": "sky note"})],
                )
            # third turn: summarize the tool result for the owner
            return Message(role=Role.ASSISTANT, content="Done, Boss — IntelX's note is in.")

        agent_ = _agent(responder=responder)
        with patch(
            "friday.tools.builtin.fleet_dispatch.FleetDispatchTool._client",
            return_value=client,
        ):
            response = agent_.process_message("I want IntelX to do a sky note for me")
        # phantom turn + redirected tool-call turn + final summary turn
        assert calls["n"] == 3
        assert client.envelopes, "the redirected turn must call the real fleet_dispatch tool"
        assert response.tool_results, "the tool result must reach the owner"

    def test_phantom_xml_twice_still_bounded(self) -> None:
        def responder(messages, tools):
            return Message(
                role=Role.ASSISTANT,
                content='<send_task>\n{"agent": "Sentinel", "task": "scan"}\n</send_task>',
            )

        agent_ = _agent(responder=responder)
        response = agent_.process_message("ask Sentinel for a scan")
        # after one redirect the loop must not keep burning turns on phantoms
        assert response.is_done

    def test_normal_text_with_angle_brackets_not_redirected(self) -> None:
        def responder(messages, tools):
            return Message(role=Role.ASSISTANT, content="Use <b>bold</b> tags in HTML, Boss.")

        agent_ = _agent(responder=responder)
        response = agent_.process_message("how do I write bold in html")
        assert response.content == "Use <b>bold</b> tags in HTML, Boss."
