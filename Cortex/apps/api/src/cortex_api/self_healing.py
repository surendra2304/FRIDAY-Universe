"""Wires CORTEX subsystems into the health registry and the self-healing supervisor.

Registered subsystems and their *real* repairs (all local, idempotent, and verified by a
post-repair probe):

* ``database``   — probe ``SELECT 1``; repair disposes the connection pool so stale
  connections are dropped (the classic "hanging pool" failure).
* ``schema``     — probe the table manifest; repair runs the idempotent create-all.
* ``redis``      — probe ``PING``; repair resets the client's connection pool.
* ``ai_universe`` — probe ``GET {base}/health`` on the Inference gateway
  (explicit env URL, else the fleet default: Inference on Server 1,
  port 8001); repair re-installs the deterministic fallback policy so
  deliberations keep working while the provider is down (graceful
  degradation, not a fake success).
* ``agents``     — probe that the registry has every expected specialist; repair re-registers
  the built-in agents.

The supervisor escalates anything it cannot verify, and every cycle is observable through
``GET /v1/friday/self_healing``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from cortex_core.resilience import EscalationNotifier, ProbeResult, SelfHealingSupervisor, global_health_registry
from cortex_core.self_model import SelfModel, SelfModificationEngine

logger = logging.getLogger("cortex-api.self-healing")

EXPECTED_AGENT_IDS = (
    "agent_growth",
    "agent_sales",
    "agent_support",
    "agent_reliability",
    "agent_qualification",
    "agent_churn_risk",
    "agent_competitive",
)

# Fleet default for the Inference gateway (TASK-CTX-002): Inference answers
# on port 8001 on Server 1 (10.0.0.121) — the verified production layout
# (AGENTS.md "Verified Production Deployment"). Cortex runs on Server 2 and
# reaches Server 1 over the private network, so the probe checks Inference
# itself, not the public Caddy/DuckDNS ingress — a failure there would
# misreport a healthy Inference as down. An explicit env URL always wins.
FLEET_INFERENCE_BASE_URL = "http://10.0.0.121:8001"

# The loop ticks every 30s; a probe that hangs must never wedge it. Matches
# the timeouts of the sibling HTTP clients (adapter, notifier: 5.0s).
PROBE_TIMEOUT_SECONDS = 5.0


async def probe_ai_universe() -> ProbeResult:
    """Real HTTP health check for the Inference gateway (TASK-CTX-002).

    The old probe only resolved the configured host's DNS — and with
    ``INFERENCE_BASE_URL`` / ``AI_UNIVERSE_BASE_URL`` both unset in
    production it observed nothing at all (UNCONFIGURED every cycle:
    suppressed noise, not health). It now performs ``GET {base}/health``
    and reports HEALTHY only on HTTP 200 from a gateway that says it is
    healthy, so a down or degraded Inference is observed truthfully and
    the supervisor's repair/escalation path means something.

    Base URL precedence: ``INFERENCE_BASE_URL`` > ``AI_UNIVERSE_BASE_URL``
    (legacy migration fallback) > the fleet default above. Tri-state
    (TASK-COR-014) is kept: a set-but-unparseable URL (no host) is
    UNCONFIGURED — there is nothing to probe; anything else that cannot
    be verified healthy is UNHEALTHY, never a silent pass.
    """
    import urllib.parse

    import httpx

    url = (
        os.getenv("INFERENCE_BASE_URL", "")
        or os.getenv("AI_UNIVERSE_BASE_URL", "")  # legacy migration fallback
        or FLEET_INFERENCE_BASE_URL
    ).rstrip("/")
    host = urllib.parse.urlparse(url).hostname
    if not host:
        return ProbeResult.UNCONFIGURED
    try:
        # trust_env=False, mirroring EscalationNotifier: the probe target is
        # a configured/fleet endpoint — ambient HTTP(S)_PROXY variables must
        # not intercept or break it.
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.get(f"{url}/health")
    except Exception:
        # Any transport failure (DNS, connect, timeout) means the gateway
        # cannot be verified healthy. The registry treats a raising probe
        # the same way; returning UNHEALTHY here keeps it explicit.
        return ProbeResult.UNHEALTHY
    if response.status_code != 200:
        return ProbeResult.UNHEALTHY
    try:
        body = response.json()
    except ValueError:
        # 200 with a non-JSON body: the process answers; liveness only.
        return ProbeResult.HEALTHY
    if isinstance(body, dict) and "status" in body:
        return ProbeResult.HEALTHY if body["status"] == "healthy" else ProbeResult.UNHEALTHY
    return ProbeResult.HEALTHY


def build_supervisor(registry: Any, max_collaboration_rounds: int = 3) -> SelfHealingSupervisor:
    """Register probes + repairs for every subsystem CORTEX can heal itself."""
    health = global_health_registry
    # Escalations go to an operator channel when one is configured; otherwise the supervisor
    # records that it could not notify anyone instead of pretending it did.
    notifier = EscalationNotifier(webhook_url=os.getenv("SELF_HEALING_ESCALATION_WEBHOOK", ""))
    if notifier.webhook_url is None:
        logger.info("self-healing: no SELF_HEALING_ESCALATION_WEBHOOK configured; escalations stay in-process")
    supervisor = SelfHealingSupervisor(health, notifier=notifier)

    # ── database ────────────────────────────────────────────────────────────
    async def probe_database() -> bool:
        from sqlalchemy import text

        from cortex_api.config import engine

        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def repair_database() -> bool:
        from cortex_api.config import engine

        logger.warning("self-healing: disposing the database connection pool")
        await engine.dispose()
        return True

    # ── schema ──────────────────────────────────────────────────────────────
    async def probe_schema() -> bool:
        from cortex_api.config import engine
        from cortex_api.schema import missing_tables

        return not await missing_tables(engine)

    async def repair_schema() -> bool:
        from cortex_api.config import engine
        from cortex_api.schema import ensure_schema

        await ensure_schema(engine, allow_create=True)
        return True

    # ── redis ───────────────────────────────────────────────────────────────
    async def probe_redis() -> bool:
        from cortex_api.config import redis_pool

        return bool(await redis_pool.ping())

    async def repair_redis() -> bool:
        from cortex_api.config import redis_pool

        logger.warning("self-healing: resetting the Redis connection pool")
        if hasattr(redis_pool, "connection_pool") and hasattr(redis_pool.connection_pool, "disconnect"):
            await redis_pool.connection_pool.disconnect()
        await redis_pool.ping()
        return True

    # ── ai universe (external, degrade gracefully) ──────────────────────────
    async def repair_ai_universe() -> bool:
        """Degrade gracefully: the deterministic fallback keeps deliberations working.

        Verification note (TASK-COR-014, updated TASK-CTX-002): the probe
        reports UNCONFIGURED only for an unparseable URL now — with no env
        URL set it probes the fleet-default Inference gateway instead — so
        this repair runs for a genuinely unreachable provider, never for an
        absent configuration. It still never claims success: the fallback is
        graceful degradation, not a repaired provider.
        """
        from cortex_api.friday_router import _get_orchestrator

        logger.warning("self-healing: ensuring the AI Universe client runs in deterministic fallback")
        orchestrator = _get_orchestrator()
        client = getattr(orchestrator, "ai_client", None)
        if client is None:
            return False
        client.endpoint = ""
        return False

    # ── agents ──────────────────────────────────────────────────────────────
    async def probe_agents() -> bool:
        present = {agent.agent_id for agent in registry._agents.values()}
        return all(agent_id in present for agent_id in EXPECTED_AGENT_IDS)

    async def repair_agents() -> bool:
        from cortex_agents import AgentRegistry

        fresh = AgentRegistry()
        for agent in fresh._agents.values():
            registry.register(agent)
        return True

    health.register_probe("database", probe_database)
    health.register_probe("schema", probe_schema)
    health.register_probe("redis", probe_redis)
    health.register_probe("ai_universe", probe_ai_universe)
    health.register_probe("agents", probe_agents)

    supervisor.register_repair("database", repair_database)
    supervisor.register_repair("schema", repair_schema)
    supervisor.register_repair("redis", repair_redis)
    supervisor.register_repair("ai_universe", repair_ai_universe)
    supervisor.register_repair("agents", repair_agents)

    # The health registry also tracks the subsystems the collaboration layer reports into.
    health.circuit("ingestion")
    health.circuit("tools")

    return supervisor


def build_self_model(registry: Any, supervisor: SelfHealingSupervisor, knobs: Any) -> SelfModel:
    engine = SelfModificationEngine(knobs)
    return SelfModel(
        registry=registry,
        health=global_health_registry,
        supervisor=supervisor,
        engine=engine,
    )


def build_settings_provider(knobs: Any) -> Any:
    """Return a callable giving (enabled, interval) for the background self-healing loop."""

    def _provider() -> tuple[bool, float]:
        return (
            bool(knobs.get("self_healing_enabled", True)),
            float(knobs.get("self_healing_interval_seconds", 30)),
        )

    return _provider
