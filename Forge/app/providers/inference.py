"""
InferenceProvider: Agent 2 (Inference) Gateway Provider for Project FORGE.
Routes all LLM completions, code generation, streaming, and structured outputs
through the FRIDAY Universe Inference Mesh (http://inference:8000).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.ai_universe_client import AIUniverseClient
from app.providers.base import (
    BaseModelProvider,
    ProviderCapabilities,
    ProviderHealthStatus,
    ProviderResponse,
    T,
    UsageEstimate,
)
from app.providers.direct import DirectProvider

logger = get_logger("providers.inference")


class InferenceProvider(BaseModelProvider):
    """
    Model provider routing requests through Agent 2 (Inference Gateway).
    Leverages 47 multi-key pools across Groq, OpenRouter, and Gemini.
    Provides automatic fallback to DirectProvider if Inference is unreachable or in mock mode.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        enable_fallback: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name or "inference-router", **kwargs)
        settings = get_settings()
        self.base_url = (base_url or settings.ai_universe_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.ai_universe_api_key
        self.client = AIUniverseClient(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
        )
        self.enable_fallback = enable_fallback
        self._fallback_provider = DirectProvider(model_name="direct-inference-fallback")

    def estimate_usage(self, prompt: str, output: str | None = None) -> UsageEstimate:
        """Token usage estimate for Inference requests (~4 chars per token)."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(0, len(output) // 4) if output else 0
        total_tokens = prompt_tokens + completion_tokens
        # Inference mesh internal cost is zero to Forge
        return UsageEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=0.0,
        )

    def capabilities(self) -> ProviderCapabilities:
        """Return capabilities supported by the Inference gateway."""
        return ProviderCapabilities(
            provider_name="InferenceProvider",
            supported_models=[
                "inference-router",
                "llama-3.3-70b-versatile",
                "deepseek-chat",
                "gemini-2.0-flash",
                "qwen-2.5-coder-32b",
            ],
            supports_streaming=True,
            supports_structured_output=True,
            supports_function_calling=True,
            supports_multimodal=False,
            context_window_size=131072,
            max_output_tokens=8192,
        )

    async def health(self) -> ProviderHealthStatus:
        """Checks reachability of the Inference mesh gateway."""
        start_time = time.perf_counter()
        try:
            # Query quick auto test
            resp = await self.client.ask("ping", mode="auto")
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=True,
                provider_name="InferenceProvider",
                message=f"Inference gateway operational (confidence: {resp.confidence:.2f})",
                latency_ms=round(latency_ms, 2),
                details={"base_url": self.base_url, "run_id": resp.run_id},
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Inference gateway health check failed: %s", exc)
            return ProviderHealthStatus(
                healthy=False,
                provider_name="InferenceProvider",
                message=f"Inference gateway unreachable: {exc}",
                latency_ms=round(latency_ms, 2),
                details={"base_url": self.base_url},
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        Executes completion via Agent 2 (Inference), with graceful DirectProvider fallback.
        """
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System Instructions: {system_prompt}\n\nTask: {prompt}"

        try:
            ai_resp = await self.client.ask(question=full_prompt, mode="auto")
            content = ai_resp.answer
            usage = self.estimate_usage(prompt, content)
            return ProviderResponse(
                content=content,
                model=self.model_name,
                finish_reason="stop",
                usage=usage,
                raw_response={
                    "confidence": ai_resp.confidence,
                    "run_id": ai_resp.run_id,
                    "key_evidence": ai_resp.key_evidence,
                },
            )
        except Exception as exc:
            if not self.enable_fallback:
                raise
            logger.warning(
                "Inference gateway request failed (%s). Falling back to DirectProvider.",
                exc,
            )
            return await self._fallback_provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streams generated tokens from Inference or fallback."""
        try:
            full_resp = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            words = full_resp.content.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield chunk
                await asyncio.sleep(0.005)
        except Exception as exc:
            logger.error("Inference streaming encountered error: %s", exc)
            yield f"[Error: {exc}]"

    async def structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> T:
        """Generates Pydantic structured output using Inference JSON enforcement."""
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        instruction = (
            f"{prompt}\n\nYou MUST respond with valid JSON strictly conforming to this JSON Schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any prose outside the JSON markdown block."
        )

        resp = await self.generate(
            prompt=instruction,
            system_prompt=system_prompt,
            temperature=temperature,
            **kwargs,
        )

        raw_text = resp.content
        extracted_json = self._fallback_provider._extract_json(raw_text)
        try:
            return response_model.model_validate(extracted_json)
        except ValidationError:
            # Retry parsing via fallback synthesizer if schema failed
            logger.warning("Inference output failed schema validation; synthesizing via direct parser.")
            return await self._fallback_provider.structured_output(
                prompt=prompt,
                response_model=response_model,
                system_prompt=system_prompt,
                temperature=temperature,
                **kwargs,
            )
