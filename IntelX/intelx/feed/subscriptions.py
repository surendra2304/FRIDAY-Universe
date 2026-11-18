"""Per-agent domain subscriptions for the Universe intel feed — TASK-INT-014.

The feed itself is broadcast (one publish, recipient ``"all"``); a
*subscription* is the consumer-side filter that decides which domains an
agent keeps. Filtering at the consumer keeps the channel simple and lets
each agent narrow or widen its intake without IntelX republishing.

``None`` means "every domain" — the right default for the agents whose job
is breadth (FRIDAY briefs the owner on anything that matters; Futuris
forecasts everything; Cortex coordinates; Memora remembers). Narrow sets
are declared for the specialists. A notice with no domain is classified
``"general"`` for filtering, so a legacy un-domained notice reaches only
agents subscribed to everything or to ``general`` — it never silently
counts as a match for a specialist domain.

Operators can override any agent without a code change:
``INTELX_FEED_SUB_<AGENT>=domain1,domain2`` (or ``all``).
"""

from __future__ import annotations

import os

ALL_DOMAINS = None  # sentinel: subscribed to every domain

DEFAULT_SUBSCRIPTIONS: dict[str, frozenset[str] | None] = {
    # Named first consumers (owner decision 2026-11-18).
    "futuris": ALL_DOMAINS,  # forecasts everything; breadth is the job
    "stratex": frozenset({"markets", "india_regulatory", "world_events"}),
    # The rest of the Universe.
    "friday": ALL_DOMAINS,  # she decides what matters to the owner
    "cortex": ALL_DOMAINS,  # coordination needs the whole picture
    "memora": ALL_DOMAINS,  # memory is potentially anything
    "sentinel": frozenset({"world_events", "tools_infra"}),
    "forge": frozenset({"tools_infra", "ai_models"}),
    "inference": frozenset({"ai_models", "tools_infra"}),
    "vyralx": frozenset({"platforms_policy", "world_events"}),
    # intelx is the publisher; she does not consume her own feed this way.
}

_ENV_PREFIX = "INTELX_FEED_SUB_"


def domains_for(agent: str, *, env: dict[str, str] | None = None) -> frozenset[str] | None:
    """The domains ``agent`` keeps; None = every domain.

    Unknown agents default to every domain: a new agent should see the
    feed and narrow deliberately, not start blind.
    """
    environ = os.environ if env is None else env
    override = environ.get(f"{_ENV_PREFIX}{agent.upper()}")
    if override is not None:
        override = override.strip()
        if override.lower() in {"all", "*"}:
            return None
        return frozenset(d.strip() for d in override.split(",") if d.strip())
    return DEFAULT_SUBSCRIPTIONS.get(agent.lower(), ALL_DOMAINS)


def accepts(agent: str, domain: str | None, *, env: dict[str, str] | None = None) -> bool:
    """True when ``agent``'s subscription keeps a notice in ``domain``."""
    subscribed = domains_for(agent, env=env)
    if subscribed is None:
        return True
    return (domain or "general") in subscribed
