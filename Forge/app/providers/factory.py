"""
Provider Factory for Project FORGE.
Provides centralized resolution and instantiation of LLM model providers.
"""

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseModelProvider
from app.providers.direct import DirectProvider
from app.providers.inference import InferenceProvider
from app.providers.openai import OpenAIProvider

logger = get_logger("providers.factory")


def get_provider(
    provider_name: str | None = None,
    model_name: str | None = None,
    **kwargs,
) -> BaseModelProvider:
    """
    Factory to retrieve an instantiated BaseModelProvider.
    Resolves provider by name, model prefix heuristics, or application defaults.
    """
    settings = get_settings()
    prov = (provider_name or settings.default_provider or "direct").lower()

    # Heuristic fallback if provider is default/direct but model indicates specific API
    if prov in ["direct", "default"] and model_name:
        if model_name.startswith(("gpt-", "o1", "o3", "text-embedding")):
            prov = "openai"
        elif model_name.startswith("claude-"):
            prov = "anthropic"
        elif model_name.startswith(("llama-", "deepseek-", "qwen-", "gemini-")):
            prov = "inference"

    if prov in ["inference", "ai_universe"]:
        return InferenceProvider(model_name=model_name, **kwargs)
    elif prov == "openai":
        return OpenAIProvider(model_name=model_name, **kwargs)
    elif prov == "anthropic":
        return AnthropicProvider(model_name=model_name, **kwargs)
    elif prov in ["direct", "mock", "local"]:
        return DirectProvider(model_name=model_name, **kwargs)
    else:
        logger.warning(f"Unrecognized provider '{prov}'. Falling back to DirectProvider.")
        return DirectProvider(model_name=model_name, **kwargs)
