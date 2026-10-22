"""
Executable Task Graph DAG for Project FORGE Planning Engine.
Converts hierarchical trees into dependency-ordered execution graphs with parallel wave resolution.
"""

from collections import deque

from app.memory.models import TaskEdge, TaskGraph, TaskNode, TaskState
from app.planning.tree import HierarchicalTaskTree


class ExecutableTaskDAG:
    """Manages dependency resolution, topological ordering, and parallel node scheduling."""

    def __init__(self, graph: TaskGraph):
        self.graph = graph

    @classmethod
    def from_tree(cls, tree: HierarchicalTaskTree) -> "ExecutableTaskDAG":
        """Transform a HierarchicalTaskTree into an executable TaskGraph DAG."""
        graph = TaskGraph(
            id=tree.project_id,
            project_id=tree.project_id,
            goal=tree.goal,
            status=TaskState.PENDING,
        )

        all_nodes = tree.get_all_nodes()
        # Add non-root nodes as executable task nodes
        for tn in all_nodes:
            if tn.id == tree.root.id:
                continue
            node = TaskNode(
                id=tn.id,
                title=f"[{tn.stage.value}] {tn.title}",
                description=tn.description,
                status=tn.status,
                dependencies=list(tn.dependencies),
                assigned_agent=tn.assigned_role,
                metadata={
                    "stage": tn.stage.value,
                    "node_type": tn.node_type.value,
                    "verification_criteria": tn.verification_gate_criteria,
                },
            )
            graph.add_node(node)

        # Build edges based on dependencies
        for node in graph.nodes.values():
            for dep_id in node.dependencies:
                if dep_id in graph.nodes:
                    graph.edges.append(TaskEdge(source=dep_id, target=node.id))

        return cls(graph)

    def get_ready_nodes(self) -> list[TaskNode]:
        """
        Return nodes that are PENDING and have all prerequisite dependencies COMPLETED.
        Allows parallel wave execution.
        """
        ready: list[TaskNode] = []
        for node in self.graph.nodes.values():
            if node.status != TaskState.PENDING:
                continue

            # Check if all dependencies are satisfied
            deps_satisfied = True
            for dep_id in node.dependencies:
                dep_node = self.graph.nodes.get(dep_id)
                if not dep_node or dep_node.status != TaskState.COMPLETED:
                    deps_satisfied = False
                    break

            if deps_satisfied:
                ready.append(node)

        return ready

    def mark_running(self, node_id: str) -> None:
        if node_id in self.graph.nodes:
            self.graph.nodes[node_id].status = TaskState.RUNNING
            self.graph.current_node_id = node_id

    def mark_completed(self, node_id: str, result: dict | None = None) -> None:
        if node_id in self.graph.nodes:
            self.graph.nodes[node_id].status = TaskState.COMPLETED
            self.graph.nodes[node_id].result = result

    def mark_failed(self, node_id: str, error: str) -> None:
        if node_id in self.graph.nodes:
            self.graph.nodes[node_id].status = TaskState.FAILED
            self.graph.nodes[node_id].error = error
            self.graph.status = TaskState.FAILED

    def is_completed(self) -> bool:
        """Check if all nodes in graph are COMPLETED."""
        if not self.graph.nodes:
            return True
        return all(n.status == TaskState.COMPLETED for n in self.graph.nodes.values())

    def has_failures(self) -> bool:
        """Check if any node is in FAILED state."""
        return any(n.status == TaskState.FAILED for n in self.graph.nodes.values())

    def get_progress_percentage(self) -> int:
        """Calculate overall DAG completion percentage."""
        if not self.graph.nodes:
            return 100
        completed = sum(1 for n in self.graph.nodes.values() if n.status == TaskState.COMPLETED)
        return int((completed / len(self.graph.nodes)) * 100)

    def validate(self) -> list[str]:
        """Validate DAG: detect self-dependencies, missing dependencies, and cycles."""
        errors: list[str] = []
        for node in self.graph.nodes.values():
            for dep in node.dependencies:
                if dep == node.id:
                    errors.append(f"Self dependency detected on node '{node.id}'")
                elif dep not in self.graph.nodes:
                    errors.append(f"Missing dependency on node '{node.id}': '{dep}' not in graph")

        in_degree: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for node in self.graph.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.id] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        seen = 0
        while queue:
            curr = queue.popleft()
            seen += 1
            for edge in self.graph.edges:
                if edge.source == curr:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        if seen != len(self.graph.nodes):
            errors.append(
                f"Dependency cycle detected in graph: processed {seen}/{len(self.graph.nodes)} nodes"
            )

        return errors

    def topological_sort(self) -> list[str]:
        """Return topological ordering of node IDs or raise ValueError if cycle detected."""
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))

        in_degree: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        for node in self.graph.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.id] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        ordered: list[str] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for edge in self.graph.edges:
                if edge.source == curr:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        if len(ordered) != len(self.graph.nodes):
            raise ValueError(
                f"Graph contains dependency cycles: ordered {len(ordered)}/{len(self.graph.nodes)} nodes"
            )

        return ordered
