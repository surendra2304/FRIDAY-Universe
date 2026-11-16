"""
InferenceProvider: Agent 2 (Inference) Gateway Provider for Project FORGE.

Routes LLM completions through the FRIDAY Universe Inference gateway's
OpenAI-compatible ``POST /v1/chat/completions`` endpoint. The gateway owns
model selection: a request naming a model outside its verified catalogue is
resolved by its best-suitable routing (TASK-REL-043), and the response body
names the model that actually served (plus a provenance block when a
substitution was chosen). Forge roles pass per-role model aliases
(``forge-<role>``) so the gateway applies that routing per role.

TASK-FRG-009: this provider previously called the ``/v1/friday/ask`` Q&A
endpoint and silently fell back to the deterministic DirectProvider mock on
any failure, so a build produced by the mock was indistinguishable from a
model-generated one. It now fails closed: gateway failures raise
``InferenceUnavailableError`` unless the caller explicitly opted into the
legacy fallback (``enable_fallback=True``), and even then the returned
response is marked ``raw_response["degraded_fallback"] = "direct"`` so the
degradation is visible in task output.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
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


class InferenceUnavailableError(RuntimeError):
    """The Inference gateway could not serve a completion.

    Raised instead of silently substituting deterministic mock output, so a
    caller (role, task) fails honestly rather than reporting mock content as
    a model-generated success.
    """


class InferenceProvider(BaseModelProvider):
    """
    Model provider routing requests through Agent 2 (Inference Gateway).

    Completions go to the gateway's OpenAI-compatible chat endpoint with the
    configured model name (a per-role alias by default; the gateway resolves
    aliases through best-suitable routing and reports the served model).
    Authentication uses Forge's own configured Inference API key
    (``INFERENCE_API_KEY`` / ``AI_UNIVERSE_API_KEY``) when one is set.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        enable_fallback: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name or "inference-router", **kwargs)
        settings = get_settings()
        self.base_url = (base_url or settings.ai_universe_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.ai_universe_api_key
        self.timeout = timeout
        # Legacy client retained for the specialised /v1/forge/* and
        # /v1/friday/* service calls other Forge modules make; completions
        # from this provider no longer go through it.
        self.client = AIUniverseClient(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
        )
        # TASK-FRG-009: fail closed by default. The DirectProvider fallback
        # survives only as an explicit opt-in for legacy callers, and its
        # output is always marked as degraded (see generate()).
        self.enable_fallback = enable_fallback
        self._fallback_provider = DirectProvider(model_name="direct-inference-fallback")
        self.last_degraded: bool = False
        self.last_error: str | None = None

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-FRIDAY-API-Key"] = self.api_key
        return headers

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """POST one chat completion to the gateway; return the parsed body.

        Raises InferenceUnavailableError on transport errors, HTTP errors
        (including the gateway's honest 503 "provider_degraded"), and
        malformed bodies — never returns mock content.
        """
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        url = f"{self.base_url}/v1/chat/completions"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            ) as client:
                response = await client.post(url, json=payload, headers=self._headers())
        except httpx.RequestError as exc:
            raise InferenceUnavailableError(
                f"Inference gateway unreachable at {self.base_url}: {exc}"
            ) from exc
        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                err = body.get("error") if isinstance(body, dict) else None
                if isinstance(err, dict):
                    detail = str(err.get("message") or err.get("code") or "")
                elif isinstance(err, str):
                    detail = err
            except Exception:
                detail = ""
            raise InferenceUnavailableError(
                f"Inference gateway returned HTTP {response.status_code}"
                + (f": {detail}" if detail else "")
            )
        try:
            body = response.json()
        except Exception as exc:
            raise InferenceUnavailableError(
                f"Inference gateway returned a non-JSON body: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise InferenceUnavailableError("Inference gateway returned a malformed body")
        return body

    async def _fetch_health(self) -> dict[str, Any]:
        """GET the gateway's unauthenticated /health document."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # BaseModelProvider contract
    # ------------------------------------------------------------------

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
                self.model_name,
                "auto",
                "gemini-3.8-flash",
                "openai/gpt-oss-120b",
                "qwen/qwen3.8-27b",
                "meta-llama/llama-3.3-70b-instruct",
                "gemini-3.6-flash",
                "nvidia/nemotron-3.5-lightning:free",
            ],
            supports_streaming=True,
            supports_structured_output=True,
            supports_function_calling=True,
            supports_multimodal=False,
            context_window_size=131072,
            max_output_tokens=8192,
        )

    async def health(self) -> ProviderHealthStatus:
        """Checks reachability of the Inference gateway process."""
        start_time = time.perf_counter()
        try:
            data = await self._fetch_health()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderHealthStatus(
                healthy=True,
                provider_name="InferenceProvider",
                message="Inference gateway operational",
                latency_ms=round(latency_ms, 2),
                details={
                    "base_url": self.base_url,
                    "status": data.get("status"),
                    "providers": data.get("providers"),
                },
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
        Execute a completion via the Inference gateway's chat endpoint.

        Fail-closed (TASK-FRG-009): any gateway failure raises
        InferenceUnavailableError. Only an explicit ``enable_fallback=True``
        construction degrades to DirectProvider, and that response is marked
        ``degraded_fallback="direct"`` in its raw_response so downstream task
        output can label the build as mock-generated.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            body = await self._chat_completion(messages, temperature, max_tokens)
            choices = body.get("choices") or []
            content = ""
            finish_reason = "stop"
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                content = message.get("content") or ""
                finish_reason = str(choices[0].get("finish_reason") or "stop")
            if not content.strip():
                raise InferenceUnavailableError(
                    "Inference gateway returned an empty completion"
                )
            usage_body = body.get("usage") or {}
            usage = UsageEstimate(
                prompt_tokens=int(usage_body.get("prompt_tokens") or 0),
                completion_tokens=int(usage_body.get("completion_tokens") or 0),
                total_tokens=int(usage_body.get("total_tokens") or 0),
                estimated_cost_usd=0.0,
            )
            if usage.total_tokens == 0:
                usage = self.estimate_usage(prompt, content)
            self.last_degraded = False
            self.last_error = None
            return ProviderResponse(
                content=content,
                model=str(body.get("model") or self.model_name),
                finish_reason=finish_reason,
                usage=usage,
                raw_response={
                    "served_by_model": body.get("model"),
                    "provenance": body.get("provenance"),
                    "completion_id": body.get("id"),
                },
            )
        except InferenceUnavailableError as exc:
            self.last_degraded = True
            self.last_error = str(exc)
            if not self.enable_fallback:
                raise
            logger.warning(
                "Inference gateway request failed (%s). Falling back to DirectProvider "
                "(explicit legacy fallback; output marked degraded).",
                exc,
            )
            fallback = await self._fallback_provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            raw = dict(fallback.raw_response or {})
            raw["degraded_fallback"] = "direct"
            raw["provider_error"] = str(exc)
            fallback.raw_response = raw
            return fallback

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
        """Generates Pydantic structured output using Inference JSON enforcement.

        TASK-FRG-009: a response that fails schema validation now raises
        instead of being silently replaced by a locally synthesized dummy
        instance (fabricated data wearing a valid schema).
        """
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
        except ValidationError as exc:
            raise ValueError(
                f"Inference output failed schema validation for "
                f"{response_model.__name__}: {exc}"
            ) from exc
