"""
Planner Engine for Project FORGE.
Synthesizes natural language requirements into the standard 8-stage hierarchical tree and durable executable DAG.
"""

from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.planning.graph import ExecutableTaskDAG
from app.planning.tree import (
    HierarchicalTaskTree,
    PipelineStage,
    TaskTreeNode,
    TreeNodeType,
)
from app.providers import BaseModelProvider, get_provider

logger = get_logger("planning.planner")


class PlannerEngine:
    """Decomposes engineering goals into standard 8-stage trees and executable DAGs."""

    def __init__(self, provider: BaseModelProvider | None = None):
        self.provider = provider or get_provider()

    async def plan(
        self,
        task_id: str,
        goal: str,
        requirements: list[str] | None = None,
        has_existing_codebase: bool = False,
        context: dict[str, Any] | None = None,
    ) -> HierarchicalTaskTree:
        """
        Synthesize goal and requirements into the canonical pipeline tree:
        Project -> Requirements -> [Codebase Analysis] -> Architecture -> Implementation -> Integration -> Verification -> Security -> Release.

        `context` carries caller-supplied recall (e.g. the CLI's Memora
        memory_context). It used to be dropped, so remembered preferences never
        reached the plan.
        """
        req_list = requirements or []
        plan_context = dict(context or {})
        memory_context = str(plan_context.get("memory_context", "") or "")
        logger.info(
            f"Synthesizing plan for task '{task_id}' (existing_codebase={has_existing_codebase}): {goal[:80]}..."
        )

        # 1. Project Root
        root = TaskTreeNode(
            id=str(uuid4()),
            title=f"Project: {goal}",
            description=f"Autonomous execution of: {goal}",
            stage=PipelineStage.PROJECT,
            node_type=TreeNodeType.MILESTONE,
            assigned_role="planner",
        )

        # 2. Stage: Requirements
        node_req = TaskTreeNode(
            id=str(uuid4()),
            title="Requirements Specification & Scope Definition",
            description=(
                f"Formalize scope and constraints: {req_list}"
                + (f"\nRecalled context: {memory_context}" if memory_context else "")
            ),
            stage=PipelineStage.REQUIREMENTS,
            node_type=TreeNodeType.TASK,
            assigned_role="planner",
            dependencies=[],
        )

        children = [node_req]
        arch_deps = [node_req.id]

        # Check if existing codebase onboarding / analysis is required
        combined_text = f"{goal} {' '.join(req_list)} {memory_context}".lower()
        if has_existing_codebase or any(
            k in combined_text
            for k in ["existing codebase", "modify repo", "refactor repo", "onboarding", "codebase"]
        ):
            node_analysis = TaskTreeNode(
                id=str(uuid4()),
                title="Codebase Analysis & Project Context Mapping",
                description="Inspect existing codebase architecture, package manifests, entrypoints, and directory structure.",
                stage=PipelineStage.REQUIREMENTS,
                node_type=TreeNodeType.TASK,
                assigned_role="codebase_analyzer",
                dependencies=[node_req.id],
            )
            children.append(node_analysis)
            arch_deps = [node_analysis.id]

        # 3. Stage: Architecture
        node_arch = TaskTreeNode(
            id=str(uuid4()),
            title="System Architecture & Module Design",
            description="Formulate module boundaries, API signatures, and data models.",
            stage=PipelineStage.ARCHITECTURE,
            node_type=TreeNodeType.TASK,
            assigned_role="architect",
            dependencies=arch_deps,
        )
        children.append(node_arch)

        # Check for full-stack frontend/backend parallel division
        is_fullstack = any(
            k in combined_text
            for k in [
                "full-stack",
                "fullstack",
                "react",
                "frontend",
                "ui",
                "web dashboard",
                "weather dashboard",
            ]
        ) and any(
            k in combined_text for k in ["fastapi", "backend", "api", "sqlite", "server", "rest"]
        )

        if is_fullstack:
            # Parallel branch: Frontend UI & Backend API
            node_fe = TaskTreeNode(
                id=str(uuid4()),
                title="Frontend Component & UI Synthesis",
                description="Build responsive client interface, state management, and user views.",
                stage=PipelineStage.IMPLEMENTATION,
                node_type=TreeNodeType.TASK,
                assigned_role="frontend",
                dependencies=[node_arch.id],
            )
            node_be = TaskTreeNode(
                id=str(uuid4()),
                title="Backend API & Data Layer Synthesis",
                description="Implement REST endpoints, schemas, and database persistence.",
                stage=PipelineStage.IMPLEMENTATION,
                node_type=TreeNodeType.TASK,
                assigned_role="backend",
                dependencies=[node_arch.id],
            )
            node_integration = TaskTreeNode(
                id=str(uuid4()),
                title="Full-Stack Integration & Configuration Wiring",
                description="Connect frontend client with backend REST API.",
                stage=PipelineStage.INTEGRATION,
                node_type=TreeNodeType.TASK,
                assigned_role="developer",
                dependencies=[node_fe.id, node_be.id],
            )
            children.extend([node_fe, node_be, node_integration])
        else:
            # 4. Stage: Implementation
            node_impl_core = TaskTreeNode(
                id=str(uuid4()),
                title="Core Implementation & Logic Synthesis",
                description="Author clean, idiomatic implementation conforming to architecture specification.",
                stage=PipelineStage.IMPLEMENTATION,
                node_type=TreeNodeType.TASK,
                assigned_role="developer",
                dependencies=[node_arch.id],
            )

            # 5. Stage: Integration
            node_integration = TaskTreeNode(
                id=str(uuid4()),
                title="Module Integration & Configuration Wiring",
                description="Connect components, environment variables, and dependencies.",
                stage=PipelineStage.INTEGRATION,
                node_type=TreeNodeType.TASK,
                assigned_role="developer",
                dependencies=[node_impl_core.id],
            )
            children.extend([node_impl_core, node_integration])

        # 6. Stage: Verification
        node_verify = TaskTreeNode(
            id=str(uuid4()),
            title="Automated Test Suite & Verification Gate",
            description="Execute automated test runner to ensure 100% assertions pass.",
            stage=PipelineStage.VERIFICATION,
            node_type=TreeNodeType.VERIFICATION_GATE,
            assigned_role="tester",
            dependencies=[node_integration.id],
            verification_gate_criteria="All automated tests pass with 0 errors.",
        )

        # 7. Stage: Security
        node_sec = TaskTreeNode(
            id=str(uuid4()),
            title="Security Audit & Code Review Gate",
            description="Scan source code for vulnerabilities, secret leaks, and architectural compliance.",
            stage=PipelineStage.SECURITY,
            node_type=TreeNodeType.VERIFICATION_GATE,
            assigned_role="security_reviewer",
            dependencies=[node_verify.id],
            verification_gate_criteria="Zero secret leaks and clean security review.",
        )

        # 8. Stage: Release
        node_release = TaskTreeNode(
            id=str(uuid4()),
            title="Release Packaging & Checkpoint Tagging",
            description="Package verified artifacts, generate summary documentation, and create git release checkpoint.",
            stage=PipelineStage.RELEASE,
            node_type=TreeNodeType.MILESTONE,
            assigned_role="release_engineer",
            dependencies=[node_sec.id],
        )

        children.extend([node_verify, node_sec, node_release])
        root.children = children

        tree = HierarchicalTaskTree(
            project_id=task_id,
            goal=goal,
            root=root,
        )

        return tree

    async def create_executable_dag(
        self,
        task_id: str,
        goal: str,
        requirements: list[str] | None = None,
    ) -> ExecutableTaskDAG:
        """Helper to create tree and immediately return the executable DAG."""
        tree = await self.plan(task_id, goal, requirements)
        return ExecutableTaskDAG.from_tree(tree)


planner_engine = PlannerEngine()
