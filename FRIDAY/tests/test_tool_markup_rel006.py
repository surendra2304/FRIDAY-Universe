"""TASK-REL-006A: tool-call markup must execute, never leak as the reply.

Production evidence (console round 1, 2026-11-14): "tell me a joke AND what
time is it in Tokyo right now" was answered with the raw string
``<tool name="get_current_time" params='{"timezone":"Asia/Tokyo"}'/>`` —
the model (Groq gpt-oss-120b) spelled its tool call as text markup, no
provider parsed that shape, the agent loop only guarded invented delegation
XML, and the turn ended. Live re-probes the same day found the sibling
misroutes pinned here too:

* "Tell me a joke and tell me ..." dispatched to **Memora** because
  ``normalize_agent("me")`` substring-matched "me" inside "memora";
* the Windows directive layer answered compound/location time questions
  with the host clock alone (bare substring match), dropping the rest.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.auth import AutoApproveAuthorizer
from friday.core.config import Settings
from friday.core.types import Message, Role
from friday.llm.mock_provider import MockLLMProvider
from friday.llm.tool_markup import (
    canonical_tool_name,
    extract_markup_tool_calls,
    strip_tool_markup,
)
from friday.tools.builtin.time_date import TimeDateTool
from friday.tools.registry import ToolRegistry

ROUND1_MARKUP = """<tool name="get_current_time" params='{"timezone":"Asia/Tokyo"}'/>"""


# --------------------------------------------------------------------------
# markup parser
# --------------------------------------------------------------------------
class TestMarkupParser:
    def test_round1_shape_recovers_aliased_call_with_args(self) -> None:
        calls, remaining = extract_markup_tool_calls(ROUND1_MARKUP)
        assert len(calls) == 1
        # The model invented "get_current_time"; the registered tool is
        # "get_time_date" — the alias map must bridge them.
        assert calls[0].name == "get_time_date"
        assert calls[0].arguments == {"timezone": "Asia/Tokyo"}
        assert remaining == ""

    def test_tool_tag_with_json_body(self) -> None:
        calls, _ = extract_markup_tool_calls(
            '<tool name="get_time_date">{"timezone": "Europe/London"}</tool>'
        )
        assert len(calls) == 1
        assert calls[0].arguments == {"timezone": "Europe/London"}

    def test_function_tag_shape(self) -> None:
        calls, _ = extract_markup_tool_calls(
            '<function=get_current_time>{"timezone":"Asia/Tokyo"}</function>'
        )
        assert len(calls) == 1
        assert calls[0].name == "get_time_date"

    def test_plain_text_is_untouched(self) -> None:
        calls, remaining = extract_markup_tool_calls("Just a normal answer.")
        assert calls == []
        assert remaining == "Just a normal answer."

    def test_strip_removes_even_unclosed_markup(self) -> None:
        assert "<tool" not in strip_tool_markup(ROUND1_MARKUP)
        assert strip_tool_markup("Answer. <tool name='x'>") == "Answer."

    def test_alias_map(self) -> None:
        assert canonical_tool_name("get_current_time") == "get_time_date"
        assert canonical_tool_name("get_time_date") == "get_time_date"


# --------------------------------------------------------------------------
# provider parsing (Groq — the fleet's usual provider)
# --------------------------------------------------------------------------
class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content, "tool_calls": None})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class TestGroqMarkupRecovery:
    def test_groq_parse_recovers_markup_tool_call(self) -> None:
        from friday.llm.groq_provider import GroqLLMProvider

        msg = GroqLLMProvider._parse_response(_FakeResponse(ROUND1_MARKUP))
        assert msg.tool_calls and len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "get_time_date"
        assert msg.tool_calls[0].arguments == {"timezone": "Asia/Tokyo"}
        assert "<tool" not in (msg.content or "")


# --------------------------------------------------------------------------
# agent loop: markup turn executes the tool, final answer is clean text
# --------------------------------------------------------------------------
class TestAgentLoopMarkupExecution:
    def test_markup_turn_executes_tool_and_answers(self) -> None:
        registry = ToolRegistry()
        registry.register(TimeDateTool())
        turns = {"n": 0}

        def responder(messages, tools):
            turns["n"] += 1
            if turns["n"] == 1:
                # The round-1 failure shape, verbatim.
                return Message(role=Role.ASSISTANT, content=ROUND1_MARKUP)
            tool_msgs = [m for m in messages if m.role == Role.TOOL]
            assert tool_msgs, "the recovered markup call must produce a TOOL message"
            return Message(
                role=Role.ASSISTANT,
                content=(
                    "Why did the scarecrow win an award? Because he was "
                    f"outstanding in his field! And in Tokyo: {tool_msgs[-1].content}"
                ),
            )

        agent = FridayAgent(
            settings=Settings(env="testing", embedding_provider="none"),
            llm_provider=MockLLMProvider(custom_responder=responder),
            tool_registry=registry,
            authorizer=AutoApproveAuthorizer.create_for_testing(),
        )
        response = agent.execute_complex_task(
            goal="tell me a joke and what time it is in Tokyo right now",
            context={"current_user_request": "tell me a joke and what time it is in Tokyo right now"},
        )
        assert "<tool" not in response.content
        assert "scarecrow" in response.content
        assert "Asia/Tokyo" in response.content
        assert response.tool_results, "the time tool must actually have run"
        assert response.tool_results[0].name == "get_time_date"


# --------------------------------------------------------------------------
# TimeDateTool timezone support
# --------------------------------------------------------------------------
class TestTimeDateTimezone:
    def test_tokyo_time_is_tokyo_not_ist(self) -> None:
        result = TimeDateTool().execute(timezone="Asia/Tokyo")
        assert not result.is_error
        assert "Asia/Tokyo" in result.content
        match = re.search(r"Current Time \(Asia/Tokyo\): (\d{2}):(\d{2}):(\d{2})", result.content)
        assert match, result.content
        shown_minutes = int(match.group(1)) * 60 + int(match.group(2))
        expected = datetime.now(tz=timezone.utc).astimezone(ZoneInfo("Asia/Tokyo"))
        expected_minutes = expected.hour * 60 + expected.minute
        assert abs(shown_minutes - expected_minutes) <= 1

    def test_default_stays_ist(self) -> None:
        result = TimeDateTool().execute()
        assert "IST" in result.content

    def test_unknown_timezone_falls_back_honestly(self) -> None:
        result = TimeDateTool().execute(timezone="Mars/Olympus")
        assert "IST" in result.content
        assert "not a timezone I recognise" in result.content


# --------------------------------------------------------------------------
# delegation pronoun guard ("tell me" is not an agent)
# --------------------------------------------------------------------------
class TestNormalizeAgentPronouns:
    @pytest.mark.parametrize("word", ["me", "you", "us", "it", "myself"])
    def test_pronouns_never_resolve_to_agents(self, word: str) -> None:
        from friday.tools.builtin.fleet_dispatch import normalize_agent

        assert normalize_agent(word) is None

    def test_real_agents_still_resolve(self) -> None:
        from friday.tools.builtin.fleet_dispatch import normalize_agent

        assert normalize_agent("memora") == "memora"
        assert normalize_agent("IntelX") == "intelx"
        assert normalize_agent("the forge agent") == "forge"


# --------------------------------------------------------------------------
# Windows directive layer: compound/location clock questions decline
# --------------------------------------------------------------------------
class TestWindowsClockAnchoring:
    def _handle(self, text: str):
        from friday.devices.windows_friday import windows_friday

        return windows_friday.handle_directive(text)

    def test_bare_time_question_still_answers(self) -> None:
        handled, reply, meta = self._handle("what time is it")
        assert handled and meta.get("action") == "time"
        assert "current time" in reply.lower()

    def test_tokyo_time_question_declines(self) -> None:
        handled, _reply, _meta = self._handle("what time is it in Tokyo right now")
        assert handled is False

    def test_compound_joke_and_time_declines(self) -> None:
        handled, _reply, _meta = self._handle(
            "tell me a joke and what time is it in Tokyo right now"
        )
        assert handled is False
