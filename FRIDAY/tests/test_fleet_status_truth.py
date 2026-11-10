"""TASK-API-002: truthful fleet-status answering.

"Friday, how's the fleet?" is a factual question about live infrastructure.
Two things must hold:

1. the question must ROUTE to a tool-execution capability (never
   DIRECT_REASONING, where the LLM could only guess);
2. the tool must report what the probes actually said — per-agent statuses
   from a real FleetClient, honest UNREACHABLE on failure, never an invented
   "all online".
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytestmark = [pytest.mark.unit]

from friday.routing.capability_router import (
    CapabilityRouter,
    ExecutionCapabilityType,
)
from friday.tools.builtin.fleet_status import FleetStatusTool


@dataclass
class _FakeStatus:
    id: str
    name: str
    role: str
    status: str
    latency_ms: int
    endpoint: str
    details: str = ""


class _FakeFleetClient:
    def __init__(self, statuses):
        self._statuses = statuses
        self.calls = 0

    async def get_all_statuses(self, force_refresh: bool = False):
        self.calls += 1
        assert force_refresh is True, "fleet answers must be fresh, not cached"
        return list(self._statuses)


class _BrokenFleetClient:
    async def get_all_statuses(self, force_refresh: bool = False):
        raise ConnectionError("fleet probe network down")


_ALL_UP = [
    _FakeStatus("inference", "Inference", "Reasoning", "ONLINE", 40, "http://x/health"),
    _FakeStatus("memora", "Memora", "Memory", "ONLINE", 35, "http://x/health"),
    _FakeStatus("stratex", "Stratex", "Trading", "REACHABLE", 80, "http://x/health"),
    _FakeStatus("intelx", "IntelX", "Research", "ONLINE", 60, "http://x/health"),
    _FakeStatus("futuris", "Futuris", "Forecasting", "ONLINE", 55, "http://x/health"),
    _FakeStatus("cortex", "Cortex", "Decisions", "ONLINE", 70, "http://x/health"),
    _FakeStatus("forge", "Forge", "Code", "REACHABLE", 90, "http://x/health"),
    _FakeStatus("sentinel", "Sentinel", "Security", "ONLINE", 45, "http://x/health"),
    _FakeStatus("vyralx", "VyralX", "Content", "ONLINE", 50, "http://x/health"),
]

_ONE_DOWN = [
    *(_ALL_UP[:4]),
    _FakeStatus("futuris", "Futuris", "Forecasting", "UNREACHABLE", 12000,
                "http://x/health", "Futuris health probe could not complete (ConnectError)."),
    *(_ALL_UP[5:]),
]


class TestFleetQuestionsRouteToTools:
    """Fleet-status questions must reach tool execution, never guessing."""

    @pytest.mark.parametrize(
        "question",
        [
            "how's the fleet",
            "friday, how is the fleet doing",
            "are the agents online",
            "check the agents status",
            "what's the universe status",
            "is anyone down in the mesh",
            "status of the agents please",
        ],
    )
    def test_fleet_questions_route_to_tool_execution(self, question: str) -> None:
        decision = CapabilityRouter().route_request(question)
        assert decision.selected_capability != ExecutionCapabilityType.DIRECT_REASONING, (
            f"{question!r} routed to DIRECT_REASONING — the LLM could only guess"
        )
        fleet_candidate = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["get_fleet_status"]
        ]
        assert fleet_candidate, (
            f"{question!r} produced no get_fleet_status candidate"
        )

    def test_plain_chat_stays_conversational(self) -> None:
        """The fleet keywords must not swallow ordinary conversation."""
        decision = CapabilityRouter().route_request("hello, what can you do for me")
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING

    def test_non_fleet_research_stays_unrouted_to_fleet(self) -> None:
        """A research question mentioning neither fleet nor agents must not hit the fleet tool."""
        decision = CapabilityRouter().route_request("research the crypto market for me")
        fleet = [
            c for c in decision.candidate_evaluations
            if getattr(c, "required_tools", None) == ["get_fleet_status"]
        ]
        assert not fleet


class TestFleetStatusToolReportsTruth:
    """The tool reports exactly what the probes said."""

    def test_all_up_summary(self) -> None:
        client = _FakeFleetClient(_ALL_UP)
        result = FleetStatusTool(fleet_client=client).execute(detail="summary")
        assert not result.is_error
        assert "9/9 specialist agents up" in result.content
        assert "task-level verification" in result.content  # scope stated
        assert result.metadata["fleet"]["specialists_up"] == 9
        assert result.metadata["fleet"]["scope"] == "peer_endpoint_reachability_only"
        assert client.calls == 1

    def test_one_down_is_reported_not_hidden(self) -> None:
        result = FleetStatusTool(fleet_client=_FakeFleetClient(_ONE_DOWN)).execute()
        assert "8/9" in result.content
        assert "Futuris (UNREACHABLE" in result.content
        assert "ConnectError" in result.content  # the failure reason survives

    def test_full_detail_lists_every_agent(self) -> None:
        result = FleetStatusTool(fleet_client=_FakeFleetClient(_ALL_UP)).execute(detail="full")
        for name in ("Inference", "Memora", "Stratex", "IntelX", "Futuris",
                     "Cortex", "Forge", "Sentinel", "VyralX"):
            assert name in result.content, f"{name} missing from full fleet report"

    def test_probe_failure_is_honest_error(self) -> None:
        result = FleetStatusTool(fleet_client=_BrokenFleetClient()).execute()
        assert result.is_error
        assert "could not probe the fleet" in result.content
        assert "ConnectionError" in result.content
        # Crucially: no invented statuses in a failed probe.
        assert "ONLINE" not in result.content

    def test_friday_counts_itself_in_the_picture(self) -> None:
        result = FleetStatusTool(fleet_client=_FakeFleetClient(_ALL_UP)).execute()
        assert "FRIDAY" in result.content


class TestFleetFastPath:
    """The deterministic fast path answers fleet questions with a real probe."""

    def test_hows_the_fleet_gets_a_probe_answer(self) -> None:
        from unittest.mock import patch
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        # The patch must stay active for the whole turn: the fast path
        # instantiates FleetStatusTool lazily inside process_message.
        with patch.object(FleetStatusTool, "_client", return_value=_FakeFleetClient(_ALL_UP)):
            agent = FridayAgent(settings=Settings(env="testing"))
            response = agent.process_message("friday, how's the fleet?")
        assert "9/9 specialist agents up" in response.content
        assert response.metadata.get("fast_path") is True
        assert response.metadata.get("fleet_status") is True
        assert response.metadata["fleet"]["specialists_up"] == 9

    def test_fleet_failure_is_reported_not_smoothed(self) -> None:
        from unittest.mock import patch
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        with patch.object(FleetStatusTool, "_client", return_value=_BrokenFleetClient()):
            agent = FridayAgent(settings=Settings(env="testing"))
            response = agent.process_message("are the agents online?")
        assert "could not probe the fleet" in response.content
        assert response.metadata.get("probe_success") is False
