"""FRIDAY Universe Mesh — High-Speed Inter-Agent Transport & Keep-Alive.

Phase 1: High-Speed Authenticated Event Mesh & Real-Time Keep-Alive.

Features:
- Standard JSON message envelope with HMAC-SHA256 signatures and UUID correlation
- 9-Agent manifest registry & capability/intent discovery
- High-throughput transport (NATS JetStream + Authenticated async HTTP fallback)
- 24/7 Keep-alive monitor & probe loop for all 9 Render cloud services
- Cloud-First execution routing with on-demand local daemon management
"""

from mesh.envelope import (
    AgentEnvelope,
    EnvelopeError,
    MessagePriority,
    build_envelope,
    validate_envelope,
)
from mesh.registry import (
    AgentDiscovery,
    AgentManifest,
    AgentRegistry,
    ManifestError,
    create_default_registry,
)
from mesh.transport import (
    MeshTransport,
    TransportMode,
    get_mesh_transport,
)
from mesh.keepalive import (
    CircuitBreaker,
    KeepAliveMonitor,
    ServiceHealth,
    ServiceStatus,
)
from mesh.keepalive_loop import (
    CLOUD_AGENTS,
    KeepAliveLoop,
)
from mesh.daemon import (
    AgentDaemon,
    DaemonSupervisor,
    ExecutionMode,
)
from mesh.memory_fabric import (
    AGENT_GROUPS,
    DistilledLesson,
    MemoryEntry,
    MemoryScope,
    NightlyLessonDistiller,
    UniversalMemoryFabric,
    fabric,
    lesson_distiller,
)

__all__ = [
    "AgentEnvelope",
    "EnvelopeError",
    "MessagePriority",
    "build_envelope",
    "validate_envelope",
    "AgentDiscovery",
    "AgentManifest",
    "AgentRegistry",
    "ManifestError",
    "create_default_registry",
    "MeshTransport",
    "TransportMode",
    "get_mesh_transport",
    "CircuitBreaker",
    "KeepAliveMonitor",
    "ServiceHealth",
    "ServiceStatus",
    "CLOUD_AGENTS",
    "KeepAliveLoop",
    "AgentDaemon",
    "DaemonSupervisor",
    "ExecutionMode",
    "MemoryScope",
    "MemoryEntry",
    "DistilledLesson",
    "UniversalMemoryFabric",
    "NightlyLessonDistiller",
    "fabric",
    "lesson_distiller",
    "AGENT_GROUPS",
]
