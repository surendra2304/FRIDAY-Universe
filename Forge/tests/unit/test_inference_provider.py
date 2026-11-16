"""
Unit tests for InferenceProvider and Agent 2 Inference mesh routing.

TASK-FRG-009: completions now go through the gateway's OpenAI-compatible
/v1/chat/completions endpoint (per-role alias in, served model + provenance
out) and the provider fails closed — the deterministic DirectProvider
fallback survives only as an explicit opt-in whose output is marked
degraded. These tests stub the provider's transport seams
(_chat_completion / _fetch_health); the FRG-009 suite covers the wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from app.providers.factory import get_provider
from app.providers.inference import InferenceProvider, InferenceUnavailableError


class StructuredOutputDemo(BaseModel):
    name: str
    status: str
    count: int


def _chat_body(content: str, model: str = "openai/gpt-oss-120b") -> dict:
    return {
        "id": "chatcmpl-unit",
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 9, "completion_tokens": 11, "total_tokens": 20},
    }


def test_inference_provider_instantiation() -> None:
    provider = InferenceProvider(model_name="llama-3.3-70b-versatile")
    assert provider.model_name == "llama-3.3-70b-versatile"
    caps = provider.capabilities()
    assert caps.provider_name == "InferenceProvider"
    assert "llama-3.3-70b-versatile" in caps.supported_models
    assert caps.supports_streaming is True


def test_factory_resolves_inference_provider() -> None:
    p1 = get_provider("inference")
    assert isinstance(p1, InferenceProvider)

    p2 = get_provider("ai_universe")
    assert isinstance(p2, InferenceProvider)

    p3 = get_provider(model_name="llama-3.3-70b-versatile")
    assert isinstance(p3, InferenceProvider)


@pytest.mark.asyncio
async def test_inference_provider_generate_success() -> None:
    provider = InferenceProvider(enable_fallback=False)
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(return_value=_chat_body("def add(a, b): return a + b")),
    ):
        resp = await provider.generate("Write an add function")
    assert resp.content == "def add(a, b): return a + b"
    # The response names the model that actually served, not the alias asked.
    assert resp.model == "openai/gpt-oss-120b"
    assert resp.raw_response.get("served_by_model") == "openai/gpt-oss-120b"
    assert resp.raw_response.get("completion_id") == "chatcmpl-unit"


@pytest.mark.asyncio
async def test_inference_provider_generate_fails_closed() -> None:
    provider = InferenceProvider(enable_fallback=False)
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(side_effect=InferenceUnavailableError("Connection refused")),
    ):
        with pytest.raises(InferenceUnavailableError):
            await provider.generate("Write an add function")


@pytest.mark.asyncio
async def test_inference_provider_fallback_to_direct() -> None:
    # If Inference gateway fails and fallback is explicitly enabled, it falls
    # back to DirectProvider — and the response is MARKED as degraded mock
    # output (TASK-FRG-009), never passed off as a model generation.
    provider = InferenceProvider(enable_fallback=True)

    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(side_effect=InferenceUnavailableError("Connection refused")),
    ):
        resp = await provider.generate("Summarize task")
        assert "[Direct Completion" in resp.content
        assert resp.raw_response.get("degraded_fallback") == "direct"


@pytest.mark.asyncio
async def test_inference_provider_structured_output_success() -> None:
    provider = InferenceProvider()
    json_data = '```json\n{"name": "Forge", "status": "active", "count": 10}\n```'
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(return_value=_chat_body(json_data)),
    ):
        out = await provider.structured_output(
            prompt="Generate status",
            response_model=StructuredOutputDemo,
        )
        assert out.name == "Forge"
        assert out.status == "active"
        assert out.count == 10


@pytest.mark.asyncio
async def test_inference_provider_health_check() -> None:
    provider = InferenceProvider()
    with patch.object(
        provider,
        "_fetch_health",
        new=AsyncMock(return_value={"status": "healthy", "providers": ["groq"]}),
    ):
        health = await provider.health()
        assert health.healthy is True
        assert health.provider_name == "InferenceProvider"
        assert "operational" in health.message
