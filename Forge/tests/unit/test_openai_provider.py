"""
Unit tests for OpenAIProvider (API integration, backoff retries, streaming, structured outputs).
"""

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest
from pydantic import BaseModel, Field

from app.providers.base import ProviderCapabilities, ProviderHealthStatus, ProviderResponse
from app.providers.openai import OpenAIProvider


class SampleOutput(BaseModel):
    title: str = Field(..., description="Project title")
    tasks: list[str] = Field(default_factory=list)
    confidence: float = 0.95


@pytest.mark.asyncio
async def test_openai_provider_init_and_capabilities():
    provider = OpenAIProvider(model_name="gpt-4o", api_key="sk-test-openai-key")
    assert provider.model_name == "gpt-4o"
    assert provider.api_key == "sk-test-openai-key"

    caps = provider.capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.provider_name == "OpenAIProvider"
    assert "gpt-4o" in caps.supported_models
    assert caps.supports_streaming is True
    assert caps.supports_structured_output is True


def test_openai_provider_estimate_usage():
    provider = OpenAIProvider(model_name="gpt-4o")
    usage = provider.estimate_usage("Hello world prompt", "Output response")
    assert usage.prompt_tokens > 0
    assert usage.completion_tokens > 0
    assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
    assert usage.estimated_cost_usd > 0.0


@pytest.mark.asyncio
async def test_openai_provider_health_unconfigured():
    provider = OpenAIProvider(api_key=None)
    provider.api_key = None
    health = await provider.health()
    assert isinstance(health, ProviderHealthStatus)
    assert health.healthy is False
    assert "not configured" in health.message


@pytest.mark.asyncio
async def test_openai_provider_health_success():
    mock_client = MagicMock()
    mock_client.models.list = AsyncMock(return_value=[])
    provider = OpenAIProvider(api_key="sk-valid-key", client=mock_client)

    health = await provider.health()
    assert health.healthy is True
    assert "operational" in health.message
    assert health.latency_ms is not None


@pytest.mark.asyncio
async def test_openai_provider_generate_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_choice = MagicMock()
    mock_choice.message.content = "Synthesized OpenAI architecture output."
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 25
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 75

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    provider = OpenAIProvider(model_name="gpt-4o", api_key="sk-test", client=mock_client)

    response = await provider.generate(
        prompt="Design a distributed cache",
        system_prompt="You are an architect",
        temperature=0.3,
    )

    assert isinstance(response, ProviderResponse)
    assert response.content == "Synthesized OpenAI architecture output."
    assert response.model == "gpt-4o"
    assert response.usage.prompt_tokens == 25
    assert response.usage.completion_tokens == 50
    assert response.usage.total_tokens == 75
    assert response.usage.estimated_cost_usd > 0.0


@pytest.mark.asyncio
async def test_openai_provider_retry_on_rate_limit():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_choice = MagicMock()
    mock_choice.message.content = "Recovered after rate limit!"
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20

    rate_limit_err = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    # Fail on first attempt, succeed on second attempt
    mock_client.chat.completions.create = AsyncMock(side_effect=[rate_limit_err, mock_response])

    provider = OpenAIProvider(
        model_name="gpt-4o",
        api_key="sk-test",
        initial_backoff=0.01,
        client=mock_client,
    )

    response = await provider.generate("Test prompt")
    assert response.content == "Recovered after rate limit!"
    assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_openai_provider_stream():
    mock_client = MagicMock()

    class MockAsyncChunk:
        def __init__(self, text):
            delta = MagicMock()
            delta.content = text
            choice = MagicMock()
            choice.delta = delta
            self.choices = [choice]

    async def mock_stream_gen(*args, **kwargs):
        for token in ["Hello", " ", "World", "!"]:
            yield MockAsyncChunk(token)

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_stream_gen)
    provider = OpenAIProvider(model_name="gpt-4o", api_key="sk-test", client=mock_client)

    chunks = []
    async for chunk in provider.stream("Say hello"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello World!"


@pytest.mark.asyncio
async def test_openai_provider_structured_output_json_fallback():
    mock_client = MagicMock()
    # Mock beta parse raising error to test JSON extraction fallback
    mock_client.beta.chat.completions.parse = AsyncMock(
        side_effect=Exception("Beta parse not supported")
    )

    json_text = """```json
    {
        "title": "Autonomous Forge",
        "tasks": ["Decompose", "Synthesize", "Verify"],
        "confidence": 0.99
    }
    ```"""

    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_choice = MagicMock()
    mock_choice.message.content = json_text
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage = None

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    provider = OpenAIProvider(model_name="gpt-4o", api_key="sk-test", client=mock_client)

    result = await provider.structured_output(
        "Generate structured plan", response_model=SampleOutput
    )
    assert isinstance(result, SampleOutput)
    assert result.title == "Autonomous Forge"
    assert len(result.tasks) == 3
    assert result.confidence == 0.99
