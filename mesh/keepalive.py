"""Keep-alive monitoring and health state tracking for all 9 ecosystem agents."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from mesh.envelope import AgentEnvelope, build_envelope


class ServiceHealth(str, Enum):
    ONLINE = "ONLINE"
    REACHABLE = "REACHABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STANDBY = "STANDBY"


class CircuitBreaker:
    """Circuit breaker pattern tracking failure threshold and auto-recovery states."""

    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_state_change = time.time()

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_state_change = time.time()

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_state_change >= self.recovery_time_sec:
                self.state = "HALF_OPEN"
                self.last_state_change = time.time()
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False


@dataclass
class ServiceStatus:
    name: str
    url: str
    health_path: str = "/health"
    last_probe: float = 0.0
    latency_ms: int = 0
    status: ServiceHealth = ServiceHealth.UNAVAILABLE
    failures: int = 0
    successes: int = 0
    last_error: Optional[str] = None
    latency_history: deque[int] = field(default_factory=lambda: deque(maxlen=20))
    metadata: dict[str, Any] = field(default_factory=dict)
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def record_probe(self, status: ServiceHealth, latency_ms: int, error: Optional[str] = None) -> None:
        self.last_probe = time.time()
        self.latency_ms = max(0, latency_ms)
        self.status = status
        self.latency_history.append(self.latency_ms)

        if status in (ServiceHealth.ONLINE, ServiceHealth.REACHABLE):
            self.successes += 1
            self.failures = 0
            self.last_error = None
            self.circuit_breaker.record_success()
        else:
            self.failures += 1
            if error:
                self.last_error = error
            self.circuit_breaker.record_failure()

    @property
    def average_latency(self) -> float:
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "health_path": self.health_path,
            "last_probe": self.last_probe,
            "latency_ms": self.latency_ms,
            "avg_latency_ms": round(self.average_latency, 2),
            "status": self.status.value,
            "failures": self.failures,
            "successes": self.successes,
            "last_error": self.last_error,
        }


class KeepAliveMonitor:
    """Manages health tracking across all registered mesh services."""

    def __init__(self, poll_interval_sec: float = 25.0):
        self.poll_interval = poll_interval_sec
        self.services: dict[str, ServiceStatus] = {}

    def register(self, name: str, url: str, health_path: str = "/health", metadata: Optional[dict[str, Any]] = None) -> None:
        key = name.lower().strip()
        self.services[key] = ServiceStatus(
            name=name.upper(),
            url=url.rstrip("/"),
            health_path="/" + health_path.lstrip("/"),
            metadata=metadata or {},
        )

    def get_service(self, name: str) -> Optional[ServiceStatus]:
        return self.services.get(name.lower().strip())

    def build_probe_envelope(self, service_name: str) -> AgentEnvelope:
        svc = self.get_service(service_name)
        path = svc.health_path if svc else "/health"
        return build_envelope(
            from_agent="KEEPALIVE_PROBE",
            to_agent=service_name.upper(),
            intent="health_probe",
            payload={"service": service_name.upper(), "health_path": path, "timestamp": time.time()},
            priority="high",
        )

    def get_summary(self) -> dict[str, Any]:
        total = len(self.services)
        online = sum(1 for s in self.services.values() if s.status == ServiceHealth.ONLINE)
        reachable = sum(1 for s in self.services.values() if s.status == ServiceHealth.REACHABLE)
        degraded = sum(1 for s in self.services.values() if s.status == ServiceHealth.DEGRADED)
        unavailable = sum(1 for s in self.services.values() if s.status == ServiceHealth.UNAVAILABLE)

        return {
            "total": total,
            "online": online,
            "reachable": reachable,
            "degraded": degraded,
            "unavailable": unavailable,
            "poll_interval_sec": self.poll_interval,
            "services": {k: s.to_dict() for k, s in self.services.items()},
        }
