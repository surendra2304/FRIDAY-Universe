"""TASK-REL-043: the owner's model-selection policy — "Inference should
give the best suitable model from the models it have" (2026-11-15).

TASK-REL-032 made the catalogue truthful, but a request naming a model
the gateway does not have was still forwarded verbatim: the provider
404'd and the gateway's fallback ladder served whatever it reached
first — observed live, a request for the retired llama-3.3-70b-versatile
was answered by a free-tier lightweight (nvidia/nemotron-3.5-super-vl:free).

These tests pin the policy that replaces that behaviour:
- a non-catalogue id is never forwarded; the route selects the best
  suitable VERIFIED-CATALOGUE model for the request's task type;
- selection is health-aware (a provider the health tracker judges
  unhealthy — e.g. quota-dead — is skipped for the next-best);
- a degraded first attempt gets exactly one bounded retry with the
  next-best suitable model, and only then the honest REL-032 503;
- containment: a gateway-ladder serve from OUTSIDE the catalogue (the
  best-free rung answering after a deadline — observed live 2026-11-15
  even with selection active) counts as a failed attempt, is retried
  the same way, and is never passed through as the answer;
- provenance records the suitability basis (selected_as) and flags a
  materially weaker substitute explicitly (downgrade);
- catalogue models still serve under their own name, untouched.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

RETIRED_70B = "llama-3.3-70b-versatile"
FREE_LIGHTWEIGHT = "nvidia/nemotron-3.5-lightning:free"


async def _post_chat(auth, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post("/v1/chat/completions", json=payload)


def _stub_execute(monkeypatch, degraded_models=(), breach_models=()):
    """Replace the unified manager's execute with a recording double.

    Models in `degraded_models` come back as honest degraded results
    (no model answered); models in `breach_models` come back as
    "successful" results served by a NON-catalogue free model — the
    gateway ladder behaviour observed live on 2026-11-15 (the selected
    model hit the gateway deadline and the ladder's best-free rung
    answered instead). Every other model answers successfully under
    its own name. Returns the list of execution requests, in order.
    """
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append(req)
        if req.model in breach_models:
            return UnifiedExecutionResponse(
                provider_used="openrouter",
                model_used="nvidia/nemotron-3.5-super-vl:free",
                agent_role=req.agent_role or "system_architect",
                content="OK",
                latency_ms=1.0,
                timestamp=1729000000.0,
                token_usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                finish_reason="stop",
                fallback_reason=f"Request deadline exceeded for provider '{req.provider}' (test double)",
            )
        if req.model in degraded_models:
            return UnifiedExecutionResponse(
                provider_used=req.provider,
                model_used=req.model or "none",
                agent_role=req.agent_role or "system_architect",
                content="",
                latency_ms=1.0,
                timestamp=1729000000.0,
                token_usage={},
                status="degraded",
                degraded=True,
                error=f"{req.provider}: provider unavailable (test double)",
            )
        return UnifiedExecutionResponse(
            provider_used=req.provider,
            model_used=req.model,
            agent_role=req.agent_role or "system_architect",
            content="OK",
            latency_ms=1.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            finish_reason="stop",
        )

    monkeypatch.setattr(unified_provider_manager, "execute", stub)
    return calls


@pytest.fixture
def healthy_tracker():
    """Isolate tests that seed the shared provider-health singleton."""
    from app.providers.health import provider_health_tracker

    provider_health_tracker.reset()
    yield provider_health_tracker
    provider_health_tracker.reset()


def _kill_provider(tracker, provider):
    """Drive a provider's health report to unhealthy (>=4 straight failures)."""
    for _ in range(4):
        tracker.record_failure(provider, "quota exhausted (test double)", is_429=True)


@pytest.mark.asyncio
async def test_retired_id_gets_best_suitable_not_the_free_lightweight(auth, monkeypatch, healthy_tracker):
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # The dead id never reached execution; the best suitable catalogue
    # model for plain chat did — not the economy free lightweight the
    # old ladder accident produced.
    assert [c.model for c in calls] == ["gemini-3.8-flash"]
    body = res.json()
    assert body["model"] == "gemini-3.8-flash"
    assert body["model"] != FREE_LIGHTWEIGHT
    provenance = body["provenance"]
    assert provenance["requested_model"] == RETIRED_70B
    assert provenance["served_by_model"] == "gemini-3.8-flash"
    assert provenance["selected_as"] == "best_suitable_for_chat"
    assert provenance["selected_model"] == "gemini-3.8-flash"
    # 70B is flagship-class; the flagship catalogue model is not a downgrade.
    assert provenance["downgrade"] is False
    assert provenance["downgrade_reason"] is None


@pytest.mark.asyncio
async def test_degraded_top_pick_falls_to_next_best(auth, monkeypatch, healthy_tracker):
    calls = _stub_execute(monkeypatch, degraded_models={"gemini-3.8-flash"})
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["gemini-3.8-flash", "openai/gpt-oss-120b"]
    body = res.json()
    assert body["model"] == "openai/gpt-oss-120b"
    provenance = body["provenance"]
    assert provenance["selected_as"] == "best_suitable_for_chat"
    assert provenance["selected_model"] == "openai/gpt-oss-120b"
    assert provenance["downgrade"] is False


@pytest.mark.asyncio
async def test_unhealthy_provider_is_skipped_by_selection(auth, monkeypatch, healthy_tracker):
    _kill_provider(healthy_tracker, "gemini")
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # Both Gemini models are skipped while the tracker judges the
    # provider unhealthy; the next-best suitable model serves FIRST
    # (no wasted attempt on the quota-dead route).
    assert [c.model for c in calls] == ["openai/gpt-oss-120b"]
    assert res.json()["model"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_catalogue_request_serves_own_name_without_selection(auth, monkeypatch, healthy_tracker):
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["openai/gpt-oss-120b"]
    body = res.json()
    assert body["model"] == "openai/gpt-oss-120b"
    assert "provenance" not in body


@pytest.mark.asyncio
async def test_catalogue_route_degraded_retries_best_suitable(auth, monkeypatch, healthy_tracker):
    calls = _stub_execute(monkeypatch, degraded_models={"gemini-3.6-flash"})
    res = await _post_chat(
        auth,
        {"model": "gemini-3.6-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["gemini-3.6-flash", "gemini-3.8-flash"]
    body = res.json()
    assert body["model"] == "gemini-3.8-flash"
    provenance = body["provenance"]
    assert provenance["requested_model"] == "gemini-3.6-flash"
    assert provenance["selected_as"] == "best_suitable_for_chat"
    assert provenance["selected_model"] == "gemini-3.8-flash"
    assert provenance["downgrade"] is False


@pytest.mark.asyncio
async def test_everything_degraded_is_still_an_honest_503(auth, monkeypatch, healthy_tracker):
    from app.api.v1_core_routes import MODEL_CATALOG

    _stub_execute(monkeypatch, degraded_models={entry["id"] for entry in MODEL_CATALOG})
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    # Best-suitable service first; refusal only when nothing suitable
    # could answer — and then the REL-032 honest shape, naming the
    # caller's own model, never a fake completion.
    assert res.status_code == 503, res.text
    body = res.json()
    assert body["error"]["code"] == "provider_degraded"
    assert body["retryable"] is True
    assert body["requested_model"] == RETIRED_70B
    assert "choices" not in body


@pytest.mark.asyncio
async def test_code_task_selects_the_code_ranking(auth, monkeypatch, healthy_tracker):
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {
            "model": RETIRED_70B,
            "messages": [{"role": "user", "content": "Explain this:\n```python\nprint('hi')\n```"}],
            "max_tokens": 16,
        },
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["openai/gpt-oss-120b"]
    assert res.json()["provenance"]["selected_as"] == "best_suitable_for_code"


@pytest.mark.asyncio
async def test_downgrade_is_flagged_when_only_a_weaker_class_is_available(
    auth, monkeypatch, healthy_tracker
):
    _kill_provider(healthy_tracker, "gemini")
    calls = _stub_execute(monkeypatch, degraded_models={"openai/gpt-oss-120b"})
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # Gemini is health-skipped, the flagship Groq pick degrades, and the
    # bounded retry lands on the standard-class 70B instruct — a real
    # downgrade from the flagship-class request, disclosed as one.
    assert [c.model for c in calls] == ["openai/gpt-oss-120b", "meta-llama/llama-3.3-70b-instruct"]
    provenance = res.json()["provenance"]
    assert provenance["selected_model"] == "meta-llama/llama-3.3-70b-instruct"
    assert provenance["downgrade"] is True
    assert "flagship" in provenance["downgrade_reason"]
    assert "standard" in provenance["downgrade_reason"]


@pytest.mark.asyncio
async def test_ladder_breach_is_contained_and_retried_with_next_best(auth, monkeypatch, healthy_tracker):
    # Live incident, 2026-11-15: the policy selected gemini-3.8-flash,
    # the gateway's deadline fired, and its best-free ladder rung served
    # a NON-catalogue model behind HTTP 200. Containment: that serve
    # counts as a failed attempt; the next-best suitable model answers.
    calls = _stub_execute(monkeypatch, breach_models={"gemini-3.8-flash"})
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["gemini-3.8-flash", "openai/gpt-oss-120b"]
    body = res.json()
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["provenance"]["selected_model"] == "openai/gpt-oss-120b"
    assert body["provenance"]["served_by_model"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_catalogue_request_breached_by_ladder_is_also_contained(auth, monkeypatch, healthy_tracker):
    # The same ladder breach on a direct catalogue request (also
    # observed live) must not pass through either.
    calls = _stub_execute(monkeypatch, breach_models={"gemini-3.8-flash"})
    res = await _post_chat(
        auth,
        {"model": "gemini-3.8-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == ["gemini-3.8-flash", "openai/gpt-oss-120b"]
    body = res.json()
    assert body["model"] == "openai/gpt-oss-120b"
    provenance = body["provenance"]
    assert provenance["requested_model"] == "gemini-3.8-flash"
    assert provenance["selected_as"] == "best_suitable_for_chat"


@pytest.mark.asyncio
async def test_ladder_breach_everywhere_is_an_honest_503_never_a_serve(auth, monkeypatch, healthy_tracker):
    from app.api.v1_core_routes import MODEL_CATALOG

    _stub_execute(monkeypatch, breach_models={entry["id"] for entry in MODEL_CATALOG})
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    # When every route can only be reached through a non-catalogue
    # substitute, the policy's answer is the honest 503 — the banned
    # model is never presented as the answer.
    assert res.status_code == 503, res.text
    body = res.json()
    assert body["error"]["code"] == "provider_degraded"
    assert body["requested_model"] == RETIRED_70B
    assert "choices" not in body
    assert "nemotron-3.5-super-vl" not in res.text


def test_suitability_tables_cover_exactly_the_verified_catalogue():
    from app.api.v1_core_routes import MODEL_CATALOG, MODEL_CLASSES, MODEL_SUITABILITY

    catalogue_ids = {entry["id"] for entry in MODEL_CATALOG}
    assert set(MODEL_CLASSES) == catalogue_ids
    for task_type, ranked in MODEL_SUITABILITY.items():
        assert set(ranked) == catalogue_ids, f"{task_type} ranking must rank the full catalogue"
        assert len(ranked) == len(catalogue_ids), f"{task_type} ranking has duplicates"


def test_task_type_inference_is_deterministic():
    from app.api.v1_core_routes import ChatCompletionRequest, _infer_task_type

    def infer(model, content):
        req = ChatCompletionRequest(model=model, messages=[{"role": "user", "content": content}])
        return _infer_task_type(req)

    assert infer(RETIRED_70B, "hello there") == "chat"
    assert infer(RETIRED_70B, "fix this:\n```python\nx = 1\n```") == "code"
    assert infer("some-vl-model", "what is in this image?") == "vision"
    assert infer(RETIRED_70B, "prove that the theorem holds, step by step") == "reasoning"
    assert infer(RETIRED_70B, "x" * 24000) == "long_context"


def test_requested_class_inference():
    from app.api.v1_core_routes import _requested_class

    assert _requested_class("llama-3.3-70b-versatile") == "flagship"
    assert _requested_class("llama-3.1-8b-instant") == "economy"
    assert _requested_class("some-unknown-model") == "standard"
    # Catalogue ids always use their declared class.
    assert _requested_class("nvidia/nemotron-3.5-lightning:free") == "economy"
    assert _requested_class("gemini-3.8-flash") == "flagship"


def test_ranked_candidates_never_leave_the_catalogue(healthy_tracker):
    from app.api.v1_core_routes import MODEL_CATALOG, _ranked_suitable_models

    catalogue_ids = {entry["id"] for entry in MODEL_CATALOG}
    _kill_provider(healthy_tracker, "groq")
    ranked = _ranked_suitable_models("chat")
    assert ranked and all(model_id in catalogue_ids for model_id in ranked)
    # Groq's two models are health-skipped; the Gemini head remains.
    assert "openai/gpt-oss-120b" not in ranked
    assert "qwen/qwen3.8-27b" not in ranked
    assert ranked[0] == "gemini-3.8-flash"
    # Excluding the whole catalogue leaves nothing to select.
    assert _ranked_suitable_models("chat", exclude=catalogue_ids) == []
