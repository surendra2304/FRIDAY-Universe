"""TASK-FRG-013: the completeness backstop must also guard FAILED tasks.

TASK-FRG-010 built the module completeness gate and wired it into
run_task as a backstop -- but only for tasks whose DAG ended
COMPLETED. The FRG-009 codegen-quality battery's G5 is the
counterexample: a 10-file taskboard goal settled at 6/10 files
(taskboard/db.py, api.py, cli.py and tests/test_api.py never written).
Its DAG ended FAILED -- its gates failed over the incomplete set --
so the backstop never ran: nothing healed the missing modules, nothing
named them as a completeness failure, and the build surfaced as a
battery PARTIAL_FAILURE whose only sign of the real defect was a
pytest collection error.

These tests pin the widened backstop:

* ``expected_modules``/``ensure_complete`` accept ``include_test_files``
  (the backstop runs after the Tester role, so declared test files are
  layout too) while the default keeps FRG-010's in-DAG behaviour;
* run_task's backstop runs for a FAILED task, records the missing
  modules under the completeness name (source modules AND the declared
  test file), and does NOT overwrite the task's original error;
* for a COMPLETED task the backstop still demotes to FAILED naming
  the missing modules, now including declared test files.

On pristine main the flag does not exist (TypeError) and the FAILED
backstop never runs (no module_completeness.backstop event).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.completeness import ModuleCompletenessGate, expected_modules
from app.execution.engine import ExecutionEngine
from app.execution.filesystem import FilesystemTool
from app.execution.permissions import PermissionManager
from app.memory.models import TaskEntity, TaskState
from app.recovery.engine import RecoveryEngine

# The FRG-009 battery's G5 goal, verbatim.
G5_GOAL = (
    "Create a multi-module task manager backend package named taskboard using ONLY the Python "
    "standard library, with exactly this layout (10 files): taskboard/__init__.py; "
    "taskboard/models.py with dataclasses User(id, name, email) and Task(id, title, description, "
    "status, assignee_id, created_at, due_date) where status is one of todo, in_progress, done; "
    "taskboard/security.py with hash_password(password) -> str and verify_password(password, "
    "hashed) -> bool using hashlib.pbkdf2_hmac with a per-password random salt from the secrets "
    "module; taskboard/db.py with a SQLite-backed repository class TaskBoardDB using the sqlite3 "
    "module with methods create_user, get_user, create_task, get_task, list_tasks(status=None, "
    "assignee_id=None), update_task_status and delete_task; taskboard/services.py with a "
    "TaskService class wrapping TaskBoardDB that validates status transitions (a task may not "
    "move from done back to todo, and creating a task for an unknown user raises ValueError); "
    "taskboard/api.py exposing the service via http.server handlers for POST /users, GET /tasks, "
    "POST /tasks and PATCH /tasks/<id>/status with JSON bodies and 400/404 handling; "
    "taskboard/cli.py with an argparse CLI with add-user, add-task, list and complete "
    "subcommands; main.py at the project root demonstrating user creation, task creation, a "
    "status transition and listing; tests/test_services.py with pytest tests for the password "
    "round-trip, transition validation and repository CRUD; and tests/test_api.py with pytest "
    "tests exercising the API endpoints on an ephemeral port."
)
G5_REQUIREMENTS = [
    "standard library only, no third-party imports anywhere",
    "the layout exists exactly as specified, all 10 files",
    "a done task cannot transition back to todo and the service rejects it",
    "verify_password accepts the correct password and rejects a wrong one",
    "the pytest tests exist and pass",
]

# What G5 actually settled with: db.py, api.py, cli.py and
# tests/test_api.py were never written.
G5_PRESENT = {
    "taskboard/__init__.py": "from . import models  # noqa\n",
    "taskboard/models.py": "# models\n",
    "taskboard/security.py": "# security\n",
    "taskboard/services.py": "# services\n",
    "main.py": "# demo\n",
    "tests/test_services.py": "# tests\n",
}
G5_MISSING = ["taskboard/api.py", "taskboard/cli.py", "taskboard/db.py", "tests/test_api.py"]


# ---------------------------------------------------------------------------
# Gate level: the include_test_files flag
# ---------------------------------------------------------------------------


def test_expected_modules_include_test_files_only_on_request():
    default = expected_modules(G5_GOAL, G5_REQUIREMENTS, [])
    assert "taskboard/db.py" in default
    assert "tests/test_api.py" not in default
    assert "tests/test_services.py" not in default

    widened = expected_modules(G5_GOAL, G5_REQUIREMENTS, [], include_test_files=True)
    assert "tests/test_api.py" in widened
    assert "tests/test_services.py" in widened
    # Nothing else changes: the source-module set is identical.
    assert [m for m in widened if not m.startswith("tests/")] == default


class _FakeFS:
    """The two fs reads the gate performs, over a planted file set."""

    def __init__(self, files: set[str], manifest: list[str] | None = None):
        self._files = files
        self._manifest = manifest

    def read_file(self, task_id, relative_path, role="debugger"):
        if relative_path == "docs/FILE_MANIFEST.json" and self._manifest is not None:
            return json.dumps(self._manifest)
        raise FileNotFoundError(relative_path)

    def search_files(self, task_id, pattern="*", role="debugger"):
        return sorted(self._files)


async def test_ensure_complete_reports_missing_test_file_only_when_asked():
    async def cannot_create(task_id, target):
        return False, "stubbed create route"

    engine = SimpleNamespaceFS(_FakeFS(set(G5_PRESENT)))
    gate = ModuleCompletenessGate(engine=engine, create_module=cannot_create)

    default_report = await gate.ensure_complete("g5", G5_GOAL, G5_REQUIREMENTS)
    assert "tests/test_api.py" not in default_report.missing
    assert "taskboard/db.py" in default_report.missing

    widened_report = await gate.ensure_complete(
        "g5", G5_GOAL, G5_REQUIREMENTS, include_test_files=True
    )
    assert sorted(widened_report.missing) == G5_MISSING


class SimpleNamespaceFS:
    def __init__(self, fs):
        self.fs = fs


# ---------------------------------------------------------------------------
# Orchestrator level: the backstop's state condition
# ---------------------------------------------------------------------------


class _FakeStore:
    def __init__(self, task: TaskEntity):
        self.task = task
        self.events: list[tuple[str, dict]] = []

    async def get_task(self, task_id):
        return self.task

    async def record_event(self, task_id, event_type, payload):
        self.events.append((event_type, payload))

    async def update_task_state(self, task_id, state=None, progress_percentage=None, error_message=None, **kw):
        if state is not None:
            self.task.state = state
        if progress_percentage is not None:
            self.task.progress_percentage = progress_percentage
        if error_message is not None:
            self.task.error_message = error_message
        return self.task


@pytest.fixture()
def no_create_route(monkeypatch):
    """The recovery create route is a separate subsystem (FRG-010's
    tests own it); here it deterministically cannot create, so the
    gate's missing set is exactly the planted omission."""

    async def _cannot(self, task_id, target_file):
        return False, "stubbed: create route unavailable in this test"

    monkeypatch.setattr(RecoveryEngine, "create_missing_module", _cannot)


def _orchestrator(tmp_path: Path, task: TaskEntity) -> OrchestratorCore:
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm, pm=PermissionManager())
    store = _FakeStore(task)
    orch = OrchestratorCore(store=store, wm=wm, engine=engine)
    wm.create_workspace(task.id)
    fs = FilesystemTool(wm=wm, pm=PermissionManager())
    for rel, content in G5_PRESENT.items():
        fs.create_file(task_id=task.id, relative_path=rel, content=content, role="developer")
    # The DAG is not under test: step_task reports the terminal state
    # immediately, and the post-backstop stages are stubbed out.
    async def _step(task_id):
        return store.task, []

    orch.step_task = _step  # type: ignore[method-assign]
    orch._verify_and_repair = AsyncMock(return_value=None)  # type: ignore[method-assign]
    orch.apply_final_verdict = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return orch


def _task(state: TaskState) -> TaskEntity:
    return TaskEntity(
        goal=G5_GOAL,
        requirements=G5_REQUIREMENTS,
        workspace_path="unused",
        state=state,
        error_message="tester gate failed: collection error" if state == TaskState.FAILED else None,
    )


async def test_backstop_runs_for_failed_task_and_names_missing(tmp_path, no_create_route):
    task = _task(TaskState.FAILED)
    orch = _orchestrator(tmp_path, task)
    result = await orch.run_task(task.id)

    assert result.state == TaskState.FAILED
    # The original failure is NOT overwritten by the completeness name.
    assert result.error_message == "tester gate failed: collection error"
    backstop_events = [
        payload for kind, payload in orch.store.events if kind == "module_completeness.backstop"
    ]
    assert len(backstop_events) == 1
    assert sorted(backstop_events[0]["missing_modules"]) == G5_MISSING


async def test_backstop_still_demotes_completed_task(tmp_path, no_create_route):
    task = _task(TaskState.COMPLETED)
    orch = _orchestrator(tmp_path, task)
    result = await orch.run_task(task.id)

    assert result.state == TaskState.FAILED
    assert result.error_message is not None
    for missing in G5_MISSING:
        assert missing in result.error_message
