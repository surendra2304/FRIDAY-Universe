"""TASK-FRG-003: Forge build reliability, round 2 -- regression defences.

Production evidence (2026-11-15, FRG-003 acceptance battery against the
deployed Forge; all five goals were NEW):

  * Run 1 (task21515112026072807, roman numerals) and Run 2
    (task22115112026075654, temperature conversion) both ended
    PARTIAL_FAILURE with the code satisfying the stated goal. All 7
    failing generated tests asserted an imagined contract: exact
    error-message strings that exist nowhere in the code
    (``"Kelvin temperature cannot be below absolute zero"``), a private
    helper the implementation never had (``temperature._validate_kelvin``,
    monkeypatched by the tests), lowercase rejection the implementation
    deliberately does not perform (``from_roman`` uppercases its input),
    and import-error handling the entry point never wrote. Root cause:
    TesterRole handed Inference's generate-tests ONLY main.py, so the
    test author invented every other module's contract.

  * Run 3 (task22215112026080942, inventory) ended FAILED at the tester
    gate, yet its final verification manifest reads all_passed=True --
    because the delivered models.py defines pricing's functions and a
    full Inventory class and registers them as ``sys.modules["pricing"]``
    and ``sys.modules["store"]`` at import time. store.py and pricing.py
    do not exist in the delivered project; the battery exercised phantom
    modules. No write path defended against module impersonation.

  * Run 4 (task22515112026084702, text statistics) had a module damaged
    mid-build into a syntactically invalid state (an appended broken
    ``def``, injected by this task's sabotage watcher at 14:22:00 IST).
    The battery indicted it precisely (file and line), but no recovery
    route could repair an unparseable file: the deterministic rescue
    covers only the escape-corrupted shape and the patch routes match
    snippets of existing text. The create route's channel could have
    authored the module -- it was never reachable for a file that exists.

These tests pin the three defences:
  1. TesterRole grounds test synthesis in ALL implementation sources.
  2. The filesystem write boundary refuses sys.modules impersonation of
     another module (create and edit paths; repair stays possible).
  3. The recovery ladder gains a last-resort ``regenerate`` route that
     recreates an unparseable project module through the create route's
     channel and gates.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.filesystem import FilesystemTool
from app.execution.permissions import PermissionManager


@pytest.fixture()
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def fs_tool(temp_dir: Path) -> FilesystemTool:
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    return FilesystemTool(wm=wm, pm=PermissionManager())


# ---------------------------------------------------------------------------
# Defence 2: sys.modules impersonation refused at the write boundary
# ---------------------------------------------------------------------------

# The Run-3 shape, distilled: a "models" module that fabricates the two
# modules synthesis never created.
PHANTOM_MODELS = (
    "import sys\n"
    "import types\n"
    "\n"
    "def apply_discount(price_cents: int, percent: float) -> int:\n"
    "    return int(price_cents * (100 - percent) / 100)\n"
    "\n"
    '_pricing_module = types.ModuleType("pricing")\n'
    "_pricing_module.apply_discount = apply_discount\n"
    'sys.modules["pricing"] = _pricing_module\n'
    "\n"
    "class Inventory:\n"
    "    def __init__(self):\n"
    "        self._items = []\n"
    "\n"
    '_store_module = types.ModuleType("store")\n'
    "_store_module.Inventory = Inventory\n"
    'sys.modules.setdefault("store", _store_module)\n'
)


def test_create_file_refuses_phantom_module_registration(fs_tool: FilesystemTool):
    with pytest.raises(ValueError, match="stand-in module"):
        fs_tool.create_file(
            task_id="frg003", relative_path="models.py",
            content=PHANTOM_MODELS, role="developer",
        )
    # Refused means NOT persisted: the workspace must not contain the file.
    assert fs_tool.search_files("frg003", pattern="*.py", role="developer") == []


def test_impersonation_shapes_are_all_detected(fs_tool: FilesystemTool):
    shapes = [
        'import sys\nsys.modules["store"] = object()\n',
        # Run 5's exact shape: stand-in package via setdefault + ModuleType.
        'import sys\nfrom types import ModuleType\n'
        'sys.modules.setdefault("salespipe", ModuleType("salespipe"))\n',
        'import sys\nsys.modules.update({"store": object()})\n',
        'import sys\nsys.modules.update(store=object())\n',
        'import sys\nsys.modules.__setitem__("store", object())\n',
        'import sys\nx: object = None\nsys.modules["store"] = x\n',
    ]
    for index, content in enumerate(shapes):
        with pytest.raises(ValueError, match="stand-in module"):
            fs_tool.create_file(
                task_id=f"frg003shape{index}", relative_path="models.py",
                content=content, role="developer",
            )


def test_self_registration_and_computed_keys_stay_allowed(fs_tool: FilesystemTool):
    # A module registering ITSELF under its own name is legitimate.
    fs_tool.create_file(
        task_id="frg003self", relative_path="models.py",
        content='import sys\nsys.modules["models"] = sys.modules[__name__]\n',
        role="developer",
    )
    # A computed key cannot be proven to impersonate: left alone.
    fs_tool.create_file(
        task_id="frg003self", relative_path="registry.py",
        content="import sys\ndef register(name, module):\n    sys.modules[name] = module\n",
        role="developer",
    )
    # Ordinary code is persisted byte-identical.
    ordinary = "def add(a, b):\n    return a + b\n"
    fs_tool.create_file(
        task_id="frg003self", relative_path="calc.py",
        content=ordinary, role="developer",
    )
    assert fs_tool.read_file("frg003self", "calc.py", role="developer") == ordinary


def test_package_init_may_register_its_package_name(fs_tool: FilesystemTool):
    fs_tool.create_file(
        task_id="frg003pkg", relative_path="inventory/__init__.py",
        content='import sys\nsys.modules["inventory"] = sys.modules[__name__]\n',
        role="developer",
    )


def test_edit_file_refuses_new_impersonation_but_allows_repair(fs_tool: FilesystemTool):
    fs_tool.create_file(
        task_id="frg003edit", relative_path="models.py",
        content="def helper():\n    return 1\n", role="developer",
    )
    with pytest.raises(ValueError, match="stand-in module"):
        fs_tool.edit_file(
            task_id="frg003edit", relative_path="models.py",
            target_content="def helper():\n    return 1\n",
            replacement_content=(
                "def helper():\n    return 1\n\n"
                "import sys\n"
                'sys.modules["store"] = object()\n'
            ),
            role="developer",
        )
    # A file that ALREADY impersonates (written before the guard, or by a
    # path outside the boundary) can still be edited -- including the edit
    # that removes the impersonation.
    fs_tool.wm.create_workspace("frg003legacy")
    paths = fs_tool.wm.get_workspace_paths("frg003legacy")
    (paths.project / "models.py").write_text(PHANTOM_MODELS, encoding="utf-8")
    fs_tool.edit_file(
        task_id="frg003legacy", relative_path="models.py",
        target_content='sys.modules["pricing"] = _pricing_module\n',
        replacement_content="",
        role="developer",
    )
    remaining = fs_tool.read_file("frg003legacy", "models.py", role="developer")
    assert 'sys.modules["pricing"]' not in remaining


# ---------------------------------------------------------------------------
# Defence 1: test synthesis grounded in all implementation sources
# ---------------------------------------------------------------------------


class _GroundingFS:
    """Stub FS: a two-module project whose helper module carries a
    distinctive error string the test author can only know by seeing it."""

    MAIN = "from temperature import c_to_k\n\nprint(c_to_k(25.0))\n"
    TEMPERATURE = (
        "def c_to_k(celsius: float) -> float:\n"
        "    kelvin = celsius + 273.15\n"
        "    if kelvin < 0:\n"
        '        raise ValueError("Resulting Kelvin temperature is below absolute zero.")\n'
        "    return kelvin\n"
    )

    def __init__(self):
        self._files = {"main.py": self.MAIN, "temperature.py": self.TEMPERATURE}

    def search_files(self, task_id, pattern, role):
        if pattern == "*.py":
            return sorted(self._files)
        if pattern == "test_*.py":
            return []
        return []

    def read_file(self, task_id, path, role):
        return self._files[path]


def test_implementation_sources_bundle_contains_every_module():
    from app.agents.roles import TesterRole

    role = TesterRole(provider=None)
    engine = SimpleNamespace(fs=_GroundingFS())
    bundle = role._implementation_sources("task_x", engine)
    assert "### File: main.py" in bundle
    assert "### File: temperature.py" in bundle
    assert "Resulting Kelvin temperature is below absolute zero." in bundle


def test_implementation_sources_excludes_test_files():
    from app.agents.roles import TesterRole

    class _FS(_GroundingFS):
        def __init__(self):
            super().__init__()
            self._files["test_main.py"] = "def test_x():\n    pass\n"
            self._files["conftest.py"] = ""

    role = TesterRole(provider=None)
    bundle = role._implementation_sources("task_x", SimpleNamespace(fs=_FS()))
    assert "test_main.py" not in bundle
    assert "conftest.py" not in bundle


def test_implementation_sources_falls_back_to_main_when_listing_fails():
    from app.agents.roles import TesterRole

    class _FS:
        def search_files(self, task_id, pattern, role):
            raise RuntimeError("listing unavailable")

        def read_file(self, task_id, path, role):
            assert path == "main.py"
            return "print('main only')\n"

    role = TesterRole(provider=None)
    assert role._implementation_sources("task_x", SimpleNamespace(fs=_FS())) == (
        "print('main only')\n"
    )


class _CapturingTestClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def generate_tests(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "test_code": "def test_smoke():\n    assert True\n",
            "generation_status": "ok",
            "error": None,
        }


class _WritableGroundingFS(_GroundingFS):
    def create_file(self, task_id, relative_path, content, role):
        self._files[relative_path] = content
        return relative_path

    def search_files(self, task_id, pattern, role):
        if pattern == "*.py":
            return sorted(self._files)
        if pattern == "test_*.py":
            return sorted(n for n in self._files if n.startswith("test_"))
        return []


@pytest.mark.asyncio
async def test_tester_synthesis_hands_all_sources_to_generate_tests(
    monkeypatch, tmp_path
):
    from unittest.mock import AsyncMock

    from app.agents.roles import TesterRole
    from app.integrations import ai_universe_client

    client = _CapturingTestClient()
    monkeypatch.setattr(
        ai_universe_client, "get_ai_universe_client", lambda: client
    )

    class _StubProvider:
        async def generate(self, prompt, system_prompt=None, temperature=0.2):
            return SimpleNamespace(
                content="",
                usage=SimpleNamespace(total_tokens=0, estimated_cost_usd=0.0),
            )

    engine = SimpleNamespace(
        fs=_WritableGroundingFS(),
        wm=SimpleNamespace(
            get_workspace_paths=lambda task_id: SimpleNamespace(project=tmp_path)
        ),
        terminal=SimpleNamespace(
            run_command=AsyncMock(
                return_value=SimpleNamespace(
                    exit_code=0, stdout="1 passed", stderr="", command="pytest"
                )
            )
        ),
    )
    role = TesterRole(provider=_StubProvider())
    await role.execute_step(
        task_id="task_frg003_grounding",
        node_title="Automated Test Suite & Verification Gate",
        context={"goal": "temperature conversion library", "requirements": []},
        engine=engine,
    )

    assert len(client.calls) == 1
    code_arg = client.calls[0]["code"]
    # On clean main the code argument is main.py's content alone; the
    # helper module's real error text can only be present if the test
    # author was grounded in the module it tests.
    assert "### File: temperature.py" in code_arg
    assert "Resulting Kelvin temperature is below absolute zero." in code_arg


# ---------------------------------------------------------------------------
# Defence 3: the recovery ladder can regenerate an unparseable module
# ---------------------------------------------------------------------------


class _FakeAIClient:
    """Stands in for the Inference code channel (REL-028 pattern)."""

    def __init__(self, answer: str, confidence: float = 0.95):
        self._answer = answer
        self._confidence = confidence
        self.calls = 0

    async def generate_code(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            answer=self._answer, confidence=self._confidence, run_id="frg003-test"
        )


class _StubStore:
    def __init__(self, goal: str):
        self._goal = goal

    async def get_task(self, task_id: str):
        return SimpleNamespace(goal=self._goal, requirements=[])


_REGEN_GOAL = (
    "Create a Python text-statistics project: a module textstats.py with "
    "functions word_count(text), unique_words(text) and top_words(text, n); "
    "and a main.py that imports these functions from textstats.py."
)

_BROKEN_TEXTSTATS = (
    "def word_count(text):\n"
    "    return len(text.split())\n"
    "\n"
    "\n"
    "def frg003_sabotage_broken(:\n"
    "    pass\n"
)

_GOOD_TEXTSTATS = (
    "def word_count(text):\n"
    "    return len(text.split())\n"
    "\n"
    "\n"
    "def unique_words(text):\n"
    "    return len(set(text.lower().split()))\n"
    "\n"
    "\n"
    "def top_words(text, n):\n"
    "    counts = {}\n"
    "    for word in text.lower().split():\n"
    "        counts[word] = counts.get(word, 0) + 1\n"
    "    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]\n"
)


def _recovery_engine(fs_tool: FilesystemTool, goal: str):
    from app.recovery.engine import RecoveryEngine
    from app.recovery.repair import PatchApplicator

    exec_engine = SimpleNamespace(fs=fs_tool)
    return RecoveryEngine(
        exec_engine=exec_engine,
        applicator=PatchApplicator(engine=exec_engine),
        store=_StubStore(goal),
    )


def _syntax_diagnosis(file: str = "textstats.py"):
    from app.recovery.classifier import FailureClass, FailureDiagnosis

    return FailureDiagnosis(
        failure_class=FailureClass.SYNTAX_ERROR,
        failing_file=file,
        error_message=(
            f"Syntax errors detected in 1 files: "
            f"[{{'file': '{file}', 'line': 6, 'offset': 28, "
            f"'text': 'def frg003_sabotage_broken('}}]"
        ),
        suggested_strategy="Inspect syntax error line and fix grammar.",
    )


def _plant_broken_module(fs_tool: FilesystemTool, task_id: str) -> None:
    fs_tool.wm.create_workspace(task_id)
    paths = fs_tool.wm.get_workspace_paths(task_id)
    (paths.project / "textstats.py").write_text(_BROKEN_TEXTSTATS, encoding="utf-8")


@pytest.mark.asyncio
async def test_regenerate_route_recreates_unparseable_module(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "frg003regen"
    _plant_broken_module(fs_tool, task_id)
    fake = _FakeAIClient(_GOOD_TEXTSTATS)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )
    engine = _recovery_engine(fs_tool, _REGEN_GOAL)

    patch = await engine._regenerate_unparseable_module_patch(
        task_id, _syntax_diagnosis(), "textstats.py"
    )
    assert patch is not None
    assert patch.patch_type == "rewrite"
    assert patch.target_file == "textstats.py"
    assert fake.calls == 1

    assert engine.applicator.apply_patch(task_id, patch, role="debugger") is True
    written = fs_tool.read_file(task_id, "textstats.py", role="debugger")
    namespace: dict = {}
    exec(compile(written, "textstats.py", "exec"), namespace)
    assert namespace["word_count"]("a b c") == 3
    assert namespace["top_words"]("b a b", 1) == [("b", 2)]


@pytest.mark.asyncio
async def test_regenerate_route_gates(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.recovery.classifier import FailureClass, FailureDiagnosis

    task_id = "frg003regengates"
    _plant_broken_module(fs_tool, task_id)
    fake = _FakeAIClient(_GOOD_TEXTSTATS)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )
    engine = _recovery_engine(fs_tool, _REGEN_GOAL)

    # Other failure classes never reach the provider.
    other = FailureDiagnosis(
        failure_class=FailureClass.DEPENDENCY_MISSING,
        error_message="No module named 'textstats'",
        suggested_strategy="create it",
    )
    assert (
        await engine._regenerate_unparseable_module_patch(task_id, other, "textstats.py")
        is None
    )
    assert fake.calls == 0

    # A file the goal/spec never names is not regenerated.
    engine_unnamed = _recovery_engine(fs_tool, "Build a calculator CLI in main.py")
    assert (
        await engine_unnamed._regenerate_unparseable_module_patch(
            task_id, _syntax_diagnosis(), "textstats.py"
        )
        is None
    )
    assert fake.calls == 0

    # Below the fleet's 0.70 confidence bar, no regeneration either.
    low = _FakeAIClient(_GOOD_TEXTSTATS, confidence=0.5)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: low
    )
    assert (
        await engine._regenerate_unparseable_module_patch(
            task_id, _syntax_diagnosis(), "textstats.py"
        )
        is None
    )
    assert low.calls == 1


@pytest.mark.asyncio
async def test_regenerate_route_leaves_parseable_files_alone(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "frg003regenok"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="textstats.py",
        content=_GOOD_TEXTSTATS, role="developer",
    )
    fake = _FakeAIClient(_GOOD_TEXTSTATS)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )
    engine = _recovery_engine(fs_tool, _REGEN_GOAL)
    assert (
        await engine._regenerate_unparseable_module_patch(
            task_id, _syntax_diagnosis(), "textstats.py"
        )
        is None
    )
    assert fake.calls == 0
