"""TASK-INF-004: OpenRouter free-model discovery cache must survive provider
instance churn.

Production measurement behind this suite (2026-11-15): the gateway builds a
fresh ``OpenRouterProvider`` for every fallback attempt
(``get_provider(name, api_key=...)`` is never memoised), so the previous
instance-level discovery cache could never hit — every fallback
re-downloaded the ~851KB /api/v1/models catalogue (0.59–1.10s from
Server 1) before its completion call. The cache now lives at module level;
these tests pin that behaviour with a counting fake transport. No network.
"""

import asyncio
import time

import pytest

import app.providers.openrouter as openrouter_module
from app.providers.openrouter import OpenRouterProvider

CATALOGUE = {
    "data": [
        {"id": "nvidia/nemotron-3.5-lightning:free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "qwen/qwen-2.5-coder-32b-instruct", "pricing": {"prompt": "0.0000001", "completion": "0.0000002"}},
        {"id": "some/zero-priced-model", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "paid/model-x", "pricing": {"prompt": "0.001", "completion": "0.002"}},
    ]
}
EXPECTED_FREE = ["nvidia/nemotron-3.5-lightning:free", "some/zero-priced-model"]


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else CATALOGUE

    def json(self):
        return self._payload


class _FakeClient:
    """Counts GETs; can sleep (to expose stampedes) or fail."""

    def __init__(self, *, status_code=200, delay=0.0, fail=False):
        self.calls = 0
        self.status_code = status_code
        self.delay = delay
        self.fail = fail

    async def get(self, url, headers=None, timeout=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("simulated network failure")
        return _FakeResponse(status_code=self.status_code)


@pytest.fixture(autouse=True)
def _clean_discovery_cache():
    openrouter_module._DISCOVERY_CACHE.clear()
    yield
    openrouter_module._DISCOVERY_CACHE.clear()


def _install_client(monkeypatch, client):
    async def _get_shared_client():
        return client

    monkeypatch.setattr(openrouter_module, "get_shared_client", _get_shared_client)


def _provider():
    # A fresh instance per call — exactly how the gateway obtains one.
    return OpenRouterProvider(api_key="test-key")


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

    # Age the shared entry beyond the TTL: the next fresh instance refetches.
    base_url = _provider().base_url
    models, _ts = openrouter_module._DISCOVERY_CACHE[base_url]
    openrouter_module._DISCOVERY_CACHE[base_url] = (
        models,
        time.time() - openrouter_module._DISCOVERY_CACHE_TTL_SECONDS - 1.0,
    )
    again = await _provider().fetch_available_free_models()
    assert again == EXPECTED_FREE
    assert client.calls == 2


async def test_discovery_failure_is_not_cached(monkeypatch):
    client = _FakeClient(fail=True)
    _install_client(monkeypatch, client)

    result = await _provider().fetch_available_free_models()
    assert result == list(OpenRouterProvider.SUPPORTED_MODELS)
    assert openrouter_module._DISCOVERY_CACHE == {}

    # A later success must be attempted (failure was not cached) and then cached.
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
    assert result == list(OpenRouterProvider.SUPPORTED_MODELS)
    assert openrouter_module._DISCOVERY_CACHE == {}
    await _provider().fetch_available_free_models()
    assert client.calls == 2


async def test_concurrent_fallbacks_fetch_once(monkeypatch):
    client = _FakeClient(delay=0.2)
    _install_client(monkeypatch, client)

    results = await asyncio.gather(
        *[_provider().fetch_available_free_models() for _ in range(5)]
    )
    assert all(r == EXPECTED_FREE for r in results)
    assert client.calls == 1


async def test_discovery_cache_keyed_by_base_url(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    await _provider().fetch_available_free_models()
    other = _provider()
    other.base_url = "https://example.invalid/api/v1"
    await other.fetch_available_free_models()
    assert client.calls == 2


async def test_keyless_provider_never_fetches(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    provider = _provider()
    provider.api_keys = []  # simulate an unconfigured deployment
    result = await provider.fetch_available_free_models()
    assert result == list(OpenRouterProvider.SUPPORTED_MODELS)
    assert client.calls == 0
    assert openrouter_module._DISCOVERY_CACHE == {}


async def test_capability_selection_unchanged_with_shared_cache(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)

    cold = await _provider().find_model_by_capability("general")
    warm = await _provider().find_model_by_capability("general")
    assert cold == warm == "nvidia/nemotron-3.5-lightning:free"
    assert client.calls == 1
