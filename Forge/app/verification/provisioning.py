"""
TASK-FRG-035 checkpoint 2: pre-battery provisioning of declared test
dependencies for the Forge verification path.

The failure it closes (TASK-FRG-036 Leg B, TP4 evidence section 4): the
battery collects the cloned project's test suite inside the task workspace
and the collection dies with ``ModuleNotFoundError: No module named
'aiosqlite'`` -- not because the code is wrong, but because the sandbox
never provisioned the project's own declared test dependencies. The
``DependencyManager`` already knew how to resolve them (AST extraction +
PyPI name mapping); nothing ever installed them before ``TestChecker`` ran.

The provisioning step runs inside ``TestChecker`` after test discovery and
before any test executes:

* resolve the declared list from the cloned project's own manifests
  (``requirements-ci.txt`` first -- the repo's CI test surface, where
  ``aiosqlite`` is declared -- then ``requirements-test.txt``, then
  ``requirements.txt``), falling back to an AST scan of the test files only;
* refuse banned / compromised packages fail-closed, without installing
  anything (``DependencyManager.check_security``);
* install only what is missing from the battery interpreter
  (``sys.executable`` -- the interpreter ``pytest_command`` already uses),
  via the sandboxed terminal with ``allow_network=True``; pip needs the
  network, and the install is of the project's own declared manifest, the
  same trust level as executing its tests (sandbox review finding F-2);
* fail CLOSED when the install fails, times out, or is denied: the test
  stage reports the provisioning failure with the real reason instead of
  letting pytest report a misleading collection error.

A project with no declared third-party test dependencies is a no-op pass:
provisioning never blocks a stdlib-only suite. Installs are recorded
(distribution + version) and surfaced on the test evidence so the
verification manifest names exactly what was provisioned.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.core.logging import get_logger
from app.execution.dependency_manager import (
    MODULE_TO_PYPI,
    PYTHON_STDLIB,
    DependencyManager,
)

logger = get_logger("verification.provisioning")

# Manifest search order. requirements-ci.txt is the repo's CI test surface
# (it declares aiosqlite); a project-level requirements.txt is the generic
# fallback. Only the FIRST manifest found is used -- the lists are
# alternatives, not layers.
TEST_REQUIREMENT_MANIFESTS = (
    "requirements-ci.txt",
    "requirements-test.txt",
    "requirements.txt",
)

# PyPI name (lowercased) -> top-level import name, for the cases where the
# naive normalisation (lowercase, '-' -> '_') names the wrong module.
# The reverse of DependencyManager.MODULE_TO_PYPI covers most of these
# (beautifulsoup4 -> bs4, opencv-python -> cv2, ...); the extras below are
# names that mapping does not know.
_PYPI_TO_IMPORT_EXTRA: dict[str, str] = {
    "python-multipart": "multipart",
    "google-genai": "google",
    "google-api-python-client": "googleapiclient",
    "python-binance": "binance",
}

_PYPI_TO_IMPORT: dict[str, str] = {
    pypi.lower(): module for module, pypi in MODULE_TO_PYPI.items()
}
_PYPI_TO_IMPORT.update(_PYPI_TO_IMPORT_EXTRA)


def _requirement_name(spec: str) -> str:
    """Distribution name from a requirement spec (bounds, extras, markers stripped)."""
    return re.split(r"[=<>!~\[;\s]", spec.strip(), maxsplit=1)[0].strip()


def _import_name(dist_name: str) -> str:
    """Top-level import name for a distribution (best effort).

    A wrong guess here costs at most one redundant, idempotent pip install:
    success is decided by pip's exit code, never by this mapping.
    """
    key = dist_name.lower()
    if key in _PYPI_TO_IMPORT:
        return _PYPI_TO_IMPORT[key]
    return key.replace("-", "_")


def _parse_requirements_file(path: Path) -> list[str]:
    specs: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith("-"):
            continue
        specs.append(stripped)
    return specs


def _ast_test_dependencies(project_dir: Path) -> list[str]:
    """Third-party imports of the test files only (fallback, no manifest).

    Scans test_*.py and conftest.py anywhere under the project, drops the
    standard library and modules provided by the project tree itself, and
    maps the rest to PyPI names. Test files only: the failure mode being
    closed is test collection, and runtime-only imports are the
    RuntimeChecker's business, not this step's.
    """
    dm = DependencyManager()
    test_files = sorted(
        set(project_dir.rglob("test_*.py")) | set(project_dir.rglob("conftest.py"))
    )
    deps: set[str] = set()
    for test_file in test_files:
        try:
            code = test_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.debug(f"Could not read {test_file} for dependency scan: {exc}")
            continue
        for module in dm.extract_python_imports(code):
            if module in PYTHON_STDLIB:
                continue
            if (project_dir / f"{module}.py").exists() or (project_dir / module).is_dir():
                continue
            deps.add(MODULE_TO_PYPI.get(module, module))
    return sorted(deps)


def resolve_test_requirements(project_dir: Path) -> tuple[list[str], str]:
    """Declared test dependencies and where they came from.

    Returns (specs, source). An empty spec list means the project declares
    no third-party test dependencies -- a no-op, not an error.
    """
    for name in TEST_REQUIREMENT_MANIFESTS:
        manifest = project_dir / name
        if manifest.is_file():
            specs = _parse_requirements_file(manifest)
            return specs, f"{name} ({len(specs)} entries)"
    test_files = sorted(
        set(project_dir.rglob("test_*.py")) | set(project_dir.rglob("conftest.py"))
    )
    return _ast_test_dependencies(project_dir), (
        f"AST scan of {len(test_files)} test file(s) (no requirements manifest found)"
    )


@dataclass
class ProvisionResult:
    """Outcome of one provisioning attempt."""

    ok: bool
    reason: str = ""
    source: str = ""
    declared: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)
    already_satisfied: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.installed:
            return (
                f"Provisioned test dependencies: {', '.join(self.installed)} "
                f"(source: {self.source})."
            )
        if self.declared:
            return (
                f"Test dependencies already satisfied: {len(self.declared)} declared "
                f"(source: {self.source})."
            )
        return "No third-party test dependencies declared; nothing to provision."


def _is_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        # A name find_spec cannot resolve is treated as missing: pip install
        # of the declared spec is idempotent, so the worst case is one
        # redundant install, never a false fail-closed.
        return False


async def _default_installer(task_id: str, engine: Any, specs: list[str]) -> Any:
    """Install specs into the battery interpreter via the sandboxed terminal.

    The command is built with shlex-quoted specs: version bounds contain
    ``>``/``<`` which the shell would otherwise read as redirection.
    ``allow_network=True`` is required -- pip fetches from the index -- and
    is permitted by the command policy (pip is not a denied tool; sandbox
    review F-2 records installs of the project's own manifest as acceptable
    on the same trust level as executing its tests).
    """
    command = (
        f'"{sys.executable}" -m pip install -q --disable-pip-version-check '
        + " ".join(shlex.quote(spec) for spec in specs)
    )
    return await engine.terminal.run_command(
        task_id, command, timeout_seconds=120, role="tester", allow_network=True
    )


async def provision_test_dependencies(
    task_id: str,
    engine: Any,
    project_dir: Path,
    *,
    installer: Callable[[str, Any, list[str]], Awaitable[Any]] | None = None,
    importable: Callable[[str], bool] | None = None,
) -> ProvisionResult:
    """Ensure the project's declared test dependencies are importable
    before the battery collects the suite. Fail-closed on every path that
    cannot establish that: banned package, install failure, timeout, or
    policy denial. Never raises for a provisioning problem -- the failure
    is the returned result, so the caller can report it as evidence.
    """
    specs, source = resolve_test_requirements(project_dir)
    if not specs:
        return ProvisionResult(
            ok=True,
            source=source,
            reason="No third-party test dependencies declared; nothing to provision.",
        )

    # Security gate FIRST: a banned/compromised package is refused without
    # any install being attempted -- never pip-install a known-malicious
    # distribution into the battery interpreter.
    names = {_requirement_name(spec) for spec in specs}
    issues = DependencyManager().check_security(names)
    if issues:
        detail = "; ".join(f"{i['package']}: {i['reason']}" for i in issues)
        logger.warning(f"Refusing to provision banned dependency for task {task_id}: {detail}")
        return ProvisionResult(
            ok=False,
            source=source,
            declared=sorted(specs),
            reason=(
                "Test-dependency provisioning REFUSED: banned/vulnerable package "
                f"in the declared list -- {detail}. Failing closed; the battery "
                "cannot collect the suite."
            ),
        )

    check_importable = importable or _is_importable
    missing = [
        spec
        for spec in specs
        if not check_importable(_import_name(_requirement_name(spec)))
    ]
    if not missing:
        return ProvisionResult(
            ok=True,
            source=source,
            declared=sorted(specs),
            already_satisfied=sorted(specs),
            reason="All declared test dependencies already importable.",
        )

    install = installer or _default_installer
    try:
        result = await install(task_id, engine, missing)
    except Exception as exc:  # installer transport failure fails closed
        logger.warning(f"Test-dependency install raised for task {task_id}: {exc}")
        return ProvisionResult(
            ok=False,
            source=source,
            declared=sorted(specs),
            reason=(
                f"Test-dependency install raised {type(exc).__name__}: {exc}. "
                "Failing closed; the battery cannot collect the suite."
            ),
        )
    if getattr(result, "timed_out", False) or getattr(result, "exit_code", 1) != 0:
        output = (getattr(result, "stderr", "") or getattr(result, "stdout", "") or "").strip()
        tail = "\n".join(output.splitlines()[-5:]) if output else "(no installer output)"
        return ProvisionResult(
            ok=False,
            source=source,
            declared=sorted(specs),
            reason=(
                "Test-dependency install FAILED "
                f"(exit={getattr(result, 'exit_code', '?')}"
                f"{', timed out' if getattr(result, 'timed_out', False) else ''}) "
                f"for: {', '.join(missing)}. Installer output:\n{tail}\n"
                "Failing closed; the battery cannot collect the suite "
                "until these are provisioned."
            ),
        )

    installed: list[str] = []
    for spec in missing:
        name = _requirement_name(spec)
        try:
            version = importlib.metadata.version(name)
        except Exception:
            version = "unknown"
        installed.append(f"{name}=={version}" if version != "unknown" else name)
    logger.info(f"Provisioned test dependencies for task {task_id}: {installed}")
    return ProvisionResult(
        ok=True,
        source=source,
        declared=sorted(specs),
        installed=installed,
        reason=f"Provisioned {len(installed)} missing test dependencies.",
    )
