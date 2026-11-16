"""TASK-INF-006: the safe response cache.

The rule under test: a personalised or contextual answer is never served
to the wrong context. Around it: exact match, registered-template match,
per-class TTLs, generation invalidation, stochastic discipline, bounds,
metrics, the gateway integration, the unified-manager integration, and
the replay harness arithmetic.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest

from app.inference_runtime.config import RuntimeConfig
from app.inference_runtime.contracts import (
    Capability,
    CompletionRequest,
    CompletionResult,
    Message,
    ProviderEndpoint,
)
from app.inference_runtime.gateway import HardenedGateway
from app.inference_runtime.response_cache import (
    CachePolicy,
    ContextClass,
    SafeResponseCache,
    TemplateSpec,
)

NS = "test.ns"
PAYLOAD = {"prompt": "What is the capital of France?", "temperature": 0.0}


def _cache(**policy_overrides) -> SafeResponseCache:
    return SafeResponseCache(CachePolicy(**policy_overrides))


def _fp(context=None, principal=None) -> str:
    return SafeResponseCache.context_fingerprint(context or {}, principal)


# ----------------------------------------------------------------------
# Classification
# ----------------------------------------------------------------------

def test_classify_public_by_default():
    cache = _cache()
    assert cache.classify(context={}, prompt_text="What is the capital of France?") is ContextClass.PUBLIC


def test_classify_context_raises_to_contextual():
    cache = _cache()
    assert cache.classify(context={"workspace": "alpha"}) is ContextClass.CONTEXTUAL


def test_classify_principal_raises_to_personalised():
    cache = _cache()
    assert cache.classify(principal_id="user-1") is ContextClass.PERSONALISED
    assert cache.classify(context={"session_id": "s-1"}) is ContextClass.PERSONALISED


def test_classify_first_person_marker_raises_to_contextual():
    cache = _cache()
    assert cache.classify(context={}, prompt_text="What is my balance?") is ContextClass.CONTEXTUAL


def test_classify_declared_class_is_a_floor_never_lowered():
    cache = _cache()
    assert cache.classify(declared="personalised", context={}) is ContextClass.PERSONALISED
    # A declared PUBLIC request with a principal is raised, not trusted.
    assert cache.classify(declared="public", principal_id="user-1") is ContextClass.PERSONALISED


# ----------------------------------------------------------------------
# Exact match and the context rule
# ----------------------------------------------------------------------

def test_exact_match_hit_and_param_change_miss():
    cache = _cache()
    fp = _fp()
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "Paris"},
                context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                original_latency_seconds=1.5)
    hit = cache.lookup(namespace=NS, payload=PAYLOAD,
                       context_class=ContextClass.PUBLIC, context_fingerprint=fp)
    assert hit.hit and hit.value == {"text": "Paris"} and hit.match_kind == "exact"

    changed = dict(PAYLOAD, temperature=0.7)
    miss = cache.lookup(namespace=NS, payload=changed,
                        context_class=ContextClass.PUBLIC, context_fingerprint=fp)
    assert not miss.hit


def test_public_answers_are_shareable_across_contexts():
    cache = _cache()
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "Paris"},
                context_class=ContextClass.PUBLIC, context_fingerprint=_fp({"a": 1}),
                original_latency_seconds=1.0)
    hit = cache.lookup(namespace=NS, payload=PAYLOAD,
                       context_class=ContextClass.PUBLIC, context_fingerprint=_fp({"b": 2}))
    assert hit.hit


def test_contextual_answer_is_never_served_to_a_different_context():
    cache = _cache()
    ctx_a, ctx_b = {"tenant_plan": "enterprise"}, {"tenant_plan": "free"}
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "for enterprise"},
                context_class=ContextClass.CONTEXTUAL, context_fingerprint=_fp(ctx_a),
                original_latency_seconds=1.0)
    assert cache.lookup(namespace=NS, payload=PAYLOAD,
                        context_class=ContextClass.CONTEXTUAL,
                        context_fingerprint=_fp(ctx_a)).hit
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.CONTEXTUAL,
                            context_fingerprint=_fp(ctx_b)).hit


def test_personalised_answers_are_not_stored_by_default():
    cache = _cache()
    result = cache.store(namespace=NS, payload=PAYLOAD, value={"text": "your balance"},
                         context_class=ContextClass.PERSONALISED,
                         context_fingerprint=_fp({}, "user-1"), principal_id="user-1",
                         original_latency_seconds=1.0)
    assert result == "bypass:personalised_storage_disabled"
    lookup = cache.lookup(namespace=NS, payload=PAYLOAD,
                          context_class=ContextClass.PERSONALISED,
                          context_fingerprint=_fp({}, "user-1"))
    assert not lookup.hit and lookup.reason == "bypass:personalised_storage_disabled"
    assert len(cache) == 0


def test_personalised_storage_when_enabled_is_principal_scoped():
    cache = _cache(allow_personalised_storage=True)
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "user-1 balance"},
                context_class=ContextClass.PERSONALISED,
                context_fingerprint=_fp({}, "user-1"), principal_id="user-1",
                original_latency_seconds=1.0)
    assert cache.lookup(namespace=NS, payload=PAYLOAD,
                        context_class=ContextClass.PERSONALISED,
                        context_fingerprint=_fp({}, "user-1")).hit
    # A different principal can never be served the entry.
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.PERSONALISED,
                            context_fingerprint=_fp({}, "user-2")).hit
    # Erasure: invalidating the principal removes exactly its entries.
    assert cache.invalidate_principal("user-1") == 1
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.PERSONALISED,
                            context_fingerprint=_fp({}, "user-1")).hit


# ----------------------------------------------------------------------
# TTLs, stochastic discipline, bounds
# ----------------------------------------------------------------------

def test_ttl_expires_entries():
    cache = _cache(public_ttl_seconds=0.05)
    fp = _fp()
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "Paris"},
                context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                original_latency_seconds=1.0)
    assert cache.lookup(namespace=NS, payload=PAYLOAD,
                        context_class=ContextClass.PUBLIC, context_fingerprint=fp).hit
    time.sleep(0.07)
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.PUBLIC, context_fingerprint=fp).hit
    assert cache.stats()["expirations"] >= 1


def test_stochastic_entries_are_capped_at_the_stochastic_ttl():
    cache = _cache(contextual_ttl_seconds=60.0, stochastic_ttl_cap_seconds=0.05)
    fp = _fp({"workspace": "alpha"})
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "x"},
                context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp,
                original_latency_seconds=1.0, stochastic=True)
    time.sleep(0.07)
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp,
                            stochastic=True).hit


def test_lru_bound_is_enforced():
    cache = _cache(max_entries=3)
    fp = _fp()
    for i in range(4):
        cache.store(namespace=NS, payload={"prompt": f"q{i}"}, value={"text": str(i)},
                    context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                    original_latency_seconds=0.5)
    assert len(cache) == 3
    assert cache.stats()["evictions"] >= 1
    assert not cache.lookup(namespace=NS, payload={"prompt": "q0"},
                            context_class=ContextClass.PUBLIC, context_fingerprint=fp).hit


# ----------------------------------------------------------------------
# Template matching
# ----------------------------------------------------------------------

def _template_cache(**overrides) -> SafeResponseCache:
    cache = _cache(**overrides)
    cache.register_template(
        TemplateSpec(template_id="market_summary", version="1",
                     invariant_slots=frozenset({"request_id"}))
    )
    return cache


def test_template_match_ignores_only_invariant_slots():
    cache = _template_cache()
    fp = _fp()
    cache.store(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                value={"text": "BTC summary"}, context_class=ContextClass.PUBLIC,
                context_fingerprint=fp, original_latency_seconds=2.0,
                template_id="market_summary",
                template_slots={"symbol": "BTCUSDT", "request_id": "r1"})
    # New request id (invariant) -> template hit.
    hit = cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r2"},
                       context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                       template_id="market_summary",
                       template_slots={"symbol": "BTCUSDT", "request_id": "r2"})
    assert hit.hit and hit.match_kind == "template"
    # Different semantic slot -> no match.
    miss = cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r3"},
                        context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                        template_id="market_summary",
                        template_slots={"symbol": "ETHUSDT", "request_id": "r3"})
    assert not miss.hit


def test_unregistered_template_never_matches():
    cache = _cache()
    fp = _fp()
    cache.store(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                value={"text": "x"}, context_class=ContextClass.PUBLIC,
                context_fingerprint=fp, original_latency_seconds=1.0,
                template_id="ghost", template_slots={"symbol": "BTCUSDT"})
    hit = cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r2"},
                       context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                       template_id="ghost", template_slots={"symbol": "BTCUSDT"})
    assert not hit.hit


def test_template_never_serves_personalised_or_stochastic():
    cache = _template_cache(allow_personalised_storage=True)
    fp = _fp({}, "user-1")
    cache.store(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                value={"text": "x"}, context_class=ContextClass.PERSONALISED,
                context_fingerprint=fp, principal_id="user-1",
                original_latency_seconds=1.0, template_id="market_summary",
                template_slots={"symbol": "BTCUSDT", "request_id": "r1"})
    hit = cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r2"},
                       context_class=ContextClass.PERSONALISED, context_fingerprint=fp,
                       template_id="market_summary",
                       template_slots={"symbol": "BTCUSDT", "request_id": "r2"})
    # Only the exact entry may serve a personalised request — the template
    # key must not exist for it, so a *different* raw request cannot hit.
    assert not hit.hit

    cache2 = _template_cache()
    fp2 = _fp()
    cache2.store(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                 value={"text": "x"}, context_class=ContextClass.PUBLIC,
                 context_fingerprint=fp2, original_latency_seconds=1.0,
                 template_id="market_summary",
                 template_slots={"symbol": "BTCUSDT", "request_id": "r1"},
                 stochastic=True)
    hit2 = cache2.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r2"},
                         context_class=ContextClass.PUBLIC, context_fingerprint=fp2,
                         template_id="market_summary",
                         template_slots={"symbol": "BTCUSDT", "request_id": "r2"},
                         stochastic=True)
    assert not hit2.hit


# ----------------------------------------------------------------------
# Invalidation
# ----------------------------------------------------------------------

def test_invalidate_namespace_orphans_entries():
    cache = _cache()
    fp = _fp()
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "Paris"},
                context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                original_latency_seconds=1.0)
    cache.invalidate_namespace(NS)
    assert not cache.lookup(namespace=NS, payload=PAYLOAD,
                            context_class=ContextClass.PUBLIC, context_fingerprint=fp).hit


def test_invalidate_template_and_context():
    cache = _template_cache()
    fp_a, fp_b = _fp({"w": "a"}), _fp({"w": "b"})
    for fp in (fp_a, fp_b):
        cache.store(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                    value={"text": "x"}, context_class=ContextClass.CONTEXTUAL,
                    context_fingerprint=fp, original_latency_seconds=1.0,
                    template_id="market_summary", template_slots={"symbol": "BTCUSDT"})
    cache.invalidate_template("market_summary")
    assert not cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r9"},
                            context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp_a,
                            template_id="market_summary",
                            template_slots={"symbol": "BTCUSDT"}).hit
    # Exact entries survive a template invalidation; a context
    # invalidation removes exactly that context's entries.
    assert cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                        context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp_a).hit
    assert cache.invalidate_context(fp_a) >= 1
    assert not cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                            context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp_a).hit
    assert cache.lookup(namespace=NS, payload={"prompt": "summary", "request_id": "r1"},
                        context_class=ContextClass.CONTEXTUAL, context_fingerprint=fp_b).hit


def test_stats_report_hits_and_latency_saved():
    cache = _cache()
    fp = _fp()
    cache.store(namespace=NS, payload=PAYLOAD, value={"text": "Paris"},
                context_class=ContextClass.PUBLIC, context_fingerprint=fp,
                original_latency_seconds=2.5)
    cache.lookup(namespace=NS, payload=PAYLOAD,
                 context_class=ContextClass.PUBLIC, context_fingerprint=fp)
    cache.lookup(namespace=NS, payload={"prompt": "other"},
                 context_class=ContextClass.PUBLIC, context_fingerprint=fp)
    stats = cache.stats()
    assert stats["hits"] == 1 and stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
    assert stats["latency_saved_seconds"] == 2.5


# ----------------------------------------------------------------------
# Gateway integration
# ----------------------------------------------------------------------

class _Transport:
    def __init__(self):
        self.calls: list[CompletionRequest] = []

    async def complete(self, request, endpoint, api_key):
        self.calls.append(request)
        return CompletionResult(
            text='{"ok": true}', provider=endpoint.provider, model=endpoint.model,
            latency_seconds=0.25, total_tokens=2, cost_usd=0.001,
        )

    async def health(self):
        return True


def _gateway(transport: _Transport) -> HardenedGateway:
    gateway = HardenedGateway(
        RuntimeConfig(max_retries=0, request_timeout_seconds=2.0, default_budget_usd=10.0)
    )
    gateway.register(
        ProviderEndpoint(provider="test-provider", model="test-model",
                         capabilities=frozenset({Capability.CHAT, Capability.JSON})),
        transport,
    )
    return gateway


def _request(**overrides) -> CompletionRequest:
    values = {
        "model": "test-model",
        "messages": (Message(role="user", content="hello"),),
        "timeout_seconds": 5.0,
        "tenant_id": "tenant-a",
        "request_id": "request-1",
        "cacheable": True,
        "temperature": 0.0,
    }
    values.update(overrides)
    return CompletionRequest(**values)


@pytest.mark.asyncio
async def test_gateway_never_serves_a_contextual_answer_to_another_context():
    transport = _Transport()
    gateway = _gateway(transport)
    ctx_a = {"account": "A"}
    ctx_b = {"account": "B"}

    await gateway.complete(_request(context=ctx_a))
    await gateway.complete(_request(context=ctx_b))
    assert len(transport.calls) == 2  # B was NOT served A's cached answer

    third = await gateway.complete(_request(context=ctx_a))
    assert third.cached is True
    assert len(transport.calls) == 2  # A again -> cache hit


@pytest.mark.asyncio
async def test_gateway_never_caches_personalised_requests_by_default():
    transport = _Transport()
    gateway = _gateway(transport)
    await gateway.complete(_request(principal_id="user-1"))
    await gateway.complete(_request(principal_id="user-1"))
    assert len(transport.calls) == 2
    assert gateway.response_cache.stats()["bypasses"].get("personalised_storage_disabled", 0) >= 1


@pytest.mark.asyncio
async def test_gateway_template_match_across_request_ids():
    transport = _Transport()
    gateway = _gateway(transport)
    gateway.response_cache.register_template(
        TemplateSpec(template_id="market_summary", version="1",
                     invariant_slots=frozenset({"request_id"}))
    )
    await gateway.complete(_request(extra={"trace": "a"}, template_id="market_summary",
                                    template_slots={"symbol": "BTCUSDT", "request_id": "a"}))
    second = await gateway.complete(_request(extra={"trace": "b"}, template_id="market_summary",
                                             template_slots={"symbol": "BTCUSDT", "request_id": "b"}))
    assert second.cached is True
    assert len(transport.calls) == 1


# ----------------------------------------------------------------------
# Unified manager integration: personalised context is never stored
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unified_personalised_context_is_never_cached(monkeypatch):
    from app.performance_cache import perf_cache
    from app.providers.base import ProviderResponse
    from app.providers.gateway import model_gateway
    from app.providers.unified_manager import (
        UnifiedExecutionRequest,
        UnifiedProviderManager,
        response_cache,
    )

    perf_cache.clear()
    response_cache.flush()
    calls = []

    async def execute(_self, *, provider_name, request, capability="general", stage_name="general"):
        calls.append(provider_name)
        return ProviderResponse(content="balance answer", model="test-model",
                                provider=provider_name, latency_seconds=0.01, total_tokens=4)

    monkeypatch.setattr(type(model_gateway), "execute", execute)
    manager = UnifiedProviderManager()
    req = UnifiedExecutionRequest(
        provider="auto", agent_role="cache_scope_regression_role",
        prompt="What is the account balance?",
        context={"session_id": "sess-1", "account": "A"},
        max_tokens=200, temperature=0.0,
    )
    await manager.execute(req)
    second = await manager.execute(req)
    assert len(calls) == 2  # personalised: provider called both times
    assert second.status == "success"
    response_cache.flush()


# ----------------------------------------------------------------------
# Replay harness
# ----------------------------------------------------------------------

def _load_replay_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "replay_response_cache.py"
    spec = importlib.util.spec_from_file_location("replay_response_cache", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_replay_harness_arithmetic_and_safety():
    replay = _load_replay_module()
    entries = [
        {"_templates": [{"template_id": "t1", "version": "1", "invariant_slots": ["request_id"]}]},
        {"prompt": "q1", "context": {}, "principal_id": None, "temperature": 0.0, "latency_ms": 1000.0},
        {"prompt": "q1", "context": {}, "principal_id": None, "temperature": 0.0, "latency_ms": 1000.0},
        {"prompt": "q1", "context": {}, "principal_id": None, "temperature": 0.0, "latency_ms": 1000.0},
        {"prompt": "mine?", "context": {"session_id": "s1"}, "principal_id": "user-1",
         "temperature": 0.0, "latency_ms": 2000.0},
        {"prompt": "mine?", "context": {"session_id": "s2"}, "principal_id": "user-2",
         "temperature": 0.0, "latency_ms": 2000.0},
        {"prompt": "summary", "context": {}, "principal_id": None, "temperature": 0.0,
         "latency_ms": 3000.0, "request_id": "r1", "template_id": "t1",
         "slots": {"symbol": "BTC", "request_id": "r1"}},
        {"prompt": "summary", "context": {}, "principal_id": None, "temperature": 0.0,
         "latency_ms": 3000.0, "request_id": "r2", "template_id": "t1",
         "slots": {"symbol": "BTC", "request_id": "r2"}},
    ]
    result = replay.replay_log(entries)
    assert result["requests"] == 7
    assert result["hits_exact"] == 2
    assert result["hits_template"] == 1
    assert result["personalised_requests"] == 2
    assert result["personalised_hits"] == 0
    assert result["cross_principal_violations"] == 0
    # Saved: 2 exact hits x (1000 - 0.2) + 1 template hit x (3000 - 0.2).
    assert result["latency_saved_ms"] == pytest.approx(2 * 999.8 + 2999.8, abs=0.2)
