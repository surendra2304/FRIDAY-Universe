"""
Unit tests for SQLite StateStore, Task Graphs, Checkpoints, Tasks, Audit Events, and Artifact Records.
"""

from uuid import uuid4

import pytest

from app.memory.models import (
    ArtifactRecord,
    Checkpoint,
    ProjectWorkspace,
    TaskEntity,
    TaskGraph,
    TaskMode,
    TaskNode,
    TaskState,
)
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_task_entity_crud(state_store: StateStore):
    task_id = str(uuid4())
    task = TaskEntity(
        id=task_id,
        goal="Develop CLI argument parser",
        requirements=["Use argparse", "Support subcommands"],
        mode=TaskMode.AUTONOMOUS,
        workspace_path=f"/workspaces/task_{task_id}",
        max_budget=15.0,
    )

    created = await state_store.create_task(task)
    assert created.id == task_id
    assert created.state == TaskState.PENDING

    fetched = await state_store.get_task(task_id)
    assert fetched is not None
    assert fetched.goal == "Develop CLI argument parser"
    assert len(fetched.requirements) == 2

    # Update state & budget
    updated = await state_store.update_task_state(
        task_id=task_id,
        state=TaskState.RUNNING,
        progress_percentage=50,
        budget_increment=0.125,
    )
    assert updated.state == TaskState.RUNNING
    assert updated.progress_percentage == 50
    assert updated.budget_consumed == 0.125


@pytest.mark.asyncio
async def test_audit_event_recording(state_store: StateStore):
    task_id = str(uuid4())
    task = TaskEntity(
        id=task_id,
        goal="Audit Event Test Task",
        workspace_path=f"/workspaces/task_{task_id}",
    )
    await state_store.create_task(task)

    await state_store.record_event(task_id, "task.created", {"goal": "Test Goal"})
    await state_store.record_event(task_id, "plan.created", {"steps": 4})

    trail = await state_store.get_audit_trail(task_id)
    assert len(trail) == 2
    assert trail[0].event_type == "task.created"
    assert trail[1].event_type == "plan.created"
    assert trail[1].payload["steps"] == 4


@pytest.mark.asyncio
async def test_artifact_recording(state_store: StateStore):
    task_id = str(uuid4())
    task = TaskEntity(
        id=task_id,
        goal="Artifact Test Task",
        workspace_path=f"/workspaces/task_{task_id}",
    )
    await state_store.create_task(task)

    art_id = str(uuid4())
    artifact = ArtifactRecord(
        id=art_id,
        task_id=task_id,
        name="dist/app.tar.gz",
        path=f"/workspaces/task_{task_id}/artifacts/app.tar.gz",
        file_type="application/gzip",
        size_bytes=1024,
    )

    await state_store.record_artifact(artifact)
    fetched = await state_store.get_artifact(art_id)
    assert fetched is not None
    assert fetched.name == "dist/app.tar.gz"

    artifacts_list = await state_store.list_artifacts_for_task(task_id)
    assert len(artifacts_list) == 1
    assert artifacts_list[0].id == art_id


@pytest.mark.asyncio
async def test_project_workspace_persistence(state_store: StateStore):
    project_id = str(uuid4())
    project = ProjectWorkspace(
        id=project_id,
        name="Microservice Auth",
        description="Build OAuth2 authentication microservice",
        workspace_path="/tmp/workspaces/auth",
        config={"python_version": "3.11", "framework": "fastapi"},
    )

    created = await state_store.create_project(project)
    assert created.id == project_id

    fetched = await state_store.get_project(project_id)
    assert fetched is not None
    assert fetched.id == project_id
    assert fetched.name == "Microservice Auth"
    assert fetched.config["framework"] == "fastapi"


@pytest.mark.asyncio
async def test_task_graph_persistence(state_store: StateStore):
    project_id = str(uuid4())
    project = ProjectWorkspace(
        id=project_id,
        name="Compiler Project",
        workspace_path="/tmp/workspaces/compiler",
    )
    await state_store.create_project(project)

    graph_id = str(uuid4())
    graph = TaskGraph(
        id=graph_id,
        project_id=project_id,
        goal="Create an AST parser for mathematical expressions",
    )

    node1 = TaskNode(id="node_1", title="Define Token Enums", status=TaskState.COMPLETED)
    node2 = TaskNode(id="node_2", title="Implement Lexer", status=TaskState.RUNNING)
    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_edge("node_1", "node_2")

    saved_graph = await state_store.save_task_graph(graph)
    assert saved_graph.id == graph_id

    loaded_graph = await state_store.get_task_graph(graph_id)
    assert loaded_graph is not None
    assert loaded_graph.nodes["node_1"].status == TaskState.COMPLETED
    assert loaded_graph.nodes["node_2"].dependencies == ["node_1"]


@pytest.mark.asyncio
async def test_checkpoint_persistence(state_store: StateStore):
    project_id = str(uuid4())
    project = ProjectWorkspace(
        id=project_id,
        name="Checkpoint Test Project",
        workspace_path="/tmp/workspaces/checkpoint",
    )
    await state_store.create_project(project)

    cp1 = Checkpoint(
        id=str(uuid4()),
        project_id=project_id,
        step_number=1,
        state_data={"completed_files": ["token.py"], "tests_passing": True},
        description="Tokens implemented",
    )
    cp2 = Checkpoint(
        id=str(uuid4()),
        project_id=project_id,
        step_number=2,
        state_data={"completed_files": ["token.py", "lexer.py"], "tests_passing": True},
        description="Lexer implemented and tested",
    )

    await state_store.save_checkpoint(cp1)
    await state_store.save_checkpoint(cp2)

    history = await state_store.list_checkpoints(project_id)
    assert len(history) == 2
    assert history[0].step_number == 1
    assert history[1].step_number == 2
