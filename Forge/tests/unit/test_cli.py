"""
Unit tests for FORGE Standalone CLI MVP.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.cli import (
    handle_build,
    handle_cancel,
    handle_inspect,
    handle_logs,
    handle_pause,
    handle_resume,
    handle_status,
)
from app.memory.db import DatabaseManager
from app.memory.models import TaskState
from app.memory.state_store import StateStore


@pytest.mark.asyncio
async def test_cli_build_and_status(temp_dir: Path, isolated_db_manager: DatabaseManager):
    # app.cli's handlers (handle_build, handle_status, ...) go through the
    # real global app.cli.db_manager / orchestrator / workspace_manager
    # singletons. isolated_db_manager (tests/conftest.py) redirects all of
    # those -- db_manager bindings across every module that imports it, plus
    # the shared Settings singleton's base_dir -- into a temp directory for
    # the duration of this test, so running it never touches the real
    # data/forge.db or workspaces/ directory on disk.
    db_manager = isolated_db_manager
    await db_manager.init_db()

    goal = "Create a minimal CLI todo tool"
    requirements = ["Add items", "List items"]

    from unittest.mock import AsyncMock, patch

    from app.integrations.ai_universe_client import AIUniverseResponse

    mock_resp = AIUniverseResponse(
        answer='"""Generated CLI."""\ndef main():\n    print("CLI operational")\n    return 0\n',
        confidence=0.95,
        run_id="run_cli_test",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_resp
        # Run CLI build handler
        built_task = await handle_build(goal=goal, requirements=requirements, max_budget=10.0)

    assert built_task is not None
    assert built_task.goal == goal

    # Verify task was created and stored
    store = StateStore(db_manager)
    task = await store.get_task(built_task.id)
    assert task is not None
    assert task.goal == goal

    # Test status handler
    await handle_status(task.id)

    # Test inspect handler
    await handle_inspect(task.id)

    # Test logs handler
    await handle_logs(task.id)


@pytest.mark.asyncio
async def test_cli_pause_resume_cancel(temp_dir: Path, isolated_db_manager: DatabaseManager):
    db_manager = isolated_db_manager
    await db_manager.init_db()
    store = StateStore(db_manager)

    task_id = str(uuid4())
    from app.memory.models import TaskEntity

    task = TaskEntity(
        id=task_id,
        goal="CLI Control Flow Test",
        workspace_path=f"/workspaces/task_{task_id}",
        state=TaskState.PENDING,
    )
    await store.create_task(task)

    # Pause
    await handle_pause(task_id, reason="Manual pause")
    t_paused = await store.get_task(task_id)
    assert t_paused.state == TaskState.BLOCKED

    # Resume
    await handle_resume(task_id, reason="Manual resume")
    t_resumed = await store.get_task(task_id)
    assert t_resumed.state == TaskState.RUNNING

    # Cancel
    await handle_cancel(task_id, reason="Manual cancel")
    t_cancelled = await store.get_task(task_id)
    assert t_cancelled.state == TaskState.CANCELLED
