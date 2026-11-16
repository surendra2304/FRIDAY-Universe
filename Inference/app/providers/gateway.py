"""Provider Gateway Subsystem for Inference.

Features:
- Global Key Pool with Round-Robin key rotation per provider.
- Per-Provider Rate Limiting (Token Bucket / Concurrency Limiter) with complete provider isolation.
- Automatic 60-second key blacklisting/quarantine on 429/503.
- Provider Health Tracking integration.
- Dynamic Capability-Based OpenRouter fallback.
"""

import asyncio
import math
import os
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.core.policies import ProviderSwitchingPolicy, SwitchReason
from app.providers.base import (
    ProviderRequest,
    ProviderResponse,
)
from app.providers.errors import (
    GatewayError,
    ProviderUnconfiguredError,
    RateLimitError,
    TemporaryUnavailableError,
    normalize_provider_exception,
)
from app.providers.errors import TimeoutError as ProviderTimeoutError
from app.providers.failover_log import failover_log
from app.providers.health import provider_health_tracker
from app.providers.quota_ledger import quota_ledger
from app.security.prompt_isolation import scrub_credentials
from app.utils.logger import logger

#: Providers that are legitimately able to serve a request with no credential at
#: all — self-hosted servers and transport shims that carry their own auth.
#: Everything else needs a key from ``settings`` before it can do anything.
KEYLESS_PROVIDERS: frozenset[str] = frozenset({"local", "litellm", "llamacpp", "vllm", "sglang", "ollama"})


def provider_has_credentials(prov_name: str) -> bool:
    """Return whether ``prov_name`` could possibly serve a request right now.

    Used as a pre-flight gate. Note that this asks only about *configured
    credentials*, not about health: an unhealthy-but-configured provider is still
    worth attempting (see the circuit-breaker semantics in
    ``ProviderHealthTracker``), whereas an unconfigured one can never answer.
    """
    normalized = prov_name.lower().strip()
    if normalized in KEYLESS_PROVIDERS:
        return True
    if normalized.startswith("custom-"):
        # TASK-IG-INF-02: an enabled custom endpoint is servable by
        # construction — keyed endpoints were disabled at parse time
        # when their api_key_env was unset, and keyless endpoints are
        # an explicit operator choice (the `local` semantics). A
        # disabled or unknown custom name is NOT servable.
        from app.providers.custom_endpoints import custom_endpoint_by_provider

        return custom_endpoint_by_provider(normalized) is not None
    try:
        return bool(settings.get_provider_keys(normalized))
    except Exception:  # noqa: BLE001 - configuration lookup must never break routing
        return False


#: TASK-REL-047 (decided in TASK-REL-045's tuning table, INF-004 evidence):
#: Groq's free tier caps a request at 8,000 tokens per minute, and prompts of
#: 9,876–11,207 tokens drew deterministic HTTP 413s (≥6 in one measured hour).
#: The chat/completions path steers long prompts away from Groq at selection
#: time (TASK-REL-043's long-context ranking), but the unified/agent-role
#: path had no equivalent guard, so oversized prompts reached Groq rungs
#: directly and burned ladder time on a rung that could never answer. The
#: guard therefore lives here, in the gateway every path traverses: above
#: this many estimated prompt tokens, Groq rungs are skipped and the request
#: routes to the remaining ladder. 7,000 leaves response headroom under the
#: 8,000 cap, per the REL-045 decision.
GROQ_PROMPT_TOKEN_LIMIT = 7000


def estimate_prompt_tokens(request: ProviderRequest) -> int:
    """Estimate a request's prompt size in tokens (chars // 4).

    The same estimator the provider adapters use for their own token
    accounting (total_chars // 4 over message contents), plus the system
    instruction, which the provider also counts against the request.
    """
    chars = len(request.system_instruction or "")
    for msg in request.messages:
        chars += len(msg.content or "")
    return max(1, chars // 4)


def groq_prompt_over_limit(request: ProviderRequest) -> bool:
    """Whether this prompt must not be sent to a Groq rung (TASK-REL-047)."""
    return estimate_prompt_tokens(request) > GROQ_PROMPT_TOKEN_LIMIT


def nvidia_rung_enabled() -> bool:
    """Whether the NVIDIA rung may be attempted (TASK-REL-047).

    Disabled by default: the configured NVIDIA model id returns HTTP 404
    ("function id not found") on both fleet accounts (TASK-INF-004;
    TASK-SEN-003 counted 62 dead-function retries), so every ladder attempt
    on the rung burns request budget on a provider that cannot answer.
    Re-enable only by setting INFERENCE_NVIDIA_RUNG_ENABLED=true after an
    INF-003-W5-style metadata probe verifies a live model id. The adapter
    code itself is untouched — this gate is configuration, not deletion.
    """
    return bool(settings.INFERENCE_NVIDIA_RUNG_ENABLED)


def bytez_rung_enabled() -> bool:
    """Whether the Bytez rung may be attempted (TASK-IG2-INF-01).

    Disabled by default, on the same doctrine as the NVIDIA rung: Bytez's
    documented $0 tier (≤7B open models, 1 concurrent request) states no
    recurring free allowance, so its usable free volume is *unproven* until
    the empirical probe in ``app.providers.bytez_probe`` has measured it
    across repeated runs. Enable only by setting
    INFERENCE_BYTEZ_RUNG_ENABLED=true after reading probe reports — and
    even then Bytez carries no declared quota-ledger limit until an
    operator declares one from that evidence.
    """
    return os.environ.get("INFERENCE_BYTEZ_RUNG_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _is_empty_completion(resp: ProviderResponse) -> bool:
    """Whether a response is a structural non-answer rather than an answer.

    Adapters return ``finish_reason="empty"`` exactly when the upstream body
    carried no candidates/choices at all (Gemini safety blocks and free-tier
    OpenAI-compatible responses do this). That is a provider failure wearing a
    success shape: the text is empty because nothing was generated. Treating
    it as success stops the fallback ladder and lets the API layers present a
    confident empty answer (TASK-INF-008 drill: /v1/friday/ask returned
    HTTP 200, answer="", confidence 0.7, when every provider was empty).
    """
    return (resp.finish_reason or "").strip().lower() == "empty" and not (resp.content or "").strip()


def _request_timeout_budget(request: ProviderRequest) -> float:
    """Validate the finite positive deadline shared by primary and fallback work."""
    value = request.extra_params.get("timeout", settings.REQUEST_TIMEOUT or 60.0)
    if isinstance(value, bool):
        raise ValueError("request timeout must be a finite positive number")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("request timeout must be a finite positive number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("request timeout must be a finite positive number")
    return timeout


def _quota_outcome(err: BaseException | None) -> str:
    """Map a typed gateway error to a quota-ledger outcome label."""
    if isinstance(err, RateLimitError):
        return "rate_limited"
    if isinstance(err, ProviderTimeoutError):
        return "timeout"
    if isinstance(err, TemporaryUnavailableError):
        return "unavailable"
    return "error"


def _quota_record(
    provider: str,
    model: str | None,
    api_key: str | None,
    outcome: str,
    response: ProviderResponse | None = None,
) -> None:
    """Best-effort free-tier quota accounting (TASK-INF-007).

    Every provider attempt the gateway makes is recorded against the
    declared free-tier limits (see app.providers.quota_ledger). Accounting
    must never break serving, so any failure here is swallowed; the ledger
    itself also swallows its own errors.
    """
    try:
        quota_ledger.record_response(
            provider=provider, model=model, api_key=api_key, outcome=outcome, response=response
        )
    except Exception:  # noqa: BLE001 - accounting must never break serving
        pass


class KeyPool:
    """Manages round-robin key rotation and 60-second quarantines for a provider."""

    def __init__(self, provider_name: str, keys: list[str] | None = None, quarantine_seconds: float = 60.0) -> None:
        self.provider_name = provider_name.lower().strip()
        self._keys: list[str] = [k.strip() for k in (keys or []) if k.strip()]
        self._index: int = 0
        self._quarantined_until: dict[str, float] = {}  # key -> timestamp until quarantined
        self._quarantine_seconds = quarantine_seconds
        self._lock = threading.RLock()

    def set_keys(self, keys: list[str]) -> None:
        with self._lock:
            self._keys = [k.strip() for k in keys if k.strip()]
            self._index = 0

    @property
    def total_keys_count(self) -> int:
        with self._lock:
            return len(self._keys)

    def get_active_keys_count(self) -> int:
        with self._lock:
            now = time.monotonic()
            return sum(1 for k in self._keys if self._quarantined_until.get(k, 0) <= now)

    def get_quarantined_keys_count(self) -> int:
        with self._lock:
            now = time.monotonic()
            return sum(1 for k in self._keys if self._quarantined_until.get(k, 0) > now)

    def choose(self) -> str | None:
        """
        Returns the next available un-quarantined key in round-robin sequence.
        Fails closed: if all keys are quarantined, returns None (never hammers quarantined keys).
        """
        with self._lock:
            if not self._keys:
                return None
            now = time.monotonic()
            for _ in range(len(self._keys)):
                key = self._keys[self._index % len(self._keys)]
                self._index = (self._index + 1) % len(self._keys)
                if self._quarantined_until.get(key, 0) <= now:
                    return key
            return None

    async def get_next_key(self) -> str | None:
        return self.choose()

    def quarantine(self, key: str, duration_seconds: float | None = None) -> None:
        with self._lock:
            dur = duration_seconds if duration_seconds is not None else self._quarantine_seconds
            self._quarantined_until[key] = time.monotonic() + dur
            masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
            logger.warning(
                "KEY POOL: Quarantining key '%s' on provider '%s' for %.0fs", masked_key, self.provider_name, dur
            )

    async def quarantine_key(self, key: str, duration_seconds: float = 60.0) -> None:
        self.quarantine(key, duration_seconds)

    def next_available_delay(self) -> float:
        with self._lock:
            if not self._keys:
                return float("inf")
            now = time.monotonic()
            delays = [self._quarantined_until.get(k, 0) - now for k in self._keys]
            return max(0.0, min(delays))


class ProviderRateLimiter:
    """Per-provider concurrency-safe token bucket and concurrency limiter."""

    def __init__(self, provider_name: str, requests_per_second: float = 5.0, max_concurrency: int = 4) -> None:
        self.provider_name = provider_name
        self.rate = max(requests_per_second, 0.001)
        self.capacity = float(max(max_concurrency * 2, 2))
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.max_concurrency = max_concurrency
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(max_concurrency)

    async def acquire(self, cost: float = 1.0) -> None:
        """Acquire a concurrency slot and a rate-limit token, without leaking either.

        Runaway-safe: the concurrency slot is taken before waiting for a token, but
        cancellation or timeout returns the slot unless the caller receives it.
        """
        # Validate before taking a semaphore slot. Invalid or impossible costs must not
        # corrupt token accounting or hold a concurrency slot while waiting forever.
        if (
            isinstance(cost, bool)
            or not isinstance(cost, (int, float))
            or not math.isfinite(cost)
            or cost <= 0
        ):
            raise ValueError("cost must be a finite positive number")
        if cost > self.capacity:
            raise ValueError(
                f"cost ({cost}) cannot exceed token bucket capacity ({self.capacity})"
            )
        await self._sem.acquire()
        handed_over = False
        try:
            while True:
                delay = 0.0
                async with self._lock:
                    now = time.monotonic()
                    self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                    self.updated = now
                    if self.tokens >= cost:
                        self.tokens -= cost
                        handed_over = True
                        return
                    delay = (cost - self.tokens) / self.rate
                # Never hold lock while sleeping!
                await asyncio.sleep(delay)
        finally:
            if not handed_over:
                # The caller never received the limiter, so it cannot release this slot.
                self._sem.release()

    def release(self) -> None:
        """Release the concurrency semaphore slot."""
        self._sem.release()


class ModelGateway:
    """
    Central gateway coordinating LLM calls with:
    - Per-provider rate limiting & isolation.
    - Round-robin key rotation with 60s quarantine on 429/503.
    - Provider health tracking.
    - Dynamic capability-based OpenRouter fallback.
    """

    def __init__(self) -> None:
        self.key_pools: dict[str, KeyPool] = {}
        self.rate_limiters: dict[str, ProviderRateLimiter] = {}
        self.health_tracker = provider_health_tracker
        self._apply_key_vault()
        self._initialize_pools()

    def _apply_key_vault(self) -> None:
        """Fill still-empty key fields from the encrypted vault (TASK-IG2-INF-02).

        Runs before pools are built so vault-stored keys are indistinguishable
        from environment keys downstream. Environment values always win, and
        each vault entry fills only its own settings field, so the FRIDAY /
        Inference / THIRD_PARTY_* pools stay separate. A vault failure must
        never break gateway startup: it is logged (entry names only, never
        values) and serving continues with whatever the environment provided.
        """
        try:
            from app.providers.key_vault import apply_vault_to_settings

            report = apply_vault_to_settings(settings)
            if report["applied"]:
                logger.info(
                    "GATEWAY: Loaded %d provider key field(s) from the encrypted key vault.",
                    len(report["applied"]),
                )
            for err in report["errors"]:
                logger.warning("GATEWAY: Key vault entry '%s' could not be applied: %s", err["name"], err["error"])
        except Exception:  # noqa: BLE001 - vault must never break gateway startup
            logger.warning("GATEWAY: Key vault application failed; continuing with environment keys only.")

    def _initialize_pools(self) -> None:
        """Initialize key pools and rate limiters for all known providers."""
        all_providers = ["gemini", "groq", "cerebras", "mistral", "openrouter", "cohere", "huggingface", "nvidia", "bytez"]
        if settings.LOCAL_ENABLED:
            # Self-hosted tier: keyless, unmetered, and therefore the correct final
            # rung of the fallback ladder. Registered only when enabled so that a
            # deployment with no local server never pays a connection-refused
            # penalty on every fallback attempt.
            all_providers.append("local")
        for prov in all_providers:
            keys = settings.get_provider_keys(prov)
            self.key_pools[prov] = KeyPool(prov, keys)
            # Default rate limits per provider
            if prov == "local":
                # A local server has finite compute slots but **no quota**, so the
                # limiting factor must be concurrency, never rate. An earlier revision
                # set this to 10 requests/second by analogy with a cloud vendor; because
                # one panel request fans out to 8+ model calls, the token bucket drained
                # after two requests and every subsequent request ran at 1/rate per call.
                # Measured: p50 latency stepped from 0.11s to 0.80s and stayed there, so
                # the zero-cost tier became the slowest tier in the system.
                self.rate_limiters[prov] = ProviderRateLimiter(
                    prov,
                    requests_per_second=float(settings.LOCAL_MAX_RPS),
                    max_concurrency=int(settings.LOCAL_MAX_CONCURRENCY),
                )
                continue
            rpm = 10.0 if prov in ("gemini", "cohere") else 20.0
            self.rate_limiters[prov] = ProviderRateLimiter(prov, requests_per_second=rpm / 60.0, max_concurrency=4)

        # TASK-IG-INF-02: operator-configured custom endpoints get their
        # own pools, keyed ONLY by each endpoint's own api_key_env value —
        # never via settings.get_provider_keys, which merges the
        # THIRD_PARTY_* and fallback pools and would break key isolation.
        from app.providers.custom_endpoints import enabled_custom_endpoints

        for endpoint in enabled_custom_endpoints():
            keys = [endpoint.api_key] if endpoint.api_key else []
            self.key_pools[endpoint.provider_name] = KeyPool(endpoint.provider_name, keys)
            self.rate_limiters[endpoint.provider_name] = ProviderRateLimiter(
                endpoint.provider_name, requests_per_second=20.0 / 60.0, max_concurrency=4
            )

    def refresh_keys(self) -> None:
        """Reload keys from environment/settings."""
        for prov, pool in self.key_pools.items():
            if prov.startswith("custom-"):
                # TASK-IG-INF-02: custom pools are re-resolved from the
                # endpoint registry, never from the pooled key sets.
                from app.providers.custom_endpoints import custom_endpoint_by_provider

                endpoint = custom_endpoint_by_provider(prov)
                pool.set_keys([endpoint.api_key] if endpoint and endpoint.api_key else [])
                continue
            keys = settings.get_provider_keys(prov)
            pool.set_keys(keys)

    def get_provider_health(self, provider_name: str) -> Any:
        """Return live health metrics for a provider."""
        pool = self.key_pools.get(provider_name.lower())
        if pool:
            self.health_tracker.update_key_counts(
                provider_name,
                active_count=pool.get_active_keys_count(),
                quarantined_count=pool.get_quarantined_keys_count(),
            )
        return self.health_tracker.get_provider_health(provider_name)

    async def execute(
        self, provider_name: str, request: ProviderRequest, capability: str = "general", stage_name: str = "general"
    ) -> ProviderResponse:
        """
        Executes an LLM request through the gateway:
        1. Selects key from round-robin pool with fail-closed quarantine semantics.
        2. Applies isolated per-provider rate limiter without holding locks during sleep.
        3. Enforces an overall request deadline across primary retries and fallbacks.
        4. Retries across alternate keys only for transient errors (429/503/timeout).
        5. If all keys exhausted/quarantined, routes through capability-matched fallback.
        6. Updates health metrics and records provenance.
        """
        timeout_budget = _request_timeout_budget(request)
        deadline = time.monotonic() + timeout_budget
        # Reserve the tail of the budget for the fallback ladder. Without this, a
        # primary provider that times out (the single most common provider failure)
        # consumes the entire deadline, `_execute_dynamic_fallback` finds no time
        # remaining, and re-raises the original error — so the ladder is unreachable
        # precisely when it is needed. The reservation is what turns "fallbacks are
        # configured" into "fallbacks actually run".
        #
        # TASK-INF-010: the fraction alone lets a HANGING primary hold the request
        # for 0.6 x budget (36s at the 60s default) before the ladder starts —
        # measured live 2026-11-16, when Gemini's failure mode from Server 1 was
        # the hang (11/11 gateway attempts timed out, zero 429s, quota buckets
        # <=10% used): a 24.3s-to-503 incident, a 43.9s repro whose journal line
        # reads "timed out after 36.1s", and 38-67s INF-009 probe latencies. The
        # absolute cap bounds any single primary attempt; the ladder keeps the
        # rest of the budget either way.
        primary_slice = min(
            timeout_budget * settings.PRIMARY_ATTEMPT_FRACTION,
            settings.PRIMARY_ATTEMPT_MAX_SECONDS,
        )
        primary_deadline = time.monotonic() + primary_slice

        # TASK-IG2-INF-04: rule-based token compression (OmniRoute pattern),
        # applied once here — the gateway every path traverses — so every rung
        # of the ladder sends the compressed prompt. Short prompts bypass
        # inside the compressor, and a compression failure must never break
        # serving: any error falls back to the original request.
        try:
            from app.providers.token_compression import compress_provider_request

            request = compress_provider_request(request)
        except Exception:  # noqa: BLE001 - compression must never break serving
            logger.warning("GATEWAY: Token compression failed; sending the original prompt.")

        # TASK-INF-010: mark the call as gateway-governed (set after compression,
        # which may return a copied request) so adapters skip their own pacing
        # sleeps — under a deadline the gateway owns pacing (key quarantine +
        # its inter-key sleep), and an adapter-level sleep is paid a second
        # time inside every fallback rung.
        request.deadline_monotonic = deadline

        prov_name = provider_name.lower().strip()
        if prov_name == "litellm":
            from app.providers.gateway_litellm import execute_via_litellm

            start_time = time.perf_counter()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Request deadline ({timeout_budget:.1f}s) exceeded before LiteLLM call.")
            try:
                resp = await asyncio.wait_for(execute_via_litellm(request), timeout=remaining)
                if _is_empty_completion(resp):
                    raise TemporaryUnavailableError(
                        "LiteLLM transport returned an empty completion "
                        "(no candidates/choices in the upstream response).",
                        provider="litellm",
                        model=request.model,
                    )
                latency = time.perf_counter() - start_time
                self.health_tracker.record_success("litellm", latency)
                _quota_record("litellm", request.model, None, "success", resp)
                return resp
            except Exception as exc:
                latency = time.perf_counter() - start_time
                typed_err = normalize_provider_exception(exc, provider="litellm", model=request.model)
                self.health_tracker.record_failure("litellm", str(exc), latency_seconds=latency)
                _quota_record("litellm", request.model, None, _quota_outcome(typed_err))
                raise typed_err from exc

        # Air-gapped / offline mode. When LOCAL_PREFERRED is set, the self-hosted tier
        # answers first and no outbound provider call is attempted at all — which is
        # what makes this usable as a privacy control (nothing leaves the machine) and
        # as an offline development mode, not merely as a cost optimisation.
        local_tier_attempted = False
        if settings.LOCAL_PREFERRED and settings.LOCAL_ENABLED and prov_name != "local":
            local_tier_attempted = True
            local_resp = await self._execute_local_tier(prov_name, request, capability, None, deadline)
            if local_resp is not None:
                return local_resp
            logger.warning(
                "GATEWAY: LOCAL_PREFERRED is enabled but the self-hosted tier failed; "
                "falling through to cloud providers. Set LOCAL_ENABLED only when a local "
                "server is actually running if you need a hard guarantee of no egress."
            )

        # TASK-REL-047 routing guards. Both escalate to the fallback ladder
        # with the reason recorded, exactly like the unconfigured-provider
        # gate below: the request is still served by the remaining rungs,
        # and if nothing can answer, the caller receives this exact error.
        if prov_name == "groq" and groq_prompt_over_limit(request):
            over_limit = TemporaryUnavailableError(
                f"Prompt estimated at {estimate_prompt_tokens(request)} tokens exceeds the "
                f"{GROQ_PROMPT_TOKEN_LIMIT}-token Groq guard (Groq free-tier cap is 8,000 TPM); "
                "routing away from Groq rungs for this request.",
                provider=prov_name,
                model=request.model,
            )
            logger.warning(
                "GATEWAY: Prompt over the Groq size guard (~%d tokens > %d); "
                "skipping the Groq primary and routing to the fallback ladder.",
                estimate_prompt_tokens(request),
                GROQ_PROMPT_TOKEN_LIMIT,
            )
            return await self._execute_dynamic_fallback(
                failed_provider=prov_name,
                request=request,
                capability=capability,
                stage_name=stage_name,
                last_error=over_limit,
                deadline=deadline,
                skip_local_tier=local_tier_attempted,
            )

        if prov_name == "nvidia" and not nvidia_rung_enabled():
            rung_disabled = ProviderUnconfiguredError(
                "Provider 'nvidia' is disabled by configuration "
                "(INFERENCE_NVIDIA_RUNG_ENABLED is off; TASK-REL-047); skipping without an attempt.",
                provider=prov_name,
                model=request.model,
            )
            logger.warning(
                "GATEWAY: NVIDIA rung is disabled by configuration; "
                "escalating to the fallback ladder without an attempt."
            )
            return await self._execute_dynamic_fallback(
                failed_provider=prov_name,
                request=request,
                capability=capability,
                stage_name=stage_name,
                last_error=rung_disabled,
                deadline=deadline,
                skip_local_tier=local_tier_attempted,
            )

        if prov_name == "bytez" and not bytez_rung_enabled():
            # TASK-IG2-INF-01: Bytez's free volume is unproven until the
            # quota probe measures it; the rung stays off by default so no
            # fleet traffic can silently become credit-metered (paid) spend.
            bytez_disabled = ProviderUnconfiguredError(
                "Provider 'bytez' is disabled by configuration "
                "(INFERENCE_BYTEZ_RUNG_ENABLED is off; TASK-IG2-INF-01 — free-tier "
                "volume unproven, see app.providers.bytez_probe); skipping without an attempt.",
                provider=prov_name,
                model=request.model,
            )
            logger.warning(
                "GATEWAY: Bytez rung is disabled by configuration; "
                "escalating to the fallback ladder without an attempt."
            )
            return await self._execute_dynamic_fallback(
                failed_provider=prov_name,
                request=request,
                capability=capability,
                stage_name=stage_name,
                last_error=bytez_disabled,
                deadline=deadline,
                skip_local_tier=local_tier_attempted,
            )

        # Pre-flight credential gate. An unconfigured provider cannot succeed, so the
        # only effects of attempting it are (a) latency, and (b) a bogus failure
        # recorded against that provider's health — which is how a fresh deployment
        # with one working provider ends up believing that all of them are down.
        # Raising here, before the rate limiter, keeps the shared per-provider queue
        # free for calls that can actually be answered.
        if not provider_has_credentials(prov_name):
            unconfigured = ProviderUnconfiguredError(
                f"Provider '{prov_name}' has no configured credential; skipping without an attempt.",
                provider=prov_name,
                model=request.model,
            )
            # Escalate to the fallback ladder instead of raising here. Raising at this point
            # skipped the ladder entirely, and the ladder's terminal rung is the self-hosted
            # tier: [FACT] measured with LOCAL_ENABLED=true, a healthy local server answering
            # /v1/models, and no cloud keys, every /v1/ask came back DEGRADED with
            # "no configured credential" while the local model sat idle. The ladder skips
            # unconfigured candidates itself and ends with ``raise last_error``, so when nothing
            # can answer the caller still receives this exact ProviderUnconfiguredError.
            return await self._execute_dynamic_fallback(
                failed_provider=prov_name,
                request=request,
                capability=capability,
                stage_name=stage_name,
                last_error=unconfigured,
                deadline=deadline,
                skip_local_tier=local_tier_attempted,
            )

        pool = self.key_pools.get(prov_name)
        if not pool or pool.total_keys_count == 0:
            keys = settings.get_provider_keys(prov_name)
            if keys:
                if not pool:
                    pool = KeyPool(prov_name, keys)
                    self.key_pools[prov_name] = pool
                else:
                    pool.set_keys(keys)

        limiter = self.rate_limiters.get(prov_name)
        if not limiter:
            limiter = ProviderRateLimiter(prov_name)
            self.rate_limiters[prov_name] = limiter

        # Fail closed immediately if all keys are quarantined
        last_error: GatewayError | Exception | None = None
        if pool and pool.total_keys_count > 0 and pool.get_active_keys_count() == 0:
            logger.warning(
                "KEY POOL: All %d keys for '%s' are quarantined. Failing closed.", pool.total_keys_count, prov_name
            )
            last_error = TemporaryUnavailableError(
                f"All credentials for provider '{prov_name}' are currently quarantined.", provider=prov_name
            )
            attempts = 0
        else:
            attempts = max(1, pool.total_keys_count if pool else 1)
            last_error = None

        current_key = None

        for _ in range(attempts):
            remaining = primary_deadline - time.monotonic()
            if remaining <= 0:
                # The primary slice is spent. Escalate to the ladder rather than
                # raising: the fallback budget is still intact by construction.
                last_error = last_error or TemporaryUnavailableError(
                    f"Primary attempt slice ({primary_slice:.1f}s of "
                    f"{timeout_budget:.1f}s) exhausted for provider '{prov_name}' before a call could be made.",
                    provider=prov_name,
                )
                logger.warning(
                    "GATEWAY: Primary attempt slice exhausted for '%s' before a call was made; "
                    "escalating to the fallback ladder.",
                    prov_name,
                )
                break

            current_key = pool.choose() if pool else None
            if pool and pool.total_keys_count > 0 and current_key is None:
                # No active key available
                break

            start_time = time.perf_counter()

            try:
                import app.providers

                provider_instance = (
                    app.providers.get_provider(prov_name, api_key=current_key)
                    if current_key
                    else app.providers.get_provider(prov_name)
                )

                # Rate-limit acquisition consumes the same request budget as the
                # provider call. Bound the wait itself, then recalculate remaining
                # primary time so a slow token/concurrency wait cannot start a call after
                # the primary deadline has already expired.
                await asyncio.wait_for(limiter.acquire(), timeout=remaining)
                try:
                    call_timeout = primary_deadline - time.monotonic()
                    if call_timeout <= 0:
                        raise asyncio.TimeoutError("Primary deadline expired while acquiring provider capacity")
                    resp = await asyncio.wait_for(provider_instance.generate(request), timeout=call_timeout)
                finally:
                    limiter.release()

                latency = time.perf_counter() - start_time
                if _is_empty_completion(resp):
                    # A structural non-answer (no candidates/choices upstream).
                    # Like a timeout, this is a property of the provider/model
                    # response, not of the credential: do not quarantine the key
                    # and do not retry the same provider — escalate to the ladder.
                    self.health_tracker.record_failure(
                        prov_name,
                        "empty completion (no candidates/choices in upstream response)",
                        is_503=True,
                        latency_seconds=latency,
                    )
                    last_error = TemporaryUnavailableError(
                        f"Provider '{prov_name}' returned an empty completion "
                        "(no candidates/choices in the upstream response).",
                        provider=prov_name,
                        model=request.model,
                    )
                    logger.warning(
                        "GATEWAY: Provider '%s' returned an empty completion; "
                        "escalating to the fallback ladder instead of serving it.",
                        prov_name,
                    )
                    break
                self.health_tracker.record_success(prov_name, latency)
                _quota_record(prov_name, request.model, current_key, "success", resp)
                return resp

            except (asyncio.TimeoutError, TimeoutError) as exc:
                # A timeout is the most likely provider failure and must NOT abort the
                # request: six other providers may be perfectly healthy. Record it,
                # then break out of the key loop so the code below escalates to
                # _execute_dynamic_fallback with the reserved budget. Retrying the
                # same provider on another key would not help — a timeout is a
                # property of the provider or the prompt, not of the credential.
                latency = time.perf_counter() - start_time
                self.health_tracker.record_failure(
                    prov_name,
                    f"timeout after {latency:.2f}s",
                    is_503=True,
                    latency_seconds=latency,
                )
                _quota_record(prov_name, request.model, current_key, "timeout")
                last_error = TimeoutError(
                    f"Request deadline exceeded for provider '{prov_name}' after {latency:.1f}s"
                )
                logger.warning(
                    "GATEWAY: Provider '%s' timed out after %.1fs (%s, model=%s). Escalating to the "
                    "fallback ladder instead of failing the request.",
                    prov_name,
                    latency,
                    type(exc).__name__,
                    request.model,
                )
                break
            except Exception as exc:
                latency = time.perf_counter() - start_time
                typed_err = normalize_provider_exception(exc, provider=prov_name, model=request.model)
                last_error = typed_err
                err_str = str(exc)
                is_429 = isinstance(typed_err, RateLimitError)
                is_503 = isinstance(typed_err, TemporaryUnavailableError)

                self.health_tracker.record_failure(
                    prov_name, err_str, is_429=is_429, is_503=is_503, latency_seconds=latency
                )
                _quota_record(prov_name, request.model, current_key, _quota_outcome(typed_err))

                if pool and current_key and typed_err.is_retryable():
                    pool.quarantine(current_key, duration_seconds=60.0)
                    logger.warning(
                        "GATEWAY: Provider '%s' [%s] retrying with next key in pool. Detail: %s",
                        prov_name,
                        type(typed_err).__name__,
                        err_str.split("\n")[0],
                    )
                    remaining = primary_deadline - time.monotonic()
                    if remaining > 0.5:
                        await asyncio.sleep(min(0.5, remaining))
                    continue
                else:
                    break

        # Primary provider failed on all keys -> Fallback logic
        logger.warning(
            "GATEWAY: Primary provider '%s' failed. Initiating capability fallback for '%s'.", prov_name, capability
        )

        fallback_resp = await self._execute_dynamic_fallback(
            failed_provider=prov_name,
            request=request,
            capability=capability,
            stage_name=stage_name,
            last_error=last_error,
            deadline=deadline,
            skip_local_tier=local_tier_attempted,
        )
        return fallback_resp

    async def _execute_local_tier(
        self,
        failed_provider: str,
        request: ProviderRequest,
        capability: str,
        last_error: Exception | None,
        deadline: float | None,
    ) -> ProviderResponse | None:
        """Attempt the self-hosted tier, returning ``None`` instead of raising on failure.

        Two callers share this one implementation so the local tier cannot drift:

        * the **terminal rung of the fallback ladder** — so a request survives total
          cloud failure when a local server is available, and
        * **air-gapped mode** (``LOCAL_PREFERRED``) — where it is the *first* rung and
          the operator intends no outbound provider call at all.

        Returning ``None`` (rather than raising) lets the caller decide the
        escalation order without a try/except at every call site.
        """
        if not settings.LOCAL_ENABLED or failed_provider == "local":
            return None
        remaining = (deadline - time.monotonic()) if deadline else float(settings.REQUEST_TIMEOUT or 60.0)
        if remaining <= 0:
            logger.warning("GATEWAY: No budget left for the self-hosted tier; skipping it.")
            return None

        try:
            import app.providers

            local_prov = app.providers.get_provider("local")
            local_limiter = self.rate_limiters.get("local")
            if not local_limiter:
                # Same sizing rationale as ``_initialize_pools``: concurrency bounds the
                # host, rate must not bound throughput.
                local_limiter = ProviderRateLimiter(
                    "local",
                    requests_per_second=float(settings.LOCAL_MAX_RPS),
                    max_concurrency=int(settings.LOCAL_MAX_CONCURRENCY),
                )
                self.rate_limiters["local"] = local_limiter

            local_req = ProviderRequest(
                messages=request.messages,
                system_instruction=request.system_instruction,
                model=request.model or settings.LOCAL_MODEL,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
                response_schema=request.response_schema,
                deadline_monotonic=deadline,
            )
            acquire_timeout = (deadline - time.monotonic()) if deadline else remaining
            if acquire_timeout <= 0:
                raise TimeoutError("Deadline exceeded while waiting for the self-hosted tier limiter.")
            await asyncio.wait_for(local_limiter.acquire(), timeout=acquire_timeout)
            try:
                rem = (deadline - time.monotonic()) if deadline else remaining
                if rem <= 0:
                    raise TimeoutError("Deadline exceeded before the self-hosted tier call.")
                resp = await asyncio.wait_for(local_prov.generate(local_req), timeout=rem)
            finally:
                local_limiter.release()

            if _is_empty_completion(resp):
                # A structural non-answer from the local tier is a tier
                # failure like any other: return None so the caller keeps
                # climbing (or raises its original error) instead of serving
                # an empty "answer" from the last-resort rung.
                self.health_tracker.record_failure(
                    "local", "empty completion (no candidates/choices in upstream response)"
                )
                logger.warning("GATEWAY: Self-hosted tier returned an empty completion; treating as failure.")
                return None

            if not resp.raw_response:
                resp.raw_response = {}
            resp.raw_response["fallback_provenance"] = {
                "requested_provider": failed_provider,
                "requested_model": request.model,
                "actual_provider": "local",
                "actual_model": local_req.model,
                "capability": capability,
                "fallback_reason": scrub_credentials(str(last_error)) if last_error else "local_preferred",
            }
            self.health_tracker.record_success("local", resp.latency_seconds)
            _quota_record("local", local_req.model, None, "success", resp)
            logger.info(
                "GATEWAY: Served capability '%s' from the self-hosted tier (model=%s, %.2fs).",
                capability,
                local_req.model,
                resp.latency_seconds,
            )
            return resp
        except Exception as local_exc:  # noqa: BLE001 - the tier must never abort the request
            self.health_tracker.record_failure("local", str(local_exc))
            _quota_record("local", request.model, None, "error")
            logger.error("GATEWAY: Self-hosted tier failed: %s", str(local_exc))
            return None

    async def _execute_dynamic_fallback(
        self,
        failed_provider: str,
        request: ProviderRequest,
        capability: str,
        stage_name: str,
        last_error: Exception | None,
        deadline: float | None = None,
        skip_local_tier: bool = False,
    ) -> ProviderResponse:
        """Executes fallback with dynamic capability matching, rate-limiting, and deadline bounds.

        ``skip_local_tier`` is set by :meth:`execute` when the self-hosted tier was
        already tried as the first choice under ``LOCAL_PREFERRED``. Re-trying it at
        the end of the ladder doubles its failure count against the health tracker —
        which shortens the circuit breaker for the one provider that is supposed to
        keep the system alive — and adds a second round trip for nothing.
        """
        # TASK-IG2-INF-03: every ladder escalation is recorded in the
        # failover log served on the admin dashboard, so "what just failed
        # over, from where, and why" is answerable without journal archaeology.
        # The reason is credential-scrubbed here, exactly like the fallback
        # provenance attached to responses; the log itself never sees a key.
        failover_log.record(
            from_provider=failed_provider,
            reason=scrub_credentials(str(last_error)) if last_error else "primary_exhausted",
            model=request.model,
            capability=capability,
            stage_name=stage_name,
        )
        # 1. If failed provider is NOT openrouter, use OpenRouter with dynamic capability model discovery
        remaining = (deadline - time.monotonic()) if deadline else 60.0
        if remaining <= 0:
            if last_error:
                raise last_error
            raise TimeoutError("Request deadline exceeded before fallback execution.")

        # The OpenRouter rung needs credentials, like every other rung. It used to run without
        # them ("some free routes permit unauthenticated calls"), which meant a live
        # ``get_best_free_model`` discovery request per fallback. [FACT] once the ladder became
        # reachable for unconfigured primaries (see the pre-flight in ``execute``), that
        # discovery call to openrouter.ai added seconds to every request in an egress-blocked
        # host: test_every_declared_operation_is_routed 0.6s -> 21.5s. The primary gate already
        # refuses to attempt an unconfigured provider on exactly this reasoning.
        openrouter_pool_for_gate = self.key_pools.get("openrouter")
        openrouter_has_credentials = provider_has_credentials("openrouter") and (
            openrouter_pool_for_gate is None or openrouter_pool_for_gate.total_keys_count > 0
        )
        if failed_provider != "openrouter" and openrouter_has_credentials:
            openrouter_key: str | None = None
            dynamic_model: str | None = None
            openrouter_pool = self.key_pools.get("openrouter")
            try:
                import app.providers

                configured_keys = settings.get_provider_keys("openrouter")
                if openrouter_pool is None:
                    openrouter_pool = KeyPool("openrouter", configured_keys)
                    self.key_pools["openrouter"] = openrouter_pool
                elif openrouter_pool.total_keys_count == 0 and configured_keys:
                    openrouter_pool.set_keys(configured_keys)

                if openrouter_pool.total_keys_count:
                    openrouter_key = openrouter_pool.choose()
                    if openrouter_key is None:
                        raise TemporaryUnavailableError(
                            "All OpenRouter credentials are currently quarantined.",
                            provider="openrouter",
                        )
                    openrouter_prov = app.providers.get_provider(
                        "openrouter", api_key=openrouter_key
                    )
                else:
                    # Some free OpenRouter routes permit unauthenticated calls.
                    openrouter_prov = app.providers.get_provider("openrouter")
                if hasattr(openrouter_prov, "get_best_free_model"):
                    discovery_coro = openrouter_prov.get_best_free_model(capability)
                elif hasattr(openrouter_prov, "find_model_by_capability"):
                    discovery_coro = openrouter_prov.find_model_by_capability(capability)
                else:
                    discovery_coro = None
                if discovery_coro is None:
                    dynamic_model = "nvidia/nemotron-3.5-lightning:free"
                else:
                    # The discovery call is an upstream HTTP request like any
                    # other and must live inside the same request deadline.
                    # It was the one unbounded await in the ladder (TASK-INF-008
                    # drill: a hung discovery blew an 8s request budget past
                    # 38s; in production the only bound was the adapter's own
                    # 60s HTTP timeout). On timeout the rung fails typed and
                    # the waterfall below still gets its reserved budget.
                    remaining = (deadline - time.monotonic()) if deadline else 60.0
                    if remaining <= 0:
                        discovery_coro.close()
                        raise ProviderTimeoutError(
                            "Request deadline exceeded before OpenRouter model discovery.",
                            provider="openrouter",
                            model=request.model,
                        )
                    # When there is real budget left, discovery gets at most
                    # half of it: the waterfall below is the ladder's actual
                    # answer path and must not be starved by a metadata call
                    # (the same reservation doctrine as PRIMARY_ATTEMPT_FRACTION
                    # for primaries). With a sliver left, discovery may use it
                    # all — the waterfall would have no usable time anyway.
                    discovery_budget = remaining / 2 if remaining > 2.0 else remaining
                    try:
                        dynamic_model = await asyncio.wait_for(discovery_coro, timeout=discovery_budget)
                    except (asyncio.TimeoutError, TimeoutError) as exc:
                        raise ProviderTimeoutError(
                            f"OpenRouter model discovery exceeded the remaining request "
                            f"budget ({discovery_budget:.1f}s).",
                            provider="openrouter",
                            model=request.model,
                        ) from exc

                logger.info(
                    "GATEWAY FALLBACK: Routed to OpenRouter (Dynamic Model: %s) for capability '%s'",
                    dynamic_model,
                    capability,
                )

                fallback_req = ProviderRequest(
                    messages=request.messages,
                    system_instruction=request.system_instruction,
                    model=dynamic_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens or 1024,
                    response_schema=request.response_schema,
                    extra_params=request.extra_params,
                    deadline_monotonic=deadline,
                )

                openrouter_limiter = self.rate_limiters.get("openrouter")
                if not openrouter_limiter:
                    openrouter_limiter = ProviderRateLimiter("openrouter")
                    self.rate_limiters["openrouter"] = openrouter_limiter

                acquire_timeout = (deadline - time.monotonic()) if deadline else 60.0
                if acquire_timeout <= 0:
                    raise TimeoutError("Deadline exceeded while waiting for OpenRouter limiter.")
                await asyncio.wait_for(openrouter_limiter.acquire(), timeout=acquire_timeout)
                try:
                    rem = (deadline - time.monotonic()) if deadline else 60.0
                    if rem <= 0:
                        raise TimeoutError("Deadline exceeded before OpenRouter fallback call.")
                    resp = await asyncio.wait_for(openrouter_prov.generate(fallback_req), timeout=rem)
                finally:
                    openrouter_limiter.release()

                if _is_empty_completion(resp):
                    # Same rule as the primary path: a structural non-answer
                    # fails this rung (the except below records it) and the
                    # waterfall still gets its turn.
                    raise TemporaryUnavailableError(
                        "OpenRouter returned an empty completion "
                        "(no candidates/choices in the upstream response).",
                        provider="openrouter",
                        model=dynamic_model,
                    )

                # Attach fallback provenance
                if not resp.raw_response:
                    resp.raw_response = {}
                resp.raw_response["fallback_provenance"] = {
                    "requested_provider": failed_provider,
                    "requested_model": request.model,
                    "actual_provider": "openrouter",
                    "actual_model": dynamic_model,
                    "capability": capability,
                    "fallback_reason": scrub_credentials(str(last_error)) if last_error else "primary_exhausted",
                }

                self.health_tracker.record_success("openrouter", resp.latency_seconds)
                _quota_record("openrouter", dynamic_model, openrouter_key, "success", resp)
                return resp

            except Exception as fb_exc:
                typed_error = normalize_provider_exception(
                    fb_exc, provider="openrouter", model=request.model
                )
                self.health_tracker.record_failure(
                    "openrouter",
                    type(typed_error).__name__,
                    is_429=isinstance(typed_error, RateLimitError),
                    is_503=isinstance(typed_error, TemporaryUnavailableError),
                )
                _quota_record(
                    "openrouter", dynamic_model or request.model, openrouter_key, _quota_outcome(typed_error)
                )
                if openrouter_key and typed_error.is_retryable() and openrouter_pool:
                    openrouter_pool.quarantine(openrouter_key, duration_seconds=60.0)
                logger.error(
                    "OpenRouter dynamic fallback failed (%s)", type(typed_error).__name__
                )

        # 2. Deterministic Failover Waterfall: Groq -> Mistral -> OpenAI -> Gemini
        remaining = (deadline - time.monotonic()) if deadline else 60.0
        if remaining > 0:
            waterfall_sequence = ProviderSwitchingPolicy.get_waterfall_sequence(failed_provider)
            fallback_route = ProviderSwitchingPolicy.get_fallback_provider(
                failed_provider, SwitchReason.TIMEOUT, stage=stage_name
            )
            candidate_rungs: list[tuple[str, str]] = []
            if fallback_route and fallback_route.fallback_provider != failed_provider:
                candidate_rungs.append((fallback_route.fallback_provider, fallback_route.fallback_model))
                for item in waterfall_sequence:
                    if item not in candidate_rungs and item[0] != failed_provider:
                        candidate_rungs.append(item)

            for sec_name, sec_model in candidate_rungs:
                rem = (deadline - time.monotonic()) if deadline else 60.0
                if rem <= 0:
                    break
                # TASK-REL-047 guards, same as the primary gate in execute():
                # an oversized prompt must not reach a Groq rung here either
                # (the waterfall cycles back to Groq for non-Groq primaries),
                # and a disabled NVIDIA rung is never attempted.
                if sec_name == "groq" and groq_prompt_over_limit(request):
                    logger.info(
                        "GATEWAY FALLBACK: Skipping 'groq' — prompt over the %d-token guard (TASK-REL-047).",
                        GROQ_PROMPT_TOKEN_LIMIT,
                    )
                    continue
                if sec_name == "nvidia" and not nvidia_rung_enabled():
                    logger.info(
                        "GATEWAY FALLBACK: Skipping 'nvidia' — rung disabled by configuration (TASK-REL-047)."
                    )
                    continue
                if not provider_has_credentials(sec_name):
                    logger.debug("GATEWAY FALLBACK: Skipping '%s' — no credentials configured.", sec_name)
                    continue

                try:
                    import app.providers

                    sec_prov = app.providers.get_provider(sec_name)
                    if not sec_prov:
                        continue

                    sec_limiter = self.rate_limiters.get(sec_name)
                    if not sec_limiter:
                        sec_limiter = ProviderRateLimiter(sec_name)
                        self.rate_limiters[sec_name] = sec_limiter

                    sec_req = ProviderRequest(
                        messages=request.messages,
                        system_instruction=request.system_instruction,
                        model=sec_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens or 1024,
                        deadline_monotonic=deadline,
                    )
                    acquire_timeout = (deadline - time.monotonic()) if deadline else 60.0
                    if acquire_timeout <= 0:
                        break
                    await asyncio.wait_for(sec_limiter.acquire(), timeout=acquire_timeout)
                    try:
                        rem = (deadline - time.monotonic()) if deadline else 60.0
                        if rem <= 0:
                            raise TimeoutError(f"Deadline exceeded for waterfall fallback {sec_name}.")
                        resp = await asyncio.wait_for(sec_prov.generate(sec_req), timeout=rem)
                    finally:
                        sec_limiter.release()

                    if _is_empty_completion(resp):
                        # Structural non-answer: fail this rung (the except
                        # below logs it) and let the next rung try.
                        raise TemporaryUnavailableError(
                            f"Waterfall provider '{sec_name}' returned an empty completion "
                            "(no candidates/choices in the upstream response).",
                            provider=sec_name,
                            model=sec_model,
                        )

                    if not resp.raw_response:
                        resp.raw_response = {}
                    clean_reason = scrub_credentials(str(last_error)) if last_error else "primary_exhausted"
                    resp.raw_response["fallback_provenance"] = {
                        "requested_provider": failed_provider,
                        "requested_model": request.model,
                        "actual_provider": sec_name,
                        "actual_model": sec_model,
                        "capability": capability,
                        "fallback_reason": clean_reason,
                    }
                    self.health_tracker.record_success(sec_name, resp.latency_seconds)
                    _quota_record(sec_name, sec_model, None, "success", resp)
                    return resp
                except Exception as sec_exc:
                    _quota_record(
                        sec_name,
                        sec_model,
                        None,
                        _quota_outcome(normalize_provider_exception(sec_exc, provider=sec_name, model=sec_model)),
                    )
                    scrubbed_exc = scrub_credentials(str(sec_exc))
                    logger.warning(
                        "Waterfall fallback provider '%s' failed: %s", sec_name, scrubbed_exc
                    )
        # 3. Self-hosted terminal tier. If a local server is running it has no quota,
        #    no key, and no network dependency, which makes it the most reliable rung
        #    of the ladder — but also usually the slowest, so it is tried after the
        #    free cloud peers and before LiteLLM (which itself needs cloud credentials).
        if skip_local_tier:
            logger.info(
                "GATEWAY FALLBACK: Self-hosted tier already attempted as primary choice; "
                "not repeating it at the end of the ladder."
            )
        else:
            local_resp = await self._execute_local_tier(
                failed_provider, request, capability, last_error, deadline
            )
            if local_resp is not None:
                return local_resp

        # 4. Optional LiteLLM unified transport fallback if enabled
        remaining = (deadline - time.monotonic()) if deadline else 60.0
        if (
            remaining > 0
            and settings.INFERENCE_LITELLM_FALLBACK_ENABLED
            and settings.INFERENCE_LITELLM_ENABLED
            and failed_provider != "litellm"
        ):
            try:
                from app.providers.gateway_litellm import execute_via_litellm

                litellm_resp = await asyncio.wait_for(execute_via_litellm(request), timeout=remaining)
                if _is_empty_completion(litellm_resp):
                    raise TemporaryUnavailableError(
                        "LiteLLM transport returned an empty completion "
                        "(no candidates/choices in the upstream response).",
                        provider="litellm",
                        model=request.model,
                    )
                if not litellm_resp.raw_response:
                    litellm_resp.raw_response = {}
                litellm_resp.raw_response["fallback_provenance"] = {
                    "requested_provider": failed_provider,
                    "requested_model": request.model,
                    "actual_provider": "litellm",
                    "actual_model": litellm_resp.model,
                    "capability": capability,
                    "fallback_reason": scrub_credentials(str(last_error)) if last_error else "primary_exhausted",
                }
                self.health_tracker.record_success("litellm", litellm_resp.latency_seconds)
                _quota_record("litellm", litellm_resp.model, None, "success", litellm_resp)
                return litellm_resp
            except Exception as litellm_exc:
                _quota_record("litellm", request.model, None, "error")
                logger.error("LiteLLM fallback failed: %s", str(litellm_exc))

        # If all fallbacks failed, raise the original error
        if last_error:
            raise last_error
        raise GatewayError(f"Provider {failed_provider} and all fallback routes failed.", provider=failed_provider)

    async def execute_speculative(
        self,
        providers: list[str],
        request: ProviderRequest,
        stage_name: str = "speculative_race",
        timeout: float = 10.0,
    ) -> ProviderResponse:
        """
        Ultra-low latency speculative racing:
        Launches parallel requests to specified providers concurrently.
        Returns the first successful response and cancels remaining slower tasks.
        """
        if not providers:
            raise GatewayError("No providers provided for speculative race.")
        # TASK-REL-047: the Groq size guard applies to raced candidates too —
        # racing an oversized prompt to Groq only buys a faster 413.
        if "groq" in providers and groq_prompt_over_limit(request):
            providers = [p for p in providers if p != "groq"]
            logger.info(
                "SPECULATIVE RACE: Removed 'groq' from candidates — prompt over the %d-token guard (TASK-REL-047).",
                GROQ_PROMPT_TOKEN_LIMIT,
            )
            if not providers:
                raise GatewayError(
                    "All speculative race candidates were removed by the Groq prompt-size guard.",
                    provider="groq",
                    model=request.model,
                )
        if len(providers) == 1:
            request.extra_params["timeout"] = timeout
            return await self.execute(providers[0], request, stage_name=stage_name)

        start_time = time.monotonic()

        async def _call_provider(prov: str) -> tuple[str, ProviderResponse]:
            prov_req = request
            # Auto-select appropriate model for each provider if needed
            if prov == "groq" and (not request.model or "gemini" in request.model):
                prov_req = ProviderRequest(
                    messages=request.messages,
                    system_instruction=request.system_instruction,
                    model="openai/gpt-oss-120b",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    extra_params={"timeout": timeout},
                )
            elif prov == "gemini" and (not request.model or "groq" in request.model or "gpt" in request.model):
                prov_req = ProviderRequest(
                    messages=request.messages,
                    system_instruction=request.system_instruction,
                    model="gemini-3.8-flash",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    extra_params={"timeout": timeout},
                )
            else:
                prov_req.extra_params["timeout"] = timeout
            resp = await self.execute(prov, prov_req, stage_name=stage_name)
            return prov, resp

        tasks = [asyncio.create_task(_call_provider(p)) for p in providers]
        first_error: Exception | None = None

        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                try:
                    winning_prov, winning_resp = d.result()
                    if _is_empty_completion(winning_resp):
                        # A racer that returns instantly with a structural
                        # non-answer has not answered: keep the slower racers
                        # running instead of crowning the empty response.
                        logger.warning(
                            "SPECULATIVE RACE: '%s' returned an empty completion; discarding it.",
                            winning_prov,
                        )
                        if first_error is None:
                            first_error = TemporaryUnavailableError(
                                f"Provider '{winning_prov}' returned an empty completion "
                                "(no candidates/choices in the upstream response).",
                                provider=winning_prov,
                            )
                        continue
                    for p in pending:
                        p.cancel()
                    elapsed = time.monotonic() - start_time
                    # The candidate LABEL that returned first is not necessarily the
                    # provider that produced the text. When a raced candidate has no
                    # usable credential (or the self-hosted tier is preferred) the call is
                    # served locally, yet callers were told the winning *label* answered:
                    # an instant request served by the local rig reported
                    # provider="groq"/model="gemini-3.8-flash". Recording the true
                    # serving provider alongside the label is what makes the race
                    # metadata usable for cost attribution instead of misleading.
                    served_by = winning_resp.provider or winning_prov
                    logger.info(
                        "SPECULATIVE RACE: '%s' returned first among %s in %.3fs; served_by=%s",
                        winning_prov,
                        providers,
                        elapsed,
                        served_by,
                    )
                    if not winning_resp.raw_response:
                        winning_resp.raw_response = {}
                    winning_resp.raw_response["speculative_race"] = {
                        "winner": winning_prov,
                        "served_by": served_by,
                        "fell_back": served_by != winning_prov,
                        "competitors": providers,
                        "elapsed_seconds": round(elapsed, 4),
                    }
                    return winning_resp
                except Exception as exc:
                    logger.warning("SPECULATIVE RACE: Provider attempt failed: %s", exc)
                    first_error = exc
            tasks = list(pending)

        if first_error:
            raise first_error
        raise GatewayError("All speculative race candidates failed.")

    async def stream(
        self,
        provider: str,
        request: ProviderRequest,
        stage_name: str = "general_stream",
    ) -> AsyncIterator[str]:
        """Stream from one provider while enforcing the request deadline and limits."""
        prov_name = provider.lower().strip()
        timeout_budget = _request_timeout_budget(request)
        deadline = time.monotonic() + timeout_budget

        # TASK-IG2-INF-04: same compression stage as execute() — streaming
        # spends the same free-tier quota, so it gets the same savings.
        try:
            from app.providers.token_compression import compress_provider_request

            request = compress_provider_request(request)
        except Exception:  # noqa: BLE001 - compression must never break serving
            logger.warning("GATEWAY: Token compression failed; streaming the original prompt.")

        # TASK-REL-047 guards (same rules as execute()): streaming has no
        # ladder to escalate to, so a guarded provider is refused up front
        # with the reason, instead of drawing a deterministic 413 (Groq) or
        # 404 (disabled NVIDIA rung) from the provider.
        if prov_name == "groq" and groq_prompt_over_limit(request):
            raise GatewayError(
                f"Prompt estimated at {estimate_prompt_tokens(request)} tokens exceeds the "
                f"{GROQ_PROMPT_TOKEN_LIMIT}-token Groq guard; streaming via Groq was not attempted.",
                provider=prov_name,
                model=request.model,
            )
        if prov_name == "nvidia" and not nvidia_rung_enabled():
            raise ProviderUnconfiguredError(
                "Provider 'nvidia' is disabled by configuration "
                "(INFERENCE_NVIDIA_RUNG_ENABLED is off; TASK-REL-047); streaming was not attempted.",
                provider=prov_name,
                model=request.model,
            )
        if prov_name == "bytez" and not bytez_rung_enabled():
            raise ProviderUnconfiguredError(
                "Provider 'bytez' is disabled by configuration "
                "(INFERENCE_BYTEZ_RUNG_ENABLED is off; TASK-IG2-INF-01); streaming was not attempted.",
                provider=prov_name,
                model=request.model,
            )

        if not provider_has_credentials(prov_name):
            raise ProviderUnconfiguredError(
                f"Provider '{prov_name}' has no configured credential; streaming was not attempted.",
                provider=prov_name,
                model=request.model,
            )

        pool = self.key_pools.get(prov_name)
        current_key = pool.choose() if pool else None
        limiter = self.rate_limiters.get(prov_name)
        if limiter is None:
            limiter = ProviderRateLimiter(prov_name)
            self.rate_limiters[prov_name] = limiter

        started = time.perf_counter()
        acquired = False
        iterator: AsyncIterator[str] | None = None
        try:
            import app.providers

            provider_instance = (
                app.providers.get_provider(prov_name, api_key=current_key)
                if current_key
                else app.providers.get_provider(prov_name)
            )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderTimeoutError(f"Stream deadline exceeded for provider '{prov_name}'.")
            await asyncio.wait_for(limiter.acquire(), timeout=remaining)
            acquired = True
            iterator = provider_instance.stream(request).__aiter__()

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderTimeoutError(f"Stream deadline exceeded for provider '{prov_name}'.")
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    self.health_tracker.record_success(prov_name, time.perf_counter() - started)
                    _quota_record(prov_name, request.model, current_key, "success")
                    return
                yield chunk
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, ProviderTimeoutError) as exc:
            typed_error: Exception = ProviderTimeoutError(
                f"Stream deadline exceeded for provider '{prov_name}' after "
                f"{time.perf_counter() - started:.2f}s.",
                provider=prov_name,
                model=request.model,
                raw_error=exc,
            )
            self.health_tracker.record_failure(
                prov_name,
                str(typed_error),
                is_429=False,
                is_503=True,
                latency_seconds=time.perf_counter() - started,
            )
            _quota_record(prov_name, request.model, current_key, "timeout")
            raise typed_error from exc
        except Exception as exc:
            typed_error = normalize_provider_exception(exc, provider=prov_name, model=request.model)
            self.health_tracker.record_failure(
                prov_name,
                str(typed_error),
                is_429=isinstance(typed_error, RateLimitError),
                is_503=isinstance(typed_error, TemporaryUnavailableError),
                latency_seconds=time.perf_counter() - started,
            )
            _quota_record(prov_name, request.model, current_key, _quota_outcome(typed_error))
            raise typed_error from exc
        finally:
            try:
                if iterator is not None:
                    close = getattr(iterator, "aclose", None)
                    if close is not None:
                        await close()
            finally:
                if acquired:
                    limiter.release()


# Global default gateway instance
model_gateway = ModelGateway()
