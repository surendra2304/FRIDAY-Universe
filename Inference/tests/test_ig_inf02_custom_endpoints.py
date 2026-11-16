"""TASK-IG-INF-02: operator-configured custom inference endpoints.

Corpus source Dctokdztllm — support third-party/custom inference
endpoints so agents can run on alternate providers. Before this task
exactly one alternate endpoint existed (the single `local` provider);
now an operator can declare any number of OpenAI-compatible endpoints
in INFERENCE_CUSTOM_ENDPOINTS, each becoming a gateway provider named
custom-<name> whose models are addressable by id.

These tests pin the safety properties, not just the happy path:
- parsing is fail-closed (malformed config registers nothing);
- a keyed endpoint whose api_key_env is unset is DISABLED with the
  reason recorded, never silently keyless;
- key isolation: a custom pool holds ONLY its endpoint's own key —
  settings.get_provider_keys (which merges THIRD_PARTY_* and fallback
  pools) is never consulted for custom providers, and refresh_keys
  re-resolves from the registry instead of wiping the pool;
- custom models are addressable but are NOT catalogue models: naming
  one serves it under its own name with no REL-043 substitution, and
  a custom failure degrades into the bounded retry / honest 503.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.providers import custom_endpoints
from app.providers.custom_endpoints import parse_custom_endpoints

AGG_KEY = "test-only-aggregator-key"  # not a credential; exists only in this process

CONFIG = json.dumps(
    [
        {
            "name": "deskbox",
            "base_url": "http://192.0.2.10:8080/v1",
            "models": [{"id": "desk-llama-70b", "context_window": 131072}],
        },
        {
            "name": "aggregator",
            "base_url": "https://agg.example.test/v1",
            "api_key_env": "IG_INF02_AGG_KEY",
            "models": ["agg/auto"],
        },
    ]
)


@pytest.fixture
def custom_config(monkeypatch):
    """Point the endpoint registry at CONFIG with the aggregator key set."""
    monkeypatch.setenv("IG_INF02_AGG_KEY", AGG_KEY)
    monkeypatch.setattr(settings, "INFERENCE_CUSTOM_ENDPOINTS", CONFIG)
    custom_endpoints.reset_custom_endpoints_cache()
    yield
    custom_endpoints.reset_custom_endpoints_cache()
    from app.providers import _PROVIDER_CACHE

    for name in ("custom-deskbox", "custom-aggregator"):
        _PROVIDER_CACHE.pop(name, None)


# ---------------------------------------------------------------------------
# Parsing (pure; environ injected)
# ---------------------------------------------------------------------------


def test_parse_keyed_and_keyless_endpoints():
    endpoints = parse_custom_endpoints(CONFIG, {"IG_INF02_AGG_KEY": AGG_KEY})
    assert [ep.name for ep in endpoints] == ["deskbox", "aggregator"]
    deskbox, aggregator = endpoints
    assert deskbox.enabled and deskbox.api_key is None  # explicit keyless choice
    assert deskbox.provider_name == "custom-deskbox"
    assert deskbox.models == [{"id": "desk-llama-70b", "context_window": 131072}]
    assert aggregator.enabled and aggregator.api_key == AGG_KEY
    assert aggregator.provider_name == "custom-aggregator"
    assert aggregator.model_ids == ["agg/auto"]


def test_parse_empty_and_malformed_register_nothing():
    assert parse_custom_endpoints("", {}) == []
    assert parse_custom_endpoints(None, {}) == []
    assert parse_custom_endpoints("{not json", {}) == []
    assert parse_custom_endpoints('{"name": "x"}', {}) == []  # not an array


def test_parse_missing_key_env_disables_with_reason():
    endpoints = parse_custom_endpoints(CONFIG, {})  # key var unset
    by_name = {ep.name: ep for ep in endpoints}
    assert by_name["deskbox"].enabled
    aggregator = by_name["aggregator"]
    assert not aggregator.enabled
    assert "IG_INF02_AGG_KEY" in (aggregator.disabled_reason or "")


def test_parse_rejects_bad_entries_but_keeps_valid_ones():
    raw = json.dumps(
        [
            {"name": "Bad Name!", "base_url": "http://x.test/v1", "models": ["m1"]},
            {"name": "nohttp", "base_url": "ftp://x.test/v1", "models": ["m2"]},
            {"name": "nomodels", "base_url": "http://x.test/v1", "models": []},
            {"name": "good", "base_url": "http://x.test/v1", "models": ["shared-model"]},
            {"name": "good", "base_url": "http://y.test/v1", "models": ["other"]},  # dup name
            {"name": "thief", "base_url": "http://z.test/v1", "models": ["shared-model"]},  # dup model
        ]
    )
    endpoints = parse_custom_endpoints(raw, {})
    assert [ep.name for ep in endpoints] == ["good"]
    assert endpoints[0].model_ids == ["shared-model"]


# ---------------------------------------------------------------------------
# Registry + provider factory
# ---------------------------------------------------------------------------


def test_registry_resolution_and_catalog_entries(custom_config):
    assert custom_endpoints.custom_provider_for_model("desk-llama-70b") == "custom-deskbox"
    assert custom_endpoints.custom_provider_for_model("AGG/AUTO") == "custom-aggregator"
    assert custom_endpoints.custom_provider_for_model("no-such-model") is None
    entries = {e["id"]: e for e in custom_endpoints.custom_catalog_entries()}
    assert entries["desk-llama-70b"]["owned_by"] == "custom:deskbox"
    assert entries["agg/auto"]["provider"] == "custom-aggregator"


def test_get_provider_builds_adapter_and_rejects_unknown(custom_config):
    from app.providers import get_provider

    adapter = get_provider("custom-deskbox")
    assert adapter.provider_name == "custom-deskbox"
    assert adapter.base_url == "http://192.0.2.10:8080/v1"
    assert adapter.supported_models == ["desk-llama-70b"]
    assert adapter.api_keys == []

    keyed = get_provider("custom-aggregator")
    assert keyed.api_keys == [AGG_KEY]

    with pytest.raises(ValueError):
        get_provider("custom-not-configured")


# ---------------------------------------------------------------------------
# Gateway pools: isolation + credentials + refresh
# ---------------------------------------------------------------------------


def test_gateway_pools_hold_only_the_endpoints_own_key(custom_config):
    from app.providers.gateway import ModelGateway

    gateway = ModelGateway()
    assert gateway.key_pools["custom-aggregator"]._keys == [AGG_KEY]
    assert gateway.key_pools["custom-deskbox"]._keys == []
    # The pooled lookup merges THIRD_PARTY_*/fallback keys; it must know
    # nothing about custom providers — proof the pool above did not come
    # from (and cannot be polluted by) that path.
    assert settings.get_provider_keys("custom-aggregator") == []
    # refresh_keys must re-resolve custom pools from the registry, not
    # wipe them via the pooled lookup.
    gateway.refresh_keys()
    assert gateway.key_pools["custom-aggregator"]._keys == [AGG_KEY]


def test_provider_has_credentials_for_custom_providers(custom_config):
    from app.providers.gateway import provider_has_credentials

    assert provider_has_credentials("custom-deskbox") is True  # keyless by choice
    assert provider_has_credentials("custom-aggregator") is True
    assert provider_has_credentials("custom-not-configured") is False


# ---------------------------------------------------------------------------
# Routes: resolution, serving, listing
# ---------------------------------------------------------------------------


def test_provider_for_model_prefers_custom_ownership(custom_config):
    from app.api.v1_core_routes import _provider_for_model

    assert _provider_for_model("desk-llama-70b") == "custom-deskbox"
    assert _provider_for_model("agg/auto") == "custom-aggregator"
    # Catalogue ownership still wins for catalogue ids.
    assert _provider_for_model("openai/gpt-oss-120b") != "custom-deskbox"


def _stub_gateway_execute(monkeypatch, fail=False):
    from app.providers.base import ProviderResponse
    from app.providers.gateway import model_gateway

    calls = []

    async def stub(provider_name, request, capability="general", stage_name="general"):
        calls.append((provider_name, request))
        if fail:
            raise RuntimeError("custom endpoint unreachable (test double)")
        return ProviderResponse(
            content="answer from the custom endpoint",
            model=request.model,
            provider=provider_name,
            prompt_tokens=5,
            completion_tokens=2,
            total_tokens=7,
            finish_reason="stop",
        )

    monkeypatch.setattr(model_gateway, "execute", stub)
    return calls


def _stub_unified_degraded(monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    async def stub(req):
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

    monkeypatch.setattr(unified_provider_manager, "execute", stub)


async def _post_chat(auth, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post("/v1/chat/completions", json=payload)


@pytest.mark.asyncio
async def test_chat_serves_custom_model_under_its_own_name(auth, custom_config, monkeypatch):
    calls = _stub_gateway_execute(monkeypatch)
    response = await _post_chat(
        auth,
        {"model": "desk-llama-70b", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "desk-llama-70b"
    assert body["choices"][0]["message"]["content"] == "answer from the custom endpoint"
    # Served by exactly what was asked: no substitution provenance.
    assert "provenance" not in body
    assert calls and calls[0][0] == "custom-deskbox"
    assert calls[0][1].model == "desk-llama-70b"


@pytest.mark.asyncio
async def test_chat_custom_failure_is_an_honest_503(auth, custom_config, monkeypatch):
    _stub_gateway_execute(monkeypatch, fail=True)
    _stub_unified_degraded(monkeypatch)  # the bounded catalogue retry also fails
    response = await _post_chat(
        auth,
        {"model": "desk-llama-70b", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "provider_degraded"
    assert body["requested_provider"] == "custom-deskbox"
    assert body["requested_model"] == "desk-llama-70b"


@pytest.mark.asyncio
async def test_models_listing_includes_custom_models(auth, custom_config):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    by_id = {entry["id"]: entry for entry in response.json()["data"]}
    assert by_id["desk-llama-70b"]["owned_by"] == "custom:deskbox"
    assert by_id["agg/auto"]["owned_by"] == "custom:aggregator"
    assert "auto" in by_id
