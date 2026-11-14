"""TASK-REL-030: the /v1/models catalogue must only advertise models that
actually answer, chat routing must resolve providers from catalogue
ownership, and a degraded or substituted chat completion must never
masquerade as a clean success.

Live evidence behind the denylist (provider-direct audit, Server 1,
2026-11-14 ~21:17-21:24Z):
- Groq returns 404 model_not_found for llama-3.3-70b-versatile AND
  llama-3.1-8b-instant (both retired; absent from the account model list).
- Google returns 404 for gemini-2.5-flash ("no longer available to new
  users. Please update your code to use models/gemini-3.8-flash").
- liquid/lfm-2.5-2.6b:free is absent from OpenRouter's live catalogue.
- Cerebras has no configured keys in Inference, so cerebras/* can never
  serve here; the NVIDIA route answers 403 with the configured key.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

RETIRED_OR_UNSERVABLE = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemini-2.5-flash",
    "liquid/lfm-2.5-2.6b:free",
    "cerebras/llama-3.3-70b",
    "nvidia/nemotron-3-super-120b-a12b",
]


async def _get(auth, path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.get(path)


async def _post_chat(auth, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post("/v1/chat/completions", json=payload)


@pytest.mark.asyncio
async def test_v1_models_catalogue_has_no_retired_or_unservable_models(auth):
    res = await _get(auth, "/v1/models")
    assert res.status_code == 200
    model_ids = [m["id"] for m in res.json()["data"]]
    for dead in RETIRED_OR_UNSERVABLE:
        assert dead not in model_ids, f"catalogue still advertises {dead}"
    # The verified-live core stays advertised.
    assert "gemini-3.8-flash" in model_ids
    assert "openai/gpt-oss-120b" in model_ids
    assert "auto" in model_ids


@pytest.mark.asyncio
async def test_operational_models_have_no_dead_entries(auth):
    res = await _get(auth, "/models")
    assert res.status_code == 200
    pairs = {(m["provider"], m["model"]) for m in res.json()["models"]}
    assert ("openrouter", "liquid/lfm-2.5-2.6b:free") not in pairs
    assert ("nvidia", "z-ai/glm-5.3") not in pairs
    # The NVIDIA route answers 403 with the configured key: it must not be
    # advertised as available until the credential can actually serve it.
    assert all(provider != "nvidia" for provider, _ in pairs)


def test_route_provider_resolves_catalogue_ownership():
    from app.api.v1_core_routes import _provider_for_model

    assert _provider_for_model("gemini-3.6-flash") == "gemini"
    assert _provider_for_model("openai/gpt-oss-120b") == "groq"
    assert _provider_for_model("qwen/qwen3.8-27b") == "groq"
    assert _provider_for_model("meta-llama/llama-3.3-70b-instruct") == "openrouter"
    # Non-catalogue ids that previously fell through to groq by accident:
    assert _provider_for_model("nvidia/nemotron-3-super-120b-a12b") == "nvidia"
    assert _provider_for_model("some/model:free") == "openrouter"


def _mock_execute(monkeypatch, response):
    from app.providers.unified_manager import unified_provider_manager

    async def mock_execute(req):
        return response

    monkeypatch.setattr(unified_provider_manager, "execute", mock_execute)


@pytest.mark.asyncio
async def test_chat_completions_degraded_is_not_a_fake_200(auth, monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse

    _mock_execute(
        monkeypatch,
        UnifiedExecutionResponse(
            provider_used="groq",
            model_used="openai/gpt-oss-120b",
            agent_role="system_architect",
            content="",
            latency_ms=42.0,
            timestamp=1729000000.0,
            token_usage={},
            status="degraded",
            degraded=True,
            error="groq: provider unavailable (test double)",
        ),
    )
    res = await _post_chat(
        auth,
        {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 503, res.text
    body = res.json()
    assert body["error"]["code"] == "provider_degraded"
    assert body["retryable"] is True
    assert body["requested_model"] == "openai/gpt-oss-120b"
    assert "choices" not in body


@pytest.mark.asyncio
async def test_chat_completions_substitution_carries_provenance(auth, monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse

    _mock_execute(
        monkeypatch,
        UnifiedExecutionResponse(
            provider_used="openrouter",
            model_used="nvidia/nemotron-3.5-super-vl:free",
            agent_role="system_architect",
            content="OK",
            latency_ms=42.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
            finish_reason="stop",
            served_by_provider="openrouter",
        ),
    )
    res = await _post_chat(
        auth,
        {"model": "gemini-3.6-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["model"] == "nvidia/nemotron-3.5-super-vl:free"
    provenance = body.get("provenance")
    assert provenance is not None, "substituted answer must not be silent"
    assert provenance["requested_model"] == "gemini-3.6-flash"
    assert provenance["requested_provider"] == "gemini"
    assert provenance["served_by_provider"] == "openrouter"
    assert provenance["served_by_model"] == "nvidia/nemotron-3.5-super-vl:free"


@pytest.mark.asyncio
async def test_chat_completions_direct_hit_has_no_provenance_block(auth, monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse

    _mock_execute(
        monkeypatch,
        UnifiedExecutionResponse(
            provider_used="groq",
            model_used="openai/gpt-oss-120b",
            agent_role="system_architect",
            content="OK",
            latency_ms=42.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
            finish_reason="stop",
        ),
    )
    res = await _post_chat(
        auth,
        {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["model"] == "openai/gpt-oss-120b"
    assert "provenance" not in body
