"""TASK-INF-039: Bytez free-tier guardrails for Inference.

Pins the three guards the TASK-IG2-INF-01 adapter left unenforced at the
call site, each a way to silently burn the $0 tier or misrecord what
happened:

* the $0 tier allows 1 concurrent request, but the gateway caps Bytez at
  4 and the adapter had no guard — the single-slot semaphore serialises
  Bytez calls and fails fast to the ladder when the slot is busy;
* Bytez is an aggregator, so the model that answers may not be the model
  asked for — the served-model id is verified and the verdict recorded
  in ``raw_response["bytez"]`` (the INF-005 serve-check, at runtime);
* the allowlist is only <=7B open models, but nothing stopped a caller
  asking for a larger, credit-metered model — unlisted models are refused
  before any HTTP call and before the slot is taken.

No network, no live keys. HTTP is a fake client installed in place of
``get_shared_client`` (the pattern from test_inf030_apinex_fallback.py).
"""

import asyncio
import logging
import os

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
import app.providers.gateway as gateway_module
from app.core.config import settings
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.bytez import BYTEZ_DEFAULT_MODEL, BYTEZ_SUPPORTED_MODELS, BytezProvider
from app.providers.bytez_guard import (
    BytezModelNotAllowedError,
    BytezSlotBusyError,
    acquire_bytez_slot,
    annotate_bytez_response,
    slot_wait_seconds,
    validate_bytez_model,
    verify_served_model,
)
from app.providers.gateway import KeyPool, ModelGateway

UNLISTED_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",  # >7B: credit-metered, must never be reachable
    "meta-llama/Llama-3.1-405B-Instruct",
    "nvidia/gpt-oss-120b",  # free elsewhere (NVIDIA rung), not a Bytez $0 model
]


# ---------------------------------------------------------------------------
# Fake HTTP layer (no network)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _chat_payload(model="Qwen/Qwen2.5-7B-Instruct", content="ok"):
    return {
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    }


class _FakeStreamResponse:
    """Minimal stand-in for httpx's streaming response (async CM)."""

    def __init__(self, lines, status_code=200):
        self.status_code = status_code
        self._lines = list(lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    """Records posts/streams; the post handler may block on an event."""

    def __init__(self, post=None, stream_lines=None):
        self.calls = []
        self._post = post
        self._stream_lines = stream_lines

    async def post(self, url, headers=None, json=None, timeout=None):
        call = {"url": url, "headers": dict(headers or {}), "json": json}
        self.calls.append(call)
        if self._post is not None:
            return await self._post(call)
        return _FakeResponse(200, _chat_payload())

    def stream(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers or {}), "json": json}
        )
        return _FakeStreamResponse(self._stream_lines or [])


def _install_client(monkeypatch, client):
    async def _get_shared_client():
        return client

    monkeypatch.setattr(
        "app.providers.openai_compatible.get_shared_client", _get_shared_client
    )


def _request(model=BYTEZ_DEFAULT_MODEL):
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content="Reply with the single word: ok")],
        model=model,
        max_tokens=8,
        temperature=0.0,
    )


# ---------------------------------------------------------------------------
# Slot wait configuration
# ---------------------------------------------------------------------------


def test_slot_wait_seconds_default(monkeypatch):
    monkeypatch.delenv("BYTEZ_SLOT_WAIT_SECONDS", raising=False)
    assert slot_wait_seconds() == 5.0


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", 0.0),
        ("2.5", 2.5),
        (" 10 ", 10.0),
        ("", 5.0),
        ("abc", 5.0),
        ("-1", 5.0),
    ],
)
def test_slot_wait_seconds_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("BYTEZ_SLOT_WAIT_SECONDS", value)
    assert slot_wait_seconds() == expected


# ---------------------------------------------------------------------------
# Model allowlist (FREE-only: no credit-metered model through the rung)
# ---------------------------------------------------------------------------


def test_validate_model_defaults_to_default_model():
    assert (
        validate_bytez_model(None, BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL)
        == BYTEZ_DEFAULT_MODEL
    )
    assert (
        validate_bytez_model("  ", BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL)
        == BYTEZ_DEFAULT_MODEL
    )


@pytest.mark.parametrize("model", BYTEZ_SUPPORTED_MODELS)
def test_validate_model_accepts_every_allowlisted_model(model):
    assert validate_bytez_model(model, BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL) == model


@pytest.mark.parametrize("model", UNLISTED_MODELS)
def test_validate_model_rejects_unlisted_model(model):
    with pytest.raises(BytezModelNotAllowedError, match="not in the free-tier allowlist"):
        validate_bytez_model(model, BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL)


def test_validate_model_rejection_is_a_value_error():
    """A ValueError, so the gateway normalises it into a non-retryable
    error (no key quarantine, no same-provider retry) and escalates to
    the ladder instead of failing the request."""
    with pytest.raises(ValueError, match="Qwen/Qwen2.5-72B-Instruct"):
        validate_bytez_model(
            "Qwen/Qwen2.5-72B-Instruct", BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL
        )


def test_supported_models_still_free_tier_only():
    """Pin: the allowlist is exactly the four <=7B open models. Adding a
    larger model here is a billing decision, not a code tweak, and must
    come with probe evidence — never silently."""
    assert BYTEZ_SUPPORTED_MODELS == [
        "Qwen/Qwen2.5-7B-Instruct",
        "Qwen/Qwen3-4B",
        "meta-llama/Llama-3.2-3B-Instruct",
        "microsoft/Phi-3-mini-4k-instruct",
    ]
    assert BYTEZ_DEFAULT_MODEL in BYTEZ_SUPPORTED_MODELS


# ---------------------------------------------------------------------------
# Served-model verification (INF-005 serve-check, at runtime)
# ---------------------------------------------------------------------------


def test_verify_served_model_match():
    verdict = verify_served_model("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct")
    assert verdict.outcome == "match"
    assert verdict.requested == verdict.served == "Qwen/Qwen2.5-7B-Instruct"


def test_verify_served_model_mismatch():
    verdict = verify_served_model("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen3-4B")
    assert verdict.outcome == "mismatch"
    assert "Qwen/Qwen3-4B" in verdict.detail
    assert "Qwen/Qwen2.5-7B-Instruct" in verdict.detail


@pytest.mark.parametrize("served", [None, ""])
def test_verify_served_model_unknown_when_served_missing(served):
    verdict = verify_served_model("Qwen/Qwen2.5-7B-Instruct", served)
    assert verdict.outcome == "unknown"
    assert "unverified" in verdict.detail


def test_verify_served_model_unknown_when_requested_missing():
    verdict = verify_served_model(None, "Qwen/Qwen2.5-7B-Instruct")
    assert verdict.outcome == "unknown"


def test_verify_served_model_is_case_sensitive():
    """Model ids are canonical Hugging Face ids: a case difference is a
    different model, not a formatting quirk."""
    verdict = verify_served_model("Qwen/Qwen2.5-7B-Instruct", "qwen/qwen2.5-7b-instruct")
    assert verdict.outcome == "mismatch"


def test_annotate_records_match_block():
    resp = ProviderResponse(content="ok", model="Qwen/Qwen2.5-7B-Instruct", provider="bytez")
    out = annotate_bytez_response(
        resp, verify_served_model("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct")
    )
    assert out is resp
    block = (resp.raw_response or {}).get("bytez") or {}
    assert block["requested_model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert block["served_model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert block["served_model_match"] is True
    assert block["served_model_outcome"] == "match"


def test_annotate_mismatch_keeps_requested_model(caplog):
    """The response content is returned as-is, but resp.model keeps the
    requested id: gateway quota accounting stays keyed on what was asked
    for, and the annotation — not a silent substitution — carries the
    truth."""
    resp = ProviderResponse(content="ok", model="Qwen/Qwen2.5-7B-Instruct", provider="bytez")
    with caplog.at_level(logging.WARNING):
        annotate_bytez_response(
            resp, verify_served_model("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen3-4B")
        )
    assert resp.model == "Qwen/Qwen2.5-7B-Instruct"
    block = (resp.raw_response or {}).get("bytez") or {}
    assert block["served_model_match"] is False
    assert block["served_model_outcome"] == "mismatch"
    assert "served" in caplog.text and "Qwen/Qwen3-4B" in caplog.text


def test_annotate_unknown_warns(caplog):
    resp = ProviderResponse(content="ok", model="Qwen/Qwen2.5-7B-Instruct", provider="bytez")
    with caplog.at_level(logging.WARNING):
        annotate_bytez_response(resp, verify_served_model("Qwen/Qwen2.5-7B-Instruct", None))
    assert (resp.raw_response or {}).get("bytez", {}).get("served_model_outcome") == "unknown"
    assert "unverified" in caplog.text


def test_annotate_creates_raw_response_when_missing():
    resp = ProviderResponse(
        content="ok", model="Qwen/Qwen2.5-7B-Instruct", provider="bytez", raw_response=None
    )
    annotate_bytez_response(
        resp, verify_served_model("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct")
    )
    assert isinstance(resp.raw_response, dict)
    assert resp.raw_response["bytez"]["served_model_match"] is True


# ---------------------------------------------------------------------------
# Concurrency-1 slot
# ---------------------------------------------------------------------------


async def test_slot_sequential_acquire_release():
    async with acquire_bytez_slot(wait_seconds=1.0):
        pass
    async with acquire_bytez_slot(wait_seconds=1.0):
        pass


async def test_slot_contention_times_out():
    """Holding the slot makes a second caller fail fast with a
    TimeoutError (which the gateway takes through its timeout branch to
    the ladder) instead of queueing behind the tier's one request."""
    async with acquire_bytez_slot(wait_seconds=1.0):
        with pytest.raises(BytezSlotBusyError, match="timed out"):
            async with acquire_bytez_slot(wait_seconds=0.05):
                pass


async def test_slot_busy_error_is_a_timeout_error():
    assert issubclass(BytezSlotBusyError, TimeoutError)


async def test_slot_released_after_exception_inside_context():
    with pytest.raises(RuntimeError, match="boom"):
        async with acquire_bytez_slot(wait_seconds=1.0):
            raise RuntimeError("boom")
    # The slot must be free again for the next caller.
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass


def test_slot_survives_across_event_loops():
    """The slot is keyed by running loop: a semaphore bound to a dead
    loop must be replaced, not reused (each pytest-asyncio case runs on
    its own loop, and the gateway rebuilds its loop on restart)."""

    async def _hold_and_release():
        async with acquire_bytez_slot(wait_seconds=1.0):
            return True

    assert asyncio.run(_hold_and_release()) is True
    assert asyncio.run(_hold_and_release()) is True


# ---------------------------------------------------------------------------
# Provider generate() under the guardrails (fake HTTP)
# ---------------------------------------------------------------------------


async def test_generate_success_match(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)
    resp = await BytezProvider(api_key="test-key").generate(_request())
    assert resp.content == "ok"
    assert resp.provider == "bytez"
    assert resp.model == "Qwen/Qwen2.5-7B-Instruct"
    assert resp.finish_reason == "stop"
    block = (resp.raw_response or {}).get("bytez") or {}
    assert block["served_model_match"] is True
    assert block["served_model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert len(client.calls) == 1
    assert client.calls[0]["json"]["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert client.calls[0]["url"] == "https://api.bytez.com/models/v2/openai/v1/chat/completions"


async def test_generate_success_mismatch_annotated_and_warned(monkeypatch, caplog):
    async def _post(call):
        return _FakeResponse(200, _chat_payload(model="Qwen/Qwen3-4B", content="substituted"))

    _install_client(monkeypatch, _FakeClient(post=_post))
    with caplog.at_level(logging.WARNING):
        resp = await BytezProvider(api_key="test-key").generate(_request())
    assert resp.content == "substituted"  # content is returned as-is
    assert resp.model == "Qwen/Qwen2.5-7B-Instruct"  # accounting keeps the request
    block = (resp.raw_response or {}).get("bytez") or {}
    assert block["served_model"] == "Qwen/Qwen3-4B"
    assert block["served_model_match"] is False
    assert "Qwen/Qwen3-4B" in caplog.text


async def test_generate_success_unknown_when_served_id_absent(monkeypatch, caplog):
    payload = _chat_payload()
    del payload["model"]

    async def _post(call):
        return _FakeResponse(200, payload)

    _install_client(monkeypatch, _FakeClient(post=_post))
    with caplog.at_level(logging.WARNING):
        resp = await BytezProvider(api_key="test-key").generate(_request())
    assert resp.content == "ok"
    assert (resp.raw_response or {}).get("bytez", {}).get("served_model_outcome") == "unknown"
    assert "unverified" in caplog.text


@pytest.mark.parametrize("model", UNLISTED_MODELS)
async def test_generate_rejects_unlisted_model_without_http(monkeypatch, model):
    client = _FakeClient()
    _install_client(monkeypatch, client)
    with pytest.raises(BytezModelNotAllowedError):
        await BytezProvider(api_key="test-key").generate(_request(model=model))
    assert client.calls == []  # refused before any call — and before the slot


async def test_generate_defaults_model_when_request_has_none(monkeypatch):
    client = _FakeClient()
    _install_client(monkeypatch, client)
    resp = await BytezProvider(api_key="test-key").generate(_request(model=None))
    assert resp.content == "ok"
    assert client.calls[0]["json"]["model"] == BYTEZ_DEFAULT_MODEL


async def test_generate_holds_slot_during_call(monkeypatch):
    """While one generate() is in flight, a second caller cannot take
    the slot — the $0 tier's one-request rule, enforced in-process."""
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _post(call):
        entered.set()
        await release.wait()
        return _FakeResponse(200, _chat_payload())

    _install_client(monkeypatch, _FakeClient(post=_post))
    provider = BytezProvider(api_key="test-key")
    task = asyncio.create_task(provider.generate(_request()))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        with pytest.raises(BytezSlotBusyError):
            async with acquire_bytez_slot(wait_seconds=0.05):
                pass
    finally:
        release.set()
    resp = await task
    assert resp.content == "ok"
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass  # slot free again after the call


@pytest.mark.parametrize("status", [500, 429])
async def test_generate_releases_slot_after_http_error(monkeypatch, status):
    async def _post(call):
        return _FakeResponse(status, {}, text="boom")

    _install_client(monkeypatch, _FakeClient(post=_post))
    provider = BytezProvider(api_key="test-key")
    with pytest.raises(RuntimeError):
        await provider.generate(_request())
    # The slot must be free for the next caller despite the failure.
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass


async def test_generate_missing_key_never_takes_slot(monkeypatch):
    monkeypatch.delenv("BYTEZ_API_KEYS", raising=False)
    monkeypatch.delenv("BYTEZ_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BYTEZ_API_KEY", None, raising=False)
    client = _FakeClient()
    _install_client(monkeypatch, client)
    with pytest.raises(ValueError, match="not configured"):
        await BytezProvider(api_key=None).generate(_request())
    assert client.calls == []
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass  # refused before the slot, so it was never held


# ---------------------------------------------------------------------------
# Provider stream() under the guardrails (fake SSE)
# ---------------------------------------------------------------------------

_SSE_LINES = [
    'data: {"choices": [{"delta": {"content": "hel"}}]}',
    'data: {"choices": [{"delta": {"content": "lo"}}]}',
    "data: [DONE]",
]


async def test_stream_yields_chunks_and_holds_slot(monkeypatch):
    _install_client(monkeypatch, _FakeClient(stream_lines=_SSE_LINES))
    provider = BytezProvider(api_key="test-key")
    gen = provider.stream(_request())
    assert await gen.__anext__() == "hel"
    # The slot is held for the whole stream, not just the first chunk.
    with pytest.raises(BytezSlotBusyError):
        async with acquire_bytez_slot(wait_seconds=0.05):
            pass
    rest = [chunk async for chunk in gen]
    assert rest == ["lo"]
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass  # released after exhaustion


async def test_stream_rejects_unlisted_model_without_http(monkeypatch):
    client = _FakeClient(stream_lines=_SSE_LINES)
    _install_client(monkeypatch, client)
    provider = BytezProvider(api_key="test-key")
    with pytest.raises(BytezModelNotAllowedError):
        async for _ in provider.stream(_request(model="Qwen/Qwen2.5-72B-Instruct")):
            pass
    assert client.calls == []


async def test_stream_releases_slot_when_consumer_closes_early(monkeypatch):
    _install_client(monkeypatch, _FakeClient(stream_lines=_SSE_LINES))
    provider = BytezProvider(api_key="test-key")
    gen = provider.stream(_request())
    assert await gen.__anext__() == "hel"
    await gen.aclose()
    async with acquire_bytez_slot(wait_seconds=0.05):
        pass  # early close releases the slot


# ---------------------------------------------------------------------------
# Gateway integration: the rung gate (off by default) still governs
# ---------------------------------------------------------------------------

PROVIDERS = [
    "gemini", "groq", "cerebras", "mistral", "openrouter", "cohere",
    "huggingface", "nvidia", "bytez", "apinex",
]


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
    """Scripted provider; records every generate() call."""

    def __init__(self, name, behaviour="ok"):
        self.name = name
        self.behaviour = behaviour
        self.calls = []

    async def get_best_free_model(self, capability="general"):
        return "test/free-model"

    async def generate(self, request):
        self.calls.append(request)
        if self.behaviour == "ok":
            return ProviderResponse(
                content=f"answer:{self.name}", model=request.model or "m",
                provider=self.name, raw_response={},
            )
        raise AssertionError(self.behaviour)


def _gateway(monkeypatch, script):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {p: KeyPool(p, [f"{p}-key-1", f"{p}-key-2"]) for p in PROVIDERS}
    gateway.rate_limiters = {p: _Limiter() for p in PROVIDERS}
    gateway.health_tracker = _Health()
    created = []

    def get_provider(name, **kwargs):
        provider = _FakeProvider(name, script.get(name, "ok"))
        created.append(provider)
        return provider

    monkeypatch.setattr(app.providers, "get_provider", get_provider)
    monkeypatch.setattr(gateway_module, "provider_has_credentials", lambda prov: True)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(
        gateway_module.settings, "INFERENCE_LITELLM_FALLBACK_ENABLED", False
    )
    return gateway, created


def _gateway_request():
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content="drill question")],
        model="drill-model",
        extra_params={"timeout": 10.0},
    )


def test_gateway_bytez_rung_disabled_falls_through(monkeypatch):
    """Rung off (the default): a bytez-primary request is served by
    another rung and the bytez provider is never even constructed."""
    monkeypatch.delenv("INFERENCE_BYTEZ_RUNG_ENABLED", raising=False)
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("bytez", _gateway_request()))
    assert resp.provider != "bytez"
    assert resp.content == f"answer:{resp.provider}"
    assert [p for p in created if p.name == "bytez"] == []


def test_gateway_bytez_rung_enabled_serves_directly(monkeypatch):
    """Rung on: the bytez primary serves, and the guardrails live in the
    real provider (not the fake one) — see the generate() tests above."""
    monkeypatch.setenv("INFERENCE_BYTEZ_RUNG_ENABLED", "true")
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("bytez", _gateway_request()))
    assert resp.provider == "bytez"
    assert resp.content == "answer:bytez"
