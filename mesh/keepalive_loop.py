"""Real continuous keep-alive loop — actively probes all 10 cloud agents.
Runs asynchronously with concurrent probes, circuit breakers, and status logging.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional

import httpx

from mesh.keepalive import KeepAliveMonitor, ServiceHealth, ServiceStatus

logger = logging.getLogger("mesh.keepalive_loop")

_HEALTHY_VALUES = {"healthy", "ok", "online", "up", "ready"}
_UNHEALTHY_VALUES = {"unhealthy", "degraded", "down", "error", "unavailable", "critical"}


def _response_health(response: httpx.Response) -> ServiceHealth:
    """Distinguish a healthy payload from an HTTP server that merely answered."""
    if response.status_code in (401, 403):
        return ServiceHealth.REACHABLE
    if response.status_code not in (200, 201, 204):
        return ServiceHealth.DEGRADED
    if response.status_code == 204:
        return ServiceHealth.REACHABLE

    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        body = None
    if isinstance(body, dict):
        for field in ("status", "health", "state"):
            value = body.get(field)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in _HEALTHY_VALUES:
                    return ServiceHealth.ONLINE
                if normalized in _UNHEALTHY_VALUES:
                    return ServiceHealth.DEGRADED
            if value is True:
                return ServiceHealth.ONLINE
            if value is False:
                return ServiceHealth.DEGRADED
    return ServiceHealth.REACHABLE

CLOUD_AGENTS = [
    ("friday", "http://friday:10000", "/health"),
    ("inference", "http://inference:8000", "/health"),
    ("memora", "http://memora:8000", "/health"),
    ("stratex", "http://stratex:8000", "/health"),
    ("intelx", "http://intelx:8000", "/api/v1/healthz"),
    ("futuris", "http://futuris:8000", "/health"),
    ("cortex", "http://cortex:8000", "/health"),
    ("forge", "http://forge:8000", "/health"),
    ("sentinel", "http://sentinel:8000", "/health"),
    ("vyralx", "http://vyralx:8000", "/health"),
]


def configured_cloud_agents(environ: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    """Resolve peer URLs and health routes from runtime config without key defaults."""
    env = os.environ if environ is None else environ
    targets = []
    for name, default_url, default_path in CLOUD_AGENTS:
        prefix = name.upper()
        url = env.get(f"{prefix}_URL") or env.get(f"FRIDAY_{prefix}_URL") or default_url
        path = env.get(f"{prefix}_HEALTH_PATH") or default_path
        targets.append((name, url.rstrip("/"), "/" + path.lstrip("/")))
    return targets


class KeepAliveLoop:
    def __init__(
        self,
        interval_sec: float = 25.0,
        timeout_sec: float = 12.0,
        agents: list[tuple[str, str, str]] | None = None,
    ):
        self.interval = interval_sec
        self.timeout_sec = timeout_sec
        self.agents = list(agents) if agents is not None else configured_cloud_agents()
        self.monitor = KeepAliveMonitor(poll_interval_sec=interval_sec)
        for name, url, path in self.agents:
            self.monitor.register(name, url, path)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.probe_log: list[dict] = []

    async def probe_once(self, client: httpx.AsyncClient, name: str, url: str, path: str) -> dict:
        full_url = url.rstrip("/") + path
        t0 = time.time()
        try:
            r = await client.get(full_url)
            lat = int((time.time() - t0) * 1000)
            status = _response_health(r)
            if r.status_code in (401, 403):
                detail = f"HTTP {r.status_code}; endpoint reachable but health response requires authentication ({lat}ms)"
            else:
                detail = f"HTTP {r.status_code}; {status.value.lower()} ({lat}ms)"
        except httpx.TimeoutException:
            lat = int((time.time() - t0) * 1000)
            status = ServiceHealth.DEGRADED
            detail = f"Timeout after {lat}ms"
        except Exception as e:
            lat = int((time.time() - t0) * 1000)
            status = ServiceHealth.UNAVAILABLE
            detail = f"Connection failed: {e}"

        svc = self.monitor.services.get(name.lower())
        if svc:
            svc.record_probe(
                status=status,
                latency_ms=lat,
                error=detail if status not in (ServiceHealth.ONLINE, ServiceHealth.REACHABLE, ServiceHealth.STANDBY) else None
            )

        entry = {
            "agent": name,
            "url": full_url,
            "status": status.value,
            "latency_ms": lat,
            "detail": detail,
            "ts": time.time(),
        }
        self.probe_log.append(entry)
        if len(self.probe_log) > 200:
            self.probe_log = self.probe_log[-200:]
        return entry

    async def run_cycle(self) -> list[dict]:
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True, limits=limits) as client:
            tasks = [
                self.probe_once(client, name, url, path)
                for name, url, path in self.agents
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            return results

    async def start(self) -> None:
        self._running = True
        logger.info("KeepAlive loop started for %d services at interval %0.1fs", len(self.agents), self.interval)
        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("Error in keep-alive cycle: %s", e)
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
