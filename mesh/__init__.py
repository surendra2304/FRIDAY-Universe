"""FRIDAY Universe Mesh public API.

Exports remain import-compatible while implementation modules load only when
a consumer requests one. In particular, importing a transport or coordination
primitive must not import every subsystem or create the local memory database.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    # Authenticated messages
    "AgentEnvelope": "envelope",
    "EnvelopeError": "envelope",
    "MessagePriority": "envelope",
    "build_envelope": "envelope",
    "validate_envelope": "envelope",
    "verify_envelope": "envelope",
    # Registry and discovery
    "AgentDiscovery": "registry",
    "AgentManifest": "registry",
    "AgentRegistry": "registry",
    "ManifestError": "registry",
    "create_default_registry": "registry",
    # Inter-agent transport
    "AGENT_AUTH_MAP": "transport",
    "MeshTransport": "transport",
    "TransportMode": "transport",
    "get_mesh_transport": "transport",
    # Cognitive guardrails
    "AutoFixZone": "cognitive_brain",
    "CognitiveBrain": "cognitive_brain",
    "CognitiveDecision": "cognitive_brain",
    "CognitiveLayer": "cognitive_brain",
    # Health monitoring
    "CircuitBreaker": "keepalive",
    "KeepAliveMonitor": "keepalive",
    "ServiceHealth": "keepalive",
    "ServiceStatus": "keepalive",
    "CLOUD_AGENTS": "keepalive_loop",
    "KeepAliveLoop": "keepalive_loop",
    # Local process management
    "AgentDaemon": "daemon",
    "DaemonSupervisor": "daemon",
    "ExecutionMode": "daemon",
    # Universal memory fabric (loaded lazily to avoid import-time SQLite creation)
    "AGENT_GROUPS": "memory_fabric",
    "DistilledLesson": "memory_fabric",
    "MemoryEntry": "memory_fabric",
    "MemoryScope": "memory_fabric",
    "NightlyLessonDistiller": "memory_fabric",
    "UniversalMemoryFabric": "memory_fabric",
    "fabric": "memory_fabric",
    "lesson_distiller": "memory_fabric",
    # Distributed heavy-task coordination
    "HeavyTaskAcquireTimeout": "heavy_task",
    "HeavyTaskBackendError": "heavy_task",
    "HeavyTaskCoordinationError": "heavy_task",
    "HeavyTaskCoordinator": "heavy_task",
    "HeavyTaskLease": "heavy_task",
    "HeavyTaskLeaseLost": "heavy_task",
    "coordinator_from_environment": "heavy_task",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    """Load public API objects on demand while preserving legacy imports."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy exports in tab completion and public API inspection."""
    return sorted(set(globals()) | set(__all__))
