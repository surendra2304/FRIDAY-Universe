"""Real local terminal regressions; provider fixtures are explicitly not live builds."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agents.coordinator import AgentCoordinator, ReviewFinding
from app.agents.roles import TesterRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import TestChecker
from app.verification.python_tests import discover_unittest_targets

SOURCE = '''import csv
import io
import unittest
from pathlib import Path

def convert(text):
    return list(csv.DictReader(io.StringIO(text)))

class EmbeddedCSV(unittest.TestCase):
    def test_quoted_comma(self):
        self.assertEqual(convert('name,city\\n"Doe, Jane",Guntur\\n'),
                         [{'name': 'Doe, Jane', 'city': 'Guntur'}])
    def test_empty(self):
        self.assertEqual(convert(''), [])
'''


def make_engine(tmp_path, source=SOURCE):
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path / 'workspaces'))
    wm.write_project_file('fixture', 'main.py', source)
    return ExecutionEngine(wm=wm)


@pytest.mark.asyncio
async def test_embedded_unittest_is_really_executed(tmp_path):
    engine = make_engine(tmp_path)
    evidence = await TestChecker().run_check('fixture', engine)
    assert evidence.passed, evidence.stderr
    assert evidence.exit_code == 0
    assert '-m unittest -v main.EmbeddedCSV' in evidence.command
    assert 'Ran 2 tests' in evidence.stderr
    assert 'test_quoted_comma' in evidence.stderr and 'test_empty' in evidence.stderr
    assert evidence.artifacts_inspected == ['main.py']


@pytest.mark.asyncio
async def test_tester_uses_embedded_suite_without_unnecessary_provider_call(tmp_path, monkeypatch):
    from app.integrations import ai_universe_client
    engine = make_engine(tmp_path)
    def forbidden():
        raise AssertionError('Existing embedded tests must not trigger model generation')
    monkeypatch.setattr(ai_universe_client, 'get_ai_universe_client', forbidden)
    role = TesterRole()
    role.prompt_model = AsyncMock(side_effect=AssertionError('unexpected fallback'))
    result = await role.execute_step('fixture', 'test', {'goal': 'CSV converter with unittest'}, engine)
    assert result['exit_code'] == 0
    assert 'Ran 2 tests' in result['stderr']
    role.prompt_model.assert_not_called()
    assert engine.fs.read_file('fixture', 'main.py') == SOURCE


@pytest.mark.asyncio
async def test_unused_import_repair_cannot_regenerate_working_csv_release(tmp_path, monkeypatch):
    from app.agents import roles
    engine = make_engine(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Lint repair must not regenerate the file manifest')
    monkeypatch.setattr(roles, 'DeveloperRole', forbidden)
    monkeypatch.setattr(roles, 'DebuggerRole', forbidden)
    result = await AgentCoordinator(engine, goal='CSV converter with unittest').review_and_repair('fixture')
    assert result.clean, result.summary
    assert result.repairs == ['main.py']
    repaired = engine.fs.read_file('fixture', 'main.py')
    assert repaired == SOURCE.replace('from pathlib import Path\n', '')
    evidence = await TestChecker().run_check('fixture', engine)
    assert evidence.passed and 'Ran 2 tests' in evidence.stderr


@pytest.mark.asyncio
async def test_debugger_receives_original_goal_requirements_and_files_no_developer_fallback(tmp_path, monkeypatch):
    from app.agents import roles
    engine = make_engine(tmp_path)
    execute = AsyncMock(return_value={'fixed_files': []})
    monkeypatch.setattr(roles, 'DebuggerRole', lambda: SimpleNamespace(execute_step=execute))
    def forbidden(*args, **kwargs):
        raise AssertionError('DeveloperRole is not a patch-oriented repair fallback')
    monkeypatch.setattr(roles, 'DeveloperRole', forbidden)
    coordinator = AgentCoordinator(engine, goal='CSV converter', requirements=['quoted commas', 'empty input'])
    findings = [ReviewFinding('test_engineer', 'Custom Test Failure', 'high', 'assertion failed')]
    assert await coordinator.delegate_repair('fixture', findings) == []
    context = execute.call_args.kwargs['context']
    assert context['goal'] == 'CSV converter'
    assert context['requirements'] == ['quoted commas', 'empty input']
    assert context['project_files'] == ['main.py']
    assert engine.fs.read_file('fixture', 'main.py') == SOURCE


@pytest.mark.asyncio
async def test_unknown_objective_refuses_model_repair(tmp_path, monkeypatch):
    from app.agents import roles
    engine = make_engine(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Missing objective must fail closed')
    monkeypatch.setattr(roles, 'DebuggerRole', forbidden)
    findings = [ReviewFinding('code_reviewer', 'Ruff', 'medium', 'F401 main.py', 'main.py')]
    assert await AgentCoordinator(engine).delegate_repair('fixture', findings) == []
    assert engine.fs.read_file('fixture', 'main.py') == SOURCE


@pytest.mark.asyncio
async def test_zero_unittest_exit_zero_is_not_passing_evidence(tmp_path):
    # AST contains a real TestCase method, but dynamic code removes it at import.
    engine = make_engine(tmp_path, SOURCE + '\nEmbeddedCSV.test_quoted_comma = None\nEmbeddedCSV.test_empty = None\n')
    evidence = await TestChecker().run_check('fixture', engine)
    assert not evidence.passed and evidence.exit_code != 0
    assert 'Ran 0 tests' in evidence.stderr
    assert 'No unittest tests were executed' in evidence.stderr
    result = await TesterRole().execute_step('fixture', 'test', {'goal': 'use unittest'}, engine)
    assert result['status'] == 'failed' and result['exit_code'] != 0


@pytest.mark.asyncio
async def test_mixed_pytest_and_embedded_unittest_both_run(tmp_path):
    engine = make_engine(tmp_path)
    engine.wm.write_project_file('fixture', 'test_extra.py', 'def test_extra():\n    assert True\n')
    evidence = await TestChecker().run_check('fixture', engine)
    assert evidence.passed, evidence.stderr
    assert '3 passed' in evidence.stdout
    assert 'main.py' in evidence.command


def test_discovery_aliases_excludes_non_test_and_venv_files(tmp_path):
    (tmp_path / 'main.py').write_text('from unittest import TestCase as Case\nclass CSV(Case):\n def test_csv(self): pass\n')
    (tmp_path / 'narrative.py').write_text('class TestNotReal:\n def test_fake(self): pass\n')
    (tmp_path / '.venv').mkdir()
    (tmp_path / '.venv/ignore.py').write_text(SOURCE)
    assert discover_unittest_targets(tmp_path) == ['main.CSV']


@pytest.mark.asyncio
async def test_orchestrator_forwards_persisted_goal_and_reverifies_after_peer_repair(monkeypatch):
    from app.core.orchestrator import OrchestratorCore
    from app.agents import coordinator
    from app.recovery import engine as recovery_module
    from app.verification import engine as verification_module
    verify = AsyncMock(return_value=SimpleNamespace(all_passed=False, passed_checks=0, total_checks=1, evidence=[]))
    monkeypatch.setattr(verification_module, 'VerificationEngine', lambda **kw: SimpleNamespace(verify_task=verify))
    monkeypatch.setattr(recovery_module, 'RecoveryEngine', lambda **kw: SimpleNamespace())
    called = {}
    def create(**kwargs):
        called.update(kwargs)
        return SimpleNamespace(review_and_repair=AsyncMock(return_value=SimpleNamespace(
            summary='explicit fixture', repairs=['main.py'], clean=True)))
    monkeypatch.setattr(coordinator, 'AgentCoordinator', create)
    store = SimpleNamespace(get_task=AsyncMock(return_value=SimpleNamespace(goal='CSV converter', requirements=['unittest'])))
    self = SimpleNamespace(engine=object(), wm=object(), store=store)
    await OrchestratorCore._verify_and_repair(self, 'fixture')
    assert called['goal'] == 'CSV converter' and called['requirements'] == ['unittest']
    assert verify.await_count == 2


@pytest.mark.asyncio
async def test_debugger_prompt_includes_original_goal_and_actual_source(tmp_path, monkeypatch):
    from app.agents.roles import DebuggerRole
    from app.integrations import ai_universe_client
    engine = make_engine(tmp_path)
    monkeypatch.setattr(ai_universe_client, 'get_ai_universe_client', lambda: SimpleNamespace(
        consult_with_verification=AsyncMock(return_value=None)))
    from app.providers.direct import DirectProvider
    role = DebuggerRole(provider=DirectProvider())
    role.prompt_model = AsyncMock(return_value=SimpleNamespace(content='No usable patch.'))
    await role.execute_step('fixture', 'repair', {'goal': 'CSV converter', 'requirements': ['quoted commas'],
                                               'project_files': ['main.py'], 'error': 'unused import'}, engine)
    prompt = role.prompt_model.call_args.args[0]
    assert 'CSV converter' in prompt and 'quoted commas' in prompt
    assert SOURCE in prompt and 'never substitute a generic scaffold' in prompt
    assert engine.fs.read_file('fixture', 'main.py') == SOURCE
