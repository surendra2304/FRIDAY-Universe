"""Regression: /v1/chat/completions with model="auto" must not enter the
60-token fast lane.

Measured live on 2026-11-17 (P3 truncation diagnosis): every
non-streaming POST /v1/chat/completions with model="auto" stopped at
exactly 60 completion tokens with finish_reason="length", regardless of
the caller's max_tokens (probes at 800 and 4,000 both stopped at 60;
a named-model control honoured the full 800). The mechanism was in this
route, not the manager: ``_execute_once`` built every auto request with
``fast_lane=True``, and the unified manager's fast-lane override then
silently clamped max_tokens to 60, forced groq/openai/gpt-oss-20b and
replaced the system prompt with a "1-2 sentences (maximum 40 words)"
instruction. Nothing in the response disclosed the override. Named
production victims: FRIDAY's autonomous daemon, which asks for 2,500
tokens through this surface with no model (i.e. "auto"), and FRIDAY's
cognition mesh default.

"auto" delegates the CHOICE of model. It is not a request for the fast
lane, and the OpenAI-compatible request schema has no fast-lane field a
caller could opt in with. These tests pin the corrected contract:

- (a) an auto chat request reaches the unified manager with
  fast_lane=False and the caller's max_tokens intact, still delegating
  the model choice (provider="auto", model=None);
- (b) the caller's system prompt is not replaced: it heads the prompt
  the route composes, and at the manager boundary a non-fast-lane auto
  execution sends no 40-word replacement system instruction;
- (c) the explicit fast-lane contracts are untouched: FRIDAY /ask still
  asks for the lane by name (max_tokens=60, fast_lane=True), and the
  manager still applies the 60-token shape when a caller explicitly
  passes fast_lane=True (the /v1/ask mode="fast" path rides the same
  mechanism);
- (d) a named-model chat request is unchanged.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.performance_cache import perf_cache
from app.providers.base import ProviderResponse
from app.providers.gateway import model_gateway
from app.providers.unified_manager import (
    UnifiedExecutionRequest,
    UnifiedExecutionResponse,
    UnifiedProviderManager,
    response_cache,
    unified_provider_manager,
)


FAST_LANE_MODEL = "openai/gpt-oss-20b"
CALLER_SYSTEM = "You are a meticulous research analyst. Answer in full paragraphs."


async def _post(path, auth, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post(path, json=payload)


def _stub_manager_execute(monkeypatch, served_model="openai/gpt-oss-120b"):
    """Replace the unified manager's execute with a recording double.

    Every request answers successfully under the served model; returns
    the list of execution requests, in order (the TASK-REL-043 harness
    shape).
    """
    calls = []

    async def stub(req):
        calls.append(req)
        return UnifiedExecutionResponse(
            provider_used=req.provider if req.provider != "auto" else "groq",
            model_used=req.model or served_model,
            agent_role=req.agent_role or "system_architect",
            content="OK",
            latency_ms=1.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            finish_reason="stop",
        )

    monkeypatch.setattr(unified_provider_manager, "execute", stub)
    return calls


# ---------------------------------------------------------------------------
# Route level: what /v1/chat/completions hands to the unified manager.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_auto_chat_is_not_fast_laned(auth, monkeypatch):
    calls = _stub_manager_execute(monkeypatch)
    res = await _post(
        "/v1/chat/completions",
        auth,
        {
            "model": "auto",
            "messages": [
                {"role": "system", "content": CALLER_SYSTEM},
                {"role": "user", "content": "Write a detailed analysis."},
            ],
            "max_tokens": 800,
        },
    )
    assert res.status_code == 200, res.text
    assert len(calls) == 1
    req = calls[0]
    # "auto" still delegates the model choice to the manager...
    assert req.provider == "auto"
    assert req.model is None
    # ...but delegation is not a fast-lane request: the caller's budget
    # reaches the manager intact instead of being clamped to 60 there.
    assert req.fast_lane is False
    assert req.max_tokens == 800
    # (b) at the route boundary: the caller's system prompt heads the
    # composed prompt; it is not dropped or swapped on this surface.
    assert req.prompt.startswith(CALLER_SYSTEM)


@pytest.mark.asyncio
async def test_v1_named_model_chat_unchanged(auth, monkeypatch):
    calls = _stub_manager_execute(monkeypatch)
    res = await _post(
        "/v1/chat/completions",
        auth,
        {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 800,
        },
    )
    assert res.status_code == 200, res.text
    assert len(calls) == 1
    req = calls[0]
    assert req.model == "openai/gpt-oss-120b"
    assert req.fast_lane is False
    assert req.max_tokens == 800
    assert "provenance" not in res.json()


@pytest.mark.asyncio
async def test_friday_ask_fast_lane_contract_unchanged(auth, monkeypatch):
    # (c) FRIDAY /ask's sub-second contract is explicit and deliberate:
    # it asks the manager for the fast lane by name, with a literal
    # 60-token budget, and reports the truncation-aware confidence. The
    # /v1 chat fix must not disturb it.
    calls = _stub_manager_execute(monkeypatch)
    res = await _post(
        "/v1/friday/ask",
        auth,
        {"question": "What is the fleet status?", "no_cache": True},
    )
    assert res.status_code == 200, res.text
    assert len(calls) == 1
    req = calls[0]
    assert req.fast_lane is True
    assert req.max_tokens == 60
    assert res.json()["mode_used"] == "fast"


# ---------------------------------------------------------------------------
# Manager level: the gateway request a non-fast-lane auto execution builds.
# (The TASK-INF-006 cache-scope harness shape: a recording gateway double.)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_response_cache():
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
                "max_tokens": request.max_tokens,
                "system_instruction": request.system_instruction,
                "content": request.messages[0].content,
            }
        )
        return ProviderResponse(
            content="OK",
            model=request.model or "test-model",
            provider=provider_name,
            latency_seconds=0.01,
            total_tokens=4,
        )

    monkeypatch.setattr(type(model_gateway), "execute", execute)
    return calls


def _manager_request(**overrides) -> UnifiedExecutionRequest:
    # An unregistered role keeps agent/role routing out of the way: with
    # provider="auto" and no model, the manager's own auto resolution is
    # what decides the target — the same resolution the /v1 auto route
    # delegates to.
    values = {
        "provider": "auto",
        "model": None,
        "agent_role": "auto_route_regression_role",
        "prompt": f"{CALLER_SYSTEM}\n\nuser: Write a detailed analysis.",
        "context": {},
        "max_tokens": 800,
        "temperature": 0.4,
        "no_cache": True,
    }
    values.update(overrides)
    return UnifiedExecutionRequest(**values)


@pytest.mark.asyncio
async def test_manager_auto_without_fast_lane_honours_budget_and_prompt(fake_gateway):
    manager = UnifiedProviderManager()
    res = await manager.execute(_manager_request(fast_lane=False))
    assert res.status == "success"
    assert len(fake_gateway) == 1
    call = fake_gateway[0]
    # (a) the caller's budget survives, and the target is the manager's
    # normal auto resolution — not the fast lane's forced 20B model.
    assert call["max_tokens"] == 800
    assert call["model"] != FAST_LANE_MODEL
    # (b) no replacement system instruction: the 40-word fast-lane text
    # is absent, and the caller's system text reaches the provider as
    # part of the composed prompt, as the /v1 route embedded it.
    assert "maximum 40 words" not in (call["system_instruction"] or "")
    assert CALLER_SYSTEM in call["content"]


@pytest.mark.asyncio
async def test_manager_explicit_fast_lane_still_clamps(fake_gateway):
    # (c) at the mechanism level: the lane itself is a legitimate
    # explicit contract. When a caller passes fast_lane=True by name,
    # the 60-token shape must still be exactly what the gateway sees —
    # this fix removes only the /v1 chat surface's implicit opt-in.
    manager = UnifiedProviderManager()
    res = await manager.execute(_manager_request(fast_lane=True))
    assert res.status == "success"
    assert len(fake_gateway) == 1
    call = fake_gateway[0]
    assert call["max_tokens"] == 60
    assert call["model"] == FAST_LANE_MODEL
    assert "maximum 40 words" in (call["system_instruction"] or "")
