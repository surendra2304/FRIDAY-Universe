"""TASK-REL-028: synthesized Python files landed on disk in string-escaped form.

Production evidence (2026-11-15, tasks task18314112026184644 and
task18414112026185142): both delegate builds ended PARTIAL_FAILURE because the
project's string_utils.py contained literal backslash-n sequences instead of
newlines -- 451 bytes, byte-identical across the two builds, and rejected by
py_compile with "unexpected character after line continuation character".
No role ever wrote that file through the workspace tools: the generated
main.py materialized it at import time while the verification battery ran,
one main.py revision held the embedded source un-decoded, and the file's
own exists-guard then froze the corrupted artifact in place. Forge had no
defence at any layer: the write boundary persisted any .py content, the
deterministic repair had no candidate for this shape, and the agent repair
refuses unparseable files as targets.

These tests pin the defences added by TASK-REL-028:
  1. the deterministic syntax repair can rescue the verbatim artifact;
  2. the filesystem write boundary normalizes escape-corrupted .py content
     and refuses still-invalid .py content instead of persisting it;
  3. the orchestrator's final syntax-rescue sweep rewrites unparseable
     workspace files (however they got there) with compile-validated repairs;
  4. the recovery ladder's create route can create a project module that
     verification proved missing (the manifest never listed string_utils.py,
     so in the follow-up acceptance run nothing corrupt existed -- the file
     was simply absent, and no existing route could create it);
  5. the write boundary repairs the generated tests' parent.parent
     sibling-path misconception when Forge's flat layout is provably the
     real one (acceptance runs 3 and 4 died at test collection on it);
  6. the write boundary refuses a module that unconditionally raises at
     import time (acceptance run 5: a repair patch rewrote the working
     module into a simulated import failure).

The artifact fixture below is the exact production file, base64-encoded so
the test source itself cannot accidentally re-escape or normalize it.
"""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from app.recovery.classifier import FailureDiagnosis
    from app.recovery.engine import RecoveryEngine
    from app.verification.evidence import VerificationEvidence

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.filesystem import FilesystemTool
from app.execution.permissions import PermissionManager
from app.recovery.syntax_repair import _repair_python_source, _unescape_literal_escapes

# Verbatim project/string_utils.py from task18314112026184644 (451 bytes).
PRODUCTION_ARTIFACT = base64.b64decode(
    "aW1wb3J0IHJlXG5cbmRlZiBpc19wYWxpbmRyb21lKHM6IHN0cikgLT4gYm9vbDpcbiAgICAiIiJSZXR1cm4gYGBUcnVlYGAgaWYg"
    "KnMqIHJlYWRzIHRoZSBzYW1lIGZvcndhcmRzIGFuZCBiYWNrd2FyZHMsCiAgICBpZ25vcmluZyBjYXNlIGFuZCBub23igJFhbHBo"
    "YW51bWVyaWMgY2hhcmFjdGVycy4KXG4gICAgUGFyYW1ldGVyc1xuICAgIC0tLS0tLS0tLS1cbiAgICBzOiBzdHJcbiAgICAgICAg"
    "SW5wdXQgc3RyaW5nIHRvIHRlc3QuXG5cbiAgICBSZXR1cm5zXG4gICAgLS0tLS0tLVxuICAgIGJvb2xcbiAgICAgICAgYGBUcnVl"
    "YGAgd2hlbiAqcyogaXMgYSBwYWxpbmRyb21lLCBgYEZhbHNlYGAgb3RoZXJ3aXNlLlxuICAgICIiIlxuICAgIGNsZWFuZWQgPSBy"
    "ZS5zdWIociJbXkEtWmEtejAtOV0iLCAiIiwgcykubG93ZXIoKVxuICAgIHJldHVybiBjbGVhbmVkID09IGNsZWFuZWRbOjotMV1c"
    "bg=="
).decode("utf-8")


def _exec_is_palindrome(source: str):
    namespace: dict = {}
    exec(compile(source, "string_utils.py", "exec"), namespace)
    return namespace["is_palindrome"]


def test_fixture_is_the_unparseable_production_shape():
    assert len(PRODUCTION_ARTIFACT.encode("utf-8")) == 451
    assert PRODUCTION_ARTIFACT.count("\\n") == 16
    with pytest.raises(SyntaxError):
        compile(PRODUCTION_ARTIFACT, "string_utils.py", "exec")


def test_unescape_signature_gate():
    # Ordinary multi-line code whose strings contain escaped newlines is NOT
    # corruption: real newlines dominate, so the rescue must not fire.
    ordinary = 'def f():\n    return "a\\nb"\n\n\ndef g():\n    return "c\\nd"\n'
    assert _unescape_literal_escapes(ordinary) is None
    # Too few escapes: not the wholesale-corruption shape.
    assert _unescape_literal_escapes("x = 1\\ny = 2") is None
    # An escaped backslash followed by 'n' stays literal text, not a newline.
    decoded = _unescape_literal_escapes("a\\\\nb\\nc\\nd\\ne")
    assert decoded is not None
    assert decoded.splitlines()[0] == "a\\nb"


def test_repair_rescues_production_artifact():
    repaired = _repair_python_source(PRODUCTION_ARTIFACT)
    assert repaired is not None
    compile(repaired, "string_utils.py", "exec")
    is_palindrome = _exec_is_palindrome(repaired)
    assert is_palindrome("A man a plan a canal Panama") is True
    assert is_palindrome("Racecar") is True
    assert is_palindrome("hello") is False
    # Non-ASCII text survives byte-identical (no unicode_escape mojibake):
    # the docstring's non-breaking hyphen U+2011 must still be present.
    assert "\u2011" in repaired


@pytest.fixture
def fs_tool(temp_dir: Path) -> FilesystemTool:
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    return FilesystemTool(wm=wm, pm=PermissionManager())


def test_create_file_normalizes_escape_corrupted_python(fs_tool: FilesystemTool):
    fs_tool.create_file(
        task_id="rel028", relative_path="string_utils.py",
        content=PRODUCTION_ARTIFACT, role="developer",
    )
    written = fs_tool.read_file("rel028", "string_utils.py", role="developer")
    compile(written, "string_utils.py", "exec")
    assert _exec_is_palindrome(written)("hello") is False


def test_create_file_rejects_unfixable_python(fs_tool: FilesystemTool):
    with pytest.raises(ValueError, match="syntactically invalid"):
        fs_tool.create_file(
            task_id="rel028", relative_path="broken.py",
            content="def broken(:\n    pass\n", role="developer",
        )
    with pytest.raises(FileNotFoundError):
        fs_tool.read_file("rel028", "broken.py", role="developer")


def test_create_file_leaves_valid_python_byte_identical(fs_tool: FilesystemTool):
    valid = 'def f():\n    return "line1\\nline2\\nline3"\n'
    fs_tool.create_file(
        task_id="rel028", relative_path="ok.py", content=valid, role="developer"
    )
    assert fs_tool.read_file("rel028", "ok.py", role="developer") == valid


_PARENT_PARENT_TEST = (
    "import pathlib as _pathlib\n\n"
    'SCRIPT_PATH = _pathlib.Path(__file__).parent.parent / "main.py"\n'
)


def test_write_boundary_repairs_parent_parent_sibling_path(
    fs_tool: FilesystemTool,
):
    """Verbatim shape from production tasks task189/task190: the generated
    suite loaded the code under test one directory too high and died at
    collection with FileNotFoundError, even though main.py sat beside it.
    The write boundary drops the spurious hop when the flat layout is
    provably the real one, and the stored file then resolves correctly."""
    task_id = "rel028sibling"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="main.py",
        content="def main() -> int:\n    return 0\n", role="developer",
    )
    fs_tool.create_file(
        task_id=task_id, relative_path="test_main.py",
        content=_PARENT_PARENT_TEST, role="tester",
    )
    stored = fs_tool.read_file(task_id, "test_main.py", role="tester")
    assert "parent.parent" not in stored
    assert '.parent / "main.py"' in stored

    paths = fs_tool.wm.get_workspace_paths(task_id)
    assert paths is not None
    namespace: dict = {"__file__": str(paths.project / "test_main.py")}
    exec(compile(stored, "test_main.py", "exec"), namespace)
    assert namespace["SCRIPT_PATH"] == paths.project / "main.py"
    assert namespace["SCRIPT_PATH"].exists()


def test_sibling_path_repair_only_when_flat_layout_is_provable(
    fs_tool: FilesystemTool,
):
    # A copy one level up makes parent.parent CORRECT -- leave it alone.
    task_id = "rel028siblingnested"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="main.py",
        content="def main() -> int:\n    return 0\n", role="developer",
    )
    paths = fs_tool.wm.get_workspace_paths(task_id)
    assert paths is not None
    (paths.root / "main.py").write_text("def main() -> int:\n    return 1\n")
    fs_tool.create_file(
        task_id=task_id, relative_path="test_main.py",
        content=_PARENT_PARENT_TEST, role="tester",
    )
    assert fs_tool.read_file(task_id, "test_main.py", role="tester") == _PARENT_PARENT_TEST

    # No sibling at all: the reference may be intentional -- leave it alone.
    task_id = "rel028siblingabsent"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="test_main.py",
        content=_PARENT_PARENT_TEST, role="tester",
    )
    assert fs_tool.read_file(task_id, "test_main.py", role="tester") == _PARENT_PARENT_TEST


_SIMULATED_RAISE_MODULE = (
    '"""Utility module."""\n\n'
    'raise ImportError("Simulated import failure for string_utils")\n'
)


def test_create_file_refuses_top_level_raise_module(fs_tool: FilesystemTool):
    """Verbatim shape from production task19314112026203137: a repair patch
    rewrote the working recovery-created string_utils.py into a module that
    raises ImportError at import time to satisfy an import-error test --
    after which the runtime check could never pass. A module that
    unconditionally raises at import can never be a valid deliverable, so
    the write boundary refuses it like unparseable content."""
    task_id = "rel028raise"
    fs_tool.wm.create_workspace(task_id)
    with pytest.raises(ValueError, match="unconditionally raises at import"):
        fs_tool.create_file(
            task_id=task_id, relative_path="string_utils.py",
            content=_SIMULATED_RAISE_MODULE, role="debugger",
        )
    assert fs_tool.search_files(task_id, "*.py", role="debugger") == []

    # A raise nested in a guard is legitimate and stays writable.
    nested = (
        "import sys\n\n"
        "if sys.version_info < (3, 0):\n"
        "    raise ImportError('Python 3 required')\n"
    )
    fs_tool.create_file(
        task_id=task_id, relative_path="guarded.py", content=nested, role="developer"
    )
    assert fs_tool.read_file(task_id, "guarded.py", role="developer") == nested


def test_edit_file_cannot_introduce_top_level_raise(fs_tool: FilesystemTool):
    task_id = "rel028editraise"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="mod.py",
        content="VALUE = 1\n", role="developer",
    )
    with pytest.raises(ValueError, match="unconditionally raise at import"):
        fs_tool.edit_file(
            task_id=task_id, relative_path="mod.py",
            target_content="VALUE = 1",
            replacement_content='raise ImportError("Simulated import failure")',
            role="debugger",
        )
    assert fs_tool.read_file(task_id, "mod.py", role="developer") == "VALUE = 1\n"

    # Repairing an already-broken file stays allowed.
    paths = fs_tool.wm.get_workspace_paths(task_id)
    assert paths is not None
    (paths.project / "broken.py").write_text(_SIMULATED_RAISE_MODULE)
    fs_tool.edit_file(
        task_id=task_id, relative_path="broken.py",
        target_content='raise ImportError("Simulated import failure for string_utils")',
        replacement_content="VALUE = 2",
        role="debugger",
    )
    assert "VALUE = 2" in fs_tool.read_file(task_id, "broken.py", role="debugger")


def test_create_file_non_python_untouched(fs_tool: FilesystemTool):
    fs_tool.create_file(
        task_id="rel028", relative_path="notes.txt",
        content=PRODUCTION_ARTIFACT, role="developer",
    )
    assert fs_tool.read_file("rel028", "notes.txt", role="developer") == PRODUCTION_ARTIFACT


class _FakeAIClient:
    """Stands in for the Inference code channel the Developer role uses."""

    def __init__(self, answer: str, confidence: float = 0.95):
        self._answer = answer
        self._confidence = confidence
        self.calls = 0

    async def generate_code(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            answer=self._answer, confidence=self._confidence, run_id="rel028-test"
        )


class _StubStore:
    def __init__(self, goal: str):
        self._goal = goal

    async def get_task(self, task_id: str):
        return SimpleNamespace(goal=self._goal, requirements=[])


_GOOD_MODULE = (
    "import re\n\n\n"
    "def is_palindrome(s: str) -> bool:\n"
    '    cleaned = re.sub(r"[^A-Za-z0-9]", "", s).lower()\n'
    "    return cleaned == cleaned[::-1]\n"
)

_GOAL = (
    "Create a small Python project: a module string_utils.py with a function "
    "is_palindrome(s: str) -> bool, and a main.py that demonstrates it."
)


def _recovery_engine(fs_tool: FilesystemTool, goal: str) -> "RecoveryEngine":
    from app.recovery.engine import RecoveryEngine
    from app.recovery.repair import PatchApplicator

    exec_engine = SimpleNamespace(fs=fs_tool)
    return RecoveryEngine(
        exec_engine=exec_engine,
        applicator=PatchApplicator(engine=exec_engine),
        store=_StubStore(goal),
    )


def _missing_module_diagnosis(module: str = "string_utils") -> "FailureDiagnosis":
    from app.recovery.classifier import FailureClass, FailureDiagnosis

    return FailureDiagnosis(
        failure_class=FailureClass.DEPENDENCY_MISSING,
        error_message=f"ModuleNotFoundError: No module named '{module}'",
        suggested_strategy="Add missing module or correct import path in project source.",
    )


async def test_create_route_creates_missing_project_module(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    from app.recovery.classifier import FailureClass, FailureDiagnosis

    task_id = "rel028create"
    fs_tool.wm.create_workspace(task_id)
    fs_tool.create_file(
        task_id=task_id, relative_path="test_main.py",
        content="import string_utils\n", role="developer",
    )
    fake = _FakeAIClient(_GOOD_MODULE)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )
    engine = _recovery_engine(fs_tool, _GOAL)

    patch = await engine._create_missing_module_patch(task_id, _missing_module_diagnosis())
    assert patch is not None
    assert patch.patch_type == "create"
    assert patch.target_file == "string_utils.py"
    assert fake.calls == 1

    assert engine.applicator.apply_patch(task_id, patch, role="debugger") is True
    written = fs_tool.read_file(task_id, "string_utils.py", role="debugger")
    assert _exec_is_palindrome(written)("Racecar") is True

    # Once the file exists, the route must not recreate it.
    assert (
        await engine._create_missing_module_patch(task_id, _missing_module_diagnosis())
        is None
    )
    assert fake.calls == 1

    # Other failure classes never reach the provider at all.
    other = FailureDiagnosis(
        failure_class=FailureClass.SYNTAX_ERROR,
        error_message="SyntaxError: invalid syntax",
        suggested_strategy="fix grammar",
    )
    assert await engine._create_missing_module_patch(task_id, other) is None
    assert fake.calls == 1


async def test_create_route_gates(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    task_id = "rel028gates"
    fs_tool.wm.create_workspace(task_id)
    fake = _FakeAIClient(_GOOD_MODULE)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )

    # A stdlib name is an environment problem, never a project file -- even
    # when the goal text happens to name it.
    engine = _recovery_engine(fs_tool, "Build a tool around os.py and string_utils.py")
    assert (
        await engine._create_missing_module_patch(task_id, _missing_module_diagnosis("os"))
        is None
    )
    assert fake.calls == 0

    # Without project evidence (goal/spec never name the file), no creation.
    engine = _recovery_engine(fs_tool, "Build a calculator CLI in main.py")
    assert (
        await engine._create_missing_module_patch(task_id, _missing_module_diagnosis())
        is None
    )
    assert fake.calls == 0

    # Below the fleet's 0.70 confidence bar, no creation either.
    low = _FakeAIClient(_GOOD_MODULE, confidence=0.5)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: low
    )
    engine = _recovery_engine(fs_tool, _GOAL)
    assert (
        await engine._create_missing_module_patch(task_id, _missing_module_diagnosis())
        is None
    )
    assert low.calls == 1


def _evidence(text: str) -> "VerificationEvidence":
    from app.verification.evidence import CheckCategory, VerificationEvidence

    return VerificationEvidence(
        check_name="Runtime CLI / Service Smoke Check",
        category=CheckCategory.RUNTIME,
        passed=False,
        exit_code=1,
        stdout=text,
        stderr="",
    )


def test_classifier_names_missing_module_in_fleet_phrasings():
    """The classifier must recognize the missing-module phrasings the fleet
    actually emits and name the module file as the repair target. On the
    pre-fix classifier the runtime smoke phrasing fell through to UNKNOWN
    (production task18814112026194737), so recovery never saw a
    dependency_missing diagnosis to act on."""
    from app.recovery.classifier import FailureClass, FailureClassifier

    classifier = FailureClassifier()
    phrasings = [
        # Runtime smoke checker, verbatim from the production report.
        "Critical error: Failed to import the required module 'string_utils'. "
        "Ensure it is present in the PYTHONPATH.",
        # Wrapper raised by this run's generated main.py.
        "ImportError: Failed to import module 'string_utils'.",
        # The other wrapper shape generated code uses.
        "ImportError: Failed to import 'is_palindrome' from 'string_utils'.",
        # The interpreter's own phrasing (test-collection failures).
        "ModuleNotFoundError: No module named 'string_utils'",
    ]
    for text in phrasings:
        diagnosis = classifier.classify(_evidence(text))
        assert diagnosis.failure_class == FailureClass.DEPENDENCY_MISSING, text
        assert diagnosis.failing_file == "string_utils.py", text


async def test_create_route_accepts_classifier_named_module(
    fs_tool: FilesystemTool, monkeypatch: pytest.MonkeyPatch
):
    """End to end at unit level: the runtime phrasing classifies to a
    diagnosis whose failing_file alone drives the create route (the error
    text contains no 'No module named')."""
    from app.recovery.classifier import FailureClassifier

    task_id = "rel028runtime"
    fs_tool.wm.create_workspace(task_id)
    fake = _FakeAIClient(_GOOD_MODULE)
    monkeypatch.setattr(
        "app.integrations.ai_universe_client.get_ai_universe_client", lambda: fake
    )
    engine = _recovery_engine(fs_tool, _GOAL)
    diagnosis = FailureClassifier().classify(
        _evidence(
            "Critical error: Failed to import the required module 'string_utils'. "
            "Ensure it is present in the PYTHONPATH."
        )
    )
    patch = await engine._create_missing_module_patch(task_id, diagnosis)
    assert patch is not None
    assert patch.patch_type == "create"
    assert patch.target_file == "string_utils.py"


def test_orchestrator_rescue_sweep_repairs_materialized_file(
    fs_tool: FilesystemTool, temp_dir: Path
):
    # Simulate runtime materialization: the corrupted file appears on disk
    # without ever passing through create_file (a generated program wrote
    # it while it ran).
    task_id = "rel028sweep"
    paths = fs_tool.wm.create_workspace(task_id)
    (paths.project / "string_utils.py").write_text(PRODUCTION_ARTIFACT, encoding="utf-8")

    orchestrator = OrchestratorCore.__new__(OrchestratorCore)
    orchestrator.engine = SimpleNamespace(fs=fs_tool)

    rescued = orchestrator._rescue_unparseable_files(task_id)
    assert rescued == ["string_utils.py"]
    healed = fs_tool.read_file(task_id, "string_utils.py", role="debugger")
    compile(healed, "string_utils.py", "exec")
    assert _exec_is_palindrome(healed)("Racecar") is True
    # A second sweep is a no-op once everything parses.
    assert orchestrator._rescue_unparseable_files(task_id) == []
