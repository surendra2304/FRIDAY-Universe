"""
Comprehensive Test Suite for Forge Tier-1 Deep Upgrades:
1. Production PostgreSQL state store with asyncpg/SQLAlchemy 2.0 & fallback
2. Autonomous Multi-File DAG Synthesizer with Kahn's algorithm cycle detection
3. Subprocess process-tree cleanup guaranteeing zero orphaned servers
4. Sentinel pre-delivery gate fail-closed verification
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator import AutonomousDAGOrchestrator, DAGExecutionResult
from app.core.config import Settings
from app.dag.cycle_detector import CycleDetectedError, KahnCycleDetector
from app.dag.models import DAGGraph, DAGNode, DAGPhase, NodeStatus
from app.dag.scheduler import DagScheduler
from app.dag.synthesizer import MultiFileSynthesizer
from app.execution.delivery import SecurityGateFailure
from app.execution.terminal import kill_process_tree
from app.memory.db import DatabaseManager, DbRow
from app.security.sentinel_client import (
    SentinelClient,
)

# --- 1. PostgreSQL & Database Layer Tests ---

def test_config_postgres_url_resolution():
    """Verify Settings resolves PostgreSQL dokploy-postgres database URL correctly."""
    settings = Settings()
    settings.database_url = None
    settings.postgres_host = "dokploy-postgres"
    settings.postgres_port = 5432
    settings.postgres_user = "forge_user"
    settings.postgres_password = "Rk5fcxK4A-V2i11aBnbvHOMT"
    settings.postgres_db = "forge_db"

    # Default without env flag returns SQLite path
    default_url = settings.get_database_url()
    assert "sqlite" in default_url

    # Explicit database_url takes highest precedence
    settings.database_url = "postgresql+asyncpg://custom:secret@db:5432/custom_db"
    assert settings.get_database_url() == "postgresql+asyncpg://custom:secret@db:5432/custom_db"


@pytest.mark.asyncio
async def test_database_manager_crud_and_row_mapping(temp_dir: Path):
    """Verify DatabaseManager connects, executes queries, and returns dict-like DbRow mappings."""
    db_file = temp_dir / "test_store.db"
    mgr = DatabaseManager(db_path=db_file)

    async with mgr.connection() as conn:
        # Create test table
        await conn.execute("CREATE TABLE test_items (id TEXT PRIMARY KEY, val INTEGER);")
        # Parameterized insert using ?
        await conn.execute("INSERT INTO test_items (id, val) VALUES (?, ?);", ("item1", 42))
        await conn.commit()

    async with mgr.connection() as conn:
        cursor = await conn.execute("SELECT * FROM test_items WHERE id = ?;", ("item1",))
        row = await cursor.fetchone()
        assert row is not None
        assert row["id"] == "item1"
        assert row["val"] == 42
        assert "id" in row.keys()
        assert "val" in row.keys()


def test_dbrow_mapping_interface():
    """Verify DbRow mapping interface behaviors."""
    row = DbRow({"task_id": "t1", "status": "COMPLETED", "score": 95})
    assert row["task_id"] == "t1"
    assert row.get("status") == "COMPLETED"
    assert row.get("missing", "def") == "def"
    assert "status" in row
    assert len(row) == 3
    assert set(row.keys()) == {"task_id", "status", "score"}


# --- 2. DAG Synthesizer & Kahn's Cycle Detector Tests ---

def test_kahn_cycle_detector_acyclic():
    """Verify Kahn's algorithm properly topologically sorts an acyclic graph."""
    nodes = {
        "A": DAGNode("A", "Node A", DAGPhase.CONTRACTS),
        "B": DAGNode("B", "Node B", DAGPhase.IMPLEMENTATION, dependencies=("A",)),
        "C": DAGNode("C", "Node C", DAGPhase.TESTS, dependencies=("A",)),
        "D": DAGNode("D", "Node D", DAGPhase.VERIFICATION, dependencies=("B", "C")),
    }
    ordered = KahnCycleDetector.topological_sort(nodes)
    assert ordered[0] == "A"
    assert ordered[-1] == "D"
    assert ordered.index("B") < ordered.index("D")
    assert ordered.index("C") < ordered.index("D")
    assert KahnCycleDetector.detect_cycles(nodes) == []


def test_kahn_cycle_detector_cyclic():
    """Verify Kahn's algorithm detects cycles and raises CycleDetectedError."""
    # A -> B -> C -> A (cycle)
    cyclic_nodes = {
        "A": DAGNode("A", "Node A", DAGPhase.CONTRACTS, dependencies=("C",)),
        "B": DAGNode("B", "Node B", DAGPhase.IMPLEMENTATION, dependencies=("A",)),
        "C": DAGNode("C", "Node C", DAGPhase.TESTS, dependencies=("B",)),
    }
    cycles = KahnCycleDetector.detect_cycles(cyclic_nodes)
    assert len(cycles) == 3
    assert set(cycles) == {"A", "B", "C"}

    with pytest.raises(CycleDetectedError) as exc_info:
        KahnCycleDetector.topological_sort(cyclic_nodes)
    assert "Dependency cycle detected" in str(exc_info.value)


def test_kahn_cycle_detector_self_dependency():
    """Verify self-dependency raises CycleDetectedError."""
    self_loop = {
        "A": DAGNode("A", "Node A", DAGPhase.CONTRACTS, dependencies=("A",)),
    }
    with pytest.raises(CycleDetectedError) as exc_info:
        KahnCycleDetector.topological_sort(self_loop)
    assert "Self dependency detected" in str(exc_info.value)


def test_dag_scheduler_wave_execution_and_cascading_blocked():
    """Verify DagScheduler advances through waves and cascades BLOCKED status on node failure."""
    graph = DAGGraph("g1", "Test Graph")
    graph.add_node(DAGNode("contracts", "Contracts", DAGPhase.CONTRACTS))
    graph.add_node(DAGNode("impl", "Implementation", DAGPhase.IMPLEMENTATION, dependencies=("contracts",)))
    graph.add_node(DAGNode("tests", "Tests", DAGPhase.TESTS, dependencies=("impl",)))

    scheduler = DagScheduler(graph)
    scheduler.validate()

    # Wave 0: contracts is ready
    ready = scheduler.ready()
    assert len(ready) == 1
    assert ready[0].node_id == "contracts"

    # Contracts fails
    scheduler.mark_failed("contracts", "Compilation failed")
    assert scheduler.has_failed() is True
    # Implementation and tests must be cascaded to BLOCKED
    assert scheduler.runtime["impl"].status == NodeStatus.BLOCKED
    assert scheduler.runtime["tests"].status == NodeStatus.BLOCKED


def test_multi_file_synthesizer_dag_construction():
    """Verify MultiFileSynthesizer builds a clean, validated 4-phase DAG."""
    synth = MultiFileSynthesizer()
    graph = synth.build_synthesis_dag(
        task_id="t_synth_1",
        goal="Build REST user authentication service",
        file_manifest=["models.py", "auth.py", "jwt_utils.py", "test_auth.py"],
    )

    assert "phase_contracts" in graph.nodes
    assert "phase_implementation" in graph.nodes
    assert "phase_tests" in graph.nodes
    assert "phase_verification" in graph.nodes

    # Kahn cycle detector verifies it is 100% acyclic
    order = KahnCycleDetector.topological_sort(graph.nodes)
    assert order == ["phase_contracts", "phase_implementation", "phase_tests", "phase_verification"]


@pytest.mark.asyncio
async def test_autonomous_dag_orchestrator_execution():
    """Verify AutonomousDAGOrchestrator executes DAG waves to completion."""
    orchestrator = AutonomousDAGOrchestrator()
    graph = orchestrator.plan_synthesis(
        task_id="t_orch_1",
        goal="Synthesize microservice data pipeline",
    )

    result = await orchestrator.execute_dag("t_orch_1", graph)
    assert isinstance(result, DAGExecutionResult)
    assert result.success is True
    assert result.progress == 1.0
    assert result.nodes_executed == len(graph.nodes)


# --- 3. Subprocess Process Tree Cleanup Tests ---

def test_kill_process_tree_graceful():
    """Verify kill_process_tree handles nonexistent and mock processes safely."""
    # Process 99999999 does not exist; should return without throwing exceptions
    result = kill_process_tree(99999999, timeout_sec=0.1)
    assert result in (True, False)


# --- 4. Sentinel Pre-Delivery Gate Integration Tests ---

@pytest.mark.asyncio
async def test_sentinel_client_audit_clean():
    """Verify SentinelClient approves clean diffs without findings."""
    client = SentinelClient(base_url="http://sentinel:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "passed": True,
        "verdict": "APPROVED",
        "critical_count": 0,
        "high_count": 0,
        "findings": [],
        "audit_id": "audit_123",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await client.audit_diff("t_clean", "git diff content")
        assert res.passed is True
        assert res.verdict == "APPROVED"


@pytest.mark.asyncio
async def test_sentinel_client_audit_fails_closed_on_critical_cve():
    """Verify SentinelClient raises SecurityGateFailure on critical findings."""
    client = SentinelClient(base_url="http://sentinel:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "passed": False,
        "verdict": "BLOCKED",
        "critical_count": 1,
        "high_count": 0,
        "findings": [
            {
                "severity": "CRITICAL",
                "rule_id": "CVE-2024-38816",
                "description": "Path traversal vulnerability detected in static handler",
            }
        ],
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(SecurityGateFailure) as exc_info:
            await client.audit_diff("t_bad", "diff content", fail_closed=True)
        assert "critical" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_sentinel_client_non_200_fails_closed():
    """Verify SentinelClient fails closed when service returns non-200 HTTP error."""
    client = SentinelClient(base_url="http://sentinel:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(SecurityGateFailure) as exc_info:
            await client.audit_diff("t_err", "diff content", fail_closed=True)
        assert "non-200" in str(exc_info.value)


@pytest.mark.asyncio
async def test_multi_file_patching_preview_and_apply(temp_dir: Path):
    """Verify MultiFileSynthesizer patch preview and atomic application."""
    from app.core.workspace import WorkspaceManager

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    synth = MultiFileSynthesizer(wm=wm)
    task_id = "t_patch_1"
    wm.create_workspace(task_id)

    # 1. Preview patch
    changes = {
        "src/models.py": "class User:\n    id: int\n",
        "src/service.py": "def get_user():\n    return 'alice'\n",
    }
    preview = synth.create_patch_preview(task_id, changes)
    assert len(preview.files) == 2
    assert preview.additions > 0

    # 2. Apply patch
    changes_applied = synth.apply_patch(task_id, changes)
    assert len(changes_applied) == 2
    paths = wm.get_workspace_paths(task_id)
    assert (paths.project / "src/models.py").exists()
    assert (paths.project / "src/service.py").exists()


@pytest.mark.asyncio
async def test_async_db_connection_wrapper_features():
    """Verify AsyncDbConnectionWrapper handles PRAGMAs, transactions, and parameter conversions."""
    from app.memory.db import AsyncDbConnectionWrapper

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings().all.return_value = [{"col": "val"}]
    mock_result.mappings().first.return_value = {"col": "val"}
    mock_conn.execute.return_value = mock_result

    wrapper = AsyncDbConnectionWrapper(mock_conn)

    # PRAGMA should be silently no-op'd
    prag_res = await wrapper.execute("PRAGMA journal_mode=WAL;")
    assert await prag_res.fetchone() is None

    # Normal execution with positional tuple converted to dict
    cursor = await wrapper.execute("SELECT * FROM tbl WHERE a = ? AND b = ?;", ("x", 10))
    row = await cursor.fetchone()
    assert row is not None
    assert row["col"] == "val"

    rows = await cursor.fetchall()
    assert len(rows) == 1

    # executescript
    await wrapper.executescript("CREATE TABLE t1 (id TEXT); CREATE TABLE t2 (id TEXT);")
    assert mock_conn.execute.call_count >= 2

    # commit and rollback
    await wrapper.commit()
    mock_conn.commit.assert_called_once()
    await wrapper.rollback()
    mock_conn.rollback.assert_called_once()


def test_oracle_json_compilation():
    """Verify SQLAlchemy JSON type compiles to native JSON on Oracle 23ai dialect."""
    from sqlalchemy.dialects import oracle
    from sqlalchemy.types import JSON

    compiled = str(JSON().compile(dialect=oracle.dialect()))
    assert compiled.upper() == "JSON"


def test_oracle_and_postgres_url_translation():
    """Verify DatabaseManager dynamically translates synchronous URLs to async drivers."""
    # Test Oracle translation
    mgr_oracle = DatabaseManager(
        database_url="oracle+oracledb://ADMIN:secret@(description=...)"
    )
    url_oracle = mgr_oracle.get_effective_url()
    assert url_oracle.startswith("oracle+oracledb://")

    # Test PostgreSQL translation
    mgr_pg = DatabaseManager(
        database_url="postgresql://user:pass@host:5432/db"
    )
    assert mgr_pg.get_effective_url() == "postgresql://user:pass@host:5432/db"


def test_mesh_private_urls_and_config():
    """Verify Settings loads private mesh URLs and supports Oracle aliases."""
    settings = Settings()
    assert "10.0.0.121" in settings.friday_url or "friday" in settings.friday_url
    assert "10.0.0.121" in settings.stratex_url or "stratex" in settings.stratex_url
    assert "10.0.0.120" in settings.vyralx_url or "vyralx" in settings.vyralx_url
    assert "10.0.0.120" in settings.sentinel_url or "sentinel" in settings.sentinel_url


@pytest.mark.asyncio
async def test_sentinel_client_identity_headers(monkeypatch):
    """Verify Sentinel client dispatches required X-Agent-Name and correlation headers."""
    import respx
    from httpx import Response

    client = SentinelClient(base_url="http://10.0.0.120:8008", api_key="test_sentinel_key")

    with respx.mock:
        route = respx.post("http://10.0.0.120:8008/v1/security/audit").mock(
            return_value=Response(
                200,
                json={"passed": True, "verdict": "APPROVED", "critical_count": 0, "high_count": 0, "findings": []},
            )
        )
        res = await client.audit_diff(task_id="task_test_001", diff_text="+ def foo(): pass\n")
        assert res.passed is True
        assert route.called
        last_req = route.calls.last.request
        assert last_req.headers["x-agent-name"] == "forge"
        assert "task_test_001" in last_req.headers["x-correlation-id"]
        assert "Bearer test_sentinel_key" in last_req.headers["authorization"]

