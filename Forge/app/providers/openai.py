"""
OpenAIProvider: OpenAI LLM provider integration for Project FORGE.
Implements BaseModelProvider with AsyncOpenAI, streaming, structured outputs,
exponential backoff retry for rate limits, timeouts, and JSON error handling.
"""

import asyncio
import json
import random
import re
import time
from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import (
    BaseModelProvider,
    ProviderCapabilities,
    ProviderHealthStatus,
    ProviderResponse,
    T,
    UsageEstimate,
)

logger = get_logger("providers.openai")

# Pricing per 1k tokens (Input, Output) in USD
OPENAI_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-2024-08-06": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o-mini-2024-07-18": (0.00015, 0.0006),
    "gpt-4-turbo": (0.010, 0.030),
    "gpt-4": (0.030, 0.060),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "o1": (0.015, 0.060),
    "o1-mini": (0.003, 0.012),
    "o1-preview": (0.015, 0.060),
    "o3-mini": (0.0011, 0.0044),
}


class OpenAIProvider(BaseModelProvider):
    """
    OpenAI model provider integration.
    Supports official AsyncOpenAI SDK, streaming token responses, schema-guided structured outputs,
    and resilient exponential backoff retry on API rate limits and connection failures.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        timeout: float = 60.0,
        client: AsyncOpenAI | None = None,
        **kwargs,
    ):
        settings = get_settings()
        resolved_model = model_name or settings.openai_default_model or "gpt-4o"
        super().__init__(model_name=resolved_model, **kwargs)

        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url
        self.organization = organization
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.timeout = timeout

        if client is not None:
            self.client = client
        else:
            self.client = AsyncOpenAI(
                api_key=self.api_key or "sk-dummy-key-placeholder",
                base_url=self.base_url,
                organization=self.organization,
                timeout=self.timeout,
            )

    def estimate_usage(self, prompt: str, output: str | None = None) -> UsageEstimate:
        """Estimate token usage and cost for prompt and completion."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(0, len(output) // 4) if output else 0
        total_tokens = prompt_tokens + completion_tokens

        pricing = OPENAI_MODEL_PRICING.get(self.model_name, (0.0025, 0.010))
        cost = (prompt_tokens / 1000.0) * pricing[0] + (completion_tokens / 1000.0) * pricing[1]

        return UsageEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(cost, 6),
        )

    def _calculate_actual_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Compute USD cost from actual token counts."""
        pricing = OPENAI_MODEL_PRICING.get(self.model_name, (0.0025, 0.010))
        cost = (prompt_tokens / 1000.0) * pricing[0] + (completion_tokens / 1000.0) * pricing[1]
        return round(cost, 6)

    def capabilities(self) -> ProviderCapabilities:
        """Return OpenAI provider capabilities and context limits."""
        return ProviderCapabilities(
            provider_name="OpenAIProvider",
            supported_models=list(OPENAI_MODEL_PRICING.keys()),
            supports_streaming=True,
            supports_structured_output=True,
            supports_function_calling=True,
            supports_multimodal=True,
            context_window_size=128000,
            max_output_tokens=16384,
        )

    async def health(self) -> ProviderHealthStatus:
        """Check OpenAI connectivity and operational status."""
        if not self.api_key or self.api_key == "sk-dummy-key-placeholder":
            return ProviderHealthStatus(
                healthy=False,
                provider_name="OpenAIProvider",
                message="OPENAI_API_KEY is not configured.",
                details={"model": self.model_name},
            )

        start_time = time.perf_counter()
        try:
            # Quick models list or validation call
            await self.client.models.list()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=True,
                provider_name="OpenAIProvider",
                message="OpenAI API operational",
                latency_ms=round(latency_ms, 2),
                details={"model": self.model_name},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=False,
                provider_name="OpenAIProvider",
                message=f"OpenAI health check failed: {e!s}",
                latency_ms=round(latency_ms, 2),
                details={"error": str(e)},
            )

    async def _execute_with_retry(self, api_func, *args, **kwargs) -> Any:
        """Execute an async API function with exponential backoff on rate limits and timeouts."""
        retries = 0
        while True:
            try:
                return await api_func(*args, **kwargs)
            except (
                TimeoutError,
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.InternalServerError,
            ) as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(f"OpenAI request failed after {self.max_retries} retries: {e}")
                    raise

                backoff = min(
                    self.max_backoff,
                    self.initial_backoff * (2 ** (retries - 1)) + random.uniform(0.1, 0.5),
                )
                logger.warning(
                    f"OpenAI error ({type(e).__name__}): {e}. Retrying {retries}/{self.max_retries} in {backoff:.2f}s..."
                )
                await asyncio.sleep(backoff)

    def _build_messages(
        self, prompt: str, system_prompt: str | None = None
    ) -> list[dict[str, str]]:
        """Construct standard chat message history."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Generate a complete text completion via OpenAI chat completions."""
        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)
        logger.debug(f"OpenAIProvider generate ({self.model_name}): {prompt[:80]}...")

        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        response = await self._execute_with_retry(
            self.client.chat.completions.create, **request_kwargs
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"

        if response.usage:
            prompt_tokens = response.usage.prompt_tokens or 0
            completion_tokens = response.usage.completion_tokens or 0
            total_tokens = response.usage.total_tokens or (prompt_tokens + completion_tokens)
            cost = self._calculate_actual_cost(prompt_tokens, completion_tokens)
            usage = UsageEstimate(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
            )
        else:
            usage = self.estimate_usage(prompt, content)

        raw_dict = None
        if hasattr(response, "model_dump") and callable(response.model_dump):
            try:
                dumped = response.model_dump(mode="json")
                if isinstance(dumped, dict):
                    raw_dict = dumped
            except Exception:
                raw_dict = None
        elif isinstance(response, dict):
            raw_dict = response

        return ProviderResponse(
            content=content,
            model=getattr(response, "model", self.model_name) or self.model_name,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=raw_dict,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chunks of generated text tokens from OpenAI."""
        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)
        logger.debug(f"OpenAIProvider stream ({self.model_name}): {prompt[:80]}...")

        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        response_stream = await self._execute_with_retry(
            self.client.chat.completions.create, **request_kwargs
        )

        async for chunk in response_stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

    async def structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.1,
        **kwargs,
    ) -> T:
        """
        Generate structured output parsed into a Pydantic model.
        Attempts beta.chat.completions.parse first, with robust schema-guided JSON fallback.
        """
        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)

        # 1. Try native beta parse endpoint if available
        if hasattr(self.client, "beta") and hasattr(self.client.beta, "chat"):
            try:
                parse_kwargs: dict[str, Any] = {
                    "model": self.model_name,
                    "messages": messages,
                    "response_format": response_model,
                    "temperature": temperature,
                    **kwargs,
                }
                completion = await self._execute_with_retry(
                    self.client.beta.chat.completions.parse, **parse_kwargs
                )
                parsed = completion.choices[0].message.parsed
                if parsed is not None and isinstance(parsed, response_model):
                    return parsed
            except Exception as parse_err:
                logger.debug(
                    f"Native beta parse failed or unsupported: {parse_err}. Falling back to JSON extraction."
                )

        # 2. Schema-guided JSON fallback with self-healing extraction
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object strictly matching this schema:\n{schema_json}"
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.generate(
                    prompt=augmented_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    response_format={"type": "json_object"}
                    if "gpt-4" in self.model_name or "gpt-3.5" in self.model_name
                    else None,
                    **kwargs,
                )
                parsed_dict = self._extract_json(response.content)
                return response_model.model_validate(parsed_dict)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                logger.warning(f"Structured output attempt {attempt + 1} validation failed: {e}")
                if attempt < self.max_retries:
                    augmented_prompt += f"\n\nPrevious response failed with error: {e}. Please fix and return ONLY valid JSON."
                    await asyncio.sleep(0.5)

        raise ValueError(
            f"Failed to generate valid structured output for {response_model.__name__}: {last_error}"
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON object from string with regex tolerance for markdown codeblocks."""
        text = text.strip()
        # Look for ```json ... ``` blocks
        json_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_block_match:
            text = json_block_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
            raise
