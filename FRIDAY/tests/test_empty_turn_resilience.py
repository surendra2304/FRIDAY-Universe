"""TASK-ORCH-005: empty-turn resilience in the agent cognitive loop.

Live incident (2026-11-11 IST): a delegation request through /api/chat
("assign a quick task to IntelX...") received a single empty visible turn
from the live reasoning model (gpt-oss-120b via Groq — the whole output sat
in the reasoning channel; content empty, no tool calls). The loop broke on
the first empty turn and the owner saw "I could not complete the request
within the action limit." after 4.7 seconds with no tool ever attempted.

These tests pin the corrected behavior:

1. a first empty turn triggers exactly one nudged retry — the model's
   second answer reaches the owner;
2. two consecutive empty turns still end gracefully with the honest
   fallback (the loop stays bounded);
3. an empty turn followed by a tool call still executes the tool and
   finishes normally.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.auth import AutoApproveAuthorizer
from friday.core.config import Settings
from friday.core.types import Message, Role, SafetyLevel, ToolCall, ToolResult
from friday.llm.mock_provider import MockLLMProvider
from friday.tools.base import BaseTool
from friday.tools.registry import ToolRegistry


class _ProbeTool(BaseTool):
    """Minimal safe tool so the loop has something real to call."""

    name = "probe_ping"
    description = "Returns a fixed acknowledgment (test probe)."
    safety_level = SafetyLevel.SAFE
    parameters = {"type": "object", "properties": {"note": {"type": "string"}}}

    def execute(self, note: str = "", **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_call_id="probe",
            name=self.name,
            content=f"probe ok: {note}",
            safety_level=SafetyLevel.SAFE,
        )


def _agent_with(responder) -> tuple[FridayAgent, MockLLMProvider]:
    registry = ToolRegistry()
    registry.register(_ProbeTool())
    provider = MockLLMProvider(custom_responder=responder)
    agent = FridayAgent(
        settings=Settings(env="testing", embedding_provider="none"),
        llm_provider=provider,
        tool_registry=registry,
        authorizer=AutoApproveAuthorizer.create_for_testing(),
    )
    return agent, provider


class TestEmptyTurnNudge:
    """One empty visible turn must not kill the request."""

    def test_empty_then_answer_reaches_owner(self) -> None:
        turns: list[Message] = []

        def responder(messages, tools):
            turns.append(messages[-1] if messages else None)
            if len(turns) == 1:
                # The live failure shape: no tool calls, nothing visible
                # (either truly empty or only <thought> text).
                return Message(role=Role.ASSISTANT, content="")
            return Message(role=Role.ASSISTANT, content="On it, Boss — done.")

        agent, provider = _agent_with(responder)
        response = agent.process_message("analyze the feasibility of a solar-powered router")

        assert response.is_done
        assert response.content == "On it, Boss — done."
        assert response.metadata.get("success") is True
        # Exactly two model turns: the empty one plus the nudged retry.
        assert len(provider.call_history) == 2
        # The nudge must have been a system message, not a silent retry.
        nudges = [
            m for m in provider.call_history[1]
            if m.role == Role.SYSTEM and "no visible answer" in (m.content or "")
        ]
        assert nudges, "the retry turn must carry the plain-text nudge"

    def test_whitespace_only_turn_is_treated_as_empty(self) -> None:
        """Blank visible content (reasoning lived in the model's reasoning
        channel) must be treated as empty and nudged, not accepted as the
        answer."""
        def responder(messages, tools):
            if len(provider.call_history) == 1:
                return Message(role=Role.ASSISTANT, content="   ")
            return Message(role=Role.ASSISTANT, content="Dispatched and verified.")

        agent, provider = _agent_with(responder)
        response = agent.process_message("assign the sky-note task to IntelX now")
        assert response.content == "Dispatched and verified."
        assert len(provider.call_history) == 2

    def test_empty_then_tool_call_still_executes(self) -> None:
        def responder(messages, tools):
            if len(provider.call_history) == 1:
                return Message(role=Role.ASSISTANT, content="")
            return Message(
                role=Role.ASSISTANT,
                content="Probing.",
                tool_calls=[ToolCall(id="p1", name="probe_ping", arguments={"note": "go"})],
            )

        agent, provider = _agent_with(responder)
        response = agent.process_message("run the probe")
        assert response.tool_results, "the nudged retry's tool call must execute"
        assert any("probe ok: go" in (r.content or "") for r in (response.tool_results or []))


class TestBoundedLoop:
    """The nudge must never unbound the loop."""

    def test_all_empty_turns_end_with_honest_fallback(self) -> None:
        def responder(messages, tools):
            return Message(role=Role.ASSISTANT, content="")

        agent, provider = _agent_with(responder)
        response = agent.process_message("probe ping with note go")

        assert response.is_done
        assert "action limit" in response.content
        # Two empty turns are enough — no full max_tool_iterations burn.
        assert len(provider.call_history) == 2

    def test_empty_streak_resets_after_a_real_turn(self) -> None:
        """Empty, empty -> stop is bounded; but empty -> real -> empty retries again."""
        calls = {"n": 0}

        def responder(messages, tools):
            calls["n"] += 1
            if calls["n"] in (1,):
                return Message(role=Role.ASSISTANT, content="")
            if calls["n"] == 2:
                return Message(
                    role=Role.ASSISTANT,
                    content="Probing.",
                    tool_calls=[ToolCall(id="p1", name="probe_ping", arguments={"note": "x"})],
                )
            if calls["n"] == 3:
                # A tool result came back; now another empty turn must be
                # nudged once more rather than breaking immediately.
                return Message(role=Role.ASSISTANT, content="")
            return Message(role=Role.ASSISTANT, content="All done, Boss.")

        agent, provider = _agent_with(responder)
        response = agent.process_message("probe then report")
        assert response.content == "All done, Boss."
        assert len(provider.call_history) == 4
