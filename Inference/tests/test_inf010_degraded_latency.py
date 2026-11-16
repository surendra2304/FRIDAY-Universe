"""TASK-INF-010 — degraded-provider latency: timeout budget + fast failover.

The defect (named blocker from TASK-FRD-011; journal-measured in FRD-005
re-run 20261116-103839): a degraded provider could hold a
/v1/chat/completions request ~24.3s before the honest 503. Reproduced
against the deployed gateway 2026-11-16 23:54 IST at 43.89s, and
decomposed from the production journal + the INF-007 quota ledger:

* Gemini's degradation from Server 1 that evening was the HANG, not
  quota: 11/11 gateway attempts timed out, 0 successes, 0 rate-limited,
  quota buckets <=10% used (INF-007 ledger snapshot, 2026-11-16T18:25Z).
  The INF-009 probe's nine requests were all served only after paying a
  Gemini timeout first — 38.3-66.8s each vs a 7.7s healthy median.
* In the repro, the route's policy retry picked gemini-3.8-flash and its
  primary attempt burned the ENTIRE primary slice — "Provider 'gemini'
  timed out after 36.1s" (0.6 x the 60s REQUEST_TIMEOUT) — before the
  fallback ladder even started.

Three incoherences, three fixes pinned by this suite:

1. A hanging primary consumed its full primary slice (36s at defaults)
   before failover. Fix: PRIMARY_ATTEMPT_MAX_SECONDS caps the slice at
   min(fraction x budget, cap) — the ladder keeps the rest of the budget.
2. The route's policy retry ran a SECOND full gateway execution under a
   fresh budget; no deadline spanned attempt + retry. Fix: one
   end-to-end route deadline; each attempt receives only the remaining
   budget (UnifiedExecutionRequest.timeout -> gateway request timeout),
   and the retry is skipped when no useful pass fits in what remains.
3. OpenAI-compatible adapters slept a redundant 2.0s "transient
   cooldown" on every 429/503 inside every ladder rung. Fix: the pause
   is skipped on gateway-governed calls (request.deadline_monotonic
   set); the gateway's key quarantine already provides the pacing.
   Direct adapter calls keep the pause.

Harness patterns mirror tests/test_inf008_failover_drill.py (gateway)
and tests/test_rel043_best_suitable.py (route): scripted fakes only —
no network, no live keys, no production contact.
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
import app.providers.gateway as gateway_module
import app.providers.openai_compatible as openai_compatible_module
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.gateway import KeyPool, ModelGateway
from app.providers.openai_compatible import OpenAICompatibleProvider

PROVIDERS = ["gemini", "groq", "cerebras", "mistral", "openrouter", "cohere", "huggingface", "nvidia"]


# ---------------------------------------------------------------------------
# Gateway fakes (INF-008 house pattern)
# ---------------------------------------------------------------------------


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
    """Scripted provider: ``ok`` answers at once, ``hang`` never answers.
    Records the deadline marking of every request it is handed."""

    def __init__(self, name, behaviour="ok", seen=None):
        self.name = name
        self.behaviour = behaviour
        self.seen = seen if seen is not None else []

    async def get_best_free_model(self, capability="general"):
        return "test/free-model"

    async def generate(self, request):
        # getattr, not attribute access: on pre-fix code the field does not
        # exist, and the timing tests must fail by TIMING there, not by an
        # AttributeError inside the fake.
        self.seen.append((self.name, getattr(request, "deadline_monotonic", None)))
        if self.behaviour == "hang":
            await asyncio.sleep(3600)
        return ProviderResponse(
            content=f"answer:{self.name}", model=request.model or "m",
            provider=self.name, raw_response={},
        )


def _gateway(monkeypatch, script, seen=None):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {p: KeyPool(p, [f"{p}-key-1", f"{p}-key-2"]) for p in PROVIDERS}
    gateway.rate_limiters = {p: _Limiter() for p in PROVIDERS}
    gateway.health_tracker = _Health()

    def get_provider(name, **kwargs):
        return _FakeProvider(name, script.get(name, "ok"), seen)

    monkeypatch.setattr(app.providers, "get_provider", get_provider)
    monkeypatch.setattr(gateway_module, "provider_has_credentials", lambda prov: True)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(gateway_module.settings, "INFERENCE_LITELLM_FALLBACK_ENABLED", False)
    return gateway


def _request(timeout=30.0):
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content="inf010 question")],
        model="drill-model",
        extra_params={"timeout": timeout},
    )


import contextlib

_MISSING = object()


@contextlib.contextmanager
def _cap_seconds(value):
    """Set PRIMARY_ATTEMPT_MAX_SECONDS for one test.

    On pre-fix trees the Settings field does not exist and pydantic
    refuses a plain setattr — object.__setattr__ bypasses the field
    validation so the timing tests there fail by TIMING (the unfixed
    gateway never reads the value), not by a harness error.
    """
    settings_obj = gateway_module.settings
    old = settings_obj.__dict__.get("PRIMARY_ATTEMPT_MAX_SECONDS", _MISSING)
    object.__setattr__(settings_obj, "PRIMARY_ATTEMPT_MAX_SECONDS", value)
    try:
        yield
    finally:
        if old is _MISSING:
            object.__delattr__(settings_obj, "PRIMARY_ATTEMPT_MAX_SECONDS")
        else:
            object.__setattr__(settings_obj, "PRIMARY_ATTEMPT_MAX_SECONDS", old)


# ---------------------------------------------------------------------------
# Fix 1 — the primary slice cap (fast failover against a hanging primary)
# ---------------------------------------------------------------------------


def test_primary_hang_is_cut_at_the_absolute_cap_not_the_fraction(monkeypatch):
    """Budget 30s => fraction slice 18s. With the cap at 1s the ladder must
    serve in a few seconds; without the cap this test would take ~18s."""
    script = {p: "ok" for p in PROVIDERS}
    script["gemini"] = "hang"
    gateway = _gateway(monkeypatch, script)
    start = time.perf_counter()
    with _cap_seconds(1.0):
        resp = asyncio.run(gateway.execute("gemini", _request(timeout=30.0)))
    elapsed = time.perf_counter() - start
    assert resp.content.startswith("answer:")
    assert resp.provider != "gemini"
    assert elapsed < 6.0


def test_fraction_still_governs_below_the_cap(monkeypatch):
    """Small explicit budgets keep the pre-fix behaviour (INF-008 contract):
    budget 4s with the cap effectively off => the 0.6 fraction (2.4s) cuts
    the hanging primary, not the cap and not the whole budget."""
    script = {p: "ok" for p in PROVIDERS}
    script["gemini"] = "hang"
    gateway = _gateway(monkeypatch, script)
    start = time.perf_counter()
    with _cap_seconds(100.0):
        resp = asyncio.run(gateway.execute("gemini", _request(timeout=4.0)))
    elapsed = time.perf_counter() - start
    assert resp.content.startswith("answer:")
    assert 1.8 <= elapsed < 4.0


def test_gateway_marks_requests_with_their_deadline(monkeypatch):
    """Every adapter call the gateway paces carries the request deadline —
    the signal Fix 3 keys on."""
    seen = []
    gateway = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS}, seen=seen)
    start = time.monotonic()
    resp = asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))
    assert resp.content == "answer:gemini"
    assert seen, "the primary provider was never called"
    name, deadline = seen[0]
    assert name == "gemini"
    assert deadline is not None
    assert 8.0 <= (deadline - start) <= 12.0


# ---------------------------------------------------------------------------
# Fix 3 — adapter cooldown skipped on gateway-governed calls only
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    async def post(self, url, headers=None, json=None, timeout=None):
        return _FakeResponse(429, "rate limited")


class _SleepRecorder:
    def __init__(self):
        self.calls = []

    async def sleep(self, seconds):
        self.calls.append(seconds)


def _adapter(monkeypatch):
    provider = OpenAICompatibleProvider(
        provider_name="testprov",
        base_url="https://example.invalid/v1",
        api_key="test-key",
        default_model="m",
        supported_models=["m"],
        timeout=5.0,
    )

    async def fake_shared_client():
        return _FakeClient()

    monkeypatch.setattr(openai_compatible_module, "get_shared_client", fake_shared_client)
    recorder = _SleepRecorder()
    shim = type("Shim", (), {"sleep": staticmethod(recorder.sleep)})
    monkeypatch.setattr(openai_compatible_module, "asyncio", shim)
    return provider, recorder


def test_adapter_keeps_cooldown_on_direct_calls(monkeypatch):
    provider, recorder = _adapter(monkeypatch)
    req = ProviderRequest(
        messages=[ProviderMessage(role="user", content="hi")], model="m"
    )
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        asyncio.run(provider.generate(req))
    assert recorder.calls == [2.0]


def test_adapter_skips_cooldown_on_gateway_governed_calls(monkeypatch):
    provider, recorder = _adapter(monkeypatch)
    req = ProviderRequest(
        messages=[ProviderMessage(role="user", content="hi")],
        model="m",
        deadline_monotonic=time.monotonic() + 30.0,
    )
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        asyncio.run(provider.generate(req))
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# Fix 2 — one end-to-end deadline across the route's attempt + policy retry
# (REL-043 house pattern: ASGI transport + recording unified-manager stub)
# ---------------------------------------------------------------------------


from httpx import ASGITransport, AsyncClient  # noqa: E402

import app.api.v1_core_routes as v1_routes  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402  (aliased: plain `app` is the package above)


async def _post_chat(auth, payload):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post("/v1/chat/completions", json=payload)


def _stub_execute_with_burn(monkeypatch, burn_seconds):
    """Unified-manager double: the FIRST call burns `burn_seconds` of wall
    clock and comes back degraded; any later call answers under its own
    model name. Records (model, timeout) for every call, in order."""
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append((req.model, req.timeout))
        if len(calls) == 1:
            if burn_seconds:
                await asyncio.sleep(burn_seconds)
            return UnifiedExecutionResponse(
                provider_used=req.provider,
                model_used=req.model or "none",
                agent_role=req.agent_role or "system_architect",
                content="",
                latency_ms=burn_seconds * 1000.0,
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
    from app.providers.health import provider_health_tracker

    provider_health_tracker.reset()
    yield provider_health_tracker
    provider_health_tracker.reset()


@pytest.mark.asyncio
async def test_chat_retry_gets_only_the_remaining_budget(auth, monkeypatch, healthy_tracker):
    monkeypatch.setattr(v1_routes.settings, "REQUEST_TIMEOUT", 30.0)
    calls = _stub_execute_with_burn(monkeypatch, burn_seconds=3.0)
    res = await _post_chat(
        auth,
        {"model": "gemini-3.8-flash", "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200
    # The REL-043 retry shape: degraded gemini-3.8-flash, then the
    # next-best suitable model serves.
    assert [c[0] for c in calls] == ["gemini-3.8-flash", "openai/gpt-oss-120b"]
    first_timeout, retry_timeout = calls[0][1], calls[1][1]
    assert first_timeout is not None and 29.0 < first_timeout <= 30.05
    # The retry inherits what is LEFT of the shared budget (~27s after the
    # 3s burn) — not a fresh 30s budget.
    assert retry_timeout is not None and 20.0 < retry_timeout < 29.0


@pytest.mark.asyncio
async def test_chat_retry_is_skipped_when_the_shared_budget_is_spent(auth, monkeypatch, healthy_tracker):
    monkeypatch.setattr(v1_routes.settings, "REQUEST_TIMEOUT", 3.0)
    calls = _stub_execute_with_burn(monkeypatch, burn_seconds=2.6)
    res = await _post_chat(
        auth,
        {"model": "gemini-3.8-flash", "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    # The first attempt's failure stands and the honest 503 reports it;
    # no second execution is started with ~0.4s left.
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "provider_degraded"
    assert len(calls) == 1
    assert calls[0][1] is not None and 2.5 < calls[0][1] <= 3.05
