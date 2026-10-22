"""
Unit tests for BaseModelProvider and DirectProvider.
"""

import pytest
from pydantic import BaseModel, Field

from app.providers.base import ProviderCapabilities, ProviderHealthStatus
from app.providers.direct import DirectProvider


class SamplePlan(BaseModel):
    plan_title: str = Field(..., description="Title of the plan")
    estimated_steps: int = Field(default=3, description="Number of steps")
    notes: list[str] = Field(default_factory=list)


@pytest.mark.asyncio
async def test_direct_provider_generate():
    provider = DirectProvider(model_name="test-model")
    response = await provider.generate("Build a simple hello-world CLI tool")

    assert response.content is not None
    assert len(response.content) > 0
    assert response.model == "test-model"
    assert response.finish_reason == "stop"
    assert response.usage.prompt_tokens > 0
    assert response.usage.total_tokens >= response.usage.prompt_tokens


@pytest.mark.asyncio
async def test_direct_provider_mock_generate():
    mock_text = "Custom synthesized response for agent execution."
    provider = DirectProvider(model_name="mock-model", mock_response=mock_text)
    response = await provider.generate("Any prompt")

    assert response.content == mock_text
    assert response.model == "mock-model"


@pytest.mark.asyncio
async def test_direct_provider_stream():
    provider = DirectProvider(model_name="test-stream")
    chunks = []
    async for chunk in provider.stream("Plan execution steps"):
        chunks.append(chunk)

    assert len(chunks) > 0
    reconstructed = "".join(chunks)
    assert "Prompt Processed" in reconstructed or "test-stream" in reconstructed


@pytest.mark.asyncio
async def test_direct_provider_structured_output():
    provider = DirectProvider(model_name="test-structured")
    result = await provider.structured_output("Generate plan", response_model=SamplePlan)

    assert isinstance(result, SamplePlan)
    assert hasattr(result, "plan_title")
    assert isinstance(result.estimated_steps, int)


@pytest.mark.asyncio
async def test_direct_provider_structured_output_with_custom_mock():
    mock_json = '{"plan_title": "Custom Architecture Plan", "estimated_steps": 5, "notes": ["Step 1", "Step 2"]}'
    provider = DirectProvider(model_name="mock-structured", mock_response=mock_json)
    result = await provider.structured_output("Synthesize plan", response_model=SamplePlan)

    assert isinstance(result, SamplePlan)
    assert result.plan_title == "Custom Architecture Plan"
    assert result.estimated_steps == 5
    assert len(result.notes) == 2


def test_direct_provider_capabilities():
    provider = DirectProvider()
    caps = provider.capabilities()

    assert isinstance(caps, ProviderCapabilities)
    assert caps.provider_name == "DirectProvider"
    assert caps.supports_streaming is True
    assert caps.supports_structured_output is True
    assert caps.context_window_size > 0


@pytest.mark.asyncio
async def test_direct_provider_health():
    provider = DirectProvider()
    health = await provider.health()

    assert isinstance(health, ProviderHealthStatus)
    assert health.healthy is True
    assert health.provider_name == "DirectProvider"
    assert health.latency_ms is not None
    assert health.latency_ms >= 0.0


def test_direct_provider_estimate_usage():
    provider = DirectProvider()
    usage = provider.estimate_usage("Test prompt with some words", "Test output response")

    assert usage.prompt_tokens > 0
    assert usage.completion_tokens > 0
    assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens
    assert usage.estimated_cost_usd >= 0.0
