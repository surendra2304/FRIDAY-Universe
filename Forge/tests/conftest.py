"""
Pytest fixtures and configuration for FORGE test suite.
"""

import shutil
import sys
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.main import create_app
from app.memory.db import DatabaseManager
from app.memory.state_store import StateStore
from app.providers.direct import DirectProvider


@pytest.fixture
def temp_dir() -> Path:
    """Provide an isolated temporary directory for test storage."""
    d = tempfile.mkdtemp(prefix="forge_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest_asyncio.fixture
async def test_db_manager(temp_dir: Path) -> DatabaseManager:
    """Initialize a clean temporary SQLite database manager."""
    db_path = temp_dir / "test_forge.db"
    manager = DatabaseManager(db_path=db_path)
    await manager.init_db()
    return manager


@pytest_asyncio.fixture
async def state_store(test_db_manager: DatabaseManager) -> StateStore:
    """Provide a StateStore bound to the temporary test database."""
    return StateStore(test_db_manager)


# Every module below does `from app.memory.db import db_manager` at import
# time, creating its own independent binding to the real, process-wide
# `app.memory.db.db_manager` singleton (which points at the real
# data/forge.db on disk by default). Tests that exercise code paths going
# through app.cli, the orchestrator, recovery engine, etc. -- rather than
# going through the `async_client`/`routes_module` override above -- were
# silently reading and writing the real development database instead of an
# isolated one, so running the test suite could corrupt or be corrupted by
# whatever tasks a developer had created locally, and tests run in different
# orders could see each other's leftover rows.
_DB_MANAGER_BINDING_MODULES = [
    "app.analytics.task_analytics",
    "app.api.tasks",
    "app.api.health",
    "app.api.routes",
    "app.backup.recovery",
    "app.cli",
    "app.core.orchestrator",
    "app.improvement.self_improve",
    "app.main",
    "app.memory",
    "app.memory.state_store",
    "app.optimization.performance",
    "app.recovery.engine",
]


@pytest_asyncio.fixture
async def isolated_db_manager(
    monkeypatch: pytest.MonkeyPatch, test_db_manager: DatabaseManager, temp_dir: Path
) -> DatabaseManager:
    """Redirect every module-level `db_manager` binding (and the shared
    `Settings` singleton's filesystem paths) to an isolated, temp-file-backed
    database for the duration of a test.

    Use this instead of importing `app.memory.db.db_manager` directly in any
    test that calls into `app.cli`, `app.core.orchestrator`, or other code
    relying on the ambient global singleton, so the test never touches the
    real development database or workspace directory on disk.
    """
    import importlib

    for mod_name in _DB_MANAGER_BINDING_MODULES:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "db_manager"):
            monkeypatch.setattr(mod, "db_manager", test_db_manager, raising=False)

    # Patching the module-level `db_manager` *name* is not enough on its
    # own: a handful of process-wide singletons (app.core.orchestrator's
    # `orchestrator`, app.recovery.engine's `recovery_engine`) build
    # `self.store = StateStore(db_manager)` exactly once, at import time,
    # and keep that StateStore (bound to the *original* db_manager object)
    # for the lifetime of the process. Re-pointing the module attribute
    # afterwards does nothing to an object that already captured the old
    # reference -- confirmed live: app.cli.handle_build() goes through
    # `orchestrator.intake_and_plan()`/`run_task()`, which wrote the task to
    # the real data/forge.db even with the module patch above in place,
    # while the test's own freshly constructed `StateStore(db_manager)`
    # looked for it in the isolated temp database and got None. Each
    # long-lived singleton's `.store` must be repointed directly.
    orchestrator_module = importlib.import_module("app.core.orchestrator")
    monkeypatch.setattr(
        orchestrator_module.orchestrator, "store", StateStore(test_db_manager), raising=False
    )
    monkeypatch.setattr(
        orchestrator_module.orchestrator.lifecycle,
        "store",
        orchestrator_module.orchestrator.store,
        raising=False,
    )
    recovery_module = importlib.import_module("app.recovery.engine")
    monkeypatch.setattr(
        recovery_module.recovery_engine, "store", StateStore(test_db_manager), raising=False
    )

    # `base_dir` is the root every other relative Settings path (data_dir,
    # database_path, workspaces_dir, artifacts_dir) is joined against, and
    # `get_settings()`/`workspace_manager`/`orchestrator` all share one
    # lru_cache'd Settings singleton -- redirecting `base_dir` alone
    # redirects all of them into the isolated temp directory at once.
    settings = get_settings()
    monkeypatch.setattr(settings, "base_dir", temp_dir)
    settings.ensure_directories()

    return test_db_manager


@pytest.fixture
def direct_provider() -> DirectProvider:
    """Provide a standard DirectProvider."""
    return DirectProvider(model_name="test-direct")


@pytest_asyncio.fixture
async def async_client(
    test_db_manager: DatabaseManager, temp_dir: Path
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient configured with overridden database and workspace paths."""
    from app.api import routes as routes_module
    from app.memory import db as db_module

    app = create_app()

    original_manager = db_module.db_manager
    db_module.db_manager = test_db_manager
    routes_module.db_manager = test_db_manager

    def get_test_settings() -> Settings:
        settings = Settings()
        settings.workspaces_dir = temp_dir / "workspaces"
        settings.data_dir = temp_dir / "data"
        settings.database_path = temp_dir / "test_forge.db"
        settings.ensure_directories()
        return settings

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[routes_module.get_state_store] = lambda: StateStore(test_db_manager)
    app.dependency_overrides[routes_module.get_orchestrator] = lambda: OrchestratorCore(
        store=StateStore(test_db_manager),
        wm=WorkspaceManager(settings=get_test_settings()),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    db_module.db_manager = original_manager
    routes_module.db_manager = original_manager
