"""
Role provider wiring for Project FORGE (TASK-FRG-009).

Before this module, specialist roles obtained a model provider only when a
caller happened to pass one: ``BaseAgent`` defaulted to the deterministic
``DirectProvider`` mock and nothing in production called ``set_provider()``
(TASK-FORGE-002 GAP 4), so every role — planner, architect, developer —
generated its "model output" from a deterministic stub while task results
reported success. TASK-FRG-004's battery proved the consequence end-to-end:
zero of 34 requested layout files produced, every architecture spec the
172-byte stub.

This module is the single resolution point every role instantiation goes
through (``BaseAgent`` when no provider is injected, and
``AgentRegistry.create_agent``):

* The configured provider comes from ``Settings.role_provider``
  (``FORGE_ROLE_PROVIDER``), whose production default is ``"inference"`` —
  the fleet Inference gateway. The Inference provider is constructed
  fail-closed (no silent mock fallback): if the gateway cannot serve, the
  role's generation raises and the task fails honestly.
* Per-role model selection: on the Inference gateway each role requests the
  alias ``forge-<role>`` (overridable via ``Settings.role_models`` /
  ``FORGE_ROLE_MODELS``). The alias is not a catalogue model, so the
  gateway resolves it through its best-suitable routing (TASK-REL-043) and
  the response names the model that actually served.
* ``"direct"`` remains available ONLY as an explicitly configured test/dev
  mode. Providers resolved that way are mocks, and the helpers here let the
  orchestrator and delegate API label their output as such
  (``provider: mock/direct``, generation degraded) — a mock build is never
  reported as a model-generated success.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.providers.base import BaseModelProvider
from app.providers.direct import DirectProvider

logger = get_logger("agents.provider_wiring")

#: Provider kinds whose output is deterministic mock content, not a model.
MOCK_PROVIDER_KINDS = {"direct", "mock"}


def role_model_alias(role_name: str) -> str:
    """Default Inference model alias requested for a role.

    The alias is deliberately NOT a gateway catalogue id: the Inference
    gateway resolves unknown ids through best-suitable routing for the
    request's inferred task type and reports the served model in the
    response (TASK-REL-043).
    """
    return f"forge-{role_name.lower()}"


def provider_kind(provider: BaseModelProvider | None) -> str:
    """Short machine-readable kind for a provider instance."""
    if provider is None:
        return "none"
    from app.providers.inference import InferenceProvider

    if isinstance(provider, DirectProvider):
        return "direct"
    if isinstance(provider, InferenceProvider):
        return "inference"
    name = type(provider).__name__.lower()
    if "openai" in name:
        return "openai"
    if "anthropic" in name:
        return "anthropic"
    return name.removesuffix("provider") or "unknown"


def is_mock_provider(provider: BaseModelProvider | None) -> bool:
    """True when the provider produces deterministic mock output."""
    return provider_kind(provider) in MOCK_PROVIDER_KINDS


def provider_label(provider: BaseModelProvider | None) -> str:
    """Human-readable provider label for task output.

    Mock providers are labelled ``mock/direct`` so a degraded build can
    never be mistaken for a model-generated one. Never includes key
    material — only the kind, model name, and (for Inference) the gateway
    base URL.
    """
    if provider is None:
        return "none"
    kind = provider_kind(provider)
    if kind in MOCK_PROVIDER_KINDS:
        return "mock/direct"
    model = getattr(provider, "model_name", "") or ""
    if kind == "inference":
        base_url = getattr(provider, "base_url", "") or ""
        return f"inference:{model}@{base_url}" if base_url else f"inference:{model}"
    return f"{kind}:{model}" if model else kind


def resolve_role_provider(
    role_name: str,
    settings: Settings | None = None,
    *,
    provider_type: str | None = None,
    model_name: str | None = None,
    preferred_model: str | None = None,
    **provider_kwargs: Any,
) -> BaseModelProvider:
    """Resolve the model provider a specialist role runs on.

    Resolution order for the provider: explicit ``provider_type`` argument,
    then ``Settings.role_provider`` (production default ``"inference"``),
    then ``Settings.default_provider``. For the Inference gateway the model
    is, in order: explicit ``model_name``, ``Settings.role_models[role]``,
    the registry's preferred model for the provider, and finally the
    per-role alias ``forge-<role>`` (best-suitable routing at the gateway).
    """
    settings = settings or get_settings()
    prov = (
        provider_type
        or getattr(settings, "role_provider", None)
        or settings.default_provider
        or "direct"
    ).lower()

    role_models = getattr(settings, "role_models", None) or {}
    routed_model = (
        model_name
        or role_models.get(role_name.lower())
        or preferred_model
    )

    if prov in ("inference", "ai_universe"):
        from app.providers.inference import InferenceProvider

        provider = InferenceProvider(
            model_name=routed_model or role_model_alias(role_name),
            enable_fallback=False,
            **provider_kwargs,
        )
        logger.info(
            "Role '%s' wired to Inference gateway (model alias '%s', base '%s')",
            role_name,
            provider.model_name,
            provider.base_url,
        )
        return provider

    if prov in MOCK_PROVIDER_KINDS or prov == "local":
        provider = DirectProvider(model_name=routed_model or f"direct-{role_name.lower()}")
        logger.warning(
            "Role '%s' wired to the deterministic DirectProvider mock "
            "(explicit test/dev mode via provider '%s'); its output is "
            "labelled provider: mock/direct, generation degraded",
            role_name,
            prov,
        )
        return provider

    if prov in ("openai", "anthropic"):
        from app.providers.factory import get_provider

        return get_provider(provider_name=prov, model_name=routed_model, **provider_kwargs)

    logger.warning(
        "Unrecognized role provider '%s' for role '%s'; falling back to the "
        "DirectProvider mock (output labelled provider: mock/direct)",
        prov,
        role_name,
    )
    return DirectProvider(model_name=routed_model or f"direct-{role_name.lower()}")


def describe_role_providers(settings: Settings | None = None) -> dict[str, Any]:
    """Startup summary of how roles will be wired (no key material)."""
    settings = settings or get_settings()
    prov = (
        getattr(settings, "role_provider", None) or settings.default_provider or "direct"
    ).lower()
    return {
        "role_provider": prov,
        "mock": prov in MOCK_PROVIDER_KINDS or prov == "local",
        "inference_base_url": settings.ai_universe_url if prov in ("inference", "ai_universe") else None,
        "role_models": dict(getattr(settings, "role_models", None) or {}),
    }
