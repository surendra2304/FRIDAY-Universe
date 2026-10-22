"""
Regression tests for three real bugs found by actually running FORGE as a
real user would and inspecting its generated output under `ruff` and live
execution (not just "does it compile" / "does pytest pass"):

1. `_print_table`'s empty-state message was emitted as an f-string with no
   placeholders (`f"No {plural}..."` where `plural` had already been spliced
   in at generation time), tripping ruff's F541. This went unnoticed for a
   long time because `LintChecker` invoked a bare `ruff` executable that was
   not on the verification subprocess's PATH, so the check silently reported
   a false "skipped/passed" result instead of ever truly running.
2. The generated CLI test file (`_cli_tests`) always imported `json` even
   though nothing in the emitted test body ever uses it, tripping F401 for
   the same underlying masked-by-broken-PATH reason.
3. `main()`'s generated command dispatch was one long if/elif chain with
   cyclomatic complexity of 20, over `CodeQualityComplexityChecker`'s
   threshold of 15 -- refactored into small `_cmd_*` handlers plus a
   dispatch dict.

A fourth bug was introduced and caught *during the fix* for #3: the first
refactor accidentally emitted the literal source text
`"Added ' + ent + ' #"` into generated files instead of concatenating the
real entity name in at generation time, producing `Added ' + ent + ' #1`
at runtime instead of `Added todo #1`. These tests exercise the actual
emitted source and the actual runtime behavior, so a regression here fails
loudly instead of silently shipping a broken CLI.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from app.agents.synthesis import GoalSpec, _cli_main, _cli_tests


def _todo_spec() -> GoalSpec:
    return GoalSpec(
        raw="Build a CLI todo app with JSON persistence",
        name="todo",
        entity="todo",
        entity_plural="todos",
        commands=["add", "list", "delete", "update", "complete", "clear", "search", "count"],
    )


def _ruff_available() -> bool:
    return shutil.which("ruff") is not None or _module_importable("ruff")


def _module_importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def test_cli_print_table_empty_message_has_no_stray_fstring_prefix():
    """The empty-state message must be a plain string, not a placeholder-free
    f-string (ruff F541). Regression for bug #1."""
    src = _cli_main(_todo_spec())
    assert 'print(f"No todos' not in src
    assert 'print("No todos yet. Use \'add\' to create one.")' in src


def test_cli_tests_do_not_import_unused_json():
    """Regression for bug #2: the generated test module must not import
    `json` when nothing in its body references it."""
    src = _cli_tests(_todo_spec())
    tree = ast.parse(src)
    imports_json = any(
        isinstance(node, ast.Import) and any(alias.name == "json" for alias in node.names)
        for node in ast.walk(tree)
    )
    uses_json = "json." in src.replace("import json", "")
    if imports_json:
        assert uses_json, "generated test file imports `json` but never uses it (F401)"


def test_generated_cli_main_has_low_cyclomatic_complexity():
    """Regression for bug #3: main() must stay well under the
    CodeQualityComplexityChecker threshold of 15."""
    src = _cli_main(_todo_spec())
    tree = ast.parse(src)
    main_fn = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    complexity = 1 + sum(
        1
        for n in ast.walk(main_fn)
        if isinstance(n, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler))
    )
    assert complexity <= 10, f"main() complexity regressed to {complexity}"


@pytest.mark.skipif(not _ruff_available(), reason="ruff not installed in this environment")
def test_generated_cli_project_is_ruff_clean():
    """Run the real linter against real generated output -- not just
    py_compile. This is the check that would have caught bugs #1 and #2
    immediately, and is exactly the check that FORGE itself runs on every
    build via LintChecker."""
    spec = _todo_spec()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "main.py").write_text(_cli_main(spec), encoding="utf-8")
        (tmp_path / "test_main.py").write_text(_cli_tests(spec), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                ".",
                "--no-cache",
                "--select=E,F",
                "--ignore=E501,F841",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"ruff found issues in generated CLI project:\n{proc.stdout}"


def test_generated_cli_runs_and_reports_correct_entity_name():
    """End-to-end regression for the 4th bug (introduced and caught during
    this session's own fix): `add` must print the real entity name, not the
    literal source text `' + ent + '` that a botched code-generator edit
    produced."""
    spec = _todo_spec()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "main.py").write_text(_cli_main(spec), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "main.py", "add", "--title", "Buy milk"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Added todo #1" in proc.stdout
        assert "' + ent + '" not in proc.stdout
