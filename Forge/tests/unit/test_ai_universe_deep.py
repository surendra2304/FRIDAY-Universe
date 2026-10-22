"""
Unit tests for Deep AI Universe Multi-Agent Integration and Debate Code Review.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ai_universe_client import AIUniverseResponse
from app.integrations.ai_universe_deep import (
    DeepAIUniverseIntegration,
    SpecializedAgentRole,
)


@pytest.mark.asyncio
async def test_route_ask_and_usage_tracking():
    mock_client = MagicMock()
    mock_client.ask = AsyncMock(
        return_value=AIUniverseResponse(
            answer="class Portfolio:\n    pass",
            confidence=0.92,
            unresolved_disagreements=[],
            key_evidence=["Clean architecture"],
            run_id="run_arch_01",
        )
    )

    integration = DeepAIUniverseIntegration(client=mock_client)
    res = await integration.route_ask(
        task_id="task_deep_01",
        question="Design portfolio layout",
        role=SpecializedAgentRole.ARCHITECT,
    )
    assert res is not None
    assert res.confidence == 0.92

    usage = integration.get_usage("task_deep_01")
    assert usage.total_calls == 1
    assert usage.total_estimated_tokens > 0
    assert "AI-Universe usage: 1 calls" in usage.summary


@pytest.mark.asyncio
async def test_debate_code_review_high_confidence_autofix():
    mock_client = MagicMock()
    mock_client.debate = AsyncMock(
        return_value=AIUniverseResponse(
            answer="```python\ndef refined_code():\n    return 'safe'\n```",
            confidence=0.88,  # > 0.80 -> auto-apply
            unresolved_disagreements=[],
            key_evidence=["Fixed potential SQL injection", "Added type hints"],
            run_id="debate_run_88",
        )
    )

    integration = DeepAIUniverseIntegration(client=mock_client)
    review = await integration.debate_code_review(
        task_id="task_deep_02",
        code="def original(): pass",
        filename="main.py",
        goal="Create secure endpoint",
    )
    assert review.applied_auto_fix is True
    assert review.refined_code == "def refined_code():\n    return 'safe'"
    assert review.confidence == 0.88


@pytest.mark.asyncio
async def test_debate_code_review_moderate_confidence_logs_suggestions():
    mock_client = MagicMock()
    mock_client.debate = AsyncMock(
        return_value=AIUniverseResponse(
            answer="Consider caching user requests",
            confidence=0.65,  # 0.50 - 0.80 -> log suggestions
            unresolved_disagreements=[],
            key_evidence=["Performance optimization opportunity"],
            run_id="debate_run_65",
        )
    )

    integration = DeepAIUniverseIntegration(client=mock_client)
    review = await integration.debate_code_review(
        task_id="task_deep_03",
        code="def process(): pass",
        filename="service.py",
    )
    assert review.applied_auto_fix is False
    assert review.refined_code is None
    assert len(review.suggestions) == 1
