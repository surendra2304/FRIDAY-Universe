"""Completeness heal: the REAL gate over the REAL recovery create route.

Production evidence (G5 acceptance re-run, 2026-11-17, task
task28517112026142322): the module completeness gate correctly identified
five missing files -- taskboard/db.py, taskboard/services.py,
taskboard/api.py, taskboard/cli.py, tests/test_api.py -- and invoked the
recovery create route for each, twice (in-DAG gate + run_task backstop).
Every one of the nine attempts failed in about a second with "Create route
produced no module", and no generation was ever attempted: the journal
contains zero provider-call lines for the whole run.

Root cause (forge-completeness-diag, verdict (d)): the gate speaks paths
-- it passes the full relative path (``taskboard/db.py``) as
``failing_file`` -- while ``RecoveryEngine._create_missing_module_patch``
re-derived its target with a bare-identifier grammar (a fullmatch against
``<name>.py`` or a "No module named '<name>'" text search). A path-shaped
target matches neither, so the route returned None before the
goal/spec/manifest naming check and before any provider call. Any file
inside a directory was un-healable by construction.

FRG-013's tests missed the seam because the gate tests inject a stub
``create_module`` callable; the real route was never wired behind the
real gate in any test. These tests close that hole: the REAL
``ModuleCompletenessGate`` with NO ``create_module`` injection, over the
REAL ``RecoveryEngine``, with only the AI client stubbed.

On the pre-fix engine the headline test fails (both files stay missing);
with the fix both files are created and ``report.missing == []``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.filesystem import FilesystemTool
from app.execution.permissions import PermissionManager

# The G5 shape, reduced to the two files the diagnosis names: a package
# module and a declared test file, both inside directories, both absent.
GOAL = "Create the taskboard project declared in the file manifest."
MANIFEST = ["taskboard/__init__.py", "taskboard/db.py", "tests/test_api.py"]

INIT_CODE = "# taskboard package\n"
DB_CODE = (
    "import sqlite3\n"
    "\n"
    "\n"
    "def connect(path=':memory:'):\n"
    "    return sqlite3.connect(path)\n"
)
TEST_API_CODE = (
    "def test_api_placeholder():\n"
    "    assert True\n"
)


@pytest.fixture()
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def fs_tool(temp_dir: Path) -> FilesystemTool:
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    return FilesystemTool(wm=wm, pm=PermissionManager())


class _PerFileAIClient:
    """Stands in for the Inference code channel, answering per filename."""

    def __init__(self, answers: dict[str, str], confidence: float = 0.95):
        self._answers = answers
        self._confidence = confidence
        self.calls: list[str] = []

    async def generate_code(self, **kwargs):
        filename = kwargs.get("filename", "")
        self.calls.append(filename)
        return SimpleNamespace(
            answer=self._answers.get(filename, ""),
            confidence=self._confidence,
            run_id="completeness-heal-test",
        )


class _StubStore:
    def __init__(self, goal: str, requirements: list[str] | None = None):
        self._goal = goal
        self._requirements = requirements or []
        self.events: list[tuple[str, dict]] = []

    async def get_task(self, task_id: str):
        return SimpleNamespace(goal=self._goal, requirements=self._requirements)

    async def record_event(self, task_id: str, event_type: str, payload: dict | None = None):
        self.events.append((event_type, payload or {}))


def _plant_project(fs_tool: FilesystemTool, task_id: str) -> None:
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id,
        relative_path="taskboard/__init__.py",
        content=INIT_CODE,
        role="developer",
    )
    fs_tool.create_file(
        task_id=task_id,
        relative_path="docs/FILE_MANIFEST.json",
        content=json.dumps(MANIFEST),
        role="developer",
    )


def _patch_ai(monkeypatch: pytest.MonkeyPatch, client: _PerFileAIClient) -> None:
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: client
    )


def _recovery_engine(fs_tool: FilesystemTool, store: _StubStore):
    from app.recovery.engine import RecoveryEngine
    from app.recovery.repair import PatchApplicator

    exec_engine = SimpleNamespace(fs=fs_tool)
    return RecoveryEngine(
        exec_engine=exec_engine,
        applicator=PatchApplicator(engine=exec_engine),
        store=store,
    )


# ---------------------------------------------------------------------------
# The seam itself: real gate, real recovery engine, only the AI stubbed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_heals_path_shaped_missing_files_via_real_recovery(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.execution.completeness import ModuleCompletenessGate

    task_id = "healg5shape"
    _plant_project(fs_tool, task_id)
    fake = _PerFileAIClient(
        {"taskboard/db.py": DB_CODE, "tests/test_api.py": TEST_API_CODE}
    )
    _patch_ai(monkeypatch, fake)
    store = _StubStore(GOAL, [])

    # NO create_module injection: the gate must use its default route,
    # which builds the real RecoveryEngine internally.
    engine = SimpleNamespace(fs=fs_tool, wm=fs_tool.wm)
    gate = ModuleCompletenessGate(engine=engine, store=store)
    report = await gate.ensure_complete(
        task_id, GOAL, [], include_test_files=True
    )

    assert report.missing == []
    assert report.healed == ["taskboard/db.py", "tests/test_api.py"]
    # The provider was actually reached, once per missing file, with the
    # full relative path as the requested filename.
    assert fake.calls == ["taskboard/db.py", "tests/test_api.py"]
    # Both files are really on disk and parse.
    for target, expected in (
        ("taskboard/db.py", DB_CODE),
        ("tests/test_api.py", TEST_API_CODE),
    ):
        written = fs_tool.read_file(task_id, target, role="debugger")
        # The extractor strips the provider's answer (LLMResponseParser),
        # so compare modulo surrounding whitespace; the file must be the
        # generated module, complete and parseable.
        assert written.strip() == expected.strip()
        compile(written, target, "exec")


# ---------------------------------------------------------------------------
# The create route directly, with path-shaped targets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_route_accepts_path_shaped_target(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "healpathdirect"
    _plant_project(fs_tool, task_id)
    fake = _PerFileAIClient({"taskboard/db.py": DB_CODE})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, _StubStore(GOAL, []))

    created, _message = await engine.create_missing_module(task_id, "taskboard/db.py")
    assert created is True
    assert fake.calls == ["taskboard/db.py"]
    written = fs_tool.read_file(task_id, "taskboard/db.py", role="debugger")
    assert written.strip() == DB_CODE.strip()


@pytest.mark.asyncio
async def test_create_route_rejects_path_named_by_nobody(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    # A path-shaped target the goal, spec and manifest never name is still
    # refused -- and the refusal message names the actual reason instead
    # of the old three-cause list, none of which was true in G5.
    task_id = "healghostpath"
    _plant_project(fs_tool, task_id)
    fake = _PerFileAIClient({"taskboard/ghost.py": DB_CODE})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, _StubStore(GOAL, []))

    created, message = await engine.create_missing_module(task_id, "taskboard/ghost.py")
    assert created is False
    assert fake.calls == []
    assert "taskboard/ghost.py" not in fs_tool.search_files(
        task_id, pattern="*.py", role="debugger"
    )
    assert "not named by the goal, spec or manifest" in message
    assert "provider unavailable, below the confidence bar" not in message


@pytest.mark.asyncio
async def test_create_route_rejects_stdlib_path_component(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    # The stdlib guard applies to a path target's stem: a missing stdlib
    # module is an environment problem, never a project file, even when
    # the manifest text happens to name the path.
    task_id = "healstdlibpath"
    _plant_project(fs_tool, task_id)
    fs_tool.create_file(
        task_id=task_id,
        relative_path="docs/FILE_MANIFEST.json",
        content=json.dumps(MANIFEST + ["taskboard/os.py"]),
        role="developer",
    )
    fake = _PerFileAIClient({"taskboard/os.py": DB_CODE})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, _StubStore(GOAL, []))

    created, message = await engine.create_missing_module(task_id, "taskboard/os.py")
    assert created is False
    assert fake.calls == []
    assert "standard-library" in message


@pytest.mark.asyncio
async def test_create_route_reports_shape_rejection_honestly(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    # A target that is neither a bare module nor a relative code-file
    # path is rejected for THAT reason, stated as such.
    task_id = "healshape"
    _plant_project(fs_tool, task_id)
    fake = _PerFileAIClient({})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, _StubStore(GOAL, []))

    created, message = await engine.create_missing_module(task_id, "taskboard/db")
    assert created is False
    assert fake.calls == []
    assert "provider unavailable, below the confidence bar" not in message
    assert "taskboard/db" in message
