"""TASK-FRG-012: the production DAG drain — regression tests.

Root cause (proven against production, 2026-11-16/17): Forge's Oracle
store bound ``task_graphs`` nodes/edges/goal JSON through SQLAlchemy's
``type_=CLOB`` bindparam path. Once a serialized graph passed the async
oracledb driver's direct-bind boundary (~32.7K chars — i.e. the first
post-wave save, once a node result is embedded), the value stored in
Oracle was binary garbage instead of the JSON text (Oracle-side proof:
``LENGTH`` <= 8,016 -> ``IS JSON`` = 1; >= 32,538 -> ``IS JSON`` = 0 for
every production row). The next step's load swallowed the parse failure
(``_loads`` -> ``{}``), producing a graph with zero nodes, and
``ExecutableTaskDAG.is_completed()`` is True for an empty node set — so
the task transitioned RUNNING -> COMPLETED after exactly one node, with
an empty provider summary. The SQLite test backend has no CLOB bind
path, which is why staging ran the same payloads to full DAGs.

These tests pin the three-part fix:

1. ``AsyncDbConnectionWrapper`` binds string CLOB values as chunked
   plain VARCHAR binds seeded with ``TO_CLOB`` — never via the
   corruption-prone typed temp-LOB path.
2. ``StateStore.get_task_graph`` parses nodes/edges strictly: a stored
   payload that is present but unparseable raises instead of silently
   becoming an empty graph.
3. ``OrchestratorCore.step_task`` refuses to run a graph with zero
   nodes, so no silent-empty load path can fake-complete a build again.
"""

from __future__ import annotations

import pytest

import pytest_asyncio

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.memory.db import AsyncDbConnectionWrapper
from app.memory.models import TaskEdge, TaskEntity, TaskGraph, TaskNode, TaskState
from app.memory.sqlite_test_backend import SQLiteTestDatabase
from app.memory.state_store import StateStore

GARBAGE = "\x01\x01\x01\x01\x00\x00\x00\x00binary-garbage-not-json"


@pytest_asyncio.fixture
async def state_store(temp_dir) -> StateStore:
    """StateStore over the test-only SQLite backend (the conftest
    ``state_store`` fixture predates the Oracle-only DatabaseManager)."""
    db = SQLiteTestDatabase(temp_dir / "frg012.db")
    await db.init_db()
    return StateStore(db)


# ---------------------------------------------------------------------------
# 1. Chunked CLOB binds (Oracle wrapper)
# ---------------------------------------------------------------------------


class _FakeResult:
    rowcount = 1


class _FakeConn:
    """Minimal stand-in for a SQLAlchemy AsyncConnection: records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params):
        self.calls.append((str(stmt), dict(params)))
        return _FakeResult()


async def _run_wrapper(query: str, params: dict, clob_params: tuple[str, ...]):
    conn = _FakeConn()
    wrapper = AsyncDbConnectionWrapper(conn)  # type: ignore[arg-type]
    await wrapper.execute(query, params, clob_params=clob_params)
    assert len(conn.calls) == 1
    return conn.calls[0]


@pytest.mark.asyncio
async def test_clob_value_over_boundary_is_chunked():
    value = "x" * 45_000
    sql, params = await _run_wrapper(
        "INSERT INTO task_graphs (id, nodes) VALUES (:id, :nodes)",
        {"id": "g1", "nodes": value},
        clob_params=("nodes",),
    )
    assert "TO_CLOB(:nodes__c0)" in sql
    assert "||" in sql
    assert "nodes" not in params  # original key replaced by chunk binds
    chunk_keys = sorted(k for k in params if k.startswith("nodes__c"))
    assert len(chunk_keys) == 57  # ceil(45000 / 800)
    assert all(len(params[k]) <= 800 for k in chunk_keys)
    reassembled = "".join(params[k] for k in chunk_keys)
    assert reassembled == value
    assert params["id"] == "g1"  # non-CLOB params untouched


@pytest.mark.asyncio
async def test_clob_small_value_single_chunk():
    value = '{"a": 1}'
    sql, params = await _run_wrapper(
        "UPDATE task_graphs SET nodes = :nodes WHERE id = :id",
        {"id": "g1", "nodes": value},
        clob_params=("nodes",),
    )
    assert sql.count("TO_CLOB(:nodes__c0)") == 1
    assert "||" not in sql
    assert params == {"id": "g1", "nodes__c0": value}


@pytest.mark.asyncio
async def test_clob_non_string_keeps_typed_bind():
    sql, params = await _run_wrapper(
        "UPDATE task_graphs SET nodes = :nodes WHERE id = :id",
        {"id": "g1", "nodes": None},
        clob_params=("nodes",),
    )
    assert ":nodes" in sql and "nodes__c0" not in sql
    assert params == {"id": "g1", "nodes": None}


@pytest.mark.asyncio
async def test_clob_rewrite_does_not_touch_prefixed_params():
    sql, params = await _run_wrapper(
        "UPDATE t SET nodes = :nodes, nodes_count = :nodes_count WHERE id = :id",
        {"id": "g1", "nodes": "abc", "nodes_count": 3},
        clob_params=("nodes",),
    )
    assert ":nodes_count" in sql
    assert params["nodes_count"] == 3
    assert params["nodes__c0"] == "abc"


@pytest.mark.asyncio
async def test_clob_rewrite_applies_to_every_occurrence():
    # The task_graphs MERGE references each CLOB bind once in its USING
    # clause; other statements (e.g. a plain UPDATE ... SET + a RETURNING
    # or a repeated reference) must be rewritten at every occurrence.
    sql, params = await _run_wrapper(
        "UPDATE t SET a = :payload WHERE b = :payload",
        {"payload": "y" * 900},
        clob_params=("payload",),
    )
    assert sql.count("TO_CLOB(:payload__c0)") == 2
    assert params["payload__c0"] + params["payload__c1"] == "y" * 900


# ---------------------------------------------------------------------------
# 2 + 3. Strict graph load and the step_task drain reproduction
# ---------------------------------------------------------------------------


def _graph(task_id: str, *, nodes: int = 2, big_result: bool = False) -> TaskGraph:
    graph = TaskGraph(project_id=task_id, goal="build a thing")
    previous: TaskNode | None = None
    for index in range(nodes):
        node = TaskNode(title=f"stage-{index}", assigned_agent="planner")
        if big_result and index == 0:
            node.result = {"spec": "s" * 45_000}
        if previous is not None:
            node.dependencies.append(previous.id)
            graph.edges.append(TaskEdge(source=previous.id, target=node.id))
        graph.nodes[node.id] = node
        previous = node
    return graph


async def _persist_task_and_graph(store: StateStore, temp_dir, graph: TaskGraph):
    task = TaskEntity(goal="build a thing", workspace_path=str(temp_dir))
    await store.create_task(task)
    graph.project_id = task.id
    await store.save_task_graph(graph)
    return task


async def _corrupt_stored_nodes(store: StateStore, graph_id: str) -> None:
    """Simulate the production CLOB corruption directly in the store."""
    async with store.db.connection() as conn:
        await conn.execute(
            "UPDATE task_graphs SET nodes = :nodes WHERE id = :id",
            {"nodes": GARBAGE, "id": graph_id},
        )
        await conn.commit()


def _orchestrator(store: StateStore, temp_dir) -> OrchestratorCore:
    settings = Settings()
    settings.base_dir = temp_dir
    settings.ensure_directories()
    return OrchestratorCore(store=store, wm=WorkspaceManager(settings=settings))


@pytest.mark.asyncio
async def test_get_task_graph_raises_on_corrupt_nodes(state_store: StateStore, temp_dir):
    graph = _graph("placeholder")
    task = await _persist_task_and_graph(state_store, temp_dir, graph)
    await _corrupt_stored_nodes(state_store, graph.id)

    with pytest.raises(ValueError, match="corrupt nodes payload"):
        await state_store.get_task_graph(graph.id)
    # The exact path step_task uses must fail the same way.
    with pytest.raises(ValueError, match="corrupt nodes payload"):
        await state_store.get_latest_task_graph_for_project(task.id)


@pytest.mark.asyncio
async def test_step_task_never_completes_on_corrupt_graph(
    state_store: StateStore, temp_dir
):
    """The drain reproduction: pre-fix, this exact setup transitioned the
    task to COMPLETED with zero further nodes dispatched."""
    graph = _graph("placeholder")
    task = await _persist_task_and_graph(state_store, temp_dir, graph)
    await _corrupt_stored_nodes(state_store, graph.id)

    orchestrator = _orchestrator(state_store, temp_dir)
    with pytest.raises(ValueError):
        await orchestrator.step_task(task.id)

    reloaded = await state_store.get_task(task.id)
    assert reloaded is not None
    assert reloaded.state != TaskState.COMPLETED


@pytest.mark.asyncio
async def test_step_task_refuses_empty_graph(state_store: StateStore, temp_dir):
    graph = _graph("placeholder", nodes=0)
    task = await _persist_task_and_graph(state_store, temp_dir, graph)

    orchestrator = _orchestrator(state_store, temp_dir)
    with pytest.raises(ValueError, match="contains no nodes"):
        await orchestrator.step_task(task.id)

    reloaded = await state_store.get_task(task.id)
    assert reloaded is not None
    assert reloaded.state != TaskState.COMPLETED


@pytest.mark.asyncio
async def test_large_graph_round_trips_through_store(
    state_store: StateStore, temp_dir
):
    """The store contract the Oracle chunked binds restore: a graph whose
    serialized nodes exceed the old ~32.7K corruption boundary must come
    back intact."""
    graph = _graph("placeholder", big_result=True)
    task = await _persist_task_and_graph(state_store, temp_dir, graph)

    loaded = await state_store.get_latest_task_graph_for_project(task.id)
    assert loaded is not None
    assert len(loaded.nodes) == 2
    first = next(iter(loaded.nodes.values()))
    assert first.result is not None
    assert len(first.result["spec"]) == 45_000
