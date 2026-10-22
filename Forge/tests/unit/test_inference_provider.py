"""
Unit tests for InferenceProvider and Agent 2 Inference mesh routing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from app.integrations.ai_universe_client import AIUniverseResponse
from app.providers.factory import get_provider
from app.providers.inference import InferenceProvider


class StructuredOutputDemo(BaseModel):
    name: str
    status: str
    count: int


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
    mock_resp = AIUniverseResponse(
        answer="def add(a, b): return a + b",
        confidence=0.98,
        run_id="run-12345",
    )

    with patch.object(provider.client, "ask", new=AsyncMock(return_value=mock_resp)):
        resp = await provider.generate("Write an add function")
        assert resp.content == "def add(a, b): return a + b"
        assert resp.model == "inference-router"
        assert resp.raw_response.get("run_id") == "run-12345"


@pytest.mark.asyncio
async def test_inference_provider_fallback_to_direct() -> None:
    # If Inference gateway fails and fallback is enabled, it falls back to DirectProvider
    provider = InferenceProvider(enable_fallback=True)

    with patch.object(
        provider.client,
        "ask",
        new=AsyncMock(side_effect=RuntimeError("Connection refused to inference:8000")),
    ):
        resp = await provider.generate("Summarize task")
        assert "[Direct Completion" in resp.content


@pytest.mark.asyncio
async def test_inference_provider_structured_output_success() -> None:
    provider = InferenceProvider()
    json_data = '```json\n{"name": "Forge", "status": "active", "count": 10}\n```'
    mock_resp = AIUniverseResponse(answer=json_data, confidence=0.99)

    with patch.object(provider.client, "ask", new=AsyncMock(return_value=mock_resp)):
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
    mock_resp = AIUniverseResponse(answer="pong", confidence=1.0, run_id="ping-test")

    with patch.object(provider.client, "ask", new=AsyncMock(return_value=mock_resp)):
        health = await provider.health()
        assert health.healthy is True
        assert health.provider_name == "InferenceProvider"
        assert "operational" in health.message
