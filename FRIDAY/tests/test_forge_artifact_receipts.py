"""Owner-facing reports preserve actual test command/exit and artifact paths."""
import pytest
from friday.tools.builtin.forge_code_task import _format_build


def test_real_manifest_test_command_exit_code_and_paths_are_rendered():
    data = {'manifest': {'stages': {'tests': {
        'category': 'test', 'check_name': 'Embedded Unittest Suite Runner',
        'passed': True, 'exit_code': 0, 'command': 'python -B -m unittest -v main.Tests'}}},
        'artifacts': ['/workspace/task/project/main.py', '/workspace/task/artifacts/verification_manifest.json']}
    reply = _format_build(data, 'Build verified')
    assert 'Test exit code: 0' in reply
    assert 'Test command: python -B -m unittest -v main.Tests' in reply
    assert '/workspace/task/project/main.py' in reply
    assert '/workspace/task/artifacts/verification_manifest.json' in reply


@pytest.mark.parametrize('exit_code,expected', [(None, 'not recorded'), (True, 'not recorded'), (1, '1')])
def test_unknown_or_failing_exit_code_never_becomes_zero(exit_code, expected):
    reply = _format_build({'manifest': {'stages': [{'category': 'test', 'passed': False, 'exit_code': exit_code}]}}, '')
    assert 'Test exit code: ' + expected in reply
    assert 'Test exit code: 0' not in reply


def test_build_only_manifest_does_not_invent_test_execution_or_paths():
    reply = _format_build({'manifest': {'stages': [{'category': 'build', 'passed': True, 'exit_code': 0}]}}, '')
    assert 'Test exit code:' not in reply
    assert 'Artifacts:' not in reply


def test_actual_saved_manifest_stage_field_and_dictionary_name_are_preserved():
    # This is the persisted shape observed in task2412112026193320, not the
    # checker's pre-serialization category/check_name shape.
    data = {'verification_manifest': {'stages': {'Embedded Unittest Suite Runner': {
        'stage': 'test', 'passed': True, 'exit_code': 0,
        'command': '"/opt/friday_universe/venv/bin/python" -B -m unittest -v main.TestCsvToJson'}}}}
    reply = _format_build(data, 'Same completed task, read-only status')
    assert 'Test exit code: 0 (Embedded Unittest Suite Runner)' in reply
    assert '-m unittest -v main.TestCsvToJson' in reply
    assert 'check_name' not in data['verification_manifest']['stages']['Embedded Unittest Suite Runner']
