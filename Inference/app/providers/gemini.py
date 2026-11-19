"""Google Gemini LLM Provider Adapter."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import (
    BaseLLMProvider,
    ProviderCapabilities,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    UsageEstimate,
)
from app.providers.http_client import get_shared_client
from app.utils.logger import logger


class GeminiProvider(BaseLLMProvider):
    """Adapter for Google Gemini API via async HTTP."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-flash-latest"
    # TASK-REL-030: gemini-2.5-flash removed — Google returns 404 for it
    # ("no longer available to new users") with this deployment's keys.
    # gemini-3.6-flash (verified generating) and gemini-3.8-flash (verified
    # listed; demand-limited on the free tier) added.
    # TASK-INF-015: gemini-3.5-flash-lite added — the current Flash-Lite
    # id (free tier 15 RPM / 500 RPD, verified from two independent
    # free-project readings, Sep + Oct 2026). NOTE: listing here is the
    # provider-adapter catalogue only; live generation with this
    # deployment's keys is a post-merge probe, not claimed by INF-015.
    # TASK-INF-017: gemini-2.5-flash-lite REMOVED. INF-015 kept the
    # legacy access-limited id only because existing callers still
    # named it (TASK-VOI-020's voice key-probe pin among them);
    # TASK-VOI-021 moved that pin to the explicit gemini-3.5-flash-lite
    # id, leaving the legacy entry with no production caller. Owner
    # order 2026-11-19: the fleet pins gemini-3.5-flash-lite — the
    # legacy id (which Google would silently route to 3.5 from
    # 2026-12-01 anyway) no longer spends this deployment's keys.
    SUPPORTED_MODELS = [
        "gemini-flash-latest",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-pro-latest",
    ]

    def __init__(self, api_key: str | None = None, default_model: str | None = None, timeout: float = 60.0) -> None:
        self.api_keys = settings.get_provider_keys("gemini")
        if api_key:
            self.api_keys = [k.strip() for k in api_key.split(",") if k.strip()]
        self._key_index = 0
        self.default_model = default_model or self.DEFAULT_MODEL
        self.timeout = timeout

    @property
    def api_key(self) -> str | None:
        if not self.api_keys:
            return None
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

    @property
    def provider_name(self) -> str:
        return "gemini"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_name="gemini",
            supported_models=self.SUPPORTED_MODELS,
            supports_streaming=True,
            supports_structured_output=True,
            supports_system_instructions=True,
            supports_tool_calling=True,
            max_context_window=1000000,
            rate_limits={"rpm": 15, "rpd": 1500, "tpm": 1000000},
        )

    def estimate_usage(self, request: ProviderRequest) -> UsageEstimate:
        """Heuristic estimation of tokens and compute cost."""
        total_chars = sum(len(m.content) for m in request.messages)
        if request.system_instruction:
            total_chars += len(request.system_instruction)

        # Rule of thumb: ~4 characters per token
        prompt_tokens = max(1, total_chars // 4)
        max_completion = request.max_tokens or 1000

        # Approximate Gemini Flash pricing ($0.075 / 1M input, $0.30 / 1M output)
        cost = (prompt_tokens * 0.000000075) + (max_completion * 0.00000030)

        return UsageEstimate(
            estimated_prompt_tokens=prompt_tokens,
            estimated_completion_tokens=max_completion,
            estimated_total_tokens=prompt_tokens + max_completion,
            estimated_cost_usd=round(cost, 6),
        )

    # TASK-INF-009: Gemini thinking models (the 2.5/3.x families and the
    # -latest aliases, which resolve to current thinking models) reason
    # before answering, and the API charges those hidden thought tokens
    # against maxOutputTokens — that ceiling is on thoughts + visible
    # output COMBINED (usageMetadata.thoughtsTokenCount +
    # candidatesTokenCount). Passing a caller's max_tokens verbatim as
    # maxOutputTokens therefore lets the reasoning burn consume the
    # entire visible budget (TASK-INF-005 measured finish_reason
    # MAX_TOKENS with 0-15 visible tokens on 14/17 served calls). The
    # adapter now accounts thinking separately: maxOutputTokens =
    # declared budget + thinking allowance, with the allowance
    # hard-capped via thinkingConfig.thinkingBudget.
    DEFAULT_THINKING_TOKEN_ALLOWANCE = 1024
    MAX_OUTPUT_TOKENS_CEILING = 65536  # documented per-response output cap

    # TASK-INF-011: measured on S1 (gemini-egress-diag, 2026-11-17), a
    # tiny prompt to gemini-3.6-flash took 45.3s to first byte with
    # default thinking and 22.6s with thinkingBudget=0 — the model's
    # default reasoning adds ~13-23s of latency before any visible
    # token, which is most of why Gemini blew the gateway's primary
    # slice and failed over. Flash models therefore default to the
    # GEMINI_FLASH_THINKING_BUDGET setting (0 = thinking off) instead
    # of the allowance above. The allowance still governs the Pro
    # family: Gemini 2.5 Pro cannot think below a 128-token budget,
    # so sending it 0 would be an unsupported value.
    _THINKING_FAMILIES = ("gemini-3", "gemini-2.5")
    _THINKING_ALIASES = {"gemini-flash-latest", "gemini-pro-latest"}

    def _thinks_by_default(self, model: str) -> bool:
        """True for models that reason before answering unless told not to.

        Flash-Lite models do not think by default (thinking starts only
        when a thinkingConfig explicitly enables it), so they are
        excluded even though their family names match.
        """
        name = (model or "").lower()
        if "lite" in name:
            return False
        return name in self._THINKING_ALIASES or any(f in name for f in self._THINKING_FAMILIES)

    @staticmethod
    def _is_flash_model(model: str) -> bool:
        """True for the Flash generation family (incl. the
        gemini-flash-latest alias). Flash-Lite also matches this test
        but never reaches the default plan: _thinks_by_default already
        excludes it, and its payload stays thinkingConfig-free."""
        return "flash" in (model or "").lower()

    def _flash_thinking_budget(self) -> int:
        """The configured default thinking budget for Flash models.

        Settings field GEMINI_FLASH_THINKING_BUDGET (env-tunable),
        measured default 0 = thinking disabled (TASK-INF-011).
        Negative or unreadable values clamp to 0 — never guess a
        positive budget the operator did not set."""
        try:
            return max(0, int(settings.GEMINI_FLASH_THINKING_BUDGET))
        except (TypeError, ValueError):
            return 0

    def _thinking_plan(self, request: ProviderRequest, model: str) -> dict[str, Any] | None:
        """Resolve how this request's thinking is budgeted.

        Returns None when no thinking accounting applies (the model does
        not think by default and the caller configured nothing), else a
        dict with:
          allowance       — tokens reserved for thinking ON TOP OF the
                            caller's declared visible budget;
          thinking_config — the thinkingConfig object to send;
          explicit        — True when the caller configured thinking
                            via extra_params (such a configuration is
                            honoured even with no declared budget).
        A caller's explicit extra_params win: "thinking_budget" (int,
        hard cap on thought tokens) or "thinking_level" (str, the
        Gemini 3 knob — a level is not a token cap, so the allowance
        still reserves the visible budget on top).
        """
        extra = request.extra_params or {}
        budget = extra.get("thinking_budget")
        level = extra.get("thinking_level")
        if budget is not None:
            try:
                allowance = max(0, int(budget))
            except (TypeError, ValueError):
                allowance = self.DEFAULT_THINKING_TOKEN_ALLOWANCE
            # Gemini 2.5 Pro cannot think below a 128-token budget.
            if "pro" in (model or "").lower() and allowance < 128:
                allowance = 128
            return {"allowance": allowance, "thinking_config": {"thinkingBudget": allowance}, "explicit": True}
        if level is not None:
            return {
                "allowance": self.DEFAULT_THINKING_TOKEN_ALLOWANCE,
                "thinking_config": {"thinkingLevel": str(level)},
                "explicit": True,
            }
        if not self._thinks_by_default(model):
            return None
        if self._is_flash_model(model):
            # TASK-INF-011: Flash defaults to the configured budget
            # (0 = thinking off; see the measurement note above). The
            # plan is flagged default_minimal so _build_payload sends
            # the thinkingConfig even when the caller declared no
            # max_tokens — otherwise the disable would silently not
            # apply to exactly the unbounded requests.
            budget = self._flash_thinking_budget()
            return {
                "allowance": budget,
                "thinking_config": {"thinkingBudget": budget},
                "explicit": False,
                "default_minimal": True,
            }
        return {
            "allowance": self.DEFAULT_THINKING_TOKEN_ALLOWANCE,
            "thinking_config": {"thinkingBudget": self.DEFAULT_THINKING_TOKEN_ALLOWANCE},
            "explicit": False,
        }

    def _convert_messages(self, messages: list[ProviderMessage]) -> list[dict[str, Any]]:
        """Converts standardized ProviderMessages to Gemini contents structure."""
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = "model" if msg.role in ("assistant", "model") else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})
        return contents

    def _build_payload(self, request: ProviderRequest, model: str | None = None) -> dict[str, Any]:
        """Constructs the JSON payload for the Gemini generateContent API."""
        contents = self._convert_messages(request.messages)
        effective_model = model or request.model or self.default_model

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
            },
        }

        plan = self._thinking_plan(request, effective_model)
        if request.max_tokens:
            if plan is None:
                payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
            else:
                # The declared budget buys VISIBLE output; thinking is
                # reserved on top of it and hard-capped by
                # thinkingConfig, because the API charges thoughts
                # against the same maxOutputTokens ceiling.
                payload["generationConfig"]["maxOutputTokens"] = min(
                    request.max_tokens + plan["allowance"],
                    self.MAX_OUTPUT_TOKENS_CEILING,
                )
                if plan["thinking_config"] is not None:
                    payload["generationConfig"]["thinkingConfig"] = plan["thinking_config"]
        elif (
            plan is not None
            and plan["thinking_config"] is not None
            and (plan["explicit"] or plan.get("default_minimal"))
        ):
            # No declared budget to protect, but honour a caller's
            # explicit thinking configuration — and, for Flash models,
            # the default thinking budget (TASK-INF-011), which must
            # reach the wire even on unbounded requests.
            payload["generationConfig"]["thinkingConfig"] = plan["thinking_config"]

        if request.response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        if request.system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": request.system_instruction}]}

        return payload

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate full completion using Gemini REST API."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        model = request.model or self.default_model
        url = f"{self.BASE_URL}/models/{model}:generateContent"
        payload = self._build_payload(request, model)
        max_attempts = min(3, len(self.api_keys)) if self.api_keys else 1

        for attempt in range(max_attempts):
            active_key = self.api_key
            headers = {"Content-Type": "application/json", "x-goog-api-key": active_key}
            start_time = time.perf_counter()
            try:
                client = await get_shared_client()
                response = await client.post(url, headers=headers, json=payload, timeout=self.timeout)
                latency = time.perf_counter() - start_time

                if response.status_code == 503 and model != "gemini-3.6-flash":
                    logger.warning(
                        "Gemini model %s experienced 503 high demand; failing over to gemini-3.6-flash",
                        model,
                    )
                    fallback_req = ProviderRequest(
                        messages=request.messages,
                        system_instruction=request.system_instruction,
                        model="gemini-3.6-flash",
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        response_schema=request.response_schema,
                        extra_params=request.extra_params,
                    )
                    return await self.generate(fallback_req)

                if response.status_code in (429, 503):
                    if attempt < max_attempts - 1:
                        logger.warning(
                            "Gemini transient error (%d) on key %s... for model %s; rotating to next key (attempt %d/%d)",
                            response.status_code,
                            active_key[:8] if active_key else "unknown",
                            model,
                            attempt + 1,
                            max_attempts,
                        )
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        if response.status_code == 429:
                            raise RuntimeError("Gemini API rate limit exceeded across rotated keys (HTTP 429).")
                        else:
                            raise RuntimeError(f"Gemini API temporarily unavailable (HTTP 503): {response.text}")
                elif response.status_code != 200:
                    error_msg = response.text
                    logger.error("Gemini API error (%d): %s", response.status_code, error_msg)
                    raise RuntimeError(f"Gemini API returned HTTP {response.status_code}: {error_msg}")

                data = response.json()

                # Extract text from response candidates
                candidates = data.get("candidates", [])
                if not candidates:
                    return ProviderResponse(
                        content="",
                        model=model,
                        provider=self.provider_name,
                        latency_seconds=latency,
                        finish_reason="empty",
                        raw_response=data,
                    )

                content_parts = candidates[0].get("content", {}).get("parts", [])
                generated_text = "".join(part.get("text", "") for part in content_parts)
                finish_reason = candidates[0].get("finishReason", "stop")

                # Extract token usage metadata. TASK-INF-009: also read
                # the hidden reasoning burn (thoughtsTokenCount). It is
                # included in totalTokenCount but NOT in
                # candidatesTokenCount; until now it was never read, so
                # the gateway's own accounting could not see the tokens
                # that were consuming callers' visible budgets.
                usage = data.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount", 0)
                completion_tokens = usage.get("candidatesTokenCount", 0)
                thoughts_tokens = usage.get("thoughtsTokenCount")
                total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

                # Honest accounting, carried on raw_response alongside
                # the gateway's fallback_provenance convention: if a
                # model still truncates (e.g. it ignored the thinking
                # cap), the split says so — truncated + how much of the
                # ceiling the thinking ate — instead of the truncated
                # text passing as a normal answer.
                plan = self._thinking_plan(request, model)
                accounting = {
                    "declared_max_tokens": request.max_tokens,
                    "effective_max_output_tokens": payload["generationConfig"].get("maxOutputTokens"),
                    "thinking_budget": plan["allowance"] if plan else None,
                    "thoughts_tokens": thoughts_tokens or 0,
                    "visible_tokens": completion_tokens,
                    "truncated": finish_reason == "MAX_TOKENS",
                    "thinking_overflow": bool(
                        plan and thoughts_tokens is not None and thoughts_tokens > plan["allowance"]
                    ),
                }
                if accounting["truncated"]:
                    logger.warning(
                        "Gemini %s truncated at MAX_TOKENS: %s thought tokens vs %s visible "
                        "(declared budget %s, thinking allowance %s) — answer is incomplete",
                        model,
                        thoughts_tokens,
                        completion_tokens,
                        request.max_tokens,
                        accounting["thinking_budget"],
                    )
                raw = dict(data)
                raw["token_accounting"] = accounting

                return ProviderResponse(
                    content=generated_text,
                    model=model,
                    provider=self.provider_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    reasoning_tokens=thoughts_tokens,
                    latency_seconds=round(latency, 4),
                    finish_reason=finish_reason,
                    raw_response=raw,
                )

            except httpx.TimeoutException as exc:
                if attempt < max_attempts - 1:
                    logger.warning("Gemini request timed out on key %s...; retrying next key", active_key[:8] if active_key else "unknown")
                    continue
                logger.error("Gemini request timed out after %.1fs", self.timeout)
                raise TimeoutError(f"Gemini API request timed out after {self.timeout}s") from exc
            except httpx.RequestError as exc:
                if attempt < max_attempts - 1:
                    logger.warning("Gemini network error on key %s...; retrying next key", active_key[:8] if active_key else "unknown")
                    continue
                logger.error("Gemini network request failure: %s", type(exc).__name__)
                raise RuntimeError(f"Gemini network connection error: {type(exc).__name__}") from exc

        raise RuntimeError("Gemini request exhausted all retry attempts without a response.")

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """Stream generated chunks using Gemini Server-Sent Events (SSE)."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        model = request.model or self.default_model
        url = f"{self.BASE_URL}/models/{model}:streamGenerateContent?alt=sse"
        payload = self._build_payload(request, model)
        max_attempts = min(3, len(self.api_keys)) if self.api_keys else 1

        for attempt in range(max_attempts):
            active_key = self.api_key
            headers = {"Content-Type": "application/json", "x-goog-api-key": active_key}
            try:
                client = await get_shared_client()
                async with client.stream("POST", url, headers=headers, json=payload, timeout=self.timeout) as stream_resp:
                    if stream_resp.status_code == 503 and model != "gemini-3.6-flash":
                        logger.warning(
                            "Gemini model %s stream experienced 503 high demand; failing over to gemini-3.6-flash",
                            model,
                        )
                        fallback_req = ProviderRequest(
                            messages=request.messages,
                            system_instruction=request.system_instruction,
                            model="gemini-3.6-flash",
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                            response_schema=request.response_schema,
                            extra_params=request.extra_params,
                        )
                        async for chunk in self.stream(fallback_req):
                            yield chunk
                        return

                    if stream_resp.status_code in (429, 503) and attempt < max_attempts - 1:
                        logger.warning(
                            "Gemini stream transient error (%d) on key %s...; rotating to next key (attempt %d/%d)",
                            stream_resp.status_code,
                            active_key[:8] if active_key else "unknown",
                            attempt + 1,
                            max_attempts,
                        )
                        await asyncio.sleep(0.3)
                        continue

                    if stream_resp.status_code != 200:
                        error_body = await stream_resp.aread()
                        raise RuntimeError(
                            f"Gemini streaming failed (HTTP {stream_resp.status_code}): {error_body.decode('utf-8')}"
                        )

                    async for line in stream_resp.aiter_lines():
                        if line.startswith("data: "):
                            raw_json = line[6:].strip()
                            if raw_json == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(raw_json)
                                candidates = chunk_data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        text_chunk = part.get("text", "")
                                        if text_chunk:
                                            yield text_chunk
                            except json.JSONDecodeError:
                                continue
                    return
            except httpx.RequestError as exc:
                if attempt < max_attempts - 1:
                    continue
                logger.error("Gemini streaming network error: %s", type(exc).__name__)
                raise RuntimeError(f"Gemini streaming connection error: {type(exc).__name__}") from exc

    async def health(self) -> bool:
        """Check provider health and key validity with a minimal probe."""
        if not self.api_key:
            return False

        url = f"{self.BASE_URL}/models/{self.default_model}"
        headers = {"x-goog-api-key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("Gemini health check failed: %s", str(exc))
            return False
