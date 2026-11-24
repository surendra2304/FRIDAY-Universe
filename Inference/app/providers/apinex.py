"""APInex LLM Provider Adapter with free-tier model discovery.

TASK-INF-030: APInex (https://api.apinex.bond/v1) is an OpenAI-compatible
gateway wired as a fallback rung behind the Inference router. One
``APINEX_API_KEY`` (``sk-apx-...``) serves the whole catalogue; the
``free/*`` models draw from a daily allowance at $0.00/1M tokens
(15 requests/minute per account).

Live probe from Server 2, 2026-11-24 (key owner-provided 2026-11-23, in
S2 /opt/friday_universe/CREDENTIALS.md; base URL recorded there):
``GET /v1/models`` -> 200, 44 models, 22 ``free/*`` ids. Completions on
free models: ``free/qwen-3.8-max`` 200 in 1.11s, ``free/gpt-6-luna`` 200 in
3.93s, ``free/deepseek-v4.1-flash`` 200 in 9.47s — all ``cost_tokens`` 0.
BUT the free list is not uniformly free: ``free/gemini-3.8-flash`` and
``free/glm-5.3`` return HTTP 402 "available only with a subscription" — the
catalogue cannot tell gated from working; only a completion attempt can.
Therefore ``SUPPORTED_MODELS`` lists ONLY the ids verified answering live,
and capability selection searches that verified list first; discovered ids
are a second pass, never the default. Never make a gated id the default or
a capability fallback: a 402 on the last rung fails the request.
"""

import asyncio
import time

from app.core.config import settings
from app.providers.base import ProviderRequest, ProviderResponse
from app.providers.http_client import get_shared_client
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.utils.logger import logger

# Capability-to-model preference mapping. Keywords are matched against the
# VERIFIED list first (see find_model_by_capability): "gemini"/"glm" must
# never appear here — free/gemini-3.8-flash and free/glm-5.3 are
# subscription-gated (402, verified 2026-11-24) despite the free/ prefix.
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "coding": ["qwen", "deepseek", "code", "coder"],
    "reasoning": ["deepseek", "qwen"],
    "research": ["qwen", "gpt"],
    "analysis": ["qwen", "gpt", "deepseek"],
    "security": ["qwen", "deepseek"],
    "general": ["qwen", "gpt"],
}

# Verified-working free models only (live probe 2026-11-24, cost_tokens 0).
FALLBACK_FREE_MODELS: dict[str, str] = {
    "coding": "free/qwen-3.8-max",
    "reasoning": "free/deepseek-v4.1-flash",
    "research": "free/qwen-3.8-max",
    "analysis": "free/qwen-3.8-max",
    "security": "free/qwen-3.8-max",
    "general": "free/qwen-3.8-max",
}

# TASK-INF-004 pattern (see openrouter.py): the free-model discovery cache
# lives at MODULE level, not on the provider instance — the gateway builds a
# fresh provider per fallback attempt, so an instance-level cache can never
# survive to a second fallback. Keyed by base_url; only successful non-empty
# fetches are cached; a failed fetch keeps the previous semantics (static
# SUPPORTED_MODELS, retried on the next call). The single-flight lock keeps
# concurrent fallbacks from stampeding the catalogue endpoint.
_DISCOVERY_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes
_DISCOVERY_CACHE: dict[str, tuple[list[str], float]] = {}
_DISCOVERY_LOCK = asyncio.Lock()


class ApinexProvider(OpenAICompatibleProvider):
    """Adapter for the APInex multi-model gateway (OpenAI-compatible wire)."""

    BASE_URL = "https://api.apinex.bond/v1"
    # Fastest verified free model (1.11s live from Server 2, 2026-11-24).
    DEFAULT_MODEL = "free/qwen-3.8-max"
    # Only ids verified answering live (200, cost_tokens 0, 2026-11-24).
    # Gated ids are deliberately absent: free/gemini-3.8-flash and
    # free/glm-5.3 return HTTP 402 (subscription required).
    SUPPORTED_MODELS = [
        "free/qwen-3.8-max",
        "free/gpt-6-luna",
        "free/deepseek-v4.1-flash",
    ]

    def __init__(self, api_key: str | None = None, default_model: str | None = None, timeout: float = 60.0) -> None:
        keys = settings.get_provider_keys("apinex")
        if api_key:
            keys = [k.strip() for k in api_key.split(",") if k.strip()]
        key_str = ",".join(keys) if keys else None
        super().__init__(
            provider_name="apinex",
            base_url=self.BASE_URL,
            api_key=key_str,
            default_model=default_model or self.DEFAULT_MODEL,
            supported_models=self.SUPPORTED_MODELS,
            timeout=timeout,
        )
        self._cached_free_models: list[str] = []
        self._cache_timestamp: float = 0.0
        self._cache_ttl_seconds: float = 300.0  # 5 minutes

    async def fetch_available_free_models(self) -> list[str]:
        """Fetch the currently listed ``free/*`` models from the APInex API.

        The catalogue is the ``free/`` prefix only: APInex marks gated
        models with the same prefix, so a listed id is NOT proof it will
        answer (see module docstring). Successful fetches are cached at
        module level; failures fall back to the verified static list.
        """
        now = time.time()
        shared = _DISCOVERY_CACHE.get(self.base_url)
        if shared and shared[0] and (now - shared[1]) < _DISCOVERY_CACHE_TTL_SECONDS:
            return list(shared[0])
        if self._cached_free_models and (now - self._cache_timestamp) < self._cache_ttl_seconds:
            return self._cached_free_models

        if not self.api_key:
            return list(self.SUPPORTED_MODELS)

        async with _DISCOVERY_LOCK:
            # Re-check inside the lock: a concurrent fallback may have
            # completed the fetch while this call was waiting for it.
            now = time.time()
            shared = _DISCOVERY_CACHE.get(self.base_url)
            if shared and shared[0] and (now - shared[1]) < _DISCOVERY_CACHE_TTL_SECONDS:
                return list(shared[0])

            url = f"{self.base_url}/models"
            headers = self._get_headers()
            try:
                client = await get_shared_client()
                resp = await client.get(url, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    free_models = [m["id"] for m in data if str(m.get("id", "")).startswith("free/")]
                    if free_models:
                        _DISCOVERY_CACHE[self.base_url] = (list(free_models), now)
                        self._cached_free_models = free_models
                        self._cache_timestamp = now
                        logger.info("Discovered %d free models on APInex", len(free_models))
                        return free_models
            except Exception as exc:
                logger.debug("Failed to query live APInex models: %s", str(exc))

        return list(self.SUPPORTED_MODELS)

    async def get_best_free_model(self, capability: str = "general") -> str:
        """Select the best verified free model on APInex for a capability."""
        return await self.find_model_by_capability(capability)

    async def find_model_by_capability(self, capability: str = "general") -> str:
        """Find the best available free model matching a capability tag.

        Verified-first: the static list is searched before the discovered
        catalogue, because a discovered ``free/*`` id may be
        subscription-gated (402 at completion time) while a verified id is
        proven answering. Discovered ids are the second pass only.
        """
        cap_lower = capability.lower().strip()
        keywords = CAPABILITY_KEYWORDS.get(cap_lower, CAPABILITY_KEYWORDS["general"])
        for kw in keywords:
            for model_id in self.SUPPORTED_MODELS:
                if kw in model_id.lower():
                    logger.info("Selected verified APInex model '%s' for capability '%s'", model_id, capability)
                    return model_id

        models = await self.fetch_available_free_models()
        for kw in keywords:
            for model_id in models:
                if kw in model_id.lower():
                    logger.info("Selected discovered APInex model '%s' for capability '%s'", model_id, capability)
                    return model_id

        # Fallback to the verified default free model.
        fallback = FALLBACK_FREE_MODELS.get(cap_lower, self.DEFAULT_MODEL)
        return fallback

    async def generate_with_capability(self, request: ProviderRequest, capability: str = "general") -> ProviderResponse:
        """Resolve the model via capability tag, then generate a response."""
        if not request.model or request.model == self.DEFAULT_MODEL:
            resolved_model = await self.get_best_free_model(capability)
            request.model = resolved_model
        return await self.generate(request)
