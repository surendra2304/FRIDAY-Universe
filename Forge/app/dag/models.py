"""
Domain models for the Autonomous Multi-File DAG Synthesizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class DAGPhase(str, Enum):
    CONTRACTS = "contracts"
    IMPLEMENTATION = "implementation"
    HELPERS = "helpers"
    TESTS = "tests"
    VERIFICATION = "verification"
    DELIVERY = "delivery"


@dataclass(frozen=True, slots=True)
class DAGNode:
    node_id: str
    title: str
    phase: DAGPhase
    dependencies: tuple[str, ...] = ()
    target_files: tuple[str, ...] = ()
    assigned_role: str = "developer"
    instructions: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DAGEdge:
    source: str
    target: str
    edge_type: str = "dependency"


@dataclass(slots=True)
class DAGGraph:
    graph_id: str
    title: str
    nodes: dict[str, DAGNode] = field(default_factory=dict)
    edges: list[DAGEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.node_id] = node
        for dep in node.dependencies:
            self.edges.append(DAGEdge(source=dep, target=node.node_id))


@dataclass(frozen=True, slots=True)
class FilePatchSpec:
    path: str
    content: str
    action: str = "modify"  # "create" | "modify" | "delete"
    expected_sha256: str | None = None
