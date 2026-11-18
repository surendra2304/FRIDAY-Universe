"""TASK-INF-016 — Inference side of adaptive routing.

FRIDAY's escalation classifier can only route a simple task to the
fast model if that model is a first-class citizen of Inference's
verified catalogue: a non-catalogue id is substituted by REL-043
selection, and a serve of it is contained as a policy breach. This
suite pins the admission of gemini-3.5-flash-lite (catalogue, class,
context window, suitability rankings) and the "simple" task type in
suitability selection: a provably small request selects the fast
tier, while code/reasoning/chat requests keep their flagship picks.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import v1_core_routes as v1
from app.main import app

FAST = "gemini-3.5-flash-lite"
RETIRED_70B = "llama-3.3-70b-versatile"


@pytest.fixture
def all_providers_available(monkeypatch):
    monkeypatch.setattr(v1, "_provider_available", lambda provider: True)


def _req(text: str, model: str = RETIRED_70B, max_tokens: int = 256):
    return v1.ChatCompletionRequest(
        model=model,
        messages=[v1.ChatMessage(role="user", content=text)],
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Catalogue admission
# ---------------------------------------------------------------------------


def test_fast_model_is_in_verified_catalogue():
    ids = [entry["id"] for entry in v1.MODEL_CATALOG]
    assert FAST in ids
    assert v1._provider_for_model(FAST) == "gemini"


def test_fast_model_declares_class_window_and_rankings():
    assert v1.MODEL_CLASSES[FAST] == "economy"
    assert v1.MODEL_CONTEXT_WINDOWS[FAST] > 0
    for task_type, ranking in v1.MODEL_SUITABILITY.items():
        assert FAST in ranking, f"{FAST} missing from the {task_type} ranking"
    assert v1.MODEL_SUITABILITY["simple"][0] == FAST


@pytest.mark.asyncio
async def test_v1_models_lists_fast_model(auth):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        res = await client.get("/v1/models")
    assert res.status_code == 200
    assert FAST in [m["id"] for m in res.json()["data"]]


# ---------------------------------------------------------------------------
# Task-type inference: simple is narrow and late
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "What is 347 + 589?",
        "Calculate 15% of 2400",
        "What is the capital of France?",
        "Rewrite this sentence to be shorter, please",
    ],
)
def test_simple_shapes_infer_simple(text):
    assert v1._infer_task_type(_req(text)) == "simple"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("```python\nprint(1)\n```", "code"),
        ("Prove that this theorem holds, step by step", "reasoning"),
        ("Hello, how are you today?", "chat"),
    ],
)
def test_complex_shapes_never_infer_simple(text, expected):
    assert v1._infer_task_type(_req(text)) == expected


# ---------------------------------------------------------------------------
# Selection: simple -> fast tier; everything else unchanged
# ---------------------------------------------------------------------------


def test_simple_request_selects_fast_model(all_providers_available):
    sel = v1._select_best_suitable(_req("What is 347 + 589?"))
    assert sel is not None
    assert sel["task_type"] == "simple"
    assert sel["model"] == FAST
    assert sel["selected_as"] == "best_suitable_for_simple"
    assert sel["served_class"] == "economy"
    # The caller asked for a flagship-class retired id; serving the
    # economy fast tier for a simple task is disclosed as a downgrade.
    assert sel["downgrade"] is True


def test_chat_request_still_selects_flagship(all_providers_available):
    sel = v1._select_best_suitable(_req("Hello, how are you today?"))
    assert sel is not None
    assert sel["task_type"] == "chat"
    assert sel["model"] == "gemini-3.8-flash"


def test_code_request_still_selects_reasoning_flagship(all_providers_available):
    sel = v1._select_best_suitable(_req("```python\nprint(1)\n```"))
    assert sel is not None
    assert sel["task_type"] == "code"
    assert sel["model"] == "openai/gpt-oss-120b"


# ---------------------------------------------------------------------------
# Route level: a named fast request serves under its own name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_named_fast_model_serves_without_substitution(auth, monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append(req)
        return UnifiedExecutionResponse(
            provider_used=req.provider,
            model_used=req.model,
            agent_role=req.agent_role or "system_architect",
            content="936",
            latency_ms=1.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 6, "completion_tokens": 1, "total_tokens": 7},
            finish_reason="stop",
        )

    monkeypatch.setattr(unified_provider_manager, "execute", stub)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        res = await client.post(
            "/v1/chat/completions",
            json={"model": FAST, "messages": [{"role": "user", "content": "What is 347 + 589?"}], "max_tokens": 16},
        )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == [FAST]
    body = res.json()
    assert body["model"] == FAST
    assert "provenance" not in body or body.get("provenance") is None
