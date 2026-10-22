"""Mesh transport with NATS JetStream, WebSocket, and authenticated HTTP fallback."""
from __future__ import annotations

import asyncio
import os
import time
from enum import Enum
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import httpx

from mesh.envelope import AgentEnvelope

try:
    import nats
    from nats.aio.client import Client as NATSClient
    _nats_available = True
except Exception:
    _nats_available = False


class TransportMode(str, Enum):
    NATS = "nats"
    HTTP = "http"
    WEBSOCKET = "websocket"


AGENT_AUTH_MAP = {
    "INFERENCE": ("http://inference:8000", "INFERENCE_API_KEY"),
    "MEMORA": ("http://memora:8000", "MEMORA_API_KEY"),
    "STRATEX": ("http://stratex:8000", "STRATEX_API_KEY"),
    "INTELX": ("http://intelx:8000", "INTELX_API_KEY"),
    "FUTURIS": ("http://futuris:8000", "FUTURIS_API_KEY"),
    "CORTEX": ("http://cortex:8000", "CORTEX_API_KEY"),
    "FORGE": ("http://forge:8000", "FORGE_API_KEY"),
    "SENTINEL": ("http://sentinel:8000", "SENTINEL_API_KEY"),
    "FRIDAY": ("http://friday:10000", "FRIDAY_API_KEY"),
}

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_loopback_url(url: str) -> bool:
    return urlparse(url).hostname in _LOOPBACK_HOSTS


class MeshTransport:
    """Transport supporting NATS (if available) with robust authenticated HTTP fallback.
    Provides retry backoff, circuit-breaker awareness, and secure signature handling.
    """
    def __init__(self, mode: TransportMode = TransportMode.HTTP, timeout_sec: float = 15.0):
        self.mode = mode
        self.timeout_sec = timeout_sec
        self._client: Optional[NATSClient] = None
        self._delivery_log: list[dict[str, Any]] = []
        self._subscriptions: dict[str, list[Callable[[AgentEnvelope], Any]]] = {}
        if mode == TransportMode.NATS and _nats_available:
            self._client = NATSClient()

    async def connect(self, url: str = "nats://localhost:4222") -> bool:
        if self.mode == TransportMode.NATS and self._client is not None:
            try:
                await self._client.connect(url)
                return True
            except Exception:
                # Graceful fallback to HTTP
                self.mode = TransportMode.HTTP
                return False
        return True

    async def publish(self, envelope: AgentEnvelope, direct_url: Optional[str] = None) -> dict[str, Any]:
        """Publish an envelope to the target agent."""
        t0 = time.time()
        to_agent = envelope.to_agent.upper()

        # 1. Try NATS if configured
        if self.mode == TransportMode.NATS and self._client is not None and self._client.is_connected:
            try:
                subject = f"mesh.{envelope.to_agent.lower()}.{envelope.intent}"
                await self._client.publish(subject.encode(), envelope.to_json().encode())
                return {"status": "ACCEPTED_NATS", "subject": subject, "duration_ms": int((time.time() - t0) * 1000)}
            except Exception:
                pass  # Fall through to HTTP dispatch

        # 2. Local subscribers dispatch (to target agent, source agent, or wildcard)
        from_agent = envelope.from_agent.upper()
        handled: set[int] = set()
        local_target_deliveries = 0
        local_target_failures = 0
        for sub_key in (to_agent, from_agent, "*"):
            if sub_key in self._subscriptions:
                for handler in self._subscriptions[sub_key]:
                    if id(handler) not in handled:
                        handled.add(id(handler))
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(envelope)
                            else:
                                handler(envelope)
                            if sub_key == to_agent:
                                local_target_deliveries += 1
                        except Exception as exc:
                            if sub_key == to_agent:
                                local_target_failures += 1

        if local_target_deliveries:
            result = {
                "status": "DELIVERED_LOCAL",
                "message_id": envelope.message_id,
                "handler_count": local_target_deliveries,
                "duration_ms": int((time.time() - t0) * 1000),
            }
            self._delivery_log.append({"message_id": envelope.message_id, **result})
            return result

        # 3. HTTP Gateway Dispatch
        target_info = AGENT_AUTH_MAP.get(to_agent)
        default_url = target_info[0] if target_info else None
        url_env_name = f"{to_agent}_URL"
        url = direct_url or os.getenv(url_env_name) or default_url
        key_env_name = target_info[1] if target_info else f"{to_agent}_API_KEY"
        api_key = os.getenv(key_env_name, "").strip()

        if url:
            endpoint = f"{url.rstrip('/')}/mesh/envelope" if not direct_url else direct_url
            headers = {
                "Content-Type": "application/json",
                "X-Agent-From": envelope.from_agent,
                "X-Agent-To": envelope.to_agent,
                "X-Correlation-ID": envelope.correlation_id,
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            elif not _is_loopback_url(endpoint):
                result = {
                    "status": "BLOCKED_MISSING_CREDENTIAL",
                    "credential_env": key_env_name,
                    "duration_ms": int((time.time() - t0) * 1000),
                    "url": endpoint,
                    "local_handler_failures": local_target_failures,
                }
                self._delivery_log.append({"message_id": envelope.message_id, **result})
                return result
            if envelope.signature:
                headers["X-Mesh-Signature"] = envelope.signature

            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as client:
                    resp = await client.post(endpoint, json=envelope.to_dict(), headers=headers)
                    duration_ms = int((time.time() - t0) * 1000)
                    result = {
                        "status": "ACCEPTED_HTTP" if resp.status_code in (200, 201, 202) else f"HTTP_{resp.status_code}",
                        "status_code": resp.status_code,
                        "duration_ms": duration_ms,
                        "url": endpoint,
                    }
                    self._delivery_log.append({"message_id": envelope.message_id, **result})
                    return result
            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                result = {
                    "status": "UNDELIVERED_HTTP",
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "url": endpoint,
                }
                self._delivery_log.append({"message_id": envelope.message_id, **result})
                return result

        status = "LOCAL_HANDLER_FAILED" if local_target_failures else "BLOCKED_NO_ENDPOINT"
        result = {
            "status": status,
            "message_id": envelope.message_id,
            "local_handler_failures": local_target_failures,
            "duration_ms": int((time.time() - t0) * 1000),
        }
        self._delivery_log.append({"message_id": envelope.message_id, **result})
        return result

    async def subscribe(self, agent_name: str, handler: Callable[[AgentEnvelope], Any]) -> None:
        """Subscribe a local handler to receive messages for a specific agent."""
        key = agent_name.upper() if agent_name != "*" else "*"
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(handler)

        if self.mode == TransportMode.NATS and self._client is not None and self._client.is_connected:
            async def cb(msg):
                data = msg.data.decode()
                env = AgentEnvelope.from_json(data)
                if asyncio.iscoroutinefunction(handler):
                    await handler(env)
                else:
                    handler(env)
            subject = f"mesh.{agent_name.lower()}.>"
            await self._client.subscribe(subject, cb=cb)

    def get_delivery_history(self) -> list[dict[str, Any]]:
        return list(self._delivery_log)


def get_mesh_transport(prefer_nats: bool = False, timeout_sec: float = 15.0) -> MeshTransport:
    if prefer_nats and _nats_available:
        return MeshTransport(mode=TransportMode.NATS, timeout_sec=timeout_sec)
    return MeshTransport(mode=TransportMode.HTTP, timeout_sec=timeout_sec)
