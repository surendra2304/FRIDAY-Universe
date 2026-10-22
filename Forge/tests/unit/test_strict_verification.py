"""
Unit tests for strict objective verification, fallback stub detection, and FAILED task state enforcement.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.roles import DeveloperRole
from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.models import TaskEntity, TaskState
from app.memory.state_store import StateStore
from app.verification.checkers import FeaturePresenceChecker


@pytest.fixture
def temp_engine(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return engine, wm


@pytest.mark.asyncio
async def test_developer_role_flags_fallback_stub_when_nothing_can_be_built(temp_engine):
    """The stub flag is the honesty guarantee: it must still fire when the agent
    genuinely cannot produce the file it was asked for.

    This test used to drive any AI failure into the stub path. That is no longer
    the whole story -- with the deterministic synthesiser in place, a goal the
    agent understands is built for real instead of stubbed. The contract under
    test here is the one that still matters and is easy to get wrong: a manifest
    entry that nobody could deliver must be reported, not quietly dropped. The
    manifest therefore asks for files no Python synthesiser produces, so the
    fallback path is exercised exactly as before.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask",
        side_effect=RuntimeError("AI Universe offline"),
    ):
        context = {
            "goal": "Build a static portfolio website",
            "file_manifest": ["app.rb", "config.yaml"],
        }
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Codebase",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        assert result["fallback_stub"] is True
        assert "app.rb" in result["fallback_files"]
        assert "config.yaml" in result["fallback_files"]

        # Check state file on disk
        paths = wm.get_workspace_paths(task_id)
        fallback_file = paths.state / "FALLBACK_STUB.json"
        assert fallback_file.exists()


@pytest.mark.asyncio
async def test_developer_role_builds_real_code_when_ai_is_unavailable(temp_engine):
    """With no model provider reachable the agent must still build working code.

    Every AI endpoint was unreachable when this was written, and the agent
    produced zero Python files while verification scored it 9/10. The
    deterministic synthesiser is the fix; this test pins it down -- the files
    exist, they compile, and they are not placeholder stubs.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask",
        side_effect=RuntimeError("AI Universe offline"),
    ):
        context = {
            "goal": (
                "Create a Python CLI note-taking app with add, list and delete "
                "commands storing notes in a local JSON file"
            ),
            "file_manifest": ["main.py"],
        }
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Codebase",
            context=context,
            engine=engine,
        )

    assert result["status"] == "success"
    assert result["fallback_stub"] is False, result["fallback_files"]
    assert "main.py" in result["files_written"]

    paths = wm.get_workspace_paths(task_id)
    main_py = paths.project / "main.py"
    assert main_py.exists(), "synthesiser wrote nothing"
    source = main_py.read_text(encoding="utf-8")
    compile(source, "main.py", "exec")

    # Real code, not a placeholder.
    assert "argparse" in source
    assert "add" in source and "list" in source and "delete" in source
    assert "Fell back to stub" not in source
    assert not (paths.state / "FALLBACK_STUB.json").exists()


@pytest.mark.asyncio
async def test_orchestrator_sets_failed_state_when_fallback_stub_occurs(tmp_path: Path):
    """Validates OrchestratorCore marks final TaskState as FAILED when fallback stub is used."""
    db_file = tmp_path / "test_store.db"
    db_manager = DatabaseManager(db_path=db_file)
    await db_manager.init_db()

    store = StateStore(db_manager)
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)

    engine = ExecutionEngine(wm=wm)
    engine.store = store
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    # Force AI Universe to fail so Developer falls back
    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask",
        side_effect=RuntimeError("AI Universe offline"),
    ):
        task, _ = await orchestrator.intake_and_plan(
            goal="Build a FastAPI backend service with SQLite database",
        )

        # Run task to completion
        final_task = await orchestrator.run_task(task.id, max_iterations=10)

        # A goal the synthesiser understands is now built for real, so the task
        # completes instead of failing. The FAILED contract is still enforced --
        # see test_orchestrator_fails_when_nothing_can_be_built below, which uses
        # a manifest no synthesiser can deliver.
        assert final_task.state == TaskState.COMPLETED, final_task.error_message
        assert "Fell back to stub generation" not in (final_task.error_message or "")


@pytest.mark.asyncio
async def test_orchestrator_fails_when_nothing_can_be_built(tmp_path: Path):
    """The FAILED contract: nothing real built means the task must not succeed.

    The orchestrator used to fail on any AI outage. It now fails only when it
    genuinely could not deliver the manifest, which is the behaviour worth
    pinning: never report success for a project that does not exist.
    """
    db_file = tmp_path / "test_store.db"
    db_manager = DatabaseManager(db_path=db_file)
    await db_manager.init_db()

    store = StateStore(db_manager)
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)

    engine = ExecutionEngine(wm=wm)
    engine.store = store
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    # Simulate an agent with no synthesis capability at all: no provider can
    # author code and the deterministic synthesiser produces nothing. This is the
    # "nothing real was built" case the FAILED state exists for.
    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask",
        side_effect=RuntimeError("AI Universe offline"),
    ), patch(
        "app.agents.synthesis.synthesize_files_for_goal", return_value={}
    ):
        task, _ = await orchestrator.intake_and_plan(
            goal="Build a FastAPI backend service with SQLite database",
        )
        final_task = await orchestrator.run_task(task.id, max_iterations=10)

    assert final_task.state in (TaskState.FAILED, TaskState.BLOCKED)
    assert "Fell back to stub generation" in (final_task.error_message or "")


@pytest.mark.asyncio
async def test_feature_presence_checker_fails_when_features_missing(temp_engine):
    """Validates FeaturePresenceChecker fails when requested features (FastAPI, dark mode, hero) are missing."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Create dummy files without requested features
    engine.fs.create_file(
        task_id=task_id,
        relative_path="main.py",
        content='"""Generated by FORGE Autonomous Engine."""\nimport sys\ndef main():\n    print("Running: Build FastAPI")\n    return 0\n',
        role="developer",
    )

    # Set task goal in mock store
    mock_task = TaskEntity(
        id=task_id,
        goal="Build a FastAPI backend with SQLite",
        workspace_path=str(wm.get_task_workspace_dir(task_id)),
    )
    engine.store = AsyncMock()
    engine.store.get_task.return_value = mock_task

    checker = FeaturePresenceChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is False
    assert evidence.exit_code == 1
    assert any("FastAPI" in issue.get("error", "") for issue in evidence.issues)
    assert any("placeholder stub" in issue.get("error", "") for issue in evidence.issues)


@pytest.mark.asyncio
async def test_feature_presence_checker_passes_when_features_present(temp_engine):
    """Validates FeaturePresenceChecker passes when requested features are actually implemented."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Create actual FastAPI implementation
    engine.fs.create_file(
        task_id=task_id,
        relative_path="main.py",
        content="""from fastapi import FastAPI
import sqlite3

app = FastAPI(title="Portfolio API")

@app.get("/")
def read_root():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
    return {"message": "Database ready"}
""",
        role="developer",
    )

    mock_task = TaskEntity(
        id=task_id,
        goal="Build a FastAPI backend with SQLite database",
        workspace_path=str(wm.get_task_workspace_dir(task_id)),
    )
    engine.store = AsyncMock()
    engine.store.get_task.return_value = mock_task

    checker = FeaturePresenceChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert len(evidence.issues) == 0
