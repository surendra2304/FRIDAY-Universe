"""Static unittest discovery, including suites embedded in application modules.

Discovery never imports or executes project source. Execution remains inside the
permission-checked terminal. Merely having a TestCase name is not passing evidence.
"""
from __future__ import annotations

import ast
import os
import re
import shlex
import sys
from pathlib import Path

_EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def discover_unittest_targets(project: Path) -> list[str]:
    targets = []
    for path in sorted(project.rglob("*.py")):
        relative = path.relative_to(project)
        if set(relative.parts) & _EXCLUDED or path.is_symlink():
            continue
        parts = list(relative.with_suffix("").parts)
        if not all(part.isidentifier() for part in parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError, OSError):
            continue  # The build checker reports malformed source separately.
        modules = {"unittest"}
        bases = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                modules.update(alias.asname or alias.name for alias in node.names if alias.name == "unittest")
            elif isinstance(node, ast.ImportFrom) and node.module == "unittest":
                bases.update(alias.asname or alias.name for alias in node.names
                             if alias.name in {"TestCase", "IsolatedAsyncioTestCase"})
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        known = set(bases)
        # Resolve same-module inheritance without importing arbitrary project code.
        for _ in classes:
            for node in classes:
                if any(isinstance(base, ast.Name) and base.id in known
                       or isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                       and base.value.id in modules and base.attr in {"TestCase", "IsolatedAsyncioTestCase"}
                       for base in node.bases):
                    known.add(node.name)
        for node in classes:
            if node.name in known and any(isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                                         and method.name.startswith("test") for method in node.body):
                targets.append(".".join(parts + [node.name]))
    return targets


def unittest_command(targets: list[str]) -> str:
    runner = f'"{sys.executable}" -B -m unittest'
    return runner + (" -v " + " ".join(shlex.quote(target) for target in targets)
                     if targets else " discover -v")


def unittest_executed(stdout: str, stderr: str) -> bool:
    """unittest exits zero for an empty suite: that is not successful testing."""
    counts = re.findall(r"Ran\s+(\d+)\s+tests?\b", stdout + "\n" + stderr)
    return bool(counts) and int(counts[-1]) > 0


def pytest_command(files: list[str] | None = None, *, project: Path | None = None) -> str:
    """Never inherit the hosting repository's pytest options or conftest files."""
    config = os.devnull
    if project:
        for name, section in [("pytest.ini", None), (".pytest.ini", None),
                              ("pyproject.toml", "[tool.pytest.ini_options]"),
                              ("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]")]:
            path = project / name
            if path.is_file() and (section is None or section in path.read_text(encoding="utf-8")):
                config = name  # Honor only the delivered project's own config.
                break
    command = (f'"{sys.executable}" -B -m pytest -v -p no:cacheprovider '
               f'-c {shlex.quote(config)} --rootdir=. --confcutdir=.')
    if files:
        command += " " + " ".join(shlex.quote(path) for path in sorted(set(files)))
    return command
