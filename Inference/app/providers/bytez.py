"""Bytez LLM Provider Adapter (TASK-IG2-INF-01).

Bytez (https://bytez.com) is a hosted serverless inference service: one API
key, an OpenAI-compatible chat-completions surface at
``https://api.bytez.com/models/v2/openai/v1``, and a catalogue of open
models. It is a *service*, not a codebase — nothing here adopts Bytez code;
this is a thin adapter in the same shape as :mod:`app.providers.nvidia`.

Free-tier status — UNPROVEN, by design
--------------------------------------
Bytez's official billing docs (verified 2026-11-16, see
~/workspace/ig-references/repos/bytez.md) describe a genuine $0 tier — open
models up to 7B parameters, 1 concurrent request — but do **not** state a
recurring free credit/token allowance, and everything past the $0 tier is
credit-metered (paid). Under the owner's FREE-only rule this adapter is
therefore shipped behind two gates:

1. **Rung gate (default OFF).** The gateway will not route to Bytez unless
   ``INFERENCE_BYTEZ_RUNG_ENABLED=true`` — the same doctrine as the NVIDIA
   rung (TASK-REL-047). Setting it is an operator decision made *after*
   reading a quota-probe report.
2. **No quota is claimed.** Bytez has no declared limit in the quota
   ledger; its ledger state is ``unproven_free_tier`` until an operator
   declares a limit based on probe evidence. Nothing in the fleet may
   budget against Bytez volume that has not been measured.

Only ≤7B open models are listed: larger models are credit-gated upstream,
so offering them here would invite accidental paid spend. The empirical
trial harness lives in :mod:`app.providers.bytez_probe`.

TASK-INF-039 free-tier guardrails
---------------------------------
``generate``/``stream`` run through :mod:`app.providers.bytez_guard`:

* the requested model must be in the ≤7B allowlist (a larger model is
  refused before any call is made — no credit-metered model is reachable
  through this rung);
* the call holds the single free-tier concurrency slot (the $0 tier
  allows 1 concurrent request); a caller that cannot get the slot within
  ``BYTEZ_SLOT_WAIT_SECONDS`` (default 5 s) fails fast so the gateway
  ladder serves the request from the next rung;
* the served-model id Bytez returns is verified against the requested
  model and the verdict is recorded in ``raw_response["bytez"]`` (the
  INF-005 serve-check, at runtime: an aggregator may substitute models).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from app.core.config import settings
from app.providers.base import ProviderCapabilities, ProviderRequest, ProviderResponse
from app.providers.bytez_guard import (
    acquire_bytez_slot,
    annotate_bytez_response,
    validate_bytez_model,
    verify_served_model,
)
from app.providers.openai_compatible import OpenAICompatibleProvider

BYTEZ_BASE_URL = "https://api.bytez.com/models/v2/openai/v1"

#: Free tier covers open models up to 7B parameters only (Bytez billing
#: docs, 2026-11-16). Every model listed here is ≤7B; do not add larger
#: models — they are credit-metered and would break the FREE-only rule.
BYTEZ_DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
BYTEZ_SUPPORTED_MODELS: list[str] = [
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen3-4B",
    "meta-llama/Llama-3.2-3B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
]


class BytezProvider(OpenAICompatibleProvider):
    """Bytez adapter over its OpenAI-compatible chat-completions surface."""

    def __init__(
        self, api_key: str | None = None, default_model: str = BYTEZ_DEFAULT_MODEL, timeout: float = 60.0
    ) -> None:
        key = (
            api_key
            or getattr(settings, "BYTEZ_API_KEY", None)
            or os.environ.get("BYTEZ_API_KEYS")
            or os.environ.get("BYTEZ_API_KEY")
        )
        super().__init__(
            provider_name="bytez",
            base_url=BYTEZ_BASE_URL,
            api_key=key,
            default_model=default_model,
            supported_models=BYTEZ_SUPPORTED_MODELS,
            timeout=timeout,
        )

    def capabilities(self) -> ProviderCapabilities:
        caps = super().capabilities()
        caps.max_context_window = 32768
        caps.rate_limits = {
            "free_tier": "open models up to 7B parameters, 1 concurrent request (Bytez billing docs)",
            "free_volume": "UNPROVEN — no recurring free allowance is documented; see app.providers.bytez_probe",
            "metering": "credit-metered beyond the $0 tier; paid spend is out of bounds (FREE-only rule)",
        }
        return caps

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate via Bytez under the TASK-INF-039 free-tier guardrails.

        Order is deliberate: the model allowlist is checked first (a
        refused model must never take the slot), then the credential, then
        the single concurrency slot. A busy slot raises
        :class:`BytezSlotBusyError` (a ``TimeoutError``) so the gateway
        escalates to the fallback ladder; the served-model verdict is
        recorded on the response before it is returned.
        """
        model = validate_bytez_model(request.model, BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL)
        self._require_key_or_raise()
        async with acquire_bytez_slot():
            resp = await super().generate(request)
        served = resp.raw_response.get("model") if isinstance(resp.raw_response, dict) else None
        return annotate_bytez_response(resp, verify_served_model(model, served))

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """Stream via Bytez under the same guardrails as :meth:`generate`.

        The concurrency slot is held for the whole stream (a streamed call
        is still one of the tier's single concurrent requests) and released
        when the stream ends, errors, or the consumer closes it early.
        """
        validate_bytez_model(request.model, BYTEZ_SUPPORTED_MODELS, BYTEZ_DEFAULT_MODEL)
        self._require_key_or_raise()
        async with acquire_bytez_slot():
            async for chunk in super().stream(request):
                yield chunk
