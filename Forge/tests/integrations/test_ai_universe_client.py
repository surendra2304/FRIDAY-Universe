"""
Unit tests for AI Universe REST Client and Peer Reasoning Integration.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.ai_universe_client import (
    AIUniverseClient,
    AIUniverseResponse,
    get_ai_universe_client,
)


@pytest.mark.asyncio
async def test_ai_universe_ask_endpoint():
    """Validates ask() sends POST to /v1/friday/ask with X-FRIDAY-API-Key header."""
    client = AIUniverseClient(
        base_url="http://localhost:8000",
        api_key="test_universe_key_123",
        timeout=10.0,
    )

    mock_response_data = {
        "answer": "Use a modular monolith with decoupled service boundaries.",
        "confidence": 0.92,
        "unresolved_disagreements": [],
        "key_evidence": ["Reduced network latency", "Simpler transaction management"],
        "run_id": "universe_run_abc123",
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=mock_response_data,
        request=httpx.Request("POST", "http://localhost:8000/v1/friday/ask"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await client.ask(
            question="Should I use a microservice or monolith for this module?",
            mode="auto",
        )

        assert isinstance(result, AIUniverseResponse)
        assert result.answer == "Use a modular monolith with decoupled service boundaries."
        assert result.confidence == 0.92
        assert result.run_id == "universe_run_abc123"
        assert len(result.key_evidence) == 2

        # Verify POST call details
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        call_json = mock_post.call_args[1]["json"]
        call_headers = mock_post.call_args[1]["headers"]

        assert call_url == "http://localhost:8000/v1/friday/ask"
        assert call_json["question"] == "Should I use a microservice or monolith for this module?"
        assert call_json["mode"] == "auto"
        assert call_headers["X-FRIDAY-API-Key"] == "test_universe_key_123"


@pytest.mark.asyncio
async def test_ai_universe_debate_endpoint():
    """Validates debate() sends POST to /v1/friday/debate with max_agents and correct headers."""
    client = AIUniverseClient(
        base_url="http://localhost:8000",
        api_key="debate_secret_key_456",
    )

    mock_response_data = {
        "answer": "Root cause is race condition on shared connection pool.",
        "confidence": 0.88,
        "unresolved_disagreements": ["Thread isolation vs mutex lock overhead"],
        "key_evidence": ["Deadlock traceback in worker thread 2"],
        "run_id": "universe_debate_run_789",
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=mock_response_data,
        request=httpx.Request("POST", "http://localhost:8000/v1/friday/debate"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await client.debate(
            question="What is the root cause of this concurrency bug?",
            max_agents=5,
        )

        assert isinstance(result, AIUniverseResponse)
        assert "Root cause is race condition" in result.answer
        assert result.confidence == 0.88
        assert result.run_id == "universe_debate_run_789"
        assert len(result.unresolved_disagreements) == 1

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        call_json = mock_post.call_args[1]["json"]
        call_headers = mock_post.call_args[1]["headers"]

        assert call_url == "http://localhost:8000/v1/friday/debate"
        assert call_json["max_agents"] == 5
        assert call_headers["X-FRIDAY-API-Key"] == "debate_secret_key_456"


@pytest.mark.asyncio
async def test_trust_but_verify_high_confidence():
    """Validates consult_with_verification returns AIUniverseResponse when confidence >= 0.70."""
    client = AIUniverseClient(api_key="test_key")

    mock_data = {
        "answer": "Optimal architecture verified.",
        "confidence": 0.85,
        "unresolved_disagreements": [],
        "key_evidence": ["Strong peer consensus"],
        "run_id": "run_high_conf",
    }

    with patch.object(client, "debate", new_callable=AsyncMock) as mock_debate:
        mock_debate.return_value = AIUniverseResponse(**mock_data)

        verified = await client.consult_with_verification(
            question="High confidence architectural decision",
            min_confidence=0.70,
            use_debate=True,
        )

        assert verified is not None
        assert verified.confidence == 0.85
        assert verified.run_id == "run_high_conf"
        assert verified.answer == "Optimal architecture verified."


@pytest.mark.asyncio
async def test_trust_but_verify_low_confidence_fallback():
    """Validates consult_with_verification returns None when confidence < 0.70 (triggering internal fallback)."""
    client = AIUniverseClient(api_key="test_key")

    mock_data = {
        "answer": "Inconclusive debate between microservice and monolith.",
        "confidence": 0.54,
        "unresolved_disagreements": ["High dispute on operational complexity"],
        "key_evidence": [],
        "run_id": "run_low_conf",
    }

    with patch.object(client, "debate", new_callable=AsyncMock) as mock_debate:
        mock_debate.return_value = AIUniverseResponse(**mock_data)

        verified = await client.consult_with_verification(
            question="Controversial architectural decision",
            min_confidence=0.70,
            use_debate=True,
        )

        # Confidence 0.54 < 0.70 -> returns None
        assert verified is None


@pytest.mark.asyncio
async def test_trust_but_verify_network_error_graceful_fallback():
    """Validates consult_with_verification catches network/HTTP errors and gracefully returns None."""
    client = AIUniverseClient(api_key="test_key")

    with patch.object(
        client, "debate", side_effect=httpx.ConnectError("Connection refused to AI Universe")
    ):
        verified = await client.consult_with_verification(
            question="Will handle network error gracefully",
            min_confidence=0.70,
            use_debate=True,
        )

        assert verified is None


def test_get_ai_universe_client_factory():
    """Validates factory helper creates configured AIUniverseClient."""
    client = get_ai_universe_client()
    assert isinstance(client, AIUniverseClient)
    assert client.base_url.startswith("http")
