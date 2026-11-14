"""TASK-REL-040: clock questions must be answered by the real clock.

Live defect (production, 2026-11-15 04:41 IST): "what time is it in
Tokyo?" routed to LOCAL_COMPUTATION and answered in one no-tool LLM
iteration — "Boss, I don't have a way to look up the exact current time
in Tokyo right now." — even though the registered ``get_time_date``
tool reads the real server clock in any IANA zone. The route the
router calls "instant local deterministic system time/info" had no
deterministic executor; the model's non-answers were then recorded as
dialogue and recalled as context for the next ask.

These tests pin the fix: a deterministic fast path wires get_time_date
into the route for turns that are SOLELY a clock/date ask, answers from
the real clock, and claims nothing else (the REL-006A full-turn
discipline). The mock LLM below always answers with the production
non-answer text, so on clean main every claimed-turn test fails with
that exact string; with the fix the LLM is never reached.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.auth import AutoApproveAuthorizer
from friday.core.config import Settings
from friday.core.types import Message, Role
from friday.llm.mock_provider import MockLLMProvider

NON_ANSWER = (
    "Boss, I don't have a way to look up the exact current time right now. "
    "You can check a world-clock app instead."
)
MARKER = "MODEL-MARKER-REPLY"


def _agent() -> FridayAgent:
    def responder(messages, tools):
        # The production model's behaviour for a clock ask: a one-shot
        # non-answer (or, for unrelated turns, a plain marker).
        last_user = next(
            (m.content for m in reversed(messages) if m.role == Role.USER), ""
        )
        if "time" in last_user.lower() or "date" in last_user.lower():
            return Message(role=Role.ASSISTANT, content=NON_ANSWER)
        return Message(role=Role.ASSISTANT, content=MARKER)

    return FridayAgent(
        settings=Settings(env="testing", embedding_provider="none"),
        llm_provider=MockLLMProvider(custom_responder=responder),
        authorizer=AutoApproveAuthorizer.create_for_testing(),
    )


def _minutes_of_day(reply: str) -> int:
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", reply)
    assert m, f"no HH:MM AM/PM time in reply: {reply!r}"
    hour = int(m.group(1)) % 12
    if m.group(3) == "PM":
        hour += 12
    return hour * 60 + int(m.group(2))


def _assert_time_matches(reply: str, zone: str, before: datetime, after: datetime) -> None:
    got = _minutes_of_day(reply)
    expected = {
        before.astimezone(ZoneInfo(zone)).hour * 60 + before.astimezone(ZoneInfo(zone)).minute,
        after.astimezone(ZoneInfo(zone)).hour * 60 + after.astimezone(ZoneInfo(zone)).minute,
    }
    assert any(abs(got - exp) <= 1 for exp in expected), (
        f"reply time {got} not within a minute of {zone} time {expected}: {reply!r}"
    )


class TestClockFastPath:
    """Solely-clock turns are served by the real clock, never the model."""

    @pytest.mark.parametrize(
        "phrase,zone",
        [
            ("what time is it in Tokyo?", "Asia/Tokyo"),
            ("What time is it in London?", "Europe/London"),
            ("what time is it in New York right now?", "America/New_York"),
            ("tell me the time in Paris", "Europe/Paris"),
        ],
    )
    def test_time_in_named_place(self, phrase: str, zone: str) -> None:
        agent = _agent()
        before = datetime.now(ZoneInfo("UTC"))
        response = agent.process_message(phrase)
        after = datetime.now(ZoneInfo("UTC"))
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("time_query") is True
        assert response.metadata.get("timezone") == zone
        assert NON_ANSWER not in response.content
        _assert_time_matches(response.content, zone, before, after)
        # The deterministic path never pays for a model call.
        assert agent.llm.call_history == []

    def test_time_here_is_owner_clock(self) -> None:
        agent = _agent()
        before = datetime.now(ZoneInfo("UTC"))
        response = agent.process_message("what time is it here?")
        after = datetime.now(ZoneInfo("UTC"))
        assert response.metadata.get("time_query") is True
        assert response.metadata.get("timezone") == "IST"
        _assert_time_matches(response.content, "Asia/Kolkata", before, after)

    @pytest.mark.parametrize("phrase", ["what time is it?", "what's the time?"])
    def test_bare_time_ask_stays_on_existing_handler(self, phrase: str) -> None:
        """Guard: bare local asks were already served correctly by the
        deterministic action path's _TIME_PATTERN handler (real IST via
        owner_now_str) — REL-040 must not disturb that working lane; the
        reply is a real IST time either way, never the non-answer."""
        agent = _agent()
        before = datetime.now(ZoneInfo("UTC"))
        response = agent.process_message(phrase)
        after = datetime.now(ZoneInfo("UTC"))
        assert NON_ANSWER not in response.content
        _assert_time_matches(response.content, "Asia/Kolkata", before, after)

    def test_todays_date(self) -> None:
        agent = _agent()
        before = datetime.now(ZoneInfo("Asia/Kolkata"))
        response = agent.process_message("what's today's date?")
        after = datetime.now(ZoneInfo("Asia/Kolkata"))
        assert response.metadata.get("time_query") is True
        assert response.metadata.get("time_query_kind") == "date"
        valid = {
            d.strftime("%d %B %Y") for d in (before, after)
        } | {d.strftime("%A") for d in (before, after)}
        assert any(v in response.content for v in valid), response.content

    def test_date_in_named_place(self) -> None:
        agent = _agent()
        before = datetime.now(ZoneInfo("Asia/Tokyo"))
        response = agent.process_message("what is today's date in Tokyo?")
        after = datetime.now(ZoneInfo("Asia/Tokyo"))
        assert response.metadata.get("time_query") is True
        assert response.metadata.get("timezone") == "Asia/Tokyo"
        valid = {d.strftime("%d %B %Y") for d in (before, after)}
        assert any(v in response.content for v in valid), response.content

    def test_real_answer_is_what_gets_recorded(self) -> None:
        """The feedback loop stops at the source: the turn recorded into
        conversation memory is the real clock answer, so a later recall
        can never feed a 'not able to look up' non-answer back in."""
        agent = _agent()
        response = agent.process_message("what time is it in Tokyo?")
        recorded = [m.content for m in agent.memory.get_messages() if m.role == Role.ASSISTANT]
        assert recorded and recorded[-1] == response.content
        assert NON_ANSWER not in recorded[-1]
        _minutes_of_day(recorded[-1])


class TestClockFastPathScope:
    """Everything that is not SOLELY a clock ask is left exactly as it was."""

    @pytest.mark.parametrize(
        "phrase",
        [
            # REL-006A compound: the joke belongs to the cognitive loop.
            "tell me a joke and what time is it in Tokyo",
            # Not a current-time ask at all.
            "what time is the meeting tomorrow?",
            "what time does the market open?",
            # A comparison needs reasoning, not one clock read.
            "what is the time difference between London and Tokyo?",
            "what time is it in Tokyo and London?",
            # An unresolvable place must never be answered with the
            # owner's clock dressed up as that place's time.
            "what time is it in Atlantis?",
            # Other LOCAL_COMPUTATION work keeps its existing route.
            "calculate 2 + 2",
        ],
    )
    def test_not_claimed(self, phrase: str) -> None:
        agent = _agent()
        response = agent.process_message(phrase)
        assert response.metadata.get("time_query") is not True
        assert "The current time in Atlantis" not in response.content

    def test_matcher_shapes(self) -> None:
        from friday.agent.mixins.fast_paths import FastPathMixin

        m = FastPathMixin._match_clock_question
        assert m("what time is it in tokyo") == ("time", "tokyo")
        assert m("what time is it here") == ("time", "here")
        assert m("what time is it") == ("time", None)
        assert m("please what is the current time in new york") == ("time", "new york")
        assert m("what's today's date") == ("date", None)
        assert m("what time is it in tokyo and london") == ("time", "tokyo and london")  # kept whole; the path declines two-place asks
        assert m("tell me a joke and what time is it in tokyo") is None
        assert m("what time is the meeting") is None
        assert m("calculate 2 + 2") is None
