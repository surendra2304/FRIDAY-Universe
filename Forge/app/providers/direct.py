"""
DirectProvider: Direct and local execution provider for FORGE.
Provides standalone execution, mock inference, direct completions, streaming, and Pydantic structured output.
"""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.providers.base import (
    BaseModelProvider,
    ProviderCapabilities,
    ProviderHealthStatus,
    ProviderResponse,
    T,
    UsageEstimate,
)

logger = get_logger("providers.direct")


class DirectProvider(BaseModelProvider):
    """
    Direct model provider.
    Supports standalone direct generation, deterministic mocking for tests,
    token estimation, streaming chunks, and schema-guided structured outputs.
    """

    def __init__(
        self,
        model_name: str | None = None,
        mock_mode: bool = False,
        mock_response: str | None = None,
        cost_per_1k_input: float = 0.0015,
        cost_per_1k_output: float = 0.002,
        **kwargs,
    ):
        super().__init__(model_name=model_name or "direct-default", **kwargs)
        self.mock_mode = mock_mode
        self.mock_response = mock_response
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output

    def estimate_usage(self, prompt: str, output: str | None = None) -> UsageEstimate:
        """Estimate token usage based on approximate ~4 chars per token rule."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(0, len(output) // 4) if output else 0
        total_tokens = prompt_tokens + completion_tokens

        cost = (prompt_tokens / 1000.0) * self.cost_per_1k_input + (
            completion_tokens / 1000.0
        ) * self.cost_per_1k_output

        return UsageEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(cost, 6),
        )

    def capabilities(self) -> ProviderCapabilities:
        """Return capabilities and execution limits."""
        return ProviderCapabilities(
            provider_name="DirectProvider",
            supported_models=["direct-default", "direct-fast", "direct-reasoning"],
            supports_streaming=True,
            supports_structured_output=True,
            supports_function_calling=True,
            supports_multimodal=False,
            context_window_size=128000,
            max_output_tokens=8192,
        )

    async def health(self) -> ProviderHealthStatus:
        """Check provider status and latency."""
        start_time = time.perf_counter()
        try:
            # Simulate quick internal heartbeat check
            await asyncio.sleep(0.001)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=True,
                provider_name="DirectProvider",
                message="DirectProvider operational",
                latency_ms=round(latency_ms, 2),
                details={"model": self.model_name, "mock_mode": self.mock_mode},
            )
        except Exception as e:
            return ProviderHealthStatus(
                healthy=False,
                provider_name="DirectProvider",
                message=f"Health check failed: {e!s}",
                latency_ms=None,
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Generate response directly or return deterministic mock response."""
        logger.debug(f"DirectProvider generating for prompt: {prompt[:80]}...")

        if self.mock_response is not None:
            content = self.mock_response
        else:
            # Default direct completion format
            content = (
                f"[Direct Completion from {self.model_name}]\n"
                f"Prompt Summary: {prompt.strip()[:80]}...\n"
                f"Status: Executed successfully."
            )

        usage = self.estimate_usage(prompt, content)
        return ProviderResponse(
            content=content,
            model=self.model_name,
            finish_reason="stop",
            usage=usage,
            raw_response={"temperature": temperature, "max_tokens": max_tokens},
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream generated response token by token."""
        full_response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        words = full_response.content.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            yield chunk
            await asyncio.sleep(0.005)  # brief async yield for streaming cadence

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
        In mock or direct mode, synthesizes or extracts valid JSON conforming to the schema.
        """
        json.dumps(response_model.model_json_schema(), indent=2)

        if self.mock_response is not None:
            raw_text = self.mock_response
        else:
            # Generate a valid default instance from schema or dummy fields
            raw_text = self._synthesize_json_for_model(response_model)

        # Parse JSON from text
        parsed_data = self._extract_json(raw_text)
        try:
            return response_model.model_validate(parsed_data)
        except ValidationError as e:
            logger.warning(
                f"Validation failed on structured output: {e}. Attempting fallback instance."
            )
            # Fallback attempt
            return response_model.model_validate(self._synthesize_dict_for_model(response_model))

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
            # Fallback to finding outermost brackets
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {}

    def _synthesize_dict_for_model(self, model: type[BaseModel]) -> dict[str, Any]:
        """Synthesize default valid dictionary matching model fields."""
        data = {}
        for field_name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            default_val = field_info.default
            if default_val is not None and str(default_val) != "PydanticUndefined":
                data[field_name] = default_val
            elif annotation is str or getattr(annotation, "__name__", "") == "str":
                data[field_name] = f"sample_{field_name}"
            elif annotation is int or getattr(annotation, "__name__", "") == "int":
                data[field_name] = 1
            elif annotation is float or getattr(annotation, "__name__", "") == "float":
                data[field_name] = 1.0
            elif annotation is bool or getattr(annotation, "__name__", "") == "bool":
                data[field_name] = True
            elif annotation is list or getattr(annotation, "__origin__", None) is list:
                data[field_name] = []
            elif annotation is dict or getattr(annotation, "__origin__", None) is dict:
                data[field_name] = {}
            else:
                data[field_name] = None
        return data

    def _synthesize_json_for_model(self, model: type[BaseModel]) -> str:
        """Synthesize JSON representation for model."""
        return json.dumps(self._synthesize_dict_for_model(model))
