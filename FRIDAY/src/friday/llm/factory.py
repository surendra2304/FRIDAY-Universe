"""LLM Provider Factory."""

import os
from typing import Any, List, Optional

from friday.auth.credential_pool import (
    credential_pool,
    groq_credential_pool,
    mistral_credential_pool,
    openrouter_credential_pool,
)
from friday.core.config import Settings
from friday.core.exceptions import ConfigError
from friday.core.logging import get_logger
from friday.llm.ai_universe_provider import AIUniverseLLMProvider
from friday.llm.base import BaseLLMProvider
from friday.llm.escalation import EscalatingLLMProvider, InferenceChatProvider
from friday.llm.fallback_chain_provider import (
    ExhaustionFailoverProvider,
    FallbackChainLLMProvider,
)
from friday.llm.gemini_provider import GeminiLLMProvider
from friday.llm.groq_provider import GROQ_DEFAULT_MODEL, GroqLLMProvider
from friday.llm.mistral_provider import MISTRAL_DEFAULT_MODEL, MistralLLMProvider
from friday.llm.mock_provider import MockLLMProvider
from friday.llm.openai_provider import OpenAILLMProvider
from friday.llm.openrouter_provider import (
    OPENROUTER_DEFAULT_MODEL,
    OpenRouterLLMProvider,
)

logger = get_logger("llm.factory")

_DEFAULT_LLM_MODEL = Settings.model_fields["llm_model"].default


def _build_inference_chat_provider(settings: Settings) -> InferenceChatProvider | None:
    """TASK-REL-044: the Inference escalation target, or None.

    None when escalation is kill-switched (FRIDAY_LLM_ESCALATION=off) or
    when no Inference endpoint is actually configured: the Settings
    default ``http://inference:8000`` is a compose hostname that resolves
    nowhere outside docker, so the default alone is not a configuration
    (production sets FRIDAY_INFERENCE_URL). With no configured endpoint
    the factory builds exactly the pre-REL-044 stack. Construction never
    probes the network — an unreachable Inference is a per-call fallback
    event inside EscalatingLLMProvider, not a startup failure.
    """
    try:
        from friday.llm.escalation import escalation_enabled

        if not escalation_enabled():
            logger.info("LLM escalation to Inference disabled (FRIDAY_LLM_ESCALATION=off).")
            return None
        url = os.getenv("FRIDAY_INFERENCE_URL") or os.getenv("INFERENCE_URL")
        if not url:
            settings_url = getattr(settings, "inference_url", None)
            if settings_url and settings_url.rstrip("/") != "http://inference:8000":
                url = settings_url
        if not url:
            logger.info(
                "No Inference endpoint configured; LLM escalation not armed "
                "(chat stays on FRIDAY's own pool, pre-REL-044 stack)."
            )
            return None
        key = (
            getattr(settings, "inference_api_key", None)
            or os.getenv("FRIDAY_INFERENCE_API_KEY")
            or ""
        )
        logger.info(f"LLM escalation target armed: Inference chat completions at {url}")
        return InferenceChatProvider(
            base_url=url,
            api_key=key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except Exception as exc:
        logger.warning(
            f"Inference escalation target could not be constructed ({exc}); "
            "continuing without escalation (pre-REL-044 stack)."
        )
        return None


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    """Create and configure the appropriate LLM provider instance from settings."""
    provider_type = settings.llm_provider.lower().strip()

    if provider_type == "mock":
        logger.info(f"Initializing Mock LLM Provider (model: {settings.llm_model})")
        return MockLLMProvider(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if provider_type in ("ai_universe", "inference"):
        url = (
            getattr(settings, "inference_url", None)
            or os.getenv("FRIDAY_INFERENCE_URL")
            or getattr(settings, "universe_api_url", None)
            or "http://inference:8000"
        )
        key = (
            getattr(settings, "inference_api_key", None)
            or os.getenv("FRIDAY_INFERENCE_API_KEY")
            or ""
        )
        logger.info(f"Initializing Inference Gateway LLM Provider (URL: {url})")
        return AIUniverseLLMProvider(base_url=url, api_key=key)

    if provider_type == "gemini":
        has_explicit = (settings.gemini_api_key is not None) or (settings.llm_api_key is not None)
        has_keys = (
            bool(settings.gemini_api_key)
            or bool(settings.llm_api_key)
            or bool(os.getenv("FRIDAY_GEMINI_API_KEY"))
            or (credential_pool and len(getattr(credential_pool, "credentials", [])) > 0)
        )
        if not has_keys and not has_explicit:
            logger.info("Direct Gemini API key not configured; using the configured Inference Gateway provider pool.")
            url = getattr(settings, "inference_url", None) or os.getenv("FRIDAY_INFERENCE_URL") or "http://inference:8000"
            key = getattr(settings, "inference_api_key", None) or os.getenv("FRIDAY_INFERENCE_API_KEY") or ""
            return AIUniverseLLMProvider(base_url=url, api_key=key)

        api_key = settings.gemini_api_key if settings.gemini_api_key is not None else settings.llm_api_key
        if api_key is None:
            api_key = os.getenv("FRIDAY_GEMINI_API_KEY")
            if api_key is not None and not api_key.strip():
                api_key = None
        elif not api_key.strip():
            # An explicitly supplied pair of blank settings means the caller
            # requested Gemini but omitted its key; preserve that marker so
            # the provider raises the clear missing-key error.  Blank values
            # inherited from ambient environment aliases remain absent and
            # must not disable credential-pool failover.
            explicitly_blank = (
                settings.gemini_api_key == ""
                and settings.llm_api_key == ""
            )
            api_key = "" if explicitly_blank else None

        model_name = settings.gemini_model or settings.llm_model
        temperature = settings.gemini_temperature if settings.gemini_temperature is not None else settings.llm_temperature
        max_tokens = settings.gemini_max_tokens if settings.gemini_max_tokens is not None else settings.llm_max_tokens
        logger.info(f"Initializing Google Gemini Provider (model: {model_name}, cost_mode: {settings.cost_mode})")
        gemini_provider = GeminiLLMProvider(
            api_key=api_key,
            credential_pool=credential_pool,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.gemini_timeout,
            max_retries=settings.gemini_max_retries,
            backoff_factor=settings.gemini_backoff_factor,
            cost_mode=settings.cost_mode,
            thinking_level=getattr(settings, "llm_thinking_level", "medium"),
        )

        # TASK-REL-010: pool-exhaustion failover. The owner's design makes
        # Groq the text fallback, but this branch historically returned the
        # bare Gemini provider, so a fully benched Gemini pool killed chat
        # outright (production incident 2026-11-14). When a Groq credential
        # is configured, wrap Gemini in a single-purpose exhaustion failover
        # whose fallback is a Groq provider built by the groq branch itself
        # (identical construction, no duplicated configuration).
        groq_available = (
            bool(getattr(settings, "groq_api_key", None))
            or bool(os.getenv("FRIDAY_GROQ_API_KEY"))
            or bool(getattr(groq_credential_pool, "credentials", None))
        )
        # TASK-REL-044: owner routing policy — chat stays on FRIDAY's own
        # pool; complex tasks escalate to Inference (friday.llm.escalation).
        # The escalation wrapper also re-orders the REL-010 exhaustion
        # safety net when an Inference endpoint is configured: the
        # exhaustion fallback tries Inference FIRST (the rung that brings
        # more usage, per the owner's words) with Groq behind it, so
        # REL-010's never-die-on-exhaustion guarantee is preserved and
        # strengthened. With no Inference configured, the stack below is
        # exactly the pre-REL-044 one.
        inference_provider = _build_inference_chat_provider(settings)
        own_stack: BaseLLMProvider = gemini_provider
        if groq_available:
            try:
                groq_provider = create_llm_provider(
                    settings.model_copy(update={"llm_provider": "groq"})
                )
                logger.info(
                    "Gemini pool-exhaustion failover armed: Groq text provider "
                    "stands by if the Gemini credential pool is exhausted."
                )
                exhaustion_fallback: BaseLLMProvider = (
                    FallbackChainLLMProvider([inference_provider, groq_provider])
                    if inference_provider is not None
                    else groq_provider
                )
                own_stack = ExhaustionFailoverProvider(
                    primary=gemini_provider, fallback=exhaustion_fallback
                )
            except Exception as exc:
                logger.warning(
                    f"Groq exhaustion failover could not be constructed ({exc}); "
                    "continuing with the Gemini provider only."
                )
                own_stack = gemini_provider
        if inference_provider is not None:
            return EscalatingLLMProvider(own=own_stack, inference=inference_provider)
        return own_stack

    if provider_type == "groq":
        # Ensure Groq never inherits Gemini model names
        candidate = settings.groq_model or settings.llm_model
        model_name = (
            GROQ_DEFAULT_MODEL
            if (not candidate or "gemini" in candidate.lower() or candidate == _DEFAULT_LLM_MODEL)
            else candidate
        )
        logger.info(f"Initializing Groq Provider (model: {model_name})")
        return GroqLLMProvider(
            api_key=settings.groq_api_key or settings.llm_api_key,
            credential_pool=groq_credential_pool,
            model=model_name,
            fallback_model=settings.groq_fallback_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if provider_type == "openrouter":
        candidate = settings.openrouter_model or settings.llm_model
        model_name = (
            OPENROUTER_DEFAULT_MODEL
            if (not candidate or "/" not in candidate or candidate == _DEFAULT_LLM_MODEL)
            else candidate
        )
        logger.info(f"Initializing OpenRouter Provider (model: {model_name})")
        return OpenRouterLLMProvider(
            api_key=settings.openrouter_api_key or settings.llm_api_key,
            credential_pool=openrouter_credential_pool,
            model=model_name,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if provider_type == "chain":
        # In multi-provider fallback chains, enforce independent provider-compatible models
        groq_model = settings.groq_model or GROQ_DEFAULT_MODEL
        openrouter_model = settings.openrouter_model or OPENROUTER_DEFAULT_MODEL
        mistral_model = settings.mistral_model or MISTRAL_DEFAULT_MODEL
        gemini_model = settings.gemini_model or (
            settings.llm_model if "gemini" in settings.llm_model.lower() else "gemini-1.5-flash-latest"
        )
        chain_providers: List[BaseLLMProvider] = []

        has_gemini = (
            bool(settings.gemini_api_key)
            or bool(os.getenv("FRIDAY_GEMINI_API_KEY"))
            or bool(os.getenv("GEMINI_API_KEY"))
            or (credential_pool and len(getattr(credential_pool, "credentials", [])) > 0)
        )
        if has_gemini:
            chain_providers.append(
                GeminiLLMProvider(
                    api_key=settings.gemini_api_key or os.getenv("FRIDAY_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"),
                    credential_pool=credential_pool,
                    model=gemini_model,
                    temperature=settings.gemini_temperature if settings.gemini_temperature is not None else settings.llm_temperature,
                    max_tokens=settings.gemini_max_tokens if settings.gemini_max_tokens is not None else settings.llm_max_tokens,
                    timeout=settings.gemini_timeout,
                    max_retries=settings.gemini_max_retries,
                    backoff_factor=settings.gemini_backoff_factor,
                    cost_mode=settings.cost_mode,
                    thinking_level=getattr(settings, "llm_thinking_level", "medium"),
                )
            )

        chain_providers.append(
            GroqLLMProvider(
                api_key=settings.groq_api_key or settings.llm_api_key,
                credential_pool=groq_credential_pool,
                model=groq_model,
                fallback_model=settings.groq_fallback_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        )

        chain_providers.extend([
            MistralLLMProvider(
                api_key=settings.mistral_api_key or settings.llm_api_key,
                credential_pool=mistral_credential_pool,
                model=mistral_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            ),
            OpenRouterLLMProvider(
                api_key=settings.openrouter_api_key or settings.llm_api_key,
                credential_pool=openrouter_credential_pool,
                model=openrouter_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            ),
        ])

        inf_url = (
            getattr(settings, "inference_url", None)
            or os.getenv("INFERENCE_URL")
            or os.getenv("FRIDAY_INFERENCE_URL")
            or "http://inference:8000"
        )
        inf_key = (
            getattr(settings, "inference_api_key", None)
            or os.getenv("INFERENCE_API_KEY")
            or os.getenv("FRIDAY_INFERENCE_API_KEY")
            or ""
        )
        
        chain_providers.append(
            AIUniverseLLMProvider(
                base_url=inf_url,
                api_key=inf_key,
            )
        )
        logger.info(
            "Initializing Fallback Chain Provider: "
            + " -> ".join(p.provider_name for p in chain_providers)
        )
        return FallbackChainLLMProvider(providers=chain_providers)

    if provider_type == "mistral":
        candidate = settings.mistral_model or settings.llm_model
        model_name = (
            MISTRAL_DEFAULT_MODEL
            if (not candidate or "gemini" in candidate.lower() or candidate == _DEFAULT_LLM_MODEL)
            else candidate
        )
        logger.info(f"Initializing Mistral Provider (model: {model_name})")
        return MistralLLMProvider(
            api_key=settings.mistral_api_key or settings.llm_api_key,
            credential_pool=mistral_credential_pool,
            model=model_name,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if provider_type in ("openai", "ollama"):
        logger.info(f"Initializing OpenAI-compatible Provider (provider: {provider_type}, model: {settings.llm_model})")
        return OpenAILLMProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    raise ConfigError(
        f"Unsupported LLM provider: '{settings.llm_provider}'. "
        "Supported: 'mock', 'openai', 'gemini', 'groq', 'openrouter', 'mistral', 'chain', 'ai_universe', 'inference', 'ollama'"
    )
