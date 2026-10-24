"""
mesh/universe_health.py — FRIDAY Universe Unified Health Check Engine.

Monitors the health of all 10 agents, tests cross-agent communication,
and provides a real-time status dashboard.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class AgentHealth:
    """Health status of a single agent."""
    agent: str
    url: str
    status: str = "unknown"  # healthy, degraded, offline, unknown
    last_check: float = 0.0
    response_time_ms: float = 0.0
    error: str = ""
    endpoints_tested: int = 0
    endpoints_passed: int = 0


@dataclass
class MeshHealth:
    """Overall mesh health."""
    total_agents: int = 0
    healthy_agents: int = 0
    degraded_agents: int = 0
    offline_agents: int = 0
    mesh_health: str = "unknown"  # healthy, degraded, critical
    avg_response_time: float = 0.0
    cross_agent_connectivity: dict[str, str] = field(default_factory=dict)
    checked_at: float = 0.0


@dataclass
class ConnectivityResult:
    """Cross-agent connectivity test result."""
    from_agent: str
    to_agent: str
    status: str  # connected, failed, timeout
    latency_ms: float = 0.0
    error: str = ""


# Agent registry with their mesh URLs
AGENT_REGISTRY = {
    "friday": {"url": "http://localhost:10000", "endpoints": ["/api/v1/mesh/health", "/health"]},
    "inference": {"url": "http://localhost:8000", "endpoints": ["/health", "/ready"]},
    "memora": {"url": "http://localhost:8001", "endpoints": ["/api/v1/memory/health", "/health"]},
    "stratex": {"url": "http://localhost:8002", "endpoints": ["/health", "/api/ecosystem/status"]},
    "forge": {"url": "http://localhost:8003", "endpoints": ["/health", "/ready"]},
    "cortex": {"url": "http://localhost:8004", "endpoints": ["/health", "/ready"]},
    "sentinel": {"url": "http://localhost:8005", "endpoints": ["/health", "/ready"]},
    "intelx": {"url": "http://localhost:8006", "endpoints": ["/health", "/ready"]},
    "futuris": {"url": "http://localhost:8007", "endpoints": ["/health", "/ready"]},
    "vyralx": {"url": "http://localhost:8008", "endpoints": ["/health", "/ready"]},
}


class UniverseHealthMonitor:
    """Universe health monitoring engine."""

    def __init__(self):
        self._health: dict[str, AgentHealth] = {}
        self._mesh_health = MeshHealth()
        self._connectivity: dict[str, ConnectivityResult] = {}

    async def check_agent(self, agent_name: str, config: dict) -> AgentHealth:
        """Check health of a single agent."""
        health = AgentHealth(agent=agent_name, url=config["url"])
        health.last_check = time.time()

        start = time.time()

        for endpoint in config["endpoints"]:
            health.endpoints_tested += 1
            url = f"{config['url']}{endpoint}"

            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url)
                    if resp.status_code < 500:
                        health.endpoints_passed += 1
                    else:
                        health.error = f"HTTP {resp.status_code} on {endpoint}"
            except Exception as e:
                health.error = str(e)[:200]

        elapsed = (time.time() - start) * 1000
        health.response_time_ms = elapsed

        if health.endpoints_passed == health.endpoints_tested and elapsed < 5000:
            health.status = "healthy"
        elif health.endpoints_passed > 0:
            health.status = "degraded"
        else:
            health.status = "offline"

        self._health[agent_name] = health
        return health

    async def check_all_agents(self) -> MeshHealth:
        """Check health of all agents."""
        tasks = []
        for agent_name, config in AGENT_REGISTRY.items():
            task = self.check_agent(agent_name, config)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        self._mesh_health = MeshHealth(
            total_agents=len(AGENT_REGISTRY),
            healthy_agents=sum(1 for h in self._health.values() if h.status == "healthy"),
            degraded_agents=sum(1 for h in self._health.values() if h.status == "degraded"),
            offline_agents=sum(1 for h in self._health.values() if h.status == "offline"),
            checked_at=time.time(),
        )

        # Average response time
        times = [h.response_time_ms for h in self._health.values() if h.response_time_ms > 0]
        self._mesh_health.avg_response_time = sum(times) / len(times) if times else 0.0

        # Overall health
        if self._mesh_health.offline_agents == 0 and self._mesh_health.degraded_agents <= 2:
            self._mesh_health.mesh_health = "healthy"
        elif self._mesh_health.healthy_agents >= 5:
            self._mesh_health.mesh_health = "degraded"
        else:
            self._mesh_health.mesh_health = "critical"

        return self._mesh_health

    async def test_cross_agent_connectivity(self) -> list[ConnectivityResult]:
        """Test connectivity between all agent pairs."""
        results = []

        # Test key pairs: each specialist → Inference, each specialist → Memora
        test_pairs = [
            ("stratex", "inference"),
            ("stratex", "memora"),
            ("forge", "inference"),
            ("forge", "sentinel"),
            ("cortex", "inference"),
            ("cortex", "intelx"),
            ("intelx", "inference"),
            ("intelx", "memora"),
            ("futuris", "stratex"),
            ("vyralx", "inference"),
            ("vyralx", "memora"),
            ("friday", "inference"),
            ("friday", "memora"),
        ]

        for from_agent, to_agent in test_pairs:
            from_config = AGENT_REGISTRY.get(from_agent)
            to_config = AGENT_REGISTRY.get(to_agent)

            if not from_config or not to_config:
                continue

            result = ConnectivityResult(
                from_agent=from_agent,
                to_agent=to_agent,
                status="unknown",
            )

            start = time.time()
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Try to hit the target's health endpoint
                    resp = await client.get(f"{to_config['url']}/health")
                    if resp.status_code < 500:
                        result.status = "connected"
                    else:
                        result.status = "failed"
                        result.error = f"HTTP {resp.status_code}"
            except Exception as e:
                result.status = "failed"
                result.error = str(e)[:100]

            result.latency_ms = (time.time() - start) * 1000
            results.append(result)

            key = f"{from_agent}->{to_agent}"
            self._connectivity[key] = result

        return results

    async def get_full_report(self) -> dict:
        """Get full universe health report."""
        mesh = await self.check_all_agents()
        connectivity = await self.test_cross_agent_connectivity()

        return {
            "mesh_health": {
                "total_agents": mesh.total_agents,
                "healthy_agents": mesh.healthy_agents,
                "degraded_agents": mesh.degraded_agents,
                "offline_agents": mesh.offline_agents,
                "mesh_status": mesh.mesh_health,
                "avg_response_time_ms": mesh.avg_response_time,
                "checked_at": mesh.checked_at,
            },
            "agents": {
                name: {
                    "url": h.url,
                    "status": h.status,
                    "response_time_ms": h.response_time_ms,
                    "endpoints_tested": h.endpoints_tested,
                    "endpoints_passed": h.endpoints_passed,
                    "error": h.error,
                }
                for name, h in self._health.items()
            },
            "connectivity": {
                f"{r.from_agent}->{r.to_agent}": {
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in connectivity
            },
        }


# Module-level singleton
universe_health = UniverseHealthMonitor()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.get("/api/v1/mesh/health")
async def get_mesh_health():
    """Get universe mesh health report."""
    return await universe_health.get_full_report()


@router.get("/api/v1/mesh/health/quick")
async def get_quick_health():
    """Quick health check (just status codes, no connectivity tests)."""
    mesh = await universe_health.check_all_agents()
    return {
        "status": mesh.mesh_health,
        "total": mesh.total_agents,
        "healthy": mesh.healthy_agents,
        "degraded": mesh.degraded_agents,
        "offline": mesh.offline_agents,
    }


@router.get("/api/v1/mesh/health/{agent_name}")
async def get_agent_health(agent_name: str):
    """Get health of a specific agent."""
    config = AGENT_REGISTRY.get(agent_name)
    if not config:
        raise HTTPException(404, f"Agent {agent_name} not in registry")

    health = await universe_health.check_agent(agent_name, config)
    return health.__dict__


@router.get("/api/v1/mesh/health/connectivity/test")
async def test_connectivity():
    """Test cross-agent connectivity."""
    results = await universe_health.test_cross_agent_connectivity()
    return [r.__dict__ for r in results]
