"""
Topological Dependency Scheduler for Multi-File Autonomous Synthesizer.
Schedules execution in deterministic, cycle-free topological waves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.dag.cycle_detector import KahnCycleDetector
from app.dag.models import DAGGraph, NodeStatus


@dataclass(slots=True)
class NodeRuntimeState:
    status: NodeStatus = NodeStatus.PENDING
    attempts: int = 0
    error: str | None = None
    output_artifacts: list[str] | None = None


class DagScheduler:
    """
    Topological wave scheduler with Kahn cycle detection, dynamic status propagation,
    and cascading blocked-node resolution.
    """

    def __init__(self, graph: DAGGraph | Any):
        self.graph = graph
        # Support both DAGGraph and PlanGraph representations
        self.nodes: dict[str, Any] = getattr(graph, "nodes", {})
        self.runtime: dict[str, NodeRuntimeState] = {
            node_id: NodeRuntimeState() for node_id in self.nodes
        }

    def validate(self) -> None:
        """Validate acyclicity using Kahn's algorithm."""
        # Convert nodes if necessary
        cycle_nodes = KahnCycleDetector.detect_cycles(self.nodes)
        if cycle_nodes:
            raise ValueError(f"Dependency cycle detected in graph among nodes: {cycle_nodes}")

    def ready(self) -> list[Any]:
        """
        Return list of nodes currently PENDING whose dependencies have all PASSED.
        Sorted deterministically by phase and node ID.
        """
        ready_nodes = []
        for node_id, node in self.nodes.items():
            state = self.runtime[node_id]
            if state.status != NodeStatus.PENDING:
                continue

            deps = getattr(node, "dependencies", ())
            if all(self.runtime[dep].status == NodeStatus.PASSED for dep in deps if dep in self.runtime):
                ready_nodes.append(node)

        # Deterministic sort
        ready_nodes.sort(key=lambda n: (getattr(n, "phase", ""), getattr(n, "node_id", getattr(n, "id", ""))))
        for node in ready_nodes:
            nid = getattr(node, "node_id", getattr(node, "id", ""))
            self.runtime[nid].status = NodeStatus.READY
        return ready_nodes

    def mark_running(self, node_id: str) -> None:
        """Mark a node as RUNNING and increment attempt counter."""
        if node_id in self.runtime:
            self.runtime[node_id].status = NodeStatus.RUNNING
            self.runtime[node_id].attempts += 1

    def mark_passed(self, node_id: str, output_artifacts: list[str] | None = None) -> None:
        """Mark a node as PASSED and record any generated artifacts."""
        if node_id in self.runtime:
            self.runtime[node_id].status = NodeStatus.PASSED
            if output_artifacts:
                self.runtime[node_id].output_artifacts = list(output_artifacts)

    def mark_failed(self, node_id: str, error: str) -> None:
        """Mark a node as FAILED and cascade BLOCKED status to all dependents."""
        if node_id in self.runtime:
            self.runtime[node_id].status = NodeStatus.FAILED
            self.runtime[node_id].error = error
            self._cascade_blocked(node_id)

    def _cascade_blocked(self, failed_node_id: str) -> None:
        """Mark all transitive downstream dependents as BLOCKED."""
        for nid, node in self.nodes.items():
            if self.runtime[nid].status == NodeStatus.PENDING:
                deps = getattr(node, "dependencies", ())
                if failed_node_id in deps:
                    self.runtime[nid].status = NodeStatus.BLOCKED
                    self.runtime[nid].error = f"Prerequisite '{failed_node_id}' failed"
                    self._cascade_blocked(nid)

    def is_complete(self) -> bool:
        """Return True if all nodes have reached terminal passed/skipped status."""
        return all(
            s.status in {NodeStatus.PASSED, NodeStatus.SKIPPED}
            for s in self.runtime.values()
        )

    def complete(self) -> bool:
        """Parity alias for complete()."""
        return self.is_complete()

    def has_failed(self) -> bool:
        """Return True if any node has failed or is blocked."""
        return any(
            s.status in {NodeStatus.FAILED, NodeStatus.BLOCKED}
            for s in self.runtime.values()
        )

    def failed(self) -> bool:
        """Parity alias for failed()."""
        return self.has_failed()

    def progress(self) -> float:
        """Return progress fraction from 0.0 to 1.0."""
        if not self.runtime:
            return 1.0
        done = sum(
            1 for s in self.runtime.values()
            if s.status in {NodeStatus.PASSED, NodeStatus.SKIPPED}
        )
        return done / len(self.runtime)
