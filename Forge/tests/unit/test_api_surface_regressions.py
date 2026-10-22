"""
Regression tests for the API-surface defects found in the 2026-10 audit.

Bug #2   Every core endpoint (task create/get/pause/resume/timeline, artifacts,
         projects) 404'd under /api because `api_router` was mounted only at ""
         and /api/v1. The dashboard's Timeline tab and lifecycle buttons were
         permanently dead.

Bug #5   `GET /api/tasks` applied `since_timestamp` and `include_archived`
         *after* the store-level LIMIT, so `limit=3` + `since=now-2h` returned
         the three newest tasks (all outside the window) instead of the tasks
         that actually matched.

Bug #6   `GET /api/tasks/{id}` reported `checkpoints[0]` -- step 1 -- as
         `latest_checkpoint_id` while the /api/v1 twin reported
         `checkpoints[-1]`, so the two endpoints disagreed forever.

Bug #4   `POST /api/tasks/from-template/{id}` built its workspace from the raw
         relative `settings.workspaces_dir` (CWD-dependent), wrote files into the
         workspace root instead of `project/`, and never validated `rel_path`.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api.marketplace import BuildFromTemplateRequest, build_task_from_template
from app.core.config import Settings
from app.core.workspace import WorkspaceManager, canonical_path
from app.main import create_app
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore

# ---------------------------------------------------------------------------
# Bug #2 -- /api prefix must expose the core endpoints
# ---------------------------------------------------------------------------


def test_core_endpoints_exist_under_api_prefix():
    from app.main import create_app as _create

    app = _create()
    paths = app.openapi()["paths"]
    expected = [
        "/api/tasks",
        "/api/tasks/{task_id}",
        "/api/tasks/{task_id}/pause",
        "/api/tasks/{task_id}/resume",
        "/api/tasks/{task_id}/timeline",
        "/api/tasks/{task_id}/cancel",
        "/api/artifacts/{artifact_id}",
        "/api/projects",
    ]
    missing = [p for p in expected if p not in paths]
    assert not missing, f"endpoints missing under /api: {missing}"


def test_pause_and_resume_endpoints_reach_the_handler(tmp_path, monkeypatch):
    """A 404 from the handler (task not found) proves routing works; a 404 from
    the router (route absent) is the original bug."""
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.data_dir = tmp_path / "data"
    settings.database_path = tmp_path / "data" / "forge.db"
    settings.ensure_directories()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.api.routes.workspace_manager", WorkspaceManager(settings=settings)
    )

    app = create_app()
    with TestClient(app) as client:
        for method, url in (
            ("post", "/api/tasks/does-not-exist/pause"),
            ("post", "/api/tasks/does-not-exist/resume"),
            ("get", "/api/tasks/does-not-exist/timeline"),
        ):
            resp = getattr(client, method)(url)
            assert resp.status_code == 404, f"{method.upper()} {url} -> {resp.status_code}"
            assert resp.json()["detail"] != "Not Found", (
                f"{method.upper()} {url} is not routed (bug #2 regressed)"
            )


async def test_api_tasks_post_uses_the_tasks_router_handler(tmp_path, monkeypatch, isolated_db_manager):
    """The two routers overlap on POST /tasks; the richer one must win.

    api_router.create_task drops `task_metadata`; tasks_router.create_task keeps
    it. Mounting order decides which handler answers, so pin the contract.

    This used to hand-roll its own isolation by monkeypatching the
    `get_settings` *function* and a handful of named `db_manager` bindings,
    but missed that `workspace_manager`/`orchestrator` (app.core.workspace,
    app.core.orchestrator) are long-lived singletons that captured the
    *original* `get_settings()` object's attributes at import time --
    replacing the function didn't change what those singletons already held,
    so `POST /api/tasks` here actually created a real task row+workspace
    under the real data/forge.db and workspaces/ in the repo checkout
    (confirmed live: a stray `workspaces/task<timestamp>` directory was left
    behind after every test run). `isolated_db_manager` (tests/conftest.py)
    mutates the shared Settings singleton's `base_dir` attribute in place,
    which both `workspace_manager` and `orchestrator` resolve their on-disk
    paths from dynamically, so it actually takes effect.
    """
    await isolated_db_manager.init_db()

    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/api/tasks",
            json={
                "goal": "Build a responsive landing page",
                "task_metadata": {"source": "client_app", "priority": "high"},
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["metadata"]["source"] == "client_app", (
            "POST /api/tasks is served by api_router.create_task, which drops task_metadata"
        )


def test_openapi_operation_ids_are_unique():
    """Bug #23: multi-mounted routers produced duplicate OpenAPI operationIds."""
    app = create_app()
    schema = app.openapi()
    ids = [
        op["operationId"]
        for item in schema["paths"].values()
        for op in item.values()
        if isinstance(op, dict)
    ]
    assert ids, "no operations found"
    assert len(ids) == len(set(ids)), (
        f"duplicate operationIds: {sorted({i for i in ids if ids.count(i) > 1})}"
    )


# ---------------------------------------------------------------------------
# Bug #5 -- filters must be applied before the LIMIT
# ---------------------------------------------------------------------------


async def _seed_tasks(store: StateStore, count: int = 5) -> list[str]:
    """Create `count` tasks aged 0..count-1 hours, oldest first."""
    from app.memory.models import TaskEntity

    now = datetime.now(timezone.utc)
    ids = []
    for i in range(count):
        task_id = f"task{i}"
        aged = now - timedelta(hours=count - 1 - i)
        await store.create_task(
            TaskEntity(
                id=task_id,
                goal=f"goal {i}",
                requirements=[],
                mode=TaskMode.AUTONOMOUS,
                workspace_path=f"/tmp/{task_id}",
                max_budget=10.0,
                state=TaskState.PENDING,
                metadata={"archived": (i % 2 == 0)},
                created_at=aged,
                updated_at=aged,
            )
        )
        ids.append(task_id)
    return ids


@pytest_asyncio.fixture
async def store(test_db_manager):
    """StateStore bound to a clean temporary database (see conftest)."""
    yield StateStore(test_db_manager)


async def test_list_tasks_since_timestamp_applied_before_limit(store: StateStore):
    """limit=3 + since=now-2h must return the two tasks inside the window."""
    await _seed_tasks(store, count=5)
    since = datetime.now(timezone.utc) - timedelta(hours=2)

    # Store level: the SQL filter must run before LIMIT.
    recent = await store.list_tasks(limit=3, since_timestamp=since)
    assert [t.id for t in recent] == ["task4", "task3"], (
        f"since_timestamp applied after LIMIT: got {[t.id for t in recent]}"
    )


async def test_list_tasks_endpoint_respects_since_and_limit(monkeypatch, test_db_manager):
    from app.api.tasks import list_tasks

    monkeypatch.setattr("app.api.tasks.db_manager", test_db_manager)

    store = StateStore(test_db_manager)
    await _seed_tasks(store, count=5)
    since = datetime.now(timezone.utc) - timedelta(hours=2)

    summaries = await list_tasks(status=None, limit=3, since_timestamp=since,
                                 include_archived=True, store=store)
    assert [s.id for s in summaries] == ["task4", "task3"]

    # Archived filtering must not silently starve the result set either.
    live = await list_tasks(status=None, limit=3, since_timestamp=since,
                            include_archived=False, store=store)
    assert [s.id for s in live] == ["task3"], (
        f"include_archived=False dropped a matching task: {[s.id for s in live]}"
    )



# ---------------------------------------------------------------------------
# Bug #6 -- latest_checkpoint_id must agree between mounts
# ---------------------------------------------------------------------------


async def test_latest_checkpoint_id_is_the_newest_checkpoint(
    tmp_path, monkeypatch, test_db_manager
):
    from app.api.tasks import get_task

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    monkeypatch.setattr(
        "app.api.tasks.workspace_manager", WorkspaceManager(settings=settings)
    )
    monkeypatch.setattr("app.api.tasks.db_manager", test_db_manager)

    store = StateStore(test_db_manager)
    task_id = "task_cp_order"
    from app.memory.models import TaskEntity

    await store.create_task(
        TaskEntity(
            id=task_id,
            goal="checkpoint ordering",
            requirements=[],
            mode=TaskMode.AUTONOMOUS,
            workspace_path="/tmp/x",
            max_budget=1.0,
            state=TaskState.PENDING,
        )
    )
    from app.memory.models import Checkpoint

    for step in (1, 2, 3):
        await store.save_checkpoint(
            Checkpoint(
                project_id=task_id,
                task_id=task_id,
                step_number=step,
                state_data={"step": step},
                description=f"step {step}",
            )
        )

    detail = await get_task(task_id, store=store)
    checkpoints = await store.list_checkpoints(task_id)
    assert len(checkpoints) == 3
    assert detail.latest_checkpoint_id == checkpoints[-1].id, (
        "latest_checkpoint_id must be the highest step_number, not the first row"
    )
    assert detail.latest_checkpoint_id != checkpoints[0].id


# ---------------------------------------------------------------------------
# Bug #4 -- from-template must write inside <root>/project with containment
# ---------------------------------------------------------------------------


async def test_from_template_writes_into_project_subdir(tmp_path, monkeypatch):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    monkeypatch.setattr(
        "app.api.marketplace.workspace_manager", WorkspaceManager(settings=settings)
    )

    resp = await build_task_from_template("portfolio-web", BuildFromTemplateRequest())
    root = Path(resp.workspace_path)
    project = root / "project"

    assert project.is_dir(), f"files were not written under {project}"
    assert resp.files_created, "no files reported"
    for rel in resp.files_created:
        assert (project / rel).is_file(), f"{rel} missing from the project sandbox"
    # The workspace root must be anchored to base_dir, not the process CWD.
    assert canonical_path(root) == canonical_path(
        settings.base_dir / settings.workspaces_dir / resp.task_id
    ), "workspace root is not anchored to settings.base_dir"


async def test_from_template_rejects_escaping_rel_paths(tmp_path, monkeypatch):
    from fastapi import HTTPException

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    monkeypatch.setattr(
        "app.api.marketplace.workspace_manager", WorkspaceManager(settings=settings)
    )

    from app.marketplace import registry as registry_mod

    original = registry_mod.template_registry.render_template

    def hostile(template_id, variables):
        files = dict(original(template_id, variables))
        files["../../escaped.txt"] = "pwned"
        return files

    monkeypatch.setattr(registry_mod.template_registry, "render_template", hostile)

    with pytest.raises(HTTPException) as exc:
        await build_task_from_template("portfolio-web", BuildFromTemplateRequest())
    assert exc.value.status_code == 400
    # Nothing may have landed outside the sandbox.
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path.parent / "escaped.txt").exists()
