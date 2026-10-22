"""
AnthropicProvider: Anthropic Claude LLM provider integration for Project FORGE.
Implements BaseModelProvider with AsyncAnthropic, streaming, structured outputs (tool-use & JSON),
exponential backoff retry for rate limits, timeouts, and JSON error handling.
"""

import asyncio
import json
import random
import re
import time
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
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

logger = get_logger("providers.anthropic")

# Pricing per 1k tokens (Input, Output) in USD
ANTHROPIC_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku-20241022": (0.0008, 0.004),
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet-20240229": (0.003, 0.015),
    "claude-3-haiku-20240307": (0.00025, 0.00125),
}


class AnthropicProvider(BaseModelProvider):
    """
    Anthropic Claude model provider integration.
    Supports AsyncAnthropic SDK, streaming text tokens, schema-guided structured outputs
    via tool calling and schema prompts, and exponential backoff retry on API rate limits.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        timeout: float = 60.0,
        client: AsyncAnthropic | None = None,
        **kwargs,
    ):
        settings = get_settings()
        resolved_model = (
            model_name or settings.anthropic_default_model or "claude-3-5-sonnet-20241022"
        )
        super().__init__(model_name=resolved_model, **kwargs)

        self.api_key = api_key or settings.anthropic_api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.timeout = timeout

        if client is not None:
            self.client = client
        else:
            self.client = AsyncAnthropic(
                api_key=self.api_key or "sk-ant-dummy-key-placeholder",
                base_url=self.base_url,
                timeout=self.timeout,
            )

    def estimate_usage(self, prompt: str, output: str | None = None) -> UsageEstimate:
        """Estimate token usage and cost for prompt and completion."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(0, len(output) // 4) if output else 0
        total_tokens = prompt_tokens + completion_tokens

        pricing = ANTHROPIC_MODEL_PRICING.get(self.model_name, (0.003, 0.015))
        cost = (prompt_tokens / 1000.0) * pricing[0] + (completion_tokens / 1000.0) * pricing[1]

        return UsageEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(cost, 6),
        )

    def _calculate_actual_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Compute USD cost from actual token counts."""
        pricing = ANTHROPIC_MODEL_PRICING.get(self.model_name, (0.003, 0.015))
        cost = (prompt_tokens / 1000.0) * pricing[0] + (completion_tokens / 1000.0) * pricing[1]
        return round(cost, 6)

    def capabilities(self) -> ProviderCapabilities:
        """Return Anthropic Claude provider capabilities and context limits."""
        return ProviderCapabilities(
            provider_name="AnthropicProvider",
            supported_models=list(ANTHROPIC_MODEL_PRICING.keys()),
            supports_streaming=True,
            supports_structured_output=True,
            supports_function_calling=True,
            supports_multimodal=True,
            context_window_size=200000,
            max_output_tokens=8192,
        )

    async def health(self) -> ProviderHealthStatus:
        """Check Anthropic connectivity and operational status."""
        if not self.api_key or self.api_key == "sk-ant-dummy-key-placeholder":
            return ProviderHealthStatus(
                healthy=False,
                provider_name="AnthropicProvider",
                message="ANTHROPIC_API_KEY is not configured.",
                details={"model": self.model_name},
            )

        start_time = time.perf_counter()
        try:
            # Send minimal validation heartbeat
            await self._execute_with_retry(
                self.client.messages.create,
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=True,
                provider_name="AnthropicProvider",
                message="Anthropic API operational",
                latency_ms=round(latency_ms, 2),
                details={"model": self.model_name},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=False,
                provider_name="AnthropicProvider",
                message=f"Anthropic health check failed: {e!s}",
                latency_ms=round(latency_ms, 2),
                details={"error": str(e)},
            )

    async def _execute_with_retry(self, api_func, *args, **kwargs) -> Any:
        """Execute an async API function with exponential backoff on rate limits, timeouts, and server errors."""
        retries = 0
        while True:
            try:
                return await api_func(*args, **kwargs)
            except (
                TimeoutError,
                anthropic.RateLimitError,
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            ) as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(f"Anthropic request failed after {self.max_retries} retries: {e}")
                    raise

                backoff = min(
                    self.max_backoff,
                    self.initial_backoff * (2 ** (retries - 1)) + random.uniform(0.1, 0.5),
                )
                logger.warning(
                    f"Anthropic error ({type(e).__name__}): {e}. Retrying {retries}/{self.max_retries} in {backoff:.2f}s..."
                )
                await asyncio.sleep(backoff)

    def _extract_text_content(self, message: Any) -> str:
        """Extract text from Anthropic content blocks."""
        if hasattr(message, "content"):
            parts: list[str] = []
            for block in message.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "".join(parts)
        return str(message)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Generate a complete text completion via Anthropic Messages API."""
        logger.debug(f"AnthropicProvider generate ({self.model_name}): {prompt[:80]}...")
        messages = [{"role": "user", "content": prompt}]
        max_tokens_val = max_tokens or 4096

        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": max_tokens_val,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        if system_prompt:
            request_kwargs["system"] = system_prompt

        response = await self._execute_with_retry(self.client.messages.create, **request_kwargs)

        content = self._extract_text_content(response)
        finish_reason = getattr(response, "stop_reason", "stop") or "stop"

        if hasattr(response, "usage") and response.usage:
            prompt_tokens = getattr(response.usage, "input_tokens", 0) or 0
            completion_tokens = getattr(response.usage, "output_tokens", 0) or 0
            total_tokens = prompt_tokens + completion_tokens
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
            finish_reason=str(finish_reason),
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
        """Stream chunks of generated text tokens from Anthropic."""
        logger.debug(f"AnthropicProvider stream ({self.model_name}): {prompt[:80]}...")
        messages = [{"role": "user", "content": prompt}]
        max_tokens_val = max_tokens or 4096

        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": max_tokens_val,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        if system_prompt:
            request_kwargs["system"] = system_prompt

        async with self.client.messages.stream(**request_kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.1,
        **kwargs,
    ) -> T:
        """
        Generate structured output matching a Pydantic model.
        Attempts Anthropic tool-calling first for reliable structured extraction,
        with schema-guided JSON fallback.
        """
        # 1. Try Tool-Calling Structured Extraction
        tool_name = "output_formatter"
        tool_schema = {
            "name": tool_name,
            "description": f"Output structured information conforming to {response_model.__name__}",
            "input_schema": response_model.model_json_schema(),
        }

        try:
            request_kwargs: dict[str, Any] = {
                "model": self.model_name,
                "max_tokens": kwargs.pop("max_tokens", 4096),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "tools": [tool_schema],
                "tool_choice": {"type": "tool", "name": tool_name},
                **kwargs,
            }
            if system_prompt:
                request_kwargs["system"] = system_prompt

            response = await self._execute_with_retry(self.client.messages.create, **request_kwargs)

            for block in response.content:
                if (
                    getattr(block, "type", None) == "tool_use"
                    and getattr(block, "name", None) == tool_name
                ):
                    return response_model.model_validate(block.input)
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == tool_name
                ):
                    return response_model.model_validate(block.get("input", {}))
        except Exception as tool_err:
            logger.debug(
                f"Anthropic tool calling for structured output failed: {tool_err}. Falling back to prompt JSON extraction."
            )

        # 2. Schema-guided JSON fallback
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
                    **kwargs,
                )
                parsed_dict = self._extract_json(response.content)
                return response_model.model_validate(parsed_dict)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                logger.warning(
                    f"Anthropic structured output attempt {attempt + 1} validation failed: {e}"
                )
                if attempt < self.max_retries:
                    augmented_prompt += (
                        f"\n\nPrevious response was invalid: {e}. Return ONLY valid JSON."
                    )
                    await asyncio.sleep(0.5)

        raise ValueError(
            f"Failed to generate valid structured output for {response_model.__name__}: {last_error}"
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON object from string with regex tolerance for markdown codeblocks."""
        text = text.strip()
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
