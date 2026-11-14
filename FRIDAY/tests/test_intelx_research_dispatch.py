"""TASK-INT-002: IntelX research briefs through FRIDAY chat.

"Friday, research X and give me the highlights" must dispatch to IntelX and
return its real evidence-based brief. The live 2026-11-10 incident proved
research requests were nobody's job (misrouted to VISION_MODEL, then died at
the action limit). These tests pin the corrected behavior:

1. research questions route to the intelx_research tool candidate (never
   VISION_MODEL, never DIRECT_REASONING);
2. the tool reports IntelX's actual response — including "no conclusive
   evidence", which is a finding, not a failure;
3. dispatch failures are honest errors, never fabricated summaries.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.routing.capability_router import (
    CapabilityRouter,
    ExecutionCapabilityType,
)
from friday.tools.builtin.intelx_research import IntelXResearchTool


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None, error: str | None = None):
        self.status = status
        self.result = result or {}
        self.error = error
        self.task_id = "task_test123"
        self.execution_time_ms = 1234


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result
        self.envelopes = []

    async def dispatch_task(self, envelope):
        self.envelopes.append(envelope)
        return self._result


class _BrokenFleetClient:
    async def dispatch_task(self, envelope):
        raise ConnectionError("intelx unreachable")


class TestResearchQuestionsRouteToIntelX:
    """Research requests must produce an intelx_research candidate."""

    @pytest.mark.parametrize(
        "question",
        [
            "friday, research the crypto market and give me the highlights",
            "do some research on quantum computing",
            "look into the latest AI chip market",
            "investigate why battery stocks moved today",
            "brief me on the Fed decision",
            "find out about the new iPhone release",
        ],
    )
    def test_research_questions_route_to_intelx(self, question: str) -> None:
        decision = CapabilityRouter().route_request(question)
        assert decision.selected_capability != ExecutionCapabilityType.VISION_MODEL, (
            f"{question!r} misrouted to VISION_MODEL (the live 2026-11-10 incident)"
        )
        assert decision.selected_capability != ExecutionCapabilityType.DIRECT_REASONING, (
            f"{question!r} routed to DIRECT_REASONING — research needs the fleet"
        )
        research = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["intelx_research"]
        ]
        assert research, f"{question!r} produced no intelx_research candidate"

    def test_plain_chat_is_not_research(self) -> None:
        decision = CapabilityRouter().route_request("hello, what can you do for me")
        research = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["intelx_research"]
        ]
        assert not research
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING

    def test_screen_request_is_not_research(self) -> None:
        """A genuine screen request must keep its vision routing."""
        decision = CapabilityRouter().route_request("take a screenshot of my screen")
        assert decision.selected_capability == ExecutionCapabilityType.VISION_MODEL


class TestIntelXResearchToolReportsTruth:
    """The tool returns IntelX's actual response."""

    def test_successful_brief_with_citations(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {
            "query": "crypto market",
            "citations_count": 3,
            "sources": [{"name": "Reuters"}],
            "spoken_summary": "Bitcoin is range-bound.",
            "text_response": "### Key Findings\n- BTC range-bound",
        }))
        result = IntelXResearchTool(fleet_client=client).execute(query="crypto market")
        assert not result.is_error
        assert "crypto market" in result.content
        assert "Bitcoin is range-bound." in result.content
        assert "3 citation(s)" in result.content
        assert "Reuters" in result.content
        # The envelope went to intelx with the research capability.
        env = client.envelopes[0]
        assert env.target_agent == "intelx"
        assert env.payload["topic"] == "crypto market"

    def test_no_evidence_is_a_finding_not_a_failure(self) -> None:
        result = IntelXResearchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", {
            "query": "obscure topic",
            "citations_count": 0,
            "spoken_summary": "No conclusive empirical evidence was found.",
            "text_response": "### Key Findings with Citations\n",
        }))).execute(query="obscure topic")
        assert not result.is_error
        assert "No conclusive empirical evidence" in result.content

    def test_empty_response_is_reported_not_invented(self) -> None:
        result = IntelXResearchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", {}))).execute(query="x")
        assert not result.is_error
        assert "empty brief" in result.content
        assert "won't invent" in result.content

    def test_intelx_failure_is_honest_error(self) -> None:
        result = IntelXResearchTool(fleet_client=_FakeFleetClient(_FakeResult("FAILED", error="HTTP 503"))).execute(query="x")
        assert result.is_error
        assert "HTTP 503" in result.content
        assert "no highlights were fabricated" in result.content

    def test_dispatch_crash_is_honest_error(self) -> None:
        result = IntelXResearchTool(fleet_client=_BrokenFleetClient()).execute(query="x")
        assert result.is_error
        assert "could not reach IntelX" in result.content
        assert "ConnectionError" in result.content

    def test_empty_query_is_rejected(self) -> None:
        result = IntelXResearchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", {}))).execute(query="  ")
        assert result.is_error
        assert "research question" in result.content


class TestResearchFastPath:
    """Explicit research requests dispatch straight to IntelX."""

    def test_research_command_dispatches(self) -> None:
        from unittest.mock import patch
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        with patch.object(
            IntelXResearchTool, "_client",
            return_value=_FakeFleetClient(_FakeResult("SUCCESS", {
                "query": "the crypto market",
                "citations_count": 2,
                "sources": [{"name": "Reuters"}],
                "spoken_summary": "Range-bound week.",
                "text_response": "### Key Findings\n- chop",
            })),
        ):
            agent = FridayAgent(settings=Settings(env="testing"))
            response = agent.process_message("friday, research the crypto market and give me the highlights")
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("research_dispatch") is True
        assert "Range-bound week." in response.content
        assert "2 citation(s)" in response.content

    def test_headlines_with_sources_dispatches(self) -> None:
        # TASK-REL-007: the exact console round-1 phrasing. Before the fix it
        # matched no research action shape, fell into the LLM tool loop and
        # surfaced as a bare "502"; a headlines request that asks for sources
        # is a research action and must reach IntelX.
        from unittest.mock import patch
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        with patch.object(
            IntelXResearchTool, "_client",
            return_value=_FakeFleetClient(_FakeResult("SUCCESS", {
                "query": "today's top three ai news headlines",
                "citations_count": 3,
                "sources": [{"name": "Reuters"}, {"name": "Bloomberg"}, {"name": "TechCrunch"}],
                "spoken_summary": "Three sourced headlines.",
                "text_response": "### Key Findings\n- headline one",
            })),
        ):
            agent = FridayAgent(settings=Settings(env="testing"))
            response = agent.process_message(
                "What are today's top three AI news headlines? Include sources."
            )
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("research_dispatch") is True
        assert "Three sourced headlines." in response.content

    def test_incidental_research_word_takes_the_normal_path(self) -> None:
        """A sentence that merely contains 'research' must NOT fast-path."""
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        agent = FridayAgent(settings=Settings(env="testing"))
        # "What is a research assistant's job?" — no leading action verb, no
        # highlights request: the fast path must decline.
        low = "what is a research assistant's job?"
        from friday.routing.capability_router import CapabilityRouter
        assert CapabilityRouter._matches(low, CapabilityRouter.RESEARCH_KEYWORDS) is True
        # but the action-shape gate rejects it (no leading verb / highlights ask)
        import re as _re
        action_shaped = bool(_re.match(
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:research|investigate|look into|dig into|find out about|brief me on|do some research)\b",
            low,
        ))
        assert action_shaped is False
