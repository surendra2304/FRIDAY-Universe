"""
Unit tests for Planning Subsystem: HierarchicalTaskTree, ExecutableTaskDAG, and PlannerEngine.
"""

from uuid import uuid4

import pytest

from app.planning.planner import PlannerEngine
from app.planning.tree import (
    PipelineStage,
)


@pytest.mark.asyncio
async def test_planner_engine_synthesizes_8_stage_tree():
    planner = PlannerEngine()
    task_id = str(uuid4())
    goal = "Build a Real-Time Distributed Chat Application in Python"
    requirements = ["Websocket support", "Redis pub/sub", "JWT auth"]

    tree = await planner.plan(task_id, goal, requirements)

    assert tree.project_id == task_id
    assert tree.goal == goal
    assert tree.root.stage == PipelineStage.PROJECT

    all_nodes = tree.get_all_nodes()
    stages_present = {n.stage for n in all_nodes}

    # Verify all 8 canonical stages exist
    assert PipelineStage.PROJECT in stages_present
    assert PipelineStage.REQUIREMENTS in stages_present
    assert PipelineStage.ARCHITECTURE in stages_present
    assert PipelineStage.IMPLEMENTATION in stages_present
    assert PipelineStage.INTEGRATION in stages_present
    assert PipelineStage.VERIFICATION in stages_present
    assert PipelineStage.SECURITY in stages_present
    assert PipelineStage.RELEASE in stages_present


@pytest.mark.asyncio
async def test_executable_dag_dependency_resolution():
    planner = PlannerEngine()
    task_id = str(uuid4())
    dag = await planner.create_executable_dag(task_id, "Build REST API")

    # Initial ready nodes should only be the first stage without dependencies
    ready = dag.get_ready_nodes()
    assert len(ready) >= 1
    first_node = ready[0]
    assert "Requirements" in first_node.title

    # Mark first node completed and check next ready nodes
    dag.mark_completed(first_node.id)
    next_ready = dag.get_ready_nodes()
    assert len(next_ready) >= 1
    assert "Architecture" in next_ready[0].title

    # Test topological sorting
    ordered_ids = dag.topological_sort()
    assert len(ordered_ids) == len(dag.graph.nodes)


@pytest.mark.asyncio
async def test_dag_progress_and_completion():
    planner = PlannerEngine()
    task_id = str(uuid4())
    dag = await planner.create_executable_dag(task_id, "Build Microservice")

    assert dag.get_progress_percentage() == 0
    assert not dag.is_completed()

    # Complete all nodes sequentially
    for node_id in dag.topological_sort():
        dag.mark_completed(node_id)

    assert dag.get_progress_percentage() == 100
    assert dag.is_completed()
    assert not dag.has_failures()
