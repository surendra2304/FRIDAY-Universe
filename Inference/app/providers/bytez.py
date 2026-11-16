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
"""

from __future__ import annotations

import os

from app.core.config import settings
from app.providers.base import ProviderCapabilities
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
