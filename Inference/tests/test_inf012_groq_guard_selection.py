"""TASK-INF-012: selection must see the gateway's Groq size guard.

Production failure (2026-11-17, Forge re-probe): Forge's G5 "taskboard"
architect call 503'd twice with "The request could only be served by a
model outside the verified catalogue", while the G1 "shortlink"
architect call served fine on openai/gpt-oss-120b. The only material
difference was prompt size: G5's architect prompt estimated ~7,082 /
~7,095 tokens (7,143 / 7,157 actual) against the gateway's
TASK-REL-047 Groq prompt guard of 7,000.

The composition defect: selection ranks Groq models top for code-shaped
prompts (the code hint is checked before the size rule in task-type
inference), the gateway refuses to execute an over-guard prompt on
Groq and diverts it to the catalogue-blind dynamic fallback ladder,
the ladder serves a non-catalogue free model, and TASK-REL-043
containment rejects that serve — twice (the bounded retry's pick is
the other Groq model) — so a request four verified models could serve
ends in a 503.

These tests pin the fix: when the estimated prompt exceeds the Groq
guard, selection drops Groq-routed candidates (never-empty: if that
would empty the pool, the pool is kept), so the first attempt is a
model the gateway will actually execute.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

GROQ_MODELS = {"openai/gpt-oss-120b", "qwen/qwen3.8-27b"}
BREACH_MODEL = "nvidia/nemotron-3.5-super-vl:free"


@pytest.fixture
def healthy_tracker():
    """Isolate tests from the shared provider-health singleton."""
    from app.providers.health import provider_health_tracker

    provider_health_tracker.reset()
    yield provider_health_tracker
    provider_health_tracker.reset()


def _architect_request(total_chars: int):
    """A forge-architect request whose messages total ~total_chars.

    Contains a code hint ("class ") so task-type inference classifies
    it as code — the ranking whose top two entries are Groq models.
    """
    from app.api.v1_core_routes import ChatCompletionRequest

    system = "You are the architect. Design the module layout. " * 10
    filler = "class TaskBoardService: pass  # " + ("x" * 200 + "\n")
    body = filler * (total_chars // len(filler) + 1)
    content = (system + body)[:total_chars]
    return ChatCompletionRequest(
        model="forge-architect",
        messages=[
            {"role": "system", "content": "Forge architect role prompt."},
            {"role": "user", "content": content},
        ],
    )


def test_over_guard_code_request_selects_non_groq(healthy_tracker):
    from app.api.v1_core_routes import _CATALOG_PROVIDERS, _select_best_suitable

    req = _architect_request(29_000)  # ~7,250 estimated prompt tokens
    record = _select_best_suitable(req)
    assert record is not None
    assert record["model"].lower() in _CATALOG_PROVIDERS
    assert _CATALOG_PROVIDERS[record["model"].lower()] != "groq"
    assert record["groq_size_guard"] is not None
    assert record["groq_size_guard"]["limit"] == 7000
    assert record["groq_size_guard"]["prompt_tokens_estimate"] > 7000


def test_under_guard_code_request_unchanged(healthy_tracker):
    from app.api.v1_core_routes import _select_best_suitable

    req = _architect_request(4_000)  # ~1,000 estimated prompt tokens
    record = _select_best_suitable(req)
    assert record is not None
    assert record["model"] == "openai/gpt-oss-120b"
    assert record["groq_size_guard"] is None


def test_over_guard_retry_exclusion_still_non_groq(healthy_tracker):
    """The bounded retry after a failed first attempt must not land on
    the second Groq model — that is exactly how production 503'd."""
    from app.api.v1_core_routes import _CATALOG_PROVIDERS, _select_best_suitable

    req = _architect_request(29_000)
    record = _select_best_suitable(req, exclude={"openai/gpt-oss-120b"})
    assert record is not None
    assert _CATALOG_PROVIDERS[record["model"].lower()] != "groq"


def test_never_empty_when_ranking_is_groq_only(healthy_tracker, monkeypatch):
    """If a ranking contained only Groq models, the guard overlay must
    keep the pool rather than invent a new refusal mode."""
    from app.api import v1_core_routes

    monkeypatch.setattr(
        v1_core_routes,
        "MODEL_SUITABILITY",
        {
            "code": ["openai/gpt-oss-120b"],
            "chat": ["openai/gpt-oss-120b"],
        },
    )
    req = _architect_request(29_000)
    record = v1_core_routes._select_best_suitable(req)
    assert record is not None
    assert record["model"] == "openai/gpt-oss-120b"


def _stub_execute_breach_on_groq(monkeypatch):
    """Recording execute double: Groq models come back as the
    production breach (the gateway ladder's non-catalogue free-model
    serve); every other model serves under its own name."""
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append(req)
        if req.model in GROQ_MODELS:
            return UnifiedExecutionResponse(
                provider_used="openrouter",
                model_used=BREACH_MODEL,
                agent_role=req.agent_role or "system_architect",
                content="OK",
                latency_ms=1.0,
                timestamp=1729000000.0,
                token_usage={"prompt_tokens": 7143, "completion_tokens": 1, "total_tokens": 7144},
                finish_reason="stop",
                fallback_reason="groq prompt-size guard diversion (test double)",
            )
        return UnifiedExecutionResponse(
            provider_used=req.provider,
            model_used=req.model,
            agent_role=req.agent_role or "system_architect",
            content="OK",
            latency_ms=1.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 7143, "completion_tokens": 1, "total_tokens": 7144},
            finish_reason="stop",
        )

    monkeypatch.setattr(unified_provider_manager, "execute", stub)
    return calls


@pytest.mark.asyncio
async def test_g5_shaped_request_serves_in_catalogue(auth, healthy_tracker, monkeypatch):
    """End-to-end: the G5-shaped architect request must be served by a
    verified model on the FIRST attempt — one execute call, no breach,
    no retry, no 503."""
    calls = _stub_execute_breach_on_groq(monkeypatch)
    req = _architect_request(29_000)
    payload = {
        "model": "forge-architect",
        "messages": [m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in req.messages],
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0].model not in GROQ_MODELS
    assert response.json()["model"] == calls[0].model
