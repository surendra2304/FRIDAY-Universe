"""Provider factory and registry for Inference (Verified Cloud Providers)."""

from app.providers.apinex import ApinexProvider
from app.providers.base import BaseLLMProvider
from app.providers.bytez import BytezProvider
from app.providers.cerebras import CerebrasProvider
from app.providers.cohere import CohereProvider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.huggingface import HuggingFaceProvider
from app.providers.litellm import LiteLLMTransport
from app.providers.litellm_adapter import LiteLLMProvider
from app.providers.llamacpp import LlamaCppTransport
from app.providers.local import LocalProvider
from app.providers.mistral import MistralProvider
from app.providers.nvidia import NvidiaProvider
from app.providers.openai import OpenAIProvider
from app.providers.openai_compatible import OpenAICompatibleTransport
from app.providers.openrouter import OpenRouterProvider
from app.providers.sglang import SGLangTransport
from app.providers.vllm import VLLMTransport

_PROVIDER_MAP: dict[str, type[BaseLLMProvider]] = {
    "cerebras": CerebrasProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "apinex": ApinexProvider,
    "cohere": CohereProvider,
    "huggingface": HuggingFaceProvider,
    "nvidia": NvidiaProvider,
    "bytez": BytezProvider,
    "litellm": LiteLLMProvider,
    "local": LocalProvider,
}

_PROVIDER_CACHE: dict[str, BaseLLMProvider] = {}


def _get_custom_provider(normalized_name: str, kwargs: dict) -> BaseLLMProvider:
    """Build the adapter for a TASK-IG-INF-02 custom endpoint provider.

    The endpoint registry is the only source of truth for these
    providers: an unknown or disabled ``custom-<name>`` is an error,
    never a silent fallthrough to a cloud adapter. The endpoint's own
    key (resolved from its own api_key_env at parse time) is used
    unless the gateway passes the pool-chosen key explicitly — which
    is the same value, from the endpoint's own pool.
    """
    from app.providers.custom_endpoints import custom_endpoint_by_provider
    from app.providers.openai_compatible import OpenAICompatibleProvider

    endpoint = custom_endpoint_by_provider(normalized_name)
    if endpoint is None:
        raise ValueError(
            f"Unsupported provider '{normalized_name}'. No enabled custom endpoint "
            "with that name is configured (see INFERENCE_CUSTOM_ENDPOINTS)."
        )
    if not kwargs and normalized_name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[normalized_name]
    key = endpoint.api_key
    if "api_key" in kwargs:
        key = kwargs["api_key"]
    instance = OpenAICompatibleProvider(
        provider_name=normalized_name,
        base_url=endpoint.base_url,
        api_key=key,
        default_model=endpoint.model_ids[0],
        supported_models=endpoint.model_ids,
        timeout=float(kwargs.get("timeout", 60.0)),
    )
    if not kwargs:
        _PROVIDER_CACHE[normalized_name] = instance
    return instance


def get_provider(name: str = "gemini", **kwargs) -> BaseLLMProvider:
    """Returns a singleton or configured instance of the requested LLM provider."""
    normalized_name = name.lower().strip()
    if normalized_name.startswith("custom-"):
        return _get_custom_provider(normalized_name, kwargs)
    if normalized_name not in _PROVIDER_MAP:
        raise ValueError(f"Unsupported provider '{name}'. Available: {list(_PROVIDER_MAP.keys())}")

    if normalized_name not in _PROVIDER_CACHE or kwargs:
        provider_cls = _PROVIDER_MAP[normalized_name]
        instance = provider_cls(**kwargs)
        if not kwargs:
            _PROVIDER_CACHE[normalized_name] = instance
        return instance

    return _PROVIDER_CACHE[normalized_name]


__all__ = [
    "ApinexProvider",
    "BaseLLMProvider",
    "BytezProvider",
    "CerebrasProvider",
    "CohereProvider",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "LiteLLMProvider",
    "LiteLLMTransport",
    "LlamaCppTransport",
    "LocalProvider",
    "MistralProvider",
    "NvidiaProvider",
    "OpenAICompatibleTransport",
    "OpenAIProvider",
    "OpenRouterProvider",
    "SGLangTransport",
    "VLLMTransport",
    "get_provider",
]
