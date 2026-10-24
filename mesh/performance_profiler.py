"""
mesh/performance_profiler.py — FRIDAY Universe Performance Profiling Engine.

Profiles each agent for performance: response times, throughput, resource
usage, bottleneck identification, and optimization recommendations.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class PerformanceMetrics:
    """Performance metrics for an agent."""
    agent: str
    avg_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    requests_per_minute: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_io: float = 0.0
    network_io: float = 0.0
    score: float = 0.0  # 0-100 performance score
    bottlenecks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class CallTrace:
    """A single call trace."""
    trace_id: str
    from_agent: str
    to_agent: str
    endpoint: str
    latency_ms: float
    status: str  # success, error, timeout
    timestamp: float
    payload_size: int = 0


@dataclass
class Bottleneck:
    """A detected bottleneck."""
    agent: str
    type: str  # latency, throughput, resource, memory, cpu
    severity: str  # critical, high, medium, low
    description: str
    impact: float
    recommendation: str


@dataclass
class OptimizationRecommendation:
    """An optimization recommendation."""
    agent: str
    category: str  # caching, batching, async, resource, config
    description: str
    expected_improvement: str
    effort: str  # low, medium, high
    priority: int = 1


@dataclass
class PerformanceReport:
    """Overall performance report."""
    total_agents: int
    avg_performance_score: float
    slowest_agent: str
    fastest_agent: str
    total_bottlenecks: int
    total_recommendations: int
    generated_at: float


class PerformanceProfiler:
    """Performance profiling engine."""

    def __init__(self):
        self._metrics: dict[str, PerformanceMetrics] = {}
        self._traces: list[CallTrace] = []
        self._bottlenecks: list[Bottleneck] = []
        self._recommendations: list[OptimizationRecommendation] = []

    def record_trace(
        self,
        from_agent: str,
        to_agent: str,
        endpoint: str,
        latency_ms: float,
        status: str = "success",
        payload_size: int = 0,
    ) -> CallTrace:
        """Record a call trace."""
        trace = CallTrace(
            trace_id=hashlib.md5(
                f"trace:{from_agent}:{to_agent}:{endpoint}:{time.time()}".encode()
            ).hexdigest()[:12],
            from_agent=from_agent,
            to_agent=to_agent,
            endpoint=endpoint,
            latency_ms=latency_ms,
            status=status,
            timestamp=time.time(),
            payload_size=payload_size,
        )

        self._traces.append(trace)

        # Update metrics
        if to_agent not in self._metrics:
            self._metrics[to_agent] = PerformanceMetrics(agent=to_agent)

        metrics = self._metrics[to_agent]
        n = len([t for t in self._traces if t.to_agent == to_agent])
        metrics.avg_response_time_ms = metrics.avg_response_time_ms * (n - 1) / n + latency_ms / n

        # Calculate percentiles
        agent_traces = sorted(
            [t for t in self._traces if t.to_agent == to_agent],
            key=lambda t: t.latency_ms
        )
        if agent_traces:
            metrics.p50_response_time_ms = agent_traces[len(agent_traces) // 2].latency_ms
            metrics.p95_response_time_ms = agent_traces[int(len(agent_traces) * 0.95)].latency_ms
            metrics.p99_response_time_ms = agent_traces[int(len(agent_traces) * 0.99)].latency_ms

        # Throughput (requests per minute)
        recent = [t for t in self._traces if t.timestamp > time.time() - 60]
        metrics.requests_per_minute = len(recent)

        # Error rate
        errors = sum(1 for t in self._traces if t.to_agent == to_agent and t.status == "error")
        total = len([t for t in self._traces if t.to_agent == to_agent])
        metrics.error_rate = errors / max(1, total)

        return trace

    def profile_agent(self, agent_name: str) -> PerformanceMetrics:
        """Profile a specific agent."""
        metrics = self._metrics.get(agent_name)
        if not metrics:
            metrics = PerformanceMetrics(agent=agent_name)
            self._metrics[agent_name] = metrics

        # Simulate resource usage
        metrics.cpu_usage = 10.0 + (ord(hashlib.md5(f"cpu_{agent_name}".encode()).hexdigest()[:1]) % 40)
        metrics.memory_usage = 30.0 + (ord(hashlib.md5(f"mem_{agent_name}".encode()).hexdigest()[:1]) % 50)
        metrics.disk_io = 5.0 + (ord(hashlib.md5(f"disk_{agent_name}".encode()).hexdigest()[:1]) % 20)
        metrics.network_io = 10.0 + (ord(hashlib.md5(f"net_{agent_name}".encode()).hexdigest()[:1]) % 30)

        # Calculate performance score
        score = 100.0

        # Latency penalty
        if metrics.p95_response_time_ms > 500:
            score -= 20
        elif metrics.p95_response_time_ms > 200:
            score -= 10
        elif metrics.p95_response_time_ms > 100:
            score -= 5

        # Error rate penalty
        score -= metrics.error_rate * 50

        # Resource penalty
        if metrics.cpu_usage > 70:
            score -= 10
        if metrics.memory_usage > 80:
            score -= 10

        metrics.score = max(0, min(100, score))

        # Detect bottlenecks
        self._detect_bottlenecks(metrics)

        # Generate recommendations
        self._generate_recommendations(metrics)

        return metrics

    def _detect_bottlenecks(self, metrics: PerformanceMetrics) -> None:
        """Detect bottlenecks for an agent."""
        agent = metrics.agent

        if metrics.p95_response_time_ms > 500:
            self._bottlenecks.append(Bottleneck(
                agent=agent,
                type="latency",
                severity="high" if metrics.p95_response_time_ms > 1000 else "medium",
                description=f"High p95 latency: {metrics.p95_response_time_ms:.0f}ms",
                impact=metrics.p95_response_time_ms / 100,
                recommendation="Optimize slow endpoints, add caching, or increase timeout limits",
            ))

        if metrics.error_rate > 0.1:
            self._bottlenecks.append(Bottleneck(
                agent=agent,
                type="throughput",
                severity="high" if metrics.error_rate > 0.2 else "medium",
                description=f"High error rate: {metrics.error_rate:.0%}",
                impact=metrics.error_rate * 5,
                recommendation="Investigate error sources, add retry logic, fix exceptions",
            ))

        if metrics.cpu_usage > 70:
            self._bottlenecks.append(Bottleneck(
                agent=agent,
                type="cpu",
                severity="high" if metrics.cpu_usage > 90 else "medium",
                description=f"High CPU usage: {metrics.cpu_usage:.0f}%",
                impact=metrics.cpu_usage / 10,
                recommendation="Optimize CPU-heavy operations, add async processing, increase CPU limits",
            ))

        if metrics.memory_usage > 80:
            self._bottlenecks.append(Bottleneck(
                agent=agent,
                type="memory",
                severity="high" if metrics.memory_usage > 90 else "medium",
                description=f"High memory usage: {metrics.memory_usage:.0f}%",
                impact=metrics.memory_usage / 10,
                recommendation="Reduce memory footprint, clear caches, increase memory limits",
            ))

    def _generate_recommendations(self, metrics: PerformanceMetrics) -> None:
        """Generate optimization recommendations."""
        agent = metrics.agent

        if metrics.p95_response_time_ms > 200:
            self._recommendations.append(OptimizationRecommendation(
                agent=agent,
                category="caching",
                description="Add response caching for frequently-called endpoints",
                expected_improvement="50-80% latency reduction",
                effort="low",
                priority=1,
            ))

        if metrics.error_rate > 0.05:
            self._recommendations.append(OptimizationRecommendation(
                agent=agent,
                category="async",
                description="Convert blocking operations to async, add retry logic",
                expected_improvement="50% error reduction",
                effort="medium",
                priority=2,
            ))

        if metrics.cpu_usage > 60:
            self._recommendations.append(OptimizationRecommendation(
                agent=agent,
                category="resource",
                description="Offload heavy computation to worker pool",
                expected_improvement="30% CPU reduction",
                effort="medium",
                priority=3,
            ))

        if metrics.memory_usage > 70:
            self._recommendations.append(OptimizationRecommendation(
                agent=agent,
                category="config",
                description="Implement memory limits and garbage collection tuning",
                expected_improvement="20% memory reduction",
                effort="low",
                priority=4,
            ))

    def profile_all(self) -> dict:
        """Profile all agents."""
        agents = [
            "friday", "inference", "memora", "stratex", "forge",
            "cortex", "sentinel", "intelx", "futuris", "vyralx"
        ]

        for agent in agents:
            self.profile_agent(agent)

        return self._generate_report()

    def _generate_report(self) -> dict:
        """Generate performance report."""
        scores = [m.score for m in self._metrics.values()]
        slowest = max(self._metrics.items(), key=lambda x: x[1].p95_response_time_ms) if self._metrics else ("none", PerformanceMetrics(agent="none"))
        fastest = min(self._metrics.items(), key=lambda x: x[1].avg_response_time_ms) if self._metrics else ("none", PerformanceMetrics(agent="none"))

        report = PerformanceReport(
            total_agents=len(self._metrics),
            avg_performance_score=sum(scores) / max(1, len(scores)),
            slowest_agent=slowest[0] if slowest[1].p95_response_time_ms > 0 else "none",
            fastest_agent=fastest[0] if fastest[1].avg_response_time_ms > 0 else "none",
            total_bottlenecks=len(self._bottlenecks),
            total_recommendations=len(self._recommendations),
            generated_at=time.time(),
        )

        return {
            "report": {
                "total_agents": report.total_agents,
                "avg_performance_score": report.avg_performance_score,
                "slowest_agent": report.slowest_agent,
                "fastest_agent": report.fastest_agent,
                "total_bottlenecks": report.total_bottlenecks,
                "total_recommendations": report.total_recommendations,
            },
            "agents": {
                name: {
                    "score": m.score,
                    "avg_latency_ms": m.avg_response_time_ms,
                    "p50_ms": m.p50_response_time_ms,
                    "p95_ms": m.p95_response_time_ms,
                    "p99_ms": m.p99_response_time_ms,
                    "rps": m.requests_per_minute,
                    "error_rate": m.error_rate,
                    "cpu": m.cpu_usage,
                    "memory": m.memory_usage,
                }
                for name, m in self._metrics.items()
            },
            "bottlenecks": [b.__dict__ for b in self._bottlenecks[:20]],
            "recommendations": [r.__dict__ for r in self._recommendations[:20]],
        }


# Module-level singleton
performance_profiler = PerformanceProfiler()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/mesh/perf/trace")
async def record_trace(payload: dict):
    """Record a call trace."""
    trace = performance_profiler.record_trace(
        from_agent=payload["from_agent"],
        to_agent=payload["to_agent"],
        endpoint=payload["endpoint"],
        latency_ms=payload["latency_ms"],
        status=payload.get("status", "success"),
        payload_size=payload.get("payload_size", 0),
    )
    return trace.__dict__


@router.get("/api/v1/mesh/perf/profile/{agent}")
async def profile_agent(agent: str):
    """Profile a specific agent."""
    metrics = performance_profiler.profile_agent(agent)
    return metrics.__dict__


@router.get("/api/v1/mesh/perf/profile/all")
async def profile_all():
    """Profile all agents."""
    return performance_profiler.profile_all()


@router.get("/api/v1/mesh/perf/bottlenecks")
async def get_bottlenecks():
    """Get detected bottlenecks."""
    return [b.__dict__ for b in performance_profiler._bottlenecks[:50]]


@router.get("/api/v1/mesh/perf/recommendations")
async def get_recommendations():
    """Get optimization recommendations."""
    return [r.__dict__ for r in performance_profiler._recommendations[:50]]
