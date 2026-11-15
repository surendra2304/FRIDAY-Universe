"""TASK-FRG-008: tests for the Output Security Gate battery checker.

The gate wraps OutputSecurityScanner (previously reachable only via the
opt-in Sentinel paths) plus extended AST rules for path traversal,
extended deserialization, os.popen/exec-family and dynamic shell flags.
It must fail the verification battery on CRITICAL/HIGH findings in
generated code, and fail closed when there is nothing to scan or the
scanner itself errors.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.verification import security_gate
from app.verification.security_gate import OutputSecurityGateChecker


def _engine_with_project(tmp_path, files):
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = project / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    engine = MagicMock()
    engine.wm.get_workspace_paths.return_value = SimpleNamespace(project=project)
    return engine


CLEAN = {"main.py": "def main():\n    print('hello')\n\n\nif __name__ == '__main__':\n    main()\n"}


@pytest.mark.asyncio
async def test_clean_project_passes(tmp_path):
    engine = _engine_with_project(tmp_path, CLEAN)
    evidence = await OutputSecurityGateChecker().run_check("t-clean", engine)
    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert evidence.issues == []


@pytest.mark.asyncio
async def test_missing_workspace_fails_closed(tmp_path):
    engine = MagicMock()
    engine.wm.get_workspace_paths.return_value = None
    evidence = await OutputSecurityGateChecker().run_check("t-missing", engine)
    assert evidence.passed is False
    assert evidence.exit_code != 0
    assert "no workspace project" in (evidence.stderr or "").lower()


@pytest.mark.asyncio
async def test_scanner_exception_fails_closed(tmp_path, monkeypatch):
    engine = _engine_with_project(tmp_path, CLEAN)

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("scanner exploded")

    monkeypatch.setattr(security_gate, "OutputSecurityScanner", Boom)
    evidence = await OutputSecurityGateChecker().run_check("t-boom", engine)
    assert evidence.passed is False
    assert "failing closed" in (evidence.stderr or "").lower()


@pytest.mark.asyncio
async def test_subprocess_shell_true_blocks(tmp_path):
    files = {"main.py": "import subprocess\n\ndef go(cmd):\n    subprocess.run(cmd, shell=True)\n"}
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-shell", engine)
    assert evidence.passed is False
    assert any("shell=True" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_eval_blocks(tmp_path):
    files = {"main.py": "def go(expr):\n    return eval(expr)\n"}
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-eval", engine)
    assert evidence.passed is False
    assert any("eval" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_pickle_and_unsafe_yaml_block(tmp_path):
    files = {
        "main.py": (
            "import pickle\nimport yaml\n\n"
            "def load(blob, text):\n"
            "    a = pickle.loads(blob)\n"
            "    b = yaml.load(text)\n"
            "    return a, b\n"
        )
    }
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-deser", engine)
    assert evidence.passed is False
    rules = [i["rule"] for i in evidence.issues]
    assert any("pickle" in r for r in rules)
    assert any("YAML" in r for r in rules)


@pytest.mark.asyncio
async def test_marshal_blocks_via_extended_rules(tmp_path):
    files = {"main.py": "import marshal\n\ndef load(blob):\n    return marshal.loads(blob)\n"}
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-marshal", engine)
    assert evidence.passed is False
    assert any("marshal" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_os_popen_blocks_via_extended_rules(tmp_path):
    files = {"main.py": "import os\n\ndef go(cmd):\n    return os.popen(cmd)\n"}
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-popen", engine)
    assert evidence.passed is False
    assert any("os.popen" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_dynamic_shell_flag_blocks_via_extended_rules(tmp_path):
    files = {
        "main.py": (
            "import subprocess\n\n"
            "def go(cmd, use_shell):\n"
            "    subprocess.run(cmd, shell=use_shell)\n"
        )
    }
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-dynshell", engine)
    assert evidence.passed is False
    assert any("unverifiable shell flag" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_path_traversal_dynamic_open_blocks(tmp_path):
    files = {
        "main.py": (
            "BASE = '/srv/files'\n\n"
            "def read(name):\n"
            "    return open(BASE + '/' + name).read()\n"
        )
    }
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-traversal", engine)
    assert evidence.passed is False
    assert any("Path Traversal" in i["rule"] for i in evidence.issues)


@pytest.mark.asyncio
async def test_hardcoded_secret_blocks(tmp_path):
    fake_key = "AKIA" + "B" * 16  # synthetic fixture value, not a real credential
    files = {"config.py": f'AWS_KEY = "{fake_key}"\n'}
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-secret", engine)
    assert evidence.passed is False
    assert any("Secret" in i["rule"] for i in evidence.issues)
    # The evidence must never embed the secret value itself.
    assert fake_key not in str(evidence.issues)
    assert fake_key not in (evidence.stderr or "")
    assert fake_key not in (evidence.stdout or "")


@pytest.mark.asyncio
async def test_production_finding_shape_blocks(tmp_path):
    """Regression shape for the real production finding class found by
    TASK-FRG-008 in a past Forge build: subprocess.run(<f-string>, shell=True)."""
    files = {
        "main.py": (
            "import subprocess\n\n"
            "def kill(pid):\n"
            "    subprocess.run(f'kill -TERM -{pid}', shell=True, check=False)\n"
        )
    }
    engine = _engine_with_project(tmp_path, files)
    evidence = await OutputSecurityGateChecker().run_check("t-prod-shape", engine)
    assert evidence.passed is False


def test_gate_registered_in_default_battery():
    from app.verification.engine import VerificationEngine

    engine = VerificationEngine(engine=MagicMock(), wm=MagicMock())
    names = [type(ch).__name__ for ch in engine.checkers]
    assert "OutputSecurityGateChecker" in names
