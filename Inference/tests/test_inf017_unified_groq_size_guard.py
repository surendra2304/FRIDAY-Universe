"""TASK-INF-017: Groq size-guard steering on the unified/agent-role path.

TASK-INF-004 recommendation 2: oversized prompts should skip Groq
*before* dispatch, the way REL-043/INF-012 selection already protects
chat/completions. The unified path resolves its target statically
(ROLE_PROVIDER_MAPPING / default groq gpt-oss-120b) with no size
check, so before this fix an oversized auto-routed prompt reached the
gateway as a Groq primary and was diverted by the TASK-REL-047
gateway guard into the catalogue-blind dynamic fallback ladder.

These tests pin the steering and its scope limits:

* auto + role-mapped/default Groq target + over-guard prompt
  -> dispatched to gemini/gemini-flash-latest, guard disclosed on the
     response (fallback_reason) and in the cache meta (cache hit
     discloses identically);
* the boundary is the gateway's own estimator: at/under the limit
  nothing changes;
* explicit provider="groq" is NOT steered (gateway guard remains
  that caller's protection);
* the fast lane is NOT steered (explicit low-latency contract);
* a caller-pinned non-Groq model id is NOT steered;
* under-limit role-mapped requests keep serving from Groq.
"""

from __future__ import annotations

import pytest

from app.performance_cache import perf_cache
from app.providers.base import ProviderResponse
from app.providers.gateway import GROQ_PROMPT_TOKEN_LIMIT, model_gateway
from app.providers.unified_manager import (
    UnifiedExecutionRequest,
    UnifiedProviderManager,
    response_cache,
)


@pytest.fixture(autouse=True)
def clear_caches():
    perf_cache.clear()
    response_cache.flush()
    yield
    perf_cache.clear()
    response_cache.flush()


@pytest.fixture
def fake_gateway(monkeypatch):
    calls = []

    async def execute(_self, *, provider_name, request, capability="general", stage_name="general"):
        calls.append(
            {
                "provider": provider_name,
                "model": request.model,
                "extra_params": dict(request.extra_params or {}),
            }
        )
        return ProviderResponse(
            content=f"served by {provider_name}/{request.model}",
            model=request.model or "test-model",
            provider=provider_name,
            latency_seconds=0.01,
            total_tokens=4,
        )

    monkeypatch.setattr(type(model_gateway), "execute", execute)
    return calls


# Prompt sizes in the gateway estimator's own units (calibrated 2.6
# chars/token, chars * 5 // 13, TASK-INF-021). The over-limit prompt is
# 100 tokens over the guard; the under-limit prompt sits 200 tokens
# below it, so the full request stays under even with the role's
# registered system instructions (~307 chars for code_generator) added
# by the unified path before estimating.
_OVER_LIMIT_PROMPT = "x" * ((GROQ_PROMPT_TOKEN_LIMIT + 100) * 13 // 5)
_UNDER_LIMIT_PROMPT = "x" * ((GROQ_PROMPT_TOKEN_LIMIT - 200) * 13 // 5)


def _request(**overrides) -> UnifiedExecutionRequest:
    values = {
        "provider": "auto",
        "agent_role": "code_generator",  # ROLE_PROVIDER_MAPPING -> groq/openai/gpt-oss-120b
        "prompt": _OVER_LIMIT_PROMPT,
        "context": {},
        "max_tokens": 200,
        "temperature": 0.0,
        "no_cache": False,
    }
    values.update(overrides)
    return UnifiedExecutionRequest(**values)


@pytest.mark.asyncio
async def test_oversized_auto_role_request_is_steered_off_groq_before_dispatch(fake_gateway):
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request())

    assert len(fake_gateway) == 1
    assert fake_gateway[0]["provider"] == "gemini"
    assert fake_gateway[0]["model"] == "gemini-flash-latest"
    # The Groq-only reasoning_effort extra param must not follow the reroute.
    assert "reasoning_effort" not in fake_gateway[0]["extra_params"]
    assert resp.provider_used == "gemini"
    assert resp.model_used == "gemini-flash-latest"
    assert resp.status == "success"
    # The steer is disclosed, not silent.
    assert resp.fallback_reason is not None
    assert "groq_size_guard" in resp.fallback_reason
    assert "TASK-INF-017" in resp.fallback_reason


@pytest.mark.asyncio
async def test_oversized_default_target_request_is_steered(fake_gateway):
    # A role with no mapping and no registered agent resolves to the
    # groq/openai/gpt-oss-120b default — the other measured shape.
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request(agent_role="unmapped_role_inf017"))

    assert fake_gateway[0]["provider"] == "gemini"
    assert resp.provider_used == "gemini"


@pytest.mark.asyncio
async def test_guard_disclosure_survives_a_cache_hit(fake_gateway):
    manager = UnifiedProviderManager()
    first = await manager.execute(_request())
    second = await manager.execute(_request())

    assert len(fake_gateway) == 1
    assert second.status == "cache_hit"
    assert second.provider_used == "gemini"
    assert second.fallback_reason is not None
    assert "groq_size_guard" in second.fallback_reason
    assert first.fallback_reason == second.fallback_reason


@pytest.mark.asyncio
async def test_under_limit_role_request_still_serves_from_groq(fake_gateway):
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request(prompt=_UNDER_LIMIT_PROMPT))

    assert fake_gateway[0]["provider"] == "groq"
    assert fake_gateway[0]["model"] == "openai/gpt-oss-120b"
    assert resp.provider_used == "groq"
    assert resp.fallback_reason is None


@pytest.mark.asyncio
async def test_explicit_groq_provider_is_not_steered(fake_gateway):
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request(provider="groq", model="openai/gpt-oss-120b"))

    assert fake_gateway[0]["provider"] == "groq"
    assert resp.provider_used == "groq"
    assert resp.fallback_reason is None


@pytest.mark.asyncio
async def test_fast_lane_is_not_steered(fake_gateway):
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request(fast_lane=True))

    assert fake_gateway[0]["provider"] == "groq"
    assert fake_gateway[0]["model"] == "openai/gpt-oss-20b"
    assert resp.provider_used == "groq"


@pytest.mark.asyncio
async def test_pinned_non_groq_model_is_not_steered(fake_gateway):
    manager = UnifiedProviderManager()
    resp = await manager.execute(_request(model="gemini-3.6-flash"))

    # Caller pinned the model id under provider="auto": the unified
    # manager's pre-existing resolution keeps it on the role-mapped
    # provider, and INF-017 deliberately does not rewrite it either —
    # the gateway guard remains this shape's protection.
    assert fake_gateway[0]["model"] == "gemini-3.6-flash"
    assert resp.fallback_reason is None
