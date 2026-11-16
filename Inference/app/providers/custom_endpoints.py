"""TASK-IG-INF-02 — operator-configured custom inference endpoints.

Corpus source: Dctokdztllm — "Support third-party/custom inference
endpoints in FRIDAY's tooling so agents can run on alternate providers."

Before this module, exactly ONE alternate endpoint could be configured:
the ``local`` provider (LOCAL_BASE_URL / LOCAL_MODEL / LOCAL_API_KEY).
That covers a self-hosted server on the LAN, but not the general case
the corpus asks for — an operator pointing Inference at an arbitrary
OpenAI-compatible endpoint (a hosted aggregator, a box on the owner's
desk, a departmental server) with its own models, addressable by name.

Configuration is a single env var holding a JSON array:

    INFERENCE_CUSTOM_ENDPOINTS='[
      {"name": "deskbox",
       "base_url": "http://192.168.1.50:8080/v1",
       "models": [{"id": "desk-llama-70b", "context_window": 131072}]},
      {"name": "aggregator",
       "base_url": "https://api.example-aggregator.com/v1",
       "api_key_env": "AGGREGATOR_API_KEY",
       "models": ["agg/auto"]}
    ]'

Each entry becomes a gateway provider named ``custom-<name>`` and its
models become addressable by id through /v1/chat/completions.

Hard rules, enforced here and pinned by tests:

* **Key isolation.** An endpoint's key is read ONLY from the env var
  its own ``api_key_env`` names — never through
  ``settings.get_provider_keys``, which merges the THIRD_PARTY_* and
  fallback pools. A custom endpoint can therefore never silently spend
  (or be spent by) another pool's credentials.
* **Fail-closed parsing.** Malformed JSON registers nothing. An entry
  with a bad name, a non-HTTP(S) base URL, no models, a duplicate
  provider name, or a model id already claimed by another endpoint is
  rejected and logged; the rest of the deployment is unaffected.
* **Missing key = disabled, loudly.** If ``api_key_env`` names a
  variable that is unset or empty, the endpoint is registered as
  DISABLED with the reason recorded — never silently keyless against
  an endpoint the operator believes is authenticated. Omitting
  ``api_key_env`` entirely is the explicit keyless choice (LAN /
  self-hosted servers, the ``local`` provider's semantics).
* **Not the verified catalogue.** Custom models are deployment-local
  and unverified, so they are NOT added to MODEL_CATALOG or to
  REL-043's suitability rankings. They serve only when a caller names
  them explicitly; best-suitable selection never substitutes one in
  unasked. (Admission to the catalogue remains the INF-005 /
  TASK-IG-INF-03 benchmark path.)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from app.utils.logger import logger

#: Provider-name prefix for every custom endpoint. The full provider
#: name is ``custom-<name>``; the prefix is also how the gateway and
#: the provider factory recognise these providers.
PROVIDER_PREFIX = "custom-"

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


@dataclass
class CustomEndpoint:
    """One validated custom-endpoint configuration."""

    name: str
    base_url: str
    models: list[dict[str, Any]] = field(default_factory=list)
    api_key_env: str | None = None
    api_key: str | None = None  # resolved value; never logged
    enabled: bool = True
    disabled_reason: str | None = None

    @property
    def provider_name(self) -> str:
        return f"{PROVIDER_PREFIX}{self.name}"

    @property
    def model_ids(self) -> list[str]:
        return [str(m["id"]) for m in self.models]


def _parse_entry(
    entry: Any,
    environ: Any,
    seen_providers: set[str],
    seen_models: set[str],
) -> CustomEndpoint | None:
    """Validate one config entry; None (with a logged reason) if unusable."""
    if not isinstance(entry, dict):
        logger.error("CUSTOM ENDPOINTS: entry is not an object (%r); skipped.", entry)
        return None
    name = str(entry.get("name") or "").strip().lower()
    if not _NAME_RE.match(name):
        logger.error(
            "CUSTOM ENDPOINTS: invalid endpoint name %r (want [a-z0-9][a-z0-9_-]{0,31}); skipped.",
            entry.get("name"),
        )
        return None
    provider_name = f"{PROVIDER_PREFIX}{name}"
    if provider_name in seen_providers:
        logger.error("CUSTOM ENDPOINTS: duplicate endpoint name %r; skipped.", name)
        return None
    base_url = str(entry.get("base_url") or "").strip()
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        logger.error(
            "CUSTOM ENDPOINTS: endpoint %r has no http(s) base_url; skipped.", name
        )
        return None
    raw_models = entry.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        logger.error("CUSTOM ENDPOINTS: endpoint %r declares no models; skipped.", name)
        return None
    models: list[dict[str, Any]] = []
    for raw in raw_models:
        if isinstance(raw, str):
            model_id, context_window = raw.strip(), None
        elif isinstance(raw, dict):
            model_id = str(raw.get("id") or "").strip()
            context_window = raw.get("context_window")
            if context_window is not None:
                try:
                    context_window = int(context_window)
                except (TypeError, ValueError):
                    context_window = None
        else:
            model_id, context_window = "", None
        if not model_id:
            logger.error(
                "CUSTOM ENDPOINTS: endpoint %r has a model entry with no id; entry skipped.",
                name,
            )
            return None
        if model_id.lower() in seen_models:
            logger.error(
                "CUSTOM ENDPOINTS: model id %r is claimed by more than one endpoint; "
                "endpoint %r skipped (ambiguous ownership must fail closed).",
                model_id,
                name,
            )
            return None
        models.append({"id": model_id, "context_window": context_window})
    if not models:
        logger.error("CUSTOM ENDPOINTS: endpoint %r has no usable models; skipped.", name)
        return None

    api_key_env = entry.get("api_key_env")
    api_key_env = str(api_key_env).strip() if api_key_env else None
    api_key = None
    enabled = bool(entry.get("enabled", True))
    disabled_reason = None
    if not enabled:
        disabled_reason = "disabled in configuration"
    if api_key_env:
        api_key = (environ.get(api_key_env) or "").strip() or None
        if api_key is None and enabled:
            enabled = False
            disabled_reason = f"api_key_env {api_key_env} is not set or empty"
    endpoint = CustomEndpoint(
        name=name,
        base_url=base_url,
        models=models,
        api_key_env=api_key_env,
        api_key=api_key,
        enabled=enabled,
        disabled_reason=disabled_reason,
    )
    if enabled:
        seen_providers.add(provider_name)
        seen_models.update(m["id"].lower() for m in models)
    else:
        logger.error(
            "CUSTOM ENDPOINTS: endpoint %r registered DISABLED (%s).",
            name,
            disabled_reason,
        )
    return endpoint


def parse_custom_endpoints(raw: str | None, environ: Any = None) -> list[CustomEndpoint]:
    """Parse and validate the INFERENCE_CUSTOM_ENDPOINTS JSON array.

    Fail-closed: unparseable input registers NOTHING (an empty list),
    so a typo can never half-configure the gateway. ``environ`` is
    injectable for tests; production passes os.environ by default.
    """
    environ = os.environ if environ is None else environ
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(
            "CUSTOM ENDPOINTS: INFERENCE_CUSTOM_ENDPOINTS is not valid JSON (%s); "
            "no custom endpoints registered.",
            exc,
        )
        return []
    if not isinstance(data, list):
        logger.error(
            "CUSTOM ENDPOINTS: INFERENCE_CUSTOM_ENDPOINTS must be a JSON array; "
            "no custom endpoints registered."
        )
        return []
    endpoints: list[CustomEndpoint] = []
    seen_providers: set[str] = set()
    seen_models: set[str] = set()
    for entry in data:
        endpoint = _parse_entry(entry, environ, seen_providers, seen_models)
        if endpoint is not None:
            endpoints.append(endpoint)
    return endpoints


# ---------------------------------------------------------------------------
# Process-wide registry (lazy; settings is imported inside the function
# because app.core.config must never import this module at module level).
# ---------------------------------------------------------------------------

_cache: list[CustomEndpoint] | None = None


def get_custom_endpoints() -> list[CustomEndpoint]:
    """All configured custom endpoints (enabled and disabled), parsed once."""
    global _cache
    if _cache is None:
        from app.core.config import settings

        _cache = parse_custom_endpoints(
            getattr(settings, "INFERENCE_CUSTOM_ENDPOINTS", "") or ""
        )
        for endpoint in _cache:
            if endpoint.enabled:
                logger.info(
                    "CUSTOM ENDPOINTS: registered provider %s (%s, %d model(s))",
                    endpoint.provider_name,
                    endpoint.base_url,
                    len(endpoint.models),
                )
    return _cache


def reset_custom_endpoints_cache() -> None:
    """Drop the parsed registry (tests and config reloads)."""
    global _cache
    _cache = None


def enabled_custom_endpoints() -> list[CustomEndpoint]:
    return [ep for ep in get_custom_endpoints() if ep.enabled]


def custom_endpoint_by_provider(provider_name: str) -> CustomEndpoint | None:
    """The ENABLED endpoint behind a ``custom-<name>`` provider name."""
    normalized = (provider_name or "").lower().strip()
    for endpoint in enabled_custom_endpoints():
        if endpoint.provider_name == normalized:
            return endpoint
    return None


def custom_provider_for_model(model_id: str) -> str | None:
    """Provider name that owns a custom model id, or None.

    Only ENABLED endpoints claim models; a disabled endpoint's ids fall
    back to the normal catalogue/substring resolution.
    """
    normalized = (model_id or "").lower().strip()
    if not normalized:
        return None
    for endpoint in enabled_custom_endpoints():
        if normalized in {m.lower() for m in endpoint.model_ids}:
            return endpoint.provider_name
    return None


def custom_catalog_entries() -> list[dict[str, str]]:
    """MODEL_CATALOG-shaped rows for every enabled custom endpoint's models."""
    entries: list[dict[str, str]] = []
    for endpoint in enabled_custom_endpoints():
        for model_id in endpoint.model_ids:
            entries.append(
                {
                    "id": model_id,
                    "owned_by": f"custom:{endpoint.name}",
                    "provider": endpoint.provider_name,
                }
            )
    return entries
