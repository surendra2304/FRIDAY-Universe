"""
Kahn's Algorithm Cycle Detection and Topological Sorting for Task Graphs.
Enforces invariant: dependency graphs must be strictly directed acyclic graphs (DAGs).
"""

from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence

from app.dag.models import DAGEdge, DAGNode


class CycleDetectedError(ValueError):
    """Raised when a circular dependency or cycle is detected in a task DAG."""


class KahnCycleDetector:
    """
    Implements Kahn's algorithm for topological sorting and cycle detection.
    Computes node in-degrees, iteratively processes zero in-degree nodes,
    and isolates cyclical subsets when deadlocks occur.
    """

    @classmethod
    def detect_cycles(
        cls,
        nodes: Mapping[str, DAGNode],
        edges: Sequence[DAGEdge] | None = None,
    ) -> list[str]:
        """
        Detect whether cycles exist in the node set.
        Returns a list of node IDs involved in or blocked by cycles.
        If the graph is acyclic, returns an empty list.
        """
        if not nodes:
            return []

        # Validate self-dependencies and missing dependencies first
        for node_id, node in nodes.items():
            for dep in node.dependencies:
                if dep == node_id:
                    return [node_id]
                if dep not in nodes:
                    # Missing dependency is not a cycle, but invalidates traversal
                    pass

        # Compute in-degrees and adjacency
        in_degree: dict[str, int] = {nid: 0 for nid in nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in nodes}

        for node_id, node in nodes.items():
            for dep in node.dependencies:
                if dep in nodes:
                    in_degree[node_id] += 1
                    adjacency[dep].append(node_id)

        # Queue of nodes with 0 in-degree (no unresolved dependencies)
        queue: deque[str] = deque([nid for nid, deg in in_degree.items() if deg == 0])
        processed_count = 0

        while queue:
            curr = queue.popleft()
            processed_count += 1
            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If processed_count < total nodes, cycle(s) exist among remaining nodes with in_degree > 0
        if processed_count < len(nodes):
            return [nid for nid, deg in in_degree.items() if deg > 0]
        return []

    @classmethod
    def topological_sort(cls, nodes: Mapping[str, DAGNode]) -> list[str]:
        """
        Return a valid topological ordering of node IDs using Kahn's algorithm.
        Raises CycleDetectedError if any cycle is present.
        """
        if not nodes:
            return []

        # Self dependency check
        for node_id, node in nodes.items():
            for dep in node.dependencies:
                if dep == node_id:
                    raise CycleDetectedError(f"Self dependency detected on node '{node_id}'")
                if dep not in nodes:
                    raise ValueError(f"Missing dependency '{dep}' for node '{node_id}'")

        in_degree: dict[str, int] = {nid: 0 for nid in nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in nodes}

        for node_id, node in nodes.items():
            for dep in node.dependencies:
                in_degree[node_id] += 1
                adjacency[dep].append(node_id)

        queue: deque[str] = deque([nid for nid, deg in in_degree.items() if deg == 0])
        ordered: list[str] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(nodes):
            cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
            raise CycleDetectedError(
                f"Dependency cycle detected via Kahn's algorithm among nodes: {cycle_nodes}"
            )

        return ordered
