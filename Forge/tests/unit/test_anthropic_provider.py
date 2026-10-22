"""
Unit tests for AnthropicProvider (API integration, backoff retries, streaming, tool-calling structured outputs).
"""

from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest
from pydantic import BaseModel, Field

from app.providers.anthropic import AnthropicProvider
from app.providers.base import ProviderCapabilities, ProviderHealthStatus, ProviderResponse


class SamplePlan(BaseModel):
    plan_name: str = Field(..., description="Name of plan")
    stages: list[str] = Field(default_factory=list)
    budget_limit: float = 10.0


@pytest.mark.asyncio
async def test_anthropic_provider_init_and_capabilities():
    provider = AnthropicProvider(model_name="claude-3-5-sonnet-20241022", api_key="sk-ant-test-key")
    assert provider.model_name == "claude-3-5-sonnet-20241022"
    assert provider.api_key == "sk-ant-test-key"

    caps = provider.capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.provider_name == "AnthropicProvider"
    assert "claude-3-5-sonnet-20241022" in caps.supported_models
    assert caps.supports_streaming is True
    assert caps.supports_structured_output is True


def test_anthropic_provider_estimate_usage():
    provider = AnthropicProvider(model_name="claude-3-5-sonnet-20241022")
    usage = provider.estimate_usage("Test Anthropic prompt", "Anthropic response content")
    assert usage.prompt_tokens > 0
    assert usage.completion_tokens > 0
    assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
    assert usage.estimated_cost_usd > 0.0


@pytest.mark.asyncio
async def test_anthropic_provider_health_unconfigured():
    provider = AnthropicProvider(api_key=None)
    provider.api_key = None
    health = await provider.health()
    assert isinstance(health, ProviderHealthStatus)
    assert health.healthy is False
    assert "not configured" in health.message


@pytest.mark.asyncio
async def test_anthropic_provider_health_success():
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock())
    provider = AnthropicProvider(api_key="sk-ant-valid-key", client=mock_client)

    health = await provider.health()
    assert health.healthy is True
    assert "operational" in health.message
    assert health.latency_ms is not None


@pytest.mark.asyncio
async def test_anthropic_provider_generate_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.stop_reason = "end_turn"

    content_block = MagicMock()
    content_block.text = "Synthesized Claude architecture plan."
    mock_response.content = [content_block]

    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 30
    mock_response.usage.output_tokens = 60

    mock_client.messages.create = AsyncMock(return_value=mock_response)
    provider = AnthropicProvider(
        model_name="claude-3-5-sonnet-20241022",
        api_key="sk-ant-test",
        client=mock_client,
    )

    response = await provider.generate(
        prompt="Design high throughput pipeline",
        system_prompt="You are a Principal Engineer",
        temperature=0.2,
    )

    assert isinstance(response, ProviderResponse)
    assert response.content == "Synthesized Claude architecture plan."
    assert response.model == "claude-3-5-sonnet-20241022"
    assert response.usage.prompt_tokens == 30
    assert response.usage.completion_tokens == 60
    assert response.usage.total_tokens == 90
    assert response.usage.estimated_cost_usd > 0.0


@pytest.mark.asyncio
async def test_anthropic_provider_retry_on_rate_limit():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.stop_reason = "end_turn"
    content_block = MagicMock()
    content_block.text = "Success after Claude rate limit backoff!"
    mock_response.content = [content_block]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 15
    mock_response.usage.output_tokens = 25

    rate_limit_err = anthropic.RateLimitError(
        message="Anthropic rate limit",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    mock_client.messages.create = AsyncMock(side_effect=[rate_limit_err, mock_response])

    provider = AnthropicProvider(
        model_name="claude-3-5-sonnet-20241022",
        api_key="sk-ant-test",
        initial_backoff=0.01,
        client=mock_client,
    )

    response = await provider.generate("Test prompt")
    assert response.content == "Success after Claude rate limit backoff!"
    assert mock_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_anthropic_provider_structured_output_tool_call():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.model = "claude-3-5-sonnet-20241022"

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "output_formatter"
    tool_block.input = {
        "plan_name": "Autonomous Architecture",
        "stages": ["Planning", "Coding", "Testing"],
        "budget_limit": 15.0,
    }
    mock_response.content = [tool_block]

    mock_client.messages.create = AsyncMock(return_value=mock_response)
    provider = AnthropicProvider(
        model_name="claude-3-5-sonnet-20241022",
        api_key="sk-ant-test",
        client=mock_client,
    )

    result = await provider.structured_output("Synthesize plan", response_model=SamplePlan)
    assert isinstance(result, SamplePlan)
    assert result.plan_name == "Autonomous Architecture"
    assert len(result.stages) == 3
    assert result.budget_limit == 15.0
