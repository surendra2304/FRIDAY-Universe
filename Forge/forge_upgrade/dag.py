from __future__ import annotations

from dataclasses import dataclass

from .models import NodeStatus, PlanGraph, PlanNode


@dataclass(slots=True)
class NodeRuntime:
    status: NodeStatus = NodeStatus.PENDING
    attempts: int = 0
    error: str | None = None


class DagScheduler:
    """Track legal DAG task transitions and propagate failed prerequisites."""

    def __init__(self, graph: PlanGraph):
        self.graph = graph
        self.runtime = {node_id: NodeRuntime() for node_id in graph.nodes}

    def validate(self) -> None:
        errors = self.graph.validate()
        if errors:
            raise ValueError("; ".join(errors))

    def ready(self) -> list[PlanNode]:
        ready = []
        for node_id, node in self.graph.nodes.items():
            state = self.runtime[node_id]
            if state.status != NodeStatus.PENDING:
                continue
            if all(self.runtime[dep].status == NodeStatus.PASSED for dep in node.dependencies):
                ready.append(node)
        ready.sort(key=lambda node: (node.phase.value, node.node_id))
        for node in ready:
            self.runtime[node.node_id].status = NodeStatus.READY
        return ready

    def mark_running(self, node_id: str) -> None:
        state = self.runtime[node_id]
        if state.status != NodeStatus.READY:
            raise ValueError(
                f"node '{node_id}' cannot start from state '{state.status.value}'; "
                "call ready() and select a ready node first"
            )
        if any(self.runtime[dependency].status != NodeStatus.PASSED
               for dependency in self.graph.nodes[node_id].dependencies):
            raise ValueError(f"node '{node_id}' has prerequisites that have not passed")
        state.status = NodeStatus.RUNNING
        state.attempts += 1

    def mark_passed(self, node_id: str) -> None:
        state = self.runtime[node_id]
        if state.status != NodeStatus.RUNNING:
            raise ValueError(
                f"node '{node_id}' cannot pass from state '{state.status.value}'; "
                "only a running node can pass"
            )
        state.status = NodeStatus.PASSED
        state.error = None

    def mark_failed(self, node_id: str, error: str) -> None:
        state = self.runtime[node_id]
        if state.status != NodeStatus.RUNNING:
            raise ValueError(
                f"node '{node_id}' cannot fail from state '{state.status.value}'; "
                "only a running node can fail"
            )
        state.status = NodeStatus.FAILED
        state.error = error
        self._propagate_blocked()

    def _propagate_blocked(self) -> None:
        """Recursively block pending descendants of a failed or blocked prerequisite."""
        changed = True
        while changed:
            changed = False
            for node_id, node in self.graph.nodes.items():
                state = self.runtime[node_id]
                if state.status not in {NodeStatus.PENDING, NodeStatus.READY}:
                    continue
                failed_dependency = next(
                    (
                        dependency
                        for dependency in node.dependencies
                        if self.runtime[dependency].status in {NodeStatus.FAILED, NodeStatus.BLOCKED}
                    ),
                    None,
                )
                if failed_dependency is not None:
                    state.status = NodeStatus.BLOCKED
                    state.error = f"blocked by prerequisite '{failed_dependency}'"
                    changed = True

    def blocking_nodes(self) -> list[str]:
        return [
            node_id
            for node_id, state in self.runtime.items()
            if state.status == NodeStatus.BLOCKED
        ]

    def complete(self) -> bool:
        return all(
            state.status in {NodeStatus.PASSED, NodeStatus.SKIPPED}
            for state in self.runtime.values()
        )

    def failed(self) -> bool:
        return any(state.status == NodeStatus.FAILED for state in self.runtime.values())

    def progress(self) -> float:
        if not self.runtime:
            return 1.0
        done = sum(
            state.status in {NodeStatus.PASSED, NodeStatus.SKIPPED, NodeStatus.FAILED, NodeStatus.BLOCKED}
            for state in self.runtime.values()
        )
        return done / len(self.runtime)
