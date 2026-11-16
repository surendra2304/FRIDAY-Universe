"""TASK-FRG-010: the module completeness gate.

Production evidence (TASK-FRG-003's battery, 2026-11-15): goals naming
several modules still produced projects where some of those modules were
never written -- R3's store.py/pricing.py, R2's and R4's two-module
layouts collapsing to a single file. The fabrication mask is gone
(TASK-FRG-003), so the omission now fails honestly at test collection,
but nothing in the pipeline ever compared the goal/manifest module set
with the files on disk: the Developer role's per-file loop accepts any
synthesised .py as satisfying any manifest entry, and the fallback path
records whatever was extracted without checking the requested file
exists. The build marched to the tester gate incomplete.

These tests pin the gate: before the tester gate (and again before the
verification battery), every goal-named or manifest-declared source
module must exist as a real file; missing modules are created through
the recovery create route; modules that still cannot be produced fail
the build with their names in the error, and the tester never runs.

On main (with PR #329 applied) every test here fails: the gate module
and the RecoveryEngine.create_missing_module entry point do not exist,
and the create route refuses manifest-named files the goal never
repeats.
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

# FRG-003's R3 goal, verbatim (the four-module inventory project whose
# store.py and pricing.py were never written).
R3_GOAL = (
    "Create a Python inventory project with four modules: models.py defining a "
    "dataclass Item with fields sku, name, price_cents, quantity; store.py defining "
    "an Inventory class that uses Item from models.py with methods add_item, "
    "remove_item(sku), total_value_cents() and low_stock(threshold); pricing.py with "
    "functions apply_discount(price_cents, percent) and add_tax(price_cents, "
    "rate_percent), used by store.py for a discounted_total_cents(percent, "
    "rate_percent) method; and main.py demonstrating the system end to end. Modules "
    "must import from each other as described, not duplicate the logic."
)
R3_REQUIREMENTS = [
    "Item dataclass in models.py used by store.py",
    "Inventory methods behave as specified including removing by sku",
    "pricing functions round to whole cents",
    "main.py demonstrates add, discount+tax total, and low-stock listing",
]
R3_MANIFEST = ["models.py", "store.py", "pricing.py", "main.py"]

MODELS_CODE = (
    "from dataclasses import dataclass\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class Item:\n"
    "    sku: str\n"
    "    name: str\n"
    "    price_cents: int\n"
    "    quantity: int\n"
)
STORE_CODE = (
    "from models import Item\n"
    "from pricing import add_tax, apply_discount\n"
    "\n"
    "\n"
    "class Inventory:\n"
    "    def __init__(self):\n"
    "        self._items = {}\n"
    "\n"
    "    def add_item(self, item):\n"
    "        self._items[item.sku] = item\n"
    "\n"
    "    def remove_item(self, sku):\n"
    "        self._items.pop(sku, None)\n"
    "\n"
    "    def total_value_cents(self):\n"
    "        return sum(i.price_cents * i.quantity for i in self._items.values())\n"
    "\n"
    "    def low_stock(self, threshold):\n"
    "        return [i for i in self._items.values() if i.quantity < threshold]\n"
    "\n"
    "    def discounted_total_cents(self, percent, rate_percent):\n"
    "        return add_tax(apply_discount(self.total_value_cents(), percent), rate_percent)\n"
)
PRICING_CODE = (
    "def apply_discount(price_cents, percent):\n"
    "    return int(round(price_cents * (100 - percent) / 100))\n"
    "\n"
    "\n"
    "def add_tax(price_cents, rate_percent):\n"
    "    return int(round(price_cents * (100 + rate_percent) / 100))\n"
)
MAIN_CODE = (
    "from models import Item\n"
    "from store import Inventory\n"
    "\n"
    "\n"
    "def main():\n"
    "    inv = Inventory()\n"
    "    inv.add_item(Item(sku='A1', name='Widget', price_cents=500, quantity=3))\n"
    "    print(inv.total_value_cents())\n"
    "\n"
    "\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
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


def _plant_project(
    fs_tool: FilesystemTool,
    task_id: str,
    files: dict[str, str],
    manifest: list[str] | None,
) -> None:
    fs_tool.wm.create_workspace(task_id)
    for path, content in files.items():
        fs_tool.create_file(
            task_id=task_id, relative_path=path, content=content, role="developer"
        )
    if manifest is not None:
        fs_tool.create_file(
            task_id=task_id,
            relative_path="docs/FILE_MANIFEST.json",
            content=json.dumps(manifest),
            role="developer",
        )


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
            run_id="frg010-test",
        )


def _patch_ai(monkeypatch: pytest.MonkeyPatch, client: _PerFileAIClient) -> None:
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: client
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


def _recovery_engine(fs_tool: FilesystemTool, goal: str, requirements=None):
    from app.recovery.engine import RecoveryEngine
    from app.recovery.repair import PatchApplicator

    exec_engine = SimpleNamespace(fs=fs_tool)
    return RecoveryEngine(
        exec_engine=exec_engine,
        applicator=PatchApplicator(engine=exec_engine),
        store=_StubStore(goal, requirements),
    )


# ---------------------------------------------------------------------------
# Expected-set computation
# ---------------------------------------------------------------------------


def test_expected_modules_union_of_manifest_and_goal():
    from app.execution.completeness import expected_modules

    manifest = R3_MANIFEST + ["test_main.py", "README.md", "docs/ARCHITECTURE_SPEC.md"]
    assert expected_modules(R3_GOAL, R3_REQUIREMENTS, manifest) == R3_MANIFEST


def test_expected_modules_includes_manifest_only_modules():
    from app.execution.completeness import expected_modules

    # A module the architect declared but the goal never repeats is still
    # owed to the build.
    manifest = ["main.py", "temperature.py", "test_main.py", "README.md"]
    assert expected_modules("Create a temperature converter", [], manifest) == [
        "main.py",
        "temperature.py",
    ]


def test_expected_modules_filters_tests_docs_and_assets():
    from app.execution.completeness import expected_modules

    manifest = [
        "main.py",
        "tests/test_api.py",
        "test_main.py",
        "docs/FILE_MANIFEST.json",
        "style.css",
        "pkg/__init__.py",
        "pkg/core.py",
    ]
    assert expected_modules("", [], manifest) == ["main.py", "pkg/__init__.py", "pkg/core.py"]


# FRG-003's R2 goal, verbatim (the two-module temperature project the
# production acceptance battery drove on 2026-11-16): the goal and its
# requirements state exactly two paths, so FRG-004's architect-side
# extraction (which engages at >=3 stated paths) yields nothing, and
# when the plan's DAG produces no FILE_MANIFEST.json either, the gate
# must still know what the build owes.
R2_GOAL = (
    "Create a small Python project with exactly two modules: a module temperature.py "
    "with functions c_to_f(c: float) -> float, f_to_c(f: float) -> float, "
    "c_to_k(c: float) -> float and k_to_c(k: float) -> float for temperature "
    "conversion (Kelvin conversions must raise ValueError for results below "
    "absolute zero), and a main.py command-line demo that imports those functions "
    "from temperature.py and prints a small conversion table. The conversion "
    "functions must live in temperature.py, not in main.py."
)
R2_REQUIREMENTS = [
    "conversion functions defined in temperature.py and imported by main.py",
    "Kelvin functions raise ValueError below absolute zero",
    "celsius-fahrenheit conversions round-trip within floating tolerance",
]


def test_expected_modules_two_module_goal_without_manifest():
    from app.execution.completeness import expected_modules

    # Two stated paths are below FRG-004's layout threshold, but the
    # gate demands whatever the goal actually states: both modules are
    # owed even with no manifest at all.
    assert expected_modules(R2_GOAL, R2_REQUIREMENTS, []) == [
        "temperature.py",
        "main.py",
    ]
    assert expected_modules(R2_GOAL, R2_REQUIREMENTS, None) == [
        "temperature.py",
        "main.py",
    ]


def test_expected_modules_single_stated_module():
    from app.execution.completeness import expected_modules

    goal = (
        "Create temperature.py with functions c_to_f(c: float) -> float "
        "and f_to_c(f: float) -> float for converting temperatures."
    )
    assert expected_modules(goal, [], []) == ["temperature.py"]


def test_expected_modules_quiet_when_nothing_is_stated():
    from app.execution.completeness import expected_modules

    # Nothing stated, no manifest: the gate invents no expectations.
    assert expected_modules("Create a temperature converter", [], []) == []
    assert expected_modules("Create a temperature converter", [], None) == []


# ---------------------------------------------------------------------------
# The gate itself (create step injected)
# ---------------------------------------------------------------------------


def _gate(fs_tool: FilesystemTool, create_module=None, store=None):
    from app.execution.completeness import ModuleCompletenessGate

    engine = SimpleNamespace(fs=fs_tool, wm=fs_tool.wm)
    return ModuleCompletenessGate(engine=engine, store=store, create_module=create_module)


@pytest.mark.asyncio
async def test_gate_heals_missing_modules(fs_tool: FilesystemTool):
    task_id = "frg010heal"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )

    async def create(task_id_, target):
        fs_tool.create_file(
            task_id=task_id_,
            relative_path=target,
            content="# created by the gate\nVALUE = 1\n",
            role="debugger",
        )
        return True, "created"

    report = await _gate(fs_tool, create_module=create).ensure_complete(
        task_id, R3_GOAL, R3_REQUIREMENTS
    )
    assert report.complete
    assert report.healed == ["store.py", "pricing.py"]
    assert report.missing == []
    present = set(fs_tool.search_files(task_id, pattern="*.py", role="debugger"))
    assert {"store.py", "pricing.py"} <= present


@pytest.mark.asyncio
async def test_gate_names_modules_it_cannot_create(fs_tool: FilesystemTool):
    task_id = "frg010refuse"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )

    async def create(task_id_, target):
        if target == "pricing.py":
            return False, "provider below the confidence bar"
        fs_tool.create_file(
            task_id=task_id_,
            relative_path=target,
            content="# created by the gate\nVALUE = 1\n",
            role="debugger",
        )
        return True, "created"

    report = await _gate(fs_tool, create_module=create).ensure_complete(
        task_id, R3_GOAL, R3_REQUIREMENTS
    )
    assert not report.complete
    assert report.healed == ["store.py"]
    assert report.missing == ["pricing.py"]
    message = report.failure_message()
    assert "pricing.py" in message
    assert "store.py" not in message


@pytest.mark.asyncio
async def test_gate_trusts_disk_over_route_claims(fs_tool: FilesystemTool):
    task_id = "frg010disk"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )

    async def lying_create(task_id_, target):
        return True, "created (but nothing was written)"

    report = await _gate(fs_tool, create_module=lying_create).ensure_complete(
        task_id, R3_GOAL, R3_REQUIREMENTS
    )
    assert report.healed == []
    assert report.missing == ["store.py", "pricing.py"]


@pytest.mark.asyncio
async def test_gate_is_quiet_when_project_is_complete(fs_tool: FilesystemTool):
    task_id = "frg010complete"
    _plant_project(
        fs_tool,
        task_id,
        {
            "models.py": MODELS_CODE,
            "store.py": STORE_CODE,
            "pricing.py": PRICING_CODE,
            "main.py": MAIN_CODE,
        },
        R3_MANIFEST,
    )
    calls: list[str] = []

    async def create(task_id_, target):
        calls.append(target)
        return True, "created"

    report = await _gate(fs_tool, create_module=create).ensure_complete(
        task_id, R3_GOAL, R3_REQUIREMENTS
    )
    assert report.complete
    assert calls == []


@pytest.mark.asyncio
async def test_gate_fires_for_two_module_goal_on_empty_project(fs_tool: FilesystemTool):
    # The production R2 shape: the goal states two modules, the plan
    # produced no manifest, and the project directory is EMPTY. Before
    # the fix the gate computed an empty expected set and stayed silent
    # while the verification battery passed vacuously over zero files.
    task_id = "frg010twomodule"
    _plant_project(fs_tool, task_id, {}, None)
    store = _StubStore(R2_GOAL, R2_REQUIREMENTS)

    async def create(task_id_, target):
        fs_tool.create_file(
            task_id=task_id_,
            relative_path=target,
            content="# created by the gate\nVALUE = 1\n",
            role="debugger",
        )
        return True, "created"

    report = await _gate(fs_tool, create_module=create, store=store).ensure_complete(
        task_id, R2_GOAL, R2_REQUIREMENTS
    )
    assert report.expected == ["temperature.py", "main.py"]
    assert report.healed == ["temperature.py", "main.py"]
    assert report.missing == []
    assert report.complete
    assert [event for event, _ in store.events] == ["module_completeness.healed"]


@pytest.mark.asyncio
async def test_gate_fails_two_module_goal_it_cannot_create(fs_tool: FilesystemTool):
    # Same empty-project shape, but the create route cannot produce the
    # modules: the gate must surface the failure by name instead of
    # letting the build proceed over zero files.
    task_id = "frg010twomodulefail"
    _plant_project(fs_tool, task_id, {}, None)
    store = _StubStore(R2_GOAL, R2_REQUIREMENTS)

    async def create(task_id_, target):
        return False, "provider below the confidence bar"

    report = await _gate(fs_tool, create_module=create, store=store).ensure_complete(
        task_id, R2_GOAL, R2_REQUIREMENTS
    )
    assert not report.complete
    assert report.expected == ["temperature.py", "main.py"]
    assert report.healed == []
    assert report.missing == ["temperature.py", "main.py"]
    message = report.failure_message()
    assert "temperature.py" in message
    assert "main.py" in message
    assert [event for event, _ in store.events] == ["module_completeness.failed"]


# ---------------------------------------------------------------------------
# RecoveryEngine.create_missing_module -- the create route, driven directly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_missing_module_creates_real_file(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "frg010create"
    _plant_project(
        fs_tool,
        task_id,
        {"models.py": MODELS_CODE, "pricing.py": PRICING_CODE, "main.py": MAIN_CODE},
        R3_MANIFEST,
    )
    fake = _PerFileAIClient({"store.py": STORE_CODE})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, R3_GOAL, R3_REQUIREMENTS)

    created, _message = await engine.create_missing_module(task_id, "store.py")
    assert created is True
    assert fake.calls == ["store.py"]
    written = fs_tool.read_file(task_id, "store.py", role="debugger")
    compile(written, "store.py", "exec")

    # The created module really imports against its siblings and works.
    import importlib
    import sys

    project = str(fs_tool.wm.get_workspace_paths(task_id).project)
    sys.path.insert(0, project)
    try:
        for mod in ("store", "pricing", "models"):
            sys.modules.pop(mod, None)
        store_mod = importlib.import_module("store")
        models_mod = importlib.import_module("models")
        inv = store_mod.Inventory()
        inv.add_item(models_mod.Item(sku="A1", name="Widget", price_cents=500, quantity=3))
        assert inv.total_value_cents() == 1500
        assert inv.discounted_total_cents(10, 10) == 1485
    finally:
        sys.path.remove(project)


@pytest.mark.asyncio
async def test_create_missing_module_respects_confidence_bar(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "frg010lowconf"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )
    low = _PerFileAIClient({"store.py": STORE_CODE}, confidence=0.5)
    _patch_ai(monkeypatch, low)
    engine = _recovery_engine(fs_tool, R3_GOAL, R3_REQUIREMENTS)

    created, _message = await engine.create_missing_module(task_id, "store.py")
    assert created is False
    assert low.calls == ["store.py"]
    assert "store.py" not in fs_tool.search_files(task_id, pattern="*.py", role="debugger")


@pytest.mark.asyncio
async def test_create_route_accepts_manifest_named_module(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    # The goal never repeats the file name; only the architect's manifest
    # declares it. On main the create route refuses (goal/spec naming
    # only); the gate exists for exactly these modules.
    task_id = "frg010manifest"
    vague_goal = "Build the inventory system described in the project manifest."
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )
    fake = _PerFileAIClient({"store.py": STORE_CODE})
    _patch_ai(monkeypatch, fake)
    engine = _recovery_engine(fs_tool, vague_goal, [])

    created, _message = await engine.create_missing_module(task_id, "store.py")
    assert created is True

    # A file named by neither goal, spec nor manifest is still refused.
    created_ghost, _ = await engine.create_missing_module(task_id, "ghost.py")
    assert created_ghost is False
    assert "ghost.py" not in fs_tool.search_files(task_id, pattern="*.py", role="debugger")


# ---------------------------------------------------------------------------
# Orchestrator wiring: the tester gate cannot run on an incomplete project
# ---------------------------------------------------------------------------


class _FakeStore:
    """The slice of StateStore step_task / run_task / lifecycle touch."""

    def __init__(self, task, graph):
        self._task = task
        self._graph = graph
        self.events: list[tuple[str, dict]] = []

    async def get_task(self, task_id):
        return self._task

    async def get_latest_task_graph_for_project(self, task_id):
        return self._graph

    async def save_task_graph(self, graph):
        self._graph = graph
        return graph

    async def record_event(self, task_id, event_type, payload=None):
        self.events.append((event_type, payload or {}))

    async def update_task_state(
        self, task_id, state=None, progress_percentage=None, error_message=None
    ):
        if state is not None:
            self._task.state = state
        if progress_percentage is not None:
            self._task.progress_percentage = progress_percentage
        if error_message is not None:
            self._task.error_message = error_message
        return self._task

    async def list_checkpoints(self, task_id):
        return []

    async def save_checkpoint(self, checkpoint):
        return checkpoint

    async def get_latest_checkpoint(self, task_id):
        return None


class _RecordingAgent:
    def __init__(self, role, calls):
        self._role = role
        self._calls = calls

    async def execute_step(self, task_id, node_title, context, engine):
        self._calls.append(self._role)
        return {"status": "success", "agent": self._role}


class _FakeRegistry:
    def __init__(self):
        self.calls: list[str] = []

    def create_agent(self, role):
        return _RecordingAgent(role, self.calls)


class _FakeContextManager:
    def build_agent_context(self, **kwargs):
        base = kwargs.get("base_context", {})
        return {
            "goal": base.get("goal", ""),
            "requirements": base.get("requirements", []),
        }

    def record_step_result(self, *args, **kwargs):
        pass

    def record_terminal_output(self, *args, **kwargs):
        pass


def _orchestrator(fs_tool: FilesystemTool, store: _FakeStore, registry: _FakeRegistry):
    from app.core.orchestrator import OrchestratorCore

    engine = SimpleNamespace(fs=fs_tool, wm=fs_tool.wm)
    return OrchestratorCore(
        store=store,
        wm=fs_tool.wm,
        engine=engine,
        registry=registry,
        ctx_manager=_FakeContextManager(),
    )


def _task_and_graph(task_id: str, gate_status):
    from app.memory.models import TaskGraph, TaskNode, TaskState

    task = SimpleNamespace(
        id=task_id,
        goal=R3_GOAL,
        requirements=R3_REQUIREMENTS,
        mode=SimpleNamespace(value="autonomous"),
        state=TaskState.RUNNING,
        error_message=None,
        progress_percentage=0,
    )
    graph = TaskGraph(id=task_id, project_id=task_id, goal=R3_GOAL)
    graph.add_node(
        TaskNode(
            id="dev1",
            title="[Implementation] Core implementation",
            status=TaskState.COMPLETED,
            dependencies=[],
            assigned_agent="developer",
            metadata={"stage": "Implementation", "node_type": "task"},
        )
    )
    graph.add_node(
        TaskNode(
            id="gate1",
            title="[Verification] Automated Test Suite & Verification Gate",
            status=gate_status,
            dependencies=["dev1"],
            assigned_agent="tester",
            metadata={"stage": "Verification", "node_type": "verification_gate"},
        )
    )
    return task, graph


@pytest.mark.asyncio
async def test_step_task_fails_tester_gate_with_missing_names(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.memory.models import TaskState

    task_id = "frg010gatefail"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )
    # The provider cannot author the missing modules (below the bar).
    _patch_ai(monkeypatch, _PerFileAIClient({"store.py": STORE_CODE}, confidence=0.5))
    task, graph = _task_and_graph(task_id, TaskState.PENDING)
    store = _FakeStore(task, graph)
    registry = _FakeRegistry()
    orchestrator = _orchestrator(fs_tool, store, registry)

    result_task, _executed = await orchestrator.step_task(task_id)

    assert registry.calls == []  # the tester never ran
    assert graph.nodes["gate1"].status == TaskState.FAILED
    assert result_task.state == TaskState.FAILED
    assert "store.py" in (result_task.error_message or "")
    assert "pricing.py" in (result_task.error_message or "")


@pytest.mark.asyncio
async def test_step_task_heals_then_runs_tester_gate(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.memory.models import TaskState

    task_id = "frg010gateheal"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )
    fake = _PerFileAIClient({"store.py": STORE_CODE, "pricing.py": PRICING_CODE})
    _patch_ai(monkeypatch, fake)
    task, graph = _task_and_graph(task_id, TaskState.PENDING)
    store = _FakeStore(task, graph)
    registry = _FakeRegistry()
    orchestrator = _orchestrator(fs_tool, store, registry)

    result_task, _executed = await orchestrator.step_task(task_id)

    assert fake.calls == ["store.py", "pricing.py"]  # healed in manifest order
    assert registry.calls == ["tester"]  # then the gate ran
    assert graph.nodes["gate1"].status == TaskState.COMPLETED
    assert result_task.state == TaskState.COMPLETED
    present = set(fs_tool.search_files(task_id, pattern="*.py", role="debugger"))
    assert {"store.py", "pricing.py"} <= present
    healed_events = [p for t, p in store.events if t == "module_completeness.healed"]
    assert healed_events and healed_events[0]["healed"] == ["store.py", "pricing.py"]


@pytest.mark.asyncio
async def test_run_task_backstop_fails_completed_task_with_missing_modules(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.core.orchestrator import OrchestratorCore
    from app.memory.models import TaskState

    task_id = "frg010backstop"
    _plant_project(
        fs_tool, task_id, {"models.py": MODELS_CODE, "main.py": MAIN_CODE}, R3_MANIFEST
    )
    _patch_ai(monkeypatch, _PerFileAIClient({"store.py": STORE_CODE}, confidence=0.5))
    task, graph = _task_and_graph(task_id, TaskState.COMPLETED)
    task.state = TaskState.COMPLETED
    store = _FakeStore(task, graph)
    registry = _FakeRegistry()
    orchestrator = _orchestrator(fs_tool, store, registry)

    verify_calls: list[str] = []

    async def _no_battery(self, task_id_):
        verify_calls.append(task_id_)
        return None

    monkeypatch.setattr(OrchestratorCore, "_verify_and_repair", _no_battery)

    result_task = await orchestrator.run_task(task_id)

    assert result_task.state == TaskState.FAILED
    assert "store.py" in (result_task.error_message or "")
    assert "pricing.py" in (result_task.error_message or "")
    assert verify_calls == []  # the battery never judged the incomplete set


@pytest.mark.asyncio
async def test_run_task_backstop_leaves_complete_build_alone(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.core.orchestrator import OrchestratorCore
    from app.memory.models import TaskState

    task_id = "frg010backstopok"
    _plant_project(
        fs_tool,
        task_id,
        {
            "models.py": MODELS_CODE,
            "store.py": STORE_CODE,
            "pricing.py": PRICING_CODE,
            "main.py": MAIN_CODE,
        },
        R3_MANIFEST,
    )
    task, graph = _task_and_graph(task_id, TaskState.COMPLETED)
    task.state = TaskState.COMPLETED
    store = _FakeStore(task, graph)
    registry = _FakeRegistry()
    orchestrator = _orchestrator(fs_tool, store, registry)

    verify_calls: list[str] = []

    async def _battery(self, task_id_):
        verify_calls.append(task_id_)
        return None

    monkeypatch.setattr(OrchestratorCore, "_verify_and_repair", _battery)

    result_task = await orchestrator.run_task(task_id)

    assert result_task.state == TaskState.COMPLETED
    assert verify_calls == [task_id]
