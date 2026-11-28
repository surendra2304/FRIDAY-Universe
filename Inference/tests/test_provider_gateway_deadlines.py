from __future__ import annotations

import asyncio
import math
import time

import pytest

import app.providers
from app.core.config import Settings, settings
from app.providers.base import ProviderMessage, ProviderRequest
from app.providers.gateway import KeyPool, ModelGateway, ProviderRateLimiter


@pytest.mark.parametrize(
    "timeout",
    [0, -1, math.nan, math.inf, -math.inf, True, "not-a-number"],
)
@pytest.mark.asyncio
async def test_execute_rejects_invalid_request_deadlines_before_provider_work(timeout):
    gateway = ModelGateway()
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="deadline validation")],
        extra_params={"timeout": timeout},
    )

    with pytest.raises(ValueError, match="request timeout must be a finite positive number"):
        await gateway.execute("groq", request)


@pytest.mark.asyncio
async def test_execute_deadline_bounds_provider_limiter_wait(monkeypatch):
    monkeypatch.setattr(settings, "PRIMARY_ATTEMPT_FRACTION", 0.5)
    monkeypatch.setattr(settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(
        "app.providers.gateway.provider_has_credentials",
        lambda _provider: True,
    )

    gateway = ModelGateway()
    gateway.key_pools["test-provider"] = KeyPool("test-provider", ["test-key"])
    limiter = ProviderRateLimiter(
        "test-provider",
        requests_per_second=0.001,
        max_concurrency=1,
    )
    # Simulate a limiter whose token bucket cannot refill within this request's
    # primary attempt slice. The completion path must time out *while acquiring* it.
    limiter.tokens = 0.0
    limiter.updated = time.monotonic()
    gateway.rate_limiters["test-provider"] = limiter

    provider_calls = 0
    fallback_called = asyncio.Event()

    class _Provider:
        async def generate(self, _request):
            nonlocal provider_calls
            provider_calls += 1
            raise AssertionError("provider call must not start without a limiter slot")

    monkeypatch.setattr(app.providers, "get_provider", lambda *_args, **_kwargs: _Provider())

    async def fallback(**_kwargs):
        fallback_called.set()
        raise RuntimeError("fallback reached after primary deadline")

    monkeypatch.setattr(gateway, "_execute_dynamic_fallback", fallback)
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="deadline test")],
        extra_params={"timeout": 0.1},
    )

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="fallback reached after primary deadline"):
        await gateway.execute("test-provider", request)
    elapsed = time.monotonic() - started

    assert fallback_called.is_set()
    assert provider_calls == 0
    assert elapsed < 0.5, f"request exceeded its 0.1s deadline by waiting {elapsed:.3f}s"
    # The timed-out acquire returns its concurrency slot rather than leaking it.
    assert limiter._sem._value == 1


@pytest.mark.asyncio
async def test_execute_uses_remaining_deadline_after_limiter_acquisition(monkeypatch):
    monkeypatch.setattr(settings, "PRIMARY_ATTEMPT_FRACTION", 0.5)
    monkeypatch.setattr(settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(
        "app.providers.gateway.provider_has_credentials",
        lambda _provider: True,
    )

    gateway = ModelGateway()
    gateway.key_pools["test-provider"] = KeyPool("test-provider", ["test-key"])
    limiter = ProviderRateLimiter("test-provider", requests_per_second=100.0, max_concurrency=1)
    gateway.rate_limiters["test-provider"] = limiter

    call_started = asyncio.Event()
    provider_cancelled = asyncio.Event()

    class _SlowProvider:
        async def generate(self, _request):
            call_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                provider_cancelled.set()
                raise

    monkeypatch.setattr(app.providers, "get_provider", lambda *_args, **_kwargs: _SlowProvider())

    async def fallback(**_kwargs):
        raise RuntimeError("fallback after timed-out provider call")

    monkeypatch.setattr(gateway, "_execute_dynamic_fallback", fallback)
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="deadline test")],
        extra_params={"timeout": 0.1},
    )

    with pytest.raises(RuntimeError, match="fallback after timed-out provider call"):
        await gateway.execute("test-provider", request)

    assert call_started.is_set()
    assert provider_cancelled.is_set()
    assert limiter._sem._value == 1


@pytest.mark.asyncio
async def test_local_fallback_deadline_bounds_limiter_wait(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_ENABLED", True)
    monkeypatch.setattr(settings, "LOCAL_MAX_RPS", 0.001)
    monkeypatch.setattr(settings, "LOCAL_MAX_CONCURRENCY", 1)

    gateway = ModelGateway()
    limiter = ProviderRateLimiter("local", requests_per_second=0.001, max_concurrency=1)
    limiter.tokens = 0.0
    limiter.updated = time.monotonic()
    gateway.rate_limiters["local"] = limiter
    provider_calls = 0

    class _LocalProvider:
        async def generate(self, _request):
            nonlocal provider_calls
            provider_calls += 1
            raise AssertionError("local provider must not run after its deadline")

    monkeypatch.setattr(app.providers, "get_provider", lambda *_args, **_kwargs: _LocalProvider())
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="local fallback timeout")],
    )

    started = time.monotonic()
    result = await gateway._execute_local_tier(
        failed_provider="groq",
        request=request,
        capability="general",
        last_error=RuntimeError("primary provider failed"),
        deadline=time.monotonic() + 0.05,
    )
    elapsed = time.monotonic() - started

    assert result is None
    assert provider_calls == 0
    assert elapsed < 0.5
    assert limiter._sem._value == 1


def test_routing_deadline_defaults_are_pinned():
    """TASK-INF-049 (INF-048 G5): pin the shipped routing-deadline defaults.

    INF-029/INF-047/INF-048 measured the live Gemini tail repeatedly and
    kept REQUEST_TIMEOUT=60.0, PRIMARY_ATTEMPT_FRACTION=0.6,
    PRIMARY_ATTEMPT_MAX_SECONDS=15.0, giving a primary slice of
    min(60.0 * 0.6, 15.0) = 15.0s. This test pins the *field defaults*
    (not any environment override) so a silent default change fails CI
    instead of quietly moving the deadline the measurements justify.
    """
    fields = Settings.model_fields
    assert fields["REQUEST_TIMEOUT"].default == 60.0
    assert fields["PRIMARY_ATTEMPT_FRACTION"].default == 0.6
    assert fields["PRIMARY_ATTEMPT_MAX_SECONDS"].default == 15.0

    # The gateway's primary slice (app/providers/gateway.py) is
    # min(timeout_budget * fraction, cap); at the default budget the cap
    # governs, so the slice the measurements were taken against is 15.0s.
    slice_s = min(
        fields["REQUEST_TIMEOUT"].default * fields["PRIMARY_ATTEMPT_FRACTION"].default,
        fields["PRIMARY_ATTEMPT_MAX_SECONDS"].default,
    )
    assert slice_s == 15.0
