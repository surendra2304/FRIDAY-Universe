"""Regression tests for TASK-ORCH-001: substring keyword misrouting.

The live incident (ACTIVITY_LOG 2026-11-10): the owner's request
``run a quick research check`` was routed to the external vision model because
``"ui" in "quick"`` — a substring containment hit on SCREEN_KEYWORDS. The same
class of false hit sent plain research questions to the most expensive path.

These tests pin whole-word/whole-phrase keyword matching: every existing
keyword still routes as before, and the substring false-hit class is gone.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit]

from friday.routing.capability_router import (
    CapabilityRouter,
    ExecutionCapabilityType,
)


class TestLiveIncidentRegressions:
    """The exact phrases that misrouted live must now route sanely."""

    def test_quick_research_check_is_not_a_vision_request(self) -> None:
        """The live incident: 'quick' contains the substring 'ui'."""
        router = CapabilityRouter()
        decision = router.route_request("run a quick research check")
        assert decision.selected_capability != ExecutionCapabilityType.VISION_MODEL
        assert decision.selected_capability != ExecutionCapabilityType.LOCAL_SCREEN_INSPECTION

    def test_quiet_question_is_not_a_vision_request(self) -> None:
        """'quiet' contains 'ui' too."""
        router = CapabilityRouter()
        decision = router.route_request("answer this quietly please")
        assert decision.selected_capability != ExecutionCapabilityType.VISION_MODEL

    def test_build_request_is_not_a_vision_request(self) -> None:
        """'build' contains 'ui'."""
        router = CapabilityRouter()
        decision = router.route_request("build a summary of today")
        assert decision.selected_capability != ExecutionCapabilityType.VISION_MODEL

    def test_historic_price_is_not_memory_recall(self) -> None:
        """'history' (memory) vs 'historic' (word): plain research is not recall."""
        router = CapabilityRouter()
        decision = router.route_request("explain historic market patterns")
        assert decision.selected_capability != ExecutionCapabilityType.MEMORY_RETRIEVAL

    def test_running_commentary_is_not_a_tool_execution(self) -> None:
        """'run' (tool) vs 'running' (word): commentary is not an execution request."""
        router = CapabilityRouter()
        decision = router.route_request("give me a running commentary on the news")
        assert decision.selected_capability != ExecutionCapabilityType.TOOL_EXECUTION


class TestExistingKeywordsStillRoute:
    """Word boundaries must not weaken any legitimate keyword hit."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # Screen perception keywords
            ("look at screen and tell me what you see", ExecutionCapabilityType.VISION_MODEL),
            ("take a screenshot", ExecutionCapabilityType.VISION_MODEL),
            ("what is on my screen right now", ExecutionCapabilityType.VISION_MODEL),
            ("click the button", ExecutionCapabilityType.TOOL_EXECUTION),
            # Memory retrieval keywords
            ("what do you remember about our last chat", ExecutionCapabilityType.MEMORY_RETRIEVAL),
            ("recall our previous conversation", ExecutionCapabilityType.MEMORY_RETRIEVAL),
            ("check the history of this file", ExecutionCapabilityType.MEMORY_RETRIEVAL),
            # Local computation keywords
            ("what time is it", ExecutionCapabilityType.LOCAL_COMPUTATION),
            ("calculate 2 + 2", ExecutionCapabilityType.LOCAL_COMPUTATION),
        ],
    )
    def test_keyword_phrases_route_as_before(
        self, text: str, expected: ExecutionCapabilityType
    ) -> None:
        router = CapabilityRouter()
        decision = router.route_request(text)
        assert decision.selected_capability == expected, (
            f"{text!r} routed to {decision.selected_capability}, expected {expected}"
        )

    def test_matches_is_word_scoped(self) -> None:
        """Unit-level: the shared matcher honours word boundaries.

        Case is normalised upstream by ``route_request`` (lowered input); the
        matcher itself is exact on the strings it is given.
        """
        assert CapabilityRouter._matches("a quick check", {"ui"}) is False
        assert CapabilityRouter._matches("fix the ui", {"ui"}) is True
        assert CapabilityRouter._matches("ui", {"ui"}) is True
        assert CapabilityRouter._matches("look at screen now", {"look at screen"}) is True
        assert CapabilityRouter._matches("look at screenplay", {"look at screen"}) is False
        assert CapabilityRouter._matches("past life regression", {"past"}) is True
        assert CapabilityRouter._matches("pasta recipe", {"past"}) is False
