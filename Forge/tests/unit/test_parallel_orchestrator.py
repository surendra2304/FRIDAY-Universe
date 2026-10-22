"""
Unit tests for Asynchronous Parallel DAG Wave Execution in OrchestratorCore.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.models import TaskEdge, TaskEntity, TaskGraph, TaskNode, TaskState
from app.memory.state_store import StateStore
from app.planning.graph import ExecutableTaskDAG


@pytest.mark.asyncio
async def test_parallel_wave_dependency_scheduling(temp_dir: Path):
    """
    Validates that independent nodes (Node A & Node B) execute concurrently in the same wave,
    while dependent Node C waits until both complete.
    """
    db_mgr = DatabaseManager(db_path=temp_dir / "parallel_test.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    task_id = str(uuid4())
    ws_paths = wm.create_workspace(task_id)

    # 1. Create Task
    task = TaskEntity(
        id=task_id,
        goal="Parallel Orchestration Verification",
        workspace_path=str(ws_paths.root),
        state=TaskState.READY,
    )
    await store.create_task(task)

    # 2. Build DAG with parallel branches:
    # Requirements (req) -> [Node_Frontend (fe), Node_Backend (be)] -> Integration (integ)
    nid_req = f"{task_id}_req"
    nid_fe = f"{task_id}_fe"
    nid_be = f"{task_id}_be"
    nid_integ = f"{task_id}_integ"

    node_req = TaskNode(
        id=nid_req, title="Requirements Spec", status=TaskState.COMPLETED, assigned_agent="planner"
    )
    node_fe = TaskNode(
        id=nid_fe, title="Frontend UI Synthesis", dependencies=[nid_req], assigned_agent="frontend"
    )
    node_be = TaskNode(
        id=nid_be, title="Backend API Synthesis", dependencies=[nid_req], assigned_agent="backend"
    )
    node_integ = TaskNode(
        id=nid_integ,
        title="Full-Stack Integration",
        dependencies=[nid_fe, nid_be],
        assigned_agent="developer",
    )

    graph = TaskGraph(
        id=task_id,
        project_id=task_id,
        goal=task.goal,
        status=TaskState.PENDING,
        nodes={
            nid_req: node_req,
            nid_fe: node_fe,
            nid_be: node_be,
            nid_integ: node_integ,
        },
        edges=[
            TaskEdge(source=nid_req, target=nid_fe),
            TaskEdge(source=nid_req, target=nid_be),
            TaskEdge(source=nid_fe, target=nid_integ),
            TaskEdge(source=nid_be, target=nid_integ),
        ],
    )
    await store.save_task_graph(graph)

    # 3. Step 1: Ready wave should contain BOTH frontend and backend concurrently
    dag = ExecutableTaskDAG(graph)
    ready = dag.get_ready_nodes()
    ready_ids = [n.id for n in ready]
    assert nid_fe in ready_ids
    assert nid_be in ready_ids
    assert nid_integ not in ready_ids  # Node C must wait for both

    from unittest.mock import AsyncMock, patch

    from app.integrations.ai_universe_client import AIUniverseResponse

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = AIUniverseResponse(
            answer="def handle(): return True\n",
            confidence=0.95,
            run_id="run_parallel_orch",
        )
        # Execute wave 1 via orchestrator
        updated_task, executed_wave_1 = await orchestrator.step_task(task_id)
        assert len(executed_wave_1) == 2
        assert nid_fe in executed_wave_1
        assert nid_be in executed_wave_1

        # 4. Step 2: Now that both frontend and backend are completed, Integration is ready
        updated_task, executed_wave_2 = await orchestrator.step_task(task_id)
        assert len(executed_wave_2) == 1
        assert executed_wave_2[0] == nid_integ

        # 5. Step 3: All nodes complete -> Task transitions to COMPLETED
        updated_task, _executed_wave_3 = await orchestrator.step_task(task_id)
        assert updated_task.state == TaskState.COMPLETED
        assert updated_task.progress_percentage == 100
