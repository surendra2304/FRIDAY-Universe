from __future__ import annotations

from dataclasses import dataclass

from .models import PlanGraph, TaskPhase


@dataclass(frozen=True, slots=True)
class PlanGuardResult:
    passed: bool
    errors: tuple[str, ...]


FORBIDDEN_DEPENDENCIES = {
    TaskPhase.DELIVER: {TaskPhase.IMPLEMENT, TaskPhase.REPAIR},
}
REQUIRED_DELIVERY_GATES = {TaskPhase.TEST, TaskPhase.REVIEW}


class PlanGuard:
    """Reject plans that can deliver output without depending on verification gates."""

    def validate(self, graph: PlanGraph) -> PlanGuardResult:
        errors = list(graph.validate())
        nodes = graph.nodes

        if not any(node.phase == TaskPhase.TEST for node in nodes.values()):
            errors.append("plan missing TEST phase")
        if not any(node.phase == TaskPhase.REVIEW for node in nodes.values()):
            errors.append("plan missing REVIEW phase")

        for node in nodes.values():
            if node.phase != TaskPhase.DELIVER:
                continue

            for dependency in node.dependencies:
                dependency_node = nodes.get(dependency)
                if (
                    dependency_node is not None
                    and dependency_node.phase in FORBIDDEN_DEPENDENCIES[TaskPhase.DELIVER]
                ):
                    errors.append(
                        f"delivery node '{node.node_id}' directly depends on "
                        f"unverified {dependency_node.phase.value} node '{dependency}'"
                    )

            ancestors = self._ancestors(graph, node.node_id)
            ancestor_phases = {nodes[ancestor].phase for ancestor in ancestors}
            missing_gates = REQUIRED_DELIVERY_GATES - ancestor_phases
            for missing_phase in sorted(missing_gates, key=lambda phase: phase.value):
                errors.append(
                    f"delivery node '{node.node_id}' does not depend on a "
                    f"{missing_phase.value} gate"
                )

        # Preserve the first occurrence while avoiding duplicate diagnostics when a
        # malformed graph triggers the same invariant through multiple checks.
        unique_errors = tuple(dict.fromkeys(errors))
        return PlanGuardResult(not unique_errors, unique_errors)

    @staticmethod
    def _ancestors(graph: PlanGraph, node_id: str) -> set[str]:
        """Return all transitive prerequisite node IDs without looping on cycles."""
        ancestors: set[str] = set()
        pending = list(graph.nodes[node_id].dependencies)
        while pending:
            dependency = pending.pop()
            if dependency in ancestors or dependency not in graph.nodes:
                continue
            ancestors.add(dependency)
            pending.extend(graph.nodes[dependency].dependencies)
        return ancestors
