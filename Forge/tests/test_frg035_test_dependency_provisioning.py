"""
TASK-FRG-035 checkpoint 2: Forge sandbox test-dependency provisioning.

Proves the pre-battery step that closes the FRG-036 Leg B failure
(``ModuleNotFoundError: No module named 'aiosqlite'`` at collection):
declared test dependencies are installed before any test executes, and a
provisioning failure fails the test stage CLOSED with the real reason
instead of a misleading pytest collection error.

No test here touches the network or the real interpreter environment: the
installer and the importability check are injected fakes. The two
TestChecker tests use the real WorkspaceManager/ExecutionEngine fixture
shape from Forge/tests/unit/test_verification.py.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import TestChecker
from app.verification.provisioning import (
    ProvisionResult,
    provision_test_dependencies,
    resolve_test_requirements,
)


@pytest.fixture
def verification_context(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return {"wm": wm, "engine": engine, "task_id": "test_frg035_task"}


def _write(project: Path, name: str, content: str) -> Path:
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- resolution -----------------------------------------------------------


def test_resolve_prefers_requirements_ci(tmp_path: Path):
    _write(tmp_path, "requirements-ci.txt", "aiosqlite>=0.20,<1\npytest>=7.4.0\n")
    _write(tmp_path, "requirements.txt", "requests>=2.31.0\n")
    specs, source = resolve_test_requirements(tmp_path)
    assert specs == ["aiosqlite>=0.20,<1", "pytest>=7.4.0"]
    assert source.startswith("requirements-ci.txt")


def test_resolve_falls_back_to_ast_when_no_manifest(tmp_path: Path):
    _write(
        tmp_path,
        "tests/conftest.py",
        "import aiosqlite\nimport os\n",
    )
    _write(tmp_path, "tests/test_x.py", "def test_x():\n    assert True\n")
    specs, source = resolve_test_requirements(tmp_path)
    assert specs == ["aiosqlite"]
    assert "AST scan" in source
    # stdlib (os) is never provisioned, and the project itself is not a dep.


def test_resolve_empty_project_is_noop(tmp_path: Path):
    specs, source = resolve_test_requirements(tmp_path)
    assert specs == []


# --- provisioning (fake installer / fake importability) -------------------


@pytest.mark.asyncio
async def test_provision_installs_only_the_missing_declared_dep(tmp_path: Path):
    _write(tmp_path, "requirements-ci.txt", "aiosqlite>=0.20,<1\npytest>=7.4.0\n")
    calls: list[list[str]] = []

    async def fake_installer(task_id, engine, specs):
        calls.append(list(specs))
        return SimpleNamespace(exit_code=0, timed_out=False, stdout="", stderr="")

    # aiosqlite missing, pytest present: only the missing spec is installed.
    result = await provision_test_dependencies(
        "t1",
        None,
        tmp_path,
        installer=fake_installer,
        importable=lambda name: name != "aiosqlite",
    )
    assert result.ok is True
    assert calls == [["aiosqlite>=0.20,<1"]]
    assert len(result.installed) == 1
    assert result.installed[0].startswith("aiosqlite")


@pytest.mark.asyncio
async def test_provision_noop_when_everything_importable(tmp_path: Path):
    _write(tmp_path, "requirements-ci.txt", "aiosqlite>=0.20,<1\n")
    calls: list[list[str]] = []

    async def fake_installer(task_id, engine, specs):
        calls.append(list(specs))
        return SimpleNamespace(exit_code=0, timed_out=False, stdout="", stderr="")

    result = await provision_test_dependencies(
        "t1", None, tmp_path, installer=fake_installer, importable=lambda name: True
    )
    assert result.ok is True
    assert calls == []
    assert result.installed == []
    assert result.already_satisfied == ["aiosqlite>=0.20,<1"]


@pytest.mark.asyncio
async def test_provision_noop_when_nothing_declared(tmp_path: Path):
    calls: list[list[str]] = []

    async def fake_installer(task_id, engine, specs):
        calls.append(list(specs))
        return SimpleNamespace(exit_code=0, timed_out=False, stdout="", stderr="")

    result = await provision_test_dependencies(
        "t1", None, tmp_path, installer=fake_installer, importable=lambda name: True
    )
    assert result.ok is True
    assert calls == []
    assert "nothing to provision" in result.summary


@pytest.mark.asyncio
async def test_provision_fails_closed_on_install_failure(tmp_path: Path):
    _write(tmp_path, "requirements-ci.txt", "aiosqlite>=0.20,<1\n")
    calls: list[list[str]] = []

    async def failing_installer(task_id, engine, specs):
        calls.append(list(specs))
        return SimpleNamespace(
            exit_code=1,
            timed_out=False,
            stdout="",
            stderr="ERROR: Could not find a version that satisfies the requirement",
        )

    result = await provision_test_dependencies(
        "t1",
        None,
        tmp_path,
        installer=failing_installer,
        importable=lambda name: False,
    )
    assert result.ok is False
    assert "aiosqlite" in result.reason
    assert "install FAILED" in result.reason
    assert "Could not find a version" in result.reason
    assert len(calls) == 1  # one attempt, no retry loop


@pytest.mark.asyncio
async def test_provision_refuses_banned_package_without_installing(tmp_path: Path):
    _write(tmp_path, "requirements-ci.txt", "pycrypto>=2.6\naiosqlite>=0.20,<1\n")
    calls: list[list[str]] = []

    async def fake_installer(task_id, engine, specs):
        calls.append(list(specs))
        return SimpleNamespace(exit_code=0, timed_out=False, stdout="", stderr="")

    result = await provision_test_dependencies(
        "t1", None, tmp_path, installer=fake_installer, importable=lambda name: False
    )
    assert result.ok is False
    assert "pycrypto" in result.reason
    assert "REFUSED" in result.reason
    assert calls == []  # nothing was installed


# --- TestChecker hook -----------------------------------------------------


@pytest.mark.asyncio
async def test_testchecker_fails_closed_when_provisioning_fails(verification_context):
    wm: WorkspaceManager = verification_context["wm"]
    engine: ExecutionEngine = verification_context["engine"]
    task_id = "test_frg035_fail_closed"

    wm.write_project_file(task_id, "test_math.py", "def test_sum():\n    assert 1 + 1 == 2\n")
    wm.write_project_file(task_id, "requirements-ci.txt", "aiosqlite>=0.20,<1\n")
    calls: list[str] = []

    async def failing_provision(task_id_arg, engine_arg, project_dir):
        calls.append(str(project_dir))
        return ProvisionResult(
            ok=False,
            source="requirements-ci.txt (1 entries)",
            declared=["aiosqlite>=0.20,<1"],
            reason="Test-dependency install FAILED (exit=1) for: aiosqlite>=0.20,<1.",
        )

    checker = TestChecker(provision_fn=failing_provision)
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is False
    assert evidence.exit_code == 1
    # The failure is reported as the provisioning stage, NOT as a pytest
    # collection error -- so the test file was never executed.
    assert evidence.check_name == "Test Dependency Provisioning"
    assert "aiosqlite" in (evidence.stderr or "")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_testchecker_provisions_then_runs_tests(verification_context):
    wm: WorkspaceManager = verification_context["wm"]
    engine: ExecutionEngine = verification_context["engine"]
    task_id = "test_frg035_provision_then_run"

    wm.write_project_file(task_id, "test_math.py", "def test_sum():\n    assert 1 + 1 == 2\n")
    wm.write_project_file(task_id, "requirements-ci.txt", "aiosqlite>=0.20,<1\n")

    async def ok_provision(task_id_arg, engine_arg, project_dir):
        return ProvisionResult(
            ok=True,
            source="requirements-ci.txt (1 entries)",
            declared=["aiosqlite>=0.20,<1"],
            installed=["aiosqlite==0.22.1"],
            reason="Provisioned 1 missing test dependencies.",
        )

    checker = TestChecker(provision_fn=ok_provision)
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert evidence.check_name == "Pytest Test Suite Runner"
    assert "Provisioned test dependencies: aiosqlite==0.22.1" in (evidence.stdout or "")
