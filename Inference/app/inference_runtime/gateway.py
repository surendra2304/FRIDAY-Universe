from __future__ import annotations

import asyncio
import time
from typing import Protocol

from app.security.prompt_isolation import scrub_credentials

from .budget import BudgetLedger
from .cache import TenantCache
from .circuit import CircuitBreaker
from .config import RuntimeConfig
from .contracts import CompletionRequest, CompletionResult, ProviderEndpoint
from .dedupe import RequestDeduper
from .response_cache import CachePolicy, SafeResponseCache
from .errors import ProviderUnavailable, SchemaViolation
from .health import ProviderHealth
from .key_pool import SafeKeyPool
from .retry import with_retries
from .router import CapabilityRouter
from .structured import validate_json
from .telemetry import TraceRecorder


class ProviderTransport(Protocol):
    async def complete(self, request: CompletionRequest, endpoint: ProviderEndpoint, api_key: str | None): ...
    async def health(self) -> bool: ...


class HardenedGateway:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.health = ProviderHealth()
        self.router = CapabilityRouter(self.health)
        self.budget = BudgetLedger(self.config.default_budget_usd)
        self.cache = TenantCache()
        # TASK-INF-006: completions are cached through the context-safe
        # response cache (per-class TTLs, context fingerprints, template
        # matching, generation invalidation). TenantCache remains for
        # generic tenant payloads; it no longer serves completions.
        self.response_cache = SafeResponseCache(
            CachePolicy(
                public_ttl_seconds=float(self.config.resp_cache_public_ttl_seconds),
                contextual_ttl_seconds=float(self.config.resp_cache_contextual_ttl_seconds),
                personalised_ttl_seconds=float(self.config.resp_cache_personalised_ttl_seconds),
                template_ttl_seconds=float(self.config.resp_cache_template_ttl_seconds),
                stochastic_ttl_cap_seconds=float(self.config.resp_cache_stochastic_ttl_cap_seconds),
                max_entries=self.config.resp_cache_max_entries,
                policy_version=self.config.resp_cache_policy_version,
                allow_personalised_storage=self.config.resp_cache_allow_personalised_storage,
            )
        )
        self.dedupe = RequestDeduper()
        self.trace = TraceRecorder()
        self.transports: dict[str, ProviderTransport] = {}
        self.keys: dict[str, SafeKeyPool] = {}
        self.breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def register(self, endpoint: ProviderEndpoint, transport: ProviderTransport, keys: list[str] | None = None) -> None:
        self.router.register(endpoint)
        self.transports[endpoint.provider] = transport
        self.keys[endpoint.provider] = SafeKeyPool(endpoint.provider, keys)
        self.breakers.setdefault(endpoint.provider, CircuitBreaker())

    def _estimate_cost(self, request: CompletionRequest, endpoint: ProviderEndpoint) -> float:
        chars = sum(len(m.content) if isinstance(m.content, str) else len(str(m.content)) for m in request.messages)
        prompt = max(1, chars // 4)
        out = request.max_tokens or 512
        return (prompt / 1000) * endpoint.cost_per_1k_input + (out / 1000) * endpoint.cost_per_1k_output

    def _cache_plan(self, request: CompletionRequest) -> dict | None:
        """Build the safe-cache plan for a request, or None when the
        request must not be cached at all (not flagged cacheable, or
        streaming). The plan carries the context classification and
        fingerprint that bind a cached answer to the context it was
        produced under (TASK-INF-006)."""
        if not request.cacheable or request.stream:
            return None
        prompt_text = " ".join(
            m.content for m in request.messages if isinstance(m.content, str)
        )
        context_class = self.response_cache.classify(
            declared=request.context_class,
            principal_id=request.principal_id,
            context=request.context,
            prompt_text=prompt_text,
        )
        stochastic = request.temperature > 0
        top_p = request.extra.get("top_p") if isinstance(request.extra, dict) else None
        if isinstance(top_p, (int, float)) and not isinstance(top_p, bool) and top_p < 1:
            stochastic = True
        return {
            "namespace": f"gateway:{request.tenant_id}",
            "payload": {
                "model": request.model,
                "messages": [m.__dict__ for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "schema": request.response_schema,
                "capabilities": sorted(capability.value for capability in request.capabilities),
                "extra": request.extra,
            },
            "context_class": context_class,
            "context_fingerprint": SafeResponseCache.context_fingerprint(
                request.context, request.principal_id
            ),
            "stochastic": stochastic,
        }

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.trace.emit("admission", request.request_id, model=request.model, tenant=request.tenant_id)
        if request.stream:
            raise ValueError("Use stream() for streaming requests")

        cache_plan = self._cache_plan(request)
        # Cache hits must remain available while providers are unhealthy and must not
        # reserve budget. Validate cached values just as strictly as fresh responses;
        # evict malformed entries and recompute rather than trusting stale payloads.
        if cache_plan:
            lookup = self.response_cache.lookup(
                namespace=cache_plan["namespace"],
                payload=cache_plan["payload"],
                context_class=cache_plan["context_class"],
                context_fingerprint=cache_plan["context_fingerprint"],
                template_id=request.template_id,
                template_slots=request.template_slots,
                stochastic=cache_plan["stochastic"],
            )
            if lookup.hit:
                try:
                    cached_fields = dict(lookup.value)
                    cached_fields["cached"] = True
                    cached_result = CompletionResult(**cached_fields)
                    if request.response_schema is not None:
                        validate_json(cached_result.text, dict(request.response_schema))
                except (TypeError, ValueError, SchemaViolation):
                    self.response_cache.delete(lookup.key)
                else:
                    self.trace.emit(
                        "cache_hit",
                        request.request_id,
                        cached_result.provider,
                        cached_result.model,
                    )
                    return cached_result

        decision = self.router.choose(request)
        ep = decision.endpoint
        estimate = self._estimate_cost(request, ep)

        # One provider execution must own one reservation and one spend
        # reconciliation. Reserving/reconciling around dedupe.run() charges every
        # waiter for the same upstream call, even though the provider ran once.
        dedupe_key = self.dedupe.fingerprint(
            {
                "tenant_id": request.tenant_id,
                "request": request.__dict__,
            }
        )

        async def execute_and_account() -> CompletionResult:
            self.budget.reserve(request.tenant_id, estimate)
            reservation_held = True
            try:
                result = await self._execute(request, ep)

                # Validation gates caching, not billing: an invalid provider response
                # can still incur real cost. Reconcile it exactly once in this shared
                # operation before propagating the contract failure to every waiter.
                if request.response_schema is not None:
                    try:
                        validate_json(result.text, dict(request.response_schema))
                    except BaseException:
                        self.budget.reconcile(request.tenant_id, estimate, result.cost_usd)
                        reservation_held = False
                        raise

                self.budget.reconcile(request.tenant_id, estimate, result.cost_usd)
                reservation_held = False
                self.trace.emit(
                    "completed",
                    request.request_id,
                    result.provider,
                    result.model,
                    latency=result.latency_seconds,
                    tokens=result.total_tokens,
                    cost=result.cost_usd,
                )
                return result
            except BaseException:
                # The shared operation itself is shielded from individual waiters.
                # If every waiter leaves, the deduper cancels this factory and any
                # outstanding reservation is released here.
                if reservation_held:
                    self.budget.reconcile(request.tenant_id, estimate, 0.0)
                raise

        result = await self.dedupe.run(dedupe_key, execute_and_account)

        if cache_plan:
            self.response_cache.store(
                namespace=cache_plan["namespace"],
                payload=cache_plan["payload"],
                value=result.__dict__,
                context_class=cache_plan["context_class"],
                context_fingerprint=cache_plan["context_fingerprint"],
                principal_id=request.principal_id,
                original_latency_seconds=result.latency_seconds,
                template_id=request.template_id,
                template_slots=request.template_slots,
                stochastic=cache_plan["stochastic"],
            )
        return result

    async def _execute(self, request: CompletionRequest, ep: ProviderEndpoint) -> CompletionResult:
        provider = ep.provider
        transport = self.transports.get(provider)
        breaker = self.breakers.get(provider)
        if transport is None:
            raise ProviderUnavailable(f"No transport registered for {provider}")
        if breaker and not breaker.allow():
            raise ProviderUnavailable(f"Circuit open for {provider}")
        pool = self.keys.get(provider)
        key = pool.choose() if pool else None

        async def call():
            started = time.perf_counter()
            try:
                raw = await asyncio.wait_for(
                    transport.complete(request, ep, key),
                    timeout=request.timeout_seconds or self.config.request_timeout_seconds,
                )
                latency = time.perf_counter() - started
                self.health.success(provider, latency)
                self.router.record(ep, True, latency)
                breaker and breaker.success()
                return raw
            except asyncio.CancelledError:
                # A cancelled recovery probe must not leave the provider breaker
                # permanently half-open with its sole permit held.
                breaker and breaker.release_probe()
                raise
            except Exception as exc:
                latency = time.perf_counter() - started
                scrubbed = scrub_credentials(str(exc))
                self.health.failure(provider, scrubbed, latency)
                self.router.record(ep, False, latency)
                breaker and breaker.failure()
                pool and key and pool.quarantine(key)
                raise

        return await with_retries(call, self.config.max_retries)
