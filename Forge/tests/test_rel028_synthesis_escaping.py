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

These tests pin the three defences added by TASK-REL-028:
  1. the deterministic syntax repair can rescue the verbatim artifact;
  2. the filesystem write boundary normalizes escape-corrupted .py content
     and refuses still-invalid .py content instead of persisting it;
  3. the orchestrator's final syntax-rescue sweep rewrites unparseable
     workspace files (however they got there) with compile-validated repairs.

The artifact fixture below is the exact production file, base64-encoded so
the test source itself cannot accidentally re-escape or normalize it.
"""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_create_file_non_python_untouched(fs_tool: FilesystemTool):
    fs_tool.create_file(
        task_id="rel028", relative_path="notes.txt",
        content=PRODUCTION_ARTIFACT, role="developer",
    )
    assert fs_tool.read_file("rel028", "notes.txt", role="developer") == PRODUCTION_ARTIFACT


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
