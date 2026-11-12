"""Provider fixtures + real sandbox execution; no cloud/build acceptance claims."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agents.coordinator import AgentCoordinator
from app.agents.repair import MAX_REPAIR_SOURCE, validate_replacement
from app.agents.roles import DebuggerRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import TestChecker

SOURCE = '''import unittest

def add(a, b):
    return a - b

class AdditionTests(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(add(2, 3), 5)
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
'''
FIXED = SOURCE.replace('return a - b', 'return a + b')


def make_engine(tmp_path, source=SOURCE):
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path / 'workspaces'))
    wm.write_project_file('fixture', 'main.py', source)
    return ExecutionEngine(wm=wm)


def fake_client(monkeypatch, answer=FIXED, confidence=0.92):
    from app.integrations import ai_universe_client
    generate = AsyncMock(return_value=SimpleNamespace(answer=answer, confidence=confidence))
    monkeypatch.setattr(ai_universe_client, 'get_ai_universe_client', lambda: SimpleNamespace(generate_code=generate))
    return generate


@pytest.mark.asyncio
async def test_default_debugger_uses_actual_source_endpoint_and_real_suite_after_patch(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    before = await TestChecker().run_check('fixture', engine)
    assert not before.passed and before.exit_code == 1
    generate = fake_client(monkeypatch)
    role = DebuggerRole()
    role.prompt_model = AsyncMock(side_effect=AssertionError('default completion stub must not be used'))
    result = await role.execute_step('fixture', 'repair', {
        'goal': 'Addition utility', 'requirements': ['preserve API'],
        'project_files': ['main.py'], 'error': before.stderr}, engine)
    assert result['fixed_files'] == ['main.py'] and result['verification_required']
    payload = generate.await_args.kwargs
    assert payload['context']['repair']['original_source'] == SOURCE
    assert 'AssertionError' in payload['context']['repair']['failure_evidence']
    assert payload['context']['project_goal'] == 'Addition utility'
    role.prompt_model.assert_not_called()
    evidence = await TestChecker().run_check('fixture', engine)
    assert evidence.passed and evidence.exit_code == 0 and 'Ran 2 tests' in evidence.stderr
    assert engine.fs.read_file('fixture', 'main.py') == FIXED.strip()


@pytest.mark.asyncio
async def test_coordinator_runs_real_review_repair_rereview(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    generate = fake_client(monkeypatch)
    result = await AgentCoordinator(engine, goal='Addition utility', requirements=['preserve API']).review_and_repair('fixture')
    assert result.clean and result.repairs == ['main.py'] and result.findings_after == 0
    assert 'AssertionError' in generate.await_args.kwargs['context']['repair']['failure_evidence']


@pytest.mark.parametrize('candidate,reason', [
    (SOURCE, 'empty_or_unchanged'),
    ('def other():\n return 0', 'definition_removed_or_retyped'),
    (FIXED.replace('add(a, b)', 'add(a, b=0)', 1), 'signature_changed'),
    (FIXED.replace('self.assertEqual(add(2, 3), 5)', 'self.assertTrue(True)'), 'test_changed'),
    (FIXED.replace('def test_positive(self):', '@unittest.skip("ignore")\n    def test_positive(self):'), 'test_changed'),
    ('def invalid(', 'unparseable_source'),
])
def test_replacement_gate_rejects_test_mutation_api_loss_and_scaffolds(candidate, reason):
    assert validate_replacement(SOURCE, candidate).startswith(reason)


@pytest.mark.asyncio
@pytest.mark.parametrize('answer,confidence', [
    (FIXED.replace('self.assertEqual(add(2, 3), 5)', 'self.assertTrue(True)'), 0.92),
    ('### File: unrelated.py\n```python\nx = 1\n```', 0.92),
    (FIXED, 0.0),
    (SOURCE, 0.92),
    ('No safe repair is available.', 0.92),
])
async def test_rejected_proposals_never_change_original_source(tmp_path, monkeypatch, answer, confidence):
    engine = make_engine(tmp_path)
    fake_client(monkeypatch, answer, confidence)
    result = await DebuggerRole().execute_step('fixture', 'repair', {
        'goal': 'Addition utility', 'project_files': ['main.py'], 'error': 'failing assertion'}, engine)
    assert result['status'] == 'failed' and result['fixed_files'] == []
    assert engine.fs.read_file('fixture', 'main.py') == SOURCE
    assert result['rejections']


@pytest.mark.asyncio
async def test_external_test_files_and_oversize_source_are_not_rewritten(tmp_path, monkeypatch):
    engine = make_engine(tmp_path, '# x\n' * (MAX_REPAIR_SOURCE // 4 + 1))
    engine.wm.write_project_file('fixture', 'test_external.py', 'def test_external():\n assert False\n')
    generate = fake_client(monkeypatch)
    result = await DebuggerRole().execute_step('fixture', 'repair', {
        'goal': 'Addition utility', 'project_files': ['test_external.py', 'main.py']}, engine)
    assert result['fixed_files'] == []
    generate.assert_not_awaited()
    assert engine.fs.read_file('fixture', 'test_external.py').endswith('assert False\n')


@pytest.mark.asyncio
async def test_source_race_is_rejected(tmp_path, monkeypatch):
    engine = make_engine(tmp_path)
    generate = fake_client(monkeypatch)
    async def racing(**kwargs):
        engine.wm.write_project_file('fixture', 'main.py', SOURCE + '\n# concurrent change\n')
        return SimpleNamespace(answer=FIXED, confidence=0.92)
    generate.side_effect = racing
    result = await DebuggerRole().execute_step('fixture', 'repair', {
        'goal': 'Addition utility', 'project_files': ['main.py']}, engine)
    assert result['fixed_files'] == []
    assert 'source_changed_during_request:main.py' in result['rejections']
    assert engine.fs.read_file('fixture', 'main.py').endswith('# concurrent change\n')


@pytest.mark.asyncio
async def test_review_diagnostics_keep_traceback_after_many_passing_tests():
    text = 'test_first ... ok\n' + 'test_noise ... ok\n' * 2000 + '\nAssertionError: expected 5, got -1\n'
    checker = SimpleNamespace(run_check=AsyncMock(return_value=SimpleNamespace(
        passed=False, stderr=text, stdout='', issues=[], check_name='Embedded Unittest', exit_code=1)))
    coordinator = AgentCoordinator(object(), goal='Addition utility')
    coordinator._reviewers = {'test_engineer': checker}
    findings = await coordinator.review_workspace('fixture')
    assert 'test_first' in findings[0].detail
    assert 'AssertionError: expected 5, got -1' in findings[0].detail
    assert len(findings[0].detail) <= 12000
