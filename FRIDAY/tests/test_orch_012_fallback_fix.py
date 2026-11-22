"""Regression tests for TASK-ORCH-012: generic fallback outranking specific tools.

ORCH-010 finding F1 (docs/collaboration/TASK-ORCH-010-ROUTING-REPROBE.md):
the tool-less generic fallback candidate scored -9.9 and beat every specific
tool candidate, so any utterance matching a specific table AND a generic verb
("read this page", "write me a script", "create a video about") routed to a
TOOL_EXECUTION with no tool. Proven live by ORCH-010 probe P7: "read this page
https://example.com" -> TOOL_EXECUTION score -9.9 instead of
web_fetch_summarize (106.0).

These tests pin the fix: the fallback is only offered when no candidate names
a concrete tool, so the specific tool wins; the fallback itself is preserved
for utterances with a generic verb and no specific table match.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit]

from friday.routing.capability_router import (
    CapabilityMetadata,
    CapabilityRouter,
    ExecutionCapabilityType,
    RoutingDecision,
)


def _chosen(decision: RoutingDecision) -> CapabilityMetadata:
    """The winning candidate: candidate_evaluations is score-sorted, [0] wins."""
    assert decision.candidate_evaluations, "router returned no candidates"
    return decision.candidate_evaluations[0]


class TestFallbackLosesToSpecificTools:
    """The three acceptance phrases must reach their named tool, not the fallback."""

    def test_read_this_page_routes_to_web_fetch_summarize(self) -> None:
        """ORCH-010 P7, the live misroute: fetch must win over the fallback."""
        router = CapabilityRouter()
        decision = router.route_request("read this page https://example.com")
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        chosen = _chosen(decision)
        assert chosen.required_tools == ["web_fetch_summarize"]
        assert chosen.compute_selection_score() == pytest.approx(106.0)

    def test_write_me_a_script_routes_to_forge_code_task(self) -> None:
        """ORCH-010 case 8: code task must win over the fallback."""
        router = CapabilityRouter()
        decision = router.route_request("write me a script to bulk-rename my photos")
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        chosen = _chosen(decision)
        assert chosen.required_tools == ["forge_code_task"]

    def test_create_a_video_about_routes_to_vyralx_project(self) -> None:
        """ORCH-010 case S2: video project must win over the fallback."""
        router = CapabilityRouter()
        decision = router.route_request("create a video about black holes")
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        chosen = _chosen(decision)
        assert chosen.required_tools == ["vyralx_project"]

    @pytest.mark.parametrize(
        ("text", "expected_tools"),
        [
            # ORCH-010 case S4: security findings must reach Sentinel.
            ("read the security findings", ["sentinel_security"]),
            # ORCH-010 case S3: fleet question must reach the fleet probe.
            ("list the agents", ["get_fleet_status"]),
            # ORCH-010 case 15: the passing fetch phrasing stays pinned.
            ("summarize this article https://example.com", ["web_fetch_summarize"]),
        ],
    )
    def test_other_f1_phrases_reach_their_tool(
        self, text: str, expected_tools: list[str]
    ) -> None:
        router = CapabilityRouter()
        decision = router.route_request(text)
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        assert _chosen(decision).required_tools == expected_tools

    def test_two_table_match_still_names_a_tool(self) -> None:
        """ORCH-010 case 33: two tables match, the winner must still name a tool.

        Which of the two specific tools wins is score arithmetic between two
        legitimate tools (the F3 disambiguator's job), so this pins only that
        the tool-less fallback does not win.
        """
        router = CapabilityRouter()
        decision = router.route_request("write a script to bulk-rename my photos")
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        assert _chosen(decision).required_tools, "fallback won: no tool named"


class TestFallbackPreservedWhenNoSpecificToolMatched:
    """The fix removes the fallback only where a specific tool was named."""

    def test_generic_verb_without_table_still_uses_fallback(self) -> None:
        """'click the button': no table names a tool, the fallback still wins."""
        router = CapabilityRouter()
        decision = router.route_request("click the button")
        assert decision.selected_capability == ExecutionCapabilityType.TOOL_EXECUTION
        chosen = _chosen(decision)
        assert chosen.required_tools is None
        assert chosen.compute_selection_score() == pytest.approx(-9.9)

    def test_list_files_without_table_still_direct_reasoning(self) -> None:
        """ORCH-010 case 25, unchanged: DIRECT beats the fallback when both run."""
        router = CapabilityRouter()
        decision = router.route_request("list the files in the folder")
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING

    def test_conversational_question_unchanged(self) -> None:
        router = CapabilityRouter()
        decision = router.route_request("Hello FRIDAY, how are you today?")
        assert decision.selected_capability == ExecutionCapabilityType.DIRECT_REASONING
