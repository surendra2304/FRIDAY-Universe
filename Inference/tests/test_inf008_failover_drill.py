"""TASK-INF-008 — Inference failover drill (failure behaviour, not policy).

Simulates each provider failing — HTTP 503s, 429 quota exhaustion, hangs,
malformed exceptions, connection refusal, and structural empty completions —
in an isolated harness (scripted fake providers; no network, no live keys,
no production contact) and asserts the failure contract:

* a single provider failure is absorbed by the fallback ladder;
* a total failure surfaces as a typed error inside the request deadline,
  which the FRIDAY-facing routes translate to an honest 503 — never a hang,
  never an unhandled 500, never a fabricated/empty 200 "answer".

Drill findings fixed alongside this suite (measured before the fix):
  G1  the OpenRouter fallback rung awaited model discovery with no deadline
      bound — an 8s request budget blew past 38s when discovery hung.
  G2  a structural empty completion (adapters label it finish_reason="empty"
      when the upstream body has no candidates/choices) was served as a
      successful answer — /v1/friday/ask returned 200 with answer="" and
      confidence 0.7; /v1/chat/completions returned 200 with empty content.
  G3  /v1/friday/ask on the DAG path returned HTTP 500 for a total provider
      outage while the fast-lane path and /debate returned 503 for the
      identical condition.

One measured boundary is pinned as a contract, not fixed: the ladder is
exactly {OpenRouter rung, waterfall groq/openrouter/gemini, local tier,
LiteLLM}. With those three providers down, second-tier providers are never
attempted — widening that is routing policy (TASK-REL-043/044), and this
test makes any change to it deliberate.
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
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.errors import (
    AuthenticationError,
    GatewayError,
    TemporaryUnavailableError,
)
from app.providers.gateway import KeyPool, ModelGateway

PROVIDERS = ["gemini", "groq", "cerebras", "mistral", "openrouter", "cohere", "huggingface", "nvidia"]


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
    """Scripted provider. Behaviours: ok, empty, e503, e429, e401, garbage,
    connerr, hang. ``discovery`` scripts OpenRouter model discovery."""

    def __init__(self, name, behaviour="ok", discovery="ok", calls=None):
        self.name = name
        self.behaviour = behaviour
        self.discovery = discovery
        self.calls = calls if calls is not None else {}

    async def get_best_free_model(self, capability="general"):
        if self.discovery == "hang":
            await asyncio.sleep(3600)
        if self.discovery == "raise":
            raise RuntimeError("503 Service Unavailable: discovery down")
        return "test/free-model"

    async def generate(self, request):
        self.calls[self.name] = self.calls.get(self.name, 0) + 1
        b = self.behaviour
        if b == "ok":
            return ProviderResponse(
                content=f"answer:{self.name}", model=request.model or "m",
                provider=self.name, raw_response={},
            )
        if b == "empty":
            # Exactly the adapters' shape for an upstream body with no
            # candidates/choices at all (gemini.py, openai_compatible.py).
            return ProviderResponse(
                content="", model=request.model or "m", provider=self.name,
                finish_reason="empty", raw_response={},
            )
        if b == "e503":
            raise RuntimeError("503 Service Unavailable: provider overloaded")
        if b == "e429":
            raise RuntimeError("429 Too Many Requests: quota exceeded for this key")
        if b == "e401":
            raise RuntimeError("401 Unauthorized: invalid api key")
        if b == "garbage":
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        if b == "connerr":
            raise ConnectionError("Connection refused by provider host")
        if b == "hang":
            await asyncio.sleep(3600)
        raise AssertionError(b)

    async def stream(self, request):
        if self.behaviour == "ok":
            yield "chunk-1"
            yield "chunk-2"
            return
        if self.behaviour == "midfail":
            yield "chunk-1"
            raise RuntimeError("503 Service Unavailable: mid-stream failure")
        raise RuntimeError("503 Service Unavailable: provider overloaded")


def _gateway(monkeypatch, script, discovery="ok", calls=None):
    """A ModelGateway wired to scripted fakes (house pattern: hand-built
    pools/limiters/health, real execute() + ladder code under test)."""
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {p: KeyPool(p, [f"{p}-key-1", f"{p}-key-2"]) for p in PROVIDERS}
    gateway.rate_limiters = {p: _Limiter() for p in PROVIDERS}
    gateway.health_tracker = _Health()

    def get_provider(name, **kwargs):
        return _FakeProvider(name, script.get(name, "ok"), discovery, calls)

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


def _all(behaviour):
    return {p: behaviour for p in PROVIDERS}


# --------------------------------------------------------------------------
# Single-provider failures: the ladder must absorb every one of them.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("primary", PROVIDERS)
def test_drill_primary_503_falls_back(monkeypatch, primary):
    script = _all("ok")
    script[primary] = "e503"
    gateway = _gateway(monkeypatch, script)
    resp = asyncio.run(gateway.execute(primary, _request()))
    assert resp.content == f"answer:{resp.provider}"
    provenance = (resp.raw_response or {}).get("fallback_provenance") or {}
    assert provenance.get("actual_provider") not in (None, primary)


def test_drill_primary_429_quarantines_keys_and_falls_back(monkeypatch):
    script = _all("ok")
    script["groq"] = "e429"
    gateway = _gateway(monkeypatch, script)
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.content.startswith("answer:")
    assert gateway.key_pools["groq"].get_quarantined_keys_count() == 2


def test_drill_primary_timeout_escalates_within_budget(monkeypatch):
    script = _all("ok")
    script["gemini"] = "hang"
    gateway = _gateway(monkeypatch, script)
    start = time.perf_counter()
    resp = asyncio.run(gateway.execute("gemini", _request(timeout=4.0)))
    elapsed = time.perf_counter() - start
    assert resp.content.startswith("answer:")
    assert elapsed < 4.0


def test_drill_primary_garbage_exception_falls_back(monkeypatch):
    script = _all("ok")
    script["gemini"] = "garbage"
    gateway = _gateway(monkeypatch, script)
    resp = asyncio.run(gateway.execute("gemini", _request()))
    assert resp.content.startswith("answer:")


def test_drill_all_keys_quarantined_fails_closed(monkeypatch):
    calls = {}
    gateway = _gateway(monkeypatch, _all("ok"), calls=calls)
    for key in ("groq-key-1", "groq-key-2"):
        gateway.key_pools["groq"].quarantine(key, duration_seconds=60)
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.content.startswith("answer:")
    assert calls.get("groq", 0) == 0  # quarantined keys are never hammered


# --------------------------------------------------------------------------
# Total failures: typed errors, inside the deadline, never a hang.
# --------------------------------------------------------------------------

def test_drill_all_providers_503_raise_typed_error(monkeypatch):
    gateway = _gateway(monkeypatch, _all("e503"))
    start = time.perf_counter()
    with pytest.raises(TemporaryUnavailableError):
        asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))
    assert time.perf_counter() - start < 5.0


def test_drill_all_providers_hang_respects_deadline(monkeypatch):
    gateway = _gateway(monkeypatch, _all("hang"))
    start = time.perf_counter()
    with pytest.raises((TimeoutError, GatewayError)):
        asyncio.run(gateway.execute("gemini", _request(timeout=3.0)))
    elapsed = time.perf_counter() - start
    assert elapsed < 4.5  # the 3s budget, plus scheduling slack — not a hang


def test_drill_all_providers_401_raise_authentication_error(monkeypatch):
    gateway = _gateway(monkeypatch, _all("e401"))
    with pytest.raises(AuthenticationError):
        asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))


def test_drill_all_providers_connrefused_raise_gateway_error(monkeypatch):
    gateway = _gateway(monkeypatch, _all("connerr"))
    with pytest.raises(GatewayError):
        asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))


def test_drill_waterfall_breadth_contract(monkeypatch):
    """Measured boundary (policy, TASK-REL-043/044): with the waterfall trio
    down, healthy second-tier providers are never attempted."""
    script = _all("ok")
    for p in ("gemini", "groq", "openrouter"):
        script[p] = "e503"
    calls = {}
    gateway = _gateway(monkeypatch, script, calls=calls)
    with pytest.raises(TemporaryUnavailableError):
        asyncio.run(gateway.execute("gemini", _request(timeout=10.0)))
    assert not any(calls.get(p) for p in ("cerebras", "mistral", "cohere", "huggingface", "nvidia"))


# --------------------------------------------------------------------------
# G1: OpenRouter model discovery lives inside the request deadline.
# --------------------------------------------------------------------------

def test_drill_openrouter_discovery_hang_is_bounded(monkeypatch):
    script = _all("ok")
    script["groq"] = "e503"
    gateway = _gateway(monkeypatch, script, discovery="hang")
    start = time.perf_counter()
    resp = asyncio.run(gateway.execute("groq", _request(timeout=6.0)))
    elapsed = time.perf_counter() - start
    assert resp.content.startswith("answer:")  # the waterfall still served
    assert elapsed < 6.0  # pre-fix this ran past 38s on an 8s budget


def test_drill_openrouter_discovery_failure_falls_to_waterfall(monkeypatch):
    script = _all("ok")
    script["groq"] = "e503"
    gateway = _gateway(monkeypatch, script, discovery="raise")
    resp = asyncio.run(gateway.execute("groq", _request(timeout=6.0)))
    assert resp.content.startswith("answer:")


# --------------------------------------------------------------------------
# G2: structural empty completions are failures, not answers.
# --------------------------------------------------------------------------

def test_drill_empty_completion_climbs_ladder(monkeypatch):
    script = _all("ok")
    script["gemini"] = "empty"
    gateway = _gateway(monkeypatch, script)
    resp = asyncio.run(gateway.execute("gemini", _request()))
    assert resp.content.startswith("answer:")
    assert resp.provider != "gemini"


def test_drill_all_empty_raises_typed_error(monkeypatch):
    gateway = _gateway(monkeypatch, _all("empty"))
    with pytest.raises(TemporaryUnavailableError) as excinfo:
        asyncio.run(gateway.execute("gemini", _request()))
    assert "empty completion" in str(excinfo.value)


def test_drill_nonempty_completion_unaffected(monkeypatch):
    gateway = _gateway(monkeypatch, _all("ok"))
    resp = asyncio.run(gateway.execute("gemini", _request()))
    assert resp.content == "answer:gemini"


# --------------------------------------------------------------------------
# Unified manager: failure becomes an honest degraded result, never a
# fabricated answer and never an exception escaping to the route.
# --------------------------------------------------------------------------

def test_drill_unified_manager_reports_degraded(monkeypatch):
    from app.providers import unified_manager as um

    gateway = _gateway(monkeypatch, _all("e503"))
    monkeypatch.setattr(um, "model_gateway", gateway)
    res = asyncio.run(
        um.unified_provider_manager.execute(
            um.UnifiedExecutionRequest(
                provider="gemini", prompt="drill unified degraded", no_cache=True
            )
        )
    )
    assert res.degraded is True
    assert res.content == ""
    assert res.status == "degraded"


def test_drill_unified_manager_serves_via_fallback(monkeypatch):
    from app.providers import unified_manager as um

    script = _all("ok")
    script["groq"] = "e503"
    gateway = _gateway(monkeypatch, script)
    monkeypatch.setattr(um, "model_gateway", gateway)
    res = asyncio.run(
        um.unified_provider_manager.execute(
            um.UnifiedExecutionRequest(
                provider="groq", prompt="drill unified fallback", no_cache=True
            )
        )
    )
    assert res.degraded is False
    assert res.content.startswith("answer:")
    assert res.served_by_provider not in (None, "groq")


# --------------------------------------------------------------------------
# FRIDAY-facing routes: the same outage, the same honest answer everywhere.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _install_route_script(monkeypatch, script, tag):
    """Point the GLOBAL gateway at scripted fakes with per-test unique keys
    (so 60s quarantines from one scenario can never leak into the next)."""
    from app.core.config import settings
    from app.providers.gateway import model_gateway
    from app.providers.health import provider_health_tracker

    keys = {p: [f"{tag}-{p}-key-1", f"{tag}-{p}-key-2"] for p in PROVIDERS}
    monkeypatch.setattr(
        type(settings), "get_provider_keys", lambda self, name: keys.get(name.lower(), [])
    )
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(settings, "INFERENCE_LITELLM_FALLBACK_ENABLED", False)
    monkeypatch.setattr(
        app.providers, "get_provider",
        lambda name, **kw: _FakeProvider(name, script.get(name, "ok")),
    )
    monkeypatch.setattr(
        gateway_module, "provider_has_credentials", lambda prov: True
    )
    model_gateway.refresh_keys()
    for p in list(model_gateway.rate_limiters):
        model_gateway.rate_limiters[p] = _Limiter()
    provider_health_tracker.reset()


def test_drill_ask_fast_lane_total_outage_is_503(client, monkeypatch, auth):
    _install_route_script(monkeypatch, _all("e503"), "askfast")
    r = client.post(
        "/v1/friday/ask", headers=auth,
        json={"question": "drill ask fast outage q1", "no_cache": True},
    )
    assert r.status_code == 503
    assert "No answer fabricated" in r.text


def test_drill_ask_dag_path_total_outage_is_503(client, monkeypatch, auth):
    """G3 regression: the DAG path must classify a total outage like the
    fast lane and /debate do — 503, not 500."""
    _install_route_script(monkeypatch, _all("e503"), "askdag")
    r = client.post(
        "/v1/friday/ask", headers=auth,
        json={
            "question": "drill ask dag outage q2", "no_cache": True,
            "fast_lane": False, "max_latency": 30.0,
        },
    )
    assert r.status_code == 503
    assert "No answer was fabricated" in r.text


def test_drill_ask_all_empty_is_503_not_empty_200(client, monkeypatch, auth):
    """G2 regression at the FRIDAY surface."""
    _install_route_script(monkeypatch, _all("empty"), "askempty")
    r = client.post(
        "/v1/friday/ask", headers=auth,
        json={"question": "drill ask empty q3", "no_cache": True},
    )
    assert r.status_code == 503


def test_drill_ask_mixed_outage_served_by_survivor(client, monkeypatch, auth):
    script = _all("ok")
    script["groq"] = "e503"
    script["openrouter"] = "e503"
    _install_route_script(monkeypatch, script, "askmixed")
    r = client.post(
        "/v1/friday/ask", headers=auth,
        json={"question": "drill ask mixed q4", "no_cache": True},
    )
    assert r.status_code == 200
    assert r.json()["answer"] == "answer:gemini"


def test_drill_chat_completions_total_outage_is_503(client, monkeypatch, auth):
    _install_route_script(monkeypatch, _all("e503"), "chatout")
    r = client.post(
        "/v1/chat/completions", headers=auth,
        json={"model": "auto", "messages": [{"role": "user", "content": "drill chat outage q5"}]},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "provider_degraded"
    assert body["retryable"] is True


def test_drill_chat_completions_all_empty_is_503(client, monkeypatch, auth):
    """G2 regression at the OpenAI-compatible surface."""
    _install_route_script(monkeypatch, _all("empty"), "chatempty")
    r = client.post(
        "/v1/chat/completions", headers=auth,
        json={"model": "auto", "messages": [{"role": "user", "content": "drill chat empty q6"}]},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "provider_degraded"


def test_drill_chat_stream_failure_emits_error_and_done(client, monkeypatch, auth):
    _install_route_script(monkeypatch, _all("e503"), "chatstream")
    r = client.post(
        "/v1/chat/completions", headers=auth,
        json={
            "model": "auto", "stream": True,
            "messages": [{"role": "user", "content": "drill chat stream q7"}],
        },
    )
    assert r.status_code == 200
    assert '"error"' in r.text
    assert "data: [DONE]" in r.text


def test_drill_friday_stream_mid_failure_emits_error_event(client, monkeypatch, auth):
    _install_route_script(monkeypatch, _all("midfail"), "fristream")
    r = client.post(
        "/v1/friday/stream", headers=auth,
        json={"question": "drill friday stream q8", "no_cache": True},
    )
    assert r.status_code == 200
    assert '"error"' in r.text
    assert '"done": true' in r.text
