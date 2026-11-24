"""TASK-INF-030: APInex gateway fallback wiring.

Pins: provider registration + config keys, verified-only free-model
selection (subscription-gated ``free/*`` ids must never be chosen), the
module-level discovery cache, waterfall placement (last cloud rung, after
gemini), gateway failover actually reaching apinex when groq/openrouter/
gemini are down, the runtime-registry rung, and key-inventory coverage.
No network, no live keys.
"""

import asyncio
import os
import time

# The app lifespan builds an httpx client that reads proxy environment
# variables; some sandboxes export values this httpx version cannot parse.
# These tests are fully in-process, so proxying is never needed here.
for _v in (
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
):
    os.environ.pop(_v, None)

import pytest

import app.providers
import app.providers.apinex as apinex_module
import app.providers.gateway as gateway_module
from app.core.config import settings
from app.core.policies import (
    DETERMINISTIC_WATERFALL_ORDER,
    PROVIDER_FALLBACK_MATRIX,
    ProviderSwitchingPolicy,
)
from app.providers.apinex import ApinexProvider
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.errors import TemporaryUnavailableError
from app.providers.gateway import KeyPool, ModelGateway

# Live catalogue shape from the Server 2 probe, 2026-11-24: 22 free/* ids,
# including two that answer only with a subscription (402). The discovery
# cache must return the whole listed set (that is the catalogue); selection
# must never pick the gated ones.
CATALOGUE = {
    "data": [
        {"id": "free/qwen-3.8-max"},
        {"id": "free/gpt-6-luna"},
        {"id": "free/deepseek-v4.1-flash"},
        {"id": "free/gemini-3.8-flash"},
        {"id": "free/glm-5.3"},
        {"id": "free/claude-sonnet-4.6"},
        {"id": "gpt-6.1-sol"},
        {"id": "claude-opus-5.5"},
    ]
}
EXPECTED_FREE = [
    "free/qwen-3.8-max",
    "free/gpt-6-luna",
    "free/deepseek-v4.1-flash",
    "free/gemini-3.8-flash",
    "free/glm-5.3",
    "free/claude-sonnet-4.6",
]
# Ids verified answering live (200, cost_tokens 0) on 2026-11-24.
VERIFIED = ["free/qwen-3.8-max", "free/gpt-6-luna", "free/deepseek-v4.1-flash"]
# Listed as free/ but subscription-gated at completion time (HTTP 402).
GATED = ["free/gemini-3.8-flash", "free/glm-5.3"]


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else CATALOGUE

    def json(self):
        return self._payload


class _FakeClient:
    """Counts GETs; records the last POST (url/headers/payload)."""

    def __init__(self, *, status_code=200, fail=False):
        self.calls = 0
        self.status_code = status_code
        self.fail = fail
        self.last_post = None

    async def get(self, url, headers=None, timeout=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated network failure")
        return _FakeResponse(status_code=self.status_code)

    async def post(self, url, headers=None, json=None, timeout=None):
        self.last_post = {"url": url, "headers": dict(headers or {}), "json": json}
        return _FakeResponse(
            payload={
                "choices": [
                    {
                        "message": {"content": "OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            }
        )


@pytest.fixture(autouse=True)
def _clean_discovery_cache():
    apinex_module._DISCOVERY_CACHE.clear()
    yield
    apinex_module._DISCOVERY_CACHE.clear()


def _install_client(monkeypatch, client):
    async def _get_shared_client():
        return client

    monkeypatch.setattr(apinex_module, "get_shared_client", _get_shared_client)


def _provider():
    return ApinexProvider(api_key="test-key")


# ---------------------------------------------------------------------------
# Registration + configuration
# ---------------------------------------------------------------------------


def test_apinex_registered_in_provider_map():
    from app.providers import _PROVIDER_MAP, get_provider

    assert _PROVIDER_MAP["apinex"] is ApinexProvider
    assert isinstance(get_provider("apinex", api_key="test-key"), ApinexProvider)


def test_apinex_base_url_and_default_model():
    assert ApinexProvider.BASE_URL == "https://api.apinex.bond/v1"
    assert ApinexProvider.DEFAULT_MODEL == "free/qwen-3.8-max"
    assert ApinexProvider.SUPPORTED_MODELS == VERIFIED
    assert all(m.startswith("free/") for m in ApinexProvider.SUPPORTED_MODELS)
    assert not any(m in ApinexProvider.SUPPORTED_MODELS for m in GATED)


def test_apinex_config_keys(monkeypatch):
    monkeypatch.setattr(settings, "APINEX_API_KEY", "sk-apx-test-key-1")
    monkeypatch.setattr(settings, "APINEX_API_KEYS", None)
    assert settings.get_provider_keys("apinex") == ["sk-apx-test-key-1"]

    monkeypatch.setattr(settings, "APINEX_API_KEY", None)
    monkeypatch.setattr(settings, "APINEX_API_KEYS", "sk-apx-test-key-2, sk-apx-test-key-3")
    assert settings.get_provider_keys("apinex") == ["sk-apx-test-key-2", "sk-apx-test-key-3"]


def test_apinex_listed_by_validate_environment(monkeypatch):
    monkeypatch.setattr(settings, "APINEX_API_KEY", "sk-apx-test-key-1")
    monkeypatch.setattr(settings, "APINEX_API_KEYS", None)
    assert "apinex" in settings.validate_environment()["configured_providers"]


def test_apinex_key_inventory_counts(monkeypatch):
    from app.core import key_inventory

    assert "APINEX" in key_inventory.PROVIDERS

    class _ExampleSettings:
        def get_provider_keys(self, provider):
            return {"APINEX": ["k1"]}.get(provider, [])

    assert key_inventory.provider_key_counts(_ExampleSettings())["APINEX"] == 1


# ---------------------------------------------------------------------------
# Adapter wire contract (fake transport, no network)
# ---------------------------------------------------------------------------


async def test_generate_posts_chat_completions_with_bearer(monkeypatch):
    import app.providers.openai_compatible as oc_module

    client = _FakeClient()

    async def _get_client():
        return client

    monkeypatch.setattr(oc_module, "get_shared_client", _get_client)

    req = ProviderRequest(
        messages=[ProviderMessage(role="user", content="Reply with the single word OK.")],
        model="free/qwen-3.8-max",
        max_tokens=16,
    )
    resp = await _provider().generate(req)

    assert resp.content == "OK"
    assert resp.provider == "apinex"
    assert resp.model == "free/qwen-3.8-max"
    post = client.last_post
    assert post["url"] == "https://api.apinex.bond/v1/chat/completions"
    assert post["headers"]["Authorization"] == "Bearer test-key"
    assert post["json"]["model"] == "free/qwen-3.8-max"
    assert post["json"]["messages"] == [{"role": "user", "content": "Reply with the single word OK."}]


# ---------------------------------------------------------------------------
# Free-model discovery cache (TASK-INF-004 pattern)
# ---------------------------------------------------------------------------


async def test_discovery_cache_shared_across_instances(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    first = await _provider().fetch_available_free_models()
    second = await _provider().fetch_available_free_models()
    third = await _provider().fetch_available_free_models()

    assert first == EXPECTED_FREE
    assert second == EXPECTED_FREE
    assert third == EXPECTED_FREE
    assert client.calls == 1


async def test_discovery_cache_ttl_expiry_refetches(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    await _provider().fetch_available_free_models()
    assert client.calls == 1

    base_url = _provider().base_url
    models, _ts = apinex_module._DISCOVERY_CACHE[base_url]
    apinex_module._DISCOVERY_CACHE[base_url] = (
        models,
        time.time() - apinex_module._DISCOVERY_CACHE_TTL_SECONDS - 1.0,
    )
    again = await _provider().fetch_available_free_models()
    assert again == EXPECTED_FREE
    assert client.calls == 2


async def test_discovery_failure_is_not_cached(monkeypatch):
    client = _FakeClient(fail=True)
    _install_client(monkeypatch, client)

    result = await _provider().fetch_available_free_models()
    assert result == list(ApinexProvider.SUPPORTED_MODELS)
    assert apinex_module._DISCOVERY_CACHE == {}

    client.fail = False
    result = await _provider().fetch_available_free_models()
    assert result == EXPECTED_FREE
    assert client.calls == 2
    await _provider().fetch_available_free_models()
    assert client.calls == 2


async def test_discovery_non_200_is_not_cached(monkeypatch):
    client = _FakeClient(status_code=503)
    _install_client(monkeypatch, client)

    result = await _provider().fetch_available_free_models()
    assert result == list(ApinexProvider.SUPPORTED_MODELS)
    assert apinex_module._DISCOVERY_CACHE == {}
    await _provider().fetch_available_free_models()
    assert client.calls == 2


async def test_keyless_provider_never_fetches(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    provider = _provider()
    provider.api_keys = []  # simulate an unconfigured deployment
    result = await provider.fetch_available_free_models()
    assert result == list(ApinexProvider.SUPPORTED_MODELS)
    assert client.calls == 0
    assert apinex_module._DISCOVERY_CACHE == {}


# ---------------------------------------------------------------------------
# Capability selection: verified-first, gated ids never chosen
# ---------------------------------------------------------------------------


async def test_capability_selection_prefers_verified_models(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    assert await _provider().find_model_by_capability("general") == "free/qwen-3.8-max"
    assert await _provider().find_model_by_capability("reasoning") == "free/deepseek-v4.1-flash"
    assert await _provider().find_model_by_capability("coding") == "free/qwen-3.8-max"
    assert await _provider().find_model_by_capability("research") == "free/qwen-3.8-max"


async def test_capability_selection_never_picks_gated_models(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    # The discovered catalogue lists the gated ids; selection must still
    # return a verified id for every capability, never a 402-at-completion id.
    for capability in ("general", "coding", "reasoning", "research", "analysis", "security"):
        chosen = await _provider().find_model_by_capability(capability)
        assert chosen not in GATED, capability
        assert chosen in VERIFIED, capability


# ---------------------------------------------------------------------------
# Waterfall placement: last cloud rung, after gemini
# ---------------------------------------------------------------------------


def test_waterfall_order_ends_with_apinex():
    names = [p for p, _ in DETERMINISTIC_WATERFALL_ORDER]
    assert names == ["groq", "openrouter", "gemini", "apinex"]
    assert DETERMINISTIC_WATERFALL_ORDER[-1] == ("apinex", "free/qwen-3.8-max")


def test_waterfall_sequence_cycles_through_apinex():
    assert [p for p, _ in ProviderSwitchingPolicy.get_waterfall_sequence("gemini")] == [
        "apinex",
        "groq",
        "openrouter",
    ]
    assert [p for p, _ in ProviderSwitchingPolicy.get_waterfall_sequence("groq")] == [
        "openrouter",
        "gemini",
        "apinex",
    ]
    assert [p for p, _ in ProviderSwitchingPolicy.get_waterfall_sequence("openrouter")] == [
        "gemini",
        "apinex",
        "groq",
    ]


def test_fallback_matrix_has_apinex_route():
    route = PROVIDER_FALLBACK_MATRIX["apinex"]
    assert route.primary_provider == "apinex"
    assert route.fallback_provider == "groq"
    assert route.fallback_model == "openai/gpt-oss-120b"


def test_gateway_pools_include_apinex(monkeypatch):
    monkeypatch.setattr(
        type(settings),
        "get_provider_keys",
        lambda self, name: ["apinex-key"] if name == "apinex" else [],
    )
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)

    gateway = ModelGateway.__new__(ModelGateway)
    # House pattern (test_inf008 / test_rel047): __new__ skips __init__,
    # so the pools dicts must exist before _initialize_pools() fills them.
    gateway.key_pools = {}
    gateway.rate_limiters = {}
    gateway._initialize_pools()

    assert "apinex" in gateway.key_pools
    assert gateway.key_pools["apinex"].total_keys_count == 1
    assert "apinex" in gateway.rate_limiters


def test_runtime_registry_waterfall_includes_apinex():
    from app.inference_runtime.model_registry import ModelRegistry

    registry = ModelRegistry()
    rec = registry.resolve("free/qwen-3.8-max", "apinex")
    assert rec is not None
    assert rec.endpoint.provider == "apinex"

    seq = registry.get_waterfall_sequence()
    assert [r.endpoint.provider for r in seq] == ["groq", "openrouter", "gemini", "apinex"]

    fb = registry.resolve_fallback("gemini", "gemini-flash-latest")
    assert fb is not None
    assert fb.endpoint.provider == "apinex"


# ---------------------------------------------------------------------------
# Gateway failover: the ladder reaches apinex (drill harness, no network)
# ---------------------------------------------------------------------------

PROVIDERS = ["gemini", "groq", "cerebras", "mistral", "openrouter", "cohere", "huggingface", "nvidia", "apinex"]


class _Limiter:
    async def acquire(self, cost=1.0):
        return None

    def release(self):
        return None


class _Health:
    def __init__(self):
        self.successes = []
        self.failures = []

    def record_success(self, provider, latency, **kwargs):
        self.successes.append(provider)

    def record_failure(self, provider, error, **kwargs):
        self.failures.append((provider, str(error)))

    def update_key_counts(self, *args, **kwargs):
        return None


class _FakeProvider:
    """Scripted provider. Behaviours: ok, e503, e429, empty."""

    def __init__(self, name, behaviour="ok"):
        self.name = name
        self.behaviour = behaviour

    async def get_best_free_model(self, capability="general"):
        return "test/free-model"

    async def generate(self, request):
        if self.behaviour == "ok":
            return ProviderResponse(
                content=f"answer:{self.name}", model=request.model or "m",
                provider=self.name, raw_response={},
            )
        if self.behaviour == "empty":
            return ProviderResponse(
                content="", model=request.model or "m", provider=self.name,
                finish_reason="empty", raw_response={},
            )
        if self.behaviour == "e503":
            raise RuntimeError("503 Service Unavailable: provider overloaded")
        if self.behaviour == "e429":
            raise RuntimeError("429 Too Many Requests: quota exceeded for this key")
        raise AssertionError(self.behaviour)


def _gateway(monkeypatch, script):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {p: KeyPool(p, [f"{p}-key-1", f"{p}-key-2"]) for p in PROVIDERS}
    gateway.rate_limiters = {p: _Limiter() for p in PROVIDERS}
    gateway.health_tracker = _Health()

    def get_provider(name, **kwargs):
        return _FakeProvider(name, script.get(name, "ok"))

    monkeypatch.setattr(app.providers, "get_provider", get_provider)
    monkeypatch.setattr(gateway_module, "provider_has_credentials", lambda prov: True)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(gateway_module.settings, "INFERENCE_LITELLM_FALLBACK_ENABLED", False)
    return gateway


def _request(timeout=10.0):
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content="drill question")],
        model="drill-model",
        extra_params={"timeout": timeout},
    )


def test_ladder_serves_via_apinex_when_trio_is_down(monkeypatch):
    """TASK-INF-030: with groq/openrouter/gemini down, the request must be
    served by the APInex rung — not raise, and not touch second-tier
    providers that the waterfall never reaches."""
    script = {p: "ok" for p in PROVIDERS}
    for p in ("groq", "openrouter", "gemini"):
        script[p] = "e503"
    gateway = _gateway(monkeypatch, script)
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.provider == "apinex"
    assert resp.content == "answer:apinex"
    provenance = (resp.raw_response or {}).get("fallback_provenance") or {}
    assert provenance.get("actual_provider") == "apinex"
    assert provenance.get("actual_model") == "free/qwen-3.8-max"


def test_ladder_raises_when_quartet_is_down(monkeypatch):
    """New boundary (TASK-INF-030): the typed error now requires the
    quartet — groq, openrouter, gemini AND apinex — to be down."""
    script = {p: "ok" for p in PROVIDERS}
    for p in ("groq", "openrouter", "gemini", "apinex"):
        script[p] = "e503"
    gateway = _gateway(monkeypatch, script)
    with pytest.raises(TemporaryUnavailableError):
        asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))
