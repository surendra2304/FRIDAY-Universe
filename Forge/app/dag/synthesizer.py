"""
Autonomous Multi-File DAG Synthesizer.
Coordinates incremental multi-file codebase generation, topological scheduling,
and atomic file patching.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.dag.cycle_detector import KahnCycleDetector
from app.dag.models import DAGGraph, DAGNode, DAGPhase
from forge_upgrade.patching import PatchPreview, SafePatcher

logger = get_logger("dag.synthesizer")


class MultiFileSynthesizer:
    """
    Synthesizes multi-file codebases in topological waves.
    Decomposes software requirements into DAG phases:
    Contracts -> Implementation -> Helpers -> Tests -> Verification.
    """

    def __init__(self, wm: WorkspaceManager | None = None):
        self.wm = wm or workspace_manager

    def build_synthesis_dag(
        self,
        task_id: str,
        goal: str,
        file_manifest: list[str] | None = None,
    ) -> DAGGraph:
        """
        Construct a multi-file dependency DAG tailored to the project goal.
        """
        graph = DAGGraph(graph_id=f"dag_{task_id}", title=f"Synthesis DAG: {goal[:40]}")
        files = file_manifest or ["models.py", "core.py", "utils.py", "test_core.py"]

        # Phase 1: Contracts & Data Models
        contract_files = [f for f in files if "model" in f or "schema" in f or "type" in f or "interface" in f]
        if not contract_files:
            contract_files = [files[0]]
        graph.add_node(
            DAGNode(
                node_id="phase_contracts",
                title="Synthesize Types and Contract Interfaces",
                phase=DAGPhase.CONTRACTS,
                dependencies=(),
                target_files=tuple(contract_files),
                assigned_role="developer",
                instructions="Define all core data models, interfaces, and schemas.",
            )
        )

        # Phase 2: Core Implementation
        impl_files = [f for f in files if f not in contract_files and not f.startswith("test_")]
        if not impl_files:
            impl_files = ["main.py"]
        graph.add_node(
            DAGNode(
                node_id="phase_implementation",
                title="Synthesize Core Application Logic",
                phase=DAGPhase.IMPLEMENTATION,
                dependencies=("phase_contracts",),
                target_files=tuple(impl_files),
                assigned_role="developer",
                instructions="Implement business logic adhering strictly to the contract interfaces.",
            )
        )

        # Phase 3: Unit & Integration Tests
        test_files = [f for f in files if f.startswith("test_") or "test" in f]
        if not test_files:
            test_files = ["test_main.py"]
        graph.add_node(
            DAGNode(
                node_id="phase_tests",
                title="Synthesize Automated Test Battery",
                phase=DAGPhase.TESTS,
                dependencies=("phase_implementation",),
                target_files=tuple(test_files),
                assigned_role="test_engineer",
                instructions="Author unit and integration tests covering >= 80% code paths.",
            )
        )

        # Phase 4: Objective Verification Gate
        graph.add_node(
            DAGNode(
                node_id="phase_verification",
                title="Verify Build, Lint, Security and Tests",
                phase=DAGPhase.VERIFICATION,
                dependencies=("phase_tests",),
                target_files=(),
                assigned_role="code_reviewer",
                instructions="Execute 10-point verification battery to confirm 100% clean exit codes.",
            )
        )

        # Validate with Kahn's algorithm before returning
        KahnCycleDetector.topological_sort(graph.nodes)
        return graph

    def create_patch_preview(
        self,
        task_id: str,
        changes: dict[str, str],
    ) -> PatchPreview:
        """Generate unified diff preview for multi-file code modifications."""
        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        patcher = SafePatcher(paths.project)
        return patcher.preview(changes)

    def apply_patch(
        self,
        task_id: str,
        changes: dict[str, str],
        expected_sha: dict[str, str | None] | None = None,
    ) -> Any:
        """
        Apply incremental file patches safely with path confinement check and sha validation.
        """
        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        patcher = SafePatcher(paths.project)
        return patcher.apply(changes, expected_sha=expected_sha)
