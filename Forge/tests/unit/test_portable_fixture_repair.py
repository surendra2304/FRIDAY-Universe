"""Equivalent public imports may fix fixtures; assertions still cannot change."""
import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agents.repair import validate_replacement
from app.agents.roles import DebuggerRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import TestChecker

OLD = '''import pathlib
import tempfile
import unittest

def identity(value):
    return value

class ResourceFixture(unittest.TestCase):
    def make_file(self):
        fd, path = tempfile.mkstemp()
        pathlib.os.close(fd)
        self.addCleanup(pathlib.Path(path).unlink)
        return pathlib.Path(path)
    def test_resource(self):
        path = self.make_file()
        self.assertTrue(path.is_file())
        self.assertEqual(identity(42), 42)
'''
NEW = OLD.replace('import pathlib\n', 'import pathlib\nimport os\n').replace('pathlib.os.close(fd)', 'os.close(fd)')


def test_public_os_import_preserves_all_test_logic():
    assert validate_replacement(OLD, NEW) is None
    assert ast.dump(ast.parse(OLD).body[-1].body[-1]) == ast.dump(ast.parse(NEW).body[-1].body[-1])


@pytest.mark.parametrize('candidate', [
    NEW.replace('self.assertEqual(identity(42), 42)', 'self.assertTrue(True)'),
    NEW.replace('def test_resource(self):', '@unittest.skip("ignore")\n    def test_resource(self):'),
    NEW.replace('self.assertTrue(path.is_file())', 'pass'),
    NEW.replace('self.addCleanup(pathlib.Path(path).unlink)', 'pass'),
    NEW.replace('os.close(fd)', 'os.close(0)'),
    NEW + '\nos = object()\n',
    NEW + '\nos.close = lambda fd: None\n',
    NEW + '\nimport math as os\n',
    NEW + '\nfrom arbitrary import *\n',
    NEW.replace('def make_file(self):', 'def make_file(self, os=None):'),
])
def test_only_import_equivalence_is_allowed_not_weakened_tests_or_shadowing(candidate):
    assert validate_replacement(OLD, candidate) is not None


def test_shadowed_old_pathlib_binding_is_not_assumed_to_mean_stdlib():
    assert validate_replacement(OLD + '\npathlib.os = object()\n', NEW) is not None


@pytest.mark.asyncio
async def test_real_py313_failure_model_patch_and_suite_rerun(tmp_path, monkeypatch):
    from app.integrations import ai_universe_client
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path/'workspaces'))
    wm.write_project_file('fixture', 'main.py', OLD)
    engine = ExecutionEngine(wm=wm)
    initial = await TestChecker().run_check('fixture', engine)
    # On Python3.13 pathlib no longer re-exports os; older runtimes can still
    # exercise the repair and assert the unchanged suite really runs.
    if not hasattr(__import__('pathlib'), 'os'):
        assert not initial.passed and 'AttributeError' in initial.stderr
    generate = AsyncMock(return_value=SimpleNamespace(answer=NEW, confidence=0.92))
    monkeypatch.setattr(ai_universe_client, 'get_ai_universe_client', lambda: SimpleNamespace(generate_code=generate))
    result = await DebuggerRole().execute_step('fixture', 'repair', {
        'goal': 'Portable resource fixture on Python3.12/3.13',
        'project_files': ['main.py'], 'error': initial.stderr}, engine)
    assert result['fixed_files'] == ['main.py']
    checked = await TestChecker().run_check('fixture', engine)
    assert checked.passed and checked.exit_code == 0 and 'Ran 1 test' in checked.stderr


def test_equivalence_cannot_downgrade_public_import_to_private_export():
    assert validate_replacement(NEW, OLD) is not None
